"""Inducks button, advanced search query builder, and cvsedit/sendscan link helpers."""
import re
from urllib.parse import quote, quote_plus, urlencode

from src import db as _db
from src.utils import does_issue_exist_in_inducks
from src.dbi.isv_search import _extract_base_and_number

INDUCKS_BUTTONS = ("Search on Inducks", "Search Inducks", "View on Inducks", "View Publication", "View issues")
SKIP_DISTRIBUTOR_PUBLISHERS = (
    "Direct Éditeurs",
    "Disney Magazines",
    "Egmont DE",
    "Lustiges Taschenbuch DE",
    "Beta Kids TR",
)


def inducks_button(issue_path: str | None, raw_title: str, country: str, info: dict | None = None) -> dict:
    """The Inducks button of a release: direct issue/publication link when known,
    otherwise Inducks' advanced search (compmag.php) with cleaned query parameters."""
    info = info or {}
    known = bool(issue_path) and "UNK" not in issue_path and "/" in issue_path
    if known:
        issue_path = re.sub(r"\s+", " ", issue_path.strip())
    if known and not re.search(r"\d", issue_path):
        return {"text": "View issues", "url": f"https://inducks.org/publication.php?c={quote_plus(issue_path)}"}
    if known and does_issue_exist_in_inducks(issue_path):
        return {"text": "View on Inducks", "url": f"https://inducks.org/issue.php?c={quote_plus(issue_path)}"}
    if known:
        publication = re.sub(r"\s+\S+$", "", issue_path.strip())
        if " " not in issue_path.strip():
            publication = re.match(r"^[a-z]+/[A-Za-z]+", issue_path).group(0)
        if _db.query_db("SELECT 1 FROM inducks_publication WHERE publicationcode = ?", (publication,)):
            return {"text": "View Publication", "url": f"https://inducks.org/publication.php?c={quote_plus(publication)}"}

    search_country = "fr" if country in ("fr_kiosk", "magazine", "glenat") else country
    params = {"country": search_country}
    if known:
        pub, _, number = issue_path.split("/", 1)[1].rpartition(" ")
        if not pub:
            pub, number = re.match(r"^([A-Za-z]+)(.*)$", issue_path.split("/", 1)[1]).groups()
        params["title1"], params["entrycodeh3"] = pub.strip(), number.strip()
    else:
        clean_raw = re.sub(r"\s+(?:con|mit|avec)\s+.*$", "", raw_title or "", flags=re.IGNORECASE)
        clean_raw = re.sub(r"\s*[-–:]\s*(?:Tome|Vol\.?|Volume|N°|Nr\.?|#)\s*", " ", clean_raw, flags=re.IGNORECASE)
        base, number = _extract_base_and_number(clean_raw)
        title_q = (base or clean_raw or "").strip(" -–:")
        words = title_q.split()
        if len(words) > 5:
            title_q = " ".join(words[:5])
        params["title1"] = title_q
        if number:
            num_clean = number.lstrip("0") or number
            if not re.match(r"^\d{4}-\d{4}$", num_clean):
                params["entrycodeh3"] = num_clean
    year = re.search(r"\b(19|20)\d{2}\b", str(info.get("date") or info.get("date_mise_en_vente") or ""))
    if year:
        params["date2"] = year.group(0)
    pub_name = info.get("publisher") or info.get("editeur") or info.get("editor")
    if pub_name and pub_name not in SKIP_DISTRIBUTOR_PUBLISHERS:
        params["publisher"] = pub_name
    return {"text": "Search on Inducks", "url": "https://inducks.org/compmag.php?" + urlencode({k: v for k, v in params.items() if v})}


def build_cvsedit_url(issue_path: str) -> str:
    """Builds the Inducks cvsedit.php URL using issuecode and createifneeded=1."""
    encoded_issue = quote(issue_path, safe="/")
    return (
        f"https://inducks.org/cvsedit.php"
        f"?storycode=&issuecode={encoded_issue}&publicationcode=&createifneeded=1&fast=&coazilla="
    )


