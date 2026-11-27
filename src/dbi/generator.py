import os
import re
from inducks_dbi.lines import code_and_pages as _code_and_pages

from src.config import SUPPORTED_COUNTRIES
from src.dbi.utils import _format_date_for_dbi, _format_price_for_dbi, sort_dbi_file
from src.dbi.mappers import (
    resolve_magazine_metadata, resolve_us_metadata, resolve_de_metadata, 
    resolve_gr_metadata, resolve_glenat_metadata, resolve_it_metadata, resolve_br_metadata,
    resolve_eg_metadata, resolve_bg_metadata, resolve_hr_metadata, resolve_ee_metadata, resolve_lv_metadata, resolve_lt_metadata, resolve_pl_metadata, resolve_cz_metadata, resolve_rs_metadata, resolve_si_metadata, resolve_cn_metadata, resolve_dk_metadata, resolve_es_metadata, resolve_fi_metadata, resolve_is_metadata, resolve_no_metadata, resolve_nl_metadata, resolve_uk_metadata, resolve_se_metadata,
    resolve_mx_metadata, resolve_tr_metadata
)

_RESOLVERS = {
    "us":       resolve_us_metadata,
    "de":       resolve_de_metadata,
    "gr":       resolve_gr_metadata,
    "it":       resolve_it_metadata,
    "br":       resolve_br_metadata,
    "eg":       resolve_eg_metadata,
    "bg":       resolve_bg_metadata,
    "hr":       resolve_hr_metadata,
    "ee":       resolve_ee_metadata,
    "lv":       resolve_lv_metadata,
    "lt":       resolve_lt_metadata,
    "pl":       resolve_pl_metadata,
    "cz":       resolve_cz_metadata,
    "rs":       resolve_rs_metadata,
    "si":       resolve_si_metadata,
    "cn":       resolve_cn_metadata,
    "dk":       resolve_dk_metadata,
    "es":       resolve_es_metadata,
    "fi":       resolve_fi_metadata,
    "is":       resolve_is_metadata,
    "no":       resolve_no_metadata,
    "nl":       resolve_nl_metadata,
    "uk":       resolve_uk_metadata,
    "se":       resolve_se_metadata,
    "mx":       resolve_mx_metadata,
    "tr":       resolve_tr_metadata,
    "glenat":   resolve_glenat_metadata,
    # magazine needs overrides -> handled separately
}

def _get_preindexed_metadata(issue_path: str) -> dict | None:
    from src.db import query_db
    try:
        cols = {c[1] for c in (query_db("PRAGMA table_info(inducks_issue)") or [])}
        if "title" not in cols:
            return None
    except Exception:
        return None
    clean_path = issue_path.strip()
    pub_code = clean_path.split(" ")[0] if " " in clean_path else clean_path
    num_part = clean_path.split(" ", 1)[1].strip() if " " in clean_path else ""
    no_space = clean_path.replace(" ", "")

    rows = query_db(
        "SELECT issuecode, title, size, pages, price, oldestdate, filledoldestdate, maintenanceteamcode "
        "FROM inducks_issue "
        "WHERE issuecode = ? OR issuecode = ? OR (publicationcode = ? AND issuenumber = ?)",
        (clean_path, no_space, pub_code, num_part)
    )
    if not rows:
        return None

    r = rows[0]
    matched_issuecode = r[0]
    existing = {
        "issuecode": matched_issuecode,
        "title": r[1] or "",
        "size": r[2] or "",
        "pages": r[3] or "",
        "price": r[4] or "",
        "oldestdate": r[5] or r[6] or "",
        "inx": r[7] or "",
        "isstrans": None,
        "cover_code": None,
        "cover_hero": None,
        "cover_title": None,
    }

    try:
        job_rows = query_db(
            "SELECT personcode, inxtransletcol FROM inducks_issuejob WHERE issuecode = ?",
            (matched_issuecode,)
        )
        for j_person, j_col in (job_rows or []):
            if j_col == 't' and j_person:
                existing["isstrans"] = j_person
            elif j_col == 'x' and j_person and not existing["inx"]:
                existing["inx"] = j_person
    except Exception:
        pass

    try:
        entry_rows = query_db(
            "SELECT entrycode, storyversioncode, position, title, reallytitle, printedhero "
            "FROM inducks_entry "
            "WHERE issuecode = ? AND (position = 'a' OR position = '' OR entrycode LIKE ?)",
            (matched_issuecode, f"{matched_issuecode}a")
        )
        if entry_rows:
            for er in entry_rows:
                pos = er[2]
                ecode = er[0]
                if pos == 'a' or ecode.endswith('a'):
                    existing["cover_code"] = er[1] or ""
                    existing["cover_title"] = er[3] or ""
                    existing["cover_hero"] = er[5] or ""
                    if existing["cover_code"] and not existing["cover_hero"]:
                        app_rows = query_db(
                            "SELECT charactercode FROM inducks_appearance WHERE storyversioncode = ? AND charactercode != '' LIMIT 1",
                            (existing["cover_code"],)
                        )
                        if app_rows:
                            existing["cover_hero"] = app_rows[0][0]
                    break
    except Exception:
        pass

    return existing


