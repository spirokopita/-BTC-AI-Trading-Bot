"""V44: capture exact first-observed publisher-page versions for prospective use.

Only metadata and hashes are persisted; raw publisher HTML is not redistributed.
The capture timestamp is recorded after each successful HTTPS response. The
RBA and CoinDesk publication timestamps are separately parsed from publisher
evidence. These observations were not available to earlier historical tests.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.v44_asof_join import strict_asof_join

RBA_INDEX_URL = "https://www.rba.gov.au/news/index.html"
RBA_MINUTES_URL = "https://www.rba.gov.au/monetary-policy/rba-board-minutes/2026/2026-11-03.html"
COINDESK_URL = "https://www.coindesk.com/markets/2026/11/17/bitcoin-remains-penned-in-near-usd64-000-even-as-etf-outflow-streak-ends"
ALLOWED_HOSTS = {"www.rba.gov.au", "rba.gov.au", "www.coindesk.com", "coindesk.com"}
MAX_BYTES = 2_000_000
LATENCY_SECONDS = 3600


def utc_iso(value):
    if value.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Unapproved publisher host")
    request = urllib.request.Request(url, headers={
        "User-Agent": "BTC-AUD-PAPER-research/44 (metadata-only; no live trading)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        final_url = response.geturl()
        final = urllib.parse.urlsplit(final_url)
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise ValueError("Publisher redirected outside allowlist")
        body = response.read(MAX_BYTES + 1)
        headers = dict(response.headers.items())
    if len(body) > MAX_BYTES:
        raise ValueError("Publisher response exceeded byte limit")
    if len(body) < 500:
        raise ValueError("Publisher response suspiciously small")
    return body, final_url, headers


def visible_text(raw):
    value = raw.decode("utf-8", errors="replace")
    value = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def meta_value(raw, keys):
    source = raw.decode("utf-8", errors="replace")
    for key in keys:
        patterns = (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(key)}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, source, re.I)
            if match:
                return html.unescape(match.group(1)).strip()
    return None


def parse_rba_publication(index_body):
    text = visible_text(index_body)
    pattern = r"17\s+November\s+2026\s+11[.]30\s+am\s+AEDT"
    if not re.search(pattern, text, re.I):
        raise ValueError("RBA November minutes release time not present in official index")
    local = datetime(2026, 11, 17, 11, 30,
                     tzinfo=ZoneInfo("Australia/Sydney"))
    return utc_iso(local)


def parse_coindesk_publication(article_body):
    machine = meta_value(article_body, ("article:published_time", "datePublished"))
    if machine:
        parsed = datetime.fromisoformat(machine.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("CoinDesk machine publication timestamp lacks timezone")
        return utc_iso(parsed)
    text = visible_text(article_body)
    pattern = r"Nov\s+17,\s+2026,\s+6:36\s+a[.]m[.]\s+EST"
    if not re.search(pattern, text, re.I):
        raise ValueError("CoinDesk publication timestamp not present in publisher page")
    local = datetime(2026, 11, 17, 6, 36,
                     tzinfo=ZoneInfo("America/New_York"))
    return utc_iso(local)


def parse_updated(raw):
    value = meta_value(raw, ("article:modified_time", "dateModified"))
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Updated timestamp lacks timezone")
    return utc_iso(parsed)


def _record(source, body, final_url, retrieved, published, updated,
            evidence_url, evidence_sha256):
    digest = hashlib.sha256(body).hexdigest()
    title = meta_value(body, ("og:title", "twitter:title")) or source["title"]
    available_epoch = max(
        datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp(),
        datetime.fromisoformat((updated or published).replace("Z", "+00:00")).timestamp(),
        datetime.fromisoformat(retrieved.replace("Z", "+00:00")).timestamp(),
    ) + LATENCY_SECONDS
    available = datetime.fromtimestamp(
        available_epoch, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema": "v44_first_observed_metadata_version_1",
        "source_id": source["id"],
        "source_ids": [source["id"]],
        "url": final_url,
        "canonical_url": final_url,
        "title": title,
        "original_publisher": source["publisher"],
        "category": source["category"],
        "sentiment": "unscored",
        "published_at_utc": published,
        "updated_at_utc": updated,
        "publication_time_evidence_url": evidence_url,
        "publication_time_evidence_sha256": evidence_sha256,
        "publication_time_confidence": source["publication_confidence"],
        "first_verified_observed_at_utc": retrieved,
        "verified_capture_at_utc": retrieved,
        "retrieved_at_utc": retrieved,
        "capture_source": "https_https_fetch",
        "capture_type": "first_observed_snapshot",
        "version_hash_algorithm": "sha256",
        "version_hash_scope": "exact publisher HTTP response body; body not redistributed",
        "content_sha256": digest,
        "version_capture_sha256": digest,
        "response_bytes": len(body),
        "available_at_utc_with_1h_latency": available,
        "availability_latency_seconds": LATENCY_SECONDS,
        "historical_asof_use": "NOT_ELIGIBLE_FOR_PRE_CAPTURE_DECISIONS",
        "paper_only": True,
        "usage_constraints": "metadata and response hashes only; no article body redistribution; respect publisher terms",
    }


def capture_all(fetcher=None, clock=None, bars=None, market_provenance=None):
    fetcher = fetcher or fetch
    clock = clock or (lambda: datetime.now(timezone.utc))
    rows, failures, statuses = [], [], {}

    # RBA official release clock is obtained from the original publisher's news index.
    rba_source = {
        "id": "rba_november_2026_minutes",
        "title": "Minutes of the November 2026 Monetary Policy Board Meeting",
        "publisher": "Reserve Bank of Australia",
        "category": "macro_policy",
        "publication_confidence": "official_RBA_news_index_release_clock",
    }
    try:
        index_body, index_url, _ = fetcher(RBA_INDEX_URL)
        body, final_url, _ = fetcher(RBA_MINUTES_URL)
        published = parse_rba_publication(index_body)
        updated = parse_updated(body)
        retrieved = utc_iso(clock())
        rows.append(_record(
            rba_source, body, final_url, retrieved, published, updated,
            index_url, hashlib.sha256(index_body).hexdigest(),
        ))
        statuses[rba_source["id"]] = {"status": "CAPTURED", "response_bytes": len(body)}
    except Exception as exc:
        statuses[rba_source["id"]] = {
            "status": "BLOCKED_OR_FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }
        failures.append({"source_id": rba_source["id"], "error": statuses[rba_source["id"]]["error"]})

    coindesk_source = {
        "id": "coindesk_btc_etf_flows_2026_11_17",
        "title": "Bitcoin remains penned in near $64,000 even as ETF outflow streak ends",
        "publisher": "CoinDesk",
        "category": "institutional_etf_flows",
        "publication_confidence": "CoinDesk_publisher_article_timestamp",
    }
    try:
        body, final_url, _ = fetcher(COINDESK_URL)
        published = parse_coindesk_publication(body)
        updated = parse_updated(body)
        retrieved = utc_iso(clock())
        rows.append(_record(
            coindesk_source, body, final_url, retrieved, published, updated,
            final_url, hashlib.sha256(body).hexdigest(),
        ))
        statuses[coindesk_source["id"]] = {
            "status": "CAPTURED", "response_bytes": len(body)}
    except Exception as exc:
        statuses[coindesk_source["id"]] = {
            "status": "BLOCKED_OR_FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }
        failures.append({"source_id": coindesk_source["id"], "error": statuses[coindesk_source["id"]]["error"]})

    market_join = (
        strict_asof_join(rows, bars, market_provenance)
        if bars is not None else {
            "mode": "V44_STRICT_ASOF_KRAKEN_4H_JOIN",
            "status": "NOT_RUN_NO_BARS",
            "strict_asof_eligible": 0,
            "pending_after_last_bar": len(rows),
            "proof_rejected": 0,
            "no_lookahead": True,
        }
    )
    return {
        "mode": "V44_PROSPECTIVE_FIRST_OBSERVED_PUBLISHER_SNAPSHOTS",
        "retrieved_at_utc": utc_iso(clock()),
        "records": rows,
        "source_status": statuses,
        "failures": failures,
        "record_count": len(rows),
        "market_join": market_join,
        "historical_backfill": False,
        "strategy_use": (
            "NOT_USED_IN_CURRENT_HISTORICAL_BACKTEST; point-in-time availability "
            "starts no earlier than verified capture plus one-hour latency"),
        "body_redistribution": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v44-recent-news-capture.json")
    parser.add_argument("--bars-json", default=None)
    parser.add_argument("--market-report", default=None)
    args = parser.parse_args(argv)
    bars = None
    market_provenance = {}
    if args.bars_json:
        bars_doc = json.loads(Path(args.bars_json).read_text(encoding="utf-8"))
        bars = bars_doc.get("bars")
        if not isinstance(bars, list) or not bars:
            raise ValueError("Recent Kraken bridge bars missing")
        if args.market_report:
            market_doc = json.loads(Path(args.market_report).read_text(encoding="utf-8"))
            market_provenance = market_doc.get("market", market_doc)
    report = capture_all(bars=bars, market_provenance=market_provenance)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    target.write_bytes(raw)
    print(json.dumps({
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": report["record_count"],
        "source_status": report["source_status"],
        "historical_backfill": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
