"""Builds a local inducks.db SQLite database from the official Inducks ISV files."""
import sqlite3
import os
import time
import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "inducks.db")
ISV_BASE = "https://inducks.org/inducks/isv"

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


def _story_table_file(table: str, cache_dir: str) -> str:
    path = os.path.join(cache_dir, f"{table}.isv")
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < STORY_TABLE_MAX_AGE_DAYS * 86400
    if not fresh:
        print(f"Downloading {table}.isv ...")
        os.makedirs(cache_dir, exist_ok=True)
        with requests.get(f"{ISV_BASE}/{table}.isv", stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.replace(path + ".part", path)
    return path


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

def build():
    t_start = time.time()
    print(f"Building {DB_PATH} ...")
    
    tmp_path = DB_PATH + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

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

    print("Downloading inducks_publication.isv ...")
    r = requests.get("https://inducks.org/inducks/isv/inducks_publication.isv", timeout=45)
    lines = [l.split("^") for l in r.text.splitlines() if l.strip()]
    pubs = [(l[0], l[1], l[3] if len(l) > 3 else "") for l in lines[1:] if len(l) > 1]
    cur.executemany("INSERT OR REPLACE INTO inducks_publication (publicationcode, countrycode, title) VALUES (?, ?, ?)", pubs)
    con.commit()
    print(f"  -> {len(pubs)} publications imported.")

    print("Downloading inducks_publicationname.isv ...")
    try:
        r_pn = requests.get("https://inducks.org/inducks/isv/inducks_publicationname.isv", timeout=30)
        lines_pn = [l.split("^") for l in r_pn.text.splitlines() if l.strip()]
        pubnames = [(l[0], l[1]) for l in lines_pn[1:] if len(l) > 1]
        cur.executemany("INSERT INTO inducks_publicationname VALUES (?, ?)", pubnames)
        con.commit()
        print(f"  -> {len(pubnames)} alternative publication names imported.")
    except Exception as e:
        print(f"  [warn] Failed to download inducks_publicationname.isv: {e}")

    print("Downloading inducks_issue.isv ...")
    r = requests.get("https://inducks.org/inducks/isv/inducks_issue.isv", timeout=90)
    lines = [l.split("^") for l in r.text.splitlines() if l.strip()]
    issues = [
        (l[0], l[2], l[3] if len(l) > 3 else "", l[4] if len(l) > 4 else "", l[11] if len(l) > 11 else "")
        for l in lines[1:] if len(l) > 2
    ]
    cur.executemany("INSERT OR REPLACE INTO inducks_issue VALUES (?, ?, ?, ?, ?)", issues)
    con.commit()
    print(f"  -> {len(issues)} issues imported.")

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
