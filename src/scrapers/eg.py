"""
eg.py
=====
Scraper for Egyptian Disney comics published by Nahdet Misr (دار نهضة مصر).
Extracts releases from the official Nahdet Misr online bookstore
(nahdetmisrbookstore.com) and resolves product metadata, pricing, and HD covers.
Strictly filters out preschool, coloring, activity, and non-comic books,
retaining only genuine Disney comics (BD) that belong to Inducks publications.
"""

import re
import json
import urllib.parse
from bs4 import BeautifulSoup
from src.utils import get_session
from src.dbi.isv_search import search_publication_code

# Preschool / activity / coloring / learning books that contain NO comics and are never on Inducks
NON_COMIC_EXCLUDE = [
    # Arabic exclusions
    'تلوين', 'أنشطة', 'انشطة', 'نشاط', 'إبحث عن', 'ابحث عن',
    'كيف ترسم', 'حجم كبير', 'حكاياتي الأولى', 'حكاياتي الاولى',
    '365 قصة', '365قصة', 'أجمل الحكايات', 'اجمل الحكايات',
    'وصفات', 'الجمع و الطرح', 'addition', 'الاعداد', 'أستمع و تعلم',
    'تعليمية', 'ملصقات', 'مانجا', 'cd', 'اسطوانة', 'ألعاب', 'العاب',
    'سلسلة ابدأ', 'كلمة وقصة', 'خط عربي', 'الخط العربي', 'درب نفسك',
    # English exclusions
    'coloring', 'activity', 'activities', 'learning', 'how to draw', 'first stories',
    'storybook', 'cookbook', 'recipes', 'flash cards', 'puzzle', 'sound book',
    'jumbo coloring', 'color and play', 'phonics', 'levels of reading', 'movie night',
    '5-minutes', '5 minutes'
]

# Genuine Disney comic / BD magazines and albums published in Egypt (matching Inducks series)
COMIC_SERIES_KEYWORDS = [
    'مجلة ميكي', 'مجلة ميكى', 'ميكي جيب', 'ميكى جيب',
    'مجلد ميكي', 'مجلد ميكى', 'مجلد ميكي جيب', 'مجلد ميكى جيب',
    'ميكي مكس', 'ميكى مكس', 'سوبر ميكي', 'سوبر ميكى',
    'ديزني كوميكس', 'ديزنى كوميكس', 'سوبر بطوط', 'مغامرات بطوط', 'مغامرات عم دهب',
    'بطوط الذهبى', 'بطوط الذهبي', 'ميكى الذهبى', 'ميكي الذهبي',
    'فرسان المجرة', 'دراكولا', 'فرانكشتاين', 'هاملت', 'بطل من ورق'
]

SEARCH_QUERIES = [
    "مجلة ميكي", "مجلد ميكي", "ميكي جيب", "سوبر ميكي", "ديزني كوميكس", "ميكي"
]


def _is_valid_disney_comic_eg(title: str) -> bool:
    """
    Checks whether the title is genuinely a Disney comic (BD) indexed on Inducks.
    Rejects coloring, activity, preschool, and non-comic books.
    """
    if not title:
        return False
    t = title.lower()

    # 1. Strictly reject coloring / activity / preschool books
    if any(exc in t for exc in NON_COMIC_EXCLUDE):
        return False

    # 2. Check if title matches known Egyptian comic series keywords
    if any(k in t for k in COMIC_SERIES_KEYWORDS):
        return True

    # 3. Check if Inducks resolves it to an Egyptian comic publication code
    try:
        code = search_publication_code(title, "eg")
        if code and code.startswith("eg/"):
            return True
    except Exception:
        pass

    return False


def discover_nahdet_misr_eg() -> list[dict]:
    """
    Discovers Disney comics and magazines published by Nahdet Misr (Egypt).
    Queries the official Nahdet Misr store for Disney comic publications.
    """
    s = get_session()
    result = []
    seen_ids = set()

    for q in SEARCH_QUERIES:
        url = f"https://nahdetmisrbookstore.com/ar/products?search={urllib.parse.quote(q)}"
        try:
            r = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            for title_el in soup.find_all(class_="product-title"):
                title = title_el.text.strip()
                if not _is_valid_disney_comic_eg(title):
                    continue

                parent = title_el
                for _ in range(6):
                    if parent.parent:
                        parent = parent.parent
                    if "product" in " ".join(parent.get("class", [])):
                        break

                link_el = parent.find("a", href=True)
                href = link_el["href"] if link_el else None
                if not href:
                    continue

                full_url = urllib.parse.urljoin("https://nahdetmisrbookstore.com", href)
                sku = href.strip("/").split("/")[-1]

                if sku in seen_ids:
                    continue
                seen_ids.add(sku)

                # Attempt price extraction from card
                price_val = None
                price_el = parent.find(class_=re.compile(r"price-value|main-price|new-price", re.I))
                if price_el:
                    price_text = price_el.text.strip()
                    if price_text:
                        price_val = price_text

                # Attempt thumbnail image extraction
                img_el = parent.find("img")
                cover_url = img_el.get("src") if img_el else None

                result.append({
                    "id": sku,
                    "title": title,
                    "url": full_url,
                    "price": price_val,
                    "cover_url": cover_url,
                    "date": None,
                    "released": True,
                    "publisher": "Nahdet Misr",
                })
        except Exception as e:
            print(f"  [warn] Nahdet Misr EG search '{q}': {e}")

    return result


def fetch_nahdet_misr_eg_details(url: str) -> dict:
    """
    Fetches detailed metadata (HD cover, exact price, description)
    from a Nahdet Misr product page via Angular TransferState or DOM fallback.
    """
    details = {}
    try:
        s = get_session()
        r = s.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code != 200:
            return details

        soup = BeautifulSoup(r.text, "html.parser")

        # 1. Extract from Angular TransferState
        for sc in soup.find_all("script"):
            if sc.text and "detail-product:ar" in sc.text:
                try:
                    d = json.loads(sc.text)
                    for k, v in d.items():
                        if k.startswith("detail-product:"):
                            prod = v.get("data", {}).get("product", {})
                            if prod:
                                if prod.get("image"):
                                    details["cover_url"] = prod["image"]
                                elif prod.get("images") and len(prod["images"]) > 0:
                                    details["cover_url"] = prod["images"][0].get("url")

                                price_num = prod.get("discount_price") or prod.get("price")
                                if price_num:
                                    details["price"] = f"{price_num} €"

                                desc = prod.get("description") or prod.get("long_description")
                                if desc:
                                    details["summary"] = desc

                                return details
                except Exception:
                    pass

        # 2. DOM fallback
        p_el = soup.find(class_=lambda c: c and "main-price" in c)
        if p_el:
            details["price"] = p_el.text.strip()

        img_el = soup.find("img", src=lambda src: src and ("uploads" in src or "supercommerce" in src))
        if img_el:
            details["cover_url"] = img_el.get("src")

        h1 = soup.find("h1")
        if h1 and not details.get("title"):
            details["title"] = h1.text.strip()

    except Exception as e:
        print(f"  [warn] Failed to fetch Nahdet Misr EG details for {url}: {e}")

    return details