def _get_inputfilename_for_issue(issue_path: str) -> tuple[str, str | None]:
    from src.db import query_db
    try:
        parts = issue_path.strip().split("/", 1)
        country = parts[0] if len(parts) == 2 else ""
        rest = parts[1] if len(parts) == 2 else parts[0]

        pub = rest.split()[0] if rest else ""
        num = rest.split(None, 1)[1] if len(rest.split()) > 1 else ""
        full_pub = f"{country}/{pub}" if country else pub

        rows = query_db("""
            SELECT inf.path, inf.filename, inf.inputfilecode
            FROM inducks_issue iss
            JOIN inducks_inputfile inf ON iss.inputfilecode = inf.inputfilecode
            WHERE iss.issuecode = ? OR iss.issuecode = ? OR (iss.publicationcode = ? AND iss.issuenumber = ?)
        """, (issue_path, issue_path.replace(" ", ""), full_pub, num))
        if rows and rows[0][0] and rows[0][1]:
            p, fn = rows[0][0].strip("/"), rows[0][1]
            code = str(rows[0][2]) if len(rows[0]) > 2 and rows[0][2] else None
            return f"{p}/{fn}", code

        files = query_db("""
            SELECT DISTINCT inf.path, inf.filename, inf.inputfilecode
            FROM inducks_inputfile inf
            JOIN inducks_issue iss ON iss.inputfilecode = inf.inputfilecode
            WHERE iss.publicationcode = ?
        """, (full_pub,))

        if not files:
            return f"issues/{country}/{pub.lower()}.dbi", None
        if len(files) == 1:
            p, fn = files[0][0].strip("/"), files[0][1]
            code = str(files[0][2]) if len(files[0]) > 2 and files[0][2] else None
            return f"{p}/{fn}", code

        num_clean = re.sub(r"[^0-9]", "", num)
        if num_clean:
            val = int(num_clean)
            range_candidates = []
            for item in files:
                p, fn = item[0], item[1]
                code = str(item[2]) if len(item) > 2 and item[2] else None
                m = re.search(r"(\d+)-(\d+)", fn)
                if m:
                    range_candidates.append((int(m.group(1)), int(m.group(2)), p, fn, code))
            if range_candidates:
                for start, end, p, fn, code in range_candidates:
                    if start <= val <= end:
                        return f"{p.strip('/')}/{fn}", code
                range_candidates.sort(key=lambda x: x[1])
                return f"{range_candidates[-1][2].strip('/')}/{range_candidates[-1][3]}", range_candidates[-1][4]

            thresh_candidates = []
            for item in files:
                p, fn = item[0], item[1]
                code = str(item[2]) if len(item) > 2 and item[2] else None
                m = re.search(r"(\d+)", fn)
                if m:
                    thresh_candidates.append((int(m.group(1)), p, fn, code))
            if thresh_candidates:
                thresh_candidates.sort(key=lambda x: x[0])
                chosen = thresh_candidates[0]
                for t_val, p, fn, code in thresh_candidates:
                    if val >= t_val:
                        chosen = (t_val, p, fn, code)
                return f"{chosen[1].strip('/')}/{chosen[2]}", chosen[3]

        recent = query_db("""
            SELECT inf.path, inf.filename, inf.inputfilecode
            FROM inducks_issue iss
            JOIN inducks_inputfile inf ON iss.inputfilecode = inf.inputfilecode
            WHERE iss.publicationcode = ?
            ORDER BY iss.issuecode DESC LIMIT 1
        """, (full_pub,))
        if recent and recent[0][0] and recent[0][1]:
            code = str(recent[0][2]) if len(recent[0]) > 2 and recent[0][2] else None
            return f"{recent[0][0].strip('/')}/{recent[0][1]}", code

        code = str(files[0][2]) if len(files[0]) > 2 and files[0][2] else None
        return f"{files[0][0].strip('/')}/{files[0][1]}", code
    except Exception as e:
        print(f"  [warn] _get_inputfilename_for_issue: {e}")

    country_fallback = issue_path.split("/", 1)[0] if "/" in issue_path else "misc"
    pub_fallback = (issue_path.split("/", 1)[1] if "/" in issue_path else issue_path).split()[0].lower()
    return f"issues/{country_fallback}/{pub_fallback}.dbi", None
