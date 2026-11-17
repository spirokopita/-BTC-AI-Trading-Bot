"""V44: capture current RBA and CoinDesk page versions for prospective PAPER use.

Stores only response hashes and provenance metadata; no copyrighted article body.
A direct fetch proves what this connector observed at retrieval time, not when the
internet first saw the page. Publication timestamps are never substituted for
first-observed or capture time. Historical use remains fail-closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES = 4_000_000
USER_AGENT = "BTC-AUD-PAPER-research/44 (+https://github.com/spirokopita/-BTC-AI-Trading-Bot)"
SPECS = (
    {
        "id": "rba_november_2026_minutes",
        "event_cluster_id": "RBA_NOVEMBER_2026_MINUTES",
        "url": "https://www.rba.gov.au/monetary-policy/rba-board-minutes/2026/2026-11-03.html",
        "publisher": "Reserve Bank of Australia",
        "role": "official_macro_minutes",
        "published_at_utc": "2026-11-17T00:30:00Z",
        "publication_time_basis": "RBA official calendar: 17 Nov 2026 11:30 AEDT (UTC+11)",
        "release_time_source_url": "https://www.rba.gov.au/schedules-events/calendar/",
        "causal_degree_hypothesis": 2,
        "btc_usd_channel": "policy expectations / real yields / global risk appetite",
        "aud_usd_channel": "Australian policy-rate expectations and AUD repricing",
        "btc_aud_channel": "BTC/USD numerator less AUD/USD denominator; net sign ambiguous",
    },
    {
        "id": "coindesk_btc_etf_flow_2026_11_17",
        "event_cluster_id": "US_BTC_ETF_FLOWS_2026_11_16",
        "url": "https://www.coindesk.com/markets/2026/11/17/bitcoin-remains-penned-in-near-usd64-000-even-as-etf-outflow-streak-ends",
        "publisher": "CoinDesk",
        "role": "crypto_etf_flows_and_market_structure",
        "published_at_utc": "2026-11-17T11:36:00Z",
        "publication_time_basis": "CoinDesk page byline: 17 Nov 2026 6:36 a.m. EST (UTC-5)",
        "release_time_source_url": None,
        "causal_degree_hypothesis": 1,
        "btc_usd_channel": "reported spot ETF flows and derivatives positioning may affect marginal BTC demand",
        "aud_usd_channel": "no direct FX sign hypothesized",
        "btc_aud_channel": "BTC/USD demand channel if AUD/USD is unchanged",
    },
    {
        "id": "cryptobriefing_btc_etf_flow_2026_11_17",
        "event_cluster_id": "US_BTC_ETF_FLOWS_2026_11_16",
        "url": "https://cryptobriefing.com/bitcoin-etf-outflow-streak-ends-64800/",
        "publisher": "Crypto Briefing",
        "role": "independent_crypto_etf_flow_followup",
        "published_at_utc": "2026-11-17T16:59:00Z",
        "publication_time_basis": "Crypto Briefing page byline: 17 Nov 2026 11:59 a.m. EST (UTC-5)",
        "release_time_source_url": None,
        "causal_degree_hypothesis": 1,
        "btc_usd_channel": "reported spot ETF flows may affect marginal BTC demand",
        "aud_usd_channel": "no direct FX sign hypothesized",
        "btc_aud_channel": "BTC/USD demand channel if AUD/USD is unchanged",
    },
    {
        "id": "rba_november_2026_release_clock",
        "event_cluster_id": "RBA_NOVEMBER_2026_MINUTES",
        "url": "https://www.rba.gov.au/schedules-events/calendar/",
        "publisher": "Reserve Bank of Australia",
        "role": "official_release_clock",
        "published_at_utc": None,
        "publication_time_basis": "Official calendar page; event time recorded separately in RBA minutes record",
        "release_time_source_url": None,
        "causal_degree_hypothesis": 2,
        "btc_usd_channel": "not an independent market event",
        "aud_usd_channel": "not an independent market event",
        "btc_aud_channel": "not an independent market event",
    },
)
ALLOWED_HOSTS = {"www.rba.gov.au", "www.coindesk.com", "cryptobriefing.com", "www.cryptobriefing.com"}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.in_title = False
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            key = values.get("property") or values.get("name") or values.get("itemprop")
            value = values.get("content")
            if key and value:
                self.meta[key.lower()] = value.strip()

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data.strip())

    @property
    def title(self):
        return " ".join(x for x in self.title_parts if x).strip() or None


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def next_4h_open(timestamp):
    seconds = int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp())
    boundary = ((seconds // 14400) + 1) * 14400
    return datetime.fromtimestamp(boundary, timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_http(url):
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("Host not on V44 HTTPS allowlist")
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                final_url = response.geturl()
                final_host = (urlparse(final_url).hostname or "").lower()
                if final_host not in ALLOWED_HOSTS:
                    raise ValueError("Redirect left trusted host allowlist")
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Page exceeded V44 response byte cap")
                if response.status != 200 or len(body) < 500:
                    raise ValueError("Unexpected HTTP status or short HTML response")
                return {
                    "status": response.status,
                    "final_url": final_url,
                    "headers": dict(response.headers.items()),
                    "body": body,
                }
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 502, 503, 504) or attempt == 2:
                raise
            retry_after = (exc.headers.get("Retry-After") if exc.headers else None)
            try:
                wait_seconds = float(retry_after) if retry_after else (2 ** attempt)
            except ValueError:
                wait_seconds = 2 ** attempt
            time.sleep(min(10.0, max(1.0, wait_seconds)))
    raise last_error


def _modified_time(meta, headers):
    for key in ("article:modified_time", "datemodified", "og:updated_time"):
        value = meta.get(key)
        if value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
    # HTTP Last-Modified is preserved as transport metadata, not asserted to be
    # the publisher's article revision time.
    return None


def capture_one(spec, fetcher=fetch_http, *, retrieved_at_utc=None,
                workflow_event=None, workflow_ref=None, workflow_run_id=None):
    retrieved = retrieved_at_utc or utc_now()
    host = (urlparse(spec["url"]).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("Capture spec host is not trusted")
    try:
        response = fetcher(spec["url"])
        final_host = (urlparse(response["final_url"]).hostname or "").lower()
        if response["status"] != 200 or final_host not in ALLOWED_HOSTS:
            raise ValueError("Untrusted redirect or non-200 response")
        body = response["body"]
        if not isinstance(body, bytes) or len(body) < 500 or len(body) > MAX_BYTES:
            raise ValueError("Invalid bounded HTML response body")
        parser = MetaParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        digest = hashlib.sha256(body).hexdigest()
        is_main_push = workflow_event == "push" and workflow_ref == "refs/heads/main"
        return {
            **spec,
            "title_observed": parser.title,
            "canonical_url_observed": parser.meta.get("og:url") or response["final_url"],
            "publisher_updated_at_utc": _modified_time(parser.meta, response["headers"]),
            "http_last_modified_header": response["headers"].get("Last-Modified"),
            "http_status": response["status"],
            "final_url": response["final_url"],
            "capture_method": "direct_https_response_body_sha256",
            "capture_version_hash_algorithm": "sha256",
            "capture_version_hash": digest,
            "body_bytes": len(body),
            "body_stored": False,
            "retrieved_at_utc": retrieved,
            "first_persisted_observation_at_utc": retrieved if is_main_push else None,
            "first_persisted_observation_scope": (
                "first direct version hash observed by this connector on a main push"
                if is_main_push else "PR validation capture only; not persisted as first observation"
            ),
            "prospective_market_available_at_utc": retrieved,
            "next_eligible_4h_decision_open_utc": next_4h_open(retrieved),
            "strict_historical_backtest_eligible": False,
            "availability_confidence": "verified_direct_fetch_at_retrieval_only",
            "workflow_event": workflow_event,
            "workflow_ref": workflow_ref,
            "workflow_run_id": workflow_run_id,
            "license_note": "Metadata and content hash only; article body is not stored or redistributed",
            "status": "CAPTURED_METADATA_HASH_ONLY",
        }
    except Exception as exc:
        return {
            **spec,
            "retrieved_at_utc": retrieved,
            "capture_version_hash": None,
            "body_stored": False,
            "status": "FETCH_FAILED",
            "failure": type(exc).__name__ + ": " + str(exc)[:240],
            "strict_historical_backtest_eligible": False,
        }


def run(fetcher=fetch_http, *, retrieved_at_utc=None, workflow_event=None,
        workflow_ref=None, workflow_run_id=None):
    rows = [
        capture_one(spec, fetcher, retrieved_at_utc=retrieved_at_utc,
                    workflow_event=workflow_event, workflow_ref=workflow_ref,
                    workflow_run_id=workflow_run_id)
        for spec in SPECS
    ]
    return {
        "schema": "v44_direct_news_capture_1",
        "mode": "PROSPECTIVE_OBSERVATION_ONLY",
        "retrieved_at_utc": retrieved_at_utc or utc_now(),
        "workflow_event": workflow_event,
        "workflow_ref": workflow_ref,
        "workflow_run_id": workflow_run_id,
        "record_count": len(rows),
        "captured_count": sum(row["status"] == "CAPTURED_METADATA_HASH_ONLY" for row in rows),
        "failed_count": sum(row["status"] != "CAPTURED_METADATA_HASH_ONLY" for row in rows),
        "records": rows,
        "policy": [
            "Direct fetch time is first persisted observation only on main push; not internet-wide first seen",
            "Publisher publication and update timestamps remain separate from retrieval/capture time",
            "No publication-time backdating; all direct captures are prospective only",
            "No article body stored; SHA256 is over exact fetched response bytes",
            "No source-claimed first_seen timestamp is trusted",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v44-live-news-capture.json")
    args = parser.parse_args(argv)
    report = run(
        workflow_event=os.environ.get("GITHUB_EVENT_NAME"),
        workflow_ref=os.environ.get("GITHUB_REF"),
        workflow_run_id=os.environ.get("GITHUB_RUN_ID"),
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({
        "captured": report["captured_count"],
        "failed": report["failed_count"],
        "records": [{
            "id": row["id"], "status": row["status"],
            "hash": row.get("capture_version_hash"),
            "retrieved_at_utc": row["retrieved_at_utc"],
            "first_persisted_observation_at_utc": row.get("first_persisted_observation_at_utc"),
            "failure": row.get("failure"),
        } for row in report["records"]],
        "report_sha256": hashlib.sha256(raw).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
