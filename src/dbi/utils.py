import os
import re
from datetime import datetime
from src.utils import is_fully_indexed_in_inducks

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


# Symbols that are not the dollar; checked before "$" because "R$" contains it.
_CURRENCY_SYMBOLS = (("R$", "BRL"), ("zł", "PLN"), ("Kč", "CZK"), ("лв", "BGN"), ("£", "GBP"), ("€", "EUR"), ("$", "USD"))


def _format_price_for_dbi(prix_str: str | None) -> str | None:
    """Converts a price to the DBI format 'X.XX CUR' ('1850 ISK' for whole units).

    The currency comes from an ISO code in the string ("1850 ISK", given by
    scrapers that know it), else from its symbol, else EUR.
    """
    if not prix_str:
        return None
    iso = re.search(r"\b([A-Z]{3})\b", prix_str)
    currency = iso.group(1) if iso else next(
        (c for sym, c in _CURRENCY_SYMBOLS if sym in prix_str), "EUR")
    m = re.search(r"([0-9]+)[,.]([0-9]{1,2})\b", prix_str)
    if m:
        return f"{m.group(1)}.{m.group(2).ljust(2, '0')} {currency}"
    # Whole-unit prices are only trusted when the scraper named the currency.
    m = re.search(r'([0-9]+)', prix_str) if iso else None
    return f"{m.group(1)} {currency}" if m else None


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

# An issue block starts on its h3 line. Inducks codes hold spaces ("PM  557",
# "TL 3700"): the code is any run of words before " h3 ", not a single word,
# or the whole file is read as one block and duplicates are never merged.
_BLOCK_START = re.compile(r'(?=\n?(?:^(?:->|[A-Za-z0-9\-_/]+(?: +[A-Za-z0-9\-_/]+)*)\s+h3\s|^\^\^ Source:))', re.MULTILINE)


def split_dbi_blocks(content: str) -> list[str]:
    """The issue blocks of a DBI file, without header comments nor legacy '^^ Source:' lines."""
    content = re.sub(r'^\^\^\s*Pre-index.*?\n', '', content, flags=re.MULTILINE)
    blocks = []
    for b in _BLOCK_START.split(content):
        lines = [line.rstrip() for line in b.strip().split('\n') if not line.startswith('^^ Source:')]
        block = '\n'.join(lines).strip()
        if block and ' h3 ' in block:
            blocks.append(block)
    return blocks


def parse_issue_code_from_block(block: str) -> str:
    """Issue code of a DBI block ('PM  557'), from its h3 line or its [entrycode:]."""
    for line in block.split('\n'):
        line = line.strip()
        if not line or line.startswith('^^'):
            continue
        if ' h3 ' in line:
            code_part = line.split(' h3 ')[0].strip()
            if code_part and code_part != '->':
                return code_part
            m = re.search(r'\[entrycode:([^\s\]]+)\]', line)
            if m:
                return m.group(1).strip()

    m = re.search(r'\[entrycode:([^\s\]]+)a\]', block)
    if m:
        return m.group(1).strip()

    m = re.search(r'\[entrycode:([^\s\]]+)\]', block)
    if m:
        ec = m.group(1).strip()
        if ec.endswith('a'):
            return ec[:-1].strip()
        return ec
    return ""


def sort_dbi_file(dbi_path: str):
    """Sorts the pre-index blocks in the DBI file alphabetically and naturally by issue code, putting a single header at the top."""
    if not os.path.exists(dbi_path):
        return
    try:
        with open(dbi_path, "r", encoding="utf-8") as f:
            content = f.read()

        cleaned_blocks = split_dbi_blocks(content)

        def natural_sort_key(s: str):
            s_clean = re.sub(r'\s+', ' ', s).strip()
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s_clean)]

        def block_sort_key(block: str):
            code = parse_issue_code_from_block(block)
            return natural_sort_key(code)

        country_prefix = os.path.basename(dbi_path).split('.')[0] + "/"
        unique_blocks = {}
        for b in cleaned_blocks:
            code = parse_issue_code_from_block(b)
            if code:
                full_code = country_prefix + code if not code.startswith(country_prefix) else code
                if is_fully_indexed_in_inducks(full_code):
                    print(f"  [DBI] Automatically removed: {full_code} is already completely indexed.")
                    continue
                # One code, one entry: a later detection of the same issue
                # replaces the earlier one (spacing aside: "PM 557" = "PM  557").
                unique_blocks[re.sub(r"\s+", "", code)] = b
            else:
                unique_blocks[f"unknown_{len(unique_blocks)}"] = b

        sorted_blocks = sorted(unique_blocks.values(), key=block_sort_key)
        
        sorted_content = "\n\n".join(sorted_blocks) + "\n\n"

        with open(dbi_path, "w", encoding="utf-8") as f:
            f.write(sorted_content)
    except Exception as e:
        print(f"  [warn] Failed to sort {dbi_path}: {e}")