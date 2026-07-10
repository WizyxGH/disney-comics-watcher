import re
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_panini_br():
    """Discovers Disney comics on Panini Brazil using Magento HTML structure."""
    s = get_session()
    result = []
    
    # URL for Disney comics on Panini Brazil
    url = "https://panini.com.br/disney"
    
    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        for item in soup.select('.product-item-info'):
            title_elem = item.select_one('.product-item-link')
            if not title_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href')
            
            price_elem = item.select_one('.price')
            price = price_elem.get_text(strip=True) if price_elem else None
            
            img_elem = item.select_one('.product-image-photo')
            cover_url = img_elem.get('src') if img_elem else None
            
            sku = None
            action_elem = item.select_one('[data-product-id]')
            if action_elem:
                sku = action_elem.get('data-product-id')
            
            if not sku and link:
                sku = link.split('/')[-1].replace('.html', '')
            if not sku:
                sku = title
                
            result.append({
                "id": sku,
                "title": title,
                "url": link,
                "price": price,
                "cover_url": cover_url,
                "date": None,
                "released": False
            })
            
    except Exception as e:
        print(f"  [warn] Panini BR: {e}")
        
    return result

def fetch_panini_br_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
