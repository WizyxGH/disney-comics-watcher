"""Rules of the shared inducks-dbi package on the watcher's Inducks database (src.db): story
rules (serial parts, strips per page, codes an equivalent issue prints) and the cover lookup."""
from inducks_dbi.covers import find_cover_code as _find_cover_code
from inducks_dbi.story_rules import apply_story_rules as _apply_story_rules

from src.db import query_db


def _query(sql, params=()):
    return query_db(sql, params)


def apply_story_rules(stories: list[dict], log=print) -> list[dict]:
    return _apply_story_rules(stories, _query, log=log)


def _fetch(url: str) -> bytes | None:
    from src.utils import get_session
    try:
        r = get_session().get(url, timeout=60)
        return r.content if r.ok and r.headers.get("content-type", "").startswith("image/") else None
    except Exception:
        return None


def find_cover_code(cover_url: str, stories: list[dict], issue_path: str = "", log=print) -> str | None:
    """Story code of the reprinted cover, or None (new cover, no clear match, or the tables or
    Pillow missing: the cover keeps "?")."""
    try:
        if not _query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='inducks_entryurl'"):
            return None
        cover = _fetch(cover_url)
        if not cover:
            return None
        return _find_cover_code(_query, cover, [s.get("story_code") for s in stories],
                                _fetch, own_issue=issue_path or "", log=log)
    except Exception as e:
        log(f"  [cover] lookup skipped: {e}")
        return None
