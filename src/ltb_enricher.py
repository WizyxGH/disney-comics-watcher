"""
ltb_enricher.py
===============
Scrapes story metadata (title, Inducks story code, page count) from
lustiges-taschenbuch.de and injects it into a publication info dict
before DBI generation.

To add a new LTB sub-series, simply add an entry to LTB_URL_PATTERNS:
    "de/<INDUCKS_CODE>": "<path_template_on_ltb_de>/{num}"
"""
import re
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration – extend here to support new sub-series
# ---------------------------------------------------------------------------
LTB_BASE = "https://www.lustiges-taschenbuch.de/ausgaben/"
LTB_DEFAULT_PAGES = 256  # used to estimate last story length

LTB_URL_PATTERNS: dict[str, str] = {
    "de/LTB":    "alle-ausgaben/ltb-{num}",
    "de/ENT":    "nebenreihen/enthologien/band-{num}",
    "de/EIB":    "nebenreihen/entenhausener-ikonen/band-{num}",
    "de/LTBWE":  "nebenreihen/weihnachtsgeschichten/band-{num}",
    "de/LTBYC":  "nebenreihen/ltb-young-comics/band-{num}",
    "de/MMLC":   "nebenreihen/micky-maus-legacy-collection/band-{num}",
    "de/LTBBA":  "nebenreihen/ltb-camping/band-{num}",
}

# Regex matching any known Inducks story code prefix:
#   Italian:  I XX 1234-5
#   Danish:   D 2025-078
#   American: W XX 1234-56
#   German:   D XXXX YYYY
_STORY_CODE_RE = re.compile(
    r'Code:\s*'
    r'((?:[A-Z]{1,2}\s+)?[A-Z]{1,4}\s+[\w\-]+)',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_ltb_url(issue_path: str) -> str | None:
    """Return the lustiges-taschenbuch.de URL for a given Inducks issue path, or None."""
    # Sort prefixes by length descending so "de/LTBBA" matches before "de/LTB"
    for pub_prefix in sorted(LTB_URL_PATTERNS.keys(), key=len, reverse=True):
        url_tpl = LTB_URL_PATTERNS[pub_prefix]
        if issue_path.startswith(pub_prefix):
            m = re.search(r'\s+(\d+)$', issue_path)
            if m:
                return LTB_BASE + url_tpl.format(num=m.group(1))
    return None


def _parse_issue_title(soup) -> str | None:
    """Extract the issue subtitle (e.g. 'Strandgetümmel') from the h1 heading."""
    h1 = soup.find('h1')
    if not h1:
        return None
    text = h1.get_text(separator=' ', strip=True)
    # h1 format: "Nr. 613 Lustiges Taschenbuch - Strandgetümmel"
    m = re.search(r'-\s+(.+)$', text)
    return m.group(1).strip() if m else None


def _parse_issue_date(soup) -> str | None:
    """Extract the issue publication date from the time tag."""
    time_tag = soup.find('time', class_='datetime')
    if time_tag and time_tag.has_attr('datetime'):
        # Format is '2026-07-28T12:00:00Z', we just want '2026-07-28'
        m = re.match(r'(\d{4}-\d{2}-\d{2})', time_tag['datetime'])
        if m:
            # We can format it as 'DD/MM/YYYY' so the generator understands it,
            # or the generator will handle YYYY-MM-DD.
            # Generator uses parse_date_fr which handles DD/MM/YYYY.
            y, m_str, d = m.group(1).split('-')
            return f"{d}/{m_str}/{y}"
    return None

def _parse_stories(html: str) -> tuple[str | None, str | None, list[dict]]:
    """Parse both the issue subtitle, publication date, and story list from a lustiges-taschenbuch.de page."""
    soup = BeautifulSoup(html, 'html.parser')
    cover_title = _parse_issue_title(soup)
    issue_date = _parse_issue_date(soup)
    stories = []

    for chapter in soup.find_all('tr', class_='toc-chapter'):
        story: dict = {}

        # Title
        title_elem = chapter.find('i', class_='toc-title')
        if title_elem:
            story['title'] = title_elem.text.strip()

        # Inducks story code (from the collapsed accordion content)
        content_div = chapter.find('div', class_='accordion-content')
        if content_div:
            text = content_div.get_text(separator=' ')
            m = _STORY_CODE_RE.search(text)
            if m:
                story['story_code'] = m.group(1).strip()
            pages_match = re.search(r'Seitenanzahl:\s*(\d+)', text)
            if pages_match:
                story['pages'] = int(pages_match.group(1))

        # Starting page number (extracted from preview image URL)
        img_link = chapter.find('link', itemprop='image')
        if img_link and img_link.has_attr('href'):
            m = re.search(r'_0*(\d+)\.jpg', img_link['href'])
            if m:
                story['start_page'] = int(m.group(1))

        stories.append(story)

    # Calculate page counts from consecutive start pages if not already found
    for i, story in enumerate(stories):
        if 'pages' in story:
            continue
        if 'start_page' not in story:
            continue
        if i + 1 < len(stories) and 'start_page' in stories[i + 1]:
            story['pages'] = stories[i + 1]['start_page'] - story['start_page']
        else:
            story['pages'] = LTB_DEFAULT_PAGES - story['start_page'] + 1

    return cover_title, issue_date, stories


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_ltb_metadata(info: dict) -> dict:
    """
    Given an info dict with a resolved 'issue_path' key (e.g. 'de/LTB 613'),
    fetch the full story list from lustiges-taschenbuch.de and inject it as
    info['stories'].  Returns the (mutated) dict unchanged if not applicable.
    """
    issue_path = info.get('issue_path', '')
    url = info.get('url')
    if not url or "lustiges-taschenbuch.de" not in url:
        url = _build_ltb_url(issue_path)
    if not url:
        return info

    print(f"  [LTB] Fetching story list: {url}")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        cover_title, issue_date, stories = _parse_stories(r.text)
        if stories:
            info['stories'] = stories
            last_story = stories[-1]
            if 'start_page' in last_story and 'pages' in last_story:
                info['pages'] = last_story['start_page'] + last_story['pages'] - 1
            else:
                info['pages'] = LTB_DEFAULT_PAGES
            if cover_title:
                info['name'] = cover_title
            if issue_date:
                info['date'] = issue_date
            print(f"  [LTB] Found {len(stories)} stories.")
        else:
            print(f"  [LTB] No stories found (page structure may have changed).")
    except Exception as e:
        print(f"  [LTB] Could not fetch story list: {e}")

    return info
