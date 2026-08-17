"""
Verification: who actually reported this, and did the story hold up?

Two jobs that a wire editor would consider table stakes and most aggregators
get wrong.

INDEPENDENCE. Eight outlets carrying the same AP story is one source
syndicated eight times, not eight confirmations. Counting it as eight inflates
every downstream number — the score, the badge, the alert. This module
collapses syndicated copies into a single independent voice.

CORRECTIONS. A headline that changes is not automatically a story developing.
Sometimes it's a walk-back. Numbers moving, hedges appearing, a link going
dead — these are different events and get labelled differently.
"""

from __future__ import annotations

import difflib
import re
import zlib
from concurrent.futures import ThreadPoolExecutor

import requests

from .common import UA, digest, norm_title, now_utc, parse_ts

# Agencies whose copy gets republished verbatim all over the world.
WIRE_PATTERN = re.compile(
    r"\b(reuters|associated press|\bap\b|agence france[- ]presse|\bafp\b|bloomberg"
    r"|dpa|pa media|press association|efe|ansa|xinhua|anadolu|interfax|tass"
    r"|kyodo|yonhap|ians|pti|sputnik|upi)\b",
    re.IGNORECASE,
)

# Language that means the outlet is walking something back.
CORRECTION_WORDS = re.compile(
    r"\b(correct(?:ion|ed)|retract(?:ed|ion)|clarif(?:y|ies|ication)|withdraw(?:n)?"
    r"|we regret|editor'?s note|updates? with|revised)\b", re.IGNORECASE)

HEDGES = re.compile(
    r"\b(reportedly|allegedly|apparently|purportedly|unconfirmed|claims?|claimed"
    r"|suggests?|may have|appears? to|denies|disputed|rumou?red|said to be)\b",
    re.IGNORECASE)

NUMBERS = re.compile(r"\b\d[\d,]*\b")


# ------------------------------------------------------------ independence

def _stable_hash(text: str) -> int:
    """
    crc32, not Python's hash().

    Fingerprints get written to disk on one run and compared on the next, and
    Python randomises string hashing per process — so hash() silently produces
    signatures that never match across runs.
    """
    return zlib.crc32(text.encode("utf-8"))


def shingles(text: str, size: int = 5, cap: int = 24) -> list[int]:
    """A compact fingerprint of the prose, for spotting republished copy."""
    words = norm_title(text).split()
    if len(words) < size:
        return [_stable_hash(" ".join(words))] if words else []
    grams = {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}
    return sorted(map(_stable_hash, grams))[:cap]


