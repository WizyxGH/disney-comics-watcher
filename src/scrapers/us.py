import re
import html as html_lib
from datetime import datetime
import http.client
http.client._MAXHEADERS = 1000

from src.config import FANTAGRAPHICS_DISNEY_URL, FANTAGRAPHICS_BASE, MARVEL_KEY_PREFIX
from src.utils import get_session


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
            
            # Target the grid container of actual issues (avoiding 'comic-series' which contains recommendations)
            grid = soup.select_one('div.FeaturedGrid__Container:not(.comic-series)')
            if not grid:
                grid = soup
                
            cards = grid.find_all('div', class_='ComicCard')
            for c in cards:
                link_tag = c.find('a', class_='ComicCard__Link', href=True)
                if not link_tag:
                    continue
                issue_url = "https://www.marvel.com" + link_tag['href']
                
                # Extract issue ID from URL e.g., /comics/issue/123735/...
                m = re.search(r'/issue/(\d+)/', issue_url)
                if not m:
                    # Skip cards pointing to series/related products rather than issues
                    continue
                issue_id = m.group(1)
                
                title_tag = c.find(class_='ComicCard__Meta__Title')
                title = title_tag.text.strip() if title_tag else "Unknown Title"
                
                img_tag = c.find('img')
                cover_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None
                
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

DYNAMITE_DISNEY = "https://disney.dynamite.com"
_RE_DYNAMITE_ON_SALE = re.compile(r"On Sale Date:\s*(\d{1,2})/(\d{1,2})/(\d{2,4})")


def _dynamite_on_sale(text: str) -> str | None:
    """'On Sale Date: 11/25/2026' (US month/day order) -> '2026-11-25'."""
    m = _RE_DYNAMITE_ON_SALE.search(text or "")
    if not m:
        return None
    month, day, year = m.groups()
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _dynamite_product_url(product_id: str) -> str:
    """Canonical product URL.

    Some listing cards link to the wrong product (Gargoyles Vol. 2 #4 points to
    the 2023 Gargoyles #4 page), while the product-id URL always resolves to
    the right one.
    """
    return f"{DYNAMITE_DISNEY}/products.php?productId={product_id}"


def discover_dynamite():
    """Discovers Disney comics on Dynamite's Disney storefront (BigCommerce).

    The "upcoming" category keeps titles listed after their release, so each
    one moves from announced to released on its on-sale date. Trade paperback
    cards carry that date in their summary; single issues list so many variant
    covers that the summary is truncated before it, so their product page is
    fetched instead.
    """
    from bs4 import BeautifulSoup

    s = get_session()
    result = []
    seen = set()
    for page in range(1, 20):
        try:
            r = s.get(f"{DYNAMITE_DISNEY}/upcoming/", params={"page": page}, timeout=15)
            r.raise_for_status()
        except Exception as e:
            # All or nothing: a partial catalogue would be seeded as the full one
            # on a first run, and the missing pages announced as new next time.
            print(f"  [warn] discover_dynamite page {page} failed, skipping this run: {e}")
            return []

        cards = BeautifulSoup(r.text, "html.parser").select("ul.productGrid article.card")
        new_ids = 0
        for card in cards:
            id_el = card.select_one("[data-product-id]")
            title_el = card.select_one(".card-title a")
            if not id_el or not title_el:
                continue
            product_id = id_el["data-product-id"]
            if product_id in seen:
                continue
            seen.add(product_id)
            new_ids += 1
            url = _dynamite_product_url(product_id)

            summary_el = card.select_one(".card-text--summary")
            date = _dynamite_on_sale(summary_el.get_text(" ")) if summary_el else None
            if not date:
                try:
                    date = _dynamite_on_sale(s.get(url, timeout=15).text)
                except Exception as e:
                    print(f"  [warn] Dynamite: no date for {title_el.get_text(strip=True)}: {e}")

            # "$4.99 - $100.00" when variant covers are sold separately: keep the base price.
            price_el = card.select_one(".price--main")
            price = price_el.get_text(strip=True).split(" - ")[0] if price_el else None

            img = card.select_one("img.card-image")
            cover = img.get("src") if img else None
            if cover:
                cover = re.sub(r"/stencil/[^/]+/", "/stencil/original/", cover)

            result.append({
                "id": product_id,
                "title": title_el.get_text(strip=True),
                "url": url,
                "price": price or None,
                "cover_url": cover,
                "date": date,
                "source": "dynamite",
            })

        # Past the last page BigCommerce may serve an empty grid or repeat the last one.
        if not new_ids:
            break

    return result


def fetch_dynamite_details(url: str) -> dict:
    """Fetches the synopsis and full-size cover from a Dynamite product page."""
    from bs4 import BeautifulSoup

    try:
        r = get_session().get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  [warn] Failed to fetch Dynamite details from {url}: {e}")
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    details = {}
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        details["cover_url"] = og["content"].split("?")[0]

    # The description is a credits block ending with "On Sale Date: …", then the synopsis.
    desc = soup.select_one(".productView-description")
    if desc:
        text = " ".join(desc.get_text(" ", strip=True).split())
        m = _RE_DYNAMITE_ON_SALE.search(text)
        synopsis = text[m.end():].strip() if m else ""
        if synopsis:
            details["summary"] = synopsis
    return details

