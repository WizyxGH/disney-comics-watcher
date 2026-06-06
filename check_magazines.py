import html as html_lib
import json
import os
import re
import time
import requests
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

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

# Overrides : nom affiché, emoji, et code Inducks (optionnel).
# Format inducks :
#   - str simple   : code → fr/<code>  <num>
#   - (code, w)    : numéro zfill(w)
#   - (code, w, s) : numéro zfill(w) + suffixe s
OVERRIDES = {
    # ── Picsou Magazine et déclinaisons ──────────────────────────────────────
    "13159": {"name": "Picsou Magazine",                        "emoji": "💰", "inducks": "PM"},
    "15681": {"name": "Picsou Magazine HS Collection Deluxe",   "emoji": "📘", "inducks": ("CD", 5)},
    "15930": {"name": "Picsou Mag HS Collection Deluxe vol.2",  "emoji": "📘", "inducks": ("CD", 5)},
    "18288": {"name": "Picsou HS Castors Juniors",              "emoji": "🦫", "inducks": ("PMHS", 3, "S")},
    "19603": {"name": "Picsou HS Souvenirs du Klondike",        "emoji": "⛏️"},
    "17575": {"name": "Picsou Anniversaire en or",              "emoji": "🎂"},
    "18658": {"name": "Picsou Soir",                            "emoji": "🌆"},
    "18360": {"name": "Nouvelle Jeunesse de Picsou",            "emoji": "🌱"},
    "19607": {"name": "Le Destin de Picsou",                    "emoji": "⏳"},
    "19052": {"name": "Pochette Picsou Magazine",               "emoji": "📦"},
    # ── Super Picsou Géant et déclinaisons ───────────────────────────────────
    "14016": {"name": "Super Picsou Géant",                     "emoji": "🦆", "inducks": ("SPG", 4)},
    "12651": {"name": "SPG HS Dynastie de Picsou",              "emoji": "📜", "inducks": ("SPGHS", 3, "H")},
    "15599": {"name": "SPG HS Dynastie de Picsou (REV)",        "emoji": "📜", "inducks": ("SPGHS", 3, "H")},
    "12825": {"name": "SPG HS Super Donald Géant",              "emoji": "🦆", "inducks": ("SPGHS", 3, "D")},
    "18262": {"name": "SPG HS Super Donald Géant (REV)",        "emoji": "🦆", "inducks": ("SPGHS", 3, "D")},
    "18268": {"name": "SPG HS Donald Double Duck (REV)",        "emoji": "🦹", "inducks": ("DON", 4)},
    "13459": {"name": "SPG HS Jeux",                            "emoji": "🎲", "inducks": ("SPGHS", 3, "J")},
    # ── Trésors de Picsou ────────────────────────────────────────────────────
    "14068": {"name": "Les Trésors de Picsou",                  "emoji": "💎", "inducks": "TP"},
    # ── Journal de Mickey et déclinaisons ────────────────────────────────────
    "14067": {"name": "Journal de Mickey",                      "emoji": "🐭", "inducks": ("JM", 8)},
    "14108": {"name": "Journal de Mickey HS",                   "emoji": "⭐", "inducks": ("JMHSN", 3)},
    "13588": {"name": "JdM HS Spécial Aventures (REV)",         "emoji": "🗺️"},
    "16096": {"name": "Journal de Mickey + Produit",            "emoji": "🎁"},
    "15935": {"name": "Le Meilleur du Journal de Mickey",       "emoji": "🏆"},
    "15970": {"name": "Le Meilleur du JdM HS",                  "emoji": "🏆"},
    "18914": {"name": "Le Meilleur du JdM HS Spécial Enquêtes", "emoji": "🔍"},
    # ── Mickey Junior ────────────────────────────────────────────────────────
    "15528": {"name": "Mickey Junior",                          "emoji": "🧒", "inducks": "MJ"},
    "14513": {"name": "Mickey Junior HS Jeux",                  "emoji": "🎲"},
    "18875": {"name": "Mickey Junior HS Baby",                  "emoji": "🍼"},
    # ── Mickey Parade ────────────────────────────────────────────────────────
    "11068": {"name": "Pochette Mickey Parade",                 "emoji": "📦"},
    # ── Fantomiald ───────────────────────────────────────────────────────────
    "15190": {"name": "Les Chroniques de Fantomiald",           "emoji": "🦸", "inducks": "CF"},
    # ── Disney divers ────────────────────────────────────────────────────────
    "14268": {"name": "Les Incontournables de Disney",          "emoji": "🏛️", "inducks": ("LI", 4)},
    "19064": {"name": "Les Incontournables (REV)",              "emoji": "🏛️", "inducks": ("LI", 4)},
}
DEFAULT_EMOJI = "🦆"

# Fuseau horaire de Paris pour la cohérence des dates
PARIS_TZ = ZoneInfo("Europe/Paris")

SEARCH_URL     = "https://direct-editeurs.fr/nos-magazines"
SITE_BASE      = "https://direct-editeurs.fr"
MLP_URL        = "https://catalogueproduits.mlp.fr/Default.aspx"
MLP_FAMILY_URL = "https://catalogueproduits.mlp.fr/liste.aspx?ssFam={}"
MLP_FAMILIES   = ["D23"]

