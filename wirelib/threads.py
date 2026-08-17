"""
Story threads.

A thread is one real-world event, tracked across every outlet that reports it
and every time the wording changes. Threads persist between runs, which is
what makes velocity and confirmation possible: you can only measure how fast
a story is spreading if you remember what it looked like an hour ago.
"""

from __future__ import annotations

from .common import (content_words, digest, hours_since, now_utc, overlap,
                     parse_ts, related)
from .translate import display_title
from .verify import (classify_change, find_revision, independence,
                     shingles)

MAX_MEMBERS = 60
MAX_HISTORY = 25
MAX_PICKUP = 80


# ------------------------------------------------- within-run clustering

def cluster_items(items: list[dict], state: dict, threshold: float,
                  secondary: float = 0.15) -> list[dict]:
    """Group this run's articles into candidate stories."""
    terms, total = state["terms"], state.get("docs_counted", 0)

    unique: dict[str, dict] = {}
    for item in items:
        key = digest(item["url"])
        if key not in unique:
            unique[key] = item

    groups: list[dict] = []
    for item in sorted(unique.values(), key=lambda i: i["published"], reverse=True):
        tokens = set(content_words(display_title(item)))
        alert = "alert" in (item.get("tags") or [])
        placed = False
        for group in groups:
            # Automated alert feeds use one template for every event, so two
            # unrelated earthquakes read as the same story. They may join
            # human-written coverage, never each other.
            if alert and all("alert" in (i.get("tags") or []) for i in group["items"]):
                continue
            if any(related(tokens, member, terms, total, threshold, secondary)
                   for member in group["token_sets"]):
                group["items"].append(item)
                group["token_sets"].append(tokens)
                group["tokens"] |= tokens
                placed = True
                break
        if not placed:
            groups.append({"items": [item], "tokens": set(tokens),
                           "token_sets": [tokens]})
    return groups


# ------------------------------------------------------ thread persistence

def _new_thread(group: dict, tags: list[str]) -> dict:
    lead = min(group["items"], key=lambda i: (i["tier"], i["published"]))
    stamp = now_utc().isoformat()
    return {
        "id": digest(lead["url"]),
        "created": stamp,
        "updated": stamp,
        "title": display_title(lead),
        "url": lead["url"],
        "source": lead["source"],
        "tier": lead["tier"],
        "access": lead.get("access", "free"),
        "tags": tags,
        "tokens": sorted(group["tokens"])[:60],
        # Each absorbed report keeps its OWN word list. Pooling them into one
        # set lets threads chain: A matches B, B's words join the pool, C
        # matches B through the pool while having nothing to do with A. Over
        # thousands of stories that snowballs into grab-bags.
        "lead_tokens": sorted(group["tokens"])[:40],
        "token_sets": [sorted(group["tokens"])[:40]],
        "members": [],
        "history": [],
        "pickup": [],
        "starter": lead["source"],
        "credited_lead": False,
        "credited_scoop": False,
        "email_level": 0,
    }


