import html as html_lib
import json
import os
import re
import time
import requests
from datetime import datetime
from urllib.parse import quote, quote_plus
from zoneinfo import ZoneInfo

from dbi_generator import build_inducks_path, generate_dbi_skeleton, DBI_FILE

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Mots-clés pour la découverte automatique sur Direct Éditeurs + MLP
KEYWORDS = ["picsou", "mickey", "mickey hs", "mickey parade", "fantomiald", "donald"]

# Codifs à ignorer explicitement (mal catégorisés sur MLP)
SKIP_CODIFS = {
    "11560",  # ANIME CULT (classé à tort en sous-famille Disney D23)
}

# Magazines qui paraissent en double numéro (ex: JdM 3856-3857).
# Si DE/MLP ne publie que la forme simple N, on synthétise N-(N+1).
BI_ISSUE_CODIFS = {
    "14067",  # Journal de Mickey
}

# Overrides : nom affiché et code Inducks (optionnel).
# Format inducks :
#   - str simple   : code → fr/<code> <num>
#   - (code, w)    : numéro zfill(w)
#   - (code, w, s) : numéro zfill(w) + suffixe s
OVERRIDES = {
    # ── Picsou Magazine et déclinaisons ──────────────────────────────────────
    "13159": {"name": "Picsou Magazine",                        "inducks": ("PM", 5)},
    "15681": {"name": "Picsou Magazine HS Collection Deluxe",   "inducks": ("CD", 5)},
    "15930": {"name": "Picsou Mag HS Collection Deluxe vol.2",  "inducks": ("CD", 5)},
    "18288": {"name": "Picsou HS Castors Juniors",              "inducks": ("PMHS", 3, "S")},
    "19603": {"name": "Picsou HS Souvenirs du Klondike"},
    "17575": {"name": "Picsou Anniversaire en or"},
    "18658": {"name": "Picsou Soir"},
    "18360": {"name": "Nouvelle Jeunesse de Picsou"},
    "19607": {"name": "Le Destin de Picsou"},
    "19052": {"name": "Pochette Picsou Magazine"},
    # ── Super Picsou Géant et déclinaisons ───────────────────────────────────
    "14016": {"name": "Super Picsou Géant",                     "inducks": "SPG"},
    "12651": {"name": "SPG HS Dynastie de Picsou",              "inducks": ("SPGHS", 3, "H")},
    "15599": {"name": "SPG HS Dynastie de Picsou (REV)",        "inducks": ("SPGHS", 3, "H")},
    "12825": {"name": "SPG HS Super Donald Géant",              "inducks": ("SPGHS", 3, "D")},
    "18262": {"name": "SPG HS Super Donald Géant (REV)",        "inducks": ("SPGHS", 3, "D")},
    "18268": {"name": "SPG HS Donald Double Duck (REV)",        "inducks": ("DON", 4)},
    "13459": {"name": "SPG HS Jeux",                            "inducks": ("SPGHS", 3, "J")},
    "11065": {"name": "SPG HS Les Méchants",                    "inducks": ("SPGHS", 3, "M")},
    # ── Trésors de Picsou ────────────────────────────────────────────────────
    "14068": {"name": "Les Trésors de Picsou",                  "inducks": "TP"},
    # ── Journal de Mickey et déclinaisons ────────────────────────────────────
    "14067": {"name": "Journal de Mickey",                      "inducks": "JM"},
    "14108": {"name": "Journal de Mickey HS",                   "inducks": ("JMHSN", 3)},
    "13588": {"name": "JdM HS Spécial Aventures (REV)"},
    "16096": {"name": "Journal de Mickey + Produit"},
    "15935": {"name": "Le Meilleur du Journal de Mickey"},
    "15970": {"name": "Le Meilleur du JdM HS"},
    "18914": {"name": "Le Meilleur du JdM HS Spécial Enquêtes"},
    # ── Mickey Parade ────────────────────────────────────────────────────────
    "11068": {"name": "Pochette Mickey Parade"},
    # ── Fantomiald ───────────────────────────────────────────────────────────
    "15190": {"name": "Les Chroniques de Fantomiald",           "inducks": ("CF", 5)},
    # ── Disney divers ────────────────────────────────────────────────────────
    "14268": {"name": "Les Incontournables de Disney",          "inducks": ("LI", 4)},
    "19064": {"name": "Les Incontournables (REV)",              "inducks": ("LI", 4)},
}