def _sanitize_bolderbast(text: str) -> str:
    if not text: return ""
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("…", "...")
    return text


def _inedit_cover_code(issue_path: str, dbi_issue_code: str) -> str:
    """Builds the standard Inducks cover storycode for an unpublished (inédit) cover
    (e.g. 'FC PM  598', 'IC TL 3701', 'GC MMB 650')."""
    if not issue_path or "/" not in issue_path:
        return "?"
    country, rest = issue_path.split("/", 1)
    short = rest.split()[0] if rest else ""
    full_pub = f"{country}/{short}" if short else ""

    prefix = None
    if full_pub:
        try:
            rows = query_db(
                "SELECT DISTINCT substr(sv.storycode, 1, 2) "
                "FROM inducks_entry e "
                "JOIN inducks_storyversion sv ON e.storyversioncode = sv.storyversioncode "
                "JOIN inducks_issue i ON e.issuecode = i.issuecode "
                "WHERE i.publicationcode = ? AND e.position = 'a' "
                "AND length(sv.storycode) >= 3 AND substr(sv.storycode, 2, 2) = 'C '",
                (full_pub,),
            ) or []
            prefixes = [r[0] for r in rows if r and r[0]]
            if len(prefixes) == 1:
                prefix = prefixes[0]
        except Exception:
            pass

    if not prefix:
        prefix = {
            "fr": "FC", "it": "IC", "nl": "HC", "de": "DC",
            "br": "BC", "es": "EC", "gr": "GC", "pl": "PC", "tr": "TC",
        }.get(country.lower(), f"{country[0].upper()}C" if country else "IC")

    return f"{prefix} {dbi_issue_code}"


def _format_cover_line(info: dict, issue_path: str, dbi_issue_code: str, isslet_val: str) -> str:
    """Formats the Bolderbast cover entry line ('a') with cover code, credits, and [xapp:...] if inédit."""
    cover_ec = dbi_issue_code + "a"
    is_inedit_cover = not info.get("cover_code") or info.get("cover_code") == "?"
    storycode = _inedit_cover_code(issue_path, dbi_issue_code) if is_inedit_cover else info["cover_code"]

    storycode_field, pages_field, cover_overflow = _code_and_pages(storycode, "1")
    brokpg = " "
    pagel = "c"

    plot_val, writ_val, art_val, ink_val, hero_val = "", "", "", "", ""
    if info.get("cover_hero"):
        hero_val = info["cover_hero"]
    else:
        for c in info.get("characters", []):
            if c.get("code"):
                hero_val = c["code"]
                break

    if dbi_issue_code.startswith("JM "):
        writ_val, art_val = "FPt", "FPt"

    credits_field = f"  {plot_val[:4].ljust(4)}{writ_val[:4].ljust(4)}{art_val[:4].ljust(4)}{ink_val[:4].ljust(4)}{hero_val[:2].ljust(2)}  "
    if len(cover_ec) <= 12:
        prefix = f"{cover_ec.ljust(12)}{storycode_field}{pages_field}{brokpg}{pagel}{credits_field}"
    else:
        prefix = f"->          {storycode_field}{pages_field}{brokpg}{pagel}{credits_field}"

    cover_title = info.get("cover_title") or ("CV" if cover_ec.endswith("a") else "")
    suffixes = []
    if cover_title:
        suffixes.append(cover_title)
    suffixes += cover_overflow
    if len(cover_ec) > 12:
        suffixes.append(f"[entrycode:{cover_ec}]")

    # Only emit [xapp:...] on unpublished (inédit) covers
    characters = info.get("characters", [])
    if is_inedit_cover and characters:
        xapp_codes = [c["code"] for c in characters if c.get("code")]
        if xapp_codes:
            suffixes.append(f"[xapp:{','.join(xapp_codes)}]")

    if isslet_val:
        suffixes.append(f"[isslet:{isslet_val}]")

    return f"{prefix}{' '.join(suffixes)}".rstrip() + "\n"


