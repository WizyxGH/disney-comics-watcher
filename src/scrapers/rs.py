import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_rs() -> list[dict]:
    """
    Discovers Serbian Disney comic magazines from trafika.online (Egmont Serbia distribution).
    Covers Miki Maus, Paja Patak, etc.
    """
    s = get_session()
    result = []
    seen = set()

    sources = [
        "https://www.trafika.online/kategorije/stripovi/strip?katid=16",
        "https://www.trafika.online/kategorije/stripovi/strip?katid=16&strana=2",
        "https://www.trafika.online/kategorije/stripovi/strip-knjiga?katid=17",
        "https://www.trafika.online/pretraga?rec=miki",
        "https://www.trafika.online/pretraga?rec=patak",
    ]

    base_url = "https://www.trafika.online"

    for url in sources:
        try:
            r = s.get(url, timeout=5)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href.startswith('/proizvod/'):
                    continue

                full_url = urljoin(base_url, href)
                parts = href.strip('/').split('/')
                if len(parts) < 3:
                    continue

                prod_id = parts[1]
                slug = parts[2].lower()

                # Filter for Disney titles (Miki Maus, Paja Patak, Disney)
                if not any(k in slug for k in ['miki-maus', 'paja-patak', 'dizni', 'disney', 'paja']):
                    continue
                # Exclude non-Disney Miki like "kapetan-miki" (Captain Miki / EsseGesse)
                if 'kapetan-miki' in slug:
                    continue

                if prod_id in seen:
                    continue
                seen.add(prod_id)

                # Fetch details for title, price, cover
                book = _fetch_single_rs(s, full_url, prod_id, slug)
                if book:
                    result.append(book)

        except Exception as e:
            print(f"  [warn] discover_rs failed for {url}: {e}")

    return result

def _fetch_single_rs(s, full_url: str, prod_id: str, slug: str) -> dict | None:
    try:
        r = s.get(full_url, timeout=12)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, 'html.parser')
        h1 = soup.find(['h1', 'h2'])
        raw_title = h1.get_text(strip=True) if h1 else slug.replace('-', ' ').title()

        # Clean title (remove "Egmont" or "Novo" prefix if stuck to title)
        title = re.sub(r'^(?:Novo)?(?:Egmont)?', '', raw_title).strip()
        if not title:
            title = slug.replace('-', ' ').title()

        # Price
        price = None
        price_elem = soup.find(class_=lambda c: c and 'cena' in c) or soup.find(text=re.compile(r'\d+[\d.,]*\s*din', re.I))
        if price_elem:
            if hasattr(price_elem, 'get_text'):
                price = price_elem.get_text(strip=True)
            else:
                price = str(price_elem).strip()

        # Cover Image
        cover_url = None
        img = soup.find('img', src=re.compile(r'/images/product/medium/')) or soup.find('img', src=re.compile(r'/images/product/'))
        if img:
            cover_url = urljoin("https://www.trafika.online", img['src']).replace('/thumb/', '/medium/')

        # ISBN / Barcode
        ean = None
        body_text = soup.get_text()
        if m_ean := re.search(r'EAN\s*(?:kod)?\s*:\s*([0-9Xx]+)', body_text, re.I):
            ean = m_ean.group(1).strip()

        # Issue code / path
        issue_path = None
        # e.g. "Miki Maus 11/26" -> rs/MM 2026-11 or rs/MM  26-11
        if m_mm := re.search(r'miki maus\s*(\d+)/(\d+)', title.lower()):
            num = int(m_mm.group(1))
            year_short = int(m_mm.group(2))
            full_year = 2000 + year_short if year_short < 50 else 1900 + year_short
            issue_path = f"rs/MM{full_year}-{num:02d}"
        elif m_pp := re.search(r'paja patak.*?(\d+)', title.lower()):
            num = int(m_pp.group(1))
            issue_path = f"rs/DPP  {num}"

        return {
            "id": prod_id,
            "title": title,
            "url": full_url,
            "price": price,
            "cover_url": cover_url,
            "ean": ean,
            "date": None,
            "released": True,
            "publisher": "Egmont",
            "issue_path": issue_path
        }
    except Exception:
        return None

def fetch_rs_details(url: str) -> dict:
    return {}
