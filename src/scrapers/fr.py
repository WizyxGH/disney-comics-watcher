import re
import html as html_lib
import json
import requests
from datetime import datetime
import http.client
http.client._MAXHEADERS = 1000

from src.config import KEYWORDS, SKIP_CODIFS, BI_ISSUE_CODIFS, OVERRIDES, SEARCH_URL, SITE_BASE, MLP_FAMILIES, MLP_FAMILY_URL, MLP_URL, GLENAT_BASE, GLENAT_COLLECTION_URL
from src.utils import get_session, parse_date_fr


def parse_block(block):
    """Extracts codif/number/date/cover/url from a <div class='info-mag'> block."""
    codif_m   = re.search(r"<span>Codif :</span>\s*(\d+)", block)
    if not codif_m:
        return None
    num_m     = re.search(r"N° de parution\s*:</span>\s*([^<\s]+)", block)
    paru_m    = re.search(r"Paru le\s*:</span>\s*([^<\s]+)", block)
    prix_m    = re.search(r"Prix :</span>\s*([0-9.,]+\s*€)", block)
    expired_m = re.search(r"Trop vieux le\s*:</span>\s*(\d{2}/\d{2}/\d{4})", block)
    img_m     = re.search(r'<img src="([^"]+/parutions/[^"]+)"', block)
    href_m    = re.search(r'href="(/magazine/\d+_([a-z0-9-]+)[^"]*)"', block)
    alt_m     = re.search(r'<img src="[^"]+/parutions/[^"]+"\s+alt="([^"]+)"', block)

    cover_url = None
    if img_m:
        cover_url = re.sub(r"/\d+x\d+/parutions/", "/parutions/", img_m.group(1))
        if cover_url.startswith("/"):
            cover_url = SITE_BASE + cover_url

    numero = num_m.group(1) if num_m else None
    if numero and numero.upper().endswith("H"):
        numero = numero[:-1].strip()

    return {
        "codif":              codif_m.group(1),
        "numero":             numero,
        "date_mise_en_vente": paru_m.group(1) if paru_m else None,
        "prix":               re.sub(r"\s+", " ", prix_m.group(1)).strip() if prix_m else None,
        "expired_on":         expired_m.group(1) if expired_m else None,
        "cover_url":          cover_url,
        "url":                SITE_BASE + href_m.group(1) if href_m else SITE_BASE,
        "slug":               href_m.group(2) if href_m else "",
        "site_name":          html_lib.unescape(alt_m.group(1)) if alt_m else "",
    }


