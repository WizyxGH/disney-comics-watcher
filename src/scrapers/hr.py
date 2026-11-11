import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_hr() -> list[dict]:
    """
    Discovers Croatian Disney comics and magazines from Egmont Croatia (shop.egmont.hr).
    Covers Miki Maus, Paško Patak, Patkograd (Carl Barks), and Disney comic albums.
    """
    s = get_session()
    result = []
    seen = set()

    search_queries = ["miki", "pasko", "strip", "disney"]
    base_url = "https://shop.egmont.hr/"

    for q in search_queries:
        url = f"https://shop.egmont.hr/?s={q}&post_type=product"
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            for li in soup.find_all('li', class_='product'):
                a = li.find('a', class_='woocommerce-LoopProduct-link')
                if not a:
                    continue

                href = a.get('href')
                title_elem = li.find(class_='woocommerce-loop-product__title')
                title = title_elem.text.strip() if title_elem else "Unknown"

                # Filter out non-comic children activity items if needed
                lower_title = title.lower()
                is_comic = any(k in lower_title for k in [
                    'miki maus', 'paško', 'patko', 'strip', 'disney princeza', 
                    'donald', 'barks', 'patkograd', 'winnie pooh: filmska',
                    'zootropola', 'vaiana: filmska', 'auti: filmska'
                ])
                if not is_comic and q == 'disney':
                    continue

                price_elem = li.find('span', class_='price')
                price = None
                if price_elem:
                    bdis = price_elem.find_all('bdi')
                    if bdis:
                        price = bdis[-1].text.strip()
                    else:
                        price = price_elem.text.strip()

                img = a.find('img')
                cover_url = img.get('src') if img else None

                book_id = None
                btn = li.find('a', class_='add_to_cart_button')
                if btn:
                    book_id = btn.get('data-product_id')
                if not book_id:
                    for c in li.get('class', []):
                        if c.startswith('post-'):
                            book_id = c.replace('post-', '')
                            break
                if not book_id:
                    book_id = href.rstrip('/').split('/')[-1]

                if not book_id or book_id in seen:
                    continue

                seen.add(book_id)

                # Determine issue_path if possible
                issue_path = None
                if m := re.search(r'miki maus\s*(\d+)/(\d+)', lower_title):
                    issue_path = f"hr/MMH{m.group(2)}-{int(m.group(1)):02d}"
                elif m := re.search(r'patkograd\s*(\d+)', lower_title):
                    issue_path = f"hr/CB  {int(m.group(1)):02d}"

                result.append({
                    "id": book_id,
                    "title": title,
                    "url": href,
                    "price": price,
                    "cover_url": cover_url,
                    "date": None,
                    "released": True,
                    "publisher": "Egmont",
                    "issue_path": issue_path
                })
        except Exception as e:
            print(f"  [warn] discover_hr failed for query '{q}': {e}")

    return result

def fetch_hr_details(url: str) -> dict:
    s = get_session()
    try:
        r = s.get(url, timeout=15)
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.text, 'html.parser')
        price_elem = soup.find('span', class_='price')
        price = price_elem.text.strip() if price_elem else None
        img = soup.find('.woocommerce-product-gallery__image img') or soup.find('img', class_='wp-post-image')
        cover_url = img.get('src') if img else None
        return {"price": price, "cover_url": cover_url}
    except Exception:
        return {}
