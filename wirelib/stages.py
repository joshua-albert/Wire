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

from .common import content_words, hours_since, parse_ts

SPOTTED, SPREADING, CONFIRMED, CHANGED = "spotted", "spreading", "confirmed", "changed"
RANK = {SPOTTED: 0, SPREADING: 1, CONFIRMED: 2, CHANGED: 3}

# A correction stays a "changed" story for this long, then the story goes
# back to its normal stage (the correction is still shown on its page).
CHANGED_HOURS = 12
SPREAD_MIN_VELOCITY = 1.0     # independent-ish outlets per hour
SPREAD_MAX_AGE = 12           # hours since first report


def official_names(feeds: list[dict]) -> set[str]:
    return {f["name"] for f in feeds if f.get("official")}


def report_time(member: dict):
    """
    When this report actually went out: the outlet's own timestamp, as long
    as it isn't in the future or wildly old. Falls back to when we saw it.
    (Using "when we saw it" alone made stories published overnight look like
    this morning's news after any gap in updates.)
    """
    seen = parse_ts(member["seen"])
    try:
        pub = parse_ts(member["published"])
    except (KeyError, ValueError, TypeError):
        return seen
    if seen - timedelta(hours=48) <= pub <= seen + timedelta(minutes=5):
        return min(pub, seen)
    return seen


def first_seen(thread: dict) -> str:
    times = [report_time(m) for m in thread.get("members", []) if m.get("seen")]
    return min(times).isoformat() if times else thread["created"]


def on_story(member: dict, thread: dict) -> bool:
    """
    Does this report plainly share the thread's subject? A guard for what we
    show as "the latest" on a story: if the newest report doesn't share real
    words with the headline, we don't present it as an update to it.
    """
    if member["url"] == thread["url"]:
        return True
    a = set(content_words(member.get("title", "")))
    b = set(content_words(thread["title"])) | set(thread.get("lead_tokens") or [])
    if not a or not b:
        return False
    shared = len(a & b)
    return shared >= 3 or (shared >= 2 and shared / min(len(a), len(b)) >= 0.5)


def _core(thread: dict) -> list[dict]:
    return [m for m in thread.get("members", []) if m.get("seen") and on_story(m, thread)]


def newest_report(thread: dict) -> dict | None:
    """The most recent on-story report, skipping search-aggregator copies."""
    core = _core(thread)
    members = [m for m in core if m.get("tier", 3) < 4] or core
    return max(members, key=report_time) if members else None


def last_report(thread: dict) -> str:
    times = [report_time(m) for m in _core(thread)]
    return max(times).isoformat() if times else first_seen(thread)


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
        thread["_newest"] = newest_report(thread)


def minutes_since(stamp: str) -> float:
    return hours_since(stamp) * 60


def newest_first(threads: list[dict]) -> list[dict]:
    return sorted(threads, key=lambda t: parse_ts(t["_first"]), reverse=True)


def latest_activity(threads: list[dict]) -> list[dict]:
    """Newest development first: a new report on an old story counts as new."""
    return sorted(threads, key=lambda t: parse_ts(t["_last"]), reverse=True)
