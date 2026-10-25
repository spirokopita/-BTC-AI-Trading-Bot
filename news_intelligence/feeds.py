"""Bounded RSS/Atom collector: remembers publication AND first observed time.

Publication alone does not prove the news was available to this bot in the past.
No API key, full-article scraping, JavaScript execution, or order placement.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

MAX_FEED_BYTES=2_000_000
MAX_ENTRIES=150

@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str

DEFAULT_FEEDS=(
    FeedSource('CoinDesk','https://www.coindesk.com/arc/outboundfeeds/rss/'),
    FeedSource('Cointelegraph','https://cointelegraph.com/rss'),
    FeedSource('The Block','https://www.theblock.co/rss.xml'),
    FeedSource('Decrypt','https://decrypt.co/feed'),
    FeedSource('Bloomberg Crypto','https://feeds.bloomberg.com/crypto/news.rss'),
)


def plain(value: str) -> str:
    """RSS descriptions may embed HTML; never accept markup as a signal."""
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>', ' ',value or ''))).strip()[:4000]


def timestamp(raw: str) -> int:
    raw=raw.strip()
    if not raw: raise ValueError('Publication date missing')
    try: d=parsedate_to_datetime(raw)
    except (ValueError,TypeError,IndexError):
        d=datetime.fromisoformat(raw.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Naive publication date is not accepted')
    return int(d.astimezone(timezone.utc).timestamp())


def child_text(element: ET.Element, *names: str) -> str:
    for name in names:
        for part in element:
            if part.tag.rsplit('}',1)[-1].lower()==name.lower() and part.text:
                return part.text.strip()
    return ''


def parse_feed(xml_bytes: bytes, source: FeedSource, *, observed_at: int, limit: int=MAX_ENTRIES) -> list[dict]:
    if not 0<len(xml_bytes)<=MAX_FEED_BYTES: raise ValueError('Invalid or overlarge news feed')
    if b'<!DOCTYPE' in xml_bytes.upper() or b'<!ENTITY' in xml_bytes.upper():
        raise ValueError('XML document/entity declarations disallowed')
    if not 1<=limit<=MAX_ENTRIES: raise ValueError('Feed entry limit out of range')
    root=ET.fromstring(xml_bytes)
    items=[]
    for element in root.iter():
        if element.tag.rsplit('}',1)[-1].lower() not in ('item','entry'): continue
        head=plain(child_text(element,'title'))
        published=child_text(element,'pubDate','published','updated','date')
        url=child_text(element,'link')
        if not url:
            for part in element:
                if part.tag.rsplit('}',1)[-1].lower()=='link' and part.attrib.get('href'):
                    url=part.attrib['href']; break
        summary=plain(child_text(element,'description','summary','content'))
        try:
            if not head or not urlparse(url).scheme=='https':continue
            ts=timestamp(published)
            if ts<1388534400 or ts>observed_at+300:continue
            items.append({'source':source.name,'url':url,'headline':head,'summary':summary,
                          'published_ts':ts,'first_seen_ts':observed_at})
            if len(items)>=limit:break
        except (ValueError,OverflowError):continue
    return items


def fetch_feed(source: FeedSource, *, observed_at: int | None=None, etag: str | None=None,
               last_modified: str | None=None, timeout: float=12.0,
               opener=urlopen, max_attempts: int=3, sleep=time.sleep) -> dict:
    """Bounded retries, conditional GET and fail-closed source host checks.

    This is an ingestion function, not an always-on scheduler. An external
    scheduler can call it every 15-30 minutes and audit last-success time.
    """
    trusted={urlparse(x.url).hostname for x in DEFAULT_FEEDS}
    parts=urlparse(source.url)
    if parts.scheme!='https' or parts.hostname not in trusted:
        raise ValueError('Feed host is not in the configured source allowlist')
    if not 1<=max_attempts<=5 or timeout<=0:raise ValueError('Bad retry or timeout settings')
    observed_at=int(time.time()) if observed_at is None else int(observed_at)
    headers={'User-Agent':'CryptoPaperResearch/1.0 (news research; contact your admin)',
             'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'}
    if etag: headers['If-None-Match']=etag
    if last_modified:headers['If-Modified-Since']=last_modified
    for attempt in range(max_attempts):
        try:
            req=Request(source.url,headers=headers)
            with opener(req,timeout=timeout) as response:
                if response.status==304:return {'not_modified':True,'items':[]}
                if response.status!=200:raise ValueError(f'HTTP status {response.status}')
                # Even if a server redirects, it must not leave the allowlist.
                final=urlparse(response.geturl())
                if final.scheme!='https' or final.hostname not in trusted:
                    raise ValueError('RSS redirect left trusted host allowlist')
                raw=response.read(MAX_FEED_BYTES+1)
                if len(raw)>MAX_FEED_BYTES:raise ValueError('RSS payload exceeds bounded size')
                return {'not_modified':False,
                        'items':parse_feed(raw,source,observed_at=observed_at),
                        'etag':response.headers.get('ETag'),
                        'last_modified':response.headers.get('Last-Modified')}
        except HTTPError as ex:
            if ex.code==304:return {'not_modified':True,'items':[]}
            if ex.code not in (429,500,502,503,504) or attempt==max_attempts-1:raise
            wait=ex.headers.get('Retry-After','')
            try:delay=min(10.,max(0.,float(wait)))
            except ValueError:delay=min(10.,2.**attempt)
            sleep(delay)
        except (URLError,TimeoutError):
            if attempt==max_attempts-1:raise
            sleep(min(10.,2.**attempt))
    raise RuntimeError('Feed retries exhausted')
