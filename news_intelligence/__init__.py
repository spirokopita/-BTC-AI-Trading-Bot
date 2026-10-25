"""Offline-safe, causality-aware news research. No live order execution."""
from .feeds import FeedSource, DEFAULT_FEEDS, parse_feed, fetch_feed
from .store import NewsStore, NewsItem
from .signals import classify, event_study, train_signal_quality, category_impact_summary
__all__ = ['FeedSource','DEFAULT_FEEDS','parse_feed','fetch_feed','NewsStore','NewsItem','classify','event_study','train_signal_quality','category_impact_summary']
