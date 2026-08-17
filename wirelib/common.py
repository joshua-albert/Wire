"""Shared plumbing: text handling, time, state on disk."""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
STATE_PATH = ROOT / "state.json"
THREADS_PATH = ROOT / "threads.json"

UA = "TheWire/2.0 (personal news aggregator)"

# Some servers reject any user-agent they don't recognise, which blocks a
# personal feed reader from the very files a site publishes for readers.
# This is the fallback identity, used only after a 403.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

STOPWORDS = set("""
a an the and or but if in on at to for of with by from as is are was were be been
being it its this that these those he she they them his her their we you i not no
after before over under new more most says said say will would could should can may
about into out up down than then there here what who which when where how why
one two three first last year years day days week month new update live latest amid
""".split())

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|smid|partner|CMP|cmp|at_)")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def hours_since(value: str) -> float:
    return max(0.0, (now_utc() - parse_ts(value)).total_seconds() / 3600)


def digest(text: str, size: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:size]


def canonical_url(url: str) -> str:
    """Strip tracking junk so one story from one site collapses to one entry."""
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)]
    parts = parts._replace(query=urlencode(query), fragment="")
    return urlunparse(parts).rstrip("/") or url


def norm_title(title: str) -> str:
    """
    Lower-case and strip punctuation, keeping every alphabet.

    Stripping anything outside a-z deletes Cyrillic, Devanagari, Arabic and
    Greek headlines down to whatever stray Latin word they contain — so two
    unrelated Hindi stories both containing "VIDEO" look identical, and two
    reports of the same event in Russian look like nothing at all.
    """
    text = html.unescape(title or "").lower()
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"_+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem(word: str) -> str:
    """
    Crude, deliberately.

    Headlines about one event rarely agree on word forms — "collapses" and
    "collapse", "Kyrgyz" and "Kyrgyzstan", "minister" and "ministry". Exact
    matching splits those into separate stories. Truncating long words to a
    common prefix costs nothing and fixes most of it; the rarity weighting
    downstream absorbs the occasional false pairing.
    """
    for suffix in ("ies", "ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    return word[:6]


def content_words(title: str) -> list[str]:
    out = []
    for word in norm_title(title).split():
        if word in STOPWORDS:
            continue
        # Non-Latin scripts pack more meaning per character, so the
        # minimum length has to be lower for them to survive at all.
        floor = 3 if word.isascii() else 1
        if len(word) > floor:
            out.append(stem(word))
    return out


def clean_text(raw: str, limit: int = 300) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def idf(word: str, term_counts: dict, total_docs: int) -> float:
    """Rare words carry more identifying weight than common ones."""
    if total_docs < 200:
        return 1.0
    return math.log((total_docs + 1) / (term_counts.get(word, 0) + 1))


def overlap(a: set, b: set, term_counts: dict, total_docs: int) -> float:
    """
    How much *distinctive* vocabulary do two headlines share?

    Plain word overlap fails on real headlines — "Explosion reported near
    government complex in Bishkek" and "Blast rocks central Bishkek" describe
    one event but share almost nothing. Weighting by rarity means the word
    that identifies the story counts far more than the filler around it.
    """
    if not a or not b:
        return 0.0
    shared = sum(idf(w, term_counts, total_docs) for w in (a & b))
    mass_a = sum(idf(w, term_counts, total_docs) for w in a)
    mass_b = sum(idf(w, term_counts, total_docs) for w in b)
    smaller = min(mass_a, mass_b)
    return shared / smaller if smaller else 0.0


# ------------------------------------------------------------------- state

ANCHOR_MIN_CORPUS = 3000


def anchors(a: set, b: set, term_counts: dict, total_docs: int,
            rarity: float = 0.62) -> set:
    """
    Shared words rare enough to pin two headlines to the same event.

    "Bishkek" in two headlines three hours apart is almost certainly one
    story. "Government" in two headlines is nothing at all.
    """
    # In a young vocabulary every word looks rare, so "rare shared name"
    # matches everything and the anchor rule merges the entire wire. It stays
    # switched off until the desk has read enough to know what common is.
    if total_docs < ANCHOR_MIN_CORPUS:
        return set()
    ceiling = math.log(total_docs + 1)
    return {w for w in (a & b)
            if idf(w, term_counts, total_docs) >= rarity * ceiling}


def related(a: set, b: set, term_counts: dict, total_docs: int,
            primary: float, secondary: float = 0.22) -> bool:
    """
    Same story?

    Two tests, because one isn't enough. Vocabulary overlap catches outlets
    filing near-identical copy. The anchor test catches what it misses: a
    local paper writing its own descriptive headline, which may share almost
    nothing with the agency version beyond the name of the place.

    The anchor test is deliberately hard to satisfy. Loosely applied it
    merges every court story with every other court story, because in a small
    corpus "supreme" and "committee" look rare. So it needs either two rare
    shared names, or one rare name plus real vocabulary overlap — one shared
    word is never enough on its own.
    """
    shared = a & b
    # A hard floor, applied before any score is consulted. Two headlines
    # sharing a couple of words are not the same story no matter how rare
    # those words look in a small vocabulary — and the vocabulary is always
    # small early on, which is exactly when bad merges do the most damage.
    if len(shared) < 2:
        return False
    if min(len(a), len(b)) >= 6 and len(shared) < 3:
        return False

    score = overlap(a, b, term_counts, total_docs)
    if score >= primary:
        return True
    pinned = anchors(a, b, term_counts, total_docs, rarity=0.70)
    if len(pinned) >= 2 and score >= secondary * 0.7:
        return True
    return len(pinned) >= 1 and score >= secondary + 0.10 and len(shared) >= 3


def _read_json(path: Path, fallback: dict) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            print(f"{path.name} unreadable — starting that file fresh")
    return fallback


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    tmp.replace(path)


def load_state() -> dict:
    state = _read_json(STATE_PATH, {})
    state.setdefault("terms", {})
    state.setdefault("docs_counted", 0)
    state.setdefault("last_email", None)
    state.setdefault("http_cache", {})
    state.setdefault("dead_feeds", {})
    state.setdefault("sources", {})
    state.setdefault("translations", {})
    return state


def save_state(state: dict) -> None:
    _write_json(STATE_PATH, state)


def load_threads() -> dict:
    return _read_json(THREADS_PATH, {}).get("threads", {})


def save_threads(threads: dict) -> None:
    _write_json(THREADS_PATH, {"threads": threads})
