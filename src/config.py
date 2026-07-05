import os
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Keywords for automatic discovery on Direct Editeurs + MLP
KEYWORDS = ["picsou", "mickey", "mickey hs", "mickey parade", "fantomiald", "donald"]

SKIP_CODIFS = {
    "11560",  # ANIME CULT
}

BI_ISSUE_CODIFS = {
    "14067",  # Journal de Mickey
}

OVERRIDES = {
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
    "14016": {"name": "Super Picsou Géant",                     "inducks": "SPG"},
    "12651": {"name": "SPG HS Dynastie de Picsou",              "inducks": ("SPGHS", 3, "H")},
    "15599": {"name": "SPG HS Dynastie de Picsou (REV)",        "inducks": ("SPGHS", 3, "H")},
    "12825": {"name": "SPG HS Super Donald Géant",              "inducks": ("SPGHS", 3, "D")},
    "18262": {"name": "SPG HS Super Donald Géant (REV)",        "inducks": ("SPGHS", 3, "D")},
    "18268": {"name": "SPG HS Donald Double Duck (REV)",        "inducks": ("DON", 4)},
    "13459": {"name": "SPG HS Jeux",                            "inducks": ("SPGHS", 3, "J")},
    "11065": {"name": "Les grands méchants",                    "inducks": ("SPGHS", 3, "M")},
    "14068": {"name": "Les Trésors de Picsou",                  "inducks": "TP"},
    "14067": {"name": "Journal de Mickey",                      "inducks": "JM"},
    "14108": {"name": "Journal de Mickey HS",                   "inducks": ("JMHSN", 3)},
    "13588": {"name": "JdM HS Spécial Aventures (REV)"},
    "16096": {"name": "Journal de Mickey + Produit"},
    "15935": {"name": "Le Meilleur du Journal de Mickey",       "inducks": "JMC"},
    "15970": {"name": "Le Meilleur du JdM HS"},
    "18914": {"name": "Le Meilleur du JdM HS Spécial Enquêtes"},
    "11068": {"name": "Pochette Mickey Parade"},
    "15190": {"name": "Les Chroniques de Fantomiald",           "inducks": ("CF", 5)},
    "14268": {"name": "Les Incontournables de Disney",          "inducks": ("LI", 4)},
    "19064": {"name": "Les Incontournables (REV)",              "inducks": ("LI", 4)},
}

PARIS_TZ = ZoneInfo("Europe/Paris")

SEARCH_URL     = "https://direct-editeurs.fr/nos-magazines"
SITE_BASE      = "https://direct-editeurs.fr"
MLP_URL        = "https://catalogueproduits.mlp.fr/Default.aspx"
MLP_FAMILY_URL = "https://catalogueproduits.mlp.fr/liste.aspx?ssFam={}"
MLP_FAMILIES   = ["D23", "D15"]

GLENAT_COLLECTION_URL = "https://www.glenat.com/livres-glenat-disney/"
GLENAT_BASE           = "https://www.glenat.com"
GLENAT_KEY_PREFIX     = "glenat:"

FANTAGRAPHICS_DISNEY_URL = "https://www.fantagraphics.com/collections/disney/products.json"
FANTAGRAPHICS_BASE       = "https://www.fantagraphics.com/products/"
FANTAGRAPHICS_KEY_PREFIX = "fanta:"

MARVEL_SERIES_URLS = [
    "https://www.marvel.com/comics/series/42808/uncle_scrooge_earths_mightiest_duck_2025_present"
]
MARVEL_KEY_PREFIX = "marvel:"

EGMONT_DE_URLS = [
    "https://www.egmont-shop.de/comics/disney/",
    "https://www.egmont-shop.de/magazine/"
]
EGMONT_DE_KEY_PREFIX = "egmont-de:"
EGMONT_BASE = "https://www.egmont-shop.de"

KATHIMERINI_URL = "https://www.kathimerini.gr/k/disney/"
KATHIMERINI_KEY_PREFIX = "kathi-gr:"

STATE_FILE    = "state.json"

if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = (
    os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID", "")
)
TELEGRAM_THREAD_ID_FR = os.environ.get("TELEGRAM_THREAD_ID_FR", "")
TELEGRAM_THREAD_ID_US = os.environ.get("TELEGRAM_THREAD_ID_US", "")
TELEGRAM_THREAD_ID_DE = os.environ.get("TELEGRAM_THREAD_ID_DE", "")
TELEGRAM_THREAD_ID_GR = os.environ.get("TELEGRAM_THREAD_ID_GR", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DisneyComicsWatcher/1.0)"}
AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "")
