"""
isv_search.py — Publication code and issue lookup for Inducks ISV.

Uses the local inducks.db / Inducks database tables.
Provides canonical series mappings and smart fuzzy lookup for new comic releases.
"""

import os
import re
from collections import Counter
import unicodedata
from src.db import query_db

def _normalize(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace and strip punctuation."""
    if not s:
        return ""
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)  # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()
    return s

# Leading articles carry no identity: "The Disney Afternoon Adventures" is the
# series a shop lists as "Disney Afternoon Adventures".
_LEADING_ARTICLES = re.compile(r"^(?:the|il|lo|la|le|les|der|die|das|el|los|las|het)\s+")

def _strip_article(s: str) -> str:
    return _LEADING_ARTICLES.sub("", s)

# Canonical mapping of known recurring publications monitored across countries.
# Keys are normalized (lowercase, unaccented, punctuation-stripped).
CANONICAL_SERIES: dict[str, dict[str, str]] = {
    "it": {
        "topolino holiday celebration": "it/TL",
        "topolino variant": "it/TL",
        "topolino": "it/TL",
        "disney big": "it/DBIG",
        "zio paperone": "it/ZP",
        "i grandi classici disney": "it/GCD",
        "grandi classici disney": "it/GCD",
        "grandi classici": "it/GCD",
        "disney mix speciale": "it/DMIX",
        "disney mix": "it/DMIX",
        "paperinik": "it/PPK",
        "paperino mese": "it/PM",
        "paperino": "it/PM",
    },
    "de": {
        "micky maus comics": "de/MMC",
        "micky maus magazin": "de/MM",
        "micky maus": "de/MM",
        "lustiges taschenbuch europareise": "de/LTBER",
        "ltb europareise": "de/LTBER",
        "europareise": "de/LTBER",
        "lustiges taschenbuch phantomias collection": "de/LTBPC",
        "ltb phantomias collection": "de/LTBPC",
        "phantomias collection": "de/LTBPC",
        "lustiges taschenbuch ultimate phantomias": "de/LTBUP",
        "ltb ultimate phantomias": "de/LTBUP",
        "ultimate phantomias": "de/LTBUP",
        "lustiges taschenbuch classic edition": "de/LTBCE",
        "ltb classic edition": "de/LTBCE",
        "lustiges taschenbuch crime": "de/LTBCR",
        "ltb crime": "de/LTBCR",
        "lustiges taschenbuch premium plus": "de/LTBPRP",
        "ltb premium plus": "de/LTBPRP",
        "lustiges taschenbuch premium": "de/LTBPR",
        "ltb premium": "de/LTBPR",
        "lustiges taschenbuch abenteuer": "de/LTBAT",
        "ltb abenteuer": "de/LTBAT",
        "lustiges taschenbuch history": "de/LTBHI",
        "ltb history": "de/LTBHI",
        "lustiges taschenbuch galaxy": "de/LTBGA",
        "ltb galaxy": "de/LTBGA",
        "lustiges taschenbuch fantasy": "de/LTBFY",
        "ltb fantasy": "de/LTBFY",
        "lustiges taschenbuch enten edition": "de/LTBE",
        "ltb enten edition": "de/LTBE",
        "enten edition": "de/LTBE",
        "lustiges taschenbuch maus edition": "de/LTBM",
        "ltb maus edition": "de/LTBM",
        "maus edition": "de/LTBM",
        "lustiges taschenbuch sonderedition": "de/LTBSE",
        "ltb sonderedition": "de/LTBSE",
        "lustiges taschenbuch extra": "de/LTBX",
        "ltb extra": "de/LTBX",
        "lustiges taschenbuch young comics": "de/LTBYC",
        "ltb young comics": "de/LTBYC",
        "lustiges taschenbuch sonderband": "de/LTBSP",
        "lustiges taschenbuch spezial": "de/LTBSP",
        "ltb spezial": "de/LTBSP",
        "lustiges taschenbuch sonderband freizeit": "de/LTBBA",
        "lustiges taschenbuch camping": "de/LTBBA",
        "ltb camping": "de/LTBBA",
        "lustiges taschenbuch sonderband weihnachten": "de/LTBSB",
        "lustiges taschenbuch weihnachtsgeschichten": "de/LTBSB",
        "ltb weihnachten": "de/LTBSB",
        "lustiges taschenbuch sonderband winter": "de/LTBW",
        "ltb winter": "de/LTBW",
        "lustiges taschenbuch sonderband ostern": "de/LTBOS",
        "ltb ostern": "de/LTBOS",
        "lustiges taschenbuch sonderband halloween": "de/LTBHA",
        "ltb halloween": "de/LTBHA",
        "lustiges taschenbuch sonderband sommer": "de/LTBSO",
        "ltb sommer": "de/LTBSO",
        "lustiges taschenbuch ducktales": "de/LTBDT",
        "ltb ducktales": "de/LTBDT",
        "lustiges taschenbuch english edition": "de/LTBENG",
        "ltb english edition": "de/LTBENG",
        "lustiges taschenbuch mini pocket": "de/LTBMP",
        "ltb mini pocket": "de/LTBMP",
        "lustiges taschenbuch": "de/LTB",
        "ltb": "de/LTB",
        "entenhausen edition dagobert": "de/EEDCB",
        "entenhausen edition donald": "de/EEDCB",
        "entenhausen edition": "de/EEDCB",
        "disney stitch": "de/DS",
        "donald duck & co": "de/DDCO",
        "tollste geschichten von donald duck": "de/TGDD",
    },
    "gr": {
        "super miky": "gr/SMB",
        "σουπερ μικυ": "gr/SMB",
        "μικυ μαους": "gr/MM",
        "miky maoys": "gr/MM",
        "micky mouse": "gr/MM",
        "ντοναλντ": "gr/NTB",
        "ntonalnt": "gr/NTB",
        "donald": "gr/NTB",
        "κομιξ": "gr/KX",
        "komix": "gr/KX",
    },
    "us": {
        "talespin": "us/TS",
        "gargoyles": "us/GARD",
        "ducktales": "us/DTCD",
        "darkwing duck": "us/DWDD",
        "uncle scrooge": "us/US",
        "mickey mouse": "us/MM",
        "donald duck": "us/DD",
    },
    "br": {
        "graphic disney": "br/GRD",
        "colecao carl barks": "br/CCBD",
        "carl barks": "br/CCBD",
        "mickey apresenta": "br/MIC",
        "mickey": "br/MIC",
        "tio patinhas": "br/TP",
        "pato donald": "br/DON",
    },
    "bg": {
        "макрокомикс": "bg/MAC",
        "мики маус": "bg/MM",
        "доналд дак": "bg/DD",
    }
}

# Pre-normalized and sorted canonical entries for O(1) loop lookups
_SORTED_CANONICAL: dict[str, list[tuple[str, str]]] = {
    c: sorted([(_normalize(k), code) for k, code in mapping.items()], key=lambda x: len(x[0]), reverse=True)
    for c, mapping in CANONICAL_SERIES.items()
}

# Panini Italy URL SKU prefixes -> Inducks publication codes (checked against
# Inducks: "spev" is Disney Special Events, Zio Paperone / Grandi Classici /
# Paperinik are the Panini periods of those titles).
PANINI_SKU_MAP = {
    "1wtopo": "it/TL",
    "1wdbig": "it/DBIG",
    "1wzipa": "it/ZPP",
    "1wdmix": "it/DMIX",
    "1wspec": "it/SPD",
    "1wspev": "it/DSE",
    "1wgcd": "it/GCDN",
    "1wpk": "it/PPK",
    "1wpap": "it/PM",
}

# In-memory publication cache: {country: [(pub_code, norm_title, clean_title, issue_count)]}
_PUB_CACHE: dict[str, list[tuple[str, str, str, int]]] = {}
_CACHE_LOADED: set[str] = set()




def _extract_base_and_number(raw_title: str) -> tuple[str, str] | tuple[None, None]:
    """Extracts (base_title, issue_number) from a raw title string."""
    title = raw_title.strip()
    if not title:
        return None, None

    # Pattern 1: Title with separator and number e.g. "Nr. 106", "#148", "Band 4", "Volume 3".
    # The number may be followed by a subtitle after a colon: "Legacy #464: The Klondike Years".
    m = re.match(
        r"^(.*?)\s*(?:(?:(?<!\w)(?:Nr\.?|Band|Volume|Vol\.?|Tome)|#|- Band|Hors[- ]S[eé]rie)\s*)(\d[\d\-/]*)(?:[/\-]\d{4})?(?:[\s:;,.!?].*)?$",
        title,
        re.IGNORECASE,
    )
    if m:
        base, num = m.group(1).strip(), re.sub(r"[^\d\-/]", "", m.group(2))
        base = re.sub(r"[\s\-:]+$", "", base).strip()
        if base and num:
            return base, num

    # Pattern 2: Trailing number or month/year e.g. "Topolino 3700", "Disney Stitch 05/2026", "Disney Big 223"
    m2 = re.match(r"^(.*?)\s+(\d{1,4}(?:[/\-]\d{2,4})?)(?:\s.*)?$", title)
    if m2:
        base, num = m2.group(1).strip(), m2.group(2).strip()
        if base and num:
            return base, num

    return None, None


_DB_HAS_ISSUESCOUNT: bool | None = None

def _check_db_has_issuescount() -> bool:
    global _DB_HAS_ISSUESCOUNT
    if _DB_HAS_ISSUESCOUNT is None:
        try:
            info = query_db("PRAGMA table_info(inducks_publication)")
            _DB_HAS_ISSUESCOUNT = any(row[1] == "issuescount" for row in (info or []))
        except Exception:
            _DB_HAS_ISSUESCOUNT = False
    return _DB_HAS_ISSUESCOUNT


def _load_country_pubs(country: str):
    """Loads publications, alternative names, and issue counts for a country into memory."""
    if country in _CACHE_LOADED:
        return
    _CACHE_LOADED.add(country)

    if _check_db_has_issuescount():
        rows = query_db(
            "SELECT publicationcode, title, issuescount "
            "FROM inducks_publication "
            "WHERE countrycode = ?",
            (country,)
        )
    else:
        rows = query_db(
            "SELECT p.publicationcode, p.title, COUNT(i.issuecode) "
            "FROM inducks_publication p "
            "LEFT JOIN inducks_issue i ON p.publicationcode = i.publicationcode "
            "WHERE p.countrycode = ? "
            "GROUP BY p.publicationcode, p.title",
            (country,)
        )
    if not rows:
        return

    # Load alternative publication names from inducks_publicationname if available
    alt_map: dict[str, list[str]] = {}
    try:
        alt_rows = query_db(
            "SELECT pn.publicationcode, pn.publicationname "
            "FROM inducks_publicationname pn "
            "JOIN inducks_publication p ON pn.publicationcode = p.publicationcode "
            "WHERE p.countrycode = ?",
            (country,)
        )
        for pub_code, alt_name in (alt_rows or []):
            if alt_name:
                alt_map.setdefault(pub_code, []).append(alt_name)
    except Exception:
        pass

    _PUB_CACHE[country] = []
    for pub_code, title, count in rows:
        titles = [title] if title else []
        for alt in alt_map.get(pub_code, []):
            if alt not in titles:
                titles.append(alt)

        for t in titles:
            norm_title = _normalize(t)
            # Drop the parenthesised qualifier for base matching, before
            # _normalize turns the brackets into spaces: "Topolino (libretto)"
            # and "Μίκυ Μάους (Περίοδος Β')" share their base with the plain title.
            clean_title = _strip_article(_normalize(re.sub(r"\(.*?\)", "", t)))
            _PUB_CACHE[country].append((str(pub_code), norm_title, clean_title, int(count or 0)))


def _pick_publication(pub_codes: list[str], num: str | None) -> str:
    """Among publications sharing a title, the one an issue number belongs to.

    Inducks splits a relaunched magazine into periods with the same title
    (gr/MM until 2013, then gr/MMB), so the title alone is ambiguous:
      - a YYYY-MM number goes to the series numbered that way (bg/MAC, not bg/MA);
      - otherwise a series still running wins over a dead one, "running" being
        judged against the newest of them, so a stale dump does not matter;
      - then the series whose last number is closest to the issue's.
    """
    pub_codes = list(dict.fromkeys(pub_codes))
    if len(pub_codes) == 1:
        return pub_codes[0]
    stats = {p: _pub_stats(p) for p in pub_codes}

    if num and re.match(r"^\d{4}-\d{2}$", num):
        dated = [p for p in pub_codes if stats[p]["year_month"]]
        if dated:
            pub_codes = dated

    years = [stats[p]["last_year"] for p in pub_codes if stats[p]["last_year"]]
    newest = max(years) if years else 0

    def key(p):
        st = stats[p]
        running = bool(newest) and st["last_year"] >= newest - _RUNNING_YEARS
        distance = abs(int(num) - st["max_num"]) if num and num.isdigit() and st["max_num"] else float("inf")
        return (not running, distance, -st["count"])

    return min(pub_codes, key=key)


# A series whose last issue is this many years older than its newest homonym's
# has stopped: it is the previous period of the same magazine.
_RUNNING_YEARS = 2

_STATS_CACHE: dict[str, dict] = {}

def _pub_stats(pub_code: str) -> dict:
    """Highest numeric issue, year of the last dated issue, issue count, and
    whether the series is numbered YYYY-MM."""
    if pub_code in _STATS_CACHE:
        return _STATS_CACHE[pub_code]
    st = {"max_num": 0, "last_year": 0, "count": 0, "year_month": False}
    rows = query_db(
        "SELECT MAX(CASE WHEN issuenumber GLOB '[0-9]*' THEN CAST(issuenumber AS INTEGER) END), "
        "COUNT(*), MAX(CASE WHEN issuenumber GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]' THEN 1 ELSE 0 END) "
        "FROM inducks_issue WHERE publicationcode = ?",
        (pub_code,)
    )
    if rows:
        st["max_num"] = int(rows[0][0] or 0)
        st["count"] = int(rows[0][1] or 0)
        st["year_month"] = bool(rows[0][2])
    try:
        # '9999-12-31' stands for an unknown date in Inducks.
        rows = query_db(
            "SELECT MAX(filledoldestdate) FROM inducks_issue "
            "WHERE publicationcode = ? AND filledoldestdate < '9999'",
            (pub_code,)
        )
        if rows and rows[0][0]:
            st["last_year"] = int(str(rows[0][0])[:4])
    except Exception:
        pass
    _STATS_CACHE[pub_code] = st
    return st


def _same_title_family(pub_code: str, country: str) -> list[str]:
    """The publication plus every other one of the country sharing its base title."""
    _load_country_pubs(country)
    pubs = _PUB_CACHE.get(country, [])
    bases = {clean for code, _, clean, _ in pubs if code == pub_code and clean}
    return [pub_code] + [code for code, _, clean, _ in pubs if clean in bases and code != pub_code]


def _resolve_canonical(pub_code: str, country: str, num: str) -> str:
    """A curated publication code, unless it has stopped while a homonym runs on.

    The curated table is trusted while its series is alive: a title like
    "topolino" also names a dozen reprint series that must not compete. Once
    the series is dead (gr/MM ended in 2013), the magazine lives on under
    another period code (gr/MMB), chosen among the homonyms by number.
    """
    family = _same_title_family(pub_code, country)
    if len(family) == 1:
        return pub_code
    stats = _pub_stats(pub_code)
    years = [_pub_stats(p)["last_year"] for p in family]
    if stats["last_year"] >= max(years) - _RUNNING_YEARS:
        return pub_code
    # Dead in the dump, but the number follows its last one: the dump is
    # simply behind on this series.
    if num.isdigit() and stats["max_num"] < int(num) <= stats["max_num"] + _CONTINUATION_GAP:
        return pub_code
    return _pick_publication(family, num)


# How far past a series' last known number an issue still continues it.
_CONTINUATION_GAP = 5
# How far below a series' last number a loosely matched title may still sit
# (a dump ahead of the shop, a late reprint): further back, it is another book.
_LOOSE_MATCH_BACKLOG = 20


def _not_an_old_number(pub_code: str, num: str) -> bool:
    """False when a loosely matched title would land on an issue the series
    printed long ago: a new release is near the series' last number."""
    return not num.isdigit() or int(num) >= _pub_stats(pub_code)["max_num"] - _LOOSE_MATCH_BACKLOG


def _contains_words(haystack: str, needle: str) -> bool:
    """True when needle appears in haystack as whole words ("io" is not in "topolino")."""
    return bool(needle) and f" {needle} " in f" {haystack} "


_NEWEST_CACHE: dict[str, int] = {}

def _country_newest_year(country: str) -> int:
    """Year of the newest dated issue of a country: "now" as far as the dump knows."""
    if country not in _NEWEST_CACHE:
        year = 0
        try:
            rows = query_db(
                "SELECT MAX(filledoldestdate) FROM inducks_issue "
                "WHERE issuecode LIKE ? AND filledoldestdate < '9999'",
                (f"{country}/%",)
            )
            if rows and rows[0][0]:
                year = int(str(rows[0][0])[:4])
        except Exception:
            pass
        _NEWEST_CACHE[country] = year
    return _NEWEST_CACHE[country]


def search_publication_code(
    raw_title: str,
    country: str,
    page_url: str | None = None,
    cover_url: str | None = None,
    publisher: str | None = None
) -> str | None:
    """
    Main entry point: given a raw title and country code, returns the full
    Inducks issue path (e.g. 'it/TL 3700', 'de/MMC 106', 'gr/SMB 134').
    A variant cover gets its own issue code, as on Inducks ('it/DSE 58B').
    """
    if not raw_title:
        return None
    path = _search_issue_path(raw_title, country, page_url)
    if path and _is_old_issue(path, country):
        # Another magazine already holds this code: Inducks lists the issue
        # years back ("Paperinik 119" is not it/PK 119 of 2003). Two magazines
        # never share a code, so an unknown beats a wrong one.
        return None
    if path and _is_variant(raw_title, page_url):
        path = _variant_path(path)
    return path


def _is_old_issue(path: str, country: str) -> bool:
    """True when Inducks lists this issue, dated years before the newest one
    of the country: a new release cannot be it."""
    rows = query_db(
        "SELECT MAX(filledoldestdate) FROM inducks_issue "
        "WHERE REPLACE(issuecode, ' ', '') = ? AND filledoldestdate < '9999'",
        (path.replace(" ", ""),)
    )
    date = rows[0][0] if rows else None
    newest = _country_newest_year(country)
    return bool(date and newest) and int(str(date)[:4]) < newest - _RUNNING_YEARS


_CODES_CACHE: dict[str, list[tuple[str, str]]] = {}

def issue_code(pub_code: str, num: str) -> str:
    """The Inducks code of an issue, spaced as Inducks spaces it ('it/PM  557',
    'it/TL 3700', 'uk/MF1993-32'): the dump's own code when it lists the
    issue, otherwise the spacing the publication uses for numbers that long.
    A single space is wrong for most series, and issue.php finds nothing."""
    pub_code = pub_code.rstrip()
    if pub_code not in _CODES_CACHE:
        _CODES_CACHE[pub_code] = [
            (str(c), str(n)) for c, n in (query_db(
                "SELECT issuecode, issuenumber FROM inducks_issue WHERE publicationcode = ?",
                (pub_code,)) or [])
        ]
    codes = _CODES_CACHE[pub_code]
    if num.isdigit() and not any(len(n) > 1 and n.startswith("0") for _, n in codes):
        # A shop's "Tome 04" is issue 4 where Inducks numbers without zeros.
        num = str(int(num))
    for code, number in codes:
        if number.upper() == num.upper():
            return code
    # Separator Inducks puts before a number of each length (the usual one:
    # a few issues of a series are spaced otherwise).
    counts: dict[int, Counter] = {}
    for code, number in codes:
        sep = code[len(pub_code):len(code) - len(number)]
        if code.startswith(pub_code) and code.endswith(number) and not sep.strip():
            counts.setdefault(len(number), Counter())[sep] += 1
    seps = {length: c.most_common(1)[0][0] for length, c in counts.items()}
    if len(num) in seps:
        return f"{pub_code}{seps[len(num)]}{num}"
    if seps:
        # Numbers are right-aligned on a fixed width: a longer one eats the spaces.
        length, sep = max(seps.items(), key=lambda kv: kv[0])
        width = len(pub_code) + len(sep) + length
        pad = max(width - len(pub_code) - len(num), 0)
        return f"{pub_code}{' ' * pad}{num}"
    # No other issue to copy: Inducks' usual width, ten characters.
    return f"{pub_code}{' ' * max(_CODE_WIDTH - len(pub_code) - len(num), 1)}{num}"


_CODE_WIDTH = 10


# Panini product codes end with the issue number, then a format tag; a
# variant repeats the tag with a trailing "v" (1wspev062sp / 1wspev062spv,
# 1wtopo3702 / 1wtopo3702v).
_PANINI_VARIANT_SKU = re.compile(r"-1w[a-z]+\d+[a-z]*v-[a-z]{2}\d+\.html")

def _is_variant(raw_title: str, page_url: str | None) -> bool:
    return bool(re.search(r"\bvariant\b", raw_title, re.IGNORECASE)
                or (page_url and _PANINI_VARIANT_SKU.search(page_url.lower())))


def _variant_path(path: str) -> str:
    """'it/DSE 62' -> 'it/DSE 62B': the first letter after those Inducks
    already gives that number's variants (58B, 58C, 58D -> 58E)."""
    pub_code, _, num = path.rpartition(" ")
    pub_code = pub_code.rstrip()
    if not num.isdigit():
        return path
    taken = {
        str(r[0]) for r in (query_db(
            "SELECT issuenumber FROM inducks_issue WHERE publicationcode = ? AND issuenumber GLOB ?",
            (pub_code, f"{num}[A-Z]"),
        ) or [])
    }
    for letter in "BCDEFGHIJKLMNOPQRSTUVWXYZ":
        if f"{num}{letter}" not in taken:
            return issue_code(pub_code, f"{num}{letter}")
    return path


def _search_issue_path(raw_title: str, country: str, page_url: str | None) -> str | None:
    # 1. Italian Panini URL SKU identification
    if page_url and country == "it":
        url_lower = page_url.lower()
        for sku_prefix, pub_code in PANINI_SKU_MAP.items():
            if sku_prefix in url_lower:
                # First try to find explicit SKU number (e.g. 1wspec113 -> 113)
                m_sku = re.search(re.escape(sku_prefix) + r"(\d+)", url_lower)
                # Next try to find issue number from title
                m_num = re.search(r"\b(\d{1,4})\b", raw_title)
                num = m_num.group(1) if m_num else (m_sku.group(1) if m_sku else None)
                # A publication code without an issue number is not an issue:
                # better an unknown than a DBI entry for "TL".
                if not num:
                    return None
                num = str(int(num))
                # Inducks numbers Panini's extra issues after the regular one
                # they follow, as the product code does: 1wdmix041sp3 is
                # Disney Mix 41SP3, whatever number the shop title shows.
                m_extra = re.search(re.escape(sku_prefix) + r"(\d+)sp(\d+)", url_lower)
                if m_extra:
                    num = f"{int(m_extra.group(1))}SP{m_extra.group(2)}"
                return issue_code(_resolve_canonical(pub_code, country, num), num)

    base, num = _extract_base_and_number(raw_title)
    if not num:
        # Same reason: a title without a number cannot name an issue, and a
        # loose match on it only finds noise ("io" -> it/BIG).
        return None
    norm_base = _normalize(base or "")

    # Normalize dates e.g. 05/2026 -> 2026-05, or 10/26 -> 2026-10
    m_date = re.match(r"^(\d{1,2})/(\d{4})$", num)
    if m_date:
        mm, yyyy = m_date.groups()
        num = f"{yyyy}-{mm.zfill(2)}"
    else:
        m_date2 = re.match(r"^(\d{1,2})/(\d{2})$", num)
        if m_date2:
            issue_part, yy = m_date2.groups()
            num = f"20{yy}-{issue_part.zfill(2)}"

    # 2. Canonical mapping, exact match first (e.g. "topolino" -> it/TL). It
    # names a magazine, not one period of it: the period is chosen by number.
    for norm_key, pub_code in _SORTED_CANONICAL.get(country, []):
        if norm_base == norm_key:
            return issue_code(_resolve_canonical(pub_code, country, num), num)

    # 3. Database search, matching whole words only, ranked by relevance.
    _load_country_pubs(country)
    pubs = _PUB_CACHE.get(country, [])
    if pubs:
        # Book titles stack series and subtitle ("Donald Duck: Duck Avenger
        # Strikes Again: Disney Masters Vol. 8"): the segment right before the
        # number names the series, so it is tried before the whole title.
        segments = [s for s in re.split(r"\s*(?::|\s-\s)\s*", base or "") if s.strip()]
        segment_term = _strip_article(_normalize(segments[-1])) if len(segments) > 1 else ""
        search_terms = [segment_term, _strip_article(norm_base)]
        # Also try expanding German abbreviations e.g. "ltb ..." -> "lustiges taschenbuch ..."
        if country == "de" and (norm_base.startswith("ltb ") or norm_base.startswith("ltb-")):
            search_terms.append(re.sub(r"^ltb[\s\-]+", "lustiges taschenbuch ", norm_base))

        best_score, best_tied = 0, []
        for term in dict.fromkeys(t for t in search_terms if t):
            scores: dict[str, int] = {}
            for pub_code, norm_title, clean_title, count in pubs:
                if not clean_title:
                    continue
                if term == clean_title or term == norm_title:
                    score = 100
                elif term.startswith(clean_title + " ") or clean_title.startswith(term + " "):
                    score = 70
                elif _contains_words(term, clean_title) or _contains_words(clean_title, term):
                    score = 40
                else:
                    continue
                scores[pub_code] = max(score, scores.get(pub_code, 0))
            if term == segment_term and 100 not in scores.values():
                # A lone segment is only trusted as an exact series name: a
                # loose hit on "Das Magazin" means nothing.
                continue
            if scores and max(scores.values()) > best_score:
                best_score = max(scores.values())
                # Homonyms (periods of one magazine) tie: the number decides.
                best_tied = [p for p, sc in scores.items() if sc == best_score]
            if best_score == 100:
                break

        if best_tied and best_score < 100:
            # A loose match to a series that stopped years ago is a different
            # magazine sharing a word ("DuckTales - Nuova Serie" is not the
            # DuckTales of 1994): a new release belongs to a running series.
            newest = _country_newest_year(country)
            best_tied = [p for p in best_tied
                         if not newest or _pub_stats(p)["last_year"] >= newest - _RUNNING_YEARS]
            # Nor does a new release reuse a number the series printed long
            # ago: "Donald Duck Gift Box Set 3" is not Donald Duck #3 (1940s).
            best_tied = [p for p in best_tied if _not_an_old_number(p, num)]

        if best_tied:
            return issue_code(_pick_publication(best_tied, num), num)

    # 4. Fallback canonical word match (for subtitles: e.g. "Topolino - La grande sfida"),
    # as loose as the matches above, so held to the same number check.
    for norm_key, pub_code in _SORTED_CANONICAL.get(country, []):
        if _contains_words(norm_base, norm_key):
            pub = _resolve_canonical(pub_code, country, num)
            return issue_code(pub, num) if _not_an_old_number(pub, num) else None

    return None


def lookup_issue_code(pub_code: str, issue_number: str) -> str | None:
    """Returns the exact Inducks issue code if present in the database."""
    rows = query_db(
        "SELECT issuecode FROM inducks_issue WHERE publicationcode = ? AND issuenumber = ?",
        (pub_code, issue_number),
    )
    if rows:
        return str(rows[0][0])
    return None


def get_latest_inducks_issue_number(publication_code: str) -> int:
    """Returns the highest numeric issue number for a publication code from the DB."""
    rows = query_db(
        "SELECT MAX(CAST(issuenumber AS INTEGER)) FROM inducks_issue WHERE publicationcode = ? AND issuenumber GLOB '[0-9]*'",
        (publication_code,)
    )
    if rows and rows[0][0] is not None:
        return int(rows[0][0])
    return 0


def _find_issue_by_title(raw_title: str, country: str) -> str | None:
    """Preserved for compatibility."""
    return search_publication_code(raw_title, country)
