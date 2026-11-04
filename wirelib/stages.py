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

import re
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


# What a headline is about, from its words. Feed tags alone aren't enough:
# AP's "Dow soars 1,000 points at open" comes from a general news feed, so
# it never reached the Money tab. Patterns are shared with the page script,
# so they stick to syntax both Python and JavaScript understand.
TOPIC_WORDS = {
    "money": r"\b(stocks?|shares|markets?|wall street|dow|s&p|nasdaq|futures|treasur(y|ies)"
             r"|bond yields?|yields|federal reserve|the fed|fed (chair|officials|rate)"
             r"|rate (cut|hike)s?|interest rates?|inflation|cpi|jobs report|payrolls"
             r"|earnings|profits?|revenue|ipo|bitcoin|crypto|oil prices?|crude|gold price"
             r"|the dollar|dollar index|u\\.s\\. dollar|tariffs?|recession|gdp|economy|economic|bank(s|ing)?|layoffs?|merger"
             r"|acquisition|billion deal|investors?|traders?|rall(y|ies|ied)|sell-?off)\b",
    "elections": r"\b(elections?|elect(s|ed)?|voters?|voting|ballots?|polls? (close|open)"
                 r"|concede[sd]?|midterms?|primar(y|ies)|runoff|recount|race call|projected (winner|to win)"
                 r"|wins? (the )?(race|seat|election|governorship|senate|house)"
                 r"|(governor|senate|house|mayoral)'?s? race|flips?|turnout|exit polls?)\b",
    "war": r"\b(war|missiles?|drones?|troops|ceasefire|shelling|invasion|airstrikes?|air strikes?"
           r"|military|offensive|militants?|rebels?|frontline|front line|army|navy|bombing"
           r"|hostages?|nato|pentagon)\b",
    "justice": r"\b(police|officers?|court|judge|lawsuit|sued|indicted|charged|sentenced"
               r"|prison|jail|supreme court|civil rights|arrested|prosecutors?|trial|verdict"
               r"|doj|fbi|ice agents?|deport(ed|ation)s?)\b",
    "env": r"\b(climate|global warming|wildfires?|forest fires?|flood(s|ed|ing)?|hurricanes?"
           r"|tropical storm|winter storm|snowstorm|blizzard|earthquakes?|quake|tsunami|volcan(o|ic)"
           r"|heat ?waves?|drought|emissions|carbon|tornado(es)?|cyclones?|typhoons?|landslides?"
           r"|mudslides?|pollution|air quality|wildlife|species|extinction|deforestation|glaciers?"
           r"|sea levels?|oceans?|coral|environmental|environmentalists?|epa|renewables?|solar|wind power"
           r"|fossil fuels?|cop\d+|weather service|heavy rain|rainfall|snowfall|freeze warning|flash flood)\b",
    "sci": r"\b(study|scientists?|research(ers)?|nasa|vaccines?|disease|outbreak|virus|health"
           r"|cancer|ai|artificial intelligence|spacex|rocket|astronauts?|moon|mars|medical|hospital|fda|cdc)\b",
    "philly": r"\b(philadelphia|philly|phl|septa|ppa|center city|south philly|north philly"
              r"|west philly|northeast philly|southwest philly|fishtown|kensington|germantown"
              r"|manayunk|roxborough|point breeze|passyunk|northern liberties|port richmond"
              r"|frankford|mayfair|olney|nicetown|strawberry mansion|mantua|university city"
              r"|grays ferry|brewerytown|rittenhouse|penn'?s landing|schuylkill|delaware county"
              r"|delco|chester county|montgomery county|montco|bucks county|camden|cherry hill"
              r"|south jersey|main line|upper darby|norristown|king of prussia|chester, pa"
              r"|temple university|temple owls|drexel|villanova|upenn|penn medicine"
              r"|jefferson health|philadelphia city council|krasner|cherelle parker|mayor parker"
              r"|eagles|phillies|sixers|76ers|flyers|union fc|wawa)\b",
    "uspol": r"\b(congress|senate|senators?|house (speaker|republicans|democrats)|white house"
             r"|trump|vance|democrats?|republicans?|gop|administration|governor|capitol)\b",
}
_TOPIC_RX = {k: re.compile(v, re.IGNORECASE) for k, v in TOPIC_WORDS.items()}


FEEDS: dict[str, dict] = {}


def set_feeds(feeds: list[dict]) -> None:
    FEEDS.clear()
    for f in feeds:
        FEEDS.setdefault(f.get("publisher") or f["name"], f)


def _trusted_tags(source: str) -> set[str]:
    """
    Feed tags only count from specialist outlets. A general newsroom (the
    Inquirer, WHYY, a social account) covers everything, so its "philly" or
    "money" label says nothing about any one story.
    """
    feed = FEEDS.get(source)
    if not feed or feed.get("mixed") or feed.get("social") or int(feed.get("tier", 3)) == 4:
        return set()
    return set(feed.get("tags", [])) - {"world", "alert"}


def topics_for(thread: dict) -> list[str]:
    """What the story is about: its headline first, specialist outlets second."""
    lead = next((m for m in thread.get("members", []) if m["url"] == thread["url"]), None)
    text = f'{thread.get("title", "")} {(lead or {}).get("blurb", "")}'
    found = {"world"} & set(thread.get("tags", []))
    for topic, rx in _TOPIC_RX.items():
        if rx.search(text):
            found.add(topic)
    # Only small stories borrow a specialist outlet's label. On big stories
    # the union of every outlet's labels is noise.
    sources = {m["source"] for m in thread.get("members", [])}
    if len(sources) <= 2:
        for src in sources:
            found |= _trusted_tags(src)
    return sorted(found)


def annotate(threads: list[dict], official: set[str]) -> None:
    """Stamp stage and timing on every live thread. Underscore keys aren't saved."""
    for thread in threads:
        thread["_stage"] = classify(thread, official)
        thread["_official"] = is_official(thread, official)
        thread["_first"] = first_seen(thread)
        thread["_last"] = last_report(thread)
        thread["_abroad"] = abroad_first(thread)
        thread["_newest"] = newest_report(thread)
        thread["_topics"] = topics_for(thread)


def minutes_since(stamp: str) -> float:
    return hours_since(stamp) * 60


def newest_first(threads: list[dict]) -> list[dict]:
    return sorted(threads, key=lambda t: parse_ts(t["_first"]), reverse=True)


def latest_activity(threads: list[dict]) -> list[dict]:
    """Newest development first: a new report on an old story counts as new."""
    return sorted(threads, key=lambda t: parse_ts(t["_last"]), reverse=True)
