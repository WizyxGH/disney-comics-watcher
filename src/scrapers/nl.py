import re
from datetime import datetime
from src.config import DONALDDUCK_NL_BASE, DONALDDUCK_NL_COLLECTIONS
from src.utils import get_session
from src.dbi.isv_search import issue_code

def _deduce_issue_path(title: str) -> str | None:
    t = title.strip()
    if m := re.search(r'Club Donald Duck Pocket\s*(\d+)', t, re.I):
        return issue_code("nl/CDDP", m.group(1))
    if m := re.search(r'Donald Duck Pocket\s*(\d+)', t, re.I):
        return issue_code("nl/PO3", m.group(1))
    if m := re.search(r'Dubbelpocket(?:\s*Donald Duck)?\s*(\d+)', t, re.I):
        return issue_code("nl/DUP", m.group(1))
    if m := re.search(r'Donald Duck Themapocket\s*(\d+)', t, re.I):
        return issue_code("nl/DUPX", m.group(1))
    if m := re.search(r'Donald Duck Megapocket\s*(\d+)', t, re.I):
        return issue_code("nl/MP", m.group(1))
    if m := re.search(r'Katrien(?: Duck)? Pocket\s*(\d+)', t, re.I):
        return issue_code("nl/KP", m.group(1))
    return None

def discover_nl() -> list[dict]:
    """Discovers Netherlands Disney comic books from the official Donald Duck Shop (Shopify)."""
    s = get_session()
    result = []
    seen = set()

    for col in DONALDDUCK_NL_COLLECTIONS:
        url = f"{DONALDDUCK_NL_BASE}/collections/{col}/products.json?limit=250"
        try:
            r = s.get(url, timeout=15)
            if not r.ok:
                continue
            products = r.json().get("products", [])
            for prod in products:
                prod_id = prod.get("id")
                if not prod_id or prod_id in seen:
                    continue
                seen.add(prod_id)

                title = prod.get("title", "").strip()
                handle = prod.get("handle", "")
                prod_url = f"{DONALDDUCK_NL_BASE}/products/{handle}" if handle else DONALDDUCK_NL_BASE

                variants = prod.get("variants", [])
                first_var = variants[0] if variants else {}
                sku = first_var.get("sku") or ""
                price_val = first_var.get("price")
                price_str = f"{price_val} €" if price_val else None

                images = prod.get("images", [])
                cover_url = images[0].get("src") if images else None

                date_str = prod.get("published_at") or prod.get("created_at") or ""
                pub_date = None
                date_str_fr = ""
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str)
                        pub_date = dt.date()
                        date_str_fr = pub_date.strftime("%d/%m/%Y")
                    except Exception:
                        date_str_fr = date_str

                # Clean summary
                body_html = prod.get("body_html") or ""
                summary = re.sub(r'<[^>]+>', ' ', body_html).strip()
                summary = re.sub(r'\s+', ' ', summary)

                result.append({
                    "id": prod_id,
                    "sku": sku,
                    "title": title,
                    "url": prod_url,
                    "date": date_str_fr,
                    "pub_date": pub_date,
                    "price": price_str,
                    "cover_url": cover_url,
                    "summary": summary if summary else None,
                    "issue_path": _deduce_issue_path(title),
                })
        except Exception as e:
            print(f"  [warn] discover_nl failed for collection {col}: {e}")

    return result

def fetch_nl_details(url: str) -> dict:
    """Fetches barcode / EAN from product .js endpoint on Shopify."""
    s = get_session()
    details = {}
    try:
        clean_url = url.split("?")[0].rstrip("/")
        r = s.get(f"{clean_url}.js", timeout=10)
        if r.ok:
            data = r.json()
            variants = data.get("variants", [])
            if variants:
                barcode = variants[0].get("barcode")
                if barcode:
                    details["ean"] = str(barcode).strip()
    except Exception as e:
        print(f"  [warn] fetch_nl_details for {url}: {e}")
    return details
