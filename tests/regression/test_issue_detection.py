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

    # Panini product codes: "1wspev" once led to the non-existent it/SPEV.
    PANINI = "https://www.panini.it/shp_ita_it/{}-it08.html"

    def test_panini_product_code(self):
        self.assertEqual(self.resolve("PK: Meno Tre all'Alba", "it",
                                      page_url=self.PANINI.format("pk-meno-tre-all-alba-1wspev062sp")),
                         "it/DSE 62")
        self.assertEqual(self.resolve("Zio Paperone 41", "it",
                                      page_url=self.PANINI.format("zio-paperone-41-1wzipa041")),
                         "it/ZPP 41")

    def test_panini_extra_issue_follows_the_product_code(self):
        # The shop titles it "Disney Mix Speciale 43"; Inducks numbers it 41SP3.
        self.assertEqual(self.resolve("Disney Mix Speciale 43", "it",
                                      page_url=self.PANINI.format("disney-mix-speciale-43-1wdmix041sp3")),
                         "it/DMIX 41SP3")

    def test_loose_match_never_lands_on_a_dead_series(self):
        # Was "DKT 3": the DuckTales of 1993-94, two issues.
        self.assertIsNone(self.resolve("Ducktales – Nuova Serie 3", "it"))

    def test_loose_match_never_lands_on_an_old_number(self):
        # Uncle Scrooge is running, but its #3 is from the 1950s.
        self.assertIsNone(self.resolve("Uncle Scrooge Gift Box Set 3", "us"))
        self.assertEqual(self.resolve("Uncle Scrooge Legacy #464", "us"), "us/US 464")

    def test_variant_gets_the_next_free_letter(self):
        # Was "SPEV 62" twice: the variant must not reuse the regular code.
        self.assertEqual(self.resolve("PK: Meno Tre all'Alba – Variant Simone Di Meo", "it",
                                      page_url=self.PANINI.format("pk-meno-tre-all-alba-variant-1wspev062spv")),
                         "it/DSE 62B")
        # 58B to 58D are already taken on Inducks.
        self.assertEqual(self.resolve("PK Early Days 58", "it",
                                      page_url=self.PANINI.format("pk-early-days-1wspev058spv")),
                         "it/DSE 58E")

    # Inducks pads codes: "it/PM 557" (one space) is not found on issue.php.
    def test_issue_code_spaced_as_inducks(self):
        self.assertEqual(self.resolve("Paperino 552", "it"), "it/PM  552")
        self.assertEqual(self.resolve("Paperino 557", "it"), "it/PM  557")
        self.assertEqual(isv_search.issue_code("it/PM", "98"), "it/PM   98")
        self.assertEqual(isv_search.issue_code("it/PM", "1000"), "it/PM 1000")
        # "Tome 04": Inducks numbers it 4.
        self.assertEqual(isv_search.issue_code("it/PM", "0552"), "it/PM  552")

    # Two magazines never share a code: "Paperinik 119" was it/PK 119 (2003).
    def test_new_release_never_takes_an_old_issue_code(self):
        self.assertEqual(self.resolve("Paperinik 119", "it"), "it/PPK 119")
        self.assertIsNone(self.resolve("Paperinik e altri supereroi 119", "it"))

    def test_band_inside_a_word_is_not_a_volume(self):
        self.assertEqual(isv_search._extract_base_and_number("Lustiges Taschenbuch Sonderband 134"),
                         ("Lustiges Taschenbuch Sonderband", "134"))
        self.assertEqual(self.resolve("Lustiges Taschenbuch Sonderband 134", "de"), "de/LTBSP 134")
        self.assertEqual(self.resolve("LTB Band 614", "de"), "de/LTB 614")


if __name__ == "__main__":
    unittest.main()
