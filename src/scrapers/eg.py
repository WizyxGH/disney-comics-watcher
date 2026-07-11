import re
import json
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_nahdet_misr_eg():
    """Discovers Disney comics on Nahdet Misr (Egypt)."""
    s = get_session()
    result = []
    
    # We search for mickey/miki related comics
    urls = [
        "https://nahdetmisrbookstore.com/en/products?search=mickey",
        "https://nahdetmisrbookstore.com/en/products?search=miki",
        "https://nahdetmisrbookstore.com/en/categories/mickey-and-disney-characters"
    ]
    
    seen_ids = set()
    
    for url in urls:
        try:
            r = s.get(url, timeout=15)
            r.raise_for_status()
            
            # Since this is an Angular/Next app, the products might be rendered 
            # in the DOM (SSR) or embedded in a JSON script tag.
            
            # 1. Try to extract from SSR DOM if available
            soup = BeautifulSoup(r.text, 'html.parser')
            for a_tag in soup.find_all('a', href=re.compile(r'/products/.*miki|mickey|disney.*', re.I)):
                link = a_tag.get('href')
                if not link.startswith('http'):
                    link = "https://nahdetmisrbookstore.com" + link
                    
                title = a_tag.get_text(strip=True)
                if not title:
                    continue
                
                # Try to find an image nearby
                img_tag = a_tag.find('img') or a_tag.find_previous('img')
                cover_url = img_tag.get('src') if img_tag else None
                
                sku = link.split('/')[-1]
                
                if sku not in seen_ids and ("miki" in title.lower() or "mickey" in title.lower() or "ميكي" in title):
                    seen_ids.add(sku)
                    result.append({
                        "id": sku,
                        "title": title,
                        "url": link,
                        "price": None, # Price extraction would need specific DOM structure
                        "cover_url": cover_url,
                        "date": None,
                        "released": True
                    })
            
            # 2. Try to extract from JSON state if Angular Universal / Next.js embeds it
            for script in soup.find_all('script'):
                if script.string and ('products' in script.string or 'items' in script.string):
                    # Basic heuristic to find JSON-like structures
                    # If we find a structured JSON state, we could parse it here.
                    pass
            
        except Exception as e:
            print(f"  [warn] Nahdet Misr EG: {e}")
            
    return result

def fetch_nahdet_misr_eg_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
