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

ISSUE_NUM_PATTERN = r'(\d+(?:/\d+)?)'

DE_MAPPINGS = [
    (re.compile(rf'Lustiges Taschenbuch Young Comics (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/LTBYC \1'),
    (re.compile(rf'Lustiges Taschenbuch Weihnachtsgeschichten (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/LTBWE \1'),
    (re.compile(rf'Micky Maus Magazin (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/MM \1'),
    (re.compile(rf'Micky Maus Comics (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/MMC \1'),
    (re.compile(rf'Micky Maus Legacy Collection (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/MMLC \1'),
    (re.compile(rf'Donald Duck Sonderheft (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/TGDD \1'),
    (re.compile(rf'Die tollsten Geschichten von Donald Duck (?:Sonderheft)?.*?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/TGDD \1'),
    (re.compile(rf'Lustiges Taschenbuch (?:Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/LTB \1'),
    (re.compile(rf'Entenhausener Ikonen (?:0*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/EIB \1'),
    (re.compile(rf'Enthologien (?:0*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'de/ENT \1'),
]

GR_MAPPINGS = [
    (re.compile(rf'Super MIKY\s*(?:#|Nr\.\s*)?{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'gr/SM \1'),
    (re.compile(rf'Μίκυ\s+Μάους\s*#{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'gr/MM \1'),
    (re.compile(rf'Κόμιξ\s*#{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'gr/KX \1'),
    (re.compile(rf'Ντόναλντ\s*#{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'gr/DD \1'),
]

US_MAPPINGS = [
    (re.compile(rf'The Complete Carl Barks Disney Library.*?Vol\.\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'us/CBL \1'),
    (re.compile(rf'Disney Masters.*?Vol\.\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'us/DM \1'),
    (re.compile(rf'Disney Afternoon Adventures.*?Vol\.\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'us/DAA \1'),
    (re.compile(rf'Life and Times of Scrooge McDuck.*?Vol(?:ume|\.)\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'us/CLTS \1'),
]

IT_MAPPINGS = [
    (re.compile(rf'Topolino\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'it/TL \1'),
    (re.compile(rf'Paperinik\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'it/PK \1'),
    (re.compile(rf'Zio Paperone\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'it/ZP \1'),
    (re.compile(rf'I Classici Disney\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'it/CWD \1'),
]

BR_MAPPINGS = [
    (re.compile(rf'Mickey\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/MK \1'),
    (re.compile(rf'Pato Donald\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/PD \1'),
    (re.compile(rf'Zé Carioca\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/ZC \1'),
    (re.compile(rf'Tio Patinhas\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/TP \1'),
    (re.compile(r'\(BD Disney\)', re.IGNORECASE), r'br/BDD'),
    (re.compile(rf'Grandes Sagas Disney.*?Vol\.\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/GSD \1'),
    (re.compile(r'\(Graphic Disney\)', re.IGNORECASE), r'br/GD'),
    (re.compile(rf'Coleção Carl Barks.*?Vol\.\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'br/CCB \1'),
]

EG_MAPPINGS = [
    (re.compile(rf'ميكي\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'eg/M \1'), # Miki (Nahdet Misr)
    (re.compile(rf'ميكي جيب\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'eg/MP \1'), # Miki Pocket
    (re.compile(rf'سوبر ميكي\s*{ISSUE_NUM_PATTERN}', re.IGNORECASE), r'eg/SM \1'), # Super Miki
]


def resolve_magazine_metadata(info, overrides):
    codif   = info.get("codif", "")
    ov      = overrides.get(codif, {})
    inducks = ov.get("inducks")
    numero  = str(info.get("numero") or "").strip()
    name    = ov.get("name") or info.get("site_name") or codif
    
    issue_path = build_inducks_path(inducks, numero) if inducks and numero else None
    if not issue_path:
        issue_path = "fr/UNK"
    return _build_metadata(issue_path, name, info)

def resolve_us_metadata(info):
    title = info.get("title", "US Comic")
    sku   = str(info.get("sku") or info.get("id") or "UNK")
    
    issue_path = None
    for pattern, repl in US_MAPPINGS:
        m = pattern.search(title)
        if m:
            issue_path = m.expand(repl)
            break
            
    if not issue_path:
        issue_path = search_publication_code(title, "us")
        
    if not issue_path:
        issue_path = f"us/UNK_{sku[-6:]}"
        
    return _build_metadata(issue_path, title, info)

def resolve_de_metadata(info):
    title = info.get("title", "DE Comic")
    book_id = str(info.get("id") or "UNK")
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
        m = re.search(r'([A-Za-z\s\.]+)(?:Nr\.\s*|0*)?(\d+(?:/\d+)?)', title)
        if m:
            text_part, num_part = m.group(1).strip(), m.group(2)
            acronym = "".join([w[0].upper() for w in text_part.split() if w and w[0].isalpha()])
            if acronym:
                issue_path = f"de/{acronym} {num_part}"
        if not issue_path:
            issue_path = f"de/UNK_{clean_id[-6:]}"

    # Bolderbast rules: MM/YYYY -> YYYY-MM (e.g. 03/2026 -> 2026-03)
    # Also removes the space if it's just a prefix and date.
    if issue_path:
        m = re.search(r'( ?)(\d{1,2})/(\d{4})$', issue_path)
        if m:
            space, mm, yyyy = m.groups()
            base = issue_path[:m.start()]
            if base.startswith("de/") and " " not in base[3:]:
                # If it's a simple prefix like 'de/DS', remove the space (e.g. de/DS2026-03)
                issue_path = f"{base.strip()}{yyyy}-{mm.zfill(2)}"
            else:
                issue_path = f"{base.strip()} {yyyy}-{mm.zfill(2)}"

    return _build_metadata(issue_path, title, info)

def resolve_gr_metadata(info):
    title = info.get("title", "GR Comic")
    book_id = str(info.get("id") or "UNK")

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
        issue_path = f"gr/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_it_metadata(info):
    title = info.get("title", "IT Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "it")

    if not issue_path:
        for pattern, repl in IT_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    if not issue_path:
        issue_path = f"it/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_br_metadata(info):
    title = info.get("title", "BR Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "br")

    if not issue_path:
        for pattern, repl in BR_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    if not issue_path:
        issue_path = f"br/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_eg_metadata(info):
    title = info.get("title", "EG Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "eg")

    if not issue_path:
        for pattern, repl in EG_MAPPINGS:
            m = pattern.search(title)
            if m:
                issue_path = m.expand(repl)
                break

    if not issue_path:
        issue_path = f"eg/UNK_{book_id[-6:]}"

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

    return "fr/UNK"

def resolve_bg_metadata(info):
    title = info.get("title", "BG Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "bg")

    if not issue_path:
        issue_path = f"bg/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_hr_metadata(info):
    title = info.get("title", "HR Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "hr")

    if not issue_path:
        issue_path = f"hr/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_ee_metadata(info):
    title = info.get("title", "EE Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "ee")

    if not issue_path:
        issue_path = f"ee/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_lv_metadata(info):
    title = info.get("title", "LV Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "lv")

    if not issue_path:
        issue_path = f"lv/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_lt_metadata(info):
    title = info.get("title", "LT Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "lt")

    if not issue_path:
        issue_path = f"lt/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_pl_metadata(info):
    title = info.get("title", "PL Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "pl")

    if not issue_path:
        issue_path = f"pl/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_cz_metadata(info):
    title = info.get("title", "CZ Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "cz")

    if not issue_path:
        issue_path = f"cz/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_rs_metadata(info):
    title = info.get("title", "RS Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "rs")

    if not issue_path:
        issue_path = f"rs/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)

def resolve_si_metadata(info):
    title = info.get("title", "SI Comic")
    book_id = str(info.get("id") or "UNK")

    issue_path = search_publication_code(title, "si")

    if not issue_path:
        issue_path = f"si/UNK_{book_id[-6:]}"

    return _build_metadata(issue_path, title, info)


def resolve_cn_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "cn/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_dk_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "dk/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_es_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "es/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_fi_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "fi/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_is_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "is/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_no_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "no/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_nl_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "nl/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_uk_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "uk/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }

def resolve_se_metadata(info: dict) -> dict:
    return {
        "issue_path": info.get("issue_path", "se/UNK"),
        "title": info.get("title", ""),
        "date": info.get("date", ""),
        "price": info.get("price", ""),
    }
