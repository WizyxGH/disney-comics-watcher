import os
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration Constants
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
#   - simple str   : code -> fr/<code> <num>
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

# Time zones and core URLs
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

# Telegram credentials — injected via GitHub Actions secrets or .env
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = (
    os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID", "")
)
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DisneyComicsWatcher/1.0)"}
AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "")