def _format_story_lines(stories: list[dict], dbi_issue_code: str, pages_val, positions_known: bool) -> list[str]:
    """Formats the Bolderbast story entry lines for an issue."""
    total_pages = 0
    if pages_val:
        try:
            total_pages = int(str(pages_val).strip())
        except Exception:
            pass

    current_page = 5 if "LTB" in dbi_issue_code else 1
    lines = []
    for i, story in enumerate(stories, start=1):
        start_p = story.get("start_page")
        if start_p is not None:
            current_page = int(start_p)

        page_len_str = str(story.get("pages", "")).strip()
        if positions_known and (page_len_str.isdigit() or start_p is not None):
            pad = 3 if (total_pages >= 100 or current_page >= 100) else 2
            story_ec = f"{dbi_issue_code}p{str(current_page).zfill(pad)}"
            if page_len_str.isdigit():
                current_page += int(page_len_str)
        else:
            story_ec = f"{dbi_issue_code}{chr(97 + i)}"

        story_code = (story.get("story_code", "") or story.get("code", "")).strip() or "?"
        pages_str = str(story.get("pages", "")).strip()
        code_field, pages_field, overflow = _code_and_pages(story_code, pages_str)
        pagel = str(story.get("pagel") or " ")[:1]

        c_hero = ""
        for c in story.get("characters") or []:
            if c.get("code"):
                c_hero = c["code"]
                break
        c_hero = (story.get("hero") or c_hero)[:2].ljust(2)
        st_credits = (
            f"  {str(story.get('plot', ''))[:4].ljust(4)}"
            f"{str(story.get('writ', ''))[:4].ljust(4)}"
            f"{str(story.get('art', ''))[:4].ljust(4)}"
            f"{str(story.get('ink', ''))[:4].ljust(4)}"
            f"{c_hero}  "
        )
        if len(story_ec) <= 12:
            st_prefix = f"{story_ec.ljust(12)}{code_field}{pages_field} {pagel}{st_credits}"
        else:
            st_prefix = f"->          {code_field}{pages_field} {pagel}{st_credits}"

        st_title = _sanitize_bolderbast(story.get("title", "").strip())
        st_suffixes = list(overflow)
        if story.get("part"):
            st_suffixes.append(f"[part:{story['part']}]")
        if len(story_ec) > 12:
            st_suffixes.append(f"[entrycode:{story_ec}]")
        if story.get("characters"):
            c_codes = [c["code"] for c in story["characters"] if c.get("code")]
            if c_codes:
                st_suffixes.append(f"[xapp:{','.join(c_codes)}]")

        lines.append(f"{st_prefix}{st_title} {' '.join(st_suffixes)}".rstrip() + "\n")
    return lines


