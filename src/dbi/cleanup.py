import re
import os
import requests

def cleanup_indexed_issues(dbi_paths: list[str]):
    """Removes blocks from the given DBI files that correspond to issues already indexed in Inducks."""
    
    issue_codes_to_check = set()
    file_blocks = {}
    
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

    for path in dbi_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r'^\^\^\s*Pre-index.*?\n', '', content, flags=re.MULTILINE)
            blocks = re.split(r'(?=\^\^ Source:)', content)
            
            country_prefix = os.path.basename(path).replace(".dbi", "").lower()
            parsed_blocks = []
            for b in blocks:
                b_str = b.strip()
                if b_str and "^^ Source:" in b_str:
                    lines = [line.rstrip() for line in b_str.split('\n')]
                    cleaned_block = '\n'.join(lines)
                    code = parse_issue_code_from_block(cleaned_block)
                    if code:
                        clean_code = code.replace(" ", "").lower()
                        if "/" not in clean_code:
                            clean_code = f"{country_prefix}/{clean_code}"
                        parsed_blocks.append((code, clean_code, cleaned_block))
                        issue_codes_to_check.add(clean_code)
                    else:
                        parsed_blocks.append((code, None, cleaned_block))
            file_blocks[path] = parsed_blocks
        except Exception as e:
            print(f"  [warn] Failed to read {path} for cleanup: {e}")

    if not issue_codes_to_check:
        return

    search_list = list(issue_codes_to_check)
    
    query_items = set(search_list)
    for code in search_list:
        if '-' in code:
            query_items.add(code.split('-')[0])
    query_list = list(query_items)
    
    found_codes = set()
    
    print(f"  [DBI] Checking {len(query_list)} issue(s) against Inducks database...")
    from src.db import query_db
    try:
        # Process in batches of 100 to avoid overly large queries
        batch_size = 100
        for i in range(0, len(query_list), batch_size):
            batch = query_list[i:i+batch_size]
            placeholders = ','.join(['?'] * len(batch))
            query = f"SELECT issuecode, fullyindexed FROM inducks_issue WHERE LOWER(REPLACE(issuecode, ' ', '')) IN ({placeholders})"
            res = query_db(query, tuple(batch))
            for row in res:
                issuecode_clean = row[0].replace(" ", "").lower()
                fully_indexed = row[1].strip().upper() if row[1] else ''
                if fully_indexed == 'Y':
                    found_codes.add(issuecode_clean)
    except Exception as e:
        print(f"  [warn] DB fetch failed: {e}")
        return

    if not found_codes:
        return

    def delete_cover_for_issue(issue_code: str, country_prefix: str):
        m = re.match(r'^([a-zA-Z]+)(\s+)(.*)$', issue_code)
        if m:
            pub_code = m.group(1).lower()
            number = re.sub(r'[^a-zA-Z0-9]', '_', m.group(3)).lower()
            safe_code = f"{pub_code}_{number.zfill(4)}"
        else:
            safe_code = re.sub(r'[^a-zA-Z0-9]', '_', issue_code).lower()
            
        # Check standard .jpg extension
        cover_path = os.path.join("covers", f"{country_prefix}_{safe_code}a_001.jpg")
        if os.path.exists(cover_path):
            try:
                os.remove(cover_path)
                print(f"  [Clean] Deleted cover image {os.path.basename(cover_path)}")
            except Exception as e:
                print(f"  [warn] Failed to delete cover {cover_path}: {e}")

    for path, parsed_blocks in file_blocks.items():
        kept_blocks = []
        country_prefix = os.path.basename(path).replace(".dbi", "").lower()
        
        for orig_code, clean_code, block in parsed_blocks:
            is_found = False
            if clean_code:
                if clean_code in found_codes:
                    is_found = True
                elif '-' in clean_code:
                    first_part = clean_code.split('-')[0]
                    if first_part in found_codes:
                        is_found = True
                        
            if not is_found:
                kept_blocks.append(block)
            else:
                print(f"  [DBI] Issue {orig_code} is already in Inducks. Removing from {path}.")
                delete_cover_for_issue(orig_code, country_prefix)
        
        if len(kept_blocks) < len(parsed_blocks):
            header = "^^ Pre-index automatically generated by DisneyComicsWatcher\n\n"
            sorted_content = header + "\n\n".join(kept_blocks) + "\n\n"
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(sorted_content)
            except Exception as e:
                print(f"  [warn] Failed to rewrite {path}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  Public Entry Point
# ─────────────────────────────────────────────────────────────────────────────