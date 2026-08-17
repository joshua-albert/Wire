"""What floats to the top, and why."""

from __future__ import annotations

import math

from .common import content_words, hours_since, norm_title
from .threads import (avg_lead_minutes, confirmation, independent_count,
                      outlets, reliability, velocity)
from .verify import latest_flag


def novelty(tokens: list[str], term_counts: dict, total_docs: int) -> float:
    """
    How unfamiliar is this story's vocabulary? Runs 0-1.

    The desk remembers every headline it has read. A story about a town it
    has never seen named, using words it rarely encounters, scores high —
    that's a small story in a small place, before anyone decides it's big.
    """
    if not tokens or total_docs < 200:
        return 0.0
    scores = sorted(
        (math.log((total_docs + 1) / (term_counts.get(w, 0) + 1)) for w in tokens),
        reverse=True,
    )[:5]
    if not scores:
        return 0.0
    ceiling = math.log(total_docs + 1)
    return min(1.0, (sum(scores) / len(scores)) / ceiling) if ceiling else 0.0


def score_thread(thread: dict, cfg: dict, state: dict) -> dict:
    rules = cfg["scoring"]
    text = norm_title(thread["title"])

    total = float(rules["tier_bonus"].get(thread["tier"], 0))

    hits = []
    for term, weight in cfg["urgency_terms"].items():
        if term in text:
            total += weight
            hits.append(term)
    for term, weight in cfg["interest_terms"].items():
        if term in text:
            total += weight
            hits.append(term)

    aggregator_tiers = set(rules.get("aggregator_tiers", [4]))
    carried = outlets(thread)
    independent = independent_count(thread, aggregator_tiers)
    # Corroboration counts independent newsrooms, not republished copies.
    total += max(0, independent - 1) * rules["corroboration_bonus"]
    total += max(0, carried - independent) * rules.get("syndication_bonus", 0.4)

    speed = velocity(thread, rules.get("velocity_window_hours", 3))
    total += min(speed, rules.get("velocity_cap", 8)) * rules.get("velocity_weight", 3.0)

    fresh = novelty(content_words(thread["title"]), state["terms"], state.get("docs_counted", 0))
    total += fresh * rules.get("novelty_weight", 10.0)

    status = confirmation(thread, aggregator_tiers)
    if status == "UNCONFIRMED":
        total += rules.get("unconfirmed_penalty", -3)

    stat = state.get("sources", {}).get(thread["source"])
    trust = 0.5
    if stat and (stat.get("scoops") or stat.get("orphans")):
        trust = reliability(stat)
        total += (trust - 0.5) * 2 * rules.get("reliability_weight", 4.0)

    flag = latest_flag(thread)
    if flag:
        total += rules.get("correction_bonus", 6.0)
        thread["_flag"] = flag
    if thread.get("_pulled"):
        total += rules.get("pulled_bonus", 4.0)

    age = hours_since(thread["created"])
    total -= age * rules["decay_per_hour"]

    thread["_score"] = round(total, 1)
    thread["_novelty"] = round(fresh, 2)
    thread["_velocity"] = round(speed, 2)
    thread["_outlets"] = carried
    thread["_independent"] = independent
    thread["_status"] = status
    thread["_age"] = round(age, 1)
    thread["_hits"] = hits
    thread["_trust"] = round(trust, 2)
    thread["_lead_minutes"] = round(avg_lead_minutes(stat), 1) if stat else 0.0
    return thread
