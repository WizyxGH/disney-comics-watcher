"""
Lithuania: Disney comics & magazines scraper.

Official source: Prenumeruoti.lt, operated by UAB Press Express
(the official national press distributor in Lithuania for publisher Kid Press / Egmont Lietuva).
Provides official retail prices in EUR, issue numbers, high-res covers, and quarterly release schedules.
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

_QUARTER_MONTHS = {
    1: "03",  # Spring
    2: "06",  # Summer
    3: "09",  # Autumn
    4: "11",  # Winter
}

def discover_lt() -> list[dict]:
    """
    Discovers Lithuanian Disney comic magazines and books from the official press
    distributor Press Express (prenumeruoti.lt).
    Covers Donaldas ir kiti, Donaldas ir kiti pristato, Auksinė Donaldo kolekcija, etc.
    """
    s = get_session()
    result = []
    seen = set()

    base_url = "https://prenumeruoti.lt"
    search_url = "https://prenumeruoti.lt/paieska?s=donaldas"

    try:
        r = s.get(search_url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Find distinct product links
            links = list(dict.fromkeys(
                a['href'] for a in soup.find_all('a', href=True)
                if any(k in a['href'] for k in ['donaldas', 'ančiogal'])
            ))

            for link in links:
                try:
                    full_url = urljoin(base_url, link)
                    slug = link.rstrip('/').split('/')[-1]
                    if slug in seen:
                        continue
                    seen.add(slug)

                    pr = s.get(full_url, timeout=12)
                    if pr.status_code != 200:
                        continue

                    psoup = BeautifulSoup(pr.text, 'html.parser')
                    h1 = psoup.find('h1')
                    raw_title = h1.get_text(strip=True) if h1 else slug

                    no_elem = psoup.find(class_='no')
                    no_text = no_elem.get_text(strip=True) if no_elem else ''

                    price_elem = psoup.find(class_=re.compile(r'current-price|price'))
                    price = None
                    if price_elem:
                        if m_pr := re.search(r'(\d+[,.]\d{2}\s*€)', price_elem.get_text()):
                            price = m_pr.group(1).replace(' ', '\xa0')

                    img = psoup.find('img', src=re.compile(r'large_default'))
                    cover_url = img['src'] if img and img.get('src') else None

                    # Description text for ISBN / EAN
                    desc = psoup.find(class_='product-description')
                    desc_text = desc.get_text(strip=True) if desc else psoup.get_text()

                    ean = None
                    if m_ean := re.search(r'(978\d{10})', desc_text):
                        ean = m_ean.group(1)

                    # Build title and extract release date
                    title = raw_title
                    rel_date = None
                    issue_path = "lt/D"

                    if no_text:
                        title = f"{raw_title} {no_text}"
                        # Try to detect year and quarter number
                        # e.g. "Nr. 4 (551)/2026" or "Nr. 4/2026"
                        if m_date := re.search(r'Nr\.?\s*(\d+)(?:\s*\(\d+\))?/(\d{4})', no_text):
                            quarter = int(m_date.group(1))
                            year = m_date.group(2)
                            month = _QUARTER_MONTHS.get(quarter, "01")
                            rel_date = f"{year}-{month}-01"

                        # Extract total issue number e.g. (551)
                        if m_tot := re.search(r'\((\d+)\)', no_text):
                            tot_num = int(m_tot.group(1))
                            issue_path = f"lt/D  {tot_num}"
                        elif "pristato" in slug:
                            issue_path = "lt/DIKP"
                    elif "auksinė" in slug.lower() or "auksine" in slug.lower():
                        issue_path = "lt/DIK"
                        # Extract year if present
                        if m_yr := re.search(r'(20\d{2}|19\d{2})', slug):
                            rel_date = f"{m_yr.group(1)}-01-01"

                    result.append({
                        "id": f"press_express_{slug}",
                        "title": title,
                        "url": full_url,
                        "price": price,
                        "cover_url": cover_url,
                        "ean": ean,
                        "date": rel_date,
                        "released": True,
                        "publisher": "Kid press",
                        "issue_path": issue_path
                    })
                except Exception as e:
                    print(f"  [warn] discover_lt product error for {link}: {e}")
    except Exception as e:
        print(f"  [warn] discover_lt search error: {e}")

    return result

def fetch_lt_details(url: str) -> dict:
    return {}
