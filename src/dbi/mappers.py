import re
import unicodedata
from src.dbi.isv_search import search_publication_code, _find_issue_by_title

def _build_metadata(issue_path: str | None, name: str, info: dict, ean: str | None = None) -> dict:
    return {
        "issue_path": issue_path,
        "name": name,
        "price": info.get("price") or info.get("prix"),
        "date": info.get("date") or info.get("date_mise_en_vente"),
        "pages": info.get("pages"),
        "size": info.get("size"),
        "isstrans": info.get("isstrans"),
        "ean": ean
    }

DE_MAPPINGS = [
    (re.compile(r'Lustiges Taschenbuch Young Comics (?:Nr\.\s*)?(\d+)', re.IGNORECASE), r'de/LTBYC \1'),
    (re.compile(r'Lustiges Taschenbuch Weihnachtsgeschichten (?:Nr\.\s*)?(\d+)', re.IGNORECASE), r'de/LTBWE \1'),
    (re.compile(r'Micky Maus Magazin (?:Nr\.\s*)?(\d+)', re.IGNORECASE), r'de/MM \1'),
    (re.compile(r'Micky Maus Legacy Collection (?:Nr\.\s*)?(\d+)', re.IGNORECASE), r'de/MMLC \1'),
    (re.compile(r'Lustiges Taschenbuch (?:Nr\.\s*)?(\d+)', re.IGNORECASE), r'de/LTB \1'),
    (re.compile(r'Entenhausener Ikonen (?:0*)?(\d+)', re.IGNORECASE), r'de/EIB \1'),
    (re.compile(r'Enthologien (?:0*)?(\d+)', re.IGNORECASE), r'de/ENT \1'),
]

GR_MAPPINGS = [
    (re.compile(r'Super MIKY\s*(?:#|Nr\.\s*)?(\d+)', re.IGNORECASE), r'gr/SM \1'),
    (re.compile(r'Μίκυ\s+Μάους\s*#(\d+)', re.IGNORECASE), r'gr/MM \1'),
    (re.compile(r'Κόμιξ\s*#(\d+)', re.IGNORECASE), r'gr/KX \1'),
    (re.compile(r'Ντόναλντ\s*#(\d+)', re.IGNORECASE), r'gr/DD \1'),
]

US_MAPPINGS = []

IT_MAPPINGS = [
    (re.compile(r'Topolino\s*(\d+)', re.IGNORECASE), r'it/TL \1'),
    (re.compile(r'Paperinik\s*(\d+)', re.IGNORECASE), r'it/PK \1'),
    (re.compile(r'Zio Paperone\s*(\d+)', re.IGNORECASE), r'it/ZP \1'),
    (re.compile(r'I Classici Disney\s*(\d+)', re.IGNORECASE), r'it/CWD \1'),
]

BR_MAPPINGS = [
    (re.compile(r'Mickey\s*(\d+)', re.IGNORECASE), r'br/MK \1'),
    (re.compile(r'Pato Donald\s*(\d+)', re.IGNORECASE), r'br/PD \1'),
    (re.compile(r'Zé Carioca\s*(\d+)', re.IGNORECASE), r'br/ZC \1'),
    (re.compile(r'Tio Patinhas\s*(\d+)', re.IGNORECASE), r'br/TP \1'),
]

def resolve_magazine_metadata(info, overrides):
    codif   = info.get("codif", "")
    ov      = overrides.get(codif, {})
    inducks = ov.get("inducks")
    numero  = str(info.get("numero") or "").strip()
    name    = ov.get("name") or info.get("site_name") or codif
    
    issue_path = build_inducks_path(inducks, numero) if inducks and numero else None
    if not issue_path:
        issue_path = f"fr/TODO_{codif} {numero}"
    return _build_metadata(issue_path, name, info)

def resolve_us_metadata(info):
    title = info.get("title", "US Comic")
    sku   = str(info.get("sku") or info.get("id") or "TODO")
    
    issue_path = None
    for pattern, repl in US_MAPPINGS:
        m = pattern.search(title)
        if m:
            issue_path = m.expand(repl)
            break
            
    if not issue_path:
        issue_path = search_publication_code(title, "us")
        
    if not issue_path:
        issue_path = f"us/US_{sku[-6:]}"
        
    return _build_metadata(issue_path, title, info)

