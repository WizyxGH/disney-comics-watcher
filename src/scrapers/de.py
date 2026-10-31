import re
import html as html_lib
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import http.client
http.client._MAXHEADERS = 1000

from src.config import EGMONT_DE_URLS, LTB_SITE_BASE, LTB_ALLE_AUSGABEN_URL, LTB_NEBENREIHEN_URL
from src.utils import get_session


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
                    if not cover.startswith('http'):
                        cover = "https://www.egmont-shop.de" + cover.split('?')[0]
                    else:
                        cover = cover.split('?')[0]
                    if any(ph in cover.lower() for ph in ('coverabbildung-nicht-verfugbar', 'nicht-verfuegbar', 'placeholder', 'coming_soon', 'coming-soon')):
                        cover = None
                    
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


def fetch_egmont_de_details(url: str) -> dict:
    if not url: return {}
    s = get_session()
    details = {}
    try:
        r = s.get(url, timeout=15)
        if r.status_code != 200: return {}
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try finding high res image
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            img_url = og['content']
            if '?' in img_url:
                img_url = img_url.split('?')[0]
            if not any(ph in img_url.lower() for ph in ('coverabbildung-nicht-verfugbar', 'nicht-verfuegbar', 'placeholder', 'coming_soon', 'coming-soon')):
                details['cover_url'] = img_url
            
        # Look for the script data state
        script = soup.find('script', attrs={'data-state': 'product-details-product', 'type': 'application/json'})
        if script:
            import json
            data = json.loads(script.text)
            for spec in data.get('specs', []):
                if spec.get('key') == 'Erscheinungsdatum':
                    details['date'] = spec.get('value')
                    return details
        
        # Fallback HTML table
        th = soup.find(lambda tag: tag.name == 'th' and tag.text and 'Erscheinungsdatum' in tag.text)
        if th:
            td = th.find_next_sibling('td')
            if td:
                details['date'] = td.text.strip()
    except Exception as e:
        print(f"  [warn] fetch_egmont_de_details failed for {url}: {e}")
    
    return details


def discover_lustiges_taschenbuch_de():
    """Discovers LTB releases from lustiges-taschenbuch.de directly (alle-ausgaben + nebenreihen)."""
    s = get_session()
    results = []
    seen = set()

    # 1. Alle Ausgaben (main series)
    try:
        r = s.get(LTB_ALLE_AUSGABEN_URL, timeout=15)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = re.search(r"/ausgaben/alle-ausgaben/ltb-(\d+)", href)
                if m and href not in seen:
                    seen.add(href)
                    num = m.group(1)
                    title_text = a.get_text(strip=True)
                    full_url = LTB_SITE_BASE + href if href.startswith("/") else href
                    img = a.find("img")
                    cover_url = (LTB_SITE_BASE + img["src"]) if img and img.get("src") and img["src"].startswith("/") else (img["src"] if img and img.get("src") else None)
                    results.append({
                        "id": f"ltb_{num}",
                        "title": f"Lustiges Taschenbuch {num}" + (f" - {title_text}" if title_text else ""),
                        "url": full_url,
                        "cover_url": cover_url,
                        "numero": num,
                        "price": "8,99 €"
                    })
    except Exception as e:
        print(f"  [warn] discover_lustiges_taschenbuch_de alle-ausgaben: {e}")

    # 2. Nebenreihen (subseries latest releases)
    try:
        r2 = s.get(LTB_NEBENREIHEN_URL, timeout=15)
        if r2.status_code == 200:
            from bs4 import BeautifulSoup
            soup2 = BeautifulSoup(r2.text, "html.parser")
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                if "/ausgaben/nebenreihen/" in href and any(b in href.lower() for b in ["/band-", "/nr-"]):
                    if href not in seen:
                        seen.add(href)
                        full_url = LTB_SITE_BASE + href if href.startswith("/") else href
                        slug = href.strip("/").split("/")[-1]
                        series_slug = href.strip("/").split("/")[-2]
                        text = a.get_text(separator=" ", strip=True)
                        # Clean up date prefix e.g. "13.10.2026 Nr. 23 Die Perle von Labuan"
                        m_clean = re.search(r"(?:Nr\.?\s*\d+.*)$", text)
                        clean_title = m_clean.group(0) if m_clean else text
                        img = a.find("img")
                        cover_url = (LTB_SITE_BASE + img["src"]) if img and img.get("src") and img["src"].startswith("/") else (img["src"] if img and img.get("src") else None)
                        results.append({
                            "id": f"{series_slug}_{slug}".replace("-", "_"),
                            "title": f"{series_slug} - {clean_title}",
                            "url": full_url,
                            "cover_url": cover_url,
                        })
    except Exception as e:
        print(f"  [warn] discover_lustiges_taschenbuch_de nebenreihen: {e}")

    return results


def fetch_lustiges_taschenbuch_de_details(url: str) -> dict:
    """Fetches date and story details from a lustiges-taschenbuch.de page."""
    if not url:
        return {}
    details = {}
    try:
        s = get_session()
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            from src.ltb_enricher import _parse_stories
            cover_title, issue_date, stories = _parse_stories(r.text)
            if issue_date:
                details["date"] = issue_date
            if cover_title:
                details["name"] = cover_title
            if stories:
                details["stories"] = stories
                last_story = stories[-1]
                if "start_page" in last_story and "pages" in last_story:
                    details["pages"] = last_story["start_page"] + last_story["pages"] - 1
                    details["pages_estimated"] = True
    except Exception as e:
        print(f"  [warn] fetch_lustiges_taschenbuch_de_details failed for {url}: {e}")
    return details
