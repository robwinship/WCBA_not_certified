import json
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path

# List of associations and their executive/staff URLs
ASSOCIATIONS = [
    {
        "name": "Sarnia Brigade",
        "url": "https://sarniabrigade.ca/Staff/1003/"
    },
    {
        "name": "Alvinston Minor Ball",
        "url": "https://alvinstonminorball.ca/Contact/1005/"
    },
    {
        "name": "Blenheim Minor Baseball",
        "url": "https://blenheimminorbaseball.com/Staff/1113/"
    },
    {
        "name": "Camlachie Athletic Association",
        "url": "https://camlachieathleticassociation.ca/Staff/1003/"
    }
]

OUTPUT_FILE = Path("executives.json")

# Helper to extract email from a mailto link
EMAIL_RE = re.compile(r"mailto:([\w\.-]+@[\w\.-]+)")
PHONE_RE = re.compile(r"(\d{3}[ -]?\d{3}[ -]?\d{4})")

def extract_executives(assoc):
    # Use Playwright to get fully rendered HTML
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(assoc["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    # 1. Special handling for Alvinston Minor Ball: extract name and role from text after mailto
    if assoc["name"] == "Alvinston Minor Ball":
        # Find all mailto links and extract name, role, email from nearby text
        for a in soup.find_all("a", href=EMAIL_RE):
            email_match = EMAIL_RE.search(a["href"])
            email = email_match.group(1) if email_match else ""
            # The parent is likely a div, get previous siblings for name/role
            parent = a.find_parent()
            # Get all text before the mailto link in the parent
            text = ""
            for elem in parent.contents:
                if elem == a:
                    break
                if isinstance(elem, str):
                    text += elem.strip() + " "
                elif hasattr(elem, 'get_text'):
                    text += elem.get_text(" ", strip=True) + " "
            text = text.strip()
            # Try to extract name and role (e.g., 'Andy Triest President')
            m = re.match(r"([A-Za-z .'-]+)\s+([A-Za-z ]+)$", text)
            if m:
                name = m.group(1).strip()
                role = m.group(2).strip()
            else:
                name = text
                role = ""
            rows.append({
                "role": role,
                "name": name,
                "phone": "",
                "email": email
            })
    else:
        # 1. Try to extract from mailto links (most reliable for email/name/role)
        for a in soup.find_all("a", href=EMAIL_RE):
            email_match = EMAIL_RE.search(a["href"])
            email = email_match.group(1) if email_match else ""
            parent = a.find_parent()
            text = parent.get_text(" ", strip=True)
            role_match = re.search(r"(president|treasurer|secretary|vice[- ]?president|registrar|scheduler)", text, re.I)
            role = role_match.group(0).title() if role_match else "Executive"
            name = ""
            name_match = re.search(r"([A-Z][A-Za-z .'-]+)[^A-Za-z]*(?=" + role + ")", text)
            if name_match:
                name = name_match.group(1).strip()
            else:
                name_match = re.search(r"([A-Z][A-Za-z .'-]+)[^A-Za-z]*(?=" + email + ")", text)
                if name_match:
                    name = name_match.group(1).strip()
            phone = ""
            phone_match = PHONE_RE.search(text)
            if phone_match:
                phone = phone_match.group(1)
            rows.append({
                "role": role,
                "name": name,
                "phone": phone,
                "email": email
            })

    # 2. Try to extract from tables (for Blenheim and similar)
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) >= 3:
                # Heuristic: Role, Name, Email/Phone
                role = cells[0].title()
                name = cells[1].strip()
                email = ""
                phone = ""
                for c in cells[2:]:
                    if EMAIL_RE.search(c):
                        email = EMAIL_RE.search(c).group(1)
                    if PHONE_RE.search(c):
                        phone = PHONE_RE.search(c).group(1)
                if name and role:
                    rows.append({
                        "role": role,
                        "name": name,
                        "phone": phone,
                        "email": email
                    })

    # 3. Try to extract from divs/spans with role keywords
    for tag in soup.find_all(string=re.compile(r"president|treasurer|secretary|vice", re.I)):
        parent = tag.find_parent()
        if not parent:
            continue
        text = parent.get_text(" ", strip=True)
        role_match = re.search(r"(president|treasurer|secretary|vice[- ]?president|registrar|scheduler)", text, re.I)
        role = role_match.group(0).title() if role_match else "Executive"
        name = ""
        name_match = re.search(r"([A-Z][A-Za-z .'-]+)[^A-Za-z]*(?=" + role + ")", text)
        if name_match:
            name = name_match.group(1).strip()
        email = ""
        mailto = parent.find("a", href=EMAIL_RE)
        if mailto:
            email_match = EMAIL_RE.search(mailto["href"])
            if email_match:
                email = email_match.group(1)
        phone = ""
        phone_match = PHONE_RE.search(text)
        if phone_match:
            phone = phone_match.group(1)
        if name and role:
            rows.append({
                "role": role,
                "name": name,
                "phone": phone,
                "email": email
            })

    # Remove duplicates
    seen = set()
    unique_rows = []
    for row in rows:
        key = (row["role"].lower(), row["name"].lower())
        if key not in seen and row["name"]:
            unique_rows.append(row)
            seen.add(key)
    return unique_rows

def main():
    all_execs = {}
    for assoc in ASSOCIATIONS:
        execs = extract_executives(assoc)
        all_execs[assoc["name"]] = execs
    output = {
        "last_updated": datetime.now().isoformat(),
        "associations": all_execs
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
