#!/usr/bin/env python3
"""WCBA in-progress certification scraper.

Uses Playwright to capture Wix cloud-data API responses and rendered HTML.
Cloud-data is used as the primary source, and rendered HTML fills any gaps.
All target locals are always emitted in data.json (count may be 0).
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

URL = "https://www.registeroba.ca/certification-inprogress-by-local"
DATA_FILE = Path("data.json")

TARGET_LOCALS = [
    "Alvinston",
    "Blenheim",
    "Chatham",
    "Corunna",
    "Dresden",
    "Dutton",
    "Lambton Shores",
    "Port Lambton",
    "Sarnia",
    "Wallaceburg",
    "Wyoming",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def target_local_for(raw_local: str) -> str | None:
    candidate = normalize(raw_local)
    for local in TARGET_LOCALS:
        if normalize(local) == candidate:
            return local
    return None


def fetch_cloud_data_items(url: str) -> List[dict]:
    captured: Dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_response(resp) -> None:
            if "/_api/cloud-data/v2/items/query" not in resp.url or resp.status != 200:
                return
            try:
                payload = resp.json()
            except Exception:
                return

            items = payload.get("items") or payload.get("dataItems") or []
            for item in items:
                item_id = item.get("id") or item.get("_id")
                if item_id:
                    captured[item_id] = item

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(3000)
        finally:
            browser.close()

    return list(captured.values())


def get_rendered_html(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass

            try:
                page.wait_for_selector("tr td", timeout=15000)
            except PlaywrightTimeoutError:
                pass

            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        print(f"Playwright HTML render failed ({exc}); falling back to requests.")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text


def rows_from_cloud_items(items: List[dict]) -> Dict[str, List[dict]]:
    locals_dict: Dict[str, List[dict]] = {}

    for item in items:
        data = item.get("data", {})
        name = str(data.get("title", "")).strip()
        reg_id = str(data.get("nccp", "")).strip()
        position = str(data.get("position", "")).strip()
        local_raw = str(data.get("team", "")).strip()

        if not name or not position or not local_raw:
            continue

        local = target_local_for(local_raw)
        if not local:
            continue

        if local not in locals_dict:
            locals_dict[local] = []

        exists = any(
            c["name"] == name and c["reg_id"] == reg_id and c["position"] == position
            for c in locals_dict[local]
        )
        if not exists:
            locals_dict[local].append(
                {
                    "name": name,
                    "position": position,
                    "reg_id": reg_id,
                }
            )

    return locals_dict


def rows_from_html(html: str) -> Dict[str, List[dict]]:
    locals_dict: Dict[str, List[dict]] = {}
    soup = BeautifulSoup(html, "html.parser")

    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 4:
            continue

        # Column order in this table: Local, Name, Position, Registration ID
        local_raw = cells[0]
        name = cells[1]
        position = cells[2]
        reg_id = cells[3]

        if not local_raw or not name:
            continue

        if normalize(local_raw) in {"loading...", "local", "association"}:
            continue
        if normalize(name) in {"loading...", "name"}:
            continue

        local = target_local_for(local_raw)
        if not local:
            continue

        if local not in locals_dict:
            locals_dict[local] = []

        exists = any(
            c["name"] == name and c["reg_id"] == reg_id and c["position"] == position
            for c in locals_dict[local]
        )
        if not exists:
            locals_dict[local].append(
                {
                    "name": name,
                    "position": position,
                    "reg_id": reg_id,
                }
            )

    return locals_dict


def merge_sources(primary: Dict[str, List[dict]], fallback: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
    merged = {k: list(v) for k, v in primary.items()}

    for local, coaches in fallback.items():
        if local not in merged:
            merged[local] = list(coaches)
            continue

        known = {
            (c["name"], c.get("reg_id", ""), c.get("position", ""))
            for c in merged[local]
        }
        for coach in coaches:
            key = (coach["name"], coach.get("reg_id", ""), coach.get("position", ""))
            if key not in known:
                merged[local].append(coach)
                known.add(key)

    for local in merged:
        merged[local].sort(key=lambda c: normalize(c["name"]))

    return merged


def scrape_coaches() -> Dict[str, List[dict]]:
    print(f"Scraping {URL}")

    cloud_rows: Dict[str, List[dict]] = {}
    html_rows: Dict[str, List[dict]] = {}

    try:
        cloud_items = fetch_cloud_data_items(URL)
        print(f"Captured {len(cloud_items)} cloud-data items")
        if cloud_items:
            cloud_rows = rows_from_cloud_items(cloud_items)
            print(f"Cloud-data yielded {len(cloud_rows)} locals")
    except Exception as exc:
        print(f"Cloud-data capture failed: {exc}")

    try:
        html = get_rendered_html(URL)
        html_rows = rows_from_html(html)
        print(f"HTML parse yielded {len(html_rows)} locals")
    except Exception as exc:
        print(f"HTML parse failed: {exc}")

    if not cloud_rows and not html_rows:
        raise RuntimeError("No coach data extracted from cloud-data or HTML")

    merged = merge_sources(cloud_rows, html_rows)
    print(f"Merged source contains {len(merged)} locals with coaches")
    return merged


def build_output_data(coaches_by_local: Dict[str, List[dict]]) -> dict:
    locals_section = {}
    total = 0

    for local in TARGET_LOCALS:
        coaches = coaches_by_local.get(local, [])
        locals_section[local] = {
            "count": len(coaches),
            "coaches": coaches,
        }
        total += len(coaches)

    return {
        "last_updated": datetime.now().isoformat(),
        "updates_at": "8:00 AM Eastern",
        "total_coaches": total,
        "locals": locals_section,
    }


def save_data(output_data: dict) -> None:
    DATA_FILE.write_text(json.dumps(output_data, indent=2), encoding="utf-8")


def print_summary(output_data: dict) -> None:
    print("\nData summary:")
    for local in TARGET_LOCALS:
        count = output_data["locals"][local]["count"]
        print(f"  {local}: {count}")
    print(f"Total coaches: {output_data['total_coaches']}")


def main() -> int:
    try:
        coaches_by_local = scrape_coaches()
        output_data = build_output_data(coaches_by_local)
        save_data(output_data)
        print_summary(output_data)
        print(f"\nSaved to {DATA_FILE}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
