"""Pull the feeds. Politely, in parallel, and without re-downloading."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import feedparser
import requests

from .common import BROWSER_UA, UA, canonical_url, clean_text, now_utc

TIMEOUT = 15
WORKERS = 16
MAX_ITEMS_PER_FEED = 60


def entry_time(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return now_utc()


def fetch_one(feed: dict, cache: dict):
    """Return (feed, entries, error). Conditional GET keeps us off their backs."""
    url = feed["url"]
    headers = {
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    previous = cache.get(url, {})
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("modified"):
        headers["If-Modified-Since"] = previous["modified"]

    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        # Retry once as a browser. Roughly a fifth of the feeds refuse an
        # unfamiliar user-agent outright, including several worth having.
        if response.status_code in (403, 406, 429):
            retry = dict(headers, **{"User-Agent": BROWSER_UA,
                                     "Accept-Language": "en-US,en;q=0.9"})
            response = requests.get(url, headers=retry, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return feed, [], type(exc).__name__

    if response.status_code == 304:
        return feed, [], None
    if response.status_code >= 400:
        return feed, [], f"HTTP {response.status_code}"

    cache[url] = {
        "etag": response.headers.get("ETag"),
        "modified": response.headers.get("Last-Modified"),
    }

    parsed = feedparser.parse(response.content)
    if not parsed.entries:
        return feed, [], "no entries"
    return feed, parsed.entries[:MAX_ITEMS_PER_FEED], None


def collect(feeds: list[dict], state: dict) -> tuple[list[dict], dict]:
    cache = state.setdefault("http_cache", {})
    items: list[dict] = []
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for feed, entries, error in pool.map(lambda f: fetch_one(f, cache), feeds):
            if error:
                errors[feed["name"]] = error
                continue
            for entry in entries:
                link = entry.get("link") or ""
                title = clean_text(entry.get("title", ""), 300)
                if not link or not title:
                    continue

                # Aggregators carry other people's work. Recording the feed
                # name as the source makes a dozen different newsrooms look
                # like one outlet endlessly correcting itself — and inflates
                # nothing, because it also hides real corroboration.
                publisher = feed["name"]
                origin = entry.get("source")
                if isinstance(origin, dict) and origin.get("title"):
                    publisher = clean_text(origin["title"], 60)
                elif int(feed.get("tier", 3)) == 4 and " - " in title:
                    headline, _, tail = title.rpartition(" - ")
                    if 2 < len(tail) < 45 and len(headline) > 20:
                        title, publisher = headline, tail
                items.append({
                    "title": title,
                    "title_en": "",
                    "lang": feed.get("lang", "en"),
                    "url": canonical_url(link),
                    "source": publisher,
                    "feed": feed["name"],
                    "tier": int(feed.get("tier", 3)),
                    "access": feed.get("access", "free"),
                    "tags": list(feed.get("tags", [])),
                    "published": entry_time(entry).isoformat(),
                    "summary": clean_text(entry.get("summary", ""), 260),
                })
    return items, errors
