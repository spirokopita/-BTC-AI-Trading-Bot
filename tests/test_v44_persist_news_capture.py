import json
import tempfile
import unittest
from pathlib import Path

from research.v44_persist_news_capture import merge_capture


class V44PersistCaptureTests(unittest.TestCase):
    def test_idempotent_version_dedup_and_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / "audit.json"
            data = root / "news.jsonl"
            manifest = root / "manifest.json"
            record = {
                "id": "sample",
                "url": "https://www.rba.gov.au/sample",
                "publisher": "RBA",
                "status": "CAPTURED_METADATA_HASH_ONLY",
                "capture_version_hash": "a"*64,
                "body_stored": False,
                "retrieved_at_utc": "2026-11-17T22:48:33Z",
                "first_persisted_observation_at_utc": "2026-11-17T22:48:33Z",
            }
            audit.write_text(json.dumps({
                "schema": "v44_direct_news_capture_1",
                "records": [record],
            }))
            first = merge_capture(audit, data_path=data, manifest_path=manifest)
            second = merge_capture(audit, data_path=data, manifest_path=manifest)
            rows = [json.loads(x) for x in data.read_text().splitlines()]
            stored_manifest = json.loads(manifest.read_text())
            self.assertEqual(first["new_versions_inserted_this_run"], 1)
            self.assertEqual(second["new_versions_inserted_this_run"], 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["observation_count"], 2)
            self.assertEqual(stored_manifest["rows"], 1)
            self.assertEqual(stored_manifest["body_bytes_stored"], 0)
            self.assertEqual(stored_manifest["rows_sha256"], second["rows_sha256"])

    def test_pr_only_observation_is_not_persisted_as_first_seen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / "audit.json"
            data = root / "news.jsonl"
            manifest = root / "manifest.json"
            audit.write_text(json.dumps({
                "schema": "v44_direct_news_capture_1",
                "records": [{
                    "url": "https://www.coindesk.com/sample",
                    "publisher": "CoinDesk",
                    "status": "CAPTURED_METADATA_HASH_ONLY",
                    "capture_version_hash": "b"*64,
                    "body_stored": False,
                    "retrieved_at_utc": "2026-11-17T22:48:33Z",
                    "first_persisted_observation_at_utc": None,
                }],
            }))
            result = merge_capture(audit, data_path=data, manifest_path=manifest)
            self.assertEqual(result["rows"], 0)
            self.assertEqual(result["new_versions_inserted_this_run"], 0)

    def test_unknown_schema_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = Path(temp) / "audit.json"
            audit.write_text(json.dumps({"schema": "unknown", "records": []}))
            with self.assertRaises(ValueError):
                merge_capture(audit, data_path=Path(temp)/"data.jsonl",
                              manifest_path=Path(temp)/"manifest.json")


if __name__ == "__main__":
    unittest.main()
