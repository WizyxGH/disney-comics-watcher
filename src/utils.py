import os
import re
import json
import requests
from datetime import datetime
from src.config import HEADERS, SEARCH_URL, STATE_FILE

_session = None

def get_session():
    """Returns a shared HTTP requests session."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        try:
            _session.get(SEARCH_URL, timeout=15)
        except requests.RequestException:
            pass
    return _session

def load_state():
    """Loads the state dictionary from the state JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "rb") as f:
                return json.loads(f.read())
        except Exception:
            pass
    return {}

def save_state(state):
    """Saves the state dictionary to the state JSON file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

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

def parse_date_fr(s):
    """DD/MM/YYYY or YYYY-MM-DD -> date object, or None if invalid."""
    if not s:
        return None
    s = str(s).strip()
    try:
        if "-" in s:
            y, m, d = s.split("-")
            return datetime(int(y), int(m), int(d)).date()
        elif "." in s:
            d, m, y = s.split(".")
            return datetime(int(y), int(m), int(d)).date()
        else:
            d, m, y = s.split("/")
            return datetime(int(y), int(m), int(d)).date()
    except (ValueError, AttributeError):
        return None

def truncate_summary(text: str, max_len: int = 400) -> str:
    """Cleanly truncates the summary to avoid cutting a word in half."""
    if not text or len(text) <= max_len:
        return text or ""
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.strip() + "…"

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

def is_fully_indexed_in_inducks(issue_code: str) -> bool:
    """Check if an issue is fully indexed in Inducks by querying the Turso DB."""
    if not issue_code:
        return False
        
    try:
        from src.db import query_db
        clean_code = issue_code.replace(" ", "").lower()
        res = query_db("SELECT fullyindexed FROM inducks_issue WHERE LOWER(REPLACE(issuecode, ' ', '')) = ?", (clean_code,))
        if res and len(res) > 0:
            return res[0][0] == 'Y'
            
        # Fallback for double issues (e.g. fr/JM 3864-65 -> check fr/JM 3864)
        if '-' in clean_code:
            first_part = clean_code.split('-')[0]
            res = query_db("SELECT fullyindexed FROM inducks_issue WHERE LOWER(REPLACE(issuecode, ' ', '')) = ?", (first_part,))
            if res and len(res) > 0:
                return res[0][0] == 'Y'
    except Exception as e:
        print(f"  [warn] Failed to query fully indexed status from DB for {issue_code}: {e}")
        
    return False

def does_issue_exist_in_inducks(issue_code: str) -> bool:
    """Check if an issue exists in Inducks by querying the Turso DB."""
    if not issue_code:
        return False
        
    try:
        from src.db import query_db
        clean_code = issue_code.replace(" ", "").lower()
        res = query_db("SELECT 1 FROM inducks_issue WHERE LOWER(REPLACE(issuecode, ' ', '')) = ?", (clean_code,))
        if res and len(res) > 0:
            return True
            
        if '-' in clean_code:
            first_part = clean_code.split('-')[0]
            res = query_db("SELECT 1 FROM inducks_issue WHERE LOWER(REPLACE(issuecode, ' ', '')) = ?", (first_part,))
            if res and len(res) > 0:
                return True
    except Exception as e:
        print(f"  [warn] Failed to query issue existence from DB for {issue_code}: {e}")
        
    return False
