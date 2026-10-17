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
    the number is lost: Inducks pads some series with two or three spaces.
    """
    parts = slug.split("-")
    i = 0
    while i < len(parts) - 1 and parts[i].isalpha():
        i += 1
    if i == 0:
        return [slug.upper()]
    prefix = " ".join(parts[:i]).upper()
    number = "-".join(parts[i:]).upper()
    return [prefix + " " * n + number for n in (1, 2, 3)]


def _resolve_storycodes(slugs: list[str]) -> dict[str, str]:
    """Maps each story slug to the Inducks code the database confirms, or "".

    Nothing is guessed: the site also splits serials into codes of its own
    ('ip-3681-a' is part 1 of I TL 3681-1P), which no spelling rule recovers.
    """
    candidates = {s: _storycode_candidates(s) for s in slugs}
    known = set()
    every = [c for cands in candidates.values() for c in cands]
    if every:
        try:
            from src.db import query_db
            marks = ",".join("?" * len(every))
            rows = query_db(f"SELECT storycode FROM inducks_story WHERE storycode IN ({marks})", tuple(every))
            known = {r[0] for r in rows or []}
        except Exception as e:
            print(f"  [warn] FI story code lookup failed: {e}")
    codes = {s: next((c for c in cands if c in known), "") for s, cands in candidates.items()}
    unknown = [s for s, c in codes.items() if not c and not s.startswith(_COVER_TITLE)]
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
            "url": f"{AKUANKKA_SITE_BASE}/lehti/{slug}",
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
    data = _get_issue(url.rstrip("/").rsplit("/", 1)[-1])
    if not data:
        return {}

    entries = data.get("stories") or []
    codes = _resolve_storycodes([e["slug_story"] for e in entries])
    details: dict = {"page_positions_unknown": True}

    stories = []
    for i, entry in enumerate(entries):
        code = codes[entry["slug_story"]]
        if i == 0 and entry.get("title", "").strip().lower() == _COVER_TITLE:
            if code:
                details["cover_code"] = code
        else:
            stories.append({"title": entry.get("title", ""), "story_code": code,
                            "pages": entry.get("page_count") or ""})
    if stories:
        details["stories"] = stories
    return details
