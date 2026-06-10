"""dbi_generator.py — Inducks pre-index skeleton (.dbi) generator.

This module is self-contained: it does not import anything from check_magazines
to avoid circular imports. Necessary data (OVERRIDES, price, date...) are passed
as parameters.

Reference format: https://inducks.org/bolderbast/xh7111_DBIReader.html
"""

import os
import re
import unicodedata
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

DBI_FILE = "fr.dbi"


# ─────────────────────────────────────────────────────────────────────────────
#  Formatting Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_fr(s: str | None):
    """DD/MM/YYYY → date object, or None if invalid."""
    if not s:
        return None
    try:
        d, m, y = str(s).strip().split("/")
        return datetime(int(y), int(m), int(d)).date()
    except (ValueError, AttributeError):
        return None


def _format_price_for_dbi(prix_str: str | None) -> str | None:
    """Converts a price like '7,50 €' or '7.50€' to the DBI format 'X.XX EUR'."""
    if not prix_str:
        return None
    m = re.search(r'([0-9]+)[,\.]([0-9]{1,2})', prix_str)
    if m:
        euros    = m.group(1)
        centimes = m.group(2).ljust(2, '0')
        return f"{euros}.{centimes} EUR"
    return None


def _format_date_for_dbi(date_str: str | None) -> str | None:
    """Converts DD/MM/YYYY or YYYY-MM-DD to the DBI format 'YYYY-MM-DD'."""
    if not date_str:
        return None
    d = _parse_date_fr(date_str)
    if d:
        return d.strftime("%Y-%m-%d")
    # Try direct ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str.strip()):
        return date_str.strip()
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Inducks Code Construction
# ─────────────────────────────────────────────────────────────────────────────

def build_inducks_path(inducks, numero: str) -> str | None:
    """Builds the raw Inducks path (e.g., 'fr/PM  580') for a given issue.

    Args:
        inducks : config from OVERRIDES — str, (code, width) or (code, width, suffix).
        numero  : issue number (e.g., '580' or '3858-3859').
    """
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


def _build_glenat_inducks_path(
    title: str,
    ean: str | None = None,
    collection_label: str | None = None,
    serie_label: str | None = None,
    tome_num: int | None = None
) -> str:
    """Builds the Inducks path for a Glénat album (known series or fallback).

    Automatically recognized series:
      - Disney By Glénat                             → fr/DBG
      - La Grande Histoire / Grande Épopée de Picsou → fr/GHP
      - Les Âges d'or de Disney                      → fr/AOD
    """
    title_lower = title.lower()

    def clean_str(s):
        if not s:
            return ""
        s = s.lower()
        s = unicodedata.normalize('NFKD', s)
        return "".join(c for c in s if not unicodedata.combining(c))

    title_clean = clean_str(title)
    coll_clean = clean_str(collection_label)
    serie_clean = clean_str(serie_label)

    # Resolve tome number
    if tome_num is not None:
        try:
            tome_num = int(tome_num)
        except (ValueError, TypeError):
            tome_num = None

    if tome_num is None:
        tome_match = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
        tome_num = int(tome_match.group(1)) if tome_match else None

    # 1. DBG: Disney By Glénat
    if "creations originales" in coll_clean or "creations originales" in serie_clean:
        return f"fr/DBG{str(tome_num).rjust(4)}" if tome_num is not None else "fr/DBG"

    # 2. GHP: La Grande Histoire de Picsou
    if any(k in title_clean for k in ("grande histoire de picsou", "grande epopee de picsou")) or "grande histoire de picsou" in serie_clean:
        return f"fr/GHP{str(tome_num).rjust(4)}" if tome_num is not None else "fr/GHP"

    # 3. AOD: Les Âges d'or de Disney
    if any(k in title_clean for k in ("ages d'or", "age d'or")) or "ages d'or" in coll_clean or "ages d'or" in serie_clean:
        return f"fr/AOD{str(tome_num).rjust(4)}" if tome_num is not None else "fr/AOD"

    # Fallback with the last 6 digits of the EAN for a unique temporary code
    return f"fr/GL_{ean[-6:]}" if ean else "fr/GL_TODO"


# ─────────────────────────────────────────────────────────────────────────────
#  Sorting Utility
# ─────────────────────────────────────────────────────────────────────────────