def _sig_overlap(a: list[int], b: list[int]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / min(len(sa), len(sb))


def detect_wire(member: dict) -> str | None:
    """Is this member republished agency copy?"""
    haystack = f"{member.get('source', '')} {member.get('byline', '')} {member.get('blurb', '')}"
    match = WIRE_PATTERN.search(haystack)
    return match.group(1).lower().strip() if match else None


def _title_twins(a: dict, b: dict, window_minutes: float = 120) -> bool:
    """
    Same headline, near-simultaneously, from different outlets.

    The prose fingerprint needs a summary to work with, and plenty of feeds
    ship empty or truncated descriptions — which is exactly where syndication
    is hardest to catch. Identical wording filed within a couple of hours is
    a reprint; two newsrooms do not independently produce the same sentence.
    """
    ta, tb = norm_title(a["title"]), norm_title(b["title"])
    if not ta or not tb:
        return False
    ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
    if ratio < 0.88:
        return False
    try:
        gap = abs((parse_ts(a["seen"]) - parse_ts(b["seen"])).total_seconds()) / 60
    except (KeyError, ValueError):
        return ratio >= 0.95
    return gap <= window_minutes or ratio >= 0.97


def independence_confidence(members: list[dict]) -> str:
    """
    How much to trust the independence count.

    It rests on comparing prose. Where feeds gave us nothing to compare, say
    so rather than presenting a guess as a measurement.
    """
    if len(members) < 2:
        return "high"
    with_text = sum(1 for m in members if len((m.get("blurb") or "").split()) >= 12)
    share = with_text / len(members)
    if share >= 0.7:
        return "high"
    return "medium" if share >= 0.35 else "low"


def independence_groups(members: list[dict], aggregator_tiers: set[int],
                        similarity: float = 0.62) -> list[dict]:
    """
    Collapse members into distinct independent reports.

    A group is one voice. Two outlets running the same agency copy share a
    group. Two newsrooms that wrote their own version do not.
    """
    groups: list[dict] = []
    aggregators: list[dict] = []

    for member in sorted(members, key=lambda m: m["seen"]):
        if member.get("tier") in aggregator_tiers:
            aggregators.append(member)
            continue

        wire = detect_wire(member)
        if wire:
            existing = next((g for g in groups if g.get("wire") == wire), None)
            if existing:
                existing["members"].append(member)
                continue
            groups.append({"wire": wire, "members": [member],
                           "label": f"{wire.title()} copy"})
            continue

        signature = member.get("sig") or []
        joined = False
        for group in groups:
            # One newsroom is one voice, however many times it files.
            same_room = any(m["source"] == member["source"] for m in group["members"])
            twins = any(_title_twins(member, m) for m in group["members"])
            if same_room or twins or any(
                    _sig_overlap(signature, m.get("sig") or []) >= similarity
                    for m in group["members"]):
                group["members"].append(member)
                joined = True
                break
        if not joined:
            groups.append({"wire": None, "members": [member],
                           "label": member["source"]})

    if not groups and aggregators:
        groups.append({"wire": None, "members": aggregators, "label": "aggregator only"})
    elif aggregators and groups:
        groups[0]["members"].extend(aggregators)

    return groups


def independence(thread: dict, aggregator_tiers: set[int]) -> tuple[int, list[dict]]:
    groups = independence_groups(thread["members"], aggregator_tiers)
    return len(groups), groups


# -------------------------------------------------------------- corrections

def _numbers(text: str) -> list[int]:
    out = []
    for raw in NUMBERS.findall(text):
        try:
            out.append(int(raw.replace(",", "")))
        except ValueError:
            continue
    return out


def find_revision(members: list[dict], incoming: dict,
                  similarity: float = 0.62) -> dict | None:
    """
    Has this outlet refiled its own story?

    Corrections rarely arrive as a change to whichever headline happens to be
    leading the thread. They arrive as the same newsroom filing again with a
    different number in it.
    """
    best, best_score = None, 0.0
    for member in members:
        if member["source"] != incoming["source"] or member["url"] == incoming["url"]:
            continue
        score = _sig_overlap(incoming.get("sig") or [], member.get("sig") or [])
        title_score = difflib.SequenceMatcher(
            None, norm_title(member["title"]), norm_title(incoming["title"])).ratio()
        score = max(score, title_score)
        if score >= similarity and score > best_score:
            best, best_score = member, score
    return best


def classify_change(old: str, new: str) -> dict | None:
    """
    Name what actually happened between two versions of a headline.

    "Developing" and "walked back" look identical if all you track is that
    the text changed. They are not the same thing and a reader deserves to
    know which one they're looking at.
    """
    if norm_title(old) == norm_title(new):
        return None

    kind, notes = "REWORDED", []

    old_numbers, new_numbers = _numbers(old), _numbers(new)
    if old_numbers and new_numbers and old_numbers != new_numbers:
        before, after = max(old_numbers), max(new_numbers)
        if after > before:
            kind, notes = "REVISED UP", [f"{before} → {after}"]
        elif after < before:
            kind, notes = "REVISED DOWN", [f"{before} → {after}"]

    old_hedged = bool(HEDGES.search(old))
    new_hedged = bool(HEDGES.search(new))
    # A number moving and a qualifier appearing are separate facts. Both get
    # recorded — a toll revised down *and* hedged is a different story from a
    # toll revised down alone.
    if new_hedged and not old_hedged:
        notes.append("qualifier added")
        if kind == "REWORDED":
            kind = "HEDGED"
    elif old_hedged and not new_hedged:
        notes.append("qualifier dropped")
        if kind == "REWORDED":
            kind = "FIRMED UP"

    if CORRECTION_WORDS.search(new):
        kind = "CORRECTION"
        notes.append("outlet flagged a correction")

    detail = " &middot; ".join(notes)

    detail = " &middot; ".join(notes)

    # Rewording is not correcting. An outlet publishing a second, differently
    # angled piece on the same subject is ordinary journalism, and counting it
    # buries the handful of cases that actually matter: a number that moved, a
    # claim that got qualified, an outlet saying it got something wrong.
    if kind == "REWORDED":
        return None

    return {"ts": now_utc().isoformat(), "kind": kind, "detail": detail,
            "from": old, "to": new}


def diff_words(old: str, new: str) -> str:
    """Inline word-level diff markup for the thread page."""
    matcher = difflib.SequenceMatcher(None, old.split(), new.split())
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append(" ".join(old.split()[i1:i2]))
        elif tag in ("replace", "delete"):
            out.append(f'<del>{" ".join(old.split()[i1:i2])}</del>')
            if tag == "replace":
                out.append(f'<ins>{" ".join(new.split()[j1:j2])}</ins>')
        elif tag == "insert":
            out.append(f'<ins>{" ".join(new.split()[j1:j2])}</ins>')
    return " ".join(p for p in out if p.strip())


# ----------------------------------------------------------------- link rot

def _probe(url: str) -> int:
    try:
        response = requests.get(url, headers={"User-Agent": UA}, timeout=10,
                                stream=True, allow_redirects=True)
        response.close()
        return response.status_code
    except requests.RequestException:
        return 0


def check_link_rot(threads: list[dict], limit: int = 25, min_age_hours: float = 1.0) -> int:
    """
    Re-check thin stories. A single-source report whose URL has gone to 404
    was almost certainly pulled, and that is worth knowing.

    Only 403/405 are treated as inconclusive — plenty of sites block bots on
    a second look, and that is not the same as a deletion.
    """
    candidates = []
    for thread in threads:
        if thread.get("_independent", 1) >= 2 or thread.get("_pulled"):
            continue
        if thread.get("_age", 0) < min_age_hours:
            continue
        member = thread["members"][0] if thread["members"] else None
        if member and not member.get("rechecked"):
            candidates.append((thread, member))
    candidates = candidates[:limit]
    if not candidates:
        return 0

    stamp = now_utc().isoformat()
    found = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda pair: _probe(pair[1]["url"]), candidates))
    for (thread, member), code in zip(candidates, codes):
        member["rechecked"] = stamp
        if code in (404, 410):
            thread["_pulled"] = True
            thread.setdefault("changes", []).append({
                "ts": stamp, "kind": "PULLED",
                "detail": f"original URL now returns {code}",
                "from": thread["title"], "to": thread["title"]})
            found += 1
    return found


def latest_flag(thread: dict) -> dict | None:
    changes = thread.get("changes") or []
    serious = [c for c in changes
               if c["kind"] in ("CORRECTION", "PULLED", "HEDGED", "FIRMED UP",
                                "REVISED UP", "REVISED DOWN")]
    return serious[-1] if serious else None
