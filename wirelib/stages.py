"""
Where each story is in its life.

Every aggregator sorts by topic or by an opaque "importance" number. A wire
editor thinks in stages instead: someone just reported it, it's catching,
it's nailed down, or it changed. The front page is built on these.

  spotted    one newsroom so far (however many sites reprinted it)
  spreading  independent newsrooms are piling on right now
  confirmed  two or more independent newsrooms, or an official source
  changed    a number moved, a claim was qualified, or the story was pulled

A story can only be in one stage at a time. "changed" outranks the rest,
because a correction is the thing you most need to know about a story you
may already have read.
"""

from __future__ import annotations

from datetime import timedelta

from .common import hours_since, parse_ts

SPOTTED, SPREADING, CONFIRMED, CHANGED = "spotted", "spreading", "confirmed", "changed"
RANK = {SPOTTED: 0, SPREADING: 1, CONFIRMED: 2, CHANGED: 3}

# A correction stays a "changed" story for this long, then the story goes
# back to its normal stage (the correction is still shown on its page).
CHANGED_HOURS = 12
SPREAD_MIN_VELOCITY = 1.0     # independent-ish outlets per hour
SPREAD_MAX_AGE = 12           # hours since first report


def official_names(feeds: list[dict]) -> set[str]:
    return {f["name"] for f in feeds if f.get("official")}


def first_seen(thread: dict) -> str:
    """
    When the story first went out. The outlet's own timestamp where it's
    believable (we check feeds every 15 minutes, so "published" can be a few
    minutes earlier than when we saw it), otherwise when we first saw it.
    """
    best = None
    for m in thread.get("members", []):
        if not m.get("seen"):
            continue
        seen = parse_ts(m["seen"])
        when = seen
        try:
            pub = parse_ts(m["published"])
            if seen - timedelta(hours=3) <= pub <= seen:
                when = pub
        except (KeyError, ValueError, TypeError):
            pass
        if best is None or when < best:
            best = when
    return best.isoformat() if best else thread["created"]


def last_report(thread: dict) -> str:
    seen = [m["seen"] for m in thread.get("members", []) if m.get("seen")]
    return max(seen) if seen else thread["updated"]


def is_official(thread: dict, official: set[str]) -> bool:
    return any(m["source"] in official for m in thread.get("members", []))


def classify(thread: dict, official: set[str]) -> str:
    flag = thread.get("_flag")
    if thread.get("_pulled"):
        return CHANGED
    if flag and hours_since(flag["ts"]) <= CHANGED_HOURS:
        return CHANGED

    independent = thread.get("_independent", 1)
    age = hours_since(first_seen(thread))
    if (thread.get("_velocity", 0) >= SPREAD_MIN_VELOCITY and independent >= 2
            and age <= SPREAD_MAX_AGE):
        return SPREADING
    if independent >= 2 or is_official(thread, official):
        return CONFIRMED
    return SPOTTED


def abroad_first(thread: dict) -> bool:
    """
    Reported by local press in another language, and not yet by any major
    English-language newsroom. The stories that are big somewhere before
    they're big here.
    """
    members = thread.get("members", [])
    foreign = [m for m in members if m.get("lang", "en") != "en"]
    if not foreign:
        return False
    major_english = [m for m in members if m.get("lang", "en") == "en" and m.get("tier", 3) <= 2]
    return not major_english


def annotate(threads: list[dict], official: set[str]) -> None:
    """Stamp stage and timing on every live thread. Underscore keys aren't saved."""
    for thread in threads:
        thread["_stage"] = classify(thread, official)
        thread["_official"] = is_official(thread, official)
        thread["_first"] = first_seen(thread)
        thread["_last"] = last_report(thread)
        thread["_abroad"] = abroad_first(thread)


def minutes_since(stamp: str) -> float:
    return hours_since(stamp) * 60


def newest_first(threads: list[dict]) -> list[dict]:
    return sorted(threads, key=lambda t: parse_ts(t["_first"]), reverse=True)