GLENAT_COLLECTION_URL = "https://www.glenat.com/livres-glenat-disney/"
GLENAT_BASE           = "https://www.glenat.com"
GLENAT_KEY_PREFIX     = "glenat:"

STATE_FILE = "state.json"

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

def discover_mlp_families(known_codifs: set):
    """Rattrape les magazines absents de DE via les sous-familles MLP (ex: D23)."""
    s = get_session()
    result: dict[str, dict] = {}

    for family in MLP_FAMILIES:
        try:
            r = s.get(MLP_FAMILY_URL.format(family), timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  [warn] MLP famille={family}: {e}")
            continue

        text = r.text

        # Extraire les codifs depuis les contextes typiques (liens, attributs, libellés)
        found = set()
        for pat in [
            r'[?&](?:codif|ref|id)=(\d{5})\b',
            r'/produits?/(\d{5})\b',
            r'[Cc]odif\s*:?\s*(\d{5})\b',
            r'data-(?:codif|ref|id)="(\d{5})"',
        ]:
            found.update(re.findall(pat, text))

        for codif in found:
            if codif in known_codifs or codif in result or codif in SKIP_CODIFS:
                continue
            result[codif] = {
                "codif":              codif,
                "numero":             None,
                "date_mise_en_vente": None,
                "prix":               None,
                "cover_url":          None,
                "url":                MLP_FAMILY_URL.format(family),
                "slug":               codif,
                "site_name":          "",
                "expired_on":         None,
            }

    return result


def get_mlp_releve(codif: str):
    """Retourne la date de relève prévisionnelle (« Jusqu'au ») depuis MLP."""
    s = get_session()
    patterns = [
        r"[Jj]usqu['']au\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
        r"[Rr]el[eè]ve?\s*(?:le|pr[eé]vue?)?\s*:?\s*(?:<[^>]+>)?\s*(\d{2}/\d{2}/\d{4})",
    ]
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
            for pat in patterns:
                m = re.search(pat, r.text)
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


def fetch_glenat_price(url: str) -> str | None:
    """Récupère à la demande le prix d'un album depuis sa fiche produit Glénat."""
    s = get_session()
    try:
        r = s.get(url, timeout=10)
        r.raise_for_status()
        r.encoding = "utf-8"
        text = r.text

        # 1. Chercher dans les attributs JSON-LD "price":"..."
        m = re.search(r'"price"\s*:\s*"([0-9.]+)"', text)
        if m:
            return m.group(1).replace(".", ",") + " €"

        # 2. Chercher dans les balises meta itemprop="price"
        m = re.search(r'itemprop="price"\s*content="([^"]+)"', text)
        if m:
            return m.group(1).replace(".", ",") + " €"

        # 3. Chercher dans le HTML classique (ex: 19,00 €)
        m = re.search(r'([0-9]+[,\.][0-9]{2})\s*(?:€|\u20ac)', text)
        if m:
            return m.group(1).replace(".", ",") + " €"

    except Exception as e:
        print(f"  [warn] Impossible de récupérer le prix pour {url}: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Notifications Telegram
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(photo_url: str | None, caption: str, retries: int = 5) -> bool:
    """Envoie un message Telegram avec photo (sendPhoto) ou texte seul (sendMessage).
    Gère automatiquement les rate limits (429) et les photos inaccessibles."""
    delay = 2
    for attempt in range(retries):
        try:
            if photo_url:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendPhoto",
                    json={
                        "chat_id":    TELEGRAM_CHAT_ID,
                        "photo":      photo_url,
                        "caption":    caption[:1024],  # limite Telegram
                        "parse_mode": "HTML",
                    },
                    timeout=15,
                )
                # Fallback texte si l'image est inaccessible
                if resp.status_code == 400:
                    desc = resp.json().get("description", "").lower()
                    if any(k in desc for k in ("photo", "wrong url", "failed to get", "url")):
                        print(f"  [warn] Photo inaccessible → fallback texte")
                        photo_url = None
                        continue
            else:
                resp = requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id":                  TELEGRAM_CHAT_ID,
                        "text":                     caption[:4096],
                        "parse_mode":               "HTML",
                        "disable_web_page_preview": False,
                    },
                    timeout=15,
                )

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", delay)
                print(f"  [429] Rate limit Telegram — attente {retry_after}s…")
                time.sleep(retry_after)
                delay = max(delay * 2, retry_after + 1)
                continue

            resp.raise_for_status()
            return True

        except requests.RequestException as e:
            print(f"  [erreur] Telegram (tentative {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)

    print("  [ECHEC] Notification Telegram non envoyée.")
    return False


def build_inducks_url(inducks, numero: str) -> str | None:
    """Construit l'URL Inducks pour un numéro de parution donné."""
    if not inducks or not numero:
        return None
    try:
        # Extraire la partie numérique (ex: "3858-3859" -> "3858", "7H" -> "7")
        first_part = numero.split("-")[0].strip()
        digits = "".join(filter(str.isdigit, first_part))
        if not digits:
            return None
        n = int(digits)
        
        if isinstance(inducks, str):
            path = f"fr/{inducks}  {n}"
        elif len(inducks) == 2:
            code, width = inducks
            path = f"fr/{code}  {str(n).zfill(width)}"
        elif len(inducks) == 3:
            code, width, suffix = inducks
            path = f"fr/{code}  {str(n).zfill(width)}{suffix}"
        else:
            return None
        return f"https://inducks.org/issue.php?c={quote(path)}"
    except (ValueError, TypeError, AttributeError):
        return None


def build_inducks_pub_url(inducks) -> str | None:
    """Construit l'URL Inducks pour la série de publication (le magazine)."""
    if not inducks:
        return None
    try:
        if isinstance(inducks, str):
            code = inducks
        elif isinstance(inducks, (list, tuple)) and len(inducks) > 0:
            code = inducks[0]
        else:
            return None
        return f"https://inducks.org/publication.php?c=fr/{quote(code)}"
    except (ValueError, TypeError, AttributeError):
        return None


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


def notify_magazine(info: dict, releve_date: str | None = None):
    """Envoie la notification Telegram pour un nouveau numéro de magazine."""
    codif = info["codif"]
    ov    = OVERRIDES.get(codif, {})
    emoji = ov.get("emoji", DEFAULT_EMOJI)
    name  = ov.get("name") or info.get("site_name") or info.get("slug") or codif
    num   = info.get("numero", "?")
    prix  = info.get("prix")
    date  = info.get("date_mise_en_vente")
    url   = info.get("url", SITE_BASE)

    lines = [f"{emoji} <b>{html_lib.escape(name)}</b>"]

    num_line = f"📌 N° {num}"
    if prix:
        num_line += f" • {html_lib.escape(prix)}"
    lines.append(num_line)

    if date:
        lines.append(f"📅 Paru le : {date}")
    if releve_date:
        lines.append(f"🔚 En kiosque jusqu'au : {releve_date}")

    lines.append(f'🔗 <a href="{url}">Voir sur Direct Éditeurs</a>')

    inducks_url = build_inducks_url(ov.get("inducks"), num)
    if inducks_url:
        lines.append(f'📖 <a href="{inducks_url}">Sommaire Inducks</a>')

    inducks_pub_url = build_inducks_pub_url(ov.get("inducks"))
    if inducks_pub_url:
        lines.append(f'🗂 <a href="{inducks_pub_url}">Fiche du magazine (Inducks)</a>')

    send_telegram(info.get("cover_url"), "\n".join(lines))
    time.sleep(1)  # throttle


def notify_glenat_announce(album: dict):
    """Notification d'annonce Glénat (album à paraître)."""
    title = html_lib.escape(album.get("title", "Album Disney"))
    lines = [f"📢 <b>Annonce — {title}</b>"]
    if album.get("date"):
        lines.append(f"🗓 Parution prévue : {album['date']}")
    if album.get("price"):
        lines.append(f"💶 {html_lib.escape(album['price'])}")
    lines.append(f'🔗 <a href="{album["url"]}">Voir sur Glénat</a>')
    
    # Lien d'affiliation Amazon si configuré et EAN valide
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            amazon_url = f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"
            lines.append(f'🛒 <a href="{amazon_url}">Acheter sur Amazon</a>')

    send_telegram(album.get("cover_url"), "\n".join(lines))
    time.sleep(1)


def notify_glenat_release(album: dict):
    """Notification de sortie Glénat (album disponible en librairie)."""
    title = html_lib.escape(album.get("title", "Album Disney"))
    lines = [f"📚 <b>Disponible — {title}</b>"]
    if album.get("date"):
        lines.append(f"🗓 Paru le : {album['date']}")
    if album.get("price"):
        lines.append(f"💶 {html_lib.escape(album['price'])}")
    lines.append(f'🔗 <a href="{album["url"]}">Voir sur Glénat</a>')
    
    # Lien d'affiliation Amazon si configuré et EAN valide
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            amazon_url = f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"
            lines.append(f'🛒 <a href="{amazon_url}">Acheter sur Amazon</a>')

    send_telegram(album.get("cover_url"), "\n".join(lines))
    time.sleep(1)


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
        mlp_extra = discover_mlp_families(known_codifs=set(magazines))
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
            releve = None
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
                    # Récupère le prix à la demande avant d'envoyer la notification
                    album["price"] = fetch_glenat_price(album["url"])
                    print(f"  [ANNONCE] {album.get('title', ean)} — Prix: {album.get('price') or 'non renseigné'}")
                    notify_glenat_announce(album)
                    notif_count += 1
                else:
                    print(f"  [ANNONCE-SILENT] {album.get('title', ean)}")
                state[key] = "announced"

        elif current == "announced" and pub_date and pub_date <= today:
            # Album annoncé dont la date de parution est atteinte → sortie en librairie
            if not first_run:
                # Récupère le prix à la demande avant d'envoyer la notification
                album["price"] = fetch_glenat_price(album["url"])
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
