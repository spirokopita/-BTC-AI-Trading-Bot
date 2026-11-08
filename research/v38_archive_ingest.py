"""V38 historical news ingestion, PAPER-ONLY research. Metadata, not copyrighted article text.

Every live adapter records HTTP failures rather than fabricating article rows.
Retrospective publication time is NOT a verified historical observation.
Only independently archived WARC captures can pass the strict as-of gate.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import html.parser
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research/v37_source_topic_registry.json"
UA = "BTC-AUD-paper-historical-research/38 (metadata-only)"
ALLOWED = frozenset({
    "cryptocurrency.cv", "infini-news.uni-graz.at",
    "api.gdeltproject.org", "index.commoncrawl.org",
    "www.federalreserve.gov", "raw.githubusercontent.com",
})
MONTHS = ("2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2025-01")
SAMPLE_LIMIT = 30
MAX_BYTES = 3_000_000
COSTS_BPS = {"taker_each_side": 80, "half_spread_each_side": 5,
             "slippage_each_side": 5}
DISABLED = {
    "media_cloud": "API credentials/access required; no authorized key",
    "newsdata_io": "archive access key/paid tier; no authorized key or purchase",
    "cryptopanic": "API authentication/plan required; no authorized key",
    "crypto_news_api": "historical API key/plan required; no authorized key",
    "sandl": "API access unverified/key may be required; no authorized key",
}
# No automatic requests to paid/key-only services, or untested macro data.
def iso(value):
    """Require timezone-aware instants. Never invent midnight for a date."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not 0 < value < 10**14:
            raise ValueError("timestamp outside plausible range")
        value = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    if not isinstance(value, str):
        raise ValueError("unsupported timestamp")
    value = value.strip()
    if re.fullmatch(r"\d{14}", value):
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc).isoformat()
    if re.fullmatch(r"\d{4}-\d\d-\d\d", value):
        return None  # date alone cannot be used as a trade timestamp
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("naive source timestamp; timezone unverified")
    return parsed.astimezone(timezone.utc).isoformat()

def epoch(value):
    if not value:
        return None
    return datetime.fromisoformat(value).timestamp()