def _absorb(thread: dict, group: dict) -> list[dict]:
    """Fold this run's articles into the thread. Returns genuinely new members."""
    known = {m["url"] for m in thread["members"]}
    stamp = now_utc().isoformat()
    fresh = []

    for item in group["items"]:
        if item["url"] in known:
            continue
        member = {
            "url": item["url"],
            "title": display_title(item),
            "original": item["title"] if item.get("title_en") else "",
            "lang": item.get("lang", "en"),
            "source": item["source"],
            "tier": item["tier"],
            "access": item.get("access", "free"),
            "published": item["published"],
            "seen": stamp,
            "blurb": item.get("summary", "")[:200],
            # Fingerprint of the prose, so republished wire copy can be spotted.
            "sig": shingles(f"{item['title']} {item.get('summary', '')}"),
        }
        # Did this outlet just refile its own story with something changed?
        prior = (None if "alert" in (item.get("tags") or [])
                 else find_revision(thread["members"], member))
        # A correction only counts on a story others are also covering. A
        # lone templated feed item refiling itself is not news being revised,
        # and precision matters far more than recall here — one bogus
        # CORRECTION badge costs more trust than ten missed ones.
        corroborated = len({m["source"] for m in thread["members"]}) >= 2
        if prior and corroborated:
            change = classify_change(prior["title"], member["title"])
            if change:
                change["source"] = member["source"]
                thread.setdefault("changes", []).append(change)
                thread["changes"] = thread["changes"][-MAX_HISTORY:]

        thread["members"].append(member)
        fresh.append(member)
        known.add(item["url"])

    thread["tags"] = sorted(set(thread["tags"]) | {t for i in group["items"] for t in i["tags"]})
    thread["tokens"] = sorted(group["tokens"])[:60]
    sets = thread.setdefault("token_sets", [thread["tokens"]])
    sets.append(sorted(group["tokens"])[:40])
    thread["token_sets"] = sets[-25:]
    thread["updated"] = stamp

    # The most trusted, earliest article owns the headline.
    best = min(thread["members"], key=lambda m: (m["tier"], m["published"]))
    if best["title"] != thread["title"]:
        # Recorded as history, NOT as a correction. Swapping to a more
        # trusted outlet's wording is the thread reorganising itself; a
        # correction is one newsroom changing its own story, which is caught
        # per-source above.
        thread["history"].append({"ts": stamp, "title": thread["title"],
                                  "source": thread["source"]})
        thread["history"] = thread["history"][-MAX_HISTORY:]
        thread.update(title=best["title"], url=best["url"], source=best["source"],
                      tier=best["tier"], access=best.get("access", "free"))
        thread["lead_tokens"] = sorted(content_words(best["title"]))[:40]

    # Record the pickup curve: how many distinct outlets, and when.
    outlets = len({m["source"] for m in thread["members"]})
    if not thread["pickup"] or thread["pickup"][-1]["n"] != outlets:
        thread["pickup"].append({"ts": stamp, "n": outlets})
        thread["pickup"] = thread["pickup"][-MAX_PICKUP:]

    thread["members"] = sorted(thread["members"], key=lambda m: m["seen"])[:MAX_MEMBERS]
    return fresh


def merge_into_threads(groups: list[dict], threads: dict, state: dict,
                       threshold: float, window_hours: float,
                       secondary: float = 0.15) -> tuple[list[dict], list[dict]]:
    """Match this run's story groups onto existing threads, or start new ones."""
    terms, total = state["terms"], state.get("docs_counted", 0)

    live = [t for t in threads.values() if hours_since(t["updated"]) <= window_hours * 2]
    live_tokens = [(t, set(t.get("lead_tokens") or t["tokens"])) for t in live]

    touched, brand_new = [], []

    for group in groups:
        best_thread, best_score = None, 0.0
        for thread, lead in live_tokens:
            # Everything joining a thread must match the LEAD story, not just
            # some member of it. Matching any member still allows drift: A
            # joins, B matches A, C matches B while having nothing to do with
            # A, and the thread wanders away from what it started as.
            if not related(group["tokens"], lead, terms, total, threshold, secondary):
                continue
            score = overlap(group["tokens"], lead, terms, total)
            if score > best_score:
                best_thread, best_score = thread, score

        if best_thread is None:
            tags = sorted({t for i in group["items"] for t in i["tags"]})
            best_thread = _new_thread(group, tags)
            # Thread ids come from the lead article's URL. Two stories can
            # land on the same id, and writing straight into the dict lets
            # the newcomer evict a live thread — leaving an orphan that is
            # still referenced elsewhere but never scored again.
            if best_thread["id"] in threads:
                suffix = 1
                base = best_thread["id"]
                while f"{base}-{suffix}" in threads:
                    suffix += 1
                best_thread["id"] = f"{base}-{suffix}"
            threads[best_thread["id"]] = best_thread
            live_tokens.append((best_thread, set(best_thread["lead_tokens"])))
            brand_new.append(best_thread)

        fresh = _absorb(best_thread, group)
        if fresh:
            best_thread["_fresh"] = fresh
            touched.append(best_thread)

    return touched, brand_new


# ------------------------------------------------------------- measurements

def outlets(thread: dict) -> int:
    return len({m["source"] for m in thread["members"]})


