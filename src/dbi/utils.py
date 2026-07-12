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


def _format_price_for_dbi(prix_str: str | None) -> str | None:
    """Converts a price to the DBI format 'X.XX CUR'."""
    if not prix_str:
        return None
    m = re.search(r'([0-9]+)[,\.]([0-9]{1,2})', prix_str)
    if m:
        major = m.group(1)
        minor = m.group(2).ljust(2, '0')
        currency = "USD" if "$" in prix_str else "EUR"
        return f"{major}.{minor} {currency}"
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

        country_prefix = os.path.basename(dbi_path).split('.')[0] + "/"
        unique_blocks = {}
        for b in cleaned_blocks:
            code = parse_issue_code_from_block(b)
            if code:
                full_code = country_prefix + code if not code.startswith(country_prefix) else code
                if is_fully_indexed_in_inducks(full_code):
                    print(f"  [DBI] Automatically removed: {full_code} is already completely indexed.")
                    continue
                unique_blocks[code] = b
            else:
                unique_blocks[f"unknown_{len(unique_blocks)}"] = b

        sorted_blocks = sorted(unique_blocks.values(), key=block_sort_key)
        
        sorted_content = "\n\n".join(sorted_blocks) + "\n\n"

        with open(dbi_path, "w", encoding="utf-8") as f:
            f.write(sorted_content)
    except Exception as e:
        print(f"  [warn] Failed to sort {dbi_path}: {e}")