import os
import sys
import re
import urllib.request
from bs4 import BeautifulSoup

# Add the root directory to sys.path to import src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ltb_enricher import LTB_URL_PATTERNS, _parse_stories, _build_ltb_url
from src.dbi.generator import generate_dbi_skeleton
from src.db import query_db

LTB_BASE = "https://www.lustiges-taschenbuch.de/ausgaben/"

# Reverse mapping to easily look up the Inducks prefix from the URL pattern
URL_TO_PREFIX = {}
for prefix, url_tpl in LTB_URL_PATTERNS.items():
    # Remove {num} to get the base path
    base_path = url_tpl.replace("{num}", "").replace("band-", "")
    if base_path.endswith("/"):
        base_path = base_path[:-1]
    URL_TO_PREFIX[base_path] = prefix

def fetch_html(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

from src.utils import is_fully_indexed_in_inducks

def is_issue_in_dedbi(issue_code: str) -> bool:
    """Check if the issue is already in issues/de.dbi."""
    dbi_path = os.path.join(os.path.dirname(__file__), "..", "issues", "de.dbi")
    if not os.path.exists(dbi_path):
        return False
    with open(dbi_path, "r", encoding="utf-8") as f:
        content = f.read()
    # The issue code in de.dbi is usually just the part after 'de/'
    short_code = issue_code
    if short_code.startswith("de/"):
        short_code = short_code[3:]
    return short_code in content

def get_latest_issue(series_path: str):
    """Finds the latest issue number for a given series path."""
    # E.g., series_path = "nebenreihen/spezial"
    url = f"{LTB_BASE}{series_path}"
    html = fetch_html(url)
    if not html:
        return None
        
    # We look for links matching the series path followed by an issue indicator
    # E.g., /ausgaben/nebenreihen/spezial/band-131 or /ausgaben/alle-ausgaben/ltb-600
    pattern = r'href=[\'"](/ausgaben/' + re.escape(series_path) + r'/(?:band-|ltb-)?(\d+))[\'"]'
    matches = re.findall(pattern, html, re.IGNORECASE)
    
    latest_num = None
    latest_url = None
    for link, num_str in matches:
        num = int(num_str)
        if latest_num is None or num > latest_num:
            latest_num = num
            latest_url = f"https://www.lustiges-taschenbuch.de{link}"
            
    return latest_num, latest_url

def main():
    print("Starting LTB site crawl...")
    
    # Get all series linked from /ausgaben/nebenreihen
    neben_html = fetch_html(f"{LTB_BASE}nebenreihen")
    alle_html = fetch_html(f"{LTB_BASE}alle-ausgaben")
    
    all_links = set(re.findall(r'href=[\'"](/ausgaben/[^\'"]+)[\'"]', neben_html + alle_html))
    
    series_paths = set()
    for link in all_links:
        # e.g., /ausgaben/nebenreihen/spezial
        path = link.replace("/ausgaben/", "")
        # Remove any specific issue part like /band-131
        path = re.sub(r'/(?:band-|ltb-)\d+$', '', path)
        series_paths.add(path)
        
    for path in sorted(series_paths):
        # Find if we have an inducks prefix mapped
        prefix = URL_TO_PREFIX.get(path)
        if not prefix:
            # Let's also check if any pattern starts with this path
            for p_path, p_prefix in URL_TO_PREFIX.items():
                if p_path.startswith(path) or path.startswith(p_path):
                    prefix = p_prefix
                    break
                    
        if not prefix:
            continue
            
        print(f"\nProcessing series: {path} (Inducks: {prefix})")
        latest = get_latest_issue(path)
        if not latest:
            print("  -> No issues found.")
            continue
            
        latest_num, latest_url = latest
        if not latest_num or not latest_url:
            print(f"  -> Could not determine latest issue for {path}. Skipping.")
            continue
            
        issue_code = f"{prefix} {latest_num}"
        print(f"  -> Latest issue: {issue_code}")
        
        if is_fully_indexed_in_inducks(issue_code):
            print("  -> Completely indexed in Inducks. Skipping.")
            continue
            
        if is_issue_in_dedbi(issue_code):
            print("  -> Already in de.dbi. Skipping.")
            continue
            
        print("  -> Missing or incompletely indexed! Generating DBI skeleton...")
        html = fetch_html(latest_url)
        if not html:
            continue
            
        cover_title, issue_date, stories = _parse_stories(html)
        
        # Generator expects issue path with prefix like de/LTBSP 131
        info = {
            "issue_path": issue_code,
            "url": latest_url,
            "title": cover_title or f"{prefix.split('/')[-1]} {latest_num}",
            "name": cover_title or f"{prefix.split('/')[-1]} {latest_num}",
            "date": issue_date,
            "stories": stories,
            # We don't have price easily without Egmont, but we can generate a skeleton
            "price": None,
            "pages": 256,
            "size": None,
            "ean": None,
            "isstrans": None
        }
        
        # Change cwd to the root of the project before running generate_dbi_skeleton
        # since it uses os.makedirs("issues", exist_ok=True)
        old_cwd = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        generate_dbi_skeleton(info, "de")
        os.chdir(old_cwd)

if __name__ == "__main__":
    main()
