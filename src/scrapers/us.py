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


def discover_fantagraphics():
    """Discovers US Disney comic books at Fantagraphics using the Shopify products.json endpoint."""
    s = get_session()
    result = []
    
    # We load 2 pages of 250 products (way more than the ~30 Disney books they have right now)
    try:
        for page in range(1, 3):
            url = f"{FANTAGRAPHICS_DISNEY_URL}?limit=250&page={page}"
            r = s.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            products = data.get("products", [])
            if not products:
                break
                
            for prod in products:
                # Basic info
                title = prod.get("title", "Unknown Title")
                handle = prod.get("handle", "")
                url = f"{FANTAGRAPHICS_BASE}{handle}" if handle else FANTAGRAPHICS_BASE
                
                # Try to get ISBN or SKU from first variant
                variants = prod.get("variants", [])
                sku = variants[0].get("sku", "") if variants else ""
                price = variants[0].get("price", "") if variants else ""
                
                # Try to extract the cover URL
                images = prod.get("images", [])
                cover_url = images[0].get("src", "") if images else ""
                
                # Check for a "published_at" or "created_at"
                date_str = prod.get("published_at") or prod.get("created_at") or ""
                pub_date = None
                if date_str:
                    try:
                        # e.g., "2023-01-24T11:41:40-08:00"
                        dt = datetime.fromisoformat(date_str)
                        pub_date = dt.date()
                        date_str_fr = pub_date.strftime("%d/%m/%Y")
                    except Exception:
                        date_str_fr = date_str
                else:
                    date_str_fr = ""

                # Summary (body_html)
                summary_html = prod.get("body_html", "")
                summary_text = re.sub(r'</?(?:p|br|div)[^>]*>', '\n', summary_html)
                summary_text = re.sub(r'<[^>]+>', '', summary_text)
                summary_text = html_lib.unescape(summary_text)
                lines = [l.strip() for l in summary_text.split('\n')]
                cleaned_lines = []
                for line in lines:
                    if line:
                        cleaned_lines.append(line)
                    elif cleaned_lines and cleaned_lines[-1] != "":
                        cleaned_lines.append("")
                summary = "\n".join(cleaned_lines).strip()

                result.append({
                    "id": prod.get("id"),
                    "sku": sku,
                    "title": title,
                    "url": url,
                    "date": date_str_fr,
                    "pub_date": pub_date,
                    "price": f"${price}" if price else None,
                    "cover_url": cover_url,
                    "summary": summary
                })
    except Exception as e:
        print(f"  [warn] discover_fantagraphics: {e}")
        
    return result

def discover_marvel():
    """Discovers US Disney comic books on Marvel.com series pages."""
    from bs4 import BeautifulSoup
    from src.config import MARVEL_SERIES_URLS
    
    s = get_session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    result = []
    
    for url in MARVEL_SERIES_URLS:
        try:
            r = s.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            
            cards = soup.find_all('div', class_='ComicCard')
            for c in cards:
                title_tag = c.find(class_='ComicCard__Meta__Title')
                title = title_tag.text.strip() if title_tag else "Unknown Title"
                
                link_tag = c.find('a', class_='ComicCard__Link', href=True)
                issue_url = "https://www.marvel.com" + link_tag['href'] if link_tag else url
                
                # Extract issue ID from URL e.g., /comics/issue/123735/...
                m = re.search(r'/issue/(\d+)/', issue_url)
                issue_id = m.group(1) if m else title
                
                img_tag = c.find('img')
                cover_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None
                
                # Basic parsing, we consider the card presence as a release for our tracker
                result.append({
                    "id": issue_id,
                    "title": title,
                    "url": issue_url,
                    "cover_url": cover_url,
                    "source": "marvel"
                })
        except Exception as e:
            print(f"  [warn] discover_marvel failed for {url}: {e}")
            
    return result

