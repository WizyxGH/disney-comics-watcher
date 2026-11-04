import requests
from urllib.parse import urljoin
import re
from datetime import date
from src.config import SERIE_NO_BASE, SERIE_NO_CATEGORIES
from src.utils import get_session
from src.dbi.isv_search import issue_code

NO_MONTHS = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12
}

def parse_date_no(s: str) -> date | None:
    if not s:
        return None
    # e.g. "fredag 9. oktober 2026"
    m = re.search(r'(\d{1,2})\.\s*([a-zA-ZæøåÆØÅ]+)\s*(\d{4})', s)
    if m:
        day = int(m.group(1))
        month_name = m.group(2).lower()
        year = int(m.group(3))
        month = NO_MONTHS.get(month_name)
        if month:
            return date(year, month, day)
    m2 = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', s)
    if m2:
        return date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
    return None

def _deduce_issue_path(title: str) -> str | None:
    t = title.strip()
    if m := re.search(r'(?:Donald Pocket|Pocket Donald)\s*(\d+)', t, re.I):
        return issue_code("no/DP", m.group(1))
    if m := re.search(r'Norsk Donald(?:\s*bokserie)?\s*(\d+)', t, re.I):
        return issue_code("no/ND", m.group(1))
    if m := re.search(r'Temapocket\s*(\d+)', t, re.I):
        return issue_code("no/TP", m.group(1))
    return None

def discover_no() -> list[dict]:
    """Discovers Norwegian Disney comics from Story House Egmont (serie.no)."""
    s = get_session()
    result = []
    seen = set()
    headers = {"X-PageLoad": "true"}

    for cat in SERIE_NO_CATEGORIES:
        url = urljoin(SERIE_NO_BASE, cat)
        try:
            r = s.get(url, headers=headers, timeout=15)
            if not r.ok:
                continue
            data = r.json()
            blocks = data.get("content", {}).get("content", {}).get("content", [])
            for block in blocks:
                bc = block.get("content", {})
                items = bc.get("search", {}).get("result", {}).get("items", [])
                if not items and "result" in bc:
                    items = bc["result"].get("items", [])

                for item in items:
                    item_id = item.get("id") or item.get("code")
                    if not item_id or item_id in seen:
                        continue
                    seen.add(item_id)

                    title = item.get("name", "").strip()
                    prod_rel_url = item.get("url", "")
                    prod_url = urljoin(SERIE_NO_BASE, prod_rel_url) if prod_rel_url else url

                    price_info = item.get("price") or {}
                    price_val = price_info.get("value")
                    price_cur = price_info.get("currency", "NOK")
                    price_str = f"{price_val} {price_cur}" if price_val is not None else None

                    img_src = item.get("mainImage", {}).get("src")
                    cover_url = urljoin(SERIE_NO_BASE, img_src) if img_src else None

                    result.append({
                        "id": str(item_id),
                        "title": title,
                        "url": prod_url,
                        "date": None,
                        "pub_date": None,
                        "price": price_str,
                        "cover_url": cover_url,
                        "issue_path": _deduce_issue_path(title),
                    })
        except Exception as e:
            print(f"  [warn] discover_no failed for {cat}: {e}")

    return result

def fetch_no_details(url: str) -> dict:
    """Fetches publication date, page count and full summary from product page."""
    s = get_session()
    details = {}
    try:
        r = s.get(url, headers={"X-PageLoad": "true"}, timeout=15)
        if r.ok:
            data = r.json()
            c = data.get("content", {})
            pub_date_str = c.get("info", {}).get("publicationDate", "")
            pub_date = parse_date_no(pub_date_str)
            if pub_date:
                details["pub_date"] = pub_date
                details["date"] = pub_date.strftime("%d/%m/%Y")

            desc = c.get("description", "")
            if desc:
                details["summary"] = desc.strip()
                m_pages = re.search(r'(\d+)\s*sider', desc, re.I)
                if m_pages:
                    details["pages"] = int(m_pages.group(1))

            meta_img = data.get("metadata", {}).get("metaImage", {}).get("src")
            if meta_img:
                details["cover_url"] = meta_img
    except Exception as e:
        print(f"  [warn] fetch_no_details for {url}: {e}")
    return details