# Fuseau horaire de Paris pour la cohérence des dates
PARIS_TZ = ZoneInfo("Europe/Paris")

SEARCH_URL     = "https://direct-editeurs.fr/nos-magazines"
SITE_BASE      = "https://direct-editeurs.fr"
MLP_URL        = "https://catalogueproduits.mlp.fr/Default.aspx"
MLP_FAMILY_URL = "https://catalogueproduits.mlp.fr/liste.aspx?ssFam={}"
MLP_FAMILIES   = ["D23", "D15"]

GLENAT_COLLECTION_URL = "https://www.glenat.com/livres-glenat-disney/"
GLENAT_BASE           = "https://www.glenat.com"
GLENAT_KEY_PREFIX     = "glenat:"

STATE_FILE    = "state.json"

# Credentials Telegram — injectés via secrets GitHub Actions
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = (
    os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID", "")
)
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DisneyComicsWatcher/1.0)"}

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "")


# ─────────────────────────────────────────────────────────────────────────────
#  Session HTTP partagée
# ─────────────────────────────────────────────────────────────────────────────

_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        try:
            _session.get(SEARCH_URL, timeout=15)
        except requests.RequestException:
            pass
    return _session


# ─────────────────────────────────────────────────────────────────────────────
#  Gestion du state
# ─────────────────────────────────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  Parsing Direct Éditeurs
# ─────────────────────────────────────────────────────────────────────────────

def parse_date_fr(s):
    """DD/MM/YYYY → objet date, ou None si invalide."""
    if not s:
        return None
    try:
        d, m, y = str(s).strip().split("/")
        return datetime(int(y), int(m), int(d)).date()
    except (ValueError, AttributeError):
        return None


def parse_block(block):
    """Extrait codif/numéro/date/cover/url depuis un bloc <div class='info-mag'>."""
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

    return {
        "codif":              codif_m.group(1),
        "numero":             num_m.group(1) if num_m else None,
        "date_mise_en_vente": paru_m.group(1) if paru_m else None,
        "prix":               re.sub(r"\s+", " ", prix_m.group(1)).strip() if prix_m else None,
        "expired_on":         expired_m.group(1) if expired_m else None,
        "cover_url":          cover_url,
        "url":                SITE_BASE + href_m.group(1) if href_m else SITE_BASE,
        "slug":               href_m.group(2) if href_m else "",
        "site_name":          html_lib.unescape(alt_m.group(1)) if alt_m else "",
    }