def canonical(url):
    if not isinstance(url, str):
        return None
    u = urllib.parse.urlsplit(url.strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    host = u.hostname.lower().removeprefix("www.")
    if u.port not in (None, 80, 443):
        return None
    path = re.sub(r"/+", "/", u.path or "/").rstrip("/") or "/"
    query = urllib.parse.urlencode(sorted(
        (k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
        if not (k.startswith("utm_") or k in ("fbclid", "gclid", "ref"))))
    return urllib.parse.urlunsplit(("https", host, path, query, ""))

def request(url, *, body=None, max_bytes=MAX_BYTES):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in ALLOWED:
        raise ValueError("URL outside fixed HTTPS host allowlist")
    headers = {"User-Agent": UA, "Accept": "application/json,text/html"}
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=22) as response:
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("response exceeds bounded byte limit")
        return raw

def get_json(url, *, body=None):
    return json.loads(request(url, body=body))

def extract_rows(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("articles", "results", "data", "items", "documents"):
            val = obj.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                for inner in ("articles", "results", "items"):
                    if isinstance(val.get(inner), list):
                        return val[inner]
    raise ValueError("unknown response shape; not counted")

def pick(obj, *keys):
    for k in keys:
        v = obj.get(k)
        if v is not None and v != "":
            return v
    return None

def normalize(source, row, retrieved, capture=None, index_version=None):
    if not isinstance(row, dict):
        return None
    url = canonical(pick(row, "canonical_link", "url", "link",
                         "warc_target_uri", "url_original"))
    if not url:
        return None
    def safe_time(*keys):
        try:
            return iso(pick(row, *keys))
        except (ValueError, OverflowError):
            return None
    published = safe_time("pub_date", "published_at", "published",
                          "seendate", "date_published", "date")
    updated = safe_time("updated_at", "modified_at", "date_modified")
    claimed_seen = safe_time("first_seen", "first_observed_at", "first_seen_at")
    capture_at = None
    capture_ref = None
    version_hash = None
    # A WARC record has a verifiable crawl timestamp and source digest.
    # An API query made today does NOT verify that an article existed in 2021.
    if source in ("common_crawl", "infini_news"):
        stamp = pick(row, "warc_date", "timestamp", "capture_at")
        if source == "common_crawl" and isinstance(stamp, str) and re.fullmatch(r"\d{14}", stamp):
            stamp = iso(stamp)
        digest = pick(row, "warc_payload_digest", "digest")
        filename = pick(row, "warc_filename", "filename")
        if stamp and digest and filename:
            try:
                capture_at = iso(stamp)
            except ValueError:
                pass
            if capture_at:
                capture_ref = str(filename)
                version_hash = str(digest)
    title = str(pick(row, "title", "headline", "name") or "")[:300]
    official_date = pick(row, "date") if source in ("fomc_calendar", "fed_press") else None
    if not published and not capture_at and not official_date:
        # Discovery-only metadata cannot be time-aligned to market bars.
        return None
    return {
        "source_ids": [source], "canonical_url": url,
        "title": title, "official_event_date_only": official_date,
        "official_release_at_utc": None,
        "official_release_time_provenance": None,
        "published_at_utc": published,
        "updated_at_utc": updated,
        "source_claimed_first_seen_at_utc": claimed_seen,
        "first_verified_capture_at_utc": capture_at,
        "capture_source": source if capture_at else None,
        "capture_reference": capture_ref,
        "version_hash": version_hash,
        "title_sha256": hashlib.sha256(title.encode()).hexdigest() if title else None,
        "content_sha256": None,  # no full article body downloaded
        "retrieved_at_utc": retrieved,
        "index_version": index_version,
        "availability_confidence": "verified_crawl" if capture_at else "retrospective_only",
        "topic_degree": None, "category": "unclassified",
        "license": "publisher_rights_metadata_only",
    }

def merge(rows):
    """Dedup exact URL + capture version; never merge different revisions."""
    result = {}
    for r in rows:
        key = (r["canonical_url"], r["version_hash"] or "UNVERIFIED_VERSION")
        if key not in result:
            result[key] = dict(r)
        else:
            a = result[key]
            a["source_ids"] = sorted(set(a["source_ids"] + r["source_ids"]))
            # A captured version is more reliable than a retrospective API row.
            if r["first_verified_capture_at_utc"] and (
                not a["first_verified_capture_at_utc"] or
                r["first_verified_capture_at_utc"] < a["first_verified_capture_at_utc"]
            ):
                for k in ("first_verified_capture_at_utc", "capture_source",
                          "capture_reference", "version_hash", "availability_confidence"):
                    a[k] = r[k]
            for k in ("published_at_utc", "updated_at_utc"):
                if a[k] is None:
                    a[k] = r[k]
    return sorted(result.values(), key=lambda x: (
        x["published_at_utc"] or x["first_verified_capture_at_utc"] or "",
        x["canonical_url"], x["version_hash"] or ""))

def asof_visible(r, decision_utc):
    """Only independently verified, already captured versions; no revisions from future."""
    t = epoch(iso(decision_utc))
    cap = epoch(r.get("first_verified_capture_at_utc"))
    pub = epoch(r.get("published_at_utc"))
    upd = epoch(r.get("updated_at_utc"))
    return bool(cap is not None and cap <= t and
                (pub is None or pub <= t) and
                (upd is None or upd <= t))

def join_market(rows, bars):
    """Retrospective price alignment is NOT a tradable news feature."""
    times = [b[0] for b in bars]
    if any(b - a != 14400 for a, b in zip(times, times[1:])):
        raise ValueError("market gap; segment first")
    linked = 0
    strict = 0
    official_release_linked = 0
    examples = []
    for r in rows:
        official = epoch(r.get("official_release_at_utc"))
        if official is not None and bisect.bisect_left(times, official) < len(times):
            official_release_linked += 1
        pub = epoch(r["published_at_utc"])
        if pub is None:
            continue
        i = bisect.bisect_left(times, pub)
        if i == len(times):
            continue
        # Bar i is a decision at its OPEN; no same-bar future data.
        linked += 1
        eligible = asof_visible(r, datetime.fromtimestamp(times[i], timezone.utc).isoformat())
        strict += eligible
        if len(examples) < 5:
            examples.append({"url": r["canonical_url"], "bar_open_utc":
                datetime.fromtimestamp(times[i], timezone.utc).isoformat(),
                "strict_asof_eligible": eligible})
    return {"retrospective_time_aligned": linked,
            "official_release_time_aligned_not_first_observed": official_release_linked,
            "strict_asof_eligible": strict,
            "examples": examples, "market_bars": len(bars)}

class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            h = dict(attrs).get("href")
            if h:
                self.links.append(h)

def fed_links(page, source, retrieved):
    links = Links()
    links.feed(page.decode("utf-8", errors="replace"))
    rows = []
    for href in links.links:
        url = urllib.parse.urljoin("https://www.federalreserve.gov/", href)
        host = urllib.parse.urlsplit(url).hostname
        if host != "www.federalreserve.gov":
            continue
        path = urllib.parse.urlsplit(url).path.lower()
        if source == "fomc_calendar":
            if not re.search(r"(fomcstatement|monetary20\d{6}a)\b", path):
                continue
        elif source == "fed_press":
            if "/newsevents/pressreleases/" not in path:
                continue
        date = re.search(r"(20(?:2[0-6]))([01]\d)([0-3]\d)", path)
        if not date:
            continue
        # Calendar/filename only verifies meeting or press date, NOT release hour.
        rows.append({"url": url, "title": "Federal Reserve official release " +
                     date.group(0), "date": date.group(0)[:4] + "-" +
                     date.group(0)[4:6] + "-" + date.group(0)[6:8]})
    return [r for r in (normalize(source, x, retrieved) for x in rows) if r]

class VisibleText(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, value):
        self.parts.append(value)

def official_release_time(page, date):
    """Read explicit Fed release clock/timezone, not infer it from meeting date."""
    visible = VisibleText()
    visible.feed(page.decode("utf-8", errors="replace"))
    body = " ".join(visible.parts)
    match = re.search(r"For release at\s+(\d{1,2}):(\d\d)\s+"
                      r"(a\.m\.|p\.m\.)\s+(EST|EDT)", body, re.I)
    if not match:
        return None
    hour = int(match.group(1)) % 12 + (12 if match.group(3).lower().startswith("p") else 0)
    minute = int(match.group(2))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid Fed release clock")
    offset = -5 if match.group(4).upper() == "EST" else -4
    dt = datetime.fromisoformat(date).replace(hour=hour, minute=minute,
                 tzinfo=timezone(timedelta(hours=offset)))
    return dt.astimezone(timezone.utc).isoformat()

def enrich_fomc_release_samples(rows):
    """Outcome-independent one official statement per 2021, 2023, 2025."""
    sampled = []
    errors = []
    for year in (2021, 2023, 2025):
        candidates = [r for r in rows if (r.get("official_event_date_only") or
                       "").startswith(str(year))]
        if not candidates:
            errors.append(str(year) + ": no official statement link")
            continue
        chosen = min(candidates, key=lambda x: x["canonical_url"])
        try:
            page = request(chosen["canonical_url"].replace(
                "https://federalreserve.gov/", "https://www.federalreserve.gov/"))
            release = official_release_time(page, chosen["official_event_date_only"])
            if release:
                chosen["official_release_at_utc"] = release
                chosen["official_release_time_provenance"] = (
                    "Fed official page clock currently displayed; NOT first-observed history")
                sampled.append(chosen["canonical_url"])
            else:
                errors.append(str(year) + ": explicit release clock absent")
        except Exception as exc:
            errors.append(str(year) + ": " + type(exc).__name__ + ": " + str(exc)[:90])
    return sampled, errors

def source_fetch(source, retrieved):
    if source in DISABLED:
        return [], "KEY_REQUIRED_OR_RESTRICTED: " + DISABLED[source]
    if source == "cryptocurrency_cv":
        allrows = []
        for month in MONTHS:
            # 2026 API route accepts start_date/end_date, NOT the date= shorthand
            # shown in older docs. Require echoed filters and post-filter UTC month.
            year, mo = map(int, month.split("-"))
            from calendar import monthrange
            first = month + "-01"
            last = month + "-" + str(monthrange(year, mo)[1]).zfill(2)
            u = "https://cryptocurrency.cv/api/archive?" + urllib.parse.urlencode(
                {"start_date": first, "end_date": last, "limit": SAMPLE_LIMIT})
            try:
                obj = get_json(u)
                if not isinstance(obj, dict) or obj.get("success") is False:
                    raise ValueError("archive API unsuccessful response")
                filters = obj.get("filters") or {}
                if filters.get("start_date") != first or filters.get("end_date") != last:
                    raise ValueError("archive API did not echo requested date filters")
                rawrows = extract_rows(obj)
                filtered = []
                for item in rawrows:
                    r = normalize(source, item, retrieved)
                    if r and r["published_at_utc"] and r["published_at_utc"][:7] == month:
                        filtered.append(r)
                if rawrows and not filtered:
                    raise ValueError("no returned article has verified publication month")
                allrows.extend(filtered)
            except Exception as exc:
                allrows.append({"_fetch_error": month + ": " + str(exc)[:170]})
        errors = [r["_fetch_error"] for r in allrows if "_fetch_error" in r]
        rows = [r for r in allrows if "_fetch_error" not in r]
        return rows, "; ".join(errors) if errors else "OK_DATE_FILTERS_VERIFIED"
    if source == "infini_news":
        obj = get_json("https://infini-news.uni-graz.at/api/v2/search",
                       body={"index": "ccnews", "query": "Bitcoin",
                             "year_min": 2020, "year_max": 2026,
                             "limit": SAMPLE_LIMIT, "preview": True})
        rows = [r for r in (normalize(source, x.get("metadata", x), retrieved,
                  index_version=obj.get("index_version")) for x in extract_rows(obj)) if r]
        return rows, ("OK_PREVIEW_INCOMPLETE" if not obj.get("complete") else "OK")
    if source == "gdelt":
        obj = get_json("https://api.gdeltproject.org/api/v2/doc/doc?" +
            urllib.parse.urlencode({"query": "bitcoin", "mode": "artlist",
                                    "format": "json", "maxrecords": SAMPLE_LIMIT}))
        return [r for r in (normalize(source, x, retrieved)
                for x in extract_rows(obj)) if r], "RECENT_ONLY_NOT_2020_2026_ARCHIVE"
    if source == "common_crawl":
        coll = get_json("https://index.commoncrawl.org/collinfo.json")
        selected = next((x for x in coll if x.get("id", "").startswith("CC-MAIN-2024-")), None)
        if not selected:
            raise ValueError("No 2024 index")
        target = "www.federalreserve.gov/monetarypolicy/fomcstatement20240131.htm"
        u = selected["cdx-api"] + "?" + urllib.parse.urlencode(
            {"url": target, "output": "json", "filter": "status:200"})
        raw = request(u, max_bytes=250_000).decode("utf-8")
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return [r for r in (normalize(source, x, retrieved,
                    index_version=selected["id"]) for x in rows) if r], "URL_SPECIFIC_CAPTURE_SAMPLE"
    if source in ("fomc_calendar", "fed_press"):
        url = ("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
               if source == "fomc_calendar" else
               "https://www.federalreserve.gov/newsevents/pressreleases.htm")
        rows = fed_links(request(url), source, retrieved)
        if source == "fomc_calendar":
            sampled, failures = enrich_fomc_release_samples(rows)
            return rows, ("DATE_ONLY_PLUS_" + str(len(sampled)) +
                "_OFFICIAL_CLOCKS_NOT_HISTORICAL_CAPTURE" +
                ("; " + "; ".join(failures) if failures else ""))
        return rows, "DATE_ONLY_NO_VERIFIED_RELEASE_HOUR"
    if source == "fomc_statements_mirror":
        # Reachability only: source mirror cannot authenticate original Fed timing.
        request("https://raw.githubusercontent.com/fomc/statements/master/README.md")
        return [], "MIRROR_REACHABLE_NO_ORIGINAL_RELEASE_TIMING"
    return [], "DISABLED_NO_IMPLEMENTED_LICENSED_CONNECTOR"

def run(source_ids=None, market_bars=None, now=None, fetcher=source_fetch):
    now = now or datetime.now(timezone.utc).isoformat()
    ids = source_ids or ("cryptocurrency_cv", "infini_news", "gdelt",
        "common_crawl", "fomc_calendar", "fed_press", "fomc_statements_mirror",
        *DISABLED)
    rows, status = [], {}
    for sid in ids:
        try:
            got, note = fetcher(sid, now)
            rows.extend(got)
            status[sid] = {"fetched_rows": len(got), "status": note}
        except Exception as exc:
            status[sid] = {"fetched_rows": 0, "status":
                type(exc).__name__ + ": " + str(exc)[:240]}
    unique = merge(rows)
    monthly = collections.Counter((r["published_at_utc"] or "")[:7] or "unknown"
                                  for r in unique)
    date_only = collections.Counter((r.get("official_event_date_only") or "")[:7]
                                    for r in unique if r.get("official_event_date_only"))
    return {"schema": "v38_metadata_provenance_1", "retrieved_at_utc": now,
        "source_status": status, "raw_normalized_rows": len(rows),
        "deduplicated_rows": len(unique),
        "historically_verified_capture_rows": sum(bool(r["first_verified_capture_at_utc"])
                                                   for r in unique),
        "months": dict(sorted(monthly.items())),
        "official_event_date_only_months": dict(sorted(date_only.items())),
        "official_release_clock_rows": sum(bool(r.get("official_release_at_utc")) for r in unique),
        "target_2020_2026": 10000, "target_met": len(unique) >= 10000,
        "market_join": join_market(unique, market_bars) if market_bars else
                       {"status": "NOT_ATTEMPTED_NO_VERIFIED_BARS"},
        "costs_bps": COSTS_BPS, "max_paper_entry_aud": 100,
        "paper_starting_cash_aud": 1000, "android_strategy": "HOLD",
        "notes": ["No article bodies copied; publisher rights remain with publishers.",
          "API retrieval now is NOT proof of historical first observation.",
          "Source-claimed first_seen is not independently verified.",
          "No strategy promotion without untouched chronological OOS NET edge."],
        "records": unique}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="audit/v38-archive-ingestion.json")
    ap.add_argument("--with-kraken", action="store_true")
    args = ap.parse_args()
    bars = None
    market_status = "NOT_REQUESTED"
    if args.with_kraken:
        try:
            from research.v33_cross_regime import archive
            from research.v32_segments import segments
            allbars, provenance = archive()
            a, b = max(segments(allbars, 1000), key=lambda pair: pair[1] - pair[0])
            bars = allbars[a:b]
            market_status = {"status": "OK", "source": provenance, "segment": [a, b]}
        except Exception as exc:
            market_status = {"status": "BLOCKED", "error": type(exc).__name__ + ": " + str(exc)[:250]}
    result = run(market_bars=bars)
    result["market_fetch"] = market_status
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, sort_keys=True, indent=2,
                            ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rows": result["deduplicated_rows"],
        "captured": result["historically_verified_capture_rows"],
        "source_status": result["source_status"],
        "market_join": result["market_join"], "output": str(p)}))

if __name__ == "__main__":
    main()
