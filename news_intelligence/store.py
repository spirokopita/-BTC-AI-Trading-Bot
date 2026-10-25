"""Persistent, idempotent, first-seen-aware news storage, independent of OHLC."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .signals import classify


@dataclass(frozen=True)
class NewsItem:
    id: int
    source: str
    url: str
    headline: str
    published_ts: int
    first_seen_ts: int
    available_ts: int
    categories: tuple[str,...]
    assets: tuple[str,...]
    polarity: int
    polarity_label: str


def canonical_url(url: str) -> str:
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('Only HTTPS publisher URLs allowed')
    q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
       if not k.lower().startswith('utm_') and k.lower() not in
       ('fbclid','gclid','ref','source','mc_cid','mc_eid')]
    return urlunsplit(('https',p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(q),''))


def normalized_title(headline: str) -> str:
    return re.sub(r'[^a-z0-9 ]','',re.sub(r'\s+',' ',headline.lower())).strip()


class NewsStore:
    def __init__(self,path: str | Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path),timeout=20)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=20000')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS news (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           source TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
           headline TEXT NOT NULL, summary TEXT NOT NULL,
           norm_title TEXT NOT NULL,
           published_ts INTEGER NOT NULL,
           first_seen_ts INTEGER NOT NULL,
           available_ts INTEGER NOT NULL,
           categories_json TEXT NOT NULL, assets_json TEXT NOT NULL, polarity INTEGER NOT NULL,
           polarity_label TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS news_available ON news(available_ts);
          CREATE INDEX IF NOT EXISTS news_title ON news(norm_title,published_ts);
          CREATE TABLE IF NOT EXISTS feed_state (
           feed TEXT PRIMARY KEY, etag TEXT, last_modified TEXT,
           last_success_ts INTEGER, last_attempt_ts INTEGER,
           last_error TEXT NOT NULL DEFAULT '');
        ''')
        self.db.commit()
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def ingest(self, items: list[dict]) -> dict:
        """Publication is historical, availability is strictly first witnessed time.

        URL duplicates and highly specific matching headlines within 12 hours
        are merged. Original earliest observed record is immutable on reimport.
        """
        clean=[]
        for obj in items:
            ts=int(obj['published_ts']);seen=int(obj['first_seen_ts'])
            src=str(obj['source']).strip()[:120]
            head=str(obj['headline']).strip()[:600]
            summary=str(obj.get('summary',''))[:4000]
            if ts<=0 or seen<ts-300 or not src or not head:raise ValueError('Invalid timestamps/source/headline')
            url=canonical_url(obj['url'])
            norm=normalized_title(head)
            if len(norm)<10:raise ValueError('News headline too short to deduplicate')
            tag=classify(head,summary)
            clean.append((src,url,head,summary,norm,ts,seen,max(ts,seen),
                         json.dumps(tag['categories']),json.dumps(tag['assets']),tag['polarity'],tag['label']))
        inserted=0;dups=0
        with self.db:
            for v in clean:
                # Atomic transaction; same normalized title within 12h groups
                # syndicated republications without multiplying an event.
                duplicate=self.db.execute('''SELECT id FROM news WHERE url=? OR
                      (norm_title=? AND published_ts BETWEEN ? AND ?)
                      ORDER BY first_seen_ts ASC LIMIT 1''',
                    (v[1],v[4],v[5]-12*3600,v[5]+12*3600)).fetchone()
                if duplicate:
                    dups+=1
                    continue
                self.db.execute('''INSERT INTO news(source,url,headline,summary,norm_title,
                   published_ts,first_seen_ts,available_ts,categories_json,assets_json,polarity,polarity_label)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',v)
                inserted+=1
        return {'received':len(clean),'inserted':inserted,'duplicates':dups}

    def items(self, start: int | None=None,end: int | None=None) -> list[NewsItem]:
        query='SELECT * FROM news WHERE 1=1';args=[]
        if start is not None:query+=' AND available_ts>=?';args.append(start)
        if end is not None:query+=' AND available_ts<=?';args.append(end)
        query+=' ORDER BY available_ts,id'
        results=[]
        for row in self.db.execute(query,args):
            results.append(NewsItem(int(row['id']),row['source'],row['url'],row['headline'],
                 int(row['published_ts']),int(row['first_seen_ts']),int(row['available_ts']),
                 tuple(json.loads(row['categories_json'])),tuple(json.loads(row['assets_json'])),int(row['polarity']),row['polarity_label']))
        return results

    def feed_headers(self,feed: str):
        row=self.db.execute('SELECT etag,last_modified FROM feed_state WHERE feed=?',(feed,)).fetchone()
        return dict(row) if row else {}

    def record_feed_attempt(self,feed: str, now: int, *, success: bool,
                           etag: str | None=None,last_modified: str | None=None,
                           error: str=''):
        if not feed:raise ValueError('Invalid feed')
        with self.db:
            self.db.execute('''INSERT INTO feed_state(feed,etag,last_modified,last_success_ts,last_attempt_ts,last_error)
             VALUES(?,?,?,?,?,?) ON CONFLICT(feed) DO UPDATE SET
             etag=CASE WHEN excluded.last_error='' THEN COALESCE(excluded.etag,feed_state.etag) ELSE feed_state.etag END,
             last_modified=CASE WHEN excluded.last_error='' THEN COALESCE(excluded.last_modified,feed_state.last_modified) ELSE feed_state.last_modified END,
             last_success_ts=CASE WHEN excluded.last_error='' THEN excluded.last_success_ts ELSE feed_state.last_success_ts END,
             last_attempt_ts=excluded.last_attempt_ts,last_error=excluded.last_error''',
                (feed,etag,last_modified,now if success else None,now,error[:400]))