def generate_dbi_skeleton(info: dict, publication_type: str, overrides: dict | None = None) -> str | None:
    overrides = overrides or {}
    try:
        if publication_type == "magazine":
            data = resolve_magazine_metadata(info, overrides)
        else:
            resolver = _RESOLVERS.get(publication_type, resolve_glenat_metadata)
            data = resolver(info)

        issue_path = data["issue_path"]

        preindexed = _get_preindexed_metadata(issue_path)
        if preindexed:
            if preindexed.get("title"):
                if not data.get("name") or data["name"].rstrip("!") == preindexed["title"].rstrip("!"):
                    data["name"] = preindexed["title"]
            if preindexed.get("price"):
                data["price"] = preindexed["price"]
            if preindexed.get("pages") and preindexed["pages"] not in ("", "0"):
                data["pages"] = preindexed["pages"]
                info["pages_estimated"] = False
            if preindexed.get("size") and not data.get("size"):
                data["size"] = preindexed["size"]
            if preindexed.get("isstrans"):
                data["isstrans"] = preindexed["isstrans"]
            if preindexed.get("oldestdate") and not data.get("date"):
                data["date"] = preindexed["oldestdate"]
            if preindexed.get("cover_code") and (not info.get("cover_code") or info.get("cover_code") == "?"):
                info["cover_code"] = preindexed["cover_code"]
            if preindexed.get("cover_hero") and not info.get("cover_hero"):
                info["cover_hero"] = preindexed["cover_hero"]
            if preindexed.get("cover_title") and not info.get("cover_title"):
                info["cover_title"] = preindexed["cover_title"]
        
        if publication_type == "de":
            try:
                from src.ltb_enricher import enrich_ltb_metadata
                info["issue_path"] = issue_path
                info = enrich_ltb_metadata(info)
                if info.get("name"):
                    data["name"] = info["name"]
                if info.get("date"):
                    data["date"] = info["date"]
                if info.get("pages"):
                    data["pages"] = info["pages"]
                if info.get("price"):
                    data["price"] = info["price"]
                if info.get("stories"):
                    from src.dbi.story_rules import apply_story_rules
                    info["stories"] = apply_story_rules(info["stories"])
            except Exception as e:
                print(f"  [warn] Failed to enrich LTB: {e}")

        if publication_type == "gr":
            try:
                from src.gr_enricher import enrich_gr_metadata
                info["issue_path"] = issue_path
                info = enrich_gr_metadata(info)
                if info.get("date"):
                    data["date"] = info["date"]
                if info.get("pages"):
                    data["pages"] = info["pages"]
                if info.get("price"):
                    data["price"] = info["price"]
                if info.get("stories"):
                    from src.dbi.story_rules import apply_story_rules
                    info["stories"] = apply_story_rules(info["stories"])
            except Exception as e:
                print(f"  [warn] Failed to enrich Greek comic: {e}")

        if info.get("stories"):
            # Global story resolution across all countries: original-title match and first-page dHash.
            try:
                from src.dbi.story_rules import find_story_codes, resolve_stories_by_title
                resolve_stories_by_title(info["stories"])
                find_story_codes(info["stories"], issue_path)
            except Exception as e:
                print(f"  [warn] Story rules failed: {e}")

        detected_cover_chars: list[str] | None = None
        if not info.get("cover_code") and info.get("cover_url"):
            # Detect cover characters once when vision is enabled so cover lookup can use them
            # to disambiguate candidates, and reuse them for xapp if the cover remains inédit.
            if not info.get("characters") and not info.get("_skip_vision"):
                try:
                    from inducks_dbi.vision import detect_cover_characters
                    from src.utils import fetch_image_bytes
                    fetched = fetch_image_bytes(info["cover_url"], timeout=10)
                    if fetched and fetched[0]:
                        detected_cover_chars = detect_cover_characters(fetched[0]) or []
                except Exception as e:
                    print(f"  [warn] Cover vision xapp failed: {e}")
            # Check shared-story covers (dHash + character filter) and global cover embedding index.
            from src.dbi.story_rules import find_cover_code
            info["cover_code"] = find_cover_code(
                info["cover_url"], info.get("stories") or [], issue_path, cover_chars=detected_cover_chars
            )

        # If the cover is still unpublished (inédit), attach xapp characters detected via vision
        if (not info.get("cover_code") or info.get("cover_code") == "?") and not info.get("characters") and info.get("cover_url") and not info.get("_skip_vision"):
            if detected_cover_chars is None:
                try:
                    from inducks_dbi.vision import detect_cover_characters
                    from src.utils import fetch_image_bytes
                    fetched = fetch_image_bytes(info["cover_url"], timeout=10)
                    if fetched and fetched[0]:
                        detected_cover_chars = detect_cover_characters(fetched[0])
                except Exception as e:
                    print(f"  [warn] Cover vision xapp failed: {e}")
            if detected_cover_chars:
                info["characters"] = [{"code": c} for c in detected_cover_chars]
                
        if preindexed:
            if preindexed.get("title"):
                data["name"] = preindexed["title"]
            if preindexed.get("price"):
                data["price"] = preindexed["price"]
            if preindexed.get("pages") and preindexed["pages"] not in ("", "0"):
                data["pages"] = preindexed["pages"]
                info["pages_estimated"] = False
            if preindexed.get("size") and not data.get("size"):
                data["size"] = preindexed["size"]
            if preindexed.get("isstrans"):
                data["isstrans"] = preindexed["isstrans"]
            if preindexed.get("oldestdate") and not data.get("date"):
                data["date"] = preindexed["oldestdate"]
            if preindexed.get("cover_code") and (not info.get("cover_code") or info.get("cover_code") == "?"):
                info["cover_code"] = preindexed["cover_code"]
            if preindexed.get("cover_hero") and not info.get("cover_hero"):
                info["cover_hero"] = preindexed["cover_hero"]
            if preindexed.get("cover_title") and not info.get("cover_title"):
                info["cover_title"] = preindexed["cover_title"]

        name = _sanitize_bolderbast(data["name"])
        prix_raw = data["price"]
        date_raw = data["date"]
        pages_val = data["pages"]
        size_val = data["size"]
        isstrans = data["isstrans"]
        ean_val = data["ean"]

        issdate = _format_date_for_dbi(date_raw)
        if preindexed and preindexed.get("price"):
            price = preindexed["price"]
        else:
            price = _format_price_for_dbi(prix_raw)

        os.makedirs("issues", exist_ok=True)
        dbi_path = os.path.join("issues", f"{publication_type}.dbi" if publication_type in SUPPORTED_COUNTRIES and publication_type != "fr" else "fr.dbi")

        dbi_issue_code = issue_path
        for country in SUPPORTED_COUNTRIES:
            prefix = f"{country}/"
            if dbi_issue_code.startswith(prefix):
                dbi_issue_code = dbi_issue_code[3:]
                break

        # An issue code needs a number: "BIG" or "fr/UNK" alone would be an
        # entry for a whole publication, which no reviewer can place. "UNK_<id>"
        # carries the shop's product id, not an issue number: same thing.
        if not re.search(r"\d", dbi_issue_code) or dbi_issue_code.startswith("UNK"):
            print(f"  [DBI] Skipped: no Inducks issue found for {info.get('title')!r} ({issue_path})")
            return None

        isslet_val = None
        if dbi_issue_code.startswith("JM "):
            if not pages_val: pages_val = 116
            isslet_val = "B.L.A.C.K Studio"

        fields = []
        if issdate: fields.append(f"[issdate:{issdate}]")
        if price: fields.append(f"[price:{price}]")
        # A page count worked out from the last story is a lower bound, not the issue's count.
        if pages_val and not info.get("pages_estimated"): fields.append(f"[pages:{pages_val}]")
        if size_val: fields.append(f"[size:{size_val}]")
        if ean_val: fields.append(f"[EAN {ean_val}]")

        
        if info.get("stories"):
            fields.append("[inx:FGK,-]")
        else:
            fields.append("[inx:-]")
        if isstrans: fields.append(f"[isstrans:{isstrans}]")

        # Bolderbast DBI spec: position 1..12 is issue code or '->          ' with [entrycode:xx]
        if len(dbi_issue_code) <= 12:
            issue_code_field = dbi_issue_code.ljust(12)
        else:
            issue_code_field = "->          "
            fields.append(f"[entrycode:{dbi_issue_code}]")

        fields_str = " ".join(fields)
        title_part = f"{name} {fields_str}".strip()

        # Bolderbast DBI spec: 'h' must be exactly on position 14
        h3_line = f"{issue_code_field} h3 {title_part}\n"
        cover_line = _format_cover_line(info, issue_path, dbi_issue_code, isslet_val)

        body_parts = [h3_line, cover_line]
        stories = info.get("stories", [])
        if stories:
            body_parts.extend(_format_story_lines(
                stories,
                dbi_issue_code,
                pages_val,
                positions_known=not info.get("page_positions_unknown"),
            ))

        content = "".join(body_parts)
        with open(dbi_path, "a", encoding="utf-8") as f:
            f.write(content)
        print(f"  [DBI] Entry added to {dbi_path} ({issue_path})")
        sort_dbi_file(dbi_path)
        return content

    except Exception as e:
        print(f"  [warn] Unable to generate DBI skeleton: {e}")
        return None
