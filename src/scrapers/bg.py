import re
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_bg():
    """Discovers Disney comics at Egmont Bulgaria."""
    s = get_session()
    result = []
    
    urls = [
        "https://egmontbulgaria.com/miki-maus-1461/",
        "https://egmontbulgaria.com/donald-dak-i-makrokomiks-200/"
    ]
    
    seen = set()
    
    for url in urls:
        try:
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for item in soup.select('.product'):
                id_elem = item.get('data-product-id')
                if not id_elem:
                    continue
                    
                if id_elem in seen:
                    continue
                seen.add(id_elem)
                
                title_elem = item.select_one('.title a')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                link = "https://egmontbulgaria.com" + title_elem.get('href')
                
                price_elem = item.select_one('.price-value')
                price = price_elem.get_text(strip=True) if price_elem else None
                
                img_elem = item.select_one('.img-content img')
                cover_url = img_elem.get('src') if img_elem else None
                if cover_url and not cover_url.startswith('http'):
                    cover_url = "https://egmontbulgaria.com" + cover_url
                    
                result.append({
                    "id": id_elem,
                    "title": title,
                    "url": link,
                    "price": price,
                    "cover_url": cover_url,
                    "date": None,
                    "released": False
                })
                
        except Exception as e:
            print(f"  [warn] Egmont BG: {e}")
            
    return result

def fetch_bg_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
