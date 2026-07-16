import re
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_panini_magento(url: str, country_code: str) -> list[dict]:
    """
    Shared generic scraper for all Panini websites using the Magento HTML structure.
    """
    s = get_session()
    result = []
    
    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        for item in soup.select('.product-item-info'):
            title_elem = item.select_one('.product-item-name .product-item-link')
            if not title_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            title_lower = title.lower()
            if "abbonamento" in title_lower or "cofanetto" in title_lower or "pacote" in title_lower or "bundle" in title_lower or "pack" in title_lower:
                continue
                
            # Exclude bundles like "Vol. 1, 2 e 3", "Vol. 1 ao 3", etc.
            if re.search(r'\b(?:vol\.|vols\.|volumes?|n\.|nr\.)\s*\d+\s*(?:,|e|y|and|al|ao|a|-)\s*\d+\b', title, re.IGNORECASE):
                continue
                
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
        print(f"  [warn] Panini {country_code.upper()}: {e}")
        
    return result

def fetch_panini_magento_details(url: str) -> dict:
    """
    Fetches the high-resolution cover image from a Panini product page.
    """
    if not url: return {}
    s = get_session()
    details = {}
    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try og:image first
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            img_url = og['content']
            # Remove query parameters to get the uncompressed image
            if '?' in img_url:
                img_url = img_url.split('?')[0]
            details['cover_url'] = img_url
            return details
            
        # Fallback to Magento gallery script
        for script in soup.find_all('script', type='text/x-magento-init'):
            if 'mage/gallery/gallery' in script.text:
                m = re.search(r'"full":"(.*?)"', script.text)
                if m:
                    img_url = m.group(1).replace(r'\/', '/')
                    if '?' in img_url:
                        img_url = img_url.split('?')[0]
                    details['cover_url'] = img_url
                    break
                    
    except Exception as e:
        print(f"  [warn] Failed to fetch Panini HD cover from {url}: {e}")
        
    return details

