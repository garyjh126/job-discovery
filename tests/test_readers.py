"""Offline tests for the job-board readers in ats_sweep.py. Run from the repo root: python3 -m unittest"""
import datetime, io, json, unittest
from unittest import mock

import ats_sweep


class FakeResponse(io.BytesIO):
    """What urlopen returns, for the readers that call it directly (Workday, Personio)."""
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Readers(unittest.TestCase):
    def test_greenhouse(self):
        board = {"jobs": [{"title": "ML Engineer", "location": {"name": "Dublin"},
                           "updated_at": "2026-10-01T10:00:00Z", "absolute_url": "https://example.com/1"}]}
        with mock.patch.object(ats_sweep, "get", return_value=board):
            self.assertEqual(ats_sweep.greenhouse("acme"), [dict(
                title="ML Engineer", location="Dublin", type="", date="2026-10-01", url="https://example.com/1")])

    def test_unreadable_board_returns_none(self):
        with mock.patch.object(ats_sweep, "get", return_value=None):
            for reader in (ats_sweep.greenhouse, ats_sweep.lever, ats_sweep.ashby, ats_sweep.workable):
                self.assertIsNone(reader("acme"), reader.__name__)

    def test_lever_falls_back_to_eu_host(self):
        posting = {"text": "Backend Engineer", "categories": {"location": "Berlin", "commitment": "Contract"},
                   "workplaceType": "remote", "createdAt": 1790848800000, "hostedUrl": "https://example.com/2"}
        get = mock.Mock(side_effect=lambda url: [posting] if "api.eu.lever.co" in url else None)
        with mock.patch.object(ats_sweep, "get", get):
            jobs = ats_sweep.lever("acme")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(jobs, [dict(title="Backend Engineer", location="Berlin / remote", type="Contract",
                                     date="2026-10-01", url="https://example.com/2")])

    def test_ashby_lists_secondary_locations_and_remote(self):
        board = {"jobs": [{"title": "Research Engineer", "location": "London",
                           "secondaryLocations": [{"location": "Paris"}], "isRemote": True,
                           "employmentType": "FullTime", "publishedAt": "2026-10-02T08:00:00Z",
                           "jobUrl": "https://example.com/3"}]}
        with mock.patch.object(ats_sweep, "get", return_value=board):
            self.assertEqual(ats_sweep.ashby("acme")[0]["location"], "London / Paris / Remote")

    def test_workday_reads_every_page(self):
        # Workday reports the total only on the first page; later pages say 0. The reader once
        # stopped after 40 roles because of that.
        def urlopen(req, timeout):
            offset = json.loads(req.data)["offset"]
            n = min(20, 45 - offset)
            page = {"total": 45 if offset == 0 else 0,
                    "jobPostings": [{"title": f"Job {offset + i}", "locationsText": "Dublin",
                                     "postedOn": "Posted 3 Days Ago", "externalPath": f"/job/{offset + i}"}
                                    for i in range(n)]}
            return FakeResponse(json.dumps(page).encode())

        with mock.patch.object(ats_sweep.urllib.request, "urlopen", urlopen):
            jobs = ats_sweep.workday("acme.wd1/acme/External")
        self.assertEqual(len(jobs), 45)
        self.assertEqual(jobs[0]["url"], "https://acme.wd1.myworkdayjobs.com/en-US/External/job/0")
        self.assertEqual(jobs[0]["date"], (datetime.date.today() - datetime.timedelta(days=3)).isoformat())

    def test_personio(self):
        xml = (b"<workzag-jobs><position><id>7</id><name>C++ Developer</name><office>Munich</office>"
               b"<employmentType>permanent</employmentType><schedule>full-time</schedule>"
               b"<createdAt>2026-09-30T09:00:00+00:00</createdAt></position></workzag-jobs>")
        with mock.patch.object(ats_sweep.urllib.request, "urlopen", return_value=FakeResponse(xml)):
            self.assertEqual(ats_sweep.personio("acme"), [dict(
                title="C++ Developer", location="Munich", type="permanent full-time", date="2026-09-30",
                url="https://acme.jobs.personio.de/job/7")])


class Filters(unittest.TestCase):
    def sweep(self, jobs):
        with mock.patch.dict(ats_sweep.FN, {"gh": lambda token: jobs}), \
             mock.patch.object(ats_sweep.sys, "argv", ["ats_sweep.py"]):
            return ats_sweep.run("gh acme Acme Corp")

    def test_keeps_matching_title_and_location(self):
        job = lambda title, location: dict(title=title, location=location, type="", date="", url="")
        name, (total, hits) = self.sweep([
            job("Senior Machine Learning Engineer", "Dublin"),  # kept
            job("Machine Learning Intern", "Dublin"),           # excluded: intern
            job("Account Executive", "London"),                 # not a target title
            job("Backend Engineer", "Austin, TX"),              # location outside the filter
        ])
        self.assertEqual((name, total), ("Acme Corp", 4))
        self.assertEqual([h["title"] for h in hits], ["Senior Machine Learning Engineer"])

    def test_unreadable_board_is_reported(self):
        self.assertEqual(self.sweep(None), ("Acme Corp", None))


if __name__ == "__main__":
    unittest.main()
