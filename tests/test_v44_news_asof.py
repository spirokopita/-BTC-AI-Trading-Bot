import unittest
from research.v44_news_asof import asof_versions,seconds,canonical,validate
B=dict(url="https://Example.com/a?utm_source=x",published_at="2023-01-01T00:00:00Z",capture_at="2023-01-02T00:00:00Z",retrieved_at="2023-01-03T00:00:00Z",captured_sha256="a"*64,version_id="1")
class TestProof(unittest.TestCase):
 def test_no_proof(self): self.assertEqual(asof_versions([dict(B,capture_at=None)],"2023-01-04T00:00:00Z"),[])
 def test_publication_not_proof(self): self.assertEqual(asof_versions([B],"2023-01-01T23:59:59Z"),[])
 def test_capture_eligible(self): self.assertEqual(len(asof_versions([B],"2023-01-02T00:00:00Z")),1)
 def test_latency(self): self.assertEqual(asof_versions([B],"2023-01-02T00:00:30Z",60),[])
 def test_future_revision(self):
  newer=dict(B,version_id="2",capture_at="2023-01-05T00:00:00Z",retrieved_at="2023-01-06T00:00:00Z")
  self.assertEqual(asof_versions([B,newer],"2023-01-04T00:00:00Z")[0]["version_id"],"1")
 def test_reject_update_after_capture(self):
  with self.assertRaises(ValueError): validate(dict(B,updated_at="2023-01-04T00:00:00Z"))
 def test_no_naive_clock(self):
  with self.assertRaises(ValueError): seconds("2023-01-01T00:00:00")
 def test_url_dedup(self):
  self.assertEqual(canonical(B["url"]),"https://example.com/a")
  self.assertEqual(len(asof_versions([B,dict(B,url="https://example.com/a")],"2023-01-04T00:00:00Z")),1)
 def test_capture_before_publication(self):
  with self.assertRaises(ValueError): validate(dict(B,capture_at="2022-12-31T00:00:00Z"))
