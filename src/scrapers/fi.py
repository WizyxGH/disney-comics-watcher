"""akuankka.fi (Sanoma): Finnish Disney issues, via the site and its JSON API.

The API answers an issue's table of contents, with story slugs derived from
the Inducks codes, only for the issues the site gives away: the latest one of
each publication, which is exactly what a new release is. Its list endpoint
fails most of the time (500), so issues are found from the home page, whose
"latest issues" rows link them by their numeric id.
"""
import re
import requests

from src.config import AKUANKKA_API_BASE, AKUANKKA_SITE_BASE, AKUANKKA_PUBLICATIONS, HEADERS
from src.utils import get_session

# The cover is the first entry of the table of contents, titled "Kansi".
_COVER_TITLE = "kansi"

FI_HERO_MAP = {
    "aku ankka": "DD",
    "mikki hiiri": "MM",
    "roope ankka": "US",
    "taikaviitta": "PK",
    "pelle peloton": "GY",
    "karhukopla": "BB",
    "hessu": "GO",
    "tupu hupu ja lupu": "HDL",
    "milla magia": "MS",
    "iines ankka": "Daisy",
    "hansu hanhi": "GL",
    "touho ankka": "FE",
    "indiana hopo": "IP",
    "mustakaapu": "PB",
    "superhessu": "SG",
    "pluto": "PL",
    "mummo ankka": "GM",
}

_ARTICLE_PATTERNS = re.compile(
    r"(?:oma-nurkka|artikkeli|toimitus|esittely|haastattelu|kolumni|uutis|puheenaihe|postilaatikko|ankallis)",
    re.IGNORECASE
)
_GAME_PATTERNS = re.compile(
    r"(?:visa|pahkina|pähkinä|tehtava|tehtävä|ristikko|sokkelo)",
    re.IGNORECASE
)


def _get_issue(ref: str) -> dict | None:
    """Issue from the API by numeric id or slug; None when not given away.

    Not the shared session: those issues answer 500, which it would retry.
    """
    try:
        r = requests.get(f"{AKUANKKA_API_BASE}/issues/{ref}", headers=HEADERS, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"  [warn] akuankka.fi issue {ref}: {e}")
        return None


def _issue_path(slug: str) -> str:
    """'fi-aa2026-42' -> 'fi/AA2026-42', 'fi-aatk561' -> 'fi/AATK561'."""
    country, code = slug.split("-", 1)
    return f"{country}/{code.upper()}"


def _storycode_candidates(slug: str) -> list[str]:
    """Inducks codes a story slug can stand for, most likely first.

    The slug lowercases the code and turns every run of spaces into one dash
    ('I PKA  42-1' -> 'i-pka-42-1'), so the gap between the letters prefix and
    the number is lost: Inducks pads some series with up to four spaces.
    """
    parts = slug.split("-")
    i = 0
    while i < len(parts) - 1 and parts[i].isalpha():
        i += 1
    if i == 0:
        return [slug.upper()]
    prefix = " ".join(parts[:i]).upper()
    number = "-".join(parts[i:]).upper()
    return [prefix + " " * n + number for n in (1, 2, 3, 4)]


def _resolve_storycodes(entries: list[dict | str]) -> dict[str, str]:
    """Maps each story entry's slug to its confirmed Inducks code, or "".
    Uses slug candidates, Finnish reprint title matching, and original title lookup."""
    norm_entries: list[dict] = []
    for e in entries:
        if isinstance(e, str):
            norm_entries.append({"slug_story": e})
        elif isinstance(e, dict):
            norm_entries.append(e)
    entries = norm_entries
    slugs = [e.get("slug_story", "") for e in entries]
    candidates = {s: _storycode_candidates(s) for s in slugs if s}
    known = set()
    every = [c for cands in candidates.values() for c in cands]
    
    from src.db import query_db
    if every:
        try:
            marks = ",".join("?" * len(every))
            rows = query_db(f"SELECT storycode FROM inducks_story WHERE storycode IN ({marks})", tuple(every))
            known = {r[0] for r in rows or []}
        except Exception as e:
            print(f"  [warn] FI story code lookup failed: {e}")

    codes = {}
    for entry in entries:
        slug = entry.get("slug_story", "")
        if not slug:
            continue
        cands = candidates.get(slug, [])
        code = next((c for c in cands if c in known), "")
        
        # Fallback 1: Finnish reprint title match in inducks_entry
        title = entry.get("title", "")
        if not code and title and not _ARTICLE_PATTERNS.search(slug) and not _ARTICLE_PATTERNS.search(title):
            try:
                t_rows = query_db(
                    "SELECT DISTINCT storyversioncode FROM inducks_entry "
                    "WHERE languagecode = 'fi' AND LOWER(title) = LOWER(?) AND reallytitle = 'Y' LIMIT 1",
                    (title,)
                )
                if t_rows and t_rows[0][0] and not t_rows[0][0].startswith("Q"):
                    code = t_rows[0][0]
            except Exception:
                pass

        # Fallback 2: Original title match in inducks_story
        orig_title = entry.get("original_title", "")
        if not code and orig_title:
            try:
                o_rows = query_db("SELECT storycode FROM inducks_story WHERE LOWER(title) = LOWER(?) LIMIT 1", (orig_title,))
                if o_rows and o_rows[0][0]:
                    code = o_rows[0][0]
            except Exception:
                pass

        codes[slug] = code

    unknown = [s for s, c in codes.items() if not c and not s.startswith(_COVER_TITLE) and not _ARTICLE_PATTERNS.search(s)]
    if unknown:
        print(f"  [FI] Story codes left blank (unknown to Inducks): {', '.join(unknown)}")
    return codes


