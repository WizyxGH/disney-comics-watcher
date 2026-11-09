"""Regression tests for the Inducks button of the notifications (src/notifications.py).

    python -m unittest discover -s tests/regression -v
"""
import unittest
from urllib.parse import parse_qs, urlparse

from fake_inducks import FakeInducks
from src import utils
from src.notifications import inducks_button
from src.utils import cover_filename


class InducksButton(unittest.TestCase):
    def setUp(self):
        self.db = FakeInducks().__enter__()
        utils.does_issue_exist_in_inducks.cache_clear()

    def tearDown(self):
        self.db.__exit__(None, None, None)

    def query(self, button):
        return {k: v[0] for k, v in parse_qs(urlparse(button["url"]).query).items()}

    def test_issue_listed_by_inducks_links_to_its_page(self):
        self.assertEqual(inducks_button("it/TL 3700", "Topolino 3700", "it"),
                         {"text": "View on Inducks", "url": "https://inducks.org/issue.php?c=it%2FTL+3700"})

    # Was issue.php?c=it/PM+557: "The issue code 'it/PM 557' was not found"; then a search,
    # while the publication was known (I Viaggi di Topolino 3): its page lists the issues.
    def test_issue_not_yet_listed_links_to_its_publication(self):
        button = inducks_button("it/PM  557", "Paperino 557", "it", {"date": "30/10/2026"})
        self.assertEqual(button, {"text": "View Publication", "url": "https://inducks.org/publication.php?c=it%2FPM"})
        self.assertEqual(inducks_button("de/LTB 999", "Lustiges Taschenbuch 999", "de")["url"],
                         "https://inducks.org/publication.php?c=de%2FLTB")

    def test_unknown_publication_is_searched_with_what_is_known(self):
        button = inducks_button("it/ZZZ 3", "Zzz 3", "it", {"date": "30/10/2026"})
        self.assertEqual(button["text"], "Search on Inducks")
        self.assertTrue(button["url"].startswith("https://inducks.org/compmag.php?"))
        self.assertEqual(self.query(button), {"country": "it", "title1": "ZZZ", "entrycodeh3": "3", "date2": "2026"})

    # Inducks matches part of the name: "Panini" finds "Disney Italia, Panini Comics".
    def test_publisher_narrows_the_search(self):
        button = inducks_button(None, "Paperinik 119", "it", {"publisher": "Panini"})
        self.assertEqual(self.query(button), {"country": "it", "title1": "Paperinik", "entrycodeh3": "119",
                                              "publisher": "Panini"})

    def test_unknown_publication_is_searched_by_title(self):
        button = inducks_button("it/UNK_314885", "PK Omnibus 7", "it")
        self.assertEqual(self.query(button), {"country": "it", "title1": "PK Omnibus", "entrycodeh3": "7"})
        button = inducks_button(None, "Papereneide", "it")
        self.assertEqual(self.query(button), {"country": "it", "title1": "Papereneide"})

    def test_code_without_space(self):
        button = inducks_button("fi/AA2026-44", "Aku Ankka 44/2026", "fi")
        self.assertEqual(self.query(button), {"country": "fi", "title1": "AA", "entrycodeh3": "2026-44"})

    def test_cvsedit_url_for_new_issue_includes_new_param(self):
        from src.notifications import _get_inputfilename_for_issue
        from urllib.parse import urlencode, quote_plus
        from src.utils import does_issue_exist_in_inducks

        # it/TL 3701 does not exist in fake database
        self.assertFalse(does_issue_exist_in_inducks("it/TL 3701"))
        input_file, input_code = _get_inputfilename_for_issue("it/TL 3701")
        self.assertEqual(input_file, "issues/it/tl2000.dbi")
        self.assertEqual(input_code, "1914")

        params = {
            "inputfilename": input_file,
            "induckscode": "TL 3701",
            "new": "1",
        }
        if input_code:
            params["inputfilecode"] = input_code
        url = f"https://inducks.org/cvsedit.php?{urlencode(params)}"
        self.assertIn("new=1", url)
        self.assertIn("inputfilename=issues%2Fit%2Ftl2000.dbi", url)
        self.assertIn("induckscode=TL+3701", url)
        self.assertIn("inputfilecode=1914", url)

    def test_cvsedit_url_for_existing_issue_uses_issuecode(self):
        from src.utils import does_issue_exist_in_inducks
        from urllib.parse import quote_plus

        # it/TL 3700 exists in fake database
        self.assertTrue(does_issue_exist_in_inducks("it/TL 3700"))
        url = f"https://inducks.org/cvsedit.php?issuecode={quote_plus('it/TL 3700')}"
        self.assertEqual(url, "https://inducks.org/cvsedit.php?issuecode=it%2FTL+3700")


class CoverFilename(unittest.TestCase):
    # A code respaced as Inducks spaces it keeps the cover saved before.
    def test_spacing_does_not_rename_the_cover(self):
        for code in ("PM 557", "PM  557"):
            self.assertEqual(cover_filename(code, "it"), "it_pm_0557a_001")
        for code in ("DBIG 223", "DBIG223"):
            self.assertEqual(cover_filename(code, "it"), "it_dbig_0223a_001")
        self.assertEqual(cover_filename("DSE  62B", "it"), "it_dse_062ba_001")
        self.assertEqual(cover_filename("MM2026-02", "bg"), "bg_mm2026_02a_001")


if __name__ == "__main__":
    unittest.main()
