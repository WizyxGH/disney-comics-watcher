"""Regression tests for DBI prices and the Iceland (Edda) source.

    python -m unittest discover -s tests/regression -v
"""
import unittest
from unittest import mock

import fake_inducks  # noqa: F401  (puts the repo on sys.path)
from src.dbi.utils import _format_price_for_dbi
from src.scrapers import isl


class PriceFormat(unittest.TestCase):
    def test_currency_from_symbol_or_code(self):
        cases = {
            "5,90 €": "5.90 EUR",
            "$4.99": "4.99 USD",
            # "R$" contains "$": Panini BR prices used to come out as USD.
            "R$ 10,90": "10.90 BRL",
            "19,99 zł": "19.99 PLN",
            "£5.99": "5.99 GBP",
            "12.99 PLN": "12.99 PLN",
            # Whole-unit currency, only when the scraper names it.
            "1850 ISK": "1850 ISK",
            "12": None,
            # Icelandic thousands separator must not read as 1.85.
            "1.850.-": None,
        }
        for raw, expected in cases.items():
            self.assertEqual(_format_price_for_dbi(raw), expected, raw)


_EDDA_HTML = """<ul class="productgrid clearfix">
<li><div class="clearfix"><div class="picture"><a href="/Vara/?categoryid=c&productid=d1f7893f-fc43-4aa6-bf03-888543b0e19d">
<img src="/library/Syrpa/Syrpa 401.jpg?proc=x" alt="" /></a></div><div class="info"><h3>
<a href="/Vara/?categoryid=c&productid=d1f7893f-fc43-4aa6-bf03-888543b0e19d" class="productTitle">Syrpa 401 &#8211; T&#253;ndur &#225; tunglinu</a></h3>
<p class="price">Ver&#240;. <span>1.850.-</span></p></div></div></li>
<li><div class="clearfix"><div class="info"><h3>
<a href="/Vara/?categoryid=c&productid=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" class="productTitle">RISASYRPA &#8211; Risae&#240;lur</a></h3>
<p class="price">Ver&#240;. <span>2.995.-</span></p></div></div></li>
<li><div class="clearfix"><div class="info"><h3>
<a href="/Vara/?categoryid=c&productid=bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee" class="productTitle">J&#211;LASYRPA 2025</a></h3>
<p class="price">Ver&#240;. <span>2.999.-</span></p></div></div></li>
</ul>"""


class EddaIceland(unittest.TestCase):
    def test_discover_maps_titles_to_inducks_codes(self):
        resp = mock.Mock(text=_EDDA_HTML, raise_for_status=lambda: None)
        with mock.patch.object(isl, "get_session") as session:
            session.return_value.get.return_value = resp
            items = isl.discover_is()
        self.assertEqual([i["issue_path"] for i in items], ["is/MS 401", None, "is/JS2025"])
        self.assertEqual(items[0]["title"], "Syrpa 401 – Týndur á tunglinu")
        self.assertEqual(items[0]["price"], "1850 ISK")
        self.assertEqual(items[0]["id"], "d1f7893f-fc43-4aa6-bf03-888543b0e19d")
        self.assertTrue(items[0]["cover_url"].endswith("/library/Syrpa/Syrpa 401.jpg"))


if __name__ == "__main__":
    unittest.main()
