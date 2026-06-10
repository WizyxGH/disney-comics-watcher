import base64
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

# Keywords for automatic discovery on Direct Éditeurs + MLP
KEYWORDS = ["picsou", "mickey", "mickey hs", "mickey parade", "fantomiald", "donald"]

# Codifs to explicitly ignore (misclassified on MLP)
SKIP_CODIFS = {
    "11560",  # ANIME CULT (incorrectly classified under Disney D23 sub-family)
}

# Magazines published as double issues (e.g. JdM 3856-3857).
# If DE/MLP only publishes the single issue N, we synthesize N-(N+1).
BI_ISSUE_CODIFS = {
    "14067",  # Journal de Mickey
}

# Overrides: displayed name and Inducks code (optional).
# Inducks format:
#   - simple str   : code → fr/<code> <num>
#   - (code, w)    : number zfill(w)
#   - (code, w, s) : number zfill(w) + suffix s
OVERRIDES = {
    # ── Picsou Magazine and spin-offs ────────────────────────────────────────
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
    # ── Super Picsou Géant and spin-offs ─────────────────────────────────────
    "14016": {"name": "Super Picsou Géant",                     "inducks": "SPG"},
    "12651": {"name": "SPG HS Dynastie de Picsou",              "inducks": ("SPGHS", 3, "H")},
    "15599": {"name": "SPG HS Dynastie de Picsou (REV)",        "inducks": ("SPGHS", 3, "H")},
    "12825": {"name": "SPG HS Super Donald Géant",              "inducks": ("SPGHS", 3, "D")},
    "18262": {"name": "SPG HS Super Donald Géant (REV)",        "inducks": ("SPGHS", 3, "D")},
    "18268": {"name": "SPG HS Donald Double Duck (REV)",        "inducks": ("DON", 4)},
    "13459": {"name": "SPG HS Jeux",                            "inducks": ("SPGHS", 3, "J")},
    "11065": {"name": "Les grands méchants",                    "inducks": ("SPGHS", 3, "M")},
    # ── Trésors de Picsou ────────────────────────────────────────────────────
    "14068": {"name": "Les Trésors de Picsou",                  "inducks": "TP"},
    # ── Journal de Mickey and spin-offs ──────────────────────────────────────
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
    # ── Miscellaneous Disney ─────────────────────────────────────────────────
    "14268": {"name": "Les Incontournables de Disney",          "inducks": ("LI", 4)},
    "19064": {"name": "Les Incontournables (REV)",              "inducks": ("LI", 4)},
}


# Paris time zone for date consistency
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

# Load local .env file if it exists
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Telegram credentials — injected via GitHub Actions secrets
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = (
    os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID", "")
)
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DisneyComicsWatcher/1.0)"}

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "")

def format_price_fr(prix_str: str | None) -> str | None:
    """Standardizes the price format in French (e.g., '4,9 €' -> '4,90 €')."""
    if not prix_str:
        return None
    prix_str = prix_str.strip()
    # Remove the euro symbol and superfluous spaces to clean the string
    clean_str = re.sub(r'(?i)\s*e?ur\s*$', '', prix_str)
    clean_str = re.sub(r'\s*€\s*$', '', clean_str).strip()
    
    # Search for a number with decimals (comma or dot)
    m = re.search(r'(\d+)[,.](\d+)', clean_str)
    if m:
        euros = m.group(1)
        dec = m.group(2)
        if len(dec) == 1:
            dec += "0"
        elif len(dec) > 2:
            dec = dec[:2]
        return f"{euros},{dec} €"
    
    # If it is an integer
    if re.match(r'^\d+$', clean_str):
        return f"{clean_str} €"
        
    return prix_str