def resolve_de_metadata(info):
    title = info.get("title", "DE Comic")
    book_id = str(info.get("id") or "TODO")
    clean_id = book_id.split('/')[-1]

    # 1. DB lookup first (exact / contains / fuzzy)
    issue_path = search_publication_code(title, "de")

    # 2. Regex fallback for very well-known series (faster, no DB needed)
    if not issue_path:
        for pattern, repl in DE_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    # 3. Generic acronym fallback
    if not issue_path:
        m = re.search(r'([A-Za-z\s\.]+)(?:Nr\.\s*|0*)?(\d+)', title)
        if m:
            text_part, num_part = m.group(1).strip(), m.group(2)
            acronym = "".join([w[0].upper() for w in text_part.split() if w and w[0].isalpha()])
            if acronym:
                issue_path = f"de/{acronym} {num_part}"
        if not issue_path:
            issue_path = f"de/DE_{clean_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_gr_metadata(info):
    title = info.get("title", "GR Comic")
    book_id = str(info.get("id") or "TODO")

    # 1. DB lookup first
    issue_path = search_publication_code(title, "gr")

    # 2. Regex fallback
    if not issue_path:
        for pattern, repl in GR_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    # 3. Generic fallback using the article ID
    if not issue_path:
        issue_path = f"gr/GR_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_it_metadata(info):
    title = info.get("title", "IT Comic")
    book_id = str(info.get("id") or "TODO")

    issue_path = search_publication_code(title, "it")

    if not issue_path:
        for pattern, repl in IT_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    if not issue_path:
        issue_path = f"it/IT_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_br_metadata(info):
    title = info.get("title", "BR Comic")
    book_id = str(info.get("id") or "TODO")

    issue_path = search_publication_code(title, "br")

    if not issue_path:
        for pattern, repl in BR_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    if not issue_path:
        issue_path = f"br/BR_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_glenat_metadata(info):
    title = info.get("title", "Album Disney")
    ean_val = info.get("ean", "")
    issue_path = _build_glenat_inducks_path(
        title,
        ean=ean_val,
        collection_label=info.get("collection_label"),
        serie_label=info.get("serie_label"),
        tome_num=info.get("numero_de_tome")
    )
    return _build_metadata(issue_path, title, info, ean=ean_val)

def build_inducks_path(inducks, numero: str) -> str | None:
    if not inducks or not numero:
        return None
    try:
        numero = str(numero).strip()
        if "-" in numero:
            parts = [p.strip() for p in numero.split("-")]
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                p1, p2 = parts[0], parts[1]
                if len(p1) == len(p2) and len(p1) >= 3 and p1[:-2] == p2[:-2]:
                    num_str = f"{p1}-{p2[-2:]}"
                else:
                    num_str = f"{p1}-{p2}"
            else:
                num_str = numero
        else:
            num_str = numero

        first_part = numero.split("-")[0].strip()
        digits = "".join(filter(str.isdigit, first_part))
        if not digits:
            return None
        n = int(digits)

        if isinstance(inducks, str):
            return f"fr/{inducks} {num_str}"
        elif len(inducks) == 2:
            code, width = inducks
            return f"fr/{code}{str(n).rjust(width)}"
        elif len(inducks) == 3:
            code, width, suffix = inducks
            return f"fr/{code} {suffix}{num_str}"
        else:
            return None
    except Exception:
        return None

def _build_glenat_inducks_path(title: str, ean: str | None = None, collection_label: str | None = None, serie_label: str | None = None, tome_num: int | None = None) -> str:
    title_lower = title.lower() if title else ""
    def clean_str(s):
        if not s: return ""
        s = s.lower()
        s = unicodedata.normalize('NFKD', s)
        return "".join(c for c in s if not unicodedata.combining(c))

    title_clean = clean_str(title)
    coll_clean = clean_str(collection_label)
    serie_clean = clean_str(serie_label)

    if tome_num is not None:
        try:
            tome_num = int(tome_num)
        except (ValueError, TypeError):
            tome_num = None

    if tome_num is None:
        tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
        tome_num = int(tome_match.group(1)) if tome_match else None

    path = None
    if "creations originales" in coll_clean or "creations originales" in serie_clean:
        path = f"fr/DBG{str(tome_num).rjust(4)}" if tome_num is not None else "fr/DBG"
    elif any(k in title_clean for k in ("grande histoire de picsou", "grande epopee de picsou")) or "grande histoire de picsou" in serie_clean:
        path = f"fr/GHP{str(tome_num).rjust(4)}" if tome_num is not None else "fr/GHP"
    elif any(k in title_clean for k in ("ages d'or", "age d'or")) or "ages d'or" in coll_clean or "ages d'or" in serie_clean:
        path = f"fr/AOD{str(tome_num).rjust(4)}" if tome_num is not None else "fr/AOD"
    elif "les grands heros" in coll_clean or "les grands heros" in serie_clean or "les grands heros" in title_clean:
        path = f"fr/GHD{str(tome_num).rjust(4)}" if tome_num is not None else "fr/GHD"

    if path and re.match(r'^fr/[A-Z]+$', path):
        found = _find_issue_by_title(title, "fr")
        if found:
            return found

    if path:
        return path

    return f"fr/GL_{ean[-6:]}" if ean else "fr/GL_TODO"
