import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_lt() -> list[dict]:
    """
    Discovers Lithuanian Disney comic magazines and books from knygos.lt (Egmont Lietuva distribution).
    Covers Donaldas ir kiti, Mega Giga, Auksinė kolekcija, etc.
    """
    s = get_session()
    result = []
    seen = set()

    search_queries = [
        "donaldas+ir+kiti",
        "antulis+donaldas"
    ]

    base_url = "https://www.knygos.lt"

    for q in search_queries:
        url = f"https://www.knygos.lt/lt/paieska/?q={q}"
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'/lt/knygos/')):
                title = a.get_text(strip=True)
                if not title:
                    continue
                lower_title = title.lower()

                # Must be a Disney comic title
                if not any(k in lower_title for k in ['donaldas', 'antulis', 'ančiogal', 'mega giga']):
                    continue

                href = a['href']
                full_url = urljoin(base_url, href)
                slug = href.rstrip('/').split('/')[-1]

                if slug in seen:
                    continue
                seen.add(slug)

                card = a.find_parent(class_=re.compile(r'product|card|item'))
                img_url = None
                price = None
                ean = None

                if card:
                    img = card.find('img')
                    if img:
                        raw_src = img.get('src') or img.get('data-src') or ''
                        if raw_src:
                            # Upgrade thumbnail resolution from 0x231 to 600x600
                            img_url = re.sub(r'fit-in/\d+x\d+/', 'fit-in/600x600/', raw_src)
                            # Extract ISBN from image filename if present (e.g. 9786090510865)
                            if m_isbn := re.search(r'(978\d{10})', raw_src):
                                ean = m_isbn.group(1)

                    price_el = card.find(class_=re.compile(r'price'))
                    if price_el:
                        # Extract e.g. "6,99 €" or "11,79 €"
                        m_pr = re.search(r'(\d+[,.]\d{2}\s*€)', price_el.get_text())
                        if m_pr:
                            price = m_pr.group(1).replace(' ', '\xa0')

                # Determine issue_path
                issue_path = None
                if m_num := re.search(r'nr\.?\s*(\d+)', lower_title):
                    issue_path = f"lt/D  {int(m_num.group(1)):02d}"
                elif 'mega giga' in lower_title:
                    issue_path = "lt/MGD"
                elif 'auksinė' in lower_title:
                    issue_path = "lt/DIK"
                elif 'donaldas ir kiti' in lower_title:
                    issue_path = "lt/D"

                result.append({
                    "id": slug,
                    "title": title,
                    "url": full_url,
                    "price": price,
                    "cover_url": img_url,
                    "ean": ean,
                    "date": None,
                    "released": True,
                    "publisher": "Egmont",
                    "issue_path": issue_path
                })
        except Exception as e:
            print(f"  [warn] discover_lt failed for query '{q}': {e}")

    return result

def fetch_lt_details(url: str) -> dict:
    return {}
