"""Denmark: Disney releases from the official Story House Egmont portal (andeby.dk).

Fetches the official annual publishing schedules for Anders And & Co., Jumbobog,
Temabog, Anders And Classic, and Anders And Junior via the WordPress REST API.
"""

import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from src.config import ANDEBY_DK_API_BASE
from src.utils import get_session

_DK_SCHEDULES = [
    ("udgivelse-aa", "dk/AA", "Anders And & Co.", "https://cdn.egmontservice.com/Publication/Cover/AND__b600m.jpg"),
    ("udgivelse-jumbo", "dk/JB", "Jumbobog", "https://cdn.egmontservice.com/Publication/Cover/JUM__b600m.jpg"),
    ("udgivelse-tema", "dk/JT", "Temabog", "https://www.andeby.dk/app/uploads/TEMA.jpg"),
    ("udgivelse-aac", "dk/AAC", "Anders And Classic", "https://cdn.egmontservice.com/Publication/Cover/AAC__b600m.jpg"),
    ("udgivelse-aaj", "dk/AJ", "Anders And Junior", "https://cdn.egmontservice.com/Publication/Cover/AAJ__b600m.jpg"),
]


def _build_issue_path(pubcode: str, num_str: str, year: int) -> str | None:
    try:
        if pubcode == "dk/AA":
            if "+" in num_str:
                p1, p2 = num_str.split("+")
                code_num = f"{int(p1):02d}-{int(p2):02d}"
            else:
                code_num = f"{int(num_str):02d}"
            return f"dk/AA{year}-{code_num}"

        idx = int(num_str)
        if pubcode == "dk/JB":
            actual_num = 556 + idx + (year - 2026) * 12
            return f"dk/JB  {actual_num}"
        if pubcode == "dk/JT":
            actual_num = 130 + idx + (year - 2026) * 6
            return f"dk/JT  {actual_num}"
        if pubcode == "dk/AAC":
            actual_num = 66 + idx + (year - 2026) * 6
            return f"dk/AAC{year}-{actual_num}"
        if pubcode == "dk/AJ":
            return f"dk/AJ{year}-{idx:02d}"
    except (ValueError, TypeError):
        return None
    return None


def _cover_last_modified(s, url: str) -> date | None:
    """Returns the Last-Modified date of an Egmont CDN cover, or None if unavailable."""
    try:
        r = s.head(url, timeout=5)
        lm = r.headers.get("Last-Modified")
        if lm:
            return parsedate_to_datetime(lm).date()
    except Exception:
        pass
    return None


def _cover_for_issue(base_cover: str, cover_lm: date | None, pub_date: date) -> str | None:
    """Egmont CDN reuses a single static URL (e.g. AND__b600m.jpg) and only updates it
    sporadically. Only attach it when its Last-Modified date matches this issue's release
    window, with a date query param so Telegram never serves a cached older cover."""
    if not base_cover or not cover_lm:
        return None
    if pub_date - timedelta(days=10) <= cover_lm <= pub_date + timedelta(days=7):
        return f"{base_cover}?d={cover_lm.strftime('%Y%m%d')}"
    return None


def discover_dk() -> list[dict]:
    """Discovers Danish Disney comic books from andeby.dk official release plans."""
    s = get_session()
    result = []
    seen = set()

    for slug, pubcode, series_name, default_cover in _DK_SCHEDULES:
        url = f"{ANDEBY_DK_API_BASE}/pages?slug={slug}"
        try:
            r = s.get(url, timeout=15)
            if not r.ok or not r.json():
                continue
            page_data = r.json()[0]
            page_link = page_data.get("link", "https://www.andeby.dk/udgivelsesplan/")
            content_html = page_data.get("content", {}).get("rendered", "")
            soup = BeautifulSoup(content_html, "html.parser")

            # Check if there is an updated cover image in the page content
            base_cover = default_cover
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if src and any(ext in src.lower() for ext in (".jpg", ".jpeg", ".png")):
                    base_cover = src
                    break
            cover_lm = _cover_last_modified(s, base_cover)

            for tr in soup.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(tds) < 2 or not tds[0] or not tds[1]:
                    continue

                pairs = []
                if len(tds) >= 4 and tds[2] and tds[3]:
                    pairs.append((tds[0], tds[1]))
                    pairs.append((tds[2], tds[3]))
                else:
                    pairs.append((tds[0], tds[1]))

                for num_str, date_str in pairs:
                    if not num_str or not date_str or "." not in date_str:
                        continue
                    try:
                        d, m, y = map(int, date_str.split("."))
                        pub_date = date(y, m, d)
                        date_str_fr = pub_date.strftime("%d/%m/%Y")
                    except Exception:
                        continue

                    issue_id = f"{slug}_{num_str}_{y}"
                    if issue_id in seen:
                        continue
                    seen.add(issue_id)

                    path = _build_issue_path(pubcode, num_str, y)
                    clean_title = f"{series_name} nr. {num_str} ({y})"

                    result.append({
                        "id": issue_id,
                        "title": clean_title,
                        "url": page_link,
                        "date": date_str_fr,
                        "pub_date": pub_date,
                        "issue_path": path,
                        "cover_url": _cover_for_issue(base_cover, cover_lm, pub_date),
                        "price": None,
                    })

        except Exception as e:
            print(f"  [warn] discover_dk failed for {slug}: {e}")

    return result


def fetch_dk_details(url: str) -> dict:
    """Fetches additional details from product page if needed."""
    return {}
