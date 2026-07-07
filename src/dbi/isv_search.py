"""
isv_search.py — DB-backed publication code lookup for the Inducks ISV.

Uses the inducks_publication and inducks_issue tables populated by setup_db.py.
Falls back gracefully if the DB is unavailable.
"""

import re
import unicodedata

from src.db import query_db

# In-memory cache: {country_code: {normalized_title: publicationcode}}
_pub_cache: dict[str, dict[str, str]] = {}
_cache_loaded: set[str] = set()

# In-memory cache for issues: {country_code: [(issuecode, title)]}
_issue_cache: dict[str, list[tuple[str, str]]] = {}



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


def _load_country(country: str):
    """Loads all publications for a country into the in-memory cache."""
    if country in _cache_loaded:
        return
    _cache_loaded.add(country)

    rows = query_db(
        "SELECT publicationcode, title FROM inducks_publication WHERE countrycode = ?",
        (country,)
    )
    if not rows:
        return

    _pub_cache[country] = {}
    for pub_code, title in rows:
        if title:
            _pub_cache[country][_normalize(title)] = str(pub_code)


def _extract_base_and_number(raw_title: str) -> tuple[str, str] | tuple[None, None]:
    """Extracts (base_title, issue_number) from a raw title string.

    Examples:
      "Micky Maus Magazin Nr. 15/2026" -> ("Micky Maus Magazin", "15")
      "Lustiges Taschenbuch 613"        -> ("Lustiges Taschenbuch", "613")
      "Mickey Mouse Legacy #331"        -> ("Mickey Mouse Legacy", "331")
    """
    # Pattern: title / Nr. / # / Band / volume followed by a number
    m = re.match(
        r"^(.*?)\s*(?:Nr\.?\s*|#\s*|- Band\s*|Volume\s*|Vol\.?\s*|Tome\s*|Hors[- ]S[eé]rie\s*)?(\d[\d\-/]*)(?:[/\-]\d{4})?(?:\s.*)?$",
        raw_title.strip(),
        re.IGNORECASE,
    )
    if m:
        base = m.group(1).strip()
        num = re.sub(r"[^\d\-/]", "", m.group(2))  # keep digits and separators
        if base and num:
            return base, num
    return None, None


def _find_publication(base_title: str, country: str) -> str | None:
    """Searches the cache for a publication matching the base title."""
    _load_country(country)
    country_pubs = _pub_cache.get(country, {})
    if not country_pubs:
        return None

    norm = _normalize(base_title)

    # 1. Exact normalized match
    if norm in country_pubs:
        return country_pubs[norm]

    # 2. Contains match (the DB title contains our query or vice versa)
    for db_title, pub_code in country_pubs.items():
        if norm in db_title or db_title in norm:
            return pub_code

    # 3. Significant word overlap (≥ 60% of words match)
    query_words = set(norm.split())
    best_score = 0.0
    best_code = None
    for db_title, pub_code in country_pubs.items():
        db_words = set(db_title.split())
        if not query_words or not db_words:
            continue
        overlap = len(query_words & db_words) / max(len(query_words), len(db_words))
        if overlap > best_score:
            best_score = overlap
            best_code = pub_code

    if best_score >= 0.6:
        return best_code

    return None


def _roman_to_int(s: str) -> str | None:
    rom_val = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}
    int_val = 0
    s = s.lower()
    for i in range(len(s)):
        if s[i] not in rom_val: return None
        if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
            int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
        else:
            int_val += rom_val[s[i]]
    return str(int_val)


def _convert_romans(s: str) -> str:
    words = s.split()
    for i, w in enumerate(words):
        val = _roman_to_int(w)
        if val: words[i] = val
    return ' '.join(words)


def _load_country_issues(country: str):
    if country in _issue_cache:
        return
    rows = query_db(
        "SELECT issuecode, title FROM inducks_issue WHERE publicationcode LIKE ? AND title IS NOT NULL AND title != ''",
        (f"{country}/%",)
    )
    _issue_cache[country] = rows if rows else []


def _find_issue_by_title(raw_title: str, country: str) -> str | None:
    """Searches the issue cache for an issue whose title words are all contained in the raw_title."""
    _load_country_issues(country)
    issues = _issue_cache.get(country, [])
    if not issues:
        return None

    norm_raw = _normalize(raw_title)
    if not norm_raw:
        return None
        
    norm_raw_converted = _convert_romans(norm_raw)
    raw_words = set(norm_raw_converted.split())
    if not raw_words:
        return None

    best_score = 0
    best_code = None

    for issuecode, title in issues:
        norm_title = _normalize(title)
        if not norm_title:
            continue
            
        norm_title_converted = _convert_romans(norm_title)
        title_words = set(norm_title_converted.split())
        
        if not title_words:
            continue
            
        # Check if ALL words in the issue title are present in the raw title
        if title_words.issubset(raw_words):
            # Prefer longer titles
            score = len(title_words)
            if score > best_score:
                best_score = score
                best_code = issuecode
                
    if best_score > 0:
        return " ".join(best_code.split())
        
    return None


def search_publication_code(raw_title: str, country: str) -> str | None:
    """
    Main entry point: given a raw title and country code, returns the full
    Inducks issue path (e.g. 'de/MM 15') or None if not found.

    Search strategy:
    1. Search issue titles directly (for pre-indexed issues that share a publication code)
    2. Extract base title + issue number from the raw title
    3. Look up the publication in the local DB cache (exact → contains → fuzzy)
    4. Build and return the issue path
    """
    issue_path = _find_issue_by_title(raw_title, country)
    if issue_path:
        return issue_path

    base_title, num = _extract_base_and_number(raw_title)
    if not base_title or not num:
        return None

    pub_code = _find_publication(base_title, country)
    if pub_code:
        # The publicationcode already contains the country prefix
        return f"{pub_code} {num}"

    return None


def lookup_issue_code(pub_code: str, issue_number: str) -> str | None:
    """
    Given a publication code and issue number, returns the exact Inducks
    issue code (e.g. 'de/MM   15') by querying the DB directly.

    Useful for verifying if an issue already exists in Inducks.
    """
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
