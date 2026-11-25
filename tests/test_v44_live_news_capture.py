import hashlib
import unittest

from research.v44_live_news_capture import (
    SPECS, capture_one, next_4h_open, run,
)

BODY = (
    b'<html><head><title>Example page</title>'
    b'<meta property="og:url" content="https://www.rba.gov.au/example">'
    b'<meta property="article:modified_time" content="2026-11-17T00:35:00Z">'
    b'</head><body>' + b'x'*600 + b'</body></html>'
)


def ok_fetch(url):
    return {
        "status": 200,
        "final_url": url,
        "headers": {"Last-Modified": "Tue, 17 Nov 2026 00:35:00 GMT"},
        "body": BODY,
    }


class V44LiveNewsCaptureTests(unittest.TestCase):
    def test_hashes_exact_response_and_does_not_store_body(self):
        row = capture_one(
            SPECS[0], ok_fetch, retrieved_at_utc="2026-11-17T22:48:33Z",
            workflow_event="push", workflow_ref="refs/heads/main",
            workflow_run_id="12345",
        )
        self.assertEqual(row["status"], "CAPTURED_METADATA_HASH_ONLY")
        self.assertEqual(row["capture_version_hash"], hashlib.sha256(BODY).hexdigest())
        self.assertFalse(row["body_stored"])
        self.assertNotIn("body", row)
        self.assertEqual(row["publisher_updated_at_utc"], "2026-11-17T00:35:00Z")
        self.assertEqual(row["first_persisted_observation_at_utc"], "2026-11-17T22:48:33Z")
        self.assertFalse(row["strict_historical_backtest_eligible"])

    def test_pr_validation_does_not_claim_persisted_first_observation(self):
        row = capture_one(
            SPECS[1], ok_fetch, retrieved_at_utc="2026-11-17T22:48:33Z",
            workflow_event="pull_request", workflow_ref="refs/pull/1/merge",
        )
        self.assertIsNone(row["first_persisted_observation_at_utc"])
        self.assertIn("PR validation", row["first_persisted_observation_scope"])

    def test_publication_time_is_not_retrieval_time(self):
        row = capture_one(
            SPECS[1], ok_fetch, retrieved_at_utc="2026-11-17T22:48:33Z",
            workflow_event="push", workflow_ref="refs/heads/main",
        )
        self.assertEqual(row["published_at_utc"], "2026-11-17T11:36:00Z")
        self.assertNotEqual(row["published_at_utc"], row["retrieved_at_utc"])
        self.assertEqual(row["prospective_market_available_at_utc"], row["retrieved_at_utc"])

    def test_redirect_outside_allowlist_fails_closed(self):
        def bad_redirect(url):
            return {"status": 200, "final_url": "https://evil.example/page",
                    "headers": {}, "body": BODY}
        row = capture_one(SPECS[0], bad_redirect,
                          retrieved_at_utc="2026-11-17T22:48:33Z")
        self.assertEqual(row["status"], "FETCH_FAILED")
        self.assertIsNone(row["capture_version_hash"])

    def test_http_failure_is_recorded_not_hidden(self):
        def bad_status(url):
            return {"status": 503, "final_url": url, "headers": {}, "body": BODY}
        row = capture_one(SPECS[0], bad_status,
                          retrieved_at_utc="2026-11-17T22:48:33Z")
        self.assertEqual(row["status"], "FETCH_FAILED")
        self.assertIn("non-200", row["failure"])

    def test_next_eligible_bar_is_strictly_after_capture(self):
        self.assertEqual(next_4h_open("2026-11-17T22:48:33Z"),
                         "2026-11-18T00:00:00Z")
        self.assertEqual(next_4h_open("2026-11-18T00:00:00Z"),
                         "2026-11-18T04:00:00Z")

    def test_run_preserves_all_source_roles(self):
        report = run(ok_fetch, retrieved_at_utc="2026-11-17T22:48:33Z",
                     workflow_event="push", workflow_ref="refs/heads/main")
        self.assertEqual(report["record_count"], 4)
        self.assertEqual(report["captured_count"], 4)
        self.assertEqual(report["failed_count"], 0)
        self.assertEqual(report["records"][1]["event_cluster_id"], report["records"][2]["event_cluster_id"])
        self.assertEqual(len({row["capture_version_hash"] for row in report["records"]}), 1)
        self.assertTrue(all(not row["strict_historical_backtest_eligible"]
                            for row in report["records"]))


if __name__ == "__main__":
    unittest.main()
