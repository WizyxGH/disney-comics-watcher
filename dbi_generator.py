"""dbi_generator.py — Générateur de squelettes de pré-index Inducks (.dbi).

Ce module est autonome : il n'importe rien de check_magazines afin d'éviter
les imports circulaires. Les données nécessaires (OVERRIDES, prix, date…) lui
sont passées en paramètres.

Format de référence : https://inducks.org/bolderbast/xh7111_DBIReader.html
"""

import os
import re
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

DBI_FILE = "fr.dbi"


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires de formatage
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date_fr(s: str | None):
    """DD/MM/YYYY → objet date, ou None si invalide."""
    if not s:
        return None
    try:
        d, m, y = str(s).strip().split("/")
        return datetime(int(y), int(m), int(d)).date()
    except (ValueError, AttributeError):
        return None


def _format_price_for_dbi(prix_str: str | None) -> str | None:
    """Convertit un prix comme '7,50 €' ou '7.50€' en format DBI 'X.XX EUR'."""
    if not prix_str:
        return None
    m = re.search(r'([0-9]+)[,\.]([0-9]{1,2})', prix_str)
    if m:
        euros    = m.group(1)
        centimes = m.group(2).ljust(2, '0')
        return f"{euros}.{centimes} EUR"
    return None


def _format_date_for_dbi(date_str: str | None) -> str | None:
    """Convertit DD/MM/YYYY ou YYYY-MM-DD en format DBI 'YYYY-MM-DD'."""
    if not date_str:
        return None
    d = _parse_date_fr(date_str)
    if d:
        return d.strftime("%Y-%m-%d")
    # Essai format ISO direct
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str.strip()):
        return date_str.strip()
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Construction du code Inducks
# ─────────────────────────────────────────────────────────────────────────────

def build_inducks_path(inducks, numero: str) -> str | None:
    """Construit le chemin Inducks brut (ex: 'fr/PM  580') pour un numéro donné.

    Args:
        inducks : config depuis OVERRIDES — str, (code, width) ou (code, width, suffix).
        numero  : numéro de parution (ex: '580' ou '3858-3859').
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
    """Construit le chemin Inducks pour un album Glénat (séries connues ou fallback).

    Séries reconnues automatiquement :
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

    # Fallback avec les 6 derniers chiffres de l'EAN pour un code provisoire unique
    return f"fr/GL_{ean[-6:]}" if ean else "fr/GL_TODO"


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def generate_dbi_skeleton(info: dict, publication_type: str, overrides: dict | None = None) -> None:
    """Génère et sauvegarde un squelette de pré-index Inducks (.dbi).

    Args:
        info             : dict décrivant la parution (codif/ean, prix, date, …).
        publication_type : ``'magazine'`` ou ``'glenat'``.
        overrides        : dict OVERRIDES de check_magazines (optionnel pour les magazines).
    """
    overrides = overrides or {}
    try:

        # ── Résoudre les métadonnées selon la source ──────────────────────────
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

        else:  # glenat
            title      = info.get("title", "Album Disney")
            ean_val    = info.get("ean", "")
            name       = title
            issue_path = _build_glenat_inducks_path(title, ean_val)
            prix_raw   = info.get("price")
            date_raw   = info.get("date")
            pages_val  = info.get("pages")
            size_val   = info.get("size")
            isstrans   = info.get("isstrans")

        # ── Formater les champs ───────────────────────────────────────────────
        issdate = _format_date_for_dbi(date_raw)
        price   = _format_price_for_dbi(prix_raw)

        # ── Nom du fichier de sortie ──────────────────────────────────────────
        dbi_path = DBI_FILE

        # ── Ligne h3 au format DBI fixe ────────────────────────────────────
        # Positions (1-indexed, spec Bolderbast) :
        #   1-12  issuecode  (12 car., espace-padded à droite)
        #   13    espace
        #   14    'h'
        #   15    '3'
        #   16    espace
        #   17+   titre + champs entre crochets
        #
        # Si le code dépasse 12 caractères (ex: fr/JM 3858-59 = 14 car.),
        # la position fixe est laissée vide (12 espaces) et le code complet
        # est renseigné via [entrycode:...] — cf. spec xe27.html#a_h3IssueCode
        if len(issue_path) <= 12:
            issue_code_field = issue_path.ljust(12)
        else:
            issue_code_field = "->" + " " * 10  # visuel : entrycode dans les entrées ci-dessous

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

        # ── Ligne d'entrée couverture (entrycode + "a") ──────────────────────
        # Format DBI (positions 1-indexed) :
        #   1-12  entrycode   (padded à 12, ou [entrycode:...] si > 12 chars)
        #  13-26  storycode   (14 chars — "?" si inconnu)
        #  27-28  pages       (" 1" pour 1 page, right-aligned)
        #    29   brokpg      (vide/espace)
        #  30-31  pagel       ("c " pour couverture)
        #    32   ignoré
        #  33-52  plot/writ/art/ink/hero (vide)
        cover_ec = issue_path + "a"
        storycode_field = "?".ljust(14)   # storycode inconnu
        pages_field     = " 1"            # 1 page, right-aligned sur 2 chars
        brokpg          = " "             # vide
        pagel           = "c "            # "c" en pagel
        rest            = " " * 21        # ignoré(1) + plot/writ/art/ink/hero(20)

        if len(cover_ec) <= 12:
            cover_line = f"{cover_ec.ljust(12)}{storycode_field}{pages_field}{brokpg}{pagel}{rest}"
        else:
            cover_line = f"->          {storycode_field}{pages_field}{brokpg}{pagel}{rest} [entrycode:{cover_ec}]"

        # ── Corps du fichier ──────────────────────────────────────────────────
        body_parts = []
        body_parts.append(
            f"^^ Pre-index genere automatiquement par DisneyComicsWatcher\n"
            f"^^ Source : {publication_type}\n"
            f"^^ A completer et soumettre sur https://inducks.org/bolderbast/\n"
        )
        body_parts.append(h3_line + "\n")
        body_parts.append(cover_line + "\n\n")

        # ── Écriture (ASCII + remplacement des caractères non-ASCII) ──────────
        content = "".join(body_parts)
        with open(dbi_path, "a", encoding="ascii", errors="replace") as f:
            f.write(content)
        print(f"  [DBI] Entrée ajoutée dans {dbi_path} ({issue_path})")

    except Exception as e:
        print(f"  [warn] Impossible de générer le squelette DBI : {e}")