def sort_dbi_file(dbi_path: str):
    """Sorts the pre-index blocks in the DBI file alphabetically and naturally by issue code, putting a single header at the top."""
    if not os.path.exists(dbi_path):
        return
    try:
        with open(dbi_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove any occurrence of "^^ Pre-index..." comment lines from the content
        content = re.sub(r'^\^\^\s*Pre-index.*?\n', '', content, flags=re.MULTILINE)

        # Split blocks by "^^ Source:"
        blocks = re.split(r'(?=\^\^ Source:)', content)
        cleaned_blocks = []
        for b in blocks:
            b_str = b.strip()
            if b_str and "^^ Source:" in b_str:
                # Remove trailing whitespace from each line in the block
                lines = [line.rstrip() for line in b_str.split('\n')]
                cleaned_blocks.append('\n'.join(lines))

        def parse_issue_code_from_block(block: str) -> str:
            m = re.search(r'\[entrycode:([^\]]+)\]', block)
            if m:
                ec = m.group(1).strip()
                if ec.endswith('a'):
                    return ec[:-1].strip()
                return ec

            for line in block.split('\n'):
                line = line.strip()
                if not line or line.startswith('^^'):
                    continue
                if ' h3 ' in line:
                    code_part = line.split(' h3 ')[0].strip()
                    if code_part != '->':
                        return code_part
            return ""

        def natural_sort_key(s: str):
            s_clean = re.sub(r'\s+', ' ', s).strip()
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s_clean)]

        def block_sort_key(block: str):
            code = parse_issue_code_from_block(block)
            return natural_sort_key(code)

        # Deduplicate blocks by issue code, keeping the latest one (which contains the new analysis/details)
        unique_blocks = {}
        for b in cleaned_blocks:
            code = parse_issue_code_from_block(b)
            if code:
                unique_blocks[code] = b
            else:
                unique_blocks[f"unknown_{len(unique_blocks)}"] = b

        sorted_blocks = sorted(unique_blocks.values(), key=block_sort_key)
        
        header = "^^ Pre-index automatically generated by DisneyComicsWatcher\n\n"
        sorted_content = header + "\n\n".join(sorted_blocks) + "\n\n"

        with open(dbi_path, "w", encoding="utf-8") as f:
            f.write(sorted_content)
    except Exception as e:
        print(f"  [warn] Failed to sort {dbi_path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Public Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def generate_dbi_skeleton(info: dict, publication_type: str, overrides: dict | None = None) -> None:
    """Generates and saves an Inducks pre-index skeleton (.dbi).

    Args:
        info             : dict describing the release (codif/ean, price, date, ...).
        publication_type : ``'magazine'`` or ``'glenat'``.
        overrides        : check_magazines OVERRIDES dict (optional for magazines).
    """
    overrides = overrides or {}
    try:

        # ── Resolve metadata depending on the source ──────────────────────────
        if publication_type == "magazine":
            codif      = info.get("codif", "")
            ov         = overrides.get(codif, {})
            inducks    = ov.get("inducks")
            numero     = str(info.get("numero") or "").strip()
            name       = ov.get("name") or info.get("site_name") or codif
            issue_path = build_inducks_path(inducks, numero) if inducks and numero else None
            if not issue_path:
                issue_path = f"fr/TODO_{codif} {numero}"
            prix_raw   = info.get("prix")
            date_raw   = info.get("date_mise_en_vente")
            pages_val  = None
            size_val   = None
            isstrans   = None
            ean_val    = None

        else:  # Glenat
            title      = info.get("title", "Album Disney")
            ean_val    = info.get("ean", "")
            name       = title
            coll_label = info.get("collection_label")
            ser_label  = info.get("serie_label")
            t_num      = info.get("numero_de_tome")
            issue_path = _build_glenat_inducks_path(
                title,
                ean=ean_val,
                collection_label=coll_label,
                serie_label=ser_label,
                tome_num=t_num
            )
            prix_raw   = info.get("price")
            date_raw   = info.get("date")
            pages_val  = info.get("pages")
            size_val   = info.get("size")
            isstrans   = info.get("isstrans")

        # ── Format fields ─────────────────────────────────────────────────────
        issdate = _format_date_for_dbi(date_raw)
        price   = _format_price_for_dbi(prix_raw)

        # ── Output file name ──────────────────────────────────────────────────
        dbi_path = DBI_FILE

        # ── h3 line with fixed DBI format ────────────────────────────────────
        # Positions (1-indexed, Bolderbast spec):
        #   1-12  issuecode  (12 chars, space-padded on the right)
        #   13    space
        #   14    'h'
        #   15    '3'
        #   16    space
        #   17+   title + bracketed fields
        #
        # If the code exceeds 12 characters (e.g., fr/JM 3858-59 = 14 chars),
        # the fixed position is left empty (12 spaces) and the full code
        # is specified via [entrycode:...] — see spec xe27.html#a_h3IssueCode
        # Strip "fr/" from issue_path for DBI representation
        dbi_issue_code = issue_path
        if dbi_issue_code.startswith("fr/"):
            dbi_issue_code = dbi_issue_code[3:]

        # Extrapolate for JM (Journal de Mickey)
        isslet_val = None
        if dbi_issue_code.startswith("JM "):
            if not pages_val:
                pages_val = 116
            isslet_val = "B.L.A.C.K Studio"

        if len(dbi_issue_code) <= 12:
            issue_code_field = dbi_issue_code.ljust(12)
        else:
            issue_code_field = "->" + " " * 10  # visual: entrycode in the entries below

        fields = []
        if publication_type != "magazine":
            fields.append(name)
        if issdate:
            fields.append(f"[issdate:{issdate}]")
        if price:
            fields.append(f"[price:{price}]")
        if pages_val:
            fields.append(f"[pages:{pages_val}]")
        if size_val:
            fields.append(f"[size:{size_val}]")
        if isstrans:
            fields.append(f"[isstrans:{isstrans}]")
        if isslet_val:
            fields.append(f"[isslet:{isslet_val}]")
        if ean_val:
            fields.append(f"[EAN {ean_val}]")
        fields.append("[inx:-]")

        h3_line = f"{issue_code_field} h3 {' '.join(fields)}".rstrip()

        # ── Cover entry line (entrycode + "a") ──────────────────────────────
        # DBI format (1-indexed positions):
        #   1-12  entrycode   (padded to 12, or [entrycode:...] if > 12 chars)
        #  13-26  storycode   (14 chars — "?" if unknown)
        #  27-28  pages       (" 1" for 1 page, right-aligned)
        #    29   brokpg      (empty/space)
        #  30-31  pagel       ("c " for cover)
        #    32   ignored
        #  33-52  plot/writ/art/ink/hero (empty)
        cover_ec = dbi_issue_code + "a"
        storycode = f"FC {dbi_issue_code}"
        storycode_field = storycode.ljust(14)
        pages_field     = " 1"            # 1 page, right-aligned to 2 chars
        brokpg          = " "             # empty
        pagel           = "c "            # "c" in pagel
        plot_val = ""
        writ_val = ""
        art_val = ""
        ink_val = ""
        hero_val = ""

        # Extract characters and find primary hero
        characters = info.get("characters", [])
        if characters:
            for c in characters:
                if c.get("code"):
                    hero_val = c["code"]
                    break

        if dbi_issue_code.startswith("JM "):
            writ_val = "FPt"
            art_val = "FPt"

        rest = " " + plot_val.ljust(4) + writ_val.ljust(4) + art_val.ljust(4) + ink_val.ljust(4) + hero_val.ljust(4)

        if len(cover_ec) <= 12:
            prefix = f"{cover_ec.ljust(12)}{storycode_field}{pages_field}{brokpg}{pagel}{rest}"
        else:
            prefix = f"->          {storycode_field}{pages_field}{brokpg}{pagel}{rest}"

        cover_title = info.get("cover_title") or ""
        suffixes = []
        if cover_title:
            suffixes.append(cover_title)
        if len(cover_ec) > 12:
            suffixes.append(f"[entrycode:{cover_ec}]")
        if dbi_issue_code.startswith("JM "):
            suffixes.append("[col:FPt]")
        if characters:
            codes = []
            for c in characters:
                code = c.get("code")
                if code and code not in codes:
                    codes.append(code)
            if codes:
                suffixes.append(f"[xapp:{','.join(codes)}]")

        title_suffix = " ".join(suffixes)
        cover_line = f"{prefix}{title_suffix}".rstrip()

        # ── File body ─────────────────────────────────────────────────────────
        body_parts = []
        url = info.get("url")
        if url:
            body_parts.append(f"^^ Source: {publication_type} ({url})\n")
        else:
            body_parts.append(f"^^ Source: {publication_type}\n")
        body_parts.append(h3_line + "\n")
        body_parts.append(cover_line + "\n\n")

        # ── Writing (UTF-8 encoding to preserve accents like Â, é, è) ───────────
        content = "".join(body_parts)
        with open(dbi_path, "a", encoding="utf-8") as f:
            f.write(content)
        print(f"  [DBI] Entry added to {dbi_path} ({issue_path})")
        sort_dbi_file(dbi_path)

    except Exception as e:
        print(f"  [warn] Unable to generate DBI skeleton: {e}")
