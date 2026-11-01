"""V28 deterministic cumulative first-observed RSS evidence (NO TRADING).

Merge *actual* historical CI SQLite snapshots, not historical article publication
as a substitute for first observation. Preserve earliest evidenced observation
per canonical URL. Source snapshot hashes and a corpus SHA are recorded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

FIELDS = ('source', 'url', 'headline', 'summary', 'published_ts', 'first_seen_ts')
MAX_ROWS = 100000


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('Invalid article HTTPS URL')
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in
             ('fbclid', 'gclid', 'ref', 'source', 'mc_cid', 'mc_eid')]
    return urlunsplit(('https', p.netloc.lower(), p.path.rstrip('/') or '/', urlencode(query), ''))


def validate_row(row, *, now):
    obj = {k: row[k] for k in FIELDS}
    obj['source'] = str(obj['source']).strip()
    obj['headline'] = str(obj['headline']).strip()
    obj['summary'] = str(obj['summary'] or '')
    obj['published_ts'] = int(obj['published_ts'])
    obj['first_seen_ts'] = int(obj['first_seen_ts'])
    obj['url'] = canonical_url(str(obj['url']))
    if (not obj['source'] or not obj['headline'] or len(obj['headline']) > 600 or
        len(obj['summary']) > 4000 or obj['published_ts'] < 1388534400 or
        obj['first_seen_ts'] < obj['published_ts'] - 300 or
        obj['first_seen_ts'] > now + 300):
        raise ValueError('Invalid or future-dated first-seen evidence')
    return obj


def read_snapshot(path, *, now):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    # Read-only immutable source; never alter first_seen_ts in prior evidence.
    uri = path.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        columns = {x[1] for x in conn.execute('PRAGMA table_info(news)')}
        if not set(FIELDS).issubset(columns):
            raise ValueError(f'Snapshot lacks first-seen news schema: {path}')
        count = conn.execute('SELECT COUNT(*) FROM news').fetchone()[0]
        if count > MAX_ROWS:
            raise ValueError('Snapshot exceeds row bound')
        rows = [validate_row(dict(x), now=now) for x in conn.execute(
            'SELECT '+','.join(FIELDS)+' FROM news ORDER BY first_seen_ts,url')]
    return rows, {'path': str(path), 'sha256': raw_hash, 'rows': count}


def read_existing(path, *, now):
    path = Path(path)
    if not path.exists():
        return []
    if path.stat().st_size > 30_000_000:
        raise ValueError('Corpus exceeds size bound')
    with path.open(encoding='utf-8') as handle:
        rows = [validate_row(json.loads(line), now=now) for line in handle if line.strip()]
    if len(rows) > MAX_ROWS:
        raise ValueError('Corpus exceeds row bound')
    return rows


def merge(existing, snapshots, *, now):
    """Earliest *recorded* first observation wins, never publication date.

    An earlier snapshot row is legitimate historical evidence only when its
    original SQLite first_seen_ts and snapshot hash are retained in manifest.
    """
    chosen = {}
    for row in sorted([*existing, *snapshots], key=lambda r: (r['first_seen_ts'], r['url'])):
        obj = validate_row(row, now=now)
        if obj['url'] not in chosen:
            chosen[obj['url']] = obj
    if len(chosen) > MAX_ROWS:
        raise ValueError('Cumulative corpus exceeds row bound')
    return sorted(chosen.values(), key=lambda r: (r['first_seen_ts'], r['url']))


def atomic_write(path, contents):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.firstseen-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build(*, existing, snapshots, output, manifest, now=None):
    now = int(time.time()) if now is None else int(now)
    old = read_existing(existing, now=now)
    sources, rows = [], []
    for source in snapshots:
        source = Path(source)
        matches = sorted(source.rglob('*.sqlite')) if source.is_dir() else [source]
        if not matches:
            raise ValueError(f'No SQLite evidence in {source}')
        for item in matches:
            data, prov = read_snapshot(item, now=now)
            rows.extend(data)
            sources.append(prov)
    if not sources and not old:
        raise ValueError('No prior or current observed news evidence')
    combined = merge(old, rows, now=now)
    content = ''.join(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(',', ':'))+'\n'
                      for r in combined).encode('utf-8')
    digest = hashlib.sha256(content).hexdigest()
    report = {'paper_only': True, 'created_at_unix': now, 'existing_rows': len(old),
              'snapshot_rows': len(rows), 'unique_cumulative_rows': len(combined),
              'deduplicated_rows': len(old)+len(rows)-len(combined),
              'earliest_first_seen_ts': combined[0]['first_seen_ts'] if combined else None,
              'latest_first_seen_ts': combined[-1]['first_seen_ts'] if combined else None,
              'corpus_sha256': digest, 'snapshot_sources': sources,
              'news_predictive_value': 'NOT TESTED: only after first-observed data and matured candles',
              'historical_first_seen_backfilled': False}
    atomic_write(output, content)
    atomic_write(manifest, json.dumps(report, indent=2).encode('utf-8'))
    if hashlib.sha256(Path(output).read_bytes()).hexdigest() != digest:
        raise AssertionError('Corpus read-back checksum mismatch')
    if len(read_existing(output, now=now)) != len(combined):
        raise AssertionError('Corpus read-back count mismatch')
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--existing', default='data/first_observed_news.jsonl')
    p.add_argument('--snapshot', action='append', default=[])
    p.add_argument('--output', default='data/first_observed_news.jsonl')
    p.add_argument('--manifest', default='audit/v28-corpus-manifest.json')
    args = p.parse_args(argv)
    print(json.dumps(build(existing=args.existing, snapshots=args.snapshot,
                           output=args.output, manifest=args.manifest), indent=2))


if __name__ == '__main__':
    main()