def velocity(thread: dict, window_hours: float) -> float:
    """
    Outlets picked up per hour, recently.

    Volume tells you a story is big. Velocity tells you it is *becoming* big —
    one outlet to eight in forty minutes is the shape of a story breaking, and
    it looks nothing like eight outlets that all filed yesterday.
    """
    curve = thread.get("pickup") or []
    if len(curve) < 2:
        return 0.0
    now = now_utc()
    current = curve[-1]["n"]
    earlier = None
    for point in curve:
        if (now - parse_ts(point["ts"])).total_seconds() / 3600 <= window_hours:
            earlier = point
            break
    if earlier is None or earlier is curve[-1]:
        earlier = curve[0]
    span = (parse_ts(curve[-1]["ts"]) - parse_ts(earlier["ts"])).total_seconds() / 3600
    span = max(span, 0.25)
    gained = current - earlier["n"]
    return max(0.0, gained / span)


def independent_count(thread: dict, aggregator_tiers: set[int]) -> int:
    """
    How many genuinely separate newsrooms have this?

    Not the same as the outlet count. Eight papers running the same Reuters
    copy is one report syndicated eight times, and treating it as eight
    confirmations is how an aggregator ends up shouting about a single
    unverified wire item.
    """
    count, _ = independence(thread, aggregator_tiers)
    return count


def confirmation(thread: dict, aggregator_tiers: set[int]) -> str:
    """
    PRIMARY     — straight from the source (a court, an agency, a seismograph)
    CONFIRMED   — two or more *independent* newsrooms
    UNCONFIRMED — one so far, however many outlets reprinted it
    """
    if thread["tier"] == 1:
        return "PRIMARY"
    if independent_count(thread, aggregator_tiers) >= 2:
        return "CONFIRMED"
    return "UNCONFIRMED"


# ----------------------------------------------------------- source ledger

def _stat(state: dict, source: str) -> dict:
    book = state.setdefault("sources", {})
    return book.setdefault(source, {
        "items": 0, "started": 0, "scoops": 0, "orphans": 0,
        "lead_minutes": 0.0, "lead_count": 0,
    })


def record_items(state: dict, items: list[dict]) -> None:
    for item in items:
        _stat(state, item["source"])["items"] += 1


def record_thread_events(state: dict, threads_touched: list[dict],
                         new_threads: list[dict]) -> None:
    """
    Keep score on the feeds themselves.

    Who broke it first, who confirmed it, and who files things nobody else
    ever corroborates. After a month this tells you which of your sources
    actually earn their place.
    """
    for thread in new_threads:
        _stat(state, thread["starter"])["started"] += 1

    for thread in threads_touched:
        members = sorted(thread["members"], key=lambda m: m["seen"])
        distinct = {m["source"] for m in members}

        # How far ahead of the second outlet was the one that broke it?
        if len(distinct) >= 2 and not thread.get("credited_lead"):
            first = members[0]
            second = next((m for m in members if m["source"] != first["source"]), None)
            if second:
                minutes = (parse_ts(second["seen"]) - parse_ts(first["seen"])).total_seconds() / 60
                stat = _stat(state, first["source"])
                stat["lead_minutes"] += max(0.0, minutes)
                stat["lead_count"] += 1
                thread["credited_lead"] = True

        # A scoop: they had it first, and it turned out to be a real story.
        if len(distinct) >= 3 and not thread.get("credited_scoop"):
            _stat(state, thread["starter"])["scoops"] += 1
            thread["credited_scoop"] = True


def record_orphans(state: dict, expiring: list[dict]) -> None:
    """Threads aging out that nobody else ever picked up."""
    for thread in expiring:
        if outlets(thread) == 1 and thread["tier"] >= 3:
            _stat(state, thread["starter"])["orphans"] += 1


def reliability(stat: dict) -> float:
    """0-1. Corroborated scoops good, permanent orphans bad, priors keep it sane."""
    scoops, orphans = stat.get("scoops", 0), stat.get("orphans", 0)
    return (scoops + 1) / (scoops + orphans + 2)


def avg_lead_minutes(stat: dict) -> float:
    count = stat.get("lead_count", 0)
    return stat["lead_minutes"] / count if count else 0.0
