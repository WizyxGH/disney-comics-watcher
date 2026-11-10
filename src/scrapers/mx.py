import re
from bs4 import BeautifulSoup
from src.utils import get_session
from src.scrapers.shared_panini import discover_panini_magento, fetch_panini_magento_details

PANINI_MX_BASE = "https://tiendapanini.com.mx"

def discover_panini_mx() -> list[dict]:
    """Discovers Disney comics on Panini Mexico."""
    search_terms = ["disney", "donald", "mickey"]
    results = []
    seen = set()

    for term in search_terms:
        url = f"{PANINI_MX_BASE}/catalogsearch/result/?q={term}"
        items = discover_panini_magento(url, "MX")
        for item in items:
            item_id = item.get("id") or item.get("url")
            if not item_id or item_id in seen:
                continue

            title = item.get("title", "")
            title_lower = title.lower()

            # Filter for Disney related titles
            disney_keywords = [
                "disney", "donald", "mickey", "tio rico", "tío rico",
                "carl barks", "don rosa", "patoaventuras", "ducktales",
                "fantomiald", "scrooge"
            ]
            if not any(k in title_lower for k in disney_keywords):
                continue

            seen.add(item_id)
            results.append(item)

    return results

def fetch_panini_mx_details(url: str) -> dict:
    """Fetches details (high-res cover, date, ean) from Panini Mexico product page."""
    details = fetch_panini_magento_details(url, "MX")
    if not url:
        return details

    try:
        s = get_session()
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Extract EAN / ISBN from product attributes
            ean_elem = soup.select_one('.product.attribute.sku .value, [itemprop="sku"], .attribute.ean .value')
            if ean_elem:
                val = ean_elem.get_text(strip=True)
                if val.isdigit() and len(val) >= 10:
                    details["ean"] = val

            # Extract page count
            pages_match = re.search(r'(\d+)\s*(?:páginas|pags|págs)', r.text, re.IGNORECASE)
            if pages_match:
                details["pages"] = int(pages_match.group(1))
    except Exception as e:
        print(f"  [warn] fetch_panini_mx_details: {e}")

    return details
