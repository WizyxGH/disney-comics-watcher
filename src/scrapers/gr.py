import re
import html as html_lib
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import http.client
http.client._MAXHEADERS = 1000

from src.utils import get_session


def discover_kathimerini() -> list[dict]:
    """
    Scrapes the Kathimerini Disney section (Greece).
    Extracts articles announcing new magazines.
    """
    result = []
    try:
        s = get_session()
        # KATHIMERINI_URL is imported from config
        from src.config import KATHIMERINI_URL
        r = s.get(KATHIMERINI_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            print(f"  [warn] Kathimerini returned {r.status_code}")
            return result
            
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Iterating over all links to find articles
        for a in soup.find_all('a', href=True):
            p_title = a.find('p', class_='title')
            if p_title:
                title_text = p_title.text.strip()
                if '#' in title_text:
                    url = a['href']
                    if any(x['url'] == url for x in result):
                        continue
                        
                    # 1. Try PressReader high-res cover
                    img_url = None

                    # 1. Fetch cover and date from the Kathimerini article itself (most reliable)
                    try:
                        date_val = None
                        r_art = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                        if r_art.status_code == 200:
                            art_soup = BeautifulSoup(r_art.text, 'html.parser')
                            for img in art_soup.find_all('img'):
                                src = img.get('src', '')
                                if src and ('uploads' in src or 'img' in src) and src.startswith('http'):
                                    img_url = src
                                    break
                                    
                            time_elem = art_soup.find('time')
                            if time_elem:
                                m_date = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', time_elem.text)
                                if m_date:
                                    date_val = f"{m_date.group(1)}/{m_date.group(2)}/{m_date.group(3)}"
                    except Exception as e:
                        print(f"  [warn] Failed to fetch Kathimerini article {url}: {e}")

                    # 2. Fallback: PressReader CID-based cover (often blocked)
                    if not img_url:
                        title_lower = title_text.lower()
                        cid = None
                        if "μίκυ μάους" in title_lower:
                            cid = "464B"
                        elif "κόμιξ" in title_lower:
                            cid = "464D"
                        elif "ντόναλντ" in title_lower:
                            cid = "464A"
                        elif "super miky" in title_lower:
                            cid = "464C"
                        if cid:
                            img_url = f"https://i.prcdn.co/img?cid={cid}&page=1&height=1000"

                        
                    # Extract a unique ID from the URL (e.g. 564262477)
                    m = re.search(r'/(\d+)/', url)
                    art_id = m.group(1) if m else url.split('/')[-2]
                    
                    result.append({
                        "id": art_id,
                        "title": title_text,
                        "url": url,
                        "price": "N/A (Kiosk)",  # Usually distributed with Sunday newspaper
                        "cover_url": img_url,
                        "date": date_val,
                        "summary": ""
                    })
    except Exception as e:
        print(f"  [warn] discover_kathimerini failed: {e}")
        
    return result