def discover_de():
    """Discovers all active Disney magazines on Direct Éditeurs.

    - Queries each keyword and deduplicates by codif.
    - Ignores expired magazines ('Trop vieux' date in the past).
    - If dates are equal, prefers the double issue format (3856-3857 > 3856).
    - Synthesizes the double issue format for BI_ISSUE_CODIFS if DE
      only published the single issue format.
    """
    s = get_session()
    today = datetime.now().date()
    candidates: dict[str, list] = {}

    for kw in KEYWORDS:
        try:
            r = s.post(SEARCH_URL, data={"searchParution.title": kw}, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  [warn] DE kw='{kw}': {e}")
            continue

        text   = r.text
        starts = [m.start() for m in re.finditer(r'<div class="info-mag"', text)]
        starts.append(len(text))

        for i in range(len(starts) - 1):
            info = parse_block(text[starts[i]: starts[i + 1]])
            if not info or info["codif"] in SKIP_CODIFS:
                continue
            if re.search(r'\bREV\b', info.get("site_name", "")):
                continue
            if info["expired_on"]:
                d = parse_date_fr(info["expired_on"])
                if d and d < today:
                    continue  # expired magazine
            candidates.setdefault(info["codif"], []).append(info)

    # Deduplication: most recent date first, then preference for the dash (double issue)
    result: dict[str, dict] = {}
    for codif, entries in candidates.items():
        def _key(e):
            d = parse_date_fr(e.get("date_mise_en_vente") or "")
            has_dash = "-" in (e.get("numero") or "")
            num_str = "".join(filter(str.isdigit, e.get("numero") or ""))
            num_val = int(num_str) if num_str else 0
            return (d or datetime.min.date(), has_dash, num_val)
        result[codif] = max(entries, key=_key)

    # Double issue synthesis if necessary
    for codif in BI_ISSUE_CODIFS:
        if codif in result:
            num = result[codif].get("numero") or ""
            if num and "-" not in num:
                try:
                    n = int(num)
                    result[codif] = dict(result[codif], numero=f"{n}-{n+1}")
                except ValueError:
                    pass

    return result


# ─────────────────────────────────────────────────────────────────────────────

from concurrent.futures import ThreadPoolExecutor, as_completed

def discover_mlp_families(known_codifs: set, state: dict | None = None):
    """Finds magazines missing from DE via MLP sub-families (e.g. D23, D15) and retrieves their details in parallel."""
    s = get_session()
    result: dict[str, dict] = {}
    state = state or {}

    from bs4 import BeautifulSoup

    def _fetch_product_details(href: str, codif: str, numero_list: str, date_list: str, title: str):
        prod_url = f"https://catalogueproduits.mlp.fr/{href}"
        try:
            rp = s.get(prod_url, timeout=10)
            if rp.status_code == 200:
                rp.encoding = "utf-8"
                unescaped_text = html_lib.unescape(rp.text)
                psoup = BeautifulSoup(unescaped_text, "html.parser")

                prix_span = psoup.find(id="ContentPlaceHolder1_ctl01_prix")
                num_detail_span = psoup.find(id="ContentPlaceHolder1_ctl00_num")
                meta_img = psoup.find("meta", property="og:image")

                prix = prix_span.get_text(strip=True) if prix_span else None
                num_detail = num_detail_span.get_text(strip=True) if num_detail_span else None
                cover_url = meta_img["content"] if meta_img else None

                if num_detail:
                    num_detail = re.sub(r"(?i)N°\s*", "", num_detail).strip()

                numero = num_detail or numero_list
                if numero and numero.upper().endswith("H"):
                    numero = numero[:-1].strip()

                releve = None
                patterns = [
                    r"[Jj]usqu[\x27\x22]au\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
                    r"[Rr]el[eè]ve?\s*(?:le|pr[eé]vue?)?\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
                ]
                for pat in patterns:
                    m = re.search(pat, unescaped_text)
                    if m:
                        releve = m.group(1)
                        break

                return {
                    "codif":              codif,
                    "numero":             numero,
                    "date_mise_en_vente": date_list.replace("-", "/"),
                    "prix":               prix,
                    "cover_url":          cover_url,
                    "url":                prod_url,
                    "slug":               codif,
                    "site_name":          title,
                    "expired_on":         None,
                    "releve_date":        releve,
                }
        except Exception as e:
            print(f"  [warn] MLP codif={codif} details: {e}")
        return None

    def _process_family(family: str):
        family_result = {}
        try:
            r = s.get(MLP_FAMILY_URL.format(family), timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  [warn] MLP family={family}: {e}")
            return family_result

        soup = BeautifulSoup(r.text, 'html.parser')
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for cat in soup.find_all(class_='catalogue'):
                code_span = cat.find(id=re.compile('results_ctl.*_titCode'))
                if not code_span:
                    continue
                codif = code_span.get_text(strip=True)

                if codif in known_codifs or codif in SKIP_CODIFS:
                    continue

                titre_span = cat.find(id=re.compile('results_ctl.*_titre'))
                num_span   = cat.find(id=re.compile('results_ctl.*_parNumero'))
                date_span  = cat.find(id=re.compile('results_ctl.*_dateParution'))
                link       = cat.find('a', href=True)

                title       = titre_span.get_text(strip=True) if titre_span else ""
                title_lower = title.lower()
                if codif not in OVERRIDES and not any(kw in title_lower for kw in KEYWORDS):
                    continue
                if re.search(r'\bREV\b', title):
                    continue

                numero_list = num_span.get_text(strip=True) if num_span else ""
                date_list   = date_span.get_text(strip=True) if date_span else ""
                href        = link['href'] if link else ""

                # We check if fr_kiosk:{codif}_{numero_list} exists and is 'released'
                if state.get(f'fr_kiosk:{codif}_{numero_list}') == 'released':
                    continue
                
                # Backwards compatibility check
                state_val = state.get(f'magazine:{codif}')
                if state_val:
                    digits_list = "".join(filter(str.isdigit, numero_list))
                    digits_state = "".join(filter(str.isdigit, state_val))
                    if digits_list and digits_state and digits_list == digits_state:
                        continue

                if href:
                    tasks.append(executor.submit(_fetch_product_details, href, codif, numero_list, date_list, title))

            for future in as_completed(tasks):
                res = future.result()
                if res:
                    family_result[res['codif']] = res

        return family_result

    # Process all families in parallel
    with ThreadPoolExecutor(max_workers=len(MLP_FAMILIES)) as executor:
        futures = [executor.submit(_process_family, fam) for fam in MLP_FAMILIES]
        for future in as_completed(futures):
            result.update(future.result())

    return result

def get_mlp_releve(codif: str):
    """Returns the expected off-sale date ('Jusqu'au') from MLP."""
    s = get_session()
    patterns = [
        r"[Jj]usqu[\x27\x22]au\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
        r"[Rr]el[eè]ve?\s*(?:le|pr[eé]vue?)?\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
    ]

    # Start by searching for the search links to find the actual product page
    search_url = f"{MLP_URL}?recherche={codif}"
    try:
        r = s.get(search_url, timeout=10)
        if r.status_code == 200:
            r.encoding = "utf-8"
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            for cat in soup.find_all(class_='catalogue'):
                code_span = cat.find(id=re.compile('results_ctl.*_titCode'))
                if code_span and code_span.get_text(strip=True) == codif:
                    link = cat.find('a', href=True)
                    if link:
                        prod_url = f"https://catalogueproduits.mlp.fr/{link['href']}"
                        rp = s.get(prod_url, timeout=10)
                        if rp.status_code == 200:
                            rp.encoding = "utf-8"
                            unescaped = html_lib.unescape(rp.text)
                            for pat in patterns:
                                m = re.search(pat, unescaped)
                                if m:
                                    return m.group(1)
    except Exception:
        pass

    # Fallback to standard URLs
    for url in [
        f"{MLP_URL}?recherche={codif}",
        f"{MLP_URL}?ref={codif}",
        f"https://catalogueproduits.mlp.fr/produit/{codif}",
    ]:
        try:
            r = s.get(url, timeout=10)
            if r.status_code != 200:
                continue
            r.encoding = "utf-8"
            unescaped = html_lib.unescape(r.text)
            for pat in patterns:
                m = re.search(pat, unescaped)
                if m:
                    return m.group(1)
        except requests.RequestException:
            continue
    return None



def discover_fr_kiosk():
    """Unified wrapper for French Kiosk magazines (DE and MLP) returning standard provider books format."""
    from src.utils import load_state
    state = load_state()
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [error] discover_de: {e}")
        magazines = {}

    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
    except Exception as e:
        print(f"  [error] discover_mlp: {e}")

    books = []
    for codif, info in magazines.items():
        if codif in SKIP_CODIFS:
            continue
        numero = info.get("numero")
        if not numero:
            continue

        ov   = OVERRIDES.get(codif, {})
        name = ov.get("name") or info.get("site_name") or codif
        
        info["id"] = f"{codif}_{numero}"
        info["title"] = f"{name} - N°{numero}"
        info["released"] = True
        
        # In check_magazines _process_provider_books, state tracks book_id = codif_numero.
        books.append(info)

    return books

def fetch_fr_kiosk_details(url: str) -> dict:
    return {}


def discover_glenat():
    """Discovers Disney comic books at Glénat (announcements + releases).

    - Retrieves data from the __NEXT_DATA__ JSON-LD block on each page
      for robust extraction of EAN, titles, release dates, and covers.
    - Avoids the old HTML regex which caused title context collisions.
    - Iterates over catalog pages using path-based pagination (e.g., /2/).
    """
    s = get_session()
    result = []
    seen: set[str] = set()

    # Retrieve page 1 and determine the total number of pages
    try:
        r = s.get(GLENAT_COLLECTION_URL, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"  [warn] Glenat: {e}")
        return result

    max_pages = 1
    pages_m = re.search(r'Page \d+ sur (\d+)', r.text)
    if pages_m:
        max_pages = min(int(pages_m.group(1)), 10)  # safety cap

    pages_to_scrape = [(1, r.text)]
    for page_num in range(2, max_pages + 1):
        try:
            url = f"{GLENAT_COLLECTION_URL}{page_num}/"
            rp = s.get(url, timeout=15)
            rp.raise_for_status()
            rp.encoding = "utf-8"
            pages_to_scrape.append((page_num, rp.text))
        except requests.RequestException as e:
            print(f"  [warn] Glenat p{page_num}: {e}")

    for page_num, html_text in pages_to_scrape:
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_text)
        if not m:
            print(f"  [warn] Glénat p{page_num}: No __NEXT_DATA__ block found.")
            continue

        try:
            data = json.loads(m.group(1))
            sections = data.get("props", {}).get("pageProps", {}).get("sections", [])
            
            # Search for the section containing prefilter_results
            target_sec = None
            for sec in sections:
                sec_data = sec.get("data") or {}
                if "prefilter_results" in sec_data:
                    target_sec = sec_data
                    break

            if not target_sec:
                continue

            results = target_sec.get("prefilter_results", [])
            for item in results:
                ean_list = item.get("product__ean")
                if not ean_list or not ean_list[0]:
                    continue
                ean = ean_list[0]
                if ean in seen or not ean.startswith("978"):
                    continue
                seen.add(ean)

                path = item.get("path", [""])[0]
                url = GLENAT_BASE + path

                title = item.get("product__titre_de_couverture", [None])[0] or item.get("title", [None])[0]
                if not title:
                    title = f"Album Disney ({ean})"

                # Extraction of the publication date
                date_str = item.get("product__date_parution", [None])[0]
                if not date_str:
                    date_str_raw = item.get("product__date_parution__date", [None])[0]
                    if date_str_raw:
                        try:
                            y, m, d = date_str_raw.split("-")
                            date_str = f"{d}/{m}/{y}"
                        except Exception:
                            pass
                else:
                    date_str = date_str.replace("-", "/")

                pub_date = parse_date_fr(date_str)

                # Cover URL
                cover_url = item.get("product__image_de_couverture", [None])[0]
                if cover_url:
                    # Clean URL query parameters (?v=...) as the images.hachette-livre.fr domain
                    # is publicly accessible and accepts requests without a cache-buster.
                    cover_url = cover_url.split("?")[0]

                # Fallback if image is missing in the JSON but we have the publication year
                if not cover_url and pub_date:
                    year = pub_date.year
                    cover_url = f"https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/{year}/{ean}-001-X.jpeg"

                result.append({
                    "ean":       ean,
                    "title":     title,
                    "url":       url,
                    "date":      date_str,
                    "pub_date":  pub_date,
                    "price":     None,  # Retrieved on-demand during notification
                    "cover_url": cover_url,
                })
        except Exception as e:
            print(f"  [warn] Glénat p{page_num}: JSON-LD parsing error: {e}")

    return result


def fetch_glenat_details(url: str) -> dict:
    """Retrieves on-demand price, summary, page count, size, and translator from the Glénat product page."""
    s = get_session()
    details = {
        "price": None,
        "summary": None,
        "pages": None,
        "size": None,
        "isstrans": None,
        "numero_de_tome": None,
        "collection_label": None,
        "serie_label": None
    }
    try:
        r = s.get(url, timeout=10)
        r.raise_for_status()
        r.encoding = "utf-8"
        text = r.text

        # 1. Price extraction
        price_m = re.search(r'"price"\s*:\s*"([0-9.]+)"', text)
        if price_m:
            details["price"] = price_m.group(1).replace(".", ",") + " €"
        else:
            price_m = re.search(r'itemprop="price"\s*content="([^"]+)"', text)
            if price_m:
                details["price"] = price_m.group(1).replace(".", ",") + " €"
            else:
                price_m = re.search(r'([0-9]+[,\.][0-9]{2})\s*(?:€|\u20ac)', text)
                if price_m:
                    details["price"] = price_m.group(1).replace(".", ",") + " €"

        # 2. Extraction of summary, page count, size, and translator (__NEXT_DATA__)
        next_m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text)
        if next_m:
            try:
                data = json.loads(next_m.group(1))
                product_data = data.get('props', {}).get('pageProps', {}).get('data', {})

                raw_summary = product_data.get('presentation_editoriale')
                if raw_summary:
                    summary_text = re.sub(r'</?(?:p|br|div)[^>]*>', '\n', raw_summary)
                    summary_text = re.sub(r'<[^>]+>', '', summary_text)
                    summary_text = html_lib.unescape(summary_text)
                    lines = [l.strip() for l in summary_text.split('\n')]
                    cleaned_lines = []
                    for line in lines:
                        if line:
                            cleaned_lines.append(line)
                        elif cleaned_lines and cleaned_lines[-1] != "":
                            cleaned_lines.append("")
                    details["summary"] = "\n".join(cleaned_lines).strip()

                # Page count
                nb_pages = (product_data.get('nb_pages')
                            or product_data.get('pages')
                            or product_data.get('page'))
                if nb_pages:
                    try:
                        details["pages"] = int(nb_pages)
                    except (ValueError, TypeError):
                        pass

                # Size (format: e.g. "21 x 28 cm" or "22 x 29" from multiple fields)
                format_val = (product_data.get('format_du_produit')
                              or product_data.get('format')
                              or product_data.get('dimensions'))
                if format_val and isinstance(format_val, str):
                    details["size"] = format_val.strip()
                else:
                    largeur = product_data.get('largeur')
                    hauteur = product_data.get('hauteur')
                    if largeur and hauteur:
                        details["size"] = f"{largeur} x {hauteur} mm"

                # Translator
                for contributor in product_data.get('contribuants', []) or []:
                    role = (contributor.get('role') or contributor.get('role_libelle') or "").lower()
                    if 'traduct' in role:
                        name = contributor.get('prenom', "").strip() + " " + contributor.get('nom', "").strip()
                        details["isstrans"] = name.strip() or None
                        break
                # Tome number
                tome_num = product_data.get('numero_de_tome')
                if tome_num is not None:
                    try:
                        details["numero_de_tome"] = int(tome_num)
                    except (ValueError, TypeError):
                        pass

                # Collection label
                collection_label = product_data.get('collection_label')
                if collection_label and isinstance(collection_label, str):
                    details["collection_label"] = collection_label.strip()

                # Serie label
                serie_label = product_data.get('serie_label')
                if serie_label and isinstance(serie_label, str):
                    details["serie_label"] = serie_label.strip()

            except Exception as e:
                print(f"  [warn] Unable to decode JSON details for {url}: {e}")

    except Exception as e:
        print(f"  [warn] Unable to fetch details for {url}: {e}")
    return details


