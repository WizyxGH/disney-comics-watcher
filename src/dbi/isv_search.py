"""
isv_search.py — Publication code and issue lookup for Inducks ISV.

Uses the local inducks.db / Inducks database tables.
Provides canonical series mappings and smart fuzzy lookup for new comic releases.
"""

import os
import re
import unicodedata
from src.db import query_db

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
        "paperino": "it/PA",
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
    }
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
    "1wpap": "it/PA",
}

# In-memory publication cache: {country: [(pub_code, norm_title, clean_title, issue_count)]}
_PUB_CACHE: dict[str, list[tuple[str, str, str, int]]] = {}
_CACHE_LOADED: set[str] = set()


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


def _load_country_pubs(country: str):
    """Loads publications and issue counts for a country into memory."""
    if country in _CACHE_LOADED:
        return
    _CACHE_LOADED.add(country)

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

    _PUB_CACHE[country] = []
    for pub_code, title, count in rows:
        if title:
            norm_title = _normalize(title)
            # Remove text in parentheses for clean base matching: e.g. "Topolino (libretto)" -> "Topolino"
            clean_title = re.sub(r"\(.*?\)", "", norm_title).strip()
            _PUB_CACHE[country].append((str(pub_code), norm_title, clean_title, int(count or 0)))


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

    # Normalize dates e.g. 05/2026 -> 2026-05
    if num:
        m_date = re.match(r"^(\d{1,2})/(\d{4})$", num)
        if m_date:
            mm, yyyy = m_date.groups()
            num = f"{yyyy}-{mm.zfill(2)}"

    # 2. Canonical mapping lookup (prioritizing longer matches first)
    country_canon = CANONICAL_SERIES.get(country, {})
    sorted_canon_keys = sorted(country_canon.keys(), key=len, reverse=True)
    for key in sorted_canon_keys:
        norm_key = _normalize(key)
        if norm_base == norm_key or norm_base.startswith(norm_key) or norm_key in norm_base:
            pub_code = country_canon[key]
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
            # Sort by score descending, then by issue count descending
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
        "SELECT issuenumber FROM inducks_issue WHERE publicationcode = ?",
        (publication_code,)
    )
    max_num = 0
    for (issue_num_str,) in rows:
        if issue_num_str:
            digits = re.sub(r"\D", "", str(issue_num_str))
            if digits:
                n = int(digits)
                if n > max_num:
                    max_num = n
    return max_num


def _find_issue_by_title(raw_title: str, country: str) -> str | None:
    """Preserved for compatibility."""
    return search_publication_code(raw_title, country)
