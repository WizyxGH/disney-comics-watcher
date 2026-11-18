"""Builds a local inducks.db SQLite database from the official Inducks ISV files."""
import sqlite3
import os
import time
import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "inducks.db")
ISV_BASE = "https://inducks.org/inducks/isv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (DisneyComicsWatcher/1.0)"
)

# Tables read by the DBI story rules and the cover lookup (package inducks-dbi): only the
# columns used. ~490 MB to download, so they are loaded only when INDUCKS_STORY_TABLES_DIR names
# a folder where the files are kept (the watcher workflow caches it for a week).
STORY_TABLES = {
    "inducks_storyversion": ("storyversioncode", "storycode", "entirepages", "rowsperpage"),
    "inducks_entry": ("entrycode", "issuecode", "storyversioncode", "position", "part"),
    "inducks_entryurl": ("entrycode", "sitecode", "pagenumber", "url", "storycode"),
}
# Rows kept: the scans Inducks serves (site "webusers") of a known story, for the cover lookup.
STORY_TABLE_ROWS = {"inducks_entryurl": lambda row: row[1] == "webusers" and row[4] != ""}
STORY_TABLE_MAX_AGE_DAYS = 7


def _fetch_isv_file(
    table: str,
    cache_dir: str,
    max_age_days: float | None = None,
    timeout: tuple = (15, 90),
    retries: int = 4,
) -> str:
    """
    Downloads an ISV file with streaming, retries, backoff, and local disk caching/fallback.
    If the download fails after all retries but an existing cached file exists, falls back to it.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{table}.isv")

    # If cache is valid and fresh according to max_age_days, reuse directly
    if max_age_days is not None and os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < max_age_days * 86400:
            return path

    url = f"{ISV_BASE}/{table}.isv"
    headers = {"User-Agent": USER_AGENT}
    part_path = path + ".part"
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading {table}.isv (attempt {attempt}/{retries}) ...")
            with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(part_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            os.replace(part_path, path)
            return path
        except Exception as e:
            last_err = e
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            if attempt < retries:
                wait_s = attempt * 3
                print(f"  [warn] Download of {table}.isv attempt {attempt} failed ({e}). Retrying in {wait_s}s...")
                time.sleep(wait_s)
            else:
                print(f"  [warn] All {retries} download attempts failed for {table}.isv: {e}")

    # Fallback to existing cached file if available
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"  [notice] Using cached copy of {table}.isv ({path}) as fallback.")
        return path

    raise last_err


def _story_table_file(table: str, cache_dir: str) -> str:
    return _fetch_isv_file(table, cache_dir, max_age_days=STORY_TABLE_MAX_AGE_DAYS, timeout=(30, 300))


def _load_story_tables(cur, cache_dir: str) -> None:
    for table, columns in STORY_TABLES.items():
        path = _story_table_file(table, cache_dir)
        cur.execute(f"CREATE TABLE {table} ({', '.join(c + ' TEXT' for c in columns)})")
        with open(path, encoding="utf-8", errors="replace") as f:
            header = f.readline().rstrip("\r\n").split("^")
            index = [header.index(c) for c in columns]
            rows = (tuple(cells[i] if i < len(cells) else "" for i in index)
                    for cells in (line.rstrip("\r\n").split("^") for line in f) if len(cells) > 1)
            keep = STORY_TABLE_ROWS.get(table)
            if keep:
                rows = (row for row in rows if keep(row))
            cur.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(columns))})", rows)
        print(f"  -> {table} imported.")
    cur.execute("CREATE INDEX idx_sv_storycode ON inducks_storyversion(storycode)")
    cur.execute("CREATE INDEX idx_sv_code ON inducks_storyversion(storyversioncode)")
    cur.execute("CREATE INDEX idx_entry_sv ON inducks_entry(storyversioncode)")
    cur.execute("CREATE INDEX idx_entry_issue ON inducks_entry(issuecode)")
    cur.execute("CREATE INDEX idx_entryurl_story ON inducks_entryurl(storycode)")
    cur.execute("CREATE INDEX idx_entryurl_entry ON inducks_entryurl(entrycode)")


def build():
    t_start = time.time()
    print(f"Building {DB_PATH} ...")
    
    tmp_path = DB_PATH + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    cache_dir = os.environ.get("INDUCKS_STORY_TABLES_DIR") or os.path.join(os.path.dirname(__file__), ".inducks-cache")
    os.makedirs(cache_dir, exist_ok=True)

    con = sqlite3.connect(tmp_path)
    cur = con.cursor()
    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA journal_mode = MEMORY")

    cur.execute("""CREATE TABLE inducks_publication (
        publicationcode TEXT PRIMARY KEY,
        countrycode     TEXT NOT NULL,
        title           TEXT,
        issuescount     INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE inducks_publicationname (
        publicationcode TEXT NOT NULL,
        publicationname TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE inducks_issue (
        issuecode       TEXT PRIMARY KEY,
        publicationcode TEXT NOT NULL,
        issuenumber     TEXT,
        title           TEXT,
        fullyindexed    TEXT
    )""")
    cur.execute("""CREATE TABLE inducks_story (
        storycode       TEXT PRIMARY KEY
    )""")

    # 1. Publications
    path_pub = _fetch_isv_file("inducks_publication", cache_dir)
    with open(path_pub, encoding="utf-8", errors="replace") as f:
        _ = f.readline()
        pubs = []
        for line in f:
            parts = line.rstrip("\r\n").split("^")
            if len(parts) > 1:
                pubs.append((parts[0], parts[1], parts[3] if len(parts) > 3 else ""))
        cur.executemany("INSERT OR REPLACE INTO inducks_publication (publicationcode, countrycode, title) VALUES (?, ?, ?)", pubs)
        con.commit()
        print(f"  -> {len(pubs)} publications imported.")

    # 2. Publication names (optional/lenient)
    try:
        path_pn = _fetch_isv_file("inducks_publicationname", cache_dir, timeout=(15, 45))
        with open(path_pn, encoding="utf-8", errors="replace") as f:
            _ = f.readline()
            pubnames = []
            for line in f:
                parts = line.rstrip("\r\n").split("^")
                if len(parts) > 1:
                    pubnames.append((parts[0], parts[1]))
            cur.executemany("INSERT INTO inducks_publicationname VALUES (?, ?)", pubnames)
            con.commit()
            print(f"  -> {len(pubnames)} alternative publication names imported.")
    except Exception as e:
        print(f"  [warn] Failed to download or import inducks_publicationname.isv: {e}")

    # 3. Issues
    path_issue = _fetch_isv_file("inducks_issue", cache_dir, timeout=(20, 120))
    with open(path_issue, encoding="utf-8", errors="replace") as f:
        _ = f.readline()
        issues = []
        for line in f:
            parts = line.rstrip("\r\n").split("^")
            if len(parts) > 2:
                issues.append((
                    parts[0],
                    parts[2],
                    parts[3] if len(parts) > 3 else "",
                    parts[4] if len(parts) > 4 else "",
                    parts[11] if len(parts) > 11 else ""
                ))
        cur.executemany("INSERT OR REPLACE INTO inducks_issue VALUES (?, ?, ?, ?, ?)", issues)
        con.commit()
        print(f"  -> {len(issues)} issues imported.")

    # 4. Story tables (if requested)
    story_dir = os.environ.get("INDUCKS_STORY_TABLES_DIR")
    if story_dir:
        try:
            _load_story_tables(cur, story_dir)
            con.commit()
        except Exception as e:  # the watcher still works without them, only the story rules are off
            print(f"  [warn] Story tables not loaded: {e}")

    print("Computing publication issue counts ...")
    cur.execute("""
        CREATE TEMP TABLE _issue_counts AS
        SELECT publicationcode, COUNT(*) AS cnt FROM inducks_issue GROUP BY publicationcode
    """)
    cur.execute("""
        UPDATE inducks_publication
        SET issuescount = COALESCE((
            SELECT cnt FROM _issue_counts WHERE _issue_counts.publicationcode = inducks_publication.publicationcode
        ), 0)
    """)
    cur.execute("DROP TABLE _issue_counts")

    print("Creating indexes ...")
    cur.execute("CREATE INDEX idx_pub_country ON inducks_publication(countrycode)")
    cur.execute("CREATE INDEX idx_issue_pub   ON inducks_issue(publicationcode)")
    cur.execute("CREATE INDEX idx_issue_pub_num ON inducks_issue(publicationcode, issuenumber)")
    cur.execute("CREATE INDEX idx_issue_clean ON inducks_issue(LOWER(REPLACE(issuecode, ' ', '')))")
    cur.execute("CREATE INDEX idx_pubname_code ON inducks_publicationname(publicationcode)")
    cur.execute("CREATE INDEX idx_pubname_name ON inducks_publicationname(LOWER(publicationname))")
    con.commit()
    con.close()

    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
    os.replace(tmp_path, DB_PATH)
    
    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"Success! {DB_PATH} built in {time.time() - t_start:.2f}s ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build()
