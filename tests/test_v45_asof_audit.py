import unittest
from research.v45_asof_audit import eligibility_audit
B=dict(url="https://example.org/story",published_at="2023-01-01T00:00:00Z",capture_at="2023-01-02T00:00:00Z",retrieved_at="2026-11-21T00:00:00Z",captured_sha256="a"*64,version_id="1")
class AuditTests(unittest.TestCase):
 def test_publication_is_not_capture(self):
  r=eligibility_audit([B],"2023-01-01T12:00:00Z")
  self.assertEqual(r["future_capture"],1)
  self.assertEqual(r.get("eligible_versions",0),0)
 def test_archive_retrieved_later_still_has_historical_capture(self):
  r=eligibility_audit([B],"2023-01-03T00:00:00Z")
  self.assertEqual(r["eligible_versions"],1)
 def test_dedup_version_count(self):
  r=eligibility_audit([B,dict(B,version_id="2")],"2023-01-03T00:00:00Z")
  self.assertEqual(r["eligible_versions"],2)
  self.assertEqual(r["eligible_unique_urls"],1)
 def test_unproven_rejected(self):
  r=eligibility_audit([dict(B,captured_sha256=None)],"2023-01-03T00:00:00Z")
  self.assertEqual(r["invalid_or_unproven"],1)
 def test_nonfinite_latency(self):
  for v in (-1,float("nan"),float("inf")):
   with self.assertRaises(ValueError): eligibility_audit([B],"2023-01-03T00:00:00Z",v)
