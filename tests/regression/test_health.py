"""Regression tests for the source health tracking (src/health.py).

    python -m unittest discover -s tests/regression -v
"""
import unittest

import fake_inducks  # noqa: F401  (puts the repo on sys.path)
from src.health import HEALTH_KEY, has_history, update_provider_health


def run(state, counts, name="Kathimerini GR", prefix="kathi-gr:", alert_after=3):
    """Feeds one count per run; returns the messages each run produced."""
    return [update_provider_health(state, name, prefix, c, alert_after) for c in counts]


class ProviderHealth(unittest.TestCase):
    def test_stub_provider_never_alerts(self):
        # Countries with no scraper yet return [] forever: not a failure.
        state = {}
        self.assertEqual(run(state, [0] * 10, prefix="se:"), [None] * 10)
        self.assertNotIn(HEALTH_KEY, state)

    def test_alert_once_after_n_empty_runs_then_recovery(self):
        state = {"kathi-gr:123": "released"}
        msgs = run(state, [0, 0, 0, 0, 0, 14])
        self.assertEqual(msgs[:2], [None, None])
        self.assertIn("returned nothing for 3 runs", msgs[2])
        self.assertEqual(msgs[3:5], [None, None])  # no repeat while still down
        self.assertIn("is back: 14 item(s) after 5 empty run(s)", msgs[5])
        self.assertEqual(state[HEALTH_KEY], {})

    def test_occasional_empty_run_is_forgotten(self):
        # Panini IT pattern: empty one run in three, never three in a row.
        state = {"panini-it:1": "announced"}
        self.assertEqual(run(state, [0, 0, 5, 0, 5, 0, 0, 5], prefix="panini-it:"), [None] * 8)

    def test_health_key_is_not_history(self):
        state = {HEALTH_KEY: {"X": {"empty_runs": 1, "alerted": False}}}
        self.assertFalse(has_history(state, "_"))


if __name__ == "__main__":
    unittest.main()
