"""
gr_enricher.py
==============
Extracts and enriches story metadata for Greek Disney comics published by
Kathimerini (Μίκυ Μάους, Κόμιξ, Ντόναλντ, Super Μίκυ, Editor's Choice) using official article
announcements and PressReader CDN assets.
"""

import os
import re
import unicodedata
import urllib.parse
from bs4 import BeautifulSoup

from src.db import query_db

PRESSREADER_CIDS = {
    "gr/MMB": "464B",  # Μίκυ Μάους
    "gr/KXB": "464D",  # Κόμιξ
    "gr/NTB": "464A",  # Ντόναλντ
    "gr/SMB": "464C",  # Super Μίκυ
    "gr/ECA": "464E",  # Editor's Choice
    "gr/ECCD": "464E", # Editor's Choice
}

PRESSREADER_SLUGS = {
    "gr/MMB": "miky-maous",
    "gr/KXB": "komix",
    "gr/NTB": "donald",
    "gr/SMB": "super-miky",
    "gr/ECA": "editors-choice",
    "gr/ECCD": "editors-choice",
}


def get_pressreader_cover_url(issue_path: str, height: int = 1200) -> str | None:
    """Returns the high-resolution PressReader cover URL for a Greek issue."""
    pub_code = issue_path.split()[0] if issue_path else ""
    cid = PRESSREADER_CIDS.get(pub_code)
    if not cid:
        for prefix, c in PRESSREADER_CIDS.items():
            if issue_path.startswith(prefix):
                cid = c
                break
    if cid:
        return f"https://i.prcdn.co/img?cid={cid}&page=1&height={height}"
    return None


def fetch_pressreader_issue_manifest(cid: str, slug: str = "miky-maous", session=None) -> dict | None:
    """
    Fetches the complete issue manifest from PressReader for a Greek magazine:
    - Obtains guest bearer token
    - Queries IssueInfo (total page count, issue key, publication date)
    - Queries PageKeys to unlock HD previews (pages 1-4)
    - Assembles the optimal URL for all pages (HD 1200px for preview pages, scale=55 for interior pages)
    """
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://disneymagazinesbykathimerini.pressreader.com",
        "Referer": "https://disneymagazinesbykathimerini.pressreader.com/",
    }

    try:
        s = session or requests.Session()
        s.headers.update(headers)

        # 1. Initialize anonymous bearer token
        auth_resp = s.post(
            "https://disneymagazinesbykathimerini.pressreader.com/authentication/v1/initialize",
            json={"tickets": [], "language": "el-GR", "url": f"https://disneymagazinesbykathimerini.pressreader.com/{slug}"},
            timeout=8
        )
        if auth_resp.status_code != 200:
            return None
        token = auth_resp.json().get("bearerToken")
        if not token:
            return None

        s.headers["Authorization"] = f"Bearer {token}"

        # 2. Get Issue Info
        info_resp = s.get(
            f"https://ingress.pressreader.com/services/IssueInfo/GetIssueInfoByCid?cid={cid.lower()}",
            timeout=8
        )
        if info_resp.status_code != 200:
            return None

        issue_data = info_resp.json()
        issue_info = issue_data.get("Issue", {})
        issue_key = issue_info.get("Issue")
        total_pages = issue_data.get("Pages") or 100
        issue_date = issue_info.get("IssueDate")

        # 3. Get Preview PageKeys (pages 1 to 4)
        preview_tickets = {}
        if issue_key:
            pk_resp = s.get(
                f"https://ingress.pressreader.com/services/IssueInfo/GetPageKeys?issue={issue_key}&pageNumber=0&preview=true",
                timeout=8
            )
            if pk_resp.status_code == 200:
                pks = pk_resp.json().get("PageKeys", [])
                for pk in pks:
                    p_num = pk.get("PageNumber")
                    p_key = pk.get("Key")
                    if p_num and p_key:
                        preview_tickets[p_num] = p_key

        # 4. Generate optimal URL for every page from 1 to total_pages
        pages_manifest = {}
        for p in range(1, total_pages + 1):
            if p in preview_tickets:
                ticket_enc = urllib.parse.quote(preview_tickets[p], safe="")
                pages_manifest[p] = {
                    "page": p,
                    "url": f"https://i.prcdn.co/img?file={issue_key}&page={p}&height=1200&ticket={ticket_enc}",
                    "is_hd": True,
                    "resolution": "1200px"
                }
            elif p == 1:
                pages_manifest[p] = {
                    "page": p,
                    "url": f"https://i.prcdn.co/img?cid={cid}&page=1&height=1200",
                    "is_hd": True,
                    "resolution": "1200px"
                }
            else:
                pages_manifest[p] = {
                    "page": p,
                    "url": f"https://i.prcdn.co/img?cid={cid}&page={p}&scale=55",
                    "is_hd": False,
                    "resolution": "330px"
                }

        cover_url = pages_manifest.get(1, {}).get("url") or f"https://i.prcdn.co/img?cid={cid}&page=1&height=1200"
        summary_url = pages_manifest.get(3, {}).get("url")

        return {
            "cid": cid,
            "slug": slug,
            "issue_key": issue_key,
            "issue_date": issue_date,
            "total_pages": total_pages,
            "cover_url": cover_url,
            "summary_page_url": summary_url,
            "pages": pages_manifest
        }
    except Exception as e:
        print(f"  [warn] Failed to fetch PressReader manifest for {cid}: {e}")
        return None


