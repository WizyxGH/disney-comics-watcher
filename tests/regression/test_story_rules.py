"""Regression tests for src/dbi/story_rules.py: serials, strips per page and invented codes in
the German LTB skeletons, checked against the official index of LTB 610 and 611.

    python -m unittest discover -s tests/regression -v
"""
import os
import tempfile
import unittest

from fake_inducks import FakeInducks
from src.dbi.generator import generate_dbi_skeleton
from src.dbi.story_rules import apply_story_rules


def story(code, start, pages, title="T"):
    return {"title": title, "story_code": code, "start_page": start, "pages": pages}


class StoryRules(unittest.TestCase):
    def setUp(self):
        self.db = FakeInducks().__enter__()

    def tearDown(self):
        self.db.__exit__(None, None, None)

    def test_serial_split_into_the_parts_other_printings_agree_on(self):
        # LTB 610: lustiges-taschenbuch.de lists Marco Polo once, 52 pages; Inducks: p005 + p031.
        out = apply_story_rules([story("I TL 3583-1P", 5, 52), story("I TL 3622-1", 57, 30)])
        self.assertEqual([(e["start_page"], e["pages"], e.get("part")) for e in out],
                         [(5, 26, "1"), (31, 26, "2"), (57, 30, None)])
        self.assertEqual(out[0].get("pagel"), "3")

    def test_chapters_printed_between_other_stories_and_invented_code(self):
        # LTB 611: "1WTOPO3683", 104 pages from p005, with other stories inside its span.
        stories = [story("1WTOPO3683", 5, 104), story("I PKA  42-1", 25, 20), story("I TL 3017-3", 65, 24),
                   story("", 109, 70), story("", 199, 32)]  # no code: not an anchor
        out = [e for e in apply_story_rules(stories, log=lambda *_: None) if e.get("part")]
        self.assertEqual({e["story_code"] for e in out}, {"I TL 3681-1P"})
        self.assertEqual([(e["start_page"], e["pages"], e["part"]) for e in out],
                         [(5, 20, "1"), (45, 20, "2"), (89, 20, "3"), (179, 20, "4"), (231, 24, "5")])

    def test_single_story_gets_pagel_only_when_its_length_is_kept(self):
        out = apply_story_rules([story("I TL 3622-1", 5, 30), story("I TL 3017-3", 35, 20)])
        self.assertEqual([e.get("pagel") for e in out], ["3", None])
        self.assertTrue(all("part" not in e for e in out))

    def test_unknown_code_without_equivalent_is_left_empty(self):
        out = apply_story_rules([story("ZZ 999", 5, 10), story("I TL 3622-1", 15, 30)], log=lambda *_: None)
        self.assertEqual(out[0]["story_code"], "")


class LtbSkeleton(unittest.TestCase):
    def setUp(self):
        self.db = FakeInducks().__enter__()
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()
        self.db.__exit__(None, None, None)

    def test_columns_and_tags(self):
        from unittest import mock
        info = {"title": "Lustiges Taschenbuch Nr. 613", "issue_path": "de/LTB 613",
                "url": "https://www.lustiges-taschenbuch.de/ausgaben/alle-ausgaben/ltb-613"}
        enriched = dict(info, pages=230, pages_estimated=True, stories=[
            story("I TL 3583-1P", 5, 52, "Marco Polo"), story("I TL 3622-1", 57, 30, "Goofs"),
            story("I TL 3017-3", 87, 104, "Lang")])
        with mock.patch("src.ltb_enricher.enrich_ltb_metadata", lambda i: dict(enriched)):
            lines = generate_dbi_skeleton(info, "de").splitlines()
        self.assertNotIn("[pages:230]", lines[0], "a page count worked out from the last story is not written")
        self.assertEqual(lines[2][:30], "LTB 613p005 I TL 3583-1P  26 3")
        self.assertTrue(lines[2].endswith("Marco Polo [part:1]"))
        self.assertEqual(lines[3][:30], "LTB 613p031 I TL 3583-1P  26 3")
        self.assertEqual(lines[4][:30], "LTB 613p057 I TL 3622-1   30 3")
        self.assertNotIn("[part:", lines[4], "no empty [part:] on a single story")
        self.assertEqual(lines[5][24:28], "    ", "a 3-digit page count leaves the 2-character column")
        self.assertIn("[pages:104]", lines[5])


if __name__ == "__main__":
    unittest.main()
