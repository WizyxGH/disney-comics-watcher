"""Iceland: Syrpa pocket books from the Edda web shop (edda.is).

The shop lists every Syrpa still on sale, newest first, with a title that
carries the Inducks number ("Syrpa 401 – Týndur á tunglinu" is is/MS 401).
Jólasyrpa is yearly (is/JS2025). Risasyrpa has no number in the shop, so its
code is left to the title search.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.config import EDDA_SYRPUR_URL
from src.utils import get_session

# Only the head of the list matters: older Syrpur stay on sale for years.
_LATEST = 12


def _issue_path(title: str) -> str | None:
    if m := re.match(r"Syrpa (\d+)\b", title):
        return f"is/MS {m.group(1)}"
    if m := re.match(r"J[ÓO]LASYRPA (\d{4})\b", title, re.I):
        return f"is/JS{m.group(1)}"
    return None


def discover_is():
    try:
        r = get_session().get(EDDA_SYRPUR_URL, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [warn] discover_is: {e}")
        return []

    results = []
    for li in BeautifulSoup(r.text, "html.parser").select("ul.productgrid > li")[:_LATEST]:
        link = li.select_one("a.productTitle")
        if not link or "productid=" not in link.get("href", ""):
            continue
        title = link.get_text(strip=True)
        img = li.select_one(".picture img")
        price = li.select_one("p.price span")
        results.append({
            "id": link["href"].split("productid=")[1][:36],
            "title": title,
            "url": urljoin(EDDA_SYRPUR_URL, link["href"]),
            "issue_path": _issue_path(title),
            "cover_url": urljoin(EDDA_SYRPUR_URL, img["src"].split("?")[0]) if img else None,
            # "1.850.-": dots are thousands separators, the krona has no decimals.
            "price": f"{re.sub(r'[^0-9]', '', price.get_text())} ISK" if price else None,
        })
    return results


def fetch_is_details(url: str) -> dict:
    """Page count from the product page ("Kilja, 256 síður")."""
    try:
        r = get_session().get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [warn] fetch_is_details: {e}")
        return {}
    m = re.search(r"(\d+)\s*síður", r.text)
    return {"pages": int(m.group(1))} if m else {}
