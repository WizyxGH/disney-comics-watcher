import re
from bs4 import BeautifulSoup
from src.utils import get_session

PANINI_MONTHS = {
    # Italian
    "gen": 1, "gennaio": 1,
    "feb": 2, "febbraio": 2,
    "mar": 3, "marzo": 3,
    "apr": 4, "aprile": 4,
    "mag": 5, "maggio": 5,
    "giu": 6, "giugno": 6,
    "lug": 7, "luglio": 7,
    "ago": 8, "agosto": 8,
    "set": 9, "settembre": 9,
    "ott": 10, "ottobre": 10,
    "nov": 11, "novembre": 11, "novembro": 11,
    "dic": 12, "dicembre": 12, "dez": 12, "dezembro": 12,
    # Portuguese
    "jan": 1, "janeiro": 1,
    "fev": 2, "fevereiro": 2,
    "mar": 3, "março": 3,
    "abr": 4, "abril": 4,
    "mai": 5, "maio": 5,
    "jun": 6, "junho": 6,
    "jul": 7, "julho": 7,
    "ago": 8, "agosto": 8,
    "set": 9, "setembro": 9,
    "out": 10, "outubro": 10,
}

def parse_panini_date(date_str: str, country_code: str) -> str | None:
    """Parses Panini's date format into YYYY-MM-DD."""
    if not date_str:
        return None
    date_str = date_str.strip().lower()
    
    # Check for DD/MM/YY or DD/MM/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if m:
        d, m_num, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m_num.zfill(2)}-{d.zfill(2)}"
        
    # Check for textual formats like "24 lug 2026" or "24 de jul. de 2026"
    date_str = date_str.replace(" de ", " ").replace(".", "")
    parts = date_str.split()
    if len(parts) >= 3:
        d = parts[0]
        month_str = parts[1]
        y = parts[2]
        
        m_num = None
        for k, v in PANINI_MONTHS.items():
            if month_str.startswith(k):
                m_num = v
                break
                
        if m_num and d.isdigit() and y.isdigit():
            if len(y) == 2:
                y = "20" + y
            return f"{y}-{str(m_num).zfill(2)}-{d.zfill(2)}"
            
    return None

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
                
            date_elem = item.select_one('.product-item-attribute-release-date small')
            if not date_elem:
                date_elem = item.select_one('.product-item-attribute-release-date')
            raw_date = date_elem.get_text(strip=True) if date_elem else None
            parsed_date = parse_panini_date(raw_date, country_code) if raw_date else None
            
            result.append({
                "id": sku,
                "title": title,
                "url": link,
                "price": price,
                "cover_url": cover_url,
                "date": parsed_date,
                "released": False
            })
            
    except Exception as e:
        print(f"  [warn] Panini {country_code.upper()}: {e}")
        
    return result

def fetch_panini_magento_details(url: str, country_code: str = "IT") -> dict:
    """
    Fetches the high-resolution cover image and release date from a Panini product page.
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
            
        # Fallback to Magento gallery script if og:image wasn't resolved/wanted
        if 'cover_url' not in details:
            for script in soup.find_all('script', type='text/x-magento-init'):
                if 'mage/gallery/gallery' in script.text:
                    m = re.search(r'"full":"(.*?)"', script.text)
                    if m:
                        img_url = m.group(1).replace(r'\/', '/')
                        if '?' in img_url:
                            img_url = img_url.split('?')[0]
                        details['cover_url'] = img_url
                        break
                        
        # Extract release date
        date_li = soup.select_one('.item.pnn_release_date')
        if date_li:
            data_span = date_li.select_one('.data')
            if data_span:
                raw_date = data_span.get_text(strip=True)
                parsed_date = parse_panini_date(raw_date, country_code)
                if parsed_date:
                    details['date'] = parsed_date
                    
    except Exception as e:
        print(f"  [warn] Failed to fetch Panini HD cover/details from {url}: {e}")
        
    return details

