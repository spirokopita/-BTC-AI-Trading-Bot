import unittest
from research.v48_news_proof_gate import classify,join
R=dict(url="https://example.org/a",capture_type="independent_warc",
 published_at_utc="2023-01-01T00:00:00Z",updated_at_utc="2023-01-01T00:00:00Z",
 verified_capture_at_utc="2023-01-01T01:00:00Z",
 retrieved_at_utc="2026-11-15T00:00:00Z",content_sha256="a"*64,
 version_capture_sha256="a"*64)
class TestAsOf(unittest.TestCase):
 def test_before_capture_blocked(self):
  self.assertFalse(classify(R,"2023-01-01T01:59:59Z")["eligible"])
 def test_after_capture_latency_allowed(self):
  self.assertTrue(classify(R,"2023-01-01T02:00:00Z")["eligible"])
 def test_retro_publication_only_blocked(self):
  r=dict(R,capture_type="retrospective_published_at")
  self.assertEqual(classify(r,"2025-01-01T00:00:00Z")["reason"],"NO_INDEPENDENT_CAPTURE_PROOF")
 def test_future_update_blocked(self):
  r=dict(R,updated_at_utc="2024-01-01T00:00:00Z")
  self.assertFalse(classify(r,"2023-01-02T00:00:00Z")["eligible"])
 def test_version_mismatch_blocked(self):
  r=dict(R,version_capture_sha256="b"*64)
  self.assertFalse(classify(r,"2025-01-01T00:00:00Z")["eligible"])
 def test_missing_hash_blocked(self):
  r=dict(R,content_sha256="")
  self.assertFalse(classify(r,"2025-01-01T00:00:00Z")["eligible"])
 def test_join_no_lookahead(self):
  bars=["2023-01-01T01:00:00Z","2023-01-01T05:00:00Z"]
  rows=join([R],bars)
  self.assertEqual([len(x["verified_urls"]) for x in rows],[0,1])
 def test_monotonic_bars(self):
  with self.assertRaises(ValueError):join([R],[1,1])
 def test_gap_or_irregular_4h_spacing_rejected(self):
  with self.assertRaises(ValueError):
   join([R],["2023-01-01T01:00:00Z","2023-01-01T09:00:00Z"])
 def test_non_hex_hash_rejected(self):
  r=dict(R,content_sha256="z"*64,version_capture_sha256="z"*64)
  self.assertEqual(classify(r,"2025-01-01T00:00:00Z")["reason"],"NO_VERSION_HASH")
 def test_non_https_url_rejected(self):
  r=dict(R,url="http://example.org/a")
  self.assertEqual(classify(r,"2025-01-01T00:00:00Z")["reason"],"INVALID_URL")
if __name__=="__main__":unittest.main()
