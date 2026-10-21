"""
setup_db.py — Imports Inducks publication and issue data into the Turso database.

Downloads the Inducks ISV files (updated daily), parses them and inserts into Turso.
Only imports data for the target countries: FR, US, DE, GR.

Usage:
    python setup_db.py           # Import if DB is empty
    python setup_db.py --force   # Force reimport even if data exists
"""

import sys
import os
import time
import requests

# Add the script's directory to sys.path so IDEs and Python find 'src'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

sys.stdout.reconfigure(encoding='utf-8')

from src.db import execute_batch, query_db

ISV_BASE = "https://inducks.org/inducks/isv"

# Tables and their column definitions as they appear in the ISV files
ISV_TABLES = {
    "inducks_publication": {
        "columns": ["publicationcode", "countrycode", "languagecode", "title",
                    "size", "publicationcomment", "circulation", "numbersarefake",
                    "error", "locked", "inxforbidden", "inputfilecode", "maintenanceteamcode"],
        "create": """CREATE TABLE IF NOT EXISTS inducks_publication (
            publicationcode TEXT PRIMARY KEY,
            countrycode     TEXT NOT NULL,
            title           TEXT
        )""",
        "insert_cols": ["publicationcode", "countrycode", "title"],
        "insert_idx": [0, 1, 3],   # positions in the ISV row
    },
    "inducks_issue": {
        "columns": ["issuecode", "issuerangecode", "publicationcode", "issuenumber", "title",
                    "size", "pages", "price"],
        "create": """CREATE TABLE IF NOT EXISTS inducks_issue (
            issuecode       TEXT PRIMARY KEY,
            publicationcode TEXT NOT NULL,
            issuenumber     TEXT,
            title           TEXT,
            fullyindexed    TEXT
        )""",
        "insert_cols": ["issuecode", "publicationcode", "issuenumber", "title", "fullyindexed"],
        "insert_idx": [0, 2, 3, 4, 11],   # positions in the ISV row
    },
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pub_country ON inducks_publication(countrycode)",
    "CREATE INDEX IF NOT EXISTS idx_issue_pub   ON inducks_issue(publicationcode)",
    "CREATE INDEX IF NOT EXISTS idx_issue_clean ON inducks_issue(LOWER(REPLACE(issuecode, ' ', '')))",
]

from src.config import SUPPORTED_COUNTRIES

# Countries we care about
TARGET_COUNTRIES = SUPPORTED_COUNTRIES


def download_isv(table_name: str) -> list[list[str]]:
    """Downloads an ISV file and returns its rows as lists of strings."""
    url = f"{ISV_BASE}/{table_name}.isv"
    print(f"  Downloading {table_name}.isv ...", end=" ", flush=True)
    
    for attempt in range(5):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            r.raise_for_status()
            r.encoding = "utf-8"
            lines = r.text.splitlines()
            # ISV format: tab-separated values, first line is headers
            rows = [line.split("^") for line in lines if line.strip()]
            print(f"{len(rows)} rows")
            return rows
        except requests.exceptions.RequestException as e:
            if attempt == 4:
                raise
            print(f"  [warn] Download failed ({e}), retrying {attempt + 1}/5...")
            time.sleep(5)
    return []


def batch_insert_rows(table: str, columns: list[str], rows: list[tuple], batch_size: int = 80):
    """Inserts rows into Turso in batches using the HTTP pipeline API."""
    total = len(rows)
    if total == 0:
        print(f"    No rows to insert for {table}")
        return

    col_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"

    inserted = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        stmts = []
        for row in batch:
            args = []
            for val in row:
                if val is None or val == "" or val == "\\N":
                    args.append({"type": "null"})
                else:
                    args.append({"type": "text", "value": str(val)})
            stmts.append({"sql": sql, "args": args})

        ok = execute_batch(stmts)
        inserted += len(batch)
        pct = inserted * 100 // total
        print(f"\r    {table}: {inserted}/{total} rows ({pct}%)", end="", flush=True)
        if not ok:
            print(f"\n    [warn] Batch {i // batch_size} had errors")
        time.sleep(0.02)

    print(f"\r    {table}: {inserted}/{total} rows (100%) ✓")


