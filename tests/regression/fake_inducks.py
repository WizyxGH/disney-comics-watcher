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

# (publicationcode, title, [(issuenumber, filledoldestdate[, issuecode]), ...], [alternative names])
# The issue code defaults to "<publication> <number>"; Inducks often pads more.
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
    # Panini's "spev" product code is Disney Special Events, variants lettered.
    ("it/DSE",  "Disney Special Events",     [("58", "2026-03-12"), ("58B", "2026-03-31"), ("58C", "2026-03-31"),
                                              ("58D", "2026-12-31"), ("59", "2026-05-31")], []),
    ("it/DMIX", "Disney Mix",                [("39", "2026-06-11"), ("39SP3", "2026-06-30")], []),
    ("it/DKT",  "DuckTales",                 [("1", "1993-05-31"), ("2", "1994-01-31")], []),
    # Paperino Mese is padded to ten characters; "Paperinik" is Panini's
    # it/PPK, while it/PK is a magazine of the 2000s with the same numbers.
    ("it/PM",   "Paperino Mese",             [("99", "1988-09-01", "it/PM   99"), ("551", "2026-04-30", "it/PM  551"),
                                              ("552", "2026-05-29", "it/PM  552")], []),
    ("it/PK",   "Paperinik e altri supereroi", [("119", "2003-08-31", "it/PK  119"), ("139", "2005-04-31", "it/PK  139")], []),
    ("it/PPK",  "Paperinik",                 [("114", "2026-06-05")], []),
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

# Story versions (storyversioncode, storycode, entirepages, rowsperpage) and their
# printings (entrycode, issuecode, storyversioncode, position, part): a serial in two
# parts (I TL 3583-1P), one in five parts printed between other stories in an issue laid
# out like the German LTB (pl/GP 269, I TL 3681-1P), and single stories.
STORY_VERSIONS = [
    ("I TL 3583-1P", "I TL 3583-1P", 52, 3), ("it/TL 3583p009", "I TL 3583-1P", 26, 3),
    ("it/TL 3583p037", "I TL 3583-1P", 26, 3),
    ("I TL 3681-1P", "I TL 3681-1P", 40, 3), ("pl/GP 269p005", "I TL 3681-1P", 20, 3),
    ("pl/GP 269p045", "I TL 3681-1P", 20, 3), ("pl/GP 269p089", "I TL 3681-1P", 20, 3),
    ("pl/GP 269p179", "I TL 3681-1P", 20, 3), ("pl/GP 269p231", "I TL 3681-1P", 24, 3),
    ("I PKA  42-1", "I PKA  42-1", 20, 3), ("I TL 3017-3", "I TL 3017-3", 24, 3),
    ("I TL 3622-1", "I TL 3622-1", 30, 3),
]
ENTRIES = [
    ("it/TL 3583p009", "it/TL 3583", "it/TL 3583p009", "p009", "1"),
    ("it/TL 3583p037", "it/TL 3583", "it/TL 3583p037", "p037", "2"),
    ("pl/GP 269p005", "pl/GP 269", "pl/GP 269p005", "p005", "1"),
    ("pl/GP 269p025", "pl/GP 269", "I PKA  42-1", "p025", ""),
    ("pl/GP 269p045", "pl/GP 269", "pl/GP 269p045", "p045", "2"),
    ("pl/GP 269p065", "pl/GP 269", "I TL 3017-3", "p065", ""),
    ("pl/GP 269p089", "pl/GP 269", "pl/GP 269p089", "p089", "3"),
    ("pl/GP 269p179", "pl/GP 269", "pl/GP 269p179", "p179", "4"),
    ("pl/GP 269p231", "pl/GP 269", "pl/GP 269p231", "p231", "5"),
    ("de/LTB 610p095", "de/LTB 610", "I TL 3622-1", "p095", ""),
]


def _build() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE inducks_publication (publicationcode TEXT, countrycode TEXT, title TEXT);
        CREATE TABLE inducks_publicationname (publicationcode TEXT, publicationname TEXT);
        CREATE TABLE inducks_issue (issuecode TEXT, publicationcode TEXT, issuenumber TEXT,
                                    filledoldestdate TEXT, fullyindexed TEXT);
        CREATE TABLE inducks_story (storycode TEXT);
        CREATE TABLE inducks_storyversion (storyversioncode TEXT, storycode TEXT, entirepages TEXT,
                                           rowsperpage TEXT);
        CREATE TABLE inducks_entry (entrycode TEXT, issuecode TEXT, storyversioncode TEXT,
                                    position TEXT, part TEXT);
    """)
    for code, title, issues, alts in PUBLICATIONS:
        conn.execute("INSERT INTO inducks_publication VALUES (?,?,?)", (code, code.split("/")[0], title))
        for alt in alts:
            conn.execute("INSERT INTO inducks_publicationname VALUES (?,?)", (code, alt))
        for number, date, *issuecode in issues:
            conn.execute("INSERT INTO inducks_issue VALUES (?,?,?,?,?)",
                         (issuecode[0] if issuecode else f"{code} {number}", code, number, date, "N"))
    conn.executemany("INSERT INTO inducks_story VALUES (?)", [(s,) for s in STORIES])
    conn.executemany("INSERT INTO inducks_storyversion VALUES (?,?,?,?)", STORY_VERSIONS)
    conn.executemany("INSERT INTO inducks_entry VALUES (?,?,?,?,?)", ENTRIES)
    return conn


class FakeInducks:
    """Context manager routing every query_db call to the in-memory database."""

    def __enter__(self):
        from src.dbi import isv_search, story_rules
        self.conn = _build()
        query = lambda sql, params=(): self.conn.execute(sql, params).fetchall()
        self.patches = [mock.patch("src.db.query_db", query),
                        mock.patch.object(isv_search, "query_db", query),
                        mock.patch.object(story_rules, "query_db", query)]
        for p in self.patches:
            p.start()
        # The search module caches per country and per publication.
        for name in ("_PUB_CACHE", "_CACHE_LOADED", "_STATS_CACHE", "_MAX_ISSUE_CACHE", "_NEWEST_CACHE", "_CODES_CACHE"):
            if hasattr(isv_search, name):
                getattr(isv_search, name).clear()
        isv_search._DB_HAS_ISSUESCOUNT = None
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.conn.close()