CHARACTER_CODE_MAP = {
    "picsou": "US",
    "oncle picsou": "US",
    "donald": "DD",
    "donald duck": "DD",
    "mickey": "MM",
    "mickey mouse": "MM",
    "dingo": "GO",
    "pluto": "PL",
    "riri": "HDL",
    "fifi": "HDL",
    "loulou": "HDL",
    "riri/fifi/loulou": "HDL",
    "riri, fifi et loulou": "HDL",
    "riri, fifi, loulou": "HDL",
    "géo trouvetou": "GP",
    "geo trouvetou": "GP",
    "gontran": "GL",
    "gontran bonheur": "GL",
    "daisy": "DA",
    "daisy duck": "DA",
    "minnie": "MI",
    "minnie mouse": "MI",
    "rapetou": "BB",
    "les rapetou": "BB",
    "miss tick": "MDS",
    "misstick": "MDS",
    "gripsou": "FLG",
    "archibald gripsou": "FLG",
    "flairsou": "RK",
    "fantomiald": "PK",
    "popop": "FE",
    "gaston": "FE",
    "fantôme noir": "PB",
    "fantome noir": "PB",
    "le fantôme noir": "PB",
    "le fantome noir": "PB",
    "gus": "GG",
    "grand-mère donald": "GD",
    "grand-mere donald": "GD",
    "clarabelle": "CC",
    "horace": "HH",
    "jojo et michou": "MF",
    "commissaire finot": "CO",
    "inspecteur duflair": "DC",
    "gamma": "EB",
    "fergus mcpicsou": "FMc",
    "downy mcpicsou": "DOD",
    "hortense mcpicsou": "HM",
    "matilda mcpicsou": "MMc",
    "goldie": "Go",
    "pat hibulaire": "PE",
}


VALID_CHARACTER_CODES = set(CHARACTER_CODE_MAP.values())


def analyze_cover_with_gemini(cover_url: str, api_key: str) -> dict:
    """Uses the free Gemini API (gemini-3.1-flash-lite) to extract the main cover story/title
    and detect the Disney characters present on the cover image in a single call.
    
    Returns a dictionary:
      {
        "title": str | None,
        "characters": list[dict]  # list of {"name_fr": str, "code": str | None}
      }
    """
    fallback_res = {"title": None, "characters": []}
    if not cover_url or not api_key:
        return fallback_res
    try:
        # Download the image
        resp = requests.get(cover_url, timeout=15)
        resp.raise_for_status()
        img_bytes = resp.content
        
        # Determine MIME type
        mime_type = resp.headers.get("Content-Type", "image/jpeg")
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"
            
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        
        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an assistant specialized in Disney comics and the Inducks database.\n"
                                "Analyze the cover image of a French Disney magazine or comic book.\n"
                                "Perform two tasks:\n"
                                "1. Identify and extract the main headline, featured story title, or major theme of this specific issue "
                                "(usually written in large, prominent, stylized letters at the bottom or middle of the cover, "
                                "like 'Escape game dans le coffre de Picsou' or 'Destination aventure !'). "
                                "Do NOT extract secondary sidebar text, barcode numbers, prices, or the main magazine name (e.g. 'Picsou Magazine', 'Le Journal de Mickey'). "
                                "Return it under the 'title' key (sentence casing, without quotes, in French). If no major feature title is visible, set it to null.\n\n"
                                "2. Identify all main Disney characters visible on the cover. For each, return their French name "
                                "and their official standard Inducks character code if known. Use the following exact mappings for reference:\n"
                                "- Picsou (US)\n"
                                "- Donald Duck (DD)\n"
                                "- Mickey Mouse (MM)\n"
                                "- Dingo (GO)\n"
                                "- Pluto (PL)\n"
                                "- Riri, Fifi, Loulou (HDL)\n"
                                "- Géo Trouvetou (GP)\n"
                                "- Gontran (GL)\n"
                                "- Daisy Duck (DA)\n"
                                "- Minnie Mouse (MI)\n"
                                "- Les Rapetou (BB)\n"
                                "- Miss Tick (MDS)\n"
                                "- Gripsou (FLG)\n"
                                "- Flairsou (RK)\n"
                                "- Fantomiald (PK)\n"
                                "- Popop (FE)\n"
                                "- Le Fantôme Noir (PB)\n"
                                "- Gus (GG)\n"
                                "- Grand-Mère Donald (GD)\n"
                                "- Clarabelle (CC)\n"
                                "- Horace (HH)\n"
                                "- Jojo et Michou (MF)\n"
                                "- Commissaire Finot (CO)\n"
                                "- Inspecteur Duflair (DC)\n"
                                "- Gamma (EB)\n"
                                "- Fergus McPicsou (FMc)\n"
                                "- Downy McPicsou (DOD)\n"
                                "- Hortense McPicsou (HM)\n"
                                "- Matilda McPicsou (MMc)\n"
                                "- Goldie (Go)\n"
                                "- Pat Hibulaire (PE)\n\n"
                                "If a character is not in this list, return their French name and set 'code' to null. "
                                "Do NOT invent character codes. Return this list under the 'characters' key, where each item is an object with 'name_fr' and 'code'.\n\n"
                                "Format the output as a JSON object with keys 'title' and 'characters'. Example:\n"
                                '{\n  "title": "Escape game chez Picsou",\n  "characters": [\n    {"name_fr": "Picsou", "code": "US"},\n    {"name_fr": "Donald Duck", "code": "DD"}\n  ]\n}'
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": img_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "maxOutputTokens": 300
            }
        }
        
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        result = r.json()
        
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        data = json.loads(text)
        
        title = data.get("title")
        if title:
            title = re.sub(r'^["\'\-\*#`\s]+', '', title)
            title = re.sub(r'["\'\-\*#`\s]+$', '', title)
            if not title.strip():
                title = None
            else:
                title = title.strip()
        
        characters = data.get("characters", [])
        cleaned_chars = []
        if isinstance(characters, list):
            for char in characters:
                if isinstance(char, dict) and "name_fr" in char:
                    name_fr = char["name_fr"].strip()
                    norm_name = name_fr.lower()
                    
                    # 1. First search in our mapping
                    code = CHARACTER_CODE_MAP.get(norm_name)
                    if not code:
                        for k, v in CHARACTER_CODE_MAP.items():
                            if k == norm_name or norm_name.startswith(k) or k.startswith(norm_name):
                                code = v
                                break
                                
                    # 2. Strict whitelist fallback: only allow the code if it's explicitly in the map's values
                    if not code and char.get("code"):
                        provided_code = char["code"].strip()
                        if provided_code in VALID_CHARACTER_CODES:
                            code = provided_code
                    
                    cleaned_chars.append({
                        "name_fr": name_fr,
                        "code": code
                    })
                    
        return {"title": title, "characters": cleaned_chars}
        
    except Exception as e:
        print(f"  [warn] Failed to analyze cover with Gemini: {e}")
        return fallback_res


