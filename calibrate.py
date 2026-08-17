#!/usr/bin/env python3
"""
Check whether the desk is reading the news correctly.

  python calibrate.py                 use whatever state you already have
  python calibrate.py --live          pull the feeds first, then measure
  python calibrate.py --sweep         try a range of thresholds and compare

Everything in this tool was tuned before it had ever seen real news. That is
the honest weak point of the whole project, and this is how you close it.

It measures four things:

  SINGLETONS   share of stories nobody else carried. Too high means the
               clustering is too strict and the same event is showing up
               five times. Too low means it is merging things it shouldn't.

  SUSPECT      clusters that look over-merged: many outlets, but the
               headlines share almost no distinctive vocabulary.

  SPLITS       pairs of separate stories that probably belong together —
               near-identical headlines that never merged.

  SYNDICATION  how much of the corroboration count is real, and how often
               the independence estimate is running on thin evidence.

Read the report, change the numbers in config.yaml, run it again.
"""

from __future__ import annotations

import statistics
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from wirelib import sources as feed_sources, threads as th  # noqa: E402
from wirelib.common import (content_words, hours_since, load_state,  # noqa: E402
                            load_threads, overlap, save_state, save_threads)
from wirelib.verify import (independence_confidence, independence_groups,  # noqa: E402
                            _sig_overlap)

GOOD_SINGLETON_RANGE = (0.45, 0.80)


def load_cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def pull_live(cfg: dict) -> dict:
    """Fetch once and build threads, so the numbers describe real feeds."""
    feeds = yaml.safe_load((ROOT / "feeds.yaml").read_text(encoding="utf-8"))["feeds"]
    state, store = load_state(), load_threads()
    rules = cfg["scoring"]

    print(f"Pulling {len(feeds)} feeds. This takes a minute.\n")
    items, errors = feed_sources.collect(feeds, state)
    print(f"  {len(items)} items from {len(feeds) - len(errors)} feeds "
          f"({len(errors)} not responding)\n")

    primary = float(rules.get("cluster_threshold", 0.42))
    secondary = float(rules.get("anchor_threshold", 0.15))
    groups = th.cluster_items(items, state, primary, secondary)
    touched, fresh = th.merge_into_threads(
        groups, store, state, primary, secondary, cfg["site"]["window_hours"])
    for thread in fresh:
        for word in set(content_words(thread["title"])):
            state["terms"][word] = state["terms"].get(word, 0) + 1
        state["docs_counted"] = state.get("docs_counted", 0) + 1
    save_state(state)
    save_threads(store)
    return store


