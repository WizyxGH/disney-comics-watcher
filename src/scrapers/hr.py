import re
from src.utils import get_session

def discover_hr():
    """Discovers Disney comic books at Egmont Croatia (shop.egmont.hr)."""
    s = get_session()
    result = []
    
    urls = [
        "https://shop.egmont.hr/kategorija-proizvoda/disney/",
        "https://shop.egmont.hr/kategorija-proizvoda/disney/page/2/",
        "https://shop.egmont.hr/kategorija-proizvoda/disney/page/3/"
    ]
    
    seen = set()
    
    for url in urls:
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue
                
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for li in soup.find_all('li', class_='product'):
                a = li.find('a', class_='woocommerce-LoopProduct-link')
                if not a: continue
                
                href = a.get('href')
                title_elem = li.find(class_='woocommerce-loop-product__title')
                title = title_elem.text.strip() if title_elem else "Unknown"
                
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
                            
                if not book_id or book_id in seen:
                    continue
                    
                seen.add(book_id)
                
                result.append({
                    "id": book_id,
                    "title": title,
                    "url": href,
                    "price": price,
                    "cover_url": cover_url,
                    "date": None,
                    "released": True
                })
                
        except Exception as e:
            print(f"  [warn] discover_hr failed for {url}: {e}")
            
    return result

def fetch_hr_details(url: str) -> dict:
    return {}