# ─────────────────────────────────────────────────────────────────────────────
#  Shared HTTP Session
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
#  State Management
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
#  Direct Éditeurs Parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_date_fr(s):
    """DD/MM/YYYY → date object, or None if invalid."""
    if not s:
        return None
    try:
        d, m, y = str(s).strip().split("/")
        return datetime(int(y), int(m), int(d)).date()
    except (ValueError, AttributeError):
        return None


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
            return (d or datetime.min.date(), has_dash)
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
#  MLP — complementary discovery and off-sale date
# ─────────────────────────────────────────────────────────────────────────────

def discover_mlp_families(known_codifs: set, state: dict | None = None):
    """Finds magazines missing from DE via MLP sub-families (e.g. D23, D15) and retrieves their details."""
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
            print(f"  [warn] MLP family={family}: {e}")
            continue

        soup = BeautifulSoup(r.text, 'html.parser')

        # Iterate over product blocks of the 'catalogue' class
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
            title_lower = title.lower()
            if codif not in OVERRIDES and not any(kw in title_lower for kw in KEYWORDS):
                continue

            numero_list = num_span.get_text(strip=True) if num_span else ""
            date_list   = date_span.get_text(strip=True) if date_span else ""
            href        = link['href'] if link else ""

            # Optimization: If the codif is already known in state and the issue
            # number (digits only) matches, we avoid the detail request.
            state_val = state.get(codif)
            if state_val:
                digits_list = "".join(filter(str.isdigit, numero_list))
                digits_state = "".join(filter(str.isdigit, state_val))
                if digits_list and digits_state and digits_list == digits_state:
                    continue

            # Fetch the product details to retrieve price, large cover image, and off-sale date
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
                        if numero and numero.upper().endswith("H"):
                            numero = numero[:-1].strip()

                        # Off-sale date
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


# ─────────────────────────────────────────────────────────────────────────────
#  Glénat — Disney Comic Books
# ─────────────────────────────────────────────────────────────────────────────

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


def get_latest_inducks_issue_number(publication_code: str) -> int:
    """Streams the official Inducks issue database to find the highest numeric issue number for a publication."""
    url = "https://inducks.org/inducks/isv/inducks_issue.isv"
    max_num = 0
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        for line_bytes in r.iter_lines():
            if not line_bytes:
                continue
            line = line_bytes.decode('utf-8', errors='ignore')
            parts = line.split('^')
            if len(parts) >= 4:
                pubcode = parts[2]
                if pubcode == publication_code:
                    issue_num_str = parts[3].strip()
                    if issue_num_str.isdigit():
                        num = int(issue_num_str)
                        if num > max_num:
                            max_num = num
    except Exception as e:
        print(f"  [warn] Failed to fetch latest Inducks issue number for {publication_code}: {e}")
    return max_num


