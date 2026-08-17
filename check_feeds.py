#!/usr/bin/env python3
"""
Test every feed in feeds.yaml and report which ones are working.

  python check_feeds.py           # check all
  python check_feeds.py --prune   # write feeds.yaml with dead ones commented out

Feeds break constantly — outlets move URLs, drop RSS, or block bots.
Run this whenever the page looks thin.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).parent
from wirelib.common import BROWSER_UA, UA


def test(feed):
    try:
        resp = requests.get(feed["url"], headers={"User-Agent": UA}, timeout=20)
        if resp.status_code in (403, 406, 429):
            resp = requests.get(
                feed["url"], timeout=20,
                headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
    except requests.RequestException as exc:
        return feed, "FAIL", type(exc).__name__
    if resp.status_code >= 400:
        return feed, "FAIL", f"HTTP {resp.status_code}"
    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        return feed, "EMPTY", "parsed but no entries"
    return feed, "OK", f"{len(parsed.entries)} entries"


def main():
    feeds = yaml.safe_load(open(ROOT / "feeds.yaml", encoding="utf-8"))["feeds"]
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for feed, status, detail in pool.map(test, feeds):
            results.append((status, feed["name"], detail, feed["url"]))
            print(f"{status:6} {feed['name']:38.38} {detail}")

    ok = sum(1 for r in results if r[0] == "OK")
    print(f"\n{ok}/{len(results)} feeds healthy")

    bad = [r for r in results if r[0] != "OK"]
    if bad:
        print("\nNot working:")
        for _, name, detail, url in bad:
            print(f"  {name} — {detail}\n    {url}")

    if "--prune" in sys.argv and bad:
        text = (ROOT / "feeds.yaml").read_text(encoding="utf-8")
        dead_urls = {r[3] for r in bad}
        lines = []
        for line in text.splitlines():
            if any(u in line for u in dead_urls) and not line.strip().startswith("#"):
                lines.append(f"  # DEAD {line.strip()}")
            else:
                lines.append(line)
        text = "\n".join(lines) + "\n"
        (ROOT / "feeds.yaml").write_text(text, encoding="utf-8")
        print(f"\nCommented out {len(bad)} dead feeds in feeds.yaml")


if __name__ == "__main__":
    main()
