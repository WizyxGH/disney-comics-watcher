import os
import re
from zoneinfo import ZoneInfo

SUPPORTED_COUNTRIES = {
    "fr", "us", "de", "gr", "it", "br", "eg", "bg", "hr", "ee", "lv", "lt",
    "pl", "cz", "rs", "si", "cn", "dk", "es", "fi", "is", "no", "nl", "uk", "se"
}

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
    "14016": {"name": "Super Picsou Géant",                     "inducks": "SPG"},
    "12651": {"name": "SPG HS Dynastie de Picsou",              "inducks": ("SPGHS", 3, "H")},
    "12825": {"name": "SPG HS Super Donald Géant",              "inducks": ("SPGHS", 3, "D")},
    "13459": {"name": "SPG HS Jeux",                            "inducks": ("SPGHS", 3, "J")},
    "11065": {"name": "Les grands méchants",                    "inducks": ("SPGHS", 3, "M")},
    "14068": {"name": "Les Trésors de Picsou",                  "inducks": "TP"},
    "14067": {"name": "Journal de Mickey",                      "inducks": "JM"},
    "14108": {"name": "Journal de Mickey HS",                   "inducks": ("JMHSN", 3)},
    "12011": {"name": "Le Journal de Mickey HS BD Collector",   "inducks": "JMHSC"},
    "15935": {"name": "Le Meilleur du Journal de Mickey",       "inducks": "JMC"},
    "15970": {"name": "Le Meilleur du JdM HS"},
    "15350": {"name": "Le Meilleur des Trésors de Picsou"},
    "18914": {"name": "Le Meilleur du JdM HS Spécial Enquêtes"},
    "15190": {"name": "Les Chroniques de Fantomiald",           "inducks": ("CF", 5)},
    "14268": {"name": "Les Incontournables de Disney",          "inducks": ("LI", 4)},
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
FANTAGRAPHICS_KEY_PREFIX = "fantagraphics:"

MARVEL_SERIES_URLS = [
    "https://www.marvel.com/comics/series/42808/uncle_scrooge_earths_mightiest_duck_2025_present"
]
MARVEL_KEY_PREFIX = "marvel:"
DYNAMITE_KEY_PREFIX = "dynamite:"

EGMONT_DE_URLS = [
    "https://www.egmont-shop.de/comics/disney/",
    "https://www.egmont-shop.de/magazine/"
]
EGMONT_DE_KEY_PREFIX = "egmont-de:"
EGMONT_BASE = "https://www.egmont-shop.de"
LTB_DE_KEY_PREFIX = "ltb-de:"

KATHIMERINI_URL = "https://www.kathimerini.gr/k/disney/"
KATHIMERINI_KEY_PREFIX = "kathi-gr:"

PANINI_IT_KEY_PREFIX = "panini-it:"
PANINI_BR_KEY_PREFIX = "panini-br:"
NAHDET_MISR_EG_KEY_PREFIX = "nahdet_misr_eg:"
BG_KEY_PREFIX = "bg:"
HR_KEY_PREFIX = "hr:"
EE_KEY_PREFIX = "ee:"
LV_KEY_PREFIX = "lv:"
LT_KEY_PREFIX = "lt:"
PL_KEY_PREFIX = "pl:"
CZ_KEY_PREFIX = "cz:"
RS_KEY_PREFIX = "rs:"
SI_KEY_PREFIX = "si:"
CN_KEY_PREFIX = "cn:"
DK_KEY_PREFIX = "dk:"
ES_KEY_PREFIX = "es:"
FI_KEY_PREFIX = "fi:"
IS_KEY_PREFIX = "is:"
NO_KEY_PREFIX = "no:"
NL_KEY_PREFIX = "nl:"
UK_KEY_PREFIX = "uk:"
SE_KEY_PREFIX = "se:"

STATE_FILE    = "state.json"

if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip().strip('"').strip("'")
                # The real environment always wins: CI passes everything
                # through it, and tests need to override a value without the
                # local .env silently clobbering it back.
                if val:
                    os.environ.setdefault(key.strip(), val)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = (
    os.environ.get("TELEGRAM_CHAT_ID_FR") or os.environ.get("TELEGRAM_CHAT_ID", "")
)
# One Telegram topic per country, mirrored by one Discord role per country
# below. Both are derived from SUPPORTED_COUNTRIES so that adding a country
# stays a single-line change instead of touching three files.
TELEGRAM_THREADS = {
    cc: os.environ.get(f"TELEGRAM_THREAD_ID_{cc.upper()}", "")
    for cc in SUPPORTED_COUNTRIES
}

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ── Discord ─────────────────────────────────────────────────────────────────
# Webhook of the single announcements channel; each message pings the country role.
DISCORD_WEBHOOK_URL       = os.environ.get("DISCORD_WEBHOOK_URL", "")
# Private channel receiving the DBI skeletons (webhook equivalent of the admin DM).
DISCORD_ADMIN_WEBHOOK_URL = os.environ.get("DISCORD_ADMIN_WEBHOOK_URL", "")

# 'fr:123', 'fr: <@&123>', 'FR : 123' — the country code, then the first run of
# digits long enough to be a snowflake.
_RE_ROLE_PAIR = re.compile(r"([A-Za-z]{2})\s*:\s*<?@?&?(\d{5,})")

def _parse_role_ids(raw: str) -> dict[str, str]:
    """Parses 'fr:123,us:456' into {'fr': '123', 'us': '456'}.

    Kept as one variable instead of 25 so the GitHub secret list stays short;
    a per-country DISCORD_ROLE_ID_XX env var still wins if set.

    Pairs are extracted rather than split, so the id half may be a raw Discord
    mention and the separators may be commas, spaces or newlines. That way the
    output of typing '\\@France' in a channel pastes in unedited.
    """
    roles = {
        cc.lower(): role_id
        for cc, role_id in _RE_ROLE_PAIR.findall(raw)
    }
    unknown = set(roles) - SUPPORTED_COUNTRIES
    if unknown:
        print(f"  [warn] DISCORD_ROLE_IDS: unsupported country code(s) {sorted(unknown)}")
    return roles


DISCORD_ROLE_IDS = _parse_role_ids(os.environ.get("DISCORD_ROLE_IDS", ""))
for _cc in SUPPORTED_COUNTRIES:
    _override = os.environ.get(f"DISCORD_ROLE_ID_{_cc.upper()}", "")
    if _override:
        DISCORD_ROLE_IDS[_cc] = _override

# ── Notification backends ───────────────────────────────────────────────────
# Comma-separated: "discord", "telegram", or "discord,telegram".
# Defaults to telegram so that deploying never depends on Discord being
# configured: switching over is a config change, not a code change.
NOTIFY_BACKENDS = {
    b.strip().lower()
    for b in os.environ.get("NOTIFY_BACKENDS", "telegram").split(",")
    if b.strip()
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DisneyComicsWatcher/1.0)"}
