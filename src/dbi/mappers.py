import re
import unicodedata
from src.dbi.isv_search import search_publication_code

def resolve_magazine_metadata(info, overrides):
    codif   = info.get("codif", "")
    ov      = overrides.get(codif, {})
    inducks = ov.get("inducks")
    numero  = str(info.get("numero") or "").strip()
    name    = ov.get("name") or info.get("site_name") or codif
    
    issue_path = build_inducks_path(inducks, numero) if inducks and numero else None
    if not issue_path:
        issue_path = f"fr/TODO_{codif} {numero}"
    return {
        "issue_path": issue_path,
        "name": name,
        "price": info.get("prix"),
        "date": info.get("date_mise_en_vente"),
        "pages": None,
        "size": None,
        "isstrans": None,
        "ean": None
    }

def resolve_us_metadata(info):
    title = info.get("title", "US Comic")
    sku   = str(info.get("sku") or info.get("id") or "TODO")
    
    mappings = [
        # Example exceptions if needed later
    ]
    
    issue_path = None
    for pattern, repl in mappings:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            issue_path = m.expand(repl)
            break
            
    if not issue_path:
        issue_path = search_publication_code(title, "us")
        
    if not issue_path:
        issue_path = f"us/US_{sku[-6:]}"
        
    return {
        "issue_path": issue_path,
        "name": title,
        "price": info.get("price"),
        "date": info.get("date"),
        "pages": info.get("pages"),
        "size": info.get("size"),
        "isstrans": info.get("isstrans"),
        "ean": None
    }

def resolve_de_metadata(info):
    title = info.get("title", "DE Comic")
    book_id = str(info.get("id") or "TODO")
    clean_id = book_id.split('/')[-1]

    # 1. DB lookup first (exact / contains / fuzzy)
    issue_path = search_publication_code(title, "de")

    # 2. Regex fallback for very well-known series (faster, no DB needed)
    if not issue_path:
        mappings = [
            (r'Lustiges Taschenbuch Young Comics (?:Nr\.\s*)?(\d+)', r'de/LTBYC \1'),
            (r'Lustiges Taschenbuch Weihnachtsgeschichten (?:Nr\.\s*)?(\d+)', r'de/LTBWE \1'),
            (r'Micky Maus Magazin (?:Nr\.\s*)?(\d+)', r'de/MM \1'),
            (r'Micky Maus Legacy Collection (?:Nr\.\s*)?(\d+)', r'de/MMLC \1'),
            (r'Lustiges Taschenbuch (?:Nr\.\s*)?(\d+)', r'de/LTB \1'),
            (r'Entenhausener Ikonen (?:0*)?(\d+)', r'de/EIB \1'),
            (r'Enthologien (?:0*)?(\d+)', r'de/ENT \1'),
        ]
        for pattern, repl in mappings:
            m = re.search(pattern, title, re.IGNORECASE)
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

    return {
        "issue_path": issue_path,
        "name": title,
        "price": info.get("price"),
        "date": info.get("date"),
        "pages": info.get("pages"),
        "size": info.get("size"),
        "isstrans": info.get("isstrans"),
        "ean": None
    }

def resolve_gr_metadata(info):
    title = info.get("title", "GR Comic")
    book_id = str(info.get("id") or "TODO")

    # 1. DB lookup first
    issue_path = search_publication_code(title, "gr")

    # 2. Regex fallback
    if not issue_path:
        mappings = [
            (r'Super MIKY\s*(?:#|Nr\.\s*)?(\d+)', r'gr/SM \1'),
            (r'M[ií]k[yu]\s+M[aá]ous\s*#(\d+)', r'gr/GR \1'),
            (r'K[oó]mix\s*#(\d+)', r'gr/GRC \1'),
            (r'Nt[oó]nalnt\s*#(\d+)', r'gr/GRD \1'),
        ]
        for pattern, repl in mappings:
            m = re.search(pattern, title, re.IGNORECASE)
            if m:
                issue_path = m.expand(repl)
                break

    # 3. Generic fallback using the article ID
    if not issue_path:
        issue_path = f"gr/GR_{book_id[-6:]}"

    return {
        "issue_path": issue_path,
        "name": title,
        "price": info.get("price"),
        "date": info.get("date"),
        "pages": info.get("pages"),
        "size": info.get("size"),
        "isstrans": info.get("isstrans"),
        "ean": None
    }

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
    return {
        "issue_path": issue_path,
        "name": title,
        "price": info.get("price"),
        "date": info.get("date"),
        "pages": info.get("pages"),
        "size": info.get("size"),
        "isstrans": info.get("isstrans"),
        "ean": ean_val
    }

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

    if "creations originales" in coll_clean or "creations originales" in serie_clean:
        return f"fr/DBG{str(tome_num).rjust(4)}" if tome_num is not None else "fr/DBG"

    if any(k in title_clean for k in ("grande histoire de picsou", "grande epopee de picsou")) or "grande histoire de picsou" in serie_clean:
        return f"fr/GHP{str(tome_num).rjust(4)}" if tome_num is not None else "fr/GHP"

    if any(k in title_clean for k in ("ages d'or", "age d'or")) or "ages d'or" in coll_clean or "ages d'or" in serie_clean:
        return f"fr/AOD{str(tome_num).rjust(4)}" if tome_num is not None else "fr/AOD"

    return f"fr/GL_{ean[-6:]}" if ean else "fr/GL_TODO"
