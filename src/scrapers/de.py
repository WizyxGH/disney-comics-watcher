import re
import html as html_lib
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import http.client
http.client._MAXHEADERS = 1000

from src.config import KEYWORDS, SKIP_CODIFS, BI_ISSUE_CODIFS, OVERRIDES, SEARCH_URL, SITE_BASE, MLP_FAMILIES, MLP_FAMILY_URL, MLP_URL, GLENAT_BASE, GLENAT_COLLECTION_URL, FANTAGRAPHICS_DISNEY_URL, FANTAGRAPHICS_BASE, EGMONT_DE_URLS
from src.utils import get_session, parse_date_fr, truncate_summary, format_price_fr


def fetch_ltb_index(ltb_number: str) -> list[dict]:
    """Fetches the story index for a given LTB from lustiges-taschenbuch.de."""
    url = f"https://www.lustiges-taschenbuch.de/ausgaben/alle-ausgaben/ltb-{ltb_number}"
    s = get_session()
    try:
        r = s.get(url, timeout=15)
        if r.status_code != 200:
            return []
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        
        stories = []
        for tr in soup.find_all('tr', class_='toc-chapter'):
            title_elem = tr.find(class_='toc-title')
            title = title_elem.text.strip() if title_elem else 'Unknown'
            
            code = None
            pages = None
            
            for small in tr.find_all('small'):
                text = small.text.strip()
                if 'Code:' in text:
                    code = text.replace('Code:', '').strip()
                elif 'Seitenanzahl:' in text:
                    pages = text.replace('Seitenanzahl:', '').strip()
                    
            if code:
                stories.append({'title': title, 'code': code, 'pages': pages})
        return stories
    except Exception as e:
        print(f"  [error] fetch_ltb_index for {ltb_number}: {e}")
        return []

def discover_egmont_de():
    """Discovers German Disney comic books and magazines at Egmont Shop."""
    s = get_session()
    result = []
    
    for url in EGMONT_DE_URLS:
        try:
            r = s.get(url, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all(class_='c-product-card')
            for c in cards:
                href = c.get('href')
                full_url = "https://www.egmont-shop.de" + href.split('?')[0] if href else None
                    
                gtm = c.get('data-gtm-product')
                if not gtm: continue
                
                try:
                    data = json.loads(gtm)
                except Exception:
                    continue
                    
                name = data.get('name')
                if not name:
                    continue
                
                # Filter out non-Disney items often found in the magazine section
                name_lower = name.lower()
                blacklist = [
                    'asterix', 'astérix', 'barbie', 'lucky luke', 'wendy',
                    'hello kitty', 'paw patrol', 'peppa pig', 'lego',
                    'w.i.t.c.h.', 'gargoyles', 'schleich', 'don quixote',
                    'squishmallows', 'fussballbande', 'die fußballbande',
                    'schule der magischen tiere', 'popcorn präsentiert',
                ]
                if any(b in name_lower for b in blacklist):
                    continue

                price = data.get('price')
                if price:
                    try:
                        price = f"{float(price):.2f} €".replace('.', ',')
                    except Exception:
                        price = f"{price} €"
                    
                img = c.find('img')
                cover = img.get('src') if img else None
                if cover:
                    cover = "https://www.egmont-shop.de" + cover.split('?')[0]
                    
                # Egmont cards do not easily expose dates in this view.
                # If they are on the page, they are available now.
                item_data = {
                    "id": data.get('id'),
                    "title": name,
                    "url": full_url,
                    "price": price,
                    "cover_url": cover,
                    "date": None
                }
                
                ltb_match = re.search(r'(?i)lustiges\s*taschenbuch\s*(?:nr\.?)?\s*(\d+)', name)
                if ltb_match:
                    ltb_num = ltb_match.group(1)
                    stories = fetch_ltb_index(ltb_num)
                    if stories:
                        item_data["stories"] = stories
                        
                result.append(item_data)
        except Exception as e:
            print(f"  [warn] discover_egmont_de failed for {url}: {e}")
            
    return result

