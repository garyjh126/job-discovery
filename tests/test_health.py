"""Offline tests for the sweep health check in daily.py. Run from the repo root: python3 -m unittest"""
import unittest

import daily

HIT = dict(title="ML Engineer", location="Dublin", type="", date="", url="https://example.com/1")


def run(results, missing=()):
    return {"results": results, "missing": list(missing)}


class Health(unittest.TestCase):
    def test_healthy_sweep_has_no_problems(self):
        today = run({"Acme": {"total": 5, "hits": [HIT]}})
        self.assertEqual(daily.health(today, today, 1), [])

    def test_board_that_failed_since_yesterday(self):
        yesterday = run({"Acme": {"total": 5, "hits": [HIT]}, "Beta": {"total": 3, "hits": []}})
        today = run({"Acme": {"total": 5, "hits": [HIT]}}, missing=["Beta"])
        problems = daily.health(today, yesterday, 2)
        self.assertIn("1 of 2 boards could not be read: Beta", problems)
        self.assertIn("Readable yesterday, failed today: Beta", problems)

    def test_board_that_dropped_to_zero_roles(self):
        yesterday = run({"Acme": {"total": 5, "hits": [HIT]}, "Beta": {"total": 3, "hits": []}})
        today = run({"Acme": {"total": 5, "hits": [HIT]}, "Beta": {"total": 0, "hits": []}})
        self.assertEqual(daily.health(today, yesterday, 2),
                         ["Board read but now lists 0 open roles (moved or broken?): Beta"])

    def test_no_matches_anywhere_means_broken_filters(self):
        today = run({"Acme": {"total": 5, "hits": []}})
        self.assertEqual(daily.health(today, None, 1),
                         ["No matching roles on any board: the sweep or the filters are probably broken"])


if __name__ == "__main__":
    unittest.main()
