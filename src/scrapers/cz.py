import re
from bs4 import BeautifulSoup
from src.utils import get_session

def discover_cz():
    """Discovers Disney comics at Nakladatelství Crew and Egmont CZ."""
    s = get_session()
    result = []
    
    # 1. Scrape Nakladatelství Crew
    url_crew = "https://obchod.crew.cz/hledani?q=disney"
    try:
        r = s.get(url_crew, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for item in soup.select('.item'):
                title_elem = item.select_one('.item__tit a')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href')
                if link and not link.startswith('http'):
                    link = "https://obchod.crew.cz" + link
                    
                price_elem = item.select_one('[itemprop="price"]')
                price = price_elem.get_text(strip=True) + " Kč" if price_elem else None
                
                img_elem = item.select_one('.item__img img')
                cover_url = img_elem.get('data-src') or img_elem.get('src')
                if cover_url and not cover_url.startswith('http'):
                    cover_url = "https://obchod.crew.cz" + cover_url
                    
                # Extract ID from link, e.g. /detail/komiks-1010071-disney-5minutove-komiksy
                m = re.search(r'komiks-(\d+)-', link)
                sku = m.group(1) if m else title
                
                result.append({
                    "id": f"crew_{sku}",
                    "title": title,
                    "url": link,
                    "price": price,
                    "cover_url": cover_url,
                    "date": None,
                    "released": False
                })
    except Exception as e:
        print(f"  [warn] Crew CZ: {e}")

    # 2. Scrape Egmont CZ (Alicanto)
    # They have Disney books on the homepage / specific category. We'll use a broad search.
    url_egmont = "https://www.egmont.cz/"
    try:
        r = s.get(url_egmont, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Look for all tituly links containing disney
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/tituly/' in href and 'disney' in href.lower():
                    # Egmont CZ returns just links on the homepage banner without full structured details sometimes,
                    # but we can grab the URL and extract an ID.
                    m = re.search(r'/tituly/(\d+)/', href)
                    if m:
                        sku = m.group(1)
                        if not any(b['id'] == f"egmont_{sku}" for b in result):
                            full_link = href if href.startswith('http') else "https://www.egmont.cz" + href
                            
                            # We can just fetch the title from the URL slug for now
                            slug = href.split('/')[-2] if href.endswith('/') else href.split('/')[-1]
                            title = slug.replace('-', ' ').title()
                            
                            result.append({
                                "id": f"egmont_{sku}",
                                "title": title,
                                "url": full_link,
                                "price": None,
                                "cover_url": None,
                                "date": None,
                                "released": False
                            })
    except Exception as e:
        print(f"  [warn] Egmont CZ: {e}")

    return result

def fetch_cz_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return {}