def resolve_dbg_tome_number(album: dict, state: dict | None = None):
    """Resolves and extrapolates the next issue number for Disney By Glénat (DBG) albums."""
    if album.get("numero_de_tome") is None:
        coll = album.get("collection_label")
        ser = album.get("serie_label")
        
        def clean_str(s):
            if not s:
                return ""
            s = s.lower()
            import unicodedata
            s = unicodedata.normalize('NFKD', s)
            return "".join(c for c in s if not unicodedata.combining(c))
        
        coll_clean = clean_str(coll)
        ser_clean = clean_str(ser)
        
        if "creations originales" in coll_clean or "creations originales" in ser_clean:
            local_state = state if state is not None else load_state()
            last_dbg = local_state.get("dbg_last_num")
            if not last_dbg:
                last_dbg = get_latest_inducks_issue_number("fr/DBG")
                if last_dbg == 0:
                    last_dbg = 20
            next_dbg = last_dbg + 1
            album["numero_de_tome"] = next_dbg
            local_state["dbg_last_num"] = next_dbg
            
            # Save local state if not passed from main
            if state is None:
                save_state(local_state)
            
            # Append tome number to the title if not already present
            tome_str = f"Tome {str(next_dbg).zfill(2)}"
            title = album.get("title", "")
            if tome_str.lower() not in title.lower() and f"tome {next_dbg}" not in title.lower():
                album["title"] = f"{title} - {tome_str}"
            
            print(f"  [DBG] Extrapolated tome number: {next_dbg}")


def truncate_summary(text: str, max_len: int = 400) -> str:
    """Cleanly truncates the summary to avoid cutting a word in half."""
    if not text or len(text) <= max_len:
        return text or ""
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.strip() + "…"


