import re
import html as html_lib
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import http.client
import concurrent.futures
http.client._MAXHEADERS = 1000

from src.utils import get_session

GREEK_PUB_MAP = {
    "464B": "gr/MMB",
    "464D": "gr/KXB",
    "464A": "gr/NTB",
    "464C": "gr/SMB",
    "464E": "gr/ECA"
}

GREEK_PRICES = {
    "464B": "1,90 €",
    "464A": "1,90 €",
    "464D": "3,50 €",
    "464C": "3,90 €",
    "464E": "4,50 €",
}

CID_MAP = {
    "μίκυ μάους": "464B", "miky": "464B",
    "κόμιξ": "464D", "komix": "464D",
    "ντόναλντ": "464A", "donald": "464A",
    "super miky": "464C", "σούπερ μίκυ": "464C",
    "editor": "464E", "επιλογή": "464E",
}


def _process_kathimerini_article(a_tag, s: requests.Session) -> dict | None:
    p_title = a_tag.find('p', class_='title')
    if not p_title or '#' not in p_title.text:
        return None

    title_text = p_title.text.strip()
    url = a_tag['href']
    title_lower = title_text.lower()

    cid = None
    for k, v in CID_MAP.items():
        if k in title_lower:
            cid = v
            break

    # Extract issue number
    m_num = re.search(r'#?\s*(\d{1,4})\b', title_text)
    issue_nr = m_num.group(1) if m_num else ""
    canonical_issue_path = f"{GREEK_PUB_MAP[cid]} {issue_nr}" if (cid in GREEK_PUB_MAP and issue_nr) else None

    # Extract a unique ID from the URL (e.g. 564262477)
    m_id = re.search(r'/(\d+)/', url)
    art_id = m_id.group(1) if m_id else url.strip('/').split('/')[-1]

    # Fetch article details
    date_val = None
    date_iso_digits = None
    article_html_content = None
    art_img = None

    try:
        r_art = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r_art.status_code == 200:
            article_html_content = r_art.text
            art_soup = BeautifulSoup(r_art.text, 'html.parser')

            # 1. Official Kathimerini article image (strip WordPress resizing for full resolution)
            for img in art_soup.find_all('img'):
                src = img.get('src', '')
                if src and 'uploads' in src and src.startswith('http'):
                    art_img = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', src.split('?')[0])
                    break

            # 2. Check body text for actual kiosk release date (e.g. "αυτή την Παρασκευή 20/11")
            body_text = art_soup.get_text()
            m_rel = re.search(r'(?:παρασκευή|τετάρτη|κυκλοφορε[ίι]|περίπτερα)[^0-9\n]*(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?', body_text, re.IGNORECASE)
            if m_rel:
                d = int(m_rel.group(1))
                m_val = int(m_rel.group(2))
                y = int(m_rel.group(3)) if m_rel.group(3) else datetime.now().year
                if y < 100:
                    y += 2000
                date_val = f"{d:02d}/{m_val:02d}/{y}"
                date_iso_digits = f"{y:04d}{m_val:02d}{d:02d}"
            else:
                time_elem = art_soup.find('time')
                if time_elem:
                    m_date = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', time_elem.text)
                    if m_date:
                        d, m_val, y = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
                        date_val = f"{d:02d}/{m_val:02d}/{y}"
                        date_iso_digits = f"{y:04d}{m_val:02d}{d:02d}"
    except Exception as e:
        print(f"  [warn] Failed to fetch Kathimerini article {url}: {e}")

    # 3. Determine the correct cover URL:
    # If PressReader already published this exact issue (head check == 200), use its HD 2D cover.
    # Otherwise (pre-announcement or older archive not on PressReader), use the official Kathimerini article illustration.
    cover_url = None
    if cid and date_iso_digits:
        pr_dated_url = f"https://i.prcdn.co/img?file={cid.lower()}{date_iso_digits}00000000001001&page=1&height=1200"
        try:
            head_resp = s.head(pr_dated_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            if head_resp.status_code == 200:
                cover_url = pr_dated_url
        except Exception:
            pass

    if not cover_url:
        cover_url = art_img or (f"https://i.prcdn.co/img?cid={cid}&page=1&height=1200" if cid else None)

    # Extract price from article or fallback to standard Greek series price
    price_val = GREEK_PRICES.get(cid, "1,90 €")
    if article_html_content:
        m_pr = re.search(r'(?:€\s*(\d+[,\.]\d{2})|(\d+[,\.]\d{2})\s*€)', article_html_content)
        if m_pr:
            price_val = f"{(m_pr.group(1) or m_pr.group(2)).replace('.', ',')} €"

    return {
        "id": art_id,
        "title": title_text,
        "url": url,
        "issue_code": canonical_issue_path,
        "issue_path": canonical_issue_path,
        "price": price_val,
        "cover_url": cover_url,
        "date": date_val,
        "summary": "",
        "publisher": "Kathimerini",
        "article_html": article_html_content,
    }


def discover_kathimerini() -> list[dict]:
    """
    Scrapes the Kathimerini Disney section (Greece).
    Extracts articles announcing new magazines with full story summaries
    and accurate issue-specific covers.
    """
    result = []
    seen_urls = set()
    try:
        s = get_session()
        from src.config import KATHIMERINI_URL
        r = s.get(KATHIMERINI_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            print(f"  [warn] Kathimerini returned {r.status_code}")
            return result

        soup = BeautifulSoup(r.text, 'html.parser')
        candidate_links = []
        for a in soup.find_all('a', href=True):
            p_title = a.find('p', class_='title')
            if p_title and '#' in p_title.text:
                url = a['href']
                if url not in seen_urls:
                    seen_urls.add(url)
                    candidate_links.append(a)

        # Concurrently fetch article contents
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(_process_kathimerini_article, a_tag, s) for a_tag in candidate_links]
            for fut in futs:
                item = fut.result()
                if item:
                    result.append(item)

    except Exception as e:
        print(f"  [warn] discover_kathimerini failed: {e}")

    return result
