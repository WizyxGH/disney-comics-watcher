"""Builds a local inducks.db SQLite database from the official Inducks ISV files."""
import sqlite3
import os
import time
import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "inducks.db")

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