def parse_kathimerini_stories(html_or_soup) -> list[dict]:
    """
    Parses story items from a Kathimerini Disney announcement article.
    Handles two layouts:
      1. Komix layout: Greek Title English Title: Credits (Writer, Artist)
      2. Numbered layout: [PageNum] [Character/Hero] [Story Title]
    """
    if isinstance(html_or_soup, str):
        soup = BeautifulSoup(html_or_soup, "html.parser")
    else:
        soup = html_or_soup

    stories = []
    paragraphs = []
    for p in soup.find_all("p"):
        text = unicodedata.normalize("NFKD", p.get_text()).strip()
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            paragraphs.append(text)

    # 1. Try Komix format: "ΕΝΑ ΜΩΡΟ ΓΙΑ ΔΥΟ Two Men and a Baby: Μια ιστορία του David Gerstein, από το πενάκι του Vicar"
    for text in paragraphs:
        m_k = re.search(r"^([Α-ΩΆ-Ώ0-9\s'’]+?)\s+([A-Za-z0-9\s,'’\-?!]+?):\s*(.*)", text)
        if m_k:
            greek_title = m_k.group(1).strip()
            english_title = m_k.group(2).strip()
            credits_text = m_k.group(3).strip()
            
            # Avoid matching site navigational paragraphs
            if len(english_title) >= 3 and not english_title.startswith("http"):
                stories.append({
                    "greek_title": greek_title,
                    "title": english_title,
                    "credits_text": credits_text,
                    "format": "komix"
                })

    if stories:
        return stories

    # 2. Try Numbered format: "07 ΤΖΩΝ ΡΟΜΠΑΞ Η ΜΠΑΛΑΝΤΑ ΤΟΥ ΤΖΩΝ ΡΟΜΠΑΞ"
    for text in paragraphs:
        m_num = re.search(r"^(\d{2,3})\s+([Α-Ωα-ωΆ-Ώά-ώ0-9\s&'’\-]+)", text)
        if m_num:
            page_str = m_num.group(1).strip()
            rest = m_num.group(2).strip()
            
            stories.append({
                "start_page": int(page_str),
                "title": rest,
                "format": "numbered"
            })

    return stories


def match_komix_story(story_entry: dict) -> dict:
    """Resolves Inducks storycode, pages, and creators for an Egmont/Komix story by English title."""
    title = story_entry.get("title", "")
    if not title:
        return story_entry

    rows = query_db("""
        SELECT sv.storycode, sv.entirepages, sv.writsummary, sv.artsummary
        FROM inducks_storyversion sv
        WHERE sv.storycode IN (SELECT storycode FROM inducks_story WHERE title = ?)
           OR sv.storyversioncode IN (SELECT storyversioncode FROM inducks_entry WHERE title = ?)
        LIMIT 1
    """, (title, title))

    if rows and rows[0]:
        r = rows[0]
        story_entry["story_code"] = r[0]
        try:
            story_entry["pages"] = int(r[1]) if r[1] else None
        except Exception:
            pass
        story_entry["writ"] = (r[2] or "").strip(",")
        story_entry["art"] = (r[3] or "").strip(",")

    return story_entry


