import json
import re
from bs4 import BeautifulSoup, NavigableString
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path

# All 12 WCBA member associations and their Staff page URLs
# All sites run on the mbsportsweb.ca platform with identical HTML structure
ASSOCIATIONS = [
    {"name": "Sarnia Brigade",                 "url": "https://sarniabrigade.ca/Staff/1003/"},
    {"name": "Alvinston Minor Ball",            "url": "https://alvinstonminorball.ca/Staff/1003/"},
    {"name": "Wallaceburg Minor Ball",          "url": "https://wallaceburgminorball.ca/Staff/1003/"},
    {"name": "Corunna Minor Baseball",          "url": "https://corunnaminorbaseball.com/Staff/1003/"},
    {"name": "Dresden Minor Ball",              "url": "https://dresdenminorball.com/Staff/1003/"},
    {"name": "Chatham Minor Baseball",          "url": "https://chathamminorbaseball.com/Staff/1103/"},
    {"name": "Lambton Shores Minor Ball",       "url": "https://lambtonshoresminorball.ca/Staff/1003/"},
    {"name": "Wyoming Minor Ball",              "url": "https://wyomingminorball.ca/Staff/1055/"},
    {"name": "Blenheim Minor Baseball",         "url": "https://blenheimminorbaseball.com/Staff/1113/"},
    {"name": "Camlachie Athletic Association",  "url": "https://camlachieathleticassociation.ca/Staff/1003/"},
    {"name": "Dutton Royals",                   "url": "https://duttonroyals.com/Staff/1113/"},
    {"name": "Port Lambton Pirates",            "url": "https://portlambtonpirates.ca/Staff/1023/"},
]

OUTPUT_FILE = Path("executives.json")

EMAIL_RE = re.compile(r"mailto:([\w\.\+\-]+@[\w\.\-]+)", re.I)
PHONE_RE = re.compile(r"(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})")
VCARD_RE = re.compile(r"/vcard/staff/", re.I)

# Role patterns ordered most-specific first; each maps to a canonical display name.
# "tre[sa]urer" handles Blenheim's misspelling "TRESURER".
ROLE_PATTERNS = [
    (r"(?:1st|first)\s+vice[\s\-]?president",  "Vice President"),
    (r"(?:2nd|second)\s+vice[\s\-]?president", "Vice President"),
    (r"vice[\s\-]?president",                  "Vice President"),
    (r"president",                              "President"),
    (r"secretary",                              "Secretary"),
    (r"tre[sa]urer",                            "Treasurer"),
]
ROLE_ORDER = ["President", "Vice President", "Secretary", "Treasurer"]


