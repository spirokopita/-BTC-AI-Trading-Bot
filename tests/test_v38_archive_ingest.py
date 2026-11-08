"""V38 deterministic provenance, as-of, normalization, gap and source-access tests."""
import unittest
from unittest.mock import patch
from research.v38_archive_ingest import (
    iso, canonical, normalize, merge, asof_visible, join_market, fed_links,
    run, extract_rows, request, source_fetch, official_release_time, DISABLED, MONTHS)

NOW = "2026-11-09T00:00:00+00:00"
def record(source="cryptocurrency_cv", **kwargs):
    return normalize(source, {"url": "https://example.com/a?utm_source=x",
        "title": "An ordinary BTC story", "pub_date": "2022-01-10T12:00:00Z",
        **kwargs}, NOW)

class V38Tests(unittest.TestCase):
    def test_timezone_is_explicit_and_utc(self):
        self.assertEqual(iso("2024-01-31T14:00:00-05:00"),
                         "2024-01-31T19:00:00+00:00")
        self.assertIsNone(iso("2024-01-31"))
        with self.assertRaises(ValueError):
            iso("2024-01-31T14:00:00")
        self.assertEqual(iso("20240131190000"), "2024-01-31T19:00:00+00:00")

    def test_url_dedup_removes_tracking_not_semantic_query(self):
        self.assertEqual(canonical("http://WWW.Example.com/a/?utm_source=feed&id=2#x"),
                         "https://example.com/a?id=2")
        self.assertIsNone(canonical("file:///etc/passwd"))

    def test_historical_api_is_retrospective_only(self):
        r = record(first_seen="2022-01-10T12:03:00Z")
        self.assertEqual(r["source_claimed_first_seen_at_utc"],
                         "2022-01-10T12:03:00+00:00")
        self.assertIsNone(r["first_verified_capture_at_utc"])
        self.assertFalse(asof_visible(r, "2022-01-11T00:00:00Z"))
        self.assertIsNone(r["content_sha256"])

    def test_common_crawl_capture_requires_warc_digest_and_filename(self):
        base = {"url": "https://example.com/a", "timestamp": "20220110120500",
                "digest": "sha1:123", "filename": "crawl-data/CC-MAIN/test.warc.gz",
                "pub_date": "2022-01-10T12:00:00Z"}
        r = normalize("common_crawl", base, NOW)
        self.assertEqual(r["first_verified_capture_at_utc"],
                         "2022-01-10T12:05:00+00:00")
        self.assertTrue(asof_visible(r, "2022-01-10T16:00:00Z"))
        base.pop("digest")
        self.assertFalse(asof_visible(normalize("common_crawl", base, NOW),
                                      "2022-01-10T16:00:00Z"))

    def test_future_capture_is_not_available_earlier(self):
        r = normalize("common_crawl", {"url": "https://example.com/a",
            "pub_date": "2022-01-10T12:00:00Z",
            "timestamp": "20220110160500", "digest": "sha1:xyz",
            "filename": "crawl.warc.gz"}, NOW)
        self.assertFalse(asof_visible(r, "2022-01-10T16:00:00Z"))
        self.assertTrue(asof_visible(r, "2022-01-10T20:00:00Z"))

    def test_future_revision_blocks_asof(self):
        r = normalize("common_crawl", {"url": "https://example.com/a",
            "pub_date": "2022-01-10T12:00:00Z",
            "updated_at": "2022-01-11T12:00:00Z",
            "timestamp": "20220110160500", "digest": "sha1:xyz",
            "filename": "crawl.warc.gz"}, NOW)
        self.assertFalse(asof_visible(r, "2022-01-10T20:00:00Z"))

    def test_versions_not_merged_and_cross_source_url_is_merged(self):
        a = record()
        b = record(source="gdelt")
        c = normalize("common_crawl", {"url": "https://example.com/a",
            "timestamp": "20220110160500", "digest": "sha1:abc",
            "filename": "crawl.warc.gz"}, NOW)
        d = normalize("common_crawl", {"url": "https://example.com/a",
            "timestamp": "20220111160500", "digest": "sha1:def",
            "filename": "crawl.warc.gz"}, NOW)
        m = merge([a, b, c, d])
        self.assertEqual(len(m), 3)
        self.assertEqual(set(m[0]["source_ids"]), {"cryptocurrency_cv", "gdelt"})
        self.assertEqual(sum(bool(x["version_hash"]) for x in m), 2)

    def test_market_alignment_is_not_asof_eligibility(self):
        a = record()
        start = 1641772800  # 2022-01-10 00:00 UTC
        bars = [(start+i*14400, 1, 1, 1, 1, 1) for i in range(20)]
        r = join_market([a], bars)
        self.assertEqual(r["retrospective_time_aligned"], 1)
        self.assertEqual(r["strict_asof_eligible"], 0)
        self.assertEqual(r["examples"][0]["bar_open_utc"],
                         "2022-01-10T12:00:00+00:00")

    def test_gaps_rejected(self):
        bars = [(0, 1), (14400, 1), (43200, 1)]
        with self.assertRaises(ValueError):
            join_market([record()], bars)

    def test_official_fed_date_only_never_invented_release_hour(self):
        page = b'<a href="/newsevents/pressreleases/monetary20240131a.htm">Statement</a>'
        rows = fed_links(page, "fed_press", NOW)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["published_at_utc"])
        self.assertIsNone(rows[0]["first_verified_capture_at_utc"])
        self.assertEqual(len(fed_links(page, "fomc_calendar", NOW)), 1)

    def test_no_network_or_paid_call_for_disabled_sources(self):
        def fake(sid, now):
            if sid in DISABLED:
                return [], "KEY_REQUIRED_OR_RESTRICTED"
            raise AssertionError("unexpected network")
        r = run(source_ids=list(DISABLED), now=NOW, fetcher=fake)
        self.assertEqual(r["deduplicated_rows"], 0)
        self.assertEqual(len(r["source_status"]), len(DISABLED))
        self.assertFalse(r["target_met"])

    def test_partial_source_failure_does_not_fabricate_data(self):
        def fake(sid, now):
            if sid == "gdelt":
                raise OSError("HTTP 429")
            return [record()], "OK"
        r = run(source_ids=("gdelt", "cryptocurrency_cv"), now=NOW, fetcher=fake)
        self.assertEqual(r["raw_normalized_rows"], 1)
        self.assertEqual(r["deduplicated_rows"], 1)
        self.assertIn("HTTP 429", r["source_status"]["gdelt"]["status"])

    def test_response_shape_unknown_rejected(self):
        self.assertEqual(len(extract_rows({"articles": [{"url": "https://x.org"}]})), 1)
        with self.assertRaises(ValueError):
            extract_rows({"total": 1000})

    def test_http_allowlist_blocks_unsafe_hosts(self):
        with self.assertRaises(ValueError):
            request("http://cryptocurrency.cv/api/archive")
        with self.assertRaises(ValueError):
            request("https://evil.example/api")

    def test_sampling_is_predeclared_not_outcome_selected(self):
        self.assertEqual(len(MONTHS), 6)
        self.assertEqual(MONTHS[0], "2020-01")
        self.assertEqual(MONTHS[-1], "2025-01")


    def test_archive_api_uses_supported_date_filters_not_ignored_date_parameter(self):
        def api(url):
            self.assertIn("start_date=2022-01-01", url)
            self.assertIn("end_date=2022-01-31", url)
            self.assertNotIn("?date=", url)
            return {"success": True, "filters": {"start_date": "2022-01-01",
                "end_date": "2022-01-31"}, "articles": [
                {"url": "https://example.com/historical",
                 "pub_date": "2022-01-10T12:00:00Z", "title": "Ordinary story"}]}
        with patch("research.v38_archive_ingest.MONTHS", ("2022-01",)), \
             patch("research.v38_archive_ingest.get_json", side_effect=api):
            rows, status = source_fetch("cryptocurrency_cv", NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(status, "OK_DATE_FILTERS_VERIFIED")

    def test_archive_api_ignoring_date_range_fails_closed(self):
        def ignored(url):
            return {"success": True, "filters": {"start_date": None,
                "end_date": None}, "articles": [
                {"url": "https://example.com/current",
                 "pub_date": "2026-11-08T12:00:00Z"}]}
        with patch("research.v38_archive_ingest.MONTHS", ("2022-01",)), \
             patch("research.v38_archive_ingest.get_json", side_effect=ignored):
            rows, status = source_fetch("cryptocurrency_cv", NOW)
        self.assertEqual(rows, [])
        self.assertIn("did not echo", status)


    def test_original_fed_release_clock_est_and_edt(self):
        est = b'<p>For release at 2:00 p.m. EST</p>'
        edt = b'<p>For release at 2:00 p.m. EDT</p>'
        self.assertEqual(official_release_time(est, "2024-01-31"),
                         "2024-01-31T19:00:00+00:00")
        self.assertEqual(official_release_time(edt, "2024-07-31"),
                         "2024-07-31T18:00:00+00:00")
        self.assertIsNone(official_release_time(b"No release time", "2024-01-31"))

    def test_fed_clock_not_automatically_first_observed(self):
        r = normalize("fomc_calendar", {"url":
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm",
            "date": "2024-01-31"}, NOW)
        r["official_release_at_utc"] = "2024-01-31T19:00:00+00:00"
        self.assertFalse(asof_visible(r, "2024-02-01T00:00:00Z"))


    def test_prearchive_old_news_is_not_mapped_to_first_market_bar(self):
        old = record(pub_date="2020-01-10T12:00:00Z")
        start = 1641772800
        bars = [(start+i*14400, 1, 1, 1, 1, 1) for i in range(20)]
        r = join_market([old], bars)
        self.assertEqual(r["retrospective_time_aligned"], 0)
        self.assertEqual(r["strict_asof_eligible"], 0)


    def test_official_annual_press_archives_are_outcome_independent(self):
        def fake(url):
            year = url.split("/")[-1][:4]
            self.assertIn(year, ("2020", "2022", "2024", "2026"))
            return ('<a href="/newsevents/pressreleases/bcreg' + year +
                    '0123a.htm">Routine banking release</a>').encode()
        with patch("research.v38_archive_ingest.request", side_effect=fake):
            rows, status = source_fetch("fed_press", NOW)
        self.assertEqual(len(rows), 4)
        self.assertTrue(status.startswith("OFFICIAL_ANNUAL_DATE_ONLY"))
        self.assertTrue(all(r["official_event_date_only"] for r in rows))
        self.assertTrue(all(not asof_visible(r, NOW) for r in rows))

if __name__ == "__main__":
    unittest.main()