def match_italian_source_issue(stories: list[dict], pub_code: str) -> str | None:
    """
    Attempts to identify which Italian Topolino / Paperino issue is being translated
    by finding candidate Italian stories matching the titles or characters.
    """
    candidates = []
    for s in stories:
        title = s.get("title", "")
        for word in title.split():
            if len(word) > 4:
                rows = query_db("""
                    SELECT issuecode FROM inducks_entry
                    WHERE issuecode LIKE 'it/TL 3%' AND title LIKE ?
                    LIMIT 3
                """, (f"%{word}%",))
                for r in (rows or []):
                    candidates.append(r[0])

    if candidates:
        from collections import Counter
        most_common = Counter(candidates).most_common(1)
        if most_common:
            return most_common[0][0]

    return None


def enrich_gr_metadata(info: dict) -> dict:
    """
    Main enricher function called before Greek DBI generation.
    Enriches info with stories list, pagination, and PressReader HD covers & pages manifest.
    """
    issue_path = info.get("issue_path", "")
    article_html = info.get("article_html") or info.get("raw_html")
    article_url = info.get("url")

    # Fetch article HTML if not already cached
    if not article_html and article_url:
        try:
            from src.utils import get_session
            s = get_session()
            r = s.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                article_html = r.text
        except Exception as e:
            print(f"  [warn] Could not fetch Kathimerini article for enrichment: {e}")

    pub_code = issue_path.split()[0] if issue_path else ""
    cid = PRESSREADER_CIDS.get(pub_code)
    slug = PRESSREADER_SLUGS.get(pub_code, "miky-maous")

    if not cid:
        for prefix, c in PRESSREADER_CIDS.items():
            if issue_path.startswith(prefix):
                cid = c
                slug = PRESSREADER_SLUGS.get(prefix, slug)
                break

    # Fetch complete PressReader manifest (total pages, HD preview tickets, all page URLs)
    manifest = None
    if cid and not info.get("_skip_pressreader_network"):
        manifest = fetch_pressreader_issue_manifest(cid, slug)
        if manifest:
            info["cover_url"] = manifest["cover_url"]
            info["summary_page_url"] = manifest["summary_page_url"]
            info["pages"] = manifest["total_pages"]
            info["pressreader_manifest"] = manifest

    if not info.get("cover_url"):
        pr_cover = get_pressreader_cover_url(issue_path)
        if pr_cover:
            info["cover_url"] = pr_cover

    if not article_html:
        return info

    parsed_stories = parse_kathimerini_stories(article_html)
    if not parsed_stories:
        return info

    # 1. Komix layout
    if parsed_stories[0].get("format") == "komix":
        for s in parsed_stories:
            match_komix_story(s)
        info["stories"] = parsed_stories
        if not info.get("pages"):
            info["pages"] = 100
        return info

    # 2. Numbered layout (Miky Maous, Donald, Super Miky)
    for i in range(len(parsed_stories)):
        current = parsed_stories[i]
        next_p = parsed_stories[i + 1]["start_page"] if i + 1 < len(parsed_stories) else None
        if next_p and current.get("start_page"):
            current["pages"] = next_p - current["start_page"]

    # Try matching Italian source issue if it's Miky Maous
    if "MM" in pub_code:
        source_issue = match_italian_source_issue(parsed_stories, pub_code)
        if source_issue:
            source_rows = query_db("""
                SELECT e.position, e.title, sv.storycode, sv.entirepages, sv.writsummary, sv.artsummary
                FROM inducks_entry e
                LEFT JOIN inducks_storyversion sv ON e.storyversioncode = sv.storyversioncode
                WHERE e.issuecode = ? AND sv.storycode NOT LIKE 'Q%'
            """, (source_issue,))
            if source_rows:
                cover_row = next((r for r in source_rows if r[0] == 'a'), None)
                if cover_row and cover_row[2]:
                    info["cover_code"] = cover_row[2]

    info["stories"] = parsed_stories
    if not info.get("pages"):
        info["pages"] = 132 if "MM" in pub_code else 100

    return info
