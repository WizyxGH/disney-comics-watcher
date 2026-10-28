"""An in-memory Inducks database for the regression tests.

Only the columns the watcher reads exist, filled with a hand-picked slice of
the real data: enough homonyms and dead periods to reproduce the cases that
went wrong in production. Nothing here touches the network or Turso.
"""
import os
import sqlite3
import sys
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# (publicationcode, title, [(issuenumber, filledoldestdate), ...], [alternative names])
PUBLICATIONS = [
    # Greece: the Kathimerini magazines are the second period of old titles.
    ("gr/MM",  "Μίκυ Μάους",                [("1", "1966-01-01"), ("646", "1979-03-01"), ("2460", "2013-09-06")], []),
    ("gr/MMB", "Μίκυ Μάους (Περίοδος Β')",   [("629", "2026-06-30"), ("630", "2026-07-10")], []),
    ("gr/KX",  "Κόμιξ",                      [("148", "1997-01-01"), ("303", "2013-08-31")], []),
    ("gr/KXB", "Κόμιξ (Περίοδος Β')",        [("145", "2026-07-30")], []),
    # Italy: a running reprint shares the base title of Topolino, and an
    # alternative name "Io" used to match inside "topolino".
    ("it/TL",   "Topolino (libretto)",       [("3699", "2026-10-01"), ("3700", "2026-10-08")], []),
    ("it/TLRD", "Topolino (ristampa Disney)", [("10", "2026-09-01")], []),
    ("it/BIG",  "Cartonatoni Disney",        [("1", "1990-01-01")], ["Io"]),
    ("it/ZP",   "Zio Paperone",              [("216", "2016-12-01")], []),
    ("it/ZPP",  "Zio Paperone (Panini)",     [("40", "2026-09-01")], []),
    # USA: book titles stack series and subtitles.
    ("us/DMF",  "Disney Masters",            [("7", "2026-01-01")], []),
    ("us/DDKK", "Walt Disney's Donald Duck", [("3", "2015-01-01")], []),
    ("us/US",   "Uncle Scrooge",             [("463", "2026-08-01")], []),
    ("us/DAA",  "The Disney Afternoon Adventures", [("6", "2026-05-01")], []),
    # Bulgaria: same title, one series numbered YYYY-MM.
    ("bg/MA",   "Макрокомикс",               [("30", "2010-01-01")], []),
    ("bg/MAC",  "Макрокомикс",               [("2026-09", "2026-09-01")], []),
    # Germany: "Sonderband" must not be read as "Sonder" + "Band 134".
    ("de/LTB",   "Lustiges Taschenbuch",         [("613", "2026-07-20")], []),
    ("de/LTBSP", "Lustiges Taschenbuch Spezial", [("133", "2026-05-01")], []),
]

STORIES = ["H 2013-227", "I PKA  42-1", "HC DD2025-38"]


def _build() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE inducks_publication (publicationcode TEXT, countrycode TEXT, title TEXT);
        CREATE TABLE inducks_publicationname (publicationcode TEXT, publicationname TEXT);
        CREATE TABLE inducks_issue (issuecode TEXT, publicationcode TEXT, issuenumber TEXT,
                                    filledoldestdate TEXT, fullyindexed TEXT);
        CREATE TABLE inducks_story (storycode TEXT);
    """)
    for code, title, issues, alts in PUBLICATIONS:
        conn.execute("INSERT INTO inducks_publication VALUES (?,?,?)", (code, code.split("/")[0], title))
        for alt in alts:
            conn.execute("INSERT INTO inducks_publicationname VALUES (?,?)", (code, alt))
        for number, date in issues:
            conn.execute("INSERT INTO inducks_issue VALUES (?,?,?,?,?)",
                         (f"{code} {number}", code, number, date, "N"))
    conn.executemany("INSERT INTO inducks_story VALUES (?)", [(s,) for s in STORIES])
    return conn


class FakeInducks:
    """Context manager routing every query_db call to the in-memory database."""

    def __enter__(self):
        from src.dbi import isv_search
        self.conn = _build()
        query = lambda sql, params=(): self.conn.execute(sql, params).fetchall()
        self.patches = [mock.patch("src.db.query_db", query),
                        mock.patch.object(isv_search, "query_db", query)]
        for p in self.patches:
            p.start()
        # The search module caches per country and per publication.
        for name in ("_PUB_CACHE", "_CACHE_LOADED", "_STATS_CACHE", "_MAX_ISSUE_CACHE"):
            if hasattr(isv_search, name):
                getattr(isv_search, name).clear()
        isv_search._DB_HAS_ISSUESCOUNT = None
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.conn.close()
