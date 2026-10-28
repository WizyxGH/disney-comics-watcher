"""Regression tests for the DBI skeletons (src/dbi/generator.py) and the
akuankka.fi story-code mapping (src/scrapers/fi.py).

    python -m unittest discover -s tests/regression -v
"""
import os
import tempfile
import unittest

from fake_inducks import FakeInducks
from src.dbi.generator import generate_dbi_skeleton
from src.scrapers import fi


class DbiSkeleton(unittest.TestCase):
    def setUp(self):
        self.db = FakeInducks().__enter__()
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)  # the generator writes issues/<cc>.dbi here

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()
        self.db.__exit__(None, None, None)

    def test_no_entry_for_a_publication_without_issue_number(self):
        # Was "BIG          h3 Topolino Sosia di Re Sorcio" in production.
        info = {"title": "Topolino Sosia di Re Sorcio", "issue_path": "it/BIG"}
        self.assertIsNone(generate_dbi_skeleton(info, "it"))
        self.assertFalse(os.path.exists(os.path.join("issues", "it.dbi")))

    def test_story_entries_by_page(self):
        info = {"title": "Topolino 3701", "issue_path": "it/TL 3701", "pages": 164,
                "stories": [{"title": "Uno", "story_code": "I TL 3701-1", "pages": 30, "start_page": 5},
                            {"title": "Due", "story_code": "I TL 3701-2", "pages": 20}]}
        lines = generate_dbi_skeleton(info, "it").splitlines()
        self.assertTrue(lines[2].startswith("TL 3701p005 I TL 3701-1"))
        self.assertTrue(lines[3].startswith("TL 3701p035 I TL 3701-2"))

    def test_story_entries_by_letter_when_positions_unknown(self):
        info = {"title": "Aku Ankka 42/26", "issue_path": "fi/AA2026-42", "cover_code": "HC DD2025-38",
                "page_positions_unknown": True,
                "stories": [{"title": "H.A.M.S.T.E.R.I.", "story_code": "H 2013-227", "pages": 1},
                            {"title": "Viikon visa", "story_code": "", "pages": 1}]}
        lines = generate_dbi_skeleton(info, "fi").splitlines()
        self.assertTrue(lines[1].startswith("AA2026-42a  HC DD2025-38"))
        self.assertTrue(lines[2].startswith("AA2026-42b  H 2013-227"))
        self.assertTrue(lines[3].startswith("AA2026-42c "))


class AkuankkaStoryCodes(unittest.TestCase):
    def test_issue_path(self):
        self.assertEqual(fi._issue_path("fi-aa2026-42"), "fi/AA2026-42")
        self.assertEqual(fi._issue_path("fi-aatk561"), "fi/AATK561")

    def test_lost_padding_is_recovered_from_the_database(self):
        with FakeInducks():
            codes = fi._resolve_storycodes(["i-pka-42-1", "h-2013-227", "hc-dd2025-38", "ip-3681-a", "kansi-561"])
        self.assertEqual(codes["i-pka-42-1"], "I PKA  42-1")
        self.assertEqual(codes["h-2013-227"], "H 2013-227")
        self.assertEqual(codes["hc-dd2025-38"], "HC DD2025-38")
        # Site-made serial codes are left blank, never guessed.
        self.assertEqual(codes["ip-3681-a"], "")
        self.assertEqual(codes["kansi-561"], "")


if __name__ == "__main__":
    unittest.main()
