"""
Sweden: Disney magazine & comic releases from official distributor Tidsam (tidsam.se).

Tidsam is the official Swedish national press & magazine distributor (owned by
Story House Egmont and Aller Media). It provides official kiosk release dates (Förs. dag),
retail prices in SEK, issue numbers (Utgåva), and high-resolution covers.
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_se() -> list[dict]:
    """
    Discovers Swedish Disney comic magazines from the official distributor Tidsam.
    Covers Kalle Anka & Co, Kalle Ankas Pocket, Kalle Anka Klassiker, Kalle Anka Pocket Special, etc.
    """
    s = get_session()
    result = []
    seen = set()
    base_url = "https://www.tidsam.se"

    search_queries = ["kalle", "anka", "musse", "disney"]
    mag_urls = []

    for q in search_queries:
        url = f"https://www.tidsam.se/sortiment/?search={q}"
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'/magazines/')):
                href = a['href']
                lower_href = href.lower()
                # Filter for Disney magazines
                if any(k in lower_href for k in ['kalle', 'anka', 'musse', 'disney']):
                    full_mag_url = urljoin(base_url, href)
                    if full_mag_url not in mag_urls:
                        mag_urls.append(full_mag_url)
        except Exception as e:
            print(f"  [warn] discover_se search failed for '{q}': {e}")

    for mag_url in mag_urls:
        try:
            r = s.get(mag_url, timeout=12)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            h1 = soup.find('h1')
            raw_title = h1.get_text(strip=True) if h1 else mag_url.rstrip('/').split('/')[-1]

            body_text = soup.get_text()

            # 1. Exact Release Date (Förs. dag YYYY-MM-DD)
            rel_date = None
            if m_date := re.search(r'Förs\.\s*dag\s*(\d{4}-\d{2}-\d{2})', body_text):
                rel_date = m_date.group(1).strip()

            # 2. Retail Price
            price = None
            if m_price := re.search(r'Pris\s*Sverige\s*([\d.]+\s*kr)', body_text):
                price = m_price.group(1).strip()

            # 3. Issue / Utgåva
            utg = None
            if m_utg := re.search(r'Utgåva\s*(\d+)', body_text):
                utg = m_utg.group(1).strip()

            # 4. Article Number
            art_nr = None
            if m_art := re.search(r'Art\.\s*nr\s*(\d+)', body_text):
                art_nr = m_art.group(1).strip()

            # 5. Cover Image
            cover_url = None
            img = soup.find('img', src=re.compile(r'/covers/hq/|/covers/'))
            if img:
                cover_url = urljoin(base_url, img['src'])

            # Determine title & Inducks issue_path
            # Art 0720: Kalle Anka & Co
            # Art 0687: Kalle Ankas Pocket
            # Art 4445: Kalle Anka Klassiker
            # Art 0778: Kalle Anka Pocket Special
            # Art 4810: Kalle Anka Junior
            title = raw_title
            issue_path = "se/KA"

            if "kalle-anka-co" in mag_url or art_nr == "0720":
                # utg e.g. 202643 -> Year 2026, issue 43
                if utg and len(utg) >= 6:
                    year = utg[:4]
                    num = int(utg[4:])
                    title = f"Kalle Anka & C:o nr {num}/{year}"
                    issue_path = f"se/KA{year}-{num:02d}"
                else:
                    title = "Kalle Anka & C:o"
                    issue_path = "se/KA"
            elif "kalle-ankas-pocket" in mag_url or art_nr == "0687":
                # Find pocket number in raw_title or utg e.g. "Kalle Ankas Pocket 589"
                if m_pnum := re.search(r'pocket\s*(\d+)', raw_title, re.I):
                    p_num = int(m_pnum.group(1))
                    title = f"Kalle Ankas Pocket nr {p_num}"
                    issue_path = f"se/KAP  {p_num}"
                else:
                    title = "Kalle Ankas Pocket"
                    issue_path = "se/KAP"
            elif "klassiker" in mag_url or art_nr == "4445":
                if utg and len(utg) >= 6:
                    year = utg[:4]
                    num = int(utg[4:])
                    title = f"Kalle Anka Klassiker nr {num}/{year}"
                    issue_path = f"se/KAE{year}-{num:02d}"
                else:
                    title = "Kalle Anka Klassiker"
                    issue_path = "se/KAE"
            elif "pocket-spec" in mag_url or art_nr == "0778":
                if utg and len(utg) >= 6:
                    year = utg[:4]
                    num = int(utg[4:])
                    title = f"Kalle Anka Pocket Special nr {num}/{year}"
                    issue_path = f"se/KAPS{year}-{num:02d}"
                else:
                    title = "Kalle Anka Pocket Special"
                    issue_path = "se/KAPS"
            elif "junior" in mag_url or art_nr == "4810":
                if utg and len(utg) >= 6:
                    year = utg[:4]
                    num = int(utg[4:])
                    title = f"Kalle Anka Junior nr {num}/{year}"
                    issue_path = f"se/KAJ{year}-{num:02d}"
                else:
                    title = "Kalle Anka Junior"
                    issue_path = "se/KAJ"
            elif "resor" in mag_url or art_nr == "5398":
                title = "Kalle Ankas Pocket Resor: Storbritannien"
                issue_path = "se/KAP"
            elif "megapase" in mag_url or art_nr == "0733":
                title = "Disney Special: Kalle Megapåse"
                issue_path = "se/KA"
            elif "prinsessor" in mag_url or art_nr == "0661":
                title = "Disney Prinsessor"
                issue_path = "se/DP"

            book_id = f"tidsam_{art_nr}_{utg}" if art_nr and utg else mag_url.rstrip('/').split('/')[-1]
            if book_id in seen:
                continue
            seen.add(book_id)

            result.append({
                "id": book_id,
                "title": title,
                "url": mag_url,
                "price": price,
                "cover_url": cover_url,
                "date": rel_date,
                "released": True,
                "publisher": "Story House Egmont",
                "issue_path": issue_path
            })

        except Exception as e:
            print(f"  [warn] discover_se failed for {mag_url}: {e}")

    return result

def fetch_se_details(url: str) -> dict:
    return {}
