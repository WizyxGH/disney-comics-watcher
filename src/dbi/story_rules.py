"""Rules of the shared inducks-dbi package on the watcher's Inducks database (src.db): story
rules (serial parts, strips per page, codes an equivalent issue prints) and the image lookups
(reprinted cover, story from its first page)."""
from collections import Counter
import re
import unicodedata
from inducks_dbi.covers import find_cover_code as _find_cover_code, find_story_code as _find_story_code
import inducks_dbi.story_rules as _idbi_story_rules
from inducks_dbi.story_rules import apply_story_rules as _apply_story_rules

from src.db import query_db

_orig_part_lengths = _idbi_story_rules.part_lengths

def _enhanced_part_lengths(query, code: str, total: int) -> list[int] | None:
    lengths = _orig_part_lengths(query, code, total)
    if lengths:
        return lengths
    # Cross-issue fallback: When a story originally ran across multiple weekly issues
    # (e.g. Topolino 3086, 3087, 3088, 3089), each issue only contains one part.
    # We aggregate the agreed page counts per part number across all issues.
    try:
        rows = query(
            "SELECT e.part, sv.entirepages FROM inducks_entry e "
            "JOIN inducks_storyversion sv ON sv.storyversioncode = e.storyversioncode "
            "WHERE sv.storycode = ? AND e.part != ''", (code,)
        )
        by_part: dict[int, Counter] = {}
        for part, pages in rows or []:
            try:
                p_num = int(str(part).strip())
                p_pages = int(str(pages).strip())
                if p_num > 0 and p_pages > 0:
                    by_part.setdefault(p_num, Counter())[p_pages] += 1
            except (ValueError, TypeError):
                continue

        if by_part:
            max_p = max(by_part.keys())
            if sorted(by_part.keys()) == list(range(1, max_p + 1)) and max_p > 1:
                candidate = [by_part[p].most_common(1)[0][0] for p in range(1, max_p + 1)]
                if sum(candidate) == total and all(candidate):
                    return candidate
    except Exception:
        pass
    return None

_idbi_story_rules.part_lengths = _enhanced_part_lengths


def _query(sql, params=()):
    return query_db(sql, params)


_CHAR_PREFIX_CACHE: dict[str, list[tuple[str, str]]] = {}


def _fold_upper(text: str) -> str:
    """Uppercase + accent-folded string for case/diacritic-insensitive prefix matching."""
    nfd = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").upper()


def _load_character_prefixes(language_code: str | None) -> list[tuple[str, str]]:
    """Loads (FOLDED_UPPER_NAME, charactercode) sorted longest-first from inducks_charactername."""
    key = language_code or "*"
    if key in _CHAR_PREFIX_CACHE:
        return _CHAR_PREFIX_CACHE[key]
    try:
        has_table = _query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='inducks_charactername'")
        if not has_table:
            return []
        if language_code:
            rows = _query(
                "SELECT charactername, charactercode FROM inducks_charactername WHERE languagecode = ?",
                (language_code,),
            ) or []
        else:
            rows = _query("SELECT charactername, charactercode FROM inducks_charactername") or []
    except Exception:
        return []
    pairs = []
    seen = set()
    for name, code in rows:
        n = _fold_upper((name or "").strip())
        c = (code or "").strip()
        if len(n) >= 3 and c and n not in seen:
            seen.add(n)
            pairs.append((n, c))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    _CHAR_PREFIX_CACHE[key] = pairs
    return pairs


def strip_hero_prefix(
    text: str,
    language_code: str | None = None,
    extra_prefixes: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """Strips a leading hero/character name using Inducks ``inducks_charactername`` (and optional
    compound fallbacks), returning ``(stripped_title, character_code)``."""
    cleaned = (text or "").strip()
    upper = _fold_upper(cleaned)
    candidates: list[tuple[str, str | None]] = [(_fold_upper(p), None) for p in extra_prefixes if p]
    candidates.extend(_load_character_prefixes(language_code))
    candidates.sort(key=lambda p: len(p[0]), reverse=True)
    for prefix, code in candidates:
        if upper.startswith(prefix + " "):
            rest = cleaned[len(prefix):].strip(" :-–—")
            if len(rest) >= 3:
                return rest, code
    return cleaned, None


def resolve_stories_by_title(stories: list[dict], log=print) -> None:
    """Fills empty ``story_code`` (and ``pages``) from ``inducks_story.title`` when available."""
    try:
        cols = _query("PRAGMA table_info(inducks_story)") or []
        if not any(r[1] == "title" for r in cols):
            return
    except Exception:
        return
    for s in stories:
        if s.get("story_code"):
            continue
        title = (s.get("title") or "").strip()
        if not title:
            continue
        rows = _query(
            "SELECT s.storycode, sv.entirepages "
            "FROM inducks_story s "
            "LEFT JOIN inducks_storyversion sv ON sv.storycode = s.storycode "
            "WHERE LOWER(s.title) = LOWER(?) "
            "ORDER BY CASE WHEN sv.entirepages IS NOT NULL AND sv.entirepages <> '' THEN 0 ELSE 1 END "
            "LIMIT 1",
            (title,),
        )
        if rows and rows[0]:
            s["story_code"] = rows[0][0]
            if not s.get("pages") and rows[0][1]:
                try:
                    s["pages"] = int(rows[0][1])
                except (ValueError, TypeError):
                    pass


def apply_story_rules(stories: list[dict], log=print) -> list[dict]:
    return _apply_story_rules(stories, _query, log=log)


def _fetch(url: str) -> bytes | None:
    from src.utils import fetch_image_bytes
    fetched = fetch_image_bytes(url, timeout=60)
    return fetched[0] if fetched else None


def find_story_codes(stories: list[dict], issue_path: str = "", log=print) -> None:
    """Fills empty story codes from the publisher's preview of the story's first page
    (``preview_url``), among issues printing the other stories or stories of the same length."""
    try:
        if not _query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='inducks_entryurl'"):
            return
        known = [s.get("story_code") for s in stories if s.get("story_code")]
        for s in stories:
            url = s.get("preview_url")
            if s.get("story_code") or not url:
                continue
            if re.search(r"_\d{3}\.jpg$", url) and not url.endswith(f"_{int(s.get('start_page') or 0):03d}.jpg"):
                continue
            page = _fetch(url)
            if not page:
                continue
            try:
                code = _find_story_code(_query, page, known, _fetch, own_issue=issue_path,
                                        pages=s.get("pages"), log=log)
            except TypeError:
                code = _find_story_code(_query, page, known, _fetch, own_issue=issue_path, log=log)
            if code and code not in known:
                s["story_code"] = code
                known.append(code)
    except Exception as e:
        log(f"  [page] lookup skipped: {e}")


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
