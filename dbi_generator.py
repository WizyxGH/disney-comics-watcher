"""dbi_generator.py — Inducks pre-index skeleton (.dbi) generator.

This module is self-contained: it does not import anything from check_magazines
to avoid circular imports. Necessary data (OVERRIDES, price, date...) are passed
as parameters.

Reference format: https://inducks.org/bolderbast/xh7111_DBIReader.html
"""

import os
import re
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


def _build_glenat_inducks_path(title: str, ean: str | None = None) -> str:
    """Builds the Inducks path for a Glénat album (known series or fallback).

    Automatically recognized series:
      - La Grande Histoire / Grande Épopée de Picsou → fr/GHP
      - Les Âges d'or de Disney                      → fr/AOD
    """
    title_lower = title.lower()
    tome_match  = re.search(r'(?:tome|t\.)\s*(\d+)', title_lower)
    tome_num    = int(tome_match.group(1)) if tome_match else None

    if any(k in title_lower for k in ("grande histoire de picsou", "grande epopee de picsou", "grande épopée de picsou")):
        return f"fr/GHP{str(tome_num).rjust(4)}" if tome_num is not None else "fr/GHP"

    if any(k in title_lower for k in ("ages d'or", "âges d'or", "age d'or", "âge d'or")):
        return f"fr/AOD{str(tome_num).rjust(4)}" if tome_num is not None else "fr/AOD"

    # Fallback with the last 6 digits of the EAN for a unique temporary code
    return f"fr/GL_{ean[-6:]}" if ean else "fr/GL_TODO"


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
            issue_path = _build_glenat_inducks_path(title, ean_val)
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
        if len(issue_path) <= 12:
            issue_code_field = issue_path.ljust(12)
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
        if ean_val:
            fields.append(f"[EAN {ean_val}]")
        fields.append("[inx:-]")

        h3_line = f"{issue_code_field} h3 {' '.join(fields)}"

        # ── Cover entry line (entrycode + "a") ──────────────────────────────
        # DBI format (1-indexed positions):
        #   1-12  entrycode   (padded to 12, or [entrycode:...] if > 12 chars)
        #  13-26  storycode   (14 chars — "?" if unknown)
        #  27-28  pages       (" 1" for 1 page, right-aligned)
        #    29   brokpg      (empty/space)
        #  30-31  pagel       ("c " for cover)
        #    32   ignored
        #  33-52  plot/writ/art/ink/hero (empty)
        cover_ec = issue_path + "a"
        storycode_field = "?".ljust(14)   # unknown storycode
        pages_field     = " 1"            # 1 page, right-aligned to 2 chars
        brokpg          = " "             # empty
        pagel           = "c "            # "c" in pagel
        rest            = " " * 21        # ignored(1) + plot/writ/art/ink/hero(20)

        if len(cover_ec) <= 12:
            cover_line = f"{cover_ec.ljust(12)}{storycode_field}{pages_field}{brokpg}{pagel}{rest}"
        else:
            cover_line = f"->          {storycode_field}{pages_field}{brokpg}{pagel}{rest} [entrycode:{cover_ec}]"

        # ── File body ─────────────────────────────────────────────────────────
        body_parts = []
        body_parts.append(
            f"^^ Pre-index automatically generated by DisneyComicsWatcher\n"
            f"^^ Source: {publication_type}\n"
            f"^^ Complete and submit on https://inducks.org/bolderbast/\n"
        )
        body_parts.append(h3_line + "\n")
        body_parts.append(cover_line + "\n\n")

        # ── Writing (ASCII + replacement of non-ASCII characters) ───────────
        content = "".join(body_parts)
        with open(dbi_path, "a", encoding="ascii", errors="replace") as f:
            f.write(content)
        print(f"  [DBI] Entry added to {dbi_path} ({issue_path})")

    except Exception as e:
        print(f"  [warn] Unable to generate DBI skeleton: {e}")
