#!/usr/bin/env python3
"""
THE WIRE — a personal breaking-news desk.

Pulls every feed in feeds.yaml, folds the same story from different outlets
into one thread, tracks how fast each thread spreads, publishes a plain
clickable page, and emails you when something clears the bar.

  python wire.py
"""

from __future__ import annotations

import sys
import time
from datetime import timedelta

import yaml

from wirelib import beats, mailer, render, sources, threads as th, translate, verify
from wirelib.common import (ROOT, content_words, hours_since, load_state,
                            load_threads, now_utc, parse_ts, save_state,
                            save_threads)
from wirelib.scoring import score_thread
import os


def load_yaml(name: str) -> dict:
    with open(ROOT / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    cfg = load_yaml("config.yaml")
    feeds = load_yaml("feeds.yaml")["feeds"]
    state = load_state()
    store = load_threads()

    site = cfg["site"]
    rules = cfg["scoring"]
    threshold = float(rules.get("cluster_threshold", 0.42))

    # --- 1. pull
    started = time.time()
    items, errors = sources.collect(feeds, state)
    print(f"fetched {len(items)} items from {len(feeds) - len(errors)}/{len(feeds)} "
          f"feeds in {time.time() - started:.1f}s")
    for name, error in sorted(errors.items()):
        print(f"  dead: {name} — {error}")

    window = now_utc() - timedelta(hours=site["window_hours"])
    items = [i for i in items if parse_ts(i["published"]) >= window]

    # --- 2. translate anything not in English
    translate.translate_headlines(items, state, cfg.get("translation", {}).get("enabled", True))

    # --- 3. cluster, then fold onto threads that already exist
    secondary = float(rules.get("anchor_threshold", 0.15))
    groups = th.cluster_items(items, state, threshold, secondary)
    touched, brand_new = th.merge_into_threads(
        groups, store, state, threshold, site["window_hours"], secondary)

    for thread in brand_new + touched:
        beats.tag_thread(thread)

    th.record_items(state, items)
    th.record_thread_events(state, touched, brand_new)
    beats.record_activity(state, brand_new)

    # Vocabulary only learns from genuinely new stories — otherwise a headline
    # that sits in the window for 36 hours gets counted on every run and the
    # rarity model goes flat.
    for thread in brand_new:
        for word in set(content_words(thread["title"])):
            state["terms"][word] = state["terms"].get(word, 0) + 1
        state["docs_counted"] = state.get("docs_counted", 0) + 1

    # --- 4. score everything still inside the window
    live = [t for t in store.values() if hours_since(t["updated"]) <= site["window_hours"]]
    for thread in live:
        if "countries" not in thread:
            beats.tag_thread(thread)
        score_thread(thread, cfg, state)
    live.sort(key=lambda t: t["_score"], reverse=True)

    # --- 5. re-check thin stories for link rot, then rescore what moved
    if cfg.get("verification", {}).get("check_link_rot", True):
        pulled = verify.check_link_rot(
            live, limit=int(cfg.get("verification", {}).get("recheck_per_run", 25)))
        if pulled:
            print(f"link rot: {pulled} single-source stor(ies) pulled by the outlet")
            for thread in live:
                score_thread(thread, cfg, state)
            live.sort(key=lambda t: t["_score"], reverse=True)

    # --- 6. publish
    site_url = (os.environ.get("SITE_URL") or "").strip()
    render.write_all(live, cfg, errors, feeds, state, site_url)
    flagged = sum(1 for t in live if t.get("_flag"))
    unusual = len(beats.anomalies(state))
    print(f"wrote docs/ — {len(live)} threads, {len(brand_new)} new, "
          f"{flagged} with corrections, {unusual} unusual beats")

    # --- 7. mail
    scored = {id(t) for t in live}
    fresh = [t for t in touched if id(t) in scored]
    seen_ids = {id(t) for t in fresh}
    fresh += [t for t in live if t.get("_flag") and t.get("email_level", 0) >= 1
              and id(t) not in seen_ids]
    # Email is a convenience. The site is the product. A failure here must
    # never stop the front page from being published.
    try:
        mailer.decide_and_send(fresh, cfg, state, site_url or "your site")
    except Exception as exc:  # noqa: BLE001
        print(f"email: skipped after an error — {type(exc).__name__}: {exc}")

    # --- 8. housekeeping
    keep_days = int(site.get("thread_retention_days", 5))
    expiring = [t for t in store.values() if hours_since(t["updated"]) > keep_days * 24]
    th.record_orphans(state, expiring)
    for thread in expiring:
        store.pop(thread["id"], None)
    for thread in store.values():
        for key in [k for k in thread if k.startswith("_")]:
            del thread[key]

    if len(state["terms"]) > 60000:
        ranked = sorted(state["terms"].items(), key=lambda kv: kv[1], reverse=True)
        state["terms"] = dict(ranked[:40000])
    state["dead_feeds"] = errors

    save_threads(store)
    save_state(state)
    print(f"state: {len(store)} threads retained, {len(state['terms'])} terms known")
    return 0


if __name__ == "__main__":
    sys.exit(main())
