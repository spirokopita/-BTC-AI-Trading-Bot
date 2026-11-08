"""V38 cumulative archive idempotence, version and no-backdating tests."""
import tempfile
import json
import unittest
from pathlib import Path
from research.v38_persist_sample import build, update, persist

def row(version=None, time="2026-11-09T00:00:00+00:00"):
    return dict(canonical_url="https://example.com/a",
        version_hash=version, source_ids=["cryptocurrency_cv"],
        retrieved_at_utc=time, first_verified_capture_at_utc=None,
        capture_reference=None, availability_confidence="retrospective_only",
        published_at_utc="2022-01-01T00:00:00+00:00",
        official_event_date_only=None, official_release_at_utc=None)

def audit(rows):
    return dict(schema="v38_metadata_provenance_1",
        android_strategy="HOLD",max_paper_entry_aud=100,
        records=rows,deduplicated_rows=len(rows),
        retrieved_at_utc="2026-11-09T00:00:00+00:00",
        source_status={"cryptocurrency_cv":{"fetched_rows":len(rows),"status":"OK"}},
        market_join={"strict_asof_eligible":0})

class V38PersistTests(unittest.TestCase):
    def test_duplicate_retrieval_preserves_earliest_and_latest(self):
        a=row(time="2026-11-08T00:00:00+00:00")
        b=row(time="2026-11-09T00:00:00+00:00")
        x=update([a],[b])
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]["our_first_retrieved_at_utc"],
                         "2026-11-08T00:00:00+00:00")
        self.assertEqual(x[0]["our_last_retrieved_at_utc"],
                         "2026-11-09T00:00:00+00:00")

    def test_distinct_warc_versions_are_not_collapsed(self):
        self.assertEqual(len(update([row("sha1:a")],[row("sha1:b")])),2)

    def test_unverified_first_seen_never_backdates(self):
        a=row()
        a["source_claimed_first_seen_at_utc"]="2022-01-01T00:00:00+00:00"
        rows,manifest=build(audit([a]),[])
        self.assertEqual(manifest["historical_verified_crawl_rows"],0)
        self.assertIsNone(rows[0]["first_verified_capture_at_utc"])

    def test_bad_capture_claim_rejected(self):
        a=row()
        a["availability_confidence"]="verified_crawl"
        with self.assertRaises(ValueError):
            build(audit([a]),[])

    def test_persist_readback_and_idempotence(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"audit.json").write_text(json.dumps(audit([row()])))
            one=persist(p/"audit.json",p/"sample.jsonl",p/"manifest.json")
            two=persist(p/"audit.json",p/"sample.jsonl",p/"manifest.json")
            self.assertEqual(one["rows_sha256"],two["rows_sha256"])
            self.assertEqual(two["rows_cumulative_deduplicated"],1)
            self.assertFalse(two["target_met"])
            self.assertTrue((p/"manifest.json").exists())

    def test_paper_only_guard(self):
        x=audit([row()])
        x["android_strategy"]="BUY"
        with self.assertRaises(ValueError):
            build(x,[])

if __name__=="__main__":unittest.main()
