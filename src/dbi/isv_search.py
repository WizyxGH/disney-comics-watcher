import os
import re
import time
import requests



_isv_cache = {}

def load_publications():
    """Loads publication mappings from the Turso database into memory."""
    global _isv_cache
    if _isv_cache:
        return _isv_cache
        
    try:
        from src.db import query_db
        print("  [DB] Fetching publications from database...")
        rows = query_db("SELECT publicationcode, countrycode, title FROM inducks_publication")
        
        for (pub_code, country_code, title) in rows:
            if not title:
                continue
            title = title.lower()
            
            if country_code not in _isv_cache:
                _isv_cache[country_code] = {}
                
            _isv_cache[country_code][title] = pub_code
    except Exception as e:
        print(f"  [warn] Failed to fetch publications from DB: {e}")
        
    return _isv_cache

def search_publication_code(raw_title: str, country: str) -> str | None:
    """
    Searches the ISV for the base title and returns the exact Inducks publication code if found.
    Extracts the issue number from the title.
    Returns: issue_path (e.g. 'de/MM 09') or None.
    """
    pubs_by_country = load_publications()
    country_pubs = pubs_by_country.get(country, {})
    if not country_pubs:
        return None
        
    m = re.match(r'^(.*?)(?:\s*(?:Nr\.|#|- Band)\s*|\s+0*)(\d+)(?:[/\-]\d{4})?(?:\s+.*)?$', raw_title, re.IGNORECASE)
    if m:
        base_title = m.group(1).strip()
        num = m.group(2).strip()
        
        # Exact match
        pub_code = country_pubs.get(base_title.lower())
        
        if pub_code:
            return f"{pub_code} {num}"
            
    return None
