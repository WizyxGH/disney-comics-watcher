import re
import json
import urllib.request
from src.scrapers.shared_panini import discover_panini_magento, fetch_panini_magento_details

def discover_panini_it():
    """Discovers Disney comics on Panini Italy."""
    url = "https://www.panini.it/shp_ita_it/fumetti/panini-disney.html"
    return discover_panini_magento(url, "IT")

def fetch_panini_it_details(url: str) -> dict:
    """Fetches additional details from the product page if needed."""
    return fetch_panini_magento_details(url, "IT")

def discover_giunti_it() -> list[dict]:
    """
    Discovers Italian Disney comics and graphic novels from Giunti Editore (giunti.it).
    Covers Le più belle storie, Letteratura a fumetti, Prime letture a fumetti, W.I.T.C.H., etc.
    """
    result = []
    seen = set()
    base_url = "https://www.giunti.it"

    # Paginate through Disney catalog (limit=100 per page, up to 3 pages)
    for page in range(1, 4):
        url = f"https://www.giunti.it/collections/disney-libri-tutto-il-catalogo/products.json?limit=100&page={page}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status != 200:
                    break
                data = json.loads(resp.read().decode("utf-8"))

            products = data.get("products", [])
            if not products:
                break

            for p in products:
                tags = p.get("tags", [])
                title = p.get("title", "").strip()
                if not title:
                    continue

                # Must be a comic / graphic novel / fumetto
                # BIC::YFW is the standard classification for comics & graphic novels
                lower_title = title.lower()
                is_comic = (
                    "BIC::YFW" in tags
                    or any(k in lower_title for k in [
                        "fumett", "le più belle storie", "letteratura a fumetti",
                        "graphic novel", "prime letture a fumetti"
                    ])
                )
                if not is_comic:
                    continue

                prod_id = str(p.get("id"))
                if prod_id in seen:
                    continue
                seen.add(prod_id)

                handle = p.get("handle", "")
                prod_url = f"{base_url}/products/{handle}"
                pub_date = p.get("published_at", "")[:10] if p.get("published_at") else None

                # Price in EUR
                price = None
                variants = p.get("variants", [])
                if variants and variants[0].get("price"):
                    price = f"{variants[0]['price']} €"

                # Cover image
                cover_url = None
                images = p.get("images", [])
                if images and images[0].get("src"):
                    cover_url = images[0]["src"]
                    if cover_url.startswith("//"):
                        cover_url = "https:" + cover_url

                # EAN / ISBN from handle
                ean = None
                if m_ean := re.search(r'(978\d{10})', handle):
                    ean = m_ean.group(1)

                # Inducks issue_path determination
                issue_path = "it/GIU"
                if "le più belle storie" in lower_title:
                    issue_path = "it/PBS"
                elif "letteratura a fumetti" in lower_title:
                    issue_path = "it/LF"
                elif "w.i.t.c.h." in lower_title:
                    issue_path = "it/WIT"

                result.append({
                    "id": f"giunti_{prod_id}",
                    "title": title,
                    "url": prod_url,
                    "price": price,
                    "cover_url": cover_url,
                    "date": pub_date,
                    "ean": ean,
                    "released": True,
                    "publisher": "Giunti Editore",
                    "issue_path": issue_path
                })
        except Exception as e:
            print(f"  [warn] discover_giunti_it failed on page {page}: {e}")

    return result

def fetch_giunti_it_details(url: str) -> dict:
    return {}