# ─────────────────────────────────────────────────────────────────────────────
#  Telegram Notifications
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(photo_url: str | None, caption: str, buttons: list | None = None, retries: int = 5):
    """Sends a Telegram message with a photo (sendPhoto) or text only (sendMessage).
    Automatically handles rate limits (429) and inaccessible photos.
    buttons: list of button rows, e.g. [[{"text": "Voir", "url": "..."}]]
    Returns the Telegram message_id (int) if successful, None otherwise."""
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
                # Text fallback if image is inaccessible
                if resp.status_code == 400:
                     print(f"  [debug] Telegram 400 error: {resp.text}")
                     desc = resp.json().get("description", "").lower()
                     if any(k in desc for k in ("photo", "wrong url", "failed to get", "url")):
                        print(f"  [warn] Photo inaccessible → fallback to text")
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
                print(f"  [429] Telegram rate limit — waiting {retry_after}s…")
                time.sleep(retry_after)
                delay = max(delay * 2, retry_after + 1)
                continue

            resp.raise_for_status()
            return resp.json().get("result", {}).get("message_id")

        except requests.RequestException as e:
            print(f"  [error] Telegram (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)

    print("  [FAILURE] Telegram notification not sent.")
    return None


def build_inducks_url(inducks, numero: str) -> str | None:
    """Builds the Inducks URL for a given issue number."""
    path = build_inducks_path(inducks, numero)
    if not path:
        return None
    return f"https://inducks.org/issue.php?c={quote_plus(path)}"


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Converts an ISBN-13 (starting with 978) to an ISBN-10 (Amazon ASIN)."""
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
    """Attempts to retrieve a higher quality cover image from disneymagazines.fr."""
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
            # 1st choice: twic.pics URL (native CDN, higher quality) — remove query parameters
            m = re.search(r'"(https://fleuruspresse-disney\.twic\.pics/media/[^"]+\.jpg)[^"]*"', r.text)
            if m:
                return m.group(1)
            # 2nd choice: Google Merchant cache URL on disneymagazines.fr
            m = re.search(r'"(https://www\.disneymagazines\.fr/media/cache/[^"]+\.jpg)"', r.text)
            if m:
                return m.group(1)
            # 3rd choice: relative src
            m = re.search(r'src="(/media/image/[^"]+\.jpg)"', r.text)
            if m:
                return f"https://www.disneymagazines.fr{m.group(1)}"
    except Exception as e:
        print(f"  [warn] Unable to retrieve cover from DisneyMagazines for {slug}: {e}")
    return None


def notify_magazine(info: dict, releve_date: str | None = None):
    """Sends the Telegram notification for a new magazine issue."""
    codif = info["codif"]
    ov    = OVERRIDES.get(codif, {})
    name  = ov.get("name") or info.get("site_name") or info.get("slug") or codif
    num   = info.get("numero", "?")
    prix  = format_price_fr(info.get("prix"))
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
    btn_text = "Voir sur MLP" if "mlp.fr" in url.lower() else "Voir sur Direct-éditeurs"
    buttons = [
        [{"text": btn_text, "url": url}],
        [{"text": "Sommaire sur Inducks", "url": inducks_url}],
    ]

    # Try to retrieve a better quality cover from DisneyMagazines first
    cover_url = None
    if info.get("slug"):
        cover_url = fetch_disneymagazines_cover(info.get("slug"))
        if cover_url:
            print(f"  [info] High quality cover found on DisneyMagazines: {cover_url}")
    if not cover_url:
        cover_url = info.get("cover_url")

    send_telegram(cover_url, "\n".join(lines), buttons=buttons)
    time.sleep(1)  # throttle

    # Try to analyze cover with Gemini if API key is present
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for {name} N° {num}...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        cover_title = analysis.get("title")
        characters = analysis.get("characters", [])
        if cover_title:
            print(f"  [Gemini] Extracted title: '{cover_title}'")
            info["cover_title"] = cover_title
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            info["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(info, publication_type="magazine", overrides=OVERRIDES)


def build_glenat_inducks_url(title: str) -> str:
    """Builds the Inducks URL for a Glénat album (direct page if possible, otherwise search)."""
    title_lower = title.lower()
    tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
    tome_num = int(tome_match.group(1)) if tome_match else None

    # 1. La Grande Histoire/Épopée de Picsou (Don Rosa) -> GHP code
    if "grande histoire de picsou" in title_lower or "grande epopee de picsou" in title_lower or "grande épopée de picsou" in title_lower:
        if tome_num is not None:
            code = f"fr/GHP{str(tome_num).rjust(4)}"
            return f"https://inducks.org/issue.php?c={quote_plus(code)}"
        return "https://inducks.org/publication.php?c=fr/GHP"

    # 2. Les Âges d'or (Picsou, Donald, Mickey, etc.) -> AOD code
    if "ages d'or" in title_lower or "âges d'or" in title_lower or "age d'or" in title_lower or "âge d'or" in title_lower:
        if tome_num is not None:
            code = f"fr/AOD{str(tome_num).rjust(4)}"
            return f"https://inducks.org/issue.php?c={quote_plus(code)}"
        return "https://inducks.org/publication.php?c=fr/AOD"

    return f"https://inducks.org/search.php?search={quote(title)}"


def notify_glenat_announce(album: dict, state: dict | None = None):
    """Glénat announcement notification (upcoming album)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption: metadata + truncated summary
    meta_lines = [f"<b>Annonce — {title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Parution prévue : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        meta_lines.append(f"💶 {html_lib.escape(prix)}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Inline keyboard buttons
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Try to analyze cover with Gemini if API key is present
    cover_url = album.get("cover_url")
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for Glénat album '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            album["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


def notify_glenat_release(album: dict, state: dict | None = None):
    """Glénat release notification (album available in bookstores)."""
    resolve_dbg_tome_number(album, state)
    title = html_lib.escape(album.get("title", "Album Disney"))
    raw_title = album.get("title", "Album Disney")

    # 1. Caption: metadata + truncated summary
    meta_lines = [f"<b>{title}</b>", ""]
    if album.get("date"):
        meta_lines.append(f"🗓 Paru le : {album['date']}")
    prix = format_price_fr(album.get("price"))
    if prix:
        meta_lines.append(f"💶 {html_lib.escape(prix)}")

    base_caption = "\n".join(meta_lines)
    summary = album.get("summary", "")
    if summary:
        available = 1024 - len(base_caption) - 40
        truncated = truncate_summary(summary, max_len=max(50, available))
        caption = base_caption + f"\n\n<i>{html_lib.escape(truncated)}</i>"
    else:
        caption = base_caption

    # 2. Inline keyboard buttons
    row1 = [{"text": "Voir sur Glénat", "url": album["url"]}]
    if AMAZON_AFFILIATE_TAG:
        asin = isbn13_to_isbn10(album.get("ean", ""))
        if asin:
            row1.append({"text": "Acheter sur Amazon", "url": f"https://www.amazon.fr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
    row2 = [{"text": "Sommaire sur Inducks", "url": build_glenat_inducks_url(raw_title)}]
    buttons = [row1, row2]

    send_telegram(album.get("cover_url"), caption, buttons=buttons)
    time.sleep(1)

    # Try to analyze cover with Gemini if API key is present
    cover_url = album.get("cover_url")
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and cover_url:
        print(f"  [Gemini] Analyzing cover for Glénat album '{raw_title}'...")
        analysis = analyze_cover_with_gemini(cover_url, api_key)
        characters = analysis.get("characters", [])
        if characters:
            char_list = ", ".join(f"{c['name_fr']} ({c['code']})" if c.get('code') else c['name_fr'] for c in characters)
            print(f"  [Gemini] Detected characters: {char_list}")
            album["characters"] = characters

    # Generation of the Inducks pre-index skeleton
    generate_dbi_skeleton(album, publication_type="glenat", overrides=OVERRIDES)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── State ─────────────────────────────────────────────────────────────────
    state = load_state()
    first_run = not state
    if first_run:
        print("[init] First run — silent initialization (no notifications).")

    notif_count = 0
    today = datetime.now(PARIS_TZ).date()

    # ── Direct Éditeurs ───────────────────────────────────────────────────────
    print("[DE] Discovering magazines…")
    try:
        magazines = discover_de()
    except Exception as e:
        print(f"  [error] discover_de: {e}")
        magazines = {}
    print(f"  → {len(magazines)} active magazine(s).")

    # ── MLP complementary ────────────────────────────────────────────────────
    print("[MLP] Complementary discovery…")
    try:
        mlp_extra = discover_mlp_families(known_codifs=set(magazines), state=state)
        added = {c: v for c, v in mlp_extra.items() if c not in magazines}
        magazines.update(added)
        print(f"  → +{len(added)} unique MLP codif(s).")
    except Exception as e:
        print(f"  [error] discover_mlp: {e}")

    # ── Magazine processing ───────────────────────────────────────────────────
    for codif, info in magazines.items():
        if codif in SKIP_CODIFS:
            continue
        numero = info.get("numero")
        if not numero:
            continue

        last = state.get(codif)
        if last and last.upper().endswith("H"):
            last = last[:-1].strip()
        if numero == last:
            continue  # no change

        ov   = OVERRIDES.get(codif, {})
        name = ov.get("name") or info.get("site_name") or codif
        print(f"  [NEW] {name} — N°{numero}  (previous: {last or '—'})")

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
    print("[Glénat] Discovering Disney comic books…")
    try:
        glenat_albums = discover_glenat()
        print(f"  → {len(glenat_albums)} album(s) found.")
    except Exception as e:
        print(f"  [error] discover_glenat: {e}")
        glenat_albums = []

    for album in glenat_albums:
        ean = album.get("ean")
        if not ean:
            continue
        key     = f"{GLENAT_KEY_PREFIX}{ean}"
        current = state.get(key)
        pub_date = album.get("pub_date")

        if current is None:
            # New album detected
            if pub_date and pub_date <= today:
                # Already released in the past -> we record it directly as released without notifying
                print(f"  [RELEASE-SILENT-INIT] {album.get('title', ean)}")
                state[key] = "released"
            else:
                # Upcoming album -> announcement notification
                if not first_run:
                    # Retrieve details on-demand before sending the notification
                    details = fetch_glenat_details(album["url"])
                    album.update(details)
                    print(f"  [ANNOUNCEMENT] {album.get('title', ean)} — Price: {album.get('price') or 'not specified'}")
                    notify_glenat_announce(album, state=state)
                    notif_count += 1
                else:
                    print(f"  [ANNOUNCEMENT-SILENT] {album.get('title', ean)}")
                state[key] = "announced"

        elif current == "announced" and pub_date and pub_date <= today:
            # Announced album whose publication date is reached → release in bookstores
            if not first_run:
                # Retrieve details on-demand before sending the notification
                details = fetch_glenat_details(album["url"])
                album.update(details)
                print(f"  [RELEASE]  {album.get('title', ean)} — Price: {album.get('price') or 'not specified'}")
                notify_glenat_release(album, state=state)
                notif_count += 1
            else:
                print(f"  [RELEASE-SILENT] {album.get('title', ean)}")
            state[key] = "released"

    # ── Saving State ──────────────────────────────────────────────────────────
    save_state(state)

    if first_run:
        print(f"[init] State initialized with {len(state)} entry(ies). Ready for the next run!")
    else:
        print(f"[done] {notif_count} Telegram notification(s) sent.")


if __name__ == "__main__":
    main()
