"""V44 Common Crawl URL-key and capture-proof tests."""
import json
import unittest
import urllib.error
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from research.v44_warc_capture_probe import (
    canonical_url, indexes_for_article, probe, url_variants,
)


class V44WarcProbeTests(unittest.TestCase):
    def test_www_scheme_and_trailing_slash_normalize_to_same_urlkey(self):
        self.assertEqual(
            canonical_url("https://www.odaily.news/newsflash/280563/"),
            canonical_url("http://odaily.news/newsflash/280563"),
        )

    def test_alternate_exact_and_prefix_variants_are_bounded(self):
        variants = url_variants("https://odaily.news/newsflash/280563")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0]["match_type"], "exact")
        self.assertEqual(variants[1]["match_type"], "prefix")
        self.assertTrue(all(item["url"].startswith("https://")
                            for item in variants))

    def test_indexes_exclude_prepublication_and_known_failed_indexes(self):
        indexes = [
            {"id": "CC-MAIN-2022-13", "from": "2022-03-01T00:00:00",
             "to": "2022-03-31T00:00:00", "cdx-api": "https://index.commoncrawl.org/a"},
            {"id": "CC-MAIN-2022-21", "from": "2022-05-01T00:00:00",
             "to": "2022-05-31T00:00:00", "cdx-api": "https://index.commoncrawl.org/b"},
            {"id": "CC-MAIN-2022-27", "from": "2022-06-01T00:00:00",
             "to": "2022-06-30T00:00:00", "cdx-api": "https://index.commoncrawl.org/c"},
            {"id": "CC-MAIN-2022-33", "from": "2022-07-01T00:00:00",
             "to": "2022-07-31T00:00:00", "cdx-api": "https://index.commoncrawl.org/d"},
            {"id": "CC-MAIN-2022-40", "from": "2022-08-01T00:00:00",
             "to": "2022-08-31T00:00:00", "cdx-api": "https://index.commoncrawl.org/e"},
        ]
        chosen = indexes_for_article(
            indexes, "2022-04-01T00:00:00Z",
            skip_ids={"CC-MAIN-2022-21", "CC-MAIN-2022-27"},
        )
        self.assertEqual([row["id"] for row in chosen],
                         ["CC-MAIN-2022-33", "CC-MAIN-2022-40"])

    def test_prefix_query_can_return_verified_capture_without_body_fetch(self):
        target = "https://odaily.news/newsflash/280563"
        article = {
            "canonical_url": target,
            "published_at_utc": "2022-04-01T00:00:00Z",
            "source_ids": ["cryptocurrency_cv"],
            "original_publisher": "Odaily",
            "title": "Sample",
        }
        indexes = [{
            "id": "CC-MAIN-2022-33",
            "from": "2022-07-01T00:00:00",
            "to": "2022-07-31T00:00:00",
            "cdx-api": "https://index.commoncrawl.org/CC-MAIN-2022-33-index",
        }]
        calls = []

        def fake_fetch(url):
            calls.append(url)
            query = parse_qs(urlsplit(url).query)
            if query.get("matchType") == ["prefix"]:
                payload = {
                    "timestamp": "20220710123456",
                    "url": target + "/",
                    "digest": "A" * 32,
                    "filename": "crawl-data/CC-MAIN-2022-33/segments/x/warc/file.warc.gz",
                    "status": "200", "mime": "text/html",
                    "offset": "10", "length": "200",
                }
                return (json.dumps(payload) + "\n").encode()
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)

        base = int(datetime(2022, 7, 10, 12, 0,
                             tzinfo=timezone.utc).timestamp())
        bars = [
            (base, 100, 101, 99, 100, 1),
            (base + 14400, 100, 101, 99, 100, 1),
            (base + 28800, 100, 101, 99, 100, 1),
        ]
        result = probe(
            [article], "2026-11-18T00:00:00Z",
            indexes=indexes, fetcher=fake_fetch,
            preferred_url=target, bars=bars,
            market_provenance={"source": "fixture"},
        )
        self.assertEqual(result["verified_capture_versions"], 1)
        row = result["capture_rows"][0]
        self.assertEqual(row["version_hash_algorithm"], "sha1_base32")
        self.assertEqual(row["verified_capture_at_utc"], "2022-07-10T12:34:56Z")
        self.assertFalse(result["body_downloaded"])
        self.assertEqual(result["market_join"]["strict_asof_eligible"], 1)
        self.assertEqual(
            result["market_join"]["matches"][0]["first_tradable_bar_open_utc"],
            "2022-07-10T16:00:00Z",
        )
        self.assertTrue(all("data.commoncrawl.org" not in call for call in calls))
        self.assertLessEqual(result["requests_attempted"], 9)

    def test_bad_digest_and_mismatched_url_are_not_promoted(self):
        target = "https://odaily.news/newsflash/280563"
        article = {"canonical_url": target,
                   "published_at_utc": "2022-04-01T00:00:00Z"}
        index = {"id": "CC-MAIN-2022-33",
                 "from": "2022-07-01T00:00:00",
                 "to": "2022-07-31T00:00:00",
                 "cdx-api": "https://index.commoncrawl.org/test"}
        indexes = [index]
        def fake_fetch(url):
            query = parse_qs(urlsplit(url).query)
            if query.get("matchType") == ["exact"]:
                return (json.dumps({
                    "timestamp": "20220710123456",
                    "url": "https://odaily.news/other",
                    "digest": "A" * 32,
                    "filename": "crawl-data/CC-MAIN-2022-33/segments/x/warc/file.warc.gz",
                    "status": "200", "mime": "text/html",
                    "offset": "10", "length": "200",
                }) + "\n").encode()
            return (json.dumps({
                "timestamp": "20220710123456",
                "url": target,
                "digest": "not-a-digest",
                "filename": "crawl-data/CC-MAIN-2022-33/segments/x/warc/file.warc.gz",
                "status": "200", "mime": "text/html",
                "offset": "10", "length": "200",
            }) + "\n").encode()
        result = probe([article], "2026-11-18T00:00:00Z",
                       indexes=indexes, fetcher=fake_fetch,
                       preferred_url=target)
        self.assertEqual(result["verified_capture_versions"], 0)


if __name__ == "__main__":
    unittest.main()
