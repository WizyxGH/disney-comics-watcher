"""Regression tests for the Inducks issue-code detection (src/dbi/isv_search.py).

Each case is a title that was once resolved wrongly in production.

    python -m unittest discover -s tests/regression -v
"""
import unittest

from fake_inducks import FakeInducks
from src.dbi import isv_search


class IssueCodeDetection(unittest.TestCase):
    def setUp(self):
        self.db = FakeInducks().__enter__()

    def tearDown(self):
        self.db.__exit__(None, None, None)

    def resolve(self, title, country, **kw):
        return isv_search.search_publication_code(title, country, **kw)

    # A magazine relaunched as a second period keeps its title: the running
    # period wins over the one that ended, even when the old one has the number.
    def test_relaunched_magazine_goes_to_running_period(self):
        self.assertEqual(self.resolve("Μίκυ Μάους #646 ΚΑΤΙ ΚΡΥΒΕΤΑΙ ΣΤΗΝ ΟΜΙΧΛΗ", "gr"), "gr/MMB 646")
        self.assertEqual(self.resolve("Κόμιξ #148", "gr"), "gr/KXB 148")
        self.assertEqual(self.resolve("Zio Paperone 41", "it"), "it/ZPP 41")

    def test_dead_series_kept_when_number_continues_it(self):
        # The dump is behind: 304 directly follows the last known Κόμιξ.
        self.assertEqual(self.resolve("Κόμιξ #304", "gr"), "gr/KX 304")

    def test_curated_series_beats_running_homonym(self):
        self.assertEqual(self.resolve("Topolino 3700", "it"), "it/TL 3700")

    # Without an issue number there is no issue: no "BIG h3" DBI entry.
    def test_title_without_number_resolves_to_nothing(self):
        self.assertIsNone(self.resolve("Topolino Sosia di Re Sorcio", "it"))
        self.assertIsNone(self.resolve("Topolino Speciale", "it",
                                       page_url="https://www.panini.it/shp_ita_it/topolino-1wtopo.html"))

    def test_matches_whole_words_only(self):
        # "io" (an alternative name of it/BIG) is inside "topolino".
        self.assertNotEqual(self.resolve("Topolino Sosia di Re Sorcio 2", "it"), "it/BIG 2")
        self.assertNotEqual(self.resolve("Il mio Topolino 5", "it"), "it/BIG 5")

    def test_series_named_before_the_volume_number(self):
        self.assertEqual(
            self.resolve("Walt Disney's Donald Duck: Duck Avenger Strikes Again: Disney Masters Vol. 8", "us"),
            "us/DMF 8")
        # ...and a leading article does not hide it.
        self.assertEqual(
            self.resolve("Chip 'n Dale Rescue Rangers: Scheme the Impossible Dream: "
                         "Disney Afternoon Adventures Vol. 7", "us"),
            "us/DAA 7")

    def test_number_followed_by_a_subtitle(self):
        self.assertEqual(self.resolve("Uncle Scrooge Legacy #464: The McDuck Journals", "us"), "us/US 464")

    def test_year_month_numbering(self):
        self.assertEqual(self.resolve("Макрокомикс 10/2026", "bg"), "bg/MAC 2026-10")

    def test_band_inside_a_word_is_not_a_volume(self):
        self.assertEqual(isv_search._extract_base_and_number("Lustiges Taschenbuch Sonderband 134"),
                         ("Lustiges Taschenbuch Sonderband", "134"))
        self.assertEqual(self.resolve("Lustiges Taschenbuch Sonderband 134", "de"), "de/LTBSP 134")
        self.assertEqual(self.resolve("LTB Band 614", "de"), "de/LTB 614")


if __name__ == "__main__":
    unittest.main()