def discover_fi():
    """Latest issues of the watched publications, as linked from the home page."""
    try:
        r = get_session().get(f"{AKUANKKA_SITE_BASE}/", timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  [warn] discover_fi: {e}")
        return []

    results = []
    for issue_id in dict.fromkeys(re.findall(r'/lehti/(\d+)"', r.text)):
        issue = _get_issue(issue_id)
        if not issue or issue.get("publication") not in AKUANKKA_PUBLICATIONS:
            continue
        slug = issue["slug"]
        title = issue["text"]
        # Pocket books carry their own title; weeklies only "#42".
        if issue.get("title") and not issue["title"].startswith("#"):
            title += f" - {issue['title']}"
        results.append({
            "id": slug,
            "title": title,
            "url": f"{AKUANKKA_SITE_BASE}/lehti/{issue_id}",
            "issue_path": _issue_path(slug),
            "cover_url": issue.get("listing_image"),
            "date": issue.get("publication_date"),
        })
    return results


def fetch_fi_details(url: str) -> dict:
    """Table of contents of an issue: cover code, then stories with their length.

    Page counts and positions are those of the digital edition, which drops
    pages of the printed one (AATK561: every story sits 2 pages earlier than
    on Inducks), so neither the issue page count nor start pages are given.
    """
    ref = url.rstrip("/").rsplit("/", 1)[-1]
    data = _get_issue(ref)
    if not data:
        return {}

    entries = data.get("stories") or []
    codes = _resolve_storycodes(entries)
    details: dict = {"page_positions_unknown": True}

    from src.db import query_db

    is_pocket = "aatk" in ref.lower() or "taskukirja" in ref.lower() or "pocket" in ref.lower()
    default_pagel = "3" if is_pocket else "4"

    stories = []
    for i, entry in enumerate(entries):
        slug = entry.get("slug_story", "")
        code = codes.get(slug, "")
        title = entry.get("title", "")
        orig_title = entry.get("original_title", "")
        chars = [c.get("name", "") for c in entry.get("main_characters", [])]

        if i == 0 and title.strip().lower() == _COVER_TITLE:
            if code:
                details["cover_code"] = code
            continue

        # Distinguish article, game/puzzle, and comic story
        is_article = False
        is_game = False
        if _ARTICLE_PATTERNS.search(slug) or _ARTICLE_PATTERNS.search(title):
            is_article = True
        elif _GAME_PATTERNS.search(slug) or _GAME_PATTERNS.search(title):
            is_game = True
        elif not orig_title and not chars and not re.match(r'^[a-z]+-\d+', slug):
            is_article = True

        pagel = "a" if is_article else ("g" if is_game else default_pagel)

        # Hero determination
        hero = ""
        if code:
            try:
                h_rows = query_db("SELECT charactercode FROM inducks_herocharacter WHERE storycode = ? LIMIT 1", (code,))
                if h_rows and h_rows[0][0]:
                    hero = h_rows[0][0]
            except Exception:
                pass
        if not hero and chars:
            for ch in chars:
                c_code = FI_HERO_MAP.get(ch.lower())
                if c_code:
                    hero = c_code
                    break

        stories.append({
            "title": title,
            "story_code": "" if is_article else code,
            "pages": entry.get("page_count") or "",
            "pagel": pagel,
            "hero": hero,
        })

    if stories:
        details["stories"] = stories
    return details