def discover_de():
    """Découvre tous les magazines Disney actifs sur Direct Éditeurs.

    - Interroge chaque mot-clé et déduplique par codif.
    - Ignore les magazines périmés (date 'Trop vieux' dans le passé).
    - À date égale, préfère le format bi-numéro (3856-3857 > 3856).
    - Synthétise le format bi-numéro pour les codifs BI_ISSUE_CODIFS si DE
      n'a publié que la forme simple.
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
            if info["expired_on"]:
                d = parse_date_fr(info["expired_on"])
                if d and d < today:
                    continue  # magazine périmé
            candidates.setdefault(info["codif"], []).append(info)

    # Déduplication : date la plus récente, puis préférence pour le tiret
    result: dict[str, dict] = {}
    for codif, entries in candidates.items():
        def _key(e):
            d = parse_date_fr(e.get("date_mise_en_vente") or "")
            has_dash = "-" in (e.get("numero") or "")
            return (d or datetime.min.date(), has_dash)
        result[codif] = max(entries, key=_key)

    # Synthèse bi-numéro si nécessaire
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
#  MLP — découverte complémentaire et date de relève
# ─────────────────────────────────────────────────────────────────────────────

def discover_mlp_families(known_codifs: set, state: dict | None = None):
    """Rattrape les magazines absents de DE via les sous-familles MLP (ex: D23, D15) et récupère leurs détails."""
    s = get_session()
    result: dict[str, dict] = {}
    state = state or {}

    from bs4 import BeautifulSoup

    for family in MLP_FAMILIES:
        try:
            r = s.get(MLP_FAMILY_URL.format(family), timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
        except requests.RequestException as e:
            print(f"  [warn] MLP famille={family}: {e}")
            continue

        soup = BeautifulSoup(r.text, 'html.parser')

        # Parcourir les blocs de produits de la classe 'catalogue'
        for cat in soup.find_all(class_='catalogue'):
            code_span = cat.find(id=re.compile('results_ctl.*_titCode'))
            if not code_span:
                continue
            codif = code_span.get_text(strip=True)

            if codif in known_codifs or codif in result or codif in SKIP_CODIFS:
                continue

            titre_span = cat.find(id=re.compile('results_ctl.*_titre'))
            num_span   = cat.find(id=re.compile('results_ctl.*_parNumero'))
            date_span  = cat.find(id=re.compile('results_ctl.*_dateParution'))
            link       = cat.find('a', href=True)

            title       = titre_span.get_text(strip=True) if titre_span else ""
            numero_list = num_span.get_text(strip=True) if num_span else ""
            date_list   = date_span.get_text(strip=True) if date_span else ""
            href        = link['href'] if link else ""

            # Optimisation : Si le codif est déjà connu dans state et que le numéro
            # de parution (chiffres uniquement) correspond, on évite la requête détail.
            state_val = state.get(codif)
            if state_val:
                digits_list = "".join(filter(str.isdigit, numero_list))
                digits_state = "".join(filter(str.isdigit, state_val))
                if digits_list and digits_state and digits_list == digits_state:
                    continue

            # Fetch la fiche produit pour récupérer le prix, la grande image et la relève
            if href:
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

                        # Date de relève
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

                        result[codif] = {
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

    return result


def get_mlp_releve(codif: str):
    """Retourne la date de relève prévisionnelle (« Jusqu'au ») depuis MLP."""
    s = get_session()
    patterns = [
        r"[Jj]usqu[\x27\x22]au\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
        r"[Rr]el[eè]ve?\s*(?:le|pr[eé]vue?)?\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
    ]

    # On commence par chercher les liens de recherche pour trouver la vraie fiche produit
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

    # Fallback sur les URLs classiques
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


# ─────────────────────────────────────────────────────────────────────────────
#  Glénat — albums BD Disney
# ─────────────────────────────────────────────────────────────────────────────

def discover_glenat():
    """Découvre les albums BD Disney chez Glénat (annonces + sorties).

    - Récupère les données depuis le bloc JSON-LD __NEXT_DATA__ de chaque page
      pour une extraction robuste des EAN, titres, dates de parution et couvertures.
    - Évite l'ancienne regex HTML qui provoquait des collisions de contexte de titre.
    - Parcourt les pages du catalogue en utilisant la pagination par chemin (ex: /2/).
    """
    s = get_session()
    result = []
    seen: set[str] = set()

    # Récupérer la page 1 et déterminer le nombre total de pages
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
        max_pages = min(int(pages_m.group(1)), 10)  # plafond de sécurité

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
            print(f"  [warn] Glénat p{page_num}: Aucun bloc __NEXT_DATA__ trouvé.")
            continue

        try:
            data = json.loads(m.group(1))
            sections = data.get("props", {}).get("pageProps", {}).get("sections", [])
            
            # Recherche de la section contenant prefilter_results
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

                # Extraction de la date de parution
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

                # URL de couverture
                cover_url = item.get("product__image_de_couverture", [None])[0]
                if cover_url:
                    # Nettoie les paramètres d'URL (?v=...) car le domaine images.hachette-livre.fr
                    # est accessible publiquement et accepte les requêtes sans cache-buster.
                    cover_url = cover_url.split("?")[0]

                # Fallback si l'image est manquante dans le JSON mais qu'on a le millésime
                if not cover_url and pub_date:
                    year = pub_date.year
                    cover_url = f"https://www.images.hachette-livre.fr/media/imgArticle/GLENAT/{year}/{ean}-001-X.jpeg"

                result.append({
                    "ean":       ean,
                    "title":     title,
                    "url":       url,
                    "date":      date_str,
                    "pub_date":  pub_date,
                    "price":     None,  # Récupéré à la demande lors de la notification
                    "cover_url": cover_url,
                })
        except Exception as e:
            print(f"  [warn] Glénat p{page_num}: Erreur de parsing JSON-LD: {e}")

    return result


def fetch_glenat_details(url: str) -> dict:
    """Récupère à la demande prix, résumé, nb. de pages, dimensions et traducteur depuis la fiche produit Glénat."""
    s = get_session()
    details = {"price": None, "summary": None, "pages": None, "size": None, "isstrans": None}
    try:
        r = s.get(url, timeout=10)
        r.raise_for_status()
        r.encoding = "utf-8"
        text = r.text

        # 1. Extraction du prix
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

        # 2. Extraction du résumé, pages, dimensions et traducteur (__NEXT_DATA__)
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

                # Nombre de pages
                nb_pages = product_data.get('nb_pages') or product_data.get('pages')
                if nb_pages:
                    try:
                        details["pages"] = int(nb_pages)
                    except (ValueError, TypeError):
                        pass

                # Dimensions (format : ex. "21 x 28 cm" ou "22 x 29" depuis plusieurs champs)
                format_val = (product_data.get('format_du_produit')
                              or product_data.get('format')
                              or product_data.get('dimensions'))
                if format_val and isinstance(format_val, str):
                    details["size"] = format_val.strip()

                # Traducteur
                for contributor in product_data.get('contribuants', []) or []:
                    role = (contributor.get('role') or contributor.get('role_libelle') or "").lower()
                    if 'traduct' in role:
                        name = contributor.get('prenom', "").strip() + " " + contributor.get('nom', "").strip()
                        details["isstrans"] = name.strip() or None
                        break

            except Exception as e:
                print(f"  [warn] Impossible de décoder les détails JSON pour {url}: {e}")

    except Exception as e:
        print(f"  [warn] Impossible de récupérer les détails pour {url}: {e}")
    return details


def truncate_summary(text: str, max_len: int = 400) -> str:
    """Tronque proprement le résumé pour ne pas couper de mot."""
    if not text or len(text) <= max_len:
        return text or ""
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.strip() + "…"


# ─────────────────────────────────────────────────────────────────────────────
#  Notifications Telegram
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(photo_url: str | None, caption: str, buttons: list | None = None, retries: int = 5):
    """Envoie un message Telegram avec photo (sendPhoto) ou texte seul (sendMessage).
    Gère automatiquement les rate limits (429) et les photos inaccessibles.
    buttons : liste de lignes de boutons, ex: [[{"text": "Voir", "url": "..."}]]
    Retourne le message_id Telegram (int) si succès, None sinon."""
    delay = 2
    reply_markup = {"inline_keyboard": buttons} if buttons else None
    for attempt in range(retries):
        try:
            if photo_url:
                payload = {
                    "chat_id":    TELEGRAM_CHAT_ID,
                    "photo":      photo_url,
                    "caption":    caption,
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload, timeout=15)
                # Fallback texte si l'image est inaccessible
                if resp.status_code == 400:
                    print(f"  [debug] Telegram 400 error: {resp.text}")
                    desc = resp.json().get("description", "").lower()
                    if any(k in desc for k in ("photo", "wrong url", "failed to get", "url")):
                        print(f"  [warn] Photo inaccessible → fallback texte")
                        photo_url = None
                        continue
            else:
                payload = {
                    "chat_id":                  TELEGRAM_CHAT_ID,
                    "text":                     caption[:4096],
                    "parse_mode":               "HTML",
                    "disable_web_page_preview": True,
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", delay)
                print(f"  [429] Rate limit Telegram — attente {retry_after}s…")
                time.sleep(retry_after)
                delay = max(delay * 2, retry_after + 1)
                continue

            resp.raise_for_status()
            return resp.json().get("result", {}).get("message_id")

        except requests.RequestException as e:
            print(f"  [erreur] Telegram (tentative {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)

    print("  [ECHEC] Notification Telegram non envoyée.")
    return None





def build_inducks_url(inducks, numero: str) -> str | None:
    """Construit l'URL Inducks pour un numéro de parution donné."""
    path = build_inducks_path(inducks, numero)
    if not path:
        return None
    return f"https://inducks.org/issue.php?c={quote_plus(path)}"


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Convertit un ISBN-13 (commençant par 978) en ISBN-10 (ASIN Amazon)."""
    clean = "".join(filter(str.isdigit, isbn13))
    if len(clean) != 13 or not clean.startswith("978"):
        return None
    
    digits = clean[3:12]
    
    total = sum(int(digit) * (10 - i) for i, digit in enumerate(digits))
    rem = total % 11
    check = 11 - rem
    if check == 10:
        check_char = "X"
    elif check == 11:
        check_char = "0"
    else:
        check_char = str(check)
        
    return digits + check_char


def fetch_disneymagazines_cover(slug: str) -> str | None:
    """Tente de récupérer une meilleure image de couverture depuis disneymagazines.fr."""
    if not slug:
        return None
    url = f"https://www.disneymagazines.fr/titre/{slug}"
    try:
        s = get_session()
        r = s.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=10
        )
        if r.status_code == 200:
            # 1er choix : URL twic.pics (CDN natif, meilleure qualité) — on retire les query params
            m = re.search(r'"(https://fleuruspresse-disney\.twic\.pics/media/[^"]+\.jpg)[^"]*"', r.text)
            if m:
                return m.group(1)
            # 2e choix : URL cache Google Merchant sur disneymagazines.fr
            m = re.search(r'"(https://www\.disneymagazines\.fr/media/cache/[^"]+\.jpg)"', r.text)
            if m:
                return m.group(1)
            # 3e choix : src relatif
            m = re.search(r'src="(/media/image/[^"]+\.jpg)"', r.text)
            if m:
                return f"https://www.disneymagazines.fr{m.group(1)}"
    except Exception as e:
        print(f"  [warn] Impossible de récupérer la couverture sur DisneyMagazines pour {slug}: {e}")
    return None


def notify_magazine(info: dict, releve_date: str | None = None):
    """Envoie la notification Telegram pour un nouveau numéro de magazine."""
    codif = info["codif"]
    ov    = OVERRIDES.get(codif, {})
    name  = ov.get("name") or info.get("site_name") or info.get("slug") or codif
    num   = info.get("numero", "?")
    prix  = info.get("prix")
    date  = info.get("date_mise_en_vente")
    url   = info.get("url", SITE_BASE)

    title_line = f"<b>{html_lib.escape(name)} {num}</b>"
    lines = [title_line, ""]
    if prix:
        lines.append(f"💶 {html_lib.escape(prix)}")
    if date:
        lines.append(f"📅 Paru le : {date}")
    if releve_date:
        lines.append(f"📅 En kiosque jusqu'au : {releve_date}")

    # Boutons inline keyboard
    inducks_url = build_inducks_url(ov.get("inducks"), num)
    if not inducks_url:
        inducks_url = f"https://inducks.org/search.php?search={quote(f'{name} {num}')}"
    buttons = [
        [{"text": "Voir sur Direct-éditeurs", "url": url}],
        [{"text": "Sommaire sur Inducks", "url": inducks_url}],
    ]

    cover_url = info.get("cover_url")
    if not cover_url:
        disney_cover = fetch_disneymagazines_cover(info.get("slug"))
        if disney_cover:
            print(f"  [info] Couverture trouvée sur DisneyMagazines: {disney_cover}")
            cover_url = disney_cover

    send_telegram(cover_url, "\n".join(lines), buttons=buttons)
    time.sleep(1)  # throttle

    # Génération du squelette de pré-index Inducks
    generate_dbi_skeleton(info, publication_type="magazine", overrides=OVERRIDES)



def build_glenat_inducks_url(title: str) -> str:
    """Construit l'URL Inducks pour un album Glénat (si possible direct, sinon recherche)."""
    title_lower = title.lower()
    tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
    tome_num = int(tome_match.group(1)) if tome_match else None

    # 1. La Grande Histoire/Épopée de Picsou (Don Rosa) -> code GHP
    if "grande histoire de picsou" in title_lower or "grande epopee de picsou" in title_lower or "grande épopée de picsou" in title_lower:
        if tome_num is not None:
            return f"https://inducks.org/issue.php?c=fr/GHP+{tome_num}"
        return "https://inducks.org/publication.php?c=fr/GHP"

    # 2. Les Âges d'or (Picsou, Donald, Mickey, etc.) -> code AOD
    if "ages d'or" in title_lower or "âges d'or" in title_lower or "age d'or" in title_lower or "âge d'or" in title_lower:
        if tome_num is not None:
            return f"https://inducks.org/issue.php?c=fr/AOD+{tome_num}"
        return "https://inducks.org/publication.php?c=fr/AOD"

    return f"https://inducks.org/search.php?search={quote(title)}"


def notify_glenat_announce(album: dict):
    """Notification d'annonce Glénat (album à paraître)."""
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption : métadonnées + résumé tronqué
    meta_lines = [f"<b>Annonce — {title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Parution prévue : {album['date']}")
    if album.get("price"):
        meta_lines.append(f"💶 {html_lib.escape(album['price'])}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Boutons inline keyboard
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Génération du squelette de pré-index Inducks
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


def notify_glenat_release(album: dict):
    """Notification de sortie Glénat (album disponible en librairie)."""
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption : métadonnées + résumé tronqué
    meta_lines = [f"<b>{title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Paru le : {album['date']}")
    if album.get("price"):
        meta_lines.append(f"💶 {html_lib.escape(album['price'])}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Boutons inline keyboard
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Génération du squelette de pré-index Inducks
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── State ─────────────────────────────────────────────────────────────────
    state = load_state()
    first_run = not state
    if first_run:
        print("[init] Premier run — initialisation silencieuse (aucune notification).")

    notif_count = 0
    today = datetime.now(PARIS_TZ).date()

    # ── Direct Éditeurs ───────────────────────────────────────────────────────
    print("[DE] Découverte des magazines…")
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [erreur] discover_de: {e}")
        magazines = {}
    print(f"  → {len(magazines)} magazine(s) actif(s).")

    # ── MLP complémentaire ────────────────────────────────────────────────────
    print("[MLP] Découverte complémentaire…")
    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
        print(f"  → +{len(added)} codif(s) MLP unique(s).")
    except Exception as e:
        print(f"  [erreur] discover_mlp: {e}")

    # ── Traitement magazines ──────────────────────────────────────────────────
    for codif, info in magazines.items():
        if codif in SKIP_CODIFS:
            continue
        numero = info.get("numero")
        if not numero:
            continue

        last = state.get(codif)
        if numero == last:
            continue  # pas de changement

        ov   = OVERRIDES.get(codif, {})
        name = ov.get("name") or info.get("site_name") or codif
        print(f"  [NEW] {name} — N°{numero}  (précédent: {last or '—'})")

        if not first_run:
            releve = info.get("releve_date")
            if not releve:
                try:
                    releve = get_mlp_releve(codif)
                except Exception:
                    pass
            notify_magazine(info, releve_date=releve)
            notif_count += 1

        state[codif] = numero

    # ── Glénat ────────────────────────────────────────────────────────────────
    print("[Glénat] Découverte des albums BD Disney…")
    try:
        glenat_albums = discover_glenat()
        print(f"  → {len(glenat_albums)} album(s) trouvé(s).")
    except Exception as e:
        print(f"  [erreur] discover_glenat: {e}")
        glenat_albums = []

    for album in glenat_albums:
        ean = album.get("ean")
        if not ean:
            continue
        key     = f"{GLENAT_KEY_PREFIX}{ean}"
        current = state.get(key)
        pub_date = album.get("pub_date")

        if current is None:
            # Nouvel album détecté
            if pub_date and pub_date <= today:
                # Déjà sorti dans le passé -> on l'enregistre directement comme sorti sans notifier
                print(f"  [SORTIE-SILENT-INIT] {album.get('title', ean)}")
                state[key] = "released"
            else:
                # Album à paraître -> notification d'annonce
                if not first_run:
                    # Récupère les détails à la demande avant d'envoyer la notification
                    details = fetch_glenat_details(album["url"])
                    album["price"] = details.get("price")
                    album["summary"] = details.get("summary")
                    print(f"  [ANNONCE] {album.get('title', ean)} — Prix: {album.get('price') or 'non renseigné'}")
                    notify_glenat_announce(album)
                    notif_count += 1
                else:
                    print(f"  [ANNONCE-SILENT] {album.get('title', ean)}")
                state[key] = "announced"

        elif current == "announced" and pub_date and pub_date <= today:
            # Album annoncé dont la date de parution est atteinte → sortie en librairie
            if not first_run:
                # Récupère les détails à la demande avant d'envoyer la notification
                details = fetch_glenat_details(album["url"])
                album["price"] = details.get("price")
                album["summary"] = details.get("summary")
                print(f"  [SORTIE]  {album.get('title', ean)} — Prix: {album.get('price') or 'non renseigné'}")
                notify_glenat_release(album)
                notif_count += 1
            else:
                print(f"  [SORTIE-SILENT] {album.get('title', ean)}")
            state[key] = "released"

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    save_state(state)

    if first_run:
        print(f"[init] State initialisé avec {len(state)} entrée(s). Prêt pour le prochain run !")
    else:
        print(f"[done] {notif_count} notification(s) Telegram envoyée(s).")


if __name__ == "__main__":
    main()
