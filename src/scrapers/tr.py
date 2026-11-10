import re
from bs4 import BeautifulSoup
from src.utils import get_session

DR_BASE = "https://www.dr.com.tr"

def discover_tr() -> list[dict]:
    """
    Discovers official Turkish Disney comics and graphic novels by Beta Kids on D&R.
    Covers the 'Disney En Güzel Maceralar' series and other official Disney comic releases.
    """
    s = get_session()
    results = []
    seen = set()

    search_urls = [
        f"{DR_BASE}/search?q=disney%20en%20g%C3%BCzel%20maceralar",
        f"{DR_BASE}/search?q=disney&publisher=Beta%20Kids"
    ]

    for url in search_urls:
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')

            # D&R product card links
            links = soup.find_all('a', href=re.compile(r'/kitap/[^/]+/.+urunno=(\d+)'))
            for a in links:
                href = a.get('href')
                if not href or href in seen:
                    continue

                m_urun = re.search(r'urunno=(\d+)', href)
                item_id = m_urun.group(1) if m_urun else href
                if item_id in seen:
                    continue

                title = a.get_text(strip=True)
                if not title:
                    title_attr = a.get('title')
                    if title_attr:
                        title = title_attr.strip()

                if not title or len(title) < 4:
                    continue

                title_lower = title.lower()
                # Ensure it's Disney related
                if "disney" not in title_lower and "miki" not in title_lower and "donald" not in title_lower:
                    continue

                seen.add(href)
                seen.add(item_id)

                full_url = DR_BASE + href if href.startswith('/') else href

                # Image
                img_elem = a.find('img')
                img_url = None
                if img_elem:
                    img_url = img_elem.get('data-src') or img_elem.get('src')
                    if img_url and img_url.startswith('//'):
                        img_url = 'https:' + img_url

                results.append({
                    "id": item_id,
                    "title": title,
                    "url": full_url,
                    "cover_url": img_url,
                    "price": None,
                    "date": None,
                    "released": True
                })
        except Exception as e:
            print(f"  [warn] discover_tr ({url}): {e}")

    return results

def fetch_tr_details(url: str) -> dict:
    """
    Fetches barcode (EAN), exact price, publication year/date, and HD cover from D&R product page.
    """
    if not url:
        return {}
    s = get_session()
    details = {}
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')

            # Title
            h1 = soup.find('h1')
            if h1:
                details['name'] = h1.get_text(strip=True)

            # High-res cover image from meta og:image or main image
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                img_src = og_img['content']
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                details['cover_url'] = img_src

            # Price
            price_m = re.search(r'([\d.,]+)\s*TL', r.text)
            if price_m:
                details['price'] = f"{price_m.group(1)} TL"

            # EAN / Barcode
            ean_m = re.search(r'Barkod:?\s*(\d{10,13})', r.text)
            if ean_m:
                details['ean'] = ean_m.group(1)

            # Page count
            pages_m = re.search(r'Sayfa Sayısı:?\s*(\d+)', r.text)
            if pages_m:
                details['pages'] = int(pages_m.group(1))

            # Publication Year
            year_m = re.search(r'İlk Baskı Yılı:?\s*(\d{4})', r.text)
            if year_m:
                details['date'] = f"{year_m.group(1)}-01-01"

    except Exception as e:
        print(f"  [warn] fetch_tr_details failed for {url}: {e}")

    return details