def fetch_html(url: str) -> str:
    """Return fully-rendered HTML for url using headless Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    return html


def find_person_container(vcard_a):
    """
    Walk UP the DOM from a vCard link until reaching a container that has
    MORE than one vCard link — then return the previous (single-vcard) level.
    That level is the per-person card.
    """
    last_single = vcard_a.parent or vcard_a
    current = vcard_a.parent
    while current is not None and current.parent is not None:
        n = len(current.find_all("a", href=VCARD_RE))
        if n == 1:
            last_single = current   # still one person at this level — keep going up
        elif n > 1:
            break                   # crossed into multi-person container — stop
        current = current.parent
    return last_single


def get_text_after_vcard(vcard_a, container) -> str:
    """
    Return text nodes that appear in document order AFTER the vCard link
    and BEFORE the next Email or vCard link, all within container.
    This skips UI labels ("Email", "Send", "CELL PHONE") that appear before
    the vCard and isolates the name + role text that follows it.
    """
    parts = []
    recording = False
    for elem in container.descendants:
        if elem is vcard_a:
            recording = True
            continue
        if not recording:
            continue
        # Stop when we hit the next person's Email or vCard link
        if hasattr(elem, "name") and elem.name == "a":
            href = elem.get("href", "")
            if VCARD_RE.search(href) or EMAIL_RE.search(href):
                break
        if isinstance(elem, NavigableString):
            # Skip text inside ANY ancestor <a> tag (handles nested spans etc.)
            if any(getattr(p, "name", None) == "a" for p in elem.parents):
                continue
            if elem.parent and elem.parent.name in ("script", "style", "button"):
                continue
            t = str(elem).strip()
            if t:
                parts.append(t)
    return " ".join(parts)


def parse_name_role(text: str):
    """
    Scan text for a target role keyword; return (name, display_role) or (None, None).
    Name is everything before the role match, cleaned up.
    """
    for pattern, display in ROLE_PATTERNS:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        # Exclude "Past President"
        prefix = text[max(0, m.start() - 10):m.start()].lower()
        if re.search(r"\bpast\b", prefix):
            continue
        name_raw = text[:m.start()]
        # Remove common page artefacts
        name_raw = re.sub(r"CELL\s+PHONE", " ", name_raw, flags=re.I)
        name_raw = PHONE_RE.sub(" ", name_raw)
        name = re.sub(r"\s+", " ", name_raw).strip()
        if name:
            return name, display
    return None, None


def extract_via_vcards(soup) -> list:
    """
    Primary extraction path for mbsportsweb.ca sites:
    Every staff member has a vCard link; we anchor on that to find the
    per-person container, then pull email, phone, name, and role.
    """
    results = []
    seen = set()

    for vcard_a in soup.find_all("a", href=VCARD_RE):
        container = find_person_container(vcard_a)

        # Email — from mailto: link inside the container
        email = ""
        mailto_a = container.find("a", href=EMAIL_RE)
        if mailto_a:
            m = EMAIL_RE.search(mailto_a["href"])
            if m:
                email = m.group(1)

        # Phone — from full text (tel: links and plain text)
        phone = ""
        pm = PHONE_RE.search(container.get_text(" ", strip=True))
        if pm:
            phone = pm.group(1)

        # Name + Role — from text that follows the vCard link (skips "Send", "Email" labels)
        clean = get_text_after_vcard(vcard_a, container)
        name, role = parse_name_role(clean)
        if not role or not name:
            continue

        key = (role.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "role": role,
            "name": name.title(),
            "phone": phone,
            "email": email,
        })

    return results


def extract_via_text(soup) -> list:
    """
    Fallback for sites (e.g. Blenheim) whose staff list is stored as plain text
    with no vCard links.

    With get_text(separator=newline, strip=True), each field lands on its own line:
        PRESIDENT
        Chris Knight
        knightcc@gmail.com
        VICE-PRESIDENT
        Mark VanDeVelde
        ...
    We scan for role-keyword lines then look ahead for name/email.
    """
    results = []
    seen = set()

    lines = [ln.strip() for ln in soup.get_text(separator="\n", strip=True).splitlines() if ln.strip()]

    ROLE_LINE_RE = re.compile(
        r'^((?:1st|2nd|first|second)\s+vice[\s\-]?president'
        r'|vice[\s\-]?president'
        r'|president'
        r'|secretary'
        r'|tre[sa]urer)$',
        re.I
    )
    EMAIL_LINE_RE = re.compile(r'^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,6}$', re.I)
    NAME_LINE_RE = re.compile(r'^[A-Za-z][A-Za-z\s\'\-\.]{1,40}$')

    for i, line in enumerate(lines):
        m = ROLE_LINE_RE.match(line)
        if not m:
            continue

        # Exclude "Past President"
        if i > 0 and "past" in lines[i - 1].lower():
            continue

        raw_role = m.group(1)
        name = ""
        email = ""

        # Look ahead up to 6 lines for name and email
        for j in range(i + 1, min(i + 7, len(lines))):
            candidate = lines[j].strip()
            # Stop if we hit the next role entry
            if ROLE_LINE_RE.match(candidate):
                break
            if not name and NAME_LINE_RE.match(candidate) and "@" not in candidate:
                name = candidate
            elif not email and EMAIL_LINE_RE.match(candidate):
                email = candidate

        if not name:
            continue

        # Map to canonical display role
        display = None
        for pattern, label in ROLE_PATTERNS:
            if re.fullmatch(pattern, raw_role, re.I):
                display = label
                break
        if not display:
            continue

        key = (display.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "role": display,
            "name": name.title(),
            "phone": "",
            "email": email,
        })

    results.sort(key=lambda r: (
        ROLE_ORDER.index(r["role"]) if r["role"] in ROLE_ORDER else 99,
        r["name"]
    ))
    return results


def extract_executives(assoc: dict) -> list:
    html = fetch_html(assoc["url"])
    soup = BeautifulSoup(html, "html.parser")

    results = extract_via_vcards(soup)
    if not results:
        results = extract_via_text(soup)

    results.sort(key=lambda r: (
        ROLE_ORDER.index(r["role"]) if r["role"] in ROLE_ORDER else 99,
        r["name"]
    ))
    return results


def main():
    all_execs = {}
    for assoc in ASSOCIATIONS:
        print(f"Scraping {assoc['name']}...")
        try:
            execs = extract_executives(assoc)
        except Exception as e:
            print(f"  ERROR: {e}")
            execs = []
        all_execs[assoc["name"]] = execs
        print(f"  Found {len(execs)}: {[e['role'] for e in execs]}")

    output = {
        "last_updated": datetime.now().isoformat(),
        "associations": all_execs,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nWrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

