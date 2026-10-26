"""
isv_search.py — Publication code and issue lookup for Inducks ISV.

Uses the local inducks.db / Inducks database tables.
Provides canonical series mappings and smart fuzzy lookup for new comic releases.
"""

import os
import re
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
        "paperinik": "it/PK",
        "paperino mese": "it/PM",
        "paperino": "it/PM",
    },
    "de": {
        "micky maus comics": "de/MMC",
        "micky maus magazin": "de/MM",
        "micky maus": "de/MM",
        "lustiges taschenbuch young comics": "de/LTBYC",
        "lustiges taschenbuch sonderband": "de/LTBSP",
        "lustiges taschenbuch spezial": "de/LTBSP",
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

# Panini Italy URL SKU prefixes -> Inducks publication codes
PANINI_SKU_MAP = {
    "1wtopo": "it/TL",
    "1wdbig": "it/DBIG",
    "1wzipa": "it/ZP",
    "1wdmix": "it/DMIX",
    "1wspec": "it/SPD",
    "1wspev": "it/SPEV",
    "1wgcd": "it/GCD",
    "1wpk": "it/PK",
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

    # Pattern 1: Title with separator and number e.g. "Nr. 106", "#148", "Band 4", "Volume 3"
    m = re.match(
        r"^(.*?)\s*(?:(?:Nr\.?|#|- Band|Band|Volume|Vol\.?|Tome|Hors[- ]S[eé]rie)\s*)(\d[\d\-/]*)(?:[/\-]\d{4})?(?:\s.*)?$",
        title,
        re.IGNORECASE,
    )
    if m:
        base, num = m.group(1).strip(), re.sub(r"[^\d\-/]", "", m.group(2))
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
            # Remove text in parentheses for clean base matching: e.g. "Topolino (libretto)" -> "Topolino"
            clean_title = re.sub(r"\(.*?\)", "", norm_title).strip()
            _PUB_CACHE[country].append((str(pub_code), norm_title, clean_title, int(count or 0)))


def _disambiguate_homonyms(candidates: list[tuple], num: str, country: str) -> str | None:
    """When multiple publications share the same title, pick the one whose
    numbering scheme matches the detected issue number.

    For instance, Bulgarian 'Макрокомикс' maps to bg/MA (issues 1-30),
    bg/MAC (issues 2025-01..2026-09, YYYY-MM format), and bg/MACRO (issues 1-4).
    A number like '2026-10' clearly belongs to bg/MAC, not bg/MA.
    """
    top_score = candidates[0][0]
    tied = [c for c in candidates if c[0] >= top_score - 10]
    if len(tied) <= 1:
        return None

    is_year_month = bool(re.match(r'^\d{4}-\d{2}$', num))

    if is_year_month:
        # Prefer the publication that uses YYYY-MM issue numbering
        for _, _, pub_code in tied:
            sample = query_db(
                "SELECT issuenumber FROM inducks_issue WHERE publicationcode = ? ORDER BY issuecode DESC LIMIT 1",
                (pub_code,)
            )
            if sample and sample[0][0] and re.match(r'^\d{4}-\d{2}$', str(sample[0][0])):
                return pub_code

    # For plain numeric issues, prefer the publication with the closest max issue number (active continuation)
    if num.isdigit():
        target_num = int(num)
        best_match = None
        best_distance = float('inf')
        for _, count, pub_code in tied:
            max_issue = _get_max_numeric_issue(pub_code)
            if max_issue > 0:
                distance = abs(target_num - max_issue)
                # Pick the series whose last published number is closest to target_num
                if distance < best_distance:
                    best_distance = distance
                    best_match = pub_code
        if best_match:
            return best_match

    return None


_MAX_ISSUE_CACHE: dict[str, int] = {}

def _get_max_numeric_issue(pub_code: str) -> int:
    if pub_code in _MAX_ISSUE_CACHE:
        return _MAX_ISSUE_CACHE[pub_code]
    rows = query_db(
        "SELECT MAX(CAST(issuenumber AS INTEGER)) FROM inducks_issue "
        "WHERE publicationcode = ? AND issuenumber GLOB '[0-9]*'",
        (pub_code,)
    )
    val = int(rows[0][0]) if rows and rows[0][0] is not None else 0
    _MAX_ISSUE_CACHE[pub_code] = val
    return val


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
    """
    if not raw_title:
        return None

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
                if num:
                    return f"{pub_code} {int(num)}"
                return pub_code

    base, num = _extract_base_and_number(raw_title)
    if not base:
        base = raw_title
    norm_base = _normalize(base)

    # Normalize dates e.g. 05/2026 -> 2026-05, or 10/26 -> 2026-10
    if num:
        m_date = re.match(r"^(\d{1,2})/(\d{4})$", num)
        if m_date:
            mm, yyyy = m_date.groups()
            num = f"{yyyy}-{mm.zfill(2)}"
        else:
            m_date2 = re.match(r"^(\d{1,2})/(\d{2})$", num)
            if m_date2:
                issue_part, yy = m_date2.groups()
                num = f"20{yy}-{issue_part.zfill(2)}"

    # 2. Canonical mapping lookup (prioritizing longer matches first, pre-sorted)
    for norm_key, pub_code in _SORTED_CANONICAL.get(country, []):
        if norm_base == norm_key or norm_base.startswith(norm_key) or norm_key in norm_base:
            if num:
                return f"{pub_code} {num}"
            return pub_code

    # 3. Database search with ranking by relevance and historical issue count
    _load_country_pubs(country)
    pubs = _PUB_CACHE.get(country, [])
    if pubs:
        candidates = []
        for pub_code, norm_title, clean_title, count in pubs:
            if norm_base == clean_title or norm_base == norm_title:
                candidates.append((100, count, pub_code))
            elif norm_base.startswith(clean_title) or clean_title.startswith(norm_base):
                candidates.append((70, count, pub_code))
            elif clean_title in norm_base or norm_base in clean_title:
                candidates.append((40, count, pub_code))

        if candidates:
            # When multiple publications share the same title (homonyms),
            # disambiguate using the issue number format and recency.
            if num and len(candidates) > 1:
                best = _disambiguate_homonyms(candidates, num, country)
                if best:
                    return f"{best} {num}"

            # Default: sort by score descending, then by issue count descending
            candidates.sort(reverse=True)
            best_pub = candidates[0][2]
            if num:
                return f"{best_pub} {num}"
            return best_pub

    # 4. Fallback: if issue number exists and title contains known single-word hints
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