def report(store: dict, cfg: dict) -> None:
    state = load_state()
    rules = cfg["scoring"]
    aggregator_tiers = set(rules.get("aggregator_tiers", [4]))
    terms, total_docs = state["terms"], state.get("docs_counted", 0)

    live = [t for t in store.values()
            if hours_since(t["updated"]) <= cfg["site"]["window_hours"]]
    if len(live) < 25:
        print("Not enough stories yet. Run with --live, or let it collect for an hour.")
        return

    print("=" * 62)
    print(f"  CALIBRATION — {len(live)} live threads")
    print("=" * 62)

    # --- 1. singletons
    singles = [t for t in live if len({m["source"] for m in t["members"]}) == 1]
    rate = len(singles) / len(live)
    low, high = GOOD_SINGLETON_RANGE
    verdict = ("looks right" if low <= rate <= high else
               "clustering may be too strict — try lowering cluster_threshold"
               if rate > high else
               "clustering may be too loose — try raising cluster_threshold")
    print(f"\nSINGLETONS   {rate:.0%} of stories carried by one source")
    if len(live) < 200:
        print(f"             only {len(live)} threads — too few to judge. Most stories "
              f"genuinely\n             are single-source until the desk is running at "
              f"full volume.")
    else:
        print(f"             healthy range {low:.0%}-{high:.0%} — {verdict}")

    # --- 2. over-merged clusters
    suspect = []
    for thread in live:
        members = thread["members"]
        if len(members) < 3:
            continue
        token_sets = [set(content_words(m["title"])) for m in members]
        scores = [overlap(token_sets[0], other, terms, total_docs)
                  for other in token_sets[1:]]
        if scores and statistics.fmean(scores) < 0.22:
            suspect.append((statistics.fmean(scores), thread))
    print(f"\nSUSPECT      {len(suspect)} cluster(s) look over-merged")
    for score, thread in sorted(suspect)[:5]:
        print(f"             [{score:.2f}] {thread['title'][:58]}")
        for member in thread["members"][:3]:
            print(f"                   + {member['title'][:54]}")
    if suspect:
        print("             if these are genuinely different stories, raise "
              "anchor_threshold")

    # --- 3. missed merges
    pairs = []
    ranked = sorted(live, key=lambda t: t["created"], reverse=True)[:220]
    for i, a in enumerate(ranked):
        ta = set(content_words(a["title"]))
        if len(ta) < 4:
            continue          # "Cash Cow" matches everything; it means nothing
        for b in ranked[i + 1:]:
            tb = set(content_words(b["title"]))
            if len(tb) < 4 or len(ta & tb) < 3:
                continue
            score = overlap(ta, tb, terms, total_docs)
            if score >= 0.34:
                pairs.append((score, a, b))
    pairs.sort(reverse=True, key=lambda p: p[0])
    print(f"\nSPLITS       {len(pairs)} pair(s) look like the same story, unmerged")
    for score, a, b in pairs[:5]:
        print(f"             [{score:.2f}] {a['title'][:52]}")
        print(f"                    {b['title'][:52]}")
    if pairs:
        print("             if these are the same event, lower cluster_threshold "
              "toward 0.35")

    # --- 4. syndication and confidence
    carried = independent = 0
    confidence = Counter()
    for thread in live:
        groups = independence_groups(thread["members"], aggregator_tiers)
        carried += len({m["source"] for m in thread["members"]})
        independent += len(groups)
        confidence[independence_confidence(thread["members"])] += 1
    collapse = 1 - (independent / carried) if carried else 0
    print(f"\nSYNDICATION  {collapse:.0%} of outlet mentions collapse into shared copy")
    print(f"             {carried} outlet mentions → {independent} independent reports")
    print(f"             confidence: {confidence['high']} high, "
          f"{confidence['medium']} medium, {confidence['low']} low")
    if confidence["low"] > len(live) * 0.4:
        print("             many feeds ship no summary text, so independence is "
              "leaning on headline matching alone")

    # --- 5. feeds pulling their weight
    counts = Counter(m["source"] for t in live for m in t["members"])
    print(f"\nVOLUME       top sources by item count")
    for name, n in counts.most_common(8):
        print(f"             {n:>4}  {name}")
    quiet = [f["name"] for f in yaml.safe_load(
        (ROOT / "feeds.yaml").read_text(encoding="utf-8"))["feeds"]
        if f["name"] not in counts]
    print(f"\n             {len(quiet)} feed(s) contributed nothing this window")
    print("             run check_feeds.py to see which are actually dead")
    print("\n" + "=" * 62)


def sweep(store: dict, cfg: dict) -> None:
    """Show how the singleton rate responds to the clustering threshold."""
    state = load_state()
    terms, total = state["terms"], state.get("docs_counted", 0)
    live = [t for t in store.values()
            if hours_since(t["updated"]) <= cfg["site"]["window_hours"]]
    items = [{"title": m["title"], "url": m["url"], "source": m["source"],
              "tier": m["tier"], "tags": t["tags"], "published": m["published"],
              "summary": m.get("blurb", ""), "title_en": "", "lang": m.get("lang", "en")}
             for t in live for m in t["members"]]
    if len(items) < 40:
        print("Not enough material to sweep. Run --live first.")
        return

    print(f"\nSWEEP — {len(items)} articles\n")
    print(f"  {'threshold':>10}  {'clusters':>9}  {'singletons':>11}  {'biggest':>8}")
    for value in (0.30, 0.34, 0.38, 0.42, 0.46, 0.52, 0.60):
        groups = th.cluster_items(items, state, value,
                                  float(cfg["scoring"].get("anchor_threshold", 0.15)))
        sizes = [len({i["source"] for i in g["items"]}) for g in groups]
        singles = sum(1 for s in sizes if s == 1) / len(sizes)
        marker = "  <- current" if abs(
            value - cfg["scoring"]["cluster_threshold"]) < 0.001 else ""
        print(f"  {value:>10.2f}  {len(groups):>9}  {singles:>10.0%}  "
              f"{max(sizes):>8}{marker}")
    print("\n  Aim for a singleton rate between 45% and 80%. Below that, check the")
    print("  SUSPECT list above — cheap merging looks efficient and isn't.\n")


def main() -> int:
    cfg = load_cfg()
    store = pull_live(cfg) if "--live" in sys.argv else load_threads()
    if not store:
        print("No threads on file. Run: python calibrate.py --live")
        return 1
    report(store, cfg)
    if "--sweep" in sys.argv:
        sweep(store, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
