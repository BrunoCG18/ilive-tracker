"""
Scraper for Campus Living Darmstadt apartment availability.
Fetches https://www.campus-living-darmstadt.de/mieten and extracts apartment statuses.
"""

import re
import html as html_lib
import requests
from bs4 import BeautifulSoup

URL = "https://www.campus-living-darmstadt.de/mieten"

STATUS_FREE = "free"
STATUS_RESERVED = "reserved"
STATUS_OCCUPIED = "occupied"
STATUS_UNKNOWN = "unknown"


def fetch_page(url=URL):
    """Fetch the rental page HTML."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def _detect_status(classes):
    """Detect status from CSS class list."""
    class_str = " ".join(classes).lower()
    if "free" in class_str:
        return STATUS_FREE
    if "reserved" in class_str:
        return STATUS_RESERVED
    if "occupied" in class_str:
        return STATUS_OCCUPIED
    return STATUS_UNKNOWN


def _detect_status_from_data_text(data_text):
    """Detect status from the data-text attribute HTML content."""
    if not data_text:
        return STATUS_UNKNOWN
    # Double-unescape since the attribute can be double-encoded
    text = html_lib.unescape(html_lib.unescape(data_text))
    if "unit_free" in text:
        return STATUS_FREE
    if "unit_reserved" in text:
        return STATUS_RESERVED
    if "unit_occupied" in text:
        return STATUS_OCCUPIED
    return STATUS_UNKNOWN


def _parse_data_text(data_text):
    """
    Parse the data-text attribute which contains apartment details as HTML.
    Example: Erdgeschoss<br>mit Terrasse<br>Ost-Ausrichtung<br>Bett: 120 x 200 cm<br>
             Größe: 24.19 m²<br><br>Miethöhe: 551 €<br>Nebenkosten: 167 €<br>
             Status: <span class=unit_occupied>vermietet</span>
    """
    if not data_text:
        return {}

    # Double-unescape since the attribute can be double-encoded
    text = html_lib.unescape(html_lib.unescape(data_text))
    parts = re.split(r"<br\s*/?>", text)
    details = {}

    for part in parts:
        clean = re.sub(r"<[^>]+>", "", part).strip()
        if not clean:
            continue
        if ":" in clean:
            key, _, val = clean.partition(":")
            details[key.strip()] = val.strip()

    return details


def parse_apartments(html):
    """
    Parse the HTML and extract apartment information with availability status.
    Returns a dict mapping apartment ID to info dict.
    """
    soup = BeautifulSoup(html, "html.parser")
    apartments = {}

    # Apartments are <a> tags with class "apartment" and href="#detail"
    apt_links = soup.find_all("a", class_="apartment", href="#detail")

    seen = set()
    for link in apt_links:
        apt_number = link.get_text(strip=True)
        if not apt_number or apt_number in seen:
            continue
        seen.add(apt_number)

        classes = link.get("class", [])
        title = link.get("title", "").strip()
        data_text = link.get("data-text", "")

        # Type from title (e.g., "Komfort-Apartment Nr. 0.1")
        apt_type = re.sub(r"\s*Nr\.\s*\S+\s*$", "", title).strip()

        # Try CSS classes first, fall back to data-text content
        status = _detect_status(classes)
        if status == STATUS_UNKNOWN:
            status = _detect_status_from_data_text(data_text)
        details = _parse_data_text(data_text)

        kaltmiete_str = details.get("Miethöhe", "")
        nebenkosten_str = details.get("Nebenkosten", "")

        # Parse numeric values (e.g., "695 €" -> 695)
        kaltmiete = 0
        nebenkosten = 0
        if kaltmiete_str:
            m = re.search(r"(\d+)", kaltmiete_str)
            if m:
                kaltmiete = int(m.group(1))
        if nebenkosten_str:
            m = re.search(r"(\d+)", nebenkosten_str)
            if m:
                nebenkosten = int(m.group(1))

        total = kaltmiete + nebenkosten

        apartments[apt_number] = {
            "name": f"Apartment {apt_number}",
            "type": apt_type or "Unknown",
            "status": status,
            "size": details.get("Größe", ""),
            "kaltmiete": f"{kaltmiete} €" if kaltmiete else "",
            "nebenkosten": f"{nebenkosten} €" if nebenkosten else "",
            "total": f"{total} €" if total else "",
        }

    return apartments


def get_apartments():
    """Fetch and parse current apartment availability. Main entry point."""
    html = fetch_page()
    return parse_apartments(html)


if __name__ == "__main__":
    print("Fetching page...")
    html = fetch_page()

    print("Parsing apartments...")
    apts = parse_apartments(html)

    if not apts:
        print("No apartments found! The page structure may have changed.")
    else:
        free = {k: v for k, v in apts.items() if v["status"] == STATUS_FREE}
        reserved = {k: v for k, v in apts.items() if v["status"] == STATUS_RESERVED}
        occupied = {k: v for k, v in apts.items() if v["status"] == STATUS_OCCUPIED}
        unknown = {k: v for k, v in apts.items() if v["status"] == STATUS_UNKNOWN}

        print(f"\nFound {len(apts)} apartments:")
        print(f"  Free:     {len(free)}")
        print(f"  Reserved: {len(reserved)}")
        print(f"  Occupied: {len(occupied)}")
        print(f"  Unknown:  {len(unknown)}")

        if free:
            print("\nFREE apartments:")
            for apt_id, info in sorted(free.items()):
                print(f"  {info['name']} - {info['type']} - {info['size']} - Total: {info['total']}")

        if reserved:
            print(f"\nReserved apartments (first 5):")
            for apt_id, info in list(sorted(reserved.items()))[:5]:
                print(f"  {info['name']} - {info['type']} - {info['size']} - Total: {info['total']}")