def sync_diff():
    """Incremental sync: only inserts NEW publications and issues into Turso.
    Saves 99.99% of Turso write quota compared to a full re-import.
    """
    print("[diff-sync] Starting incremental update...")

    # 1. Publications
    print("\n[diff-sync] Checking inducks_publication...")
    pub_rows_raw = download_isv("inducks_publication")
    if pub_rows_raw and pub_rows_raw[0][0].lower() == "publicationcode":
        pub_rows_raw = pub_rows_raw[1:]

    cfg_pub = ISV_TABLES["inducks_publication"]
    idx_pub = cfg_pub["insert_idx"]
    country_col = 1

    filtered_pubs = []
    all_pub_codes = set()
    for row in pub_rows_raw:
        if len(row) < max(idx_pub) + 1:
            continue
        country = row[country_col].strip().lower()
        if country not in TARGET_COUNTRIES:
            continue
        values = tuple(row[i].strip() or None for i in idx_pub)
        filtered_pubs.append(values)
        all_pub_codes.add(row[0].strip())

    existing_pubs = set()
    rows = query_db("SELECT publicationcode FROM inducks_publication")
    if rows:
        existing_pubs = {r[0] for r in rows if r and r[0]}
    print(f"  Existing in Turso: {len(existing_pubs)} publications | Target ISV: {len(filtered_pubs)}")

    new_pubs = [p for p in filtered_pubs if p[0] not in existing_pubs]
    if new_pubs:
        print(f"  -> Found {len(new_pubs)} new publications to insert.")
        batch_insert_rows("inducks_publication", cfg_pub["insert_cols"], new_pubs)
    else:
        print("  -> Publications are already up to date (0 writes).")

    # 2. Issues
    print("\n[diff-sync] Checking inducks_issue...")
    issue_rows_raw = download_isv("inducks_issue")
    if issue_rows_raw and issue_rows_raw[0][0].lower() == "issuecode":
        issue_rows_raw = issue_rows_raw[1:]

    cfg_iss = ISV_TABLES["inducks_issue"]
    idx_iss = cfg_iss["insert_idx"]
    pub_col = 2

    filtered_issues = []
    for row in issue_rows_raw:
        if len(row) < max(idx_iss) + 1:
            continue
        pub_code = row[pub_col].strip()
        if pub_code not in all_pub_codes:
            continue
        values = tuple(row[i].strip() or None for i in idx_iss)
        filtered_issues.append(values)

    existing_issues = set()
    offset = 0
    chunk_size = 50000
    while True:
        rows = query_db(f"SELECT issuecode FROM inducks_issue LIMIT {chunk_size} OFFSET {offset}")
        if not rows:
            break
        for r in rows:
            if r and r[0]:
                existing_issues.add(r[0])
        if len(rows) < chunk_size:
            break
        offset += chunk_size
    print(f"  Existing in Turso: {len(existing_issues)} issues | Target ISV: {len(filtered_issues)}")

    new_issues = [iss for iss in filtered_issues if iss[0] not in existing_issues]
    if new_issues:
        print(f"  -> Found {len(new_issues)} new issues to insert.")
        batch_insert_rows("inducks_issue", cfg_iss["insert_cols"], new_issues)
    else:
        print("  -> Issues are already up to date (0 writes).")

    print("\n[diff-sync] Incremental update completed successfully!")


def main():
    print("[setup] Creating tables and indexes...")
    stmts = [ISV_TABLES["inducks_publication"]["create"],
              ISV_TABLES["inducks_issue"]["create"]] + INDEXES
    execute_batch(stmts)

    print("[setup] Checking existing data...")
    existing_pubs = query_db("SELECT COUNT(*) FROM inducks_publication")
    existing_issues = query_db("SELECT COUNT(*) FROM inducks_issue")
    pub_count = int(existing_pubs[0][0]) if existing_pubs else 0
    issue_count = int(existing_issues[0][0]) if existing_issues else 0
    print(f"  inducks_publication: {pub_count} rows")
    print(f"  inducks_issue:       {issue_count} rows")

    if pub_count > 500 and issue_count > 5000:
        if "--force" not in sys.argv:
            print("[setup] Database already populated. Running smart incremental diff sync...")
            sync_diff()
            return
        print("[setup] --force specified. Performing full re-import...")

    # --- inducks_publication ---
    print("\n[setup] Processing inducks_publication...")
    pub_rows_raw = download_isv("inducks_publication")

    # First row may be headers — skip if looks like a header
    if pub_rows_raw and pub_rows_raw[0][0].lower() == "publicationcode":
        pub_rows_raw = pub_rows_raw[1:]

    cfg = ISV_TABLES["inducks_publication"]
    idx = cfg["insert_idx"]
    country_col = 1  # countrycode is column index 1

    filtered_pubs = []
    all_pub_codes = set()
    for row in pub_rows_raw:
        if len(row) < max(idx) + 1:
            continue
        country = row[country_col].strip().lower()
        if country not in TARGET_COUNTRIES:
            continue
        values = tuple(row[i].strip() or None for i in idx)
        filtered_pubs.append(values)
        all_pub_codes.add(row[0].strip())

    print(f"  Keeping {len(filtered_pubs)} publications for {TARGET_COUNTRIES}")
    batch_insert_rows("inducks_publication", cfg["insert_cols"], filtered_pubs)

    # --- inducks_issue ---
    print("\n[setup] Processing inducks_issue...")
    issue_rows_raw = download_isv("inducks_issue")

    if issue_rows_raw and issue_rows_raw[0][0].lower() == "issuecode":
        issue_rows_raw = issue_rows_raw[1:]

    cfg = ISV_TABLES["inducks_issue"]
    idx = cfg["insert_idx"]
    pub_col = 2  # publicationcode is column index 2 in inducks_issue

    filtered_issues = []
    for row in issue_rows_raw:
        if len(row) < max(idx) + 1:
            continue
        pub_code = row[pub_col].strip()
        if pub_code not in all_pub_codes:
            continue
        values = tuple(row[i].strip() or None for i in idx)
        filtered_issues.append(values)

    print(f"  Keeping {len(filtered_issues)} issues for our countries")
    batch_insert_rows("inducks_issue", cfg["insert_cols"], filtered_issues)

    print("\n[setup] Done!")
    final_pubs = query_db("SELECT COUNT(*) FROM inducks_publication")
    final_issues = query_db("SELECT COUNT(*) FROM inducks_issue")
    print(f"  inducks_publication: {final_pubs[0][0] if final_pubs else '?'} rows")
    print(f"  inducks_issue:       {final_issues[0][0] if final_issues else '?'} rows")


if __name__ == "__main__":
    main()
