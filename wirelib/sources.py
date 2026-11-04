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


# Shopping, deals and evergreen service pieces. Feeds mix these in with the
# news, and because many carry no date they used to look brand new forever.
import re as _re
SOFT = _re.compile(
    r"\b(lowest price|best deals?|deals? on|on sale|% off|discount code|coupon|promo code"
    r"|gift guide|gifts? (?:for|she|he|they)|best .{0,30} to buy|we tested|our favorite"
    r"|shop (?:the|our)|review: |recipe|horoscope|crossword|wordle|how to watch"
    r"|where to watch|live stream|streaming guide)\b", _re.IGNORECASE)


def entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


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
    # Undated items get the time we first saw them, not "now" on every run.
    # Otherwise an April tax explainer stays "breaking" into November.
    first_time = "undated" not in state
    undated = state.setdefault("undated", {})
    stamp = now_utc().isoformat()
    if first_time:
        # Anything undated already sitting in a feed on the first run is old.
        from datetime import timedelta
        stamp = (now_utc() - timedelta(days=4)).isoformat()
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
                # Social feeds (Bluesky profiles) have no titles, just the post.
                if not title and feed.get("social"):
                    title = _post_headline(entry.get("summary", ""))
                if not link or not title:
                    continue
                if SOFT.search(title):
                    continue

                # Aggregators carry other people's work. Recording the feed
                # name as the source makes a dozen different newsrooms look
                # like one outlet endlessly correcting itself — and inflates
                # nothing, because it also hides real corroboration.
                # A newsroom's social account is the same newsroom, so it can
                # name the publisher it belongs to and never counts twice.
                publisher = feed.get("publisher") or feed["name"]
                origin = entry.get("source")
                if (isinstance(origin, dict) and origin.get("title")
                        and not ("/" in origin["title"] and " " not in origin["title"])):
                    # (Some feeds put a URL path like "taxonomy/term/2" here.)
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
                    "official": bool(feed.get("official")),
                    "social": bool(feed.get("social")),
                    "access": feed.get("access", "free"),
                    "tags": list(feed.get("tags", [])),
                    "published": _published(entry, canonical_url(link), undated, stamp),
                    "summary": clean_text(entry.get("summary", ""), 260),
                })
    if first_time:
        stamp = now_utc().isoformat()
    if len(undated) > 20000:
        keep = sorted(undated.items(), key=lambda kv: kv[1], reverse=True)[:12000]
        state["undated"] = dict(keep)
    return items, errors


def _published(entry, url: str, undated: dict, stamp: str) -> str:
    when = entry_time(entry)
    if when:
        return when.isoformat()
    return undated.setdefault(url, stamp)


_LINK = _re.compile(r"(https?://\S+|\b[a-z0-9-]+\.[a-z]{2,6}/\S+)", _re.IGNORECASE)


def _post_headline(text: str) -> str:
    """A social post as a headline: links out, first sentence, sensible length."""
    text = _LINK.sub("", clean_text(text, 600)).strip(" -:|")
    text = _re.sub(r"\s{2,}", " ", text)
    first = _re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    if 40 <= len(first) <= 160:
        return first.rstrip(".")
    if len(text) <= 160:
        return text
    cut = text[:157].rsplit(" ", 1)[0]
    return cut + "…"
