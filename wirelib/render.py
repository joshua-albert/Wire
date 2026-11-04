"""The pages."""

from __future__ import annotations

import html
import json
import re
from datetime import timedelta
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from .assets import CSS, FONTS, JS
from .beats import anomalies, entity_index, slug
from .common import DOCS, hours_since, now_utc, parse_ts
from .stages import (CHANGED, CONFIRMED, SPOTTED, SPREADING, annotate, latest_activity,
                     newest_first, official_names)
from .threads import avg_lead_minutes, reliability
from .verify import diff_words, independence_groups, latest_flag

BANNER = ""
LIVE_ATTR = ' data-live="1"'
import zlib as _z
ASSET_V = format(_z.crc32((CSS + JS).encode()), "x")
TZ = ZoneInfo("America/New_York")

STAGE_WORD = {SPOTTED: "Spotted", SPREADING: "Spreading", CONFIRMED: "Confirmed",
              CHANGED: "Changed"}
LANGS = {"fr": "French", "es": "Spanish", "de": "German", "pt": "Portuguese", "it": "Italian",
         "ar": "Arabic", "uk": "Ukrainian", "ru": "Russian", "tr": "Turkish", "ja": "Japanese",
         "ko": "Korean", "hi": "Hindi", "th": "Thai", "vi": "Vietnamese", "nl": "Dutch",
         "zh": "Chinese", "fa": "Persian", "he": "Hebrew", "pl": "Polish"}
CHANGE_WORD = {"REVISED UP": "Number revised up", "REVISED DOWN": "Number revised down",
               "HEDGED": "Claim qualified", "FIRMED UP": "Claim firmed up",
               "CORRECTION": "Correction", "PULLED": "Story pulled"}


def esc(text: str) -> str:
    return html.escape(text or "")


def _local(stamp: str):
    return parse_ts(stamp).astimezone(TZ)


def _clock(stamp: str) -> str:
    return _local(stamp).strftime("%-I:%M %p")


def _ago(stamp: str) -> str:
    minutes = hours_since(stamp) * 60
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{int(minutes)} min ago"
    if minutes < 24 * 60:
        return f"{int(minutes // 60)} hr ago"
    return f"{int(minutes // 1440)} d ago"


def _time(stamp: str, mode: str = "") -> str:
    """Server renders Eastern time; the page re-renders in the reader's clock."""
    attr = f' data-mode="{mode}"' if mode else ""
    # No "x min ago" baked into the HTML: it would change every page on
    # every run and bloat the repo. The page fills it in live.
    if mode in ("ago", "clock"):
        inner = _clock(stamp)
    else:
        inner = f"{_clock(stamp)}<small></small>"
    return f'<time datetime="{esc(stamp)}"{attr}>{inner}</time>'


def _shell(title: str, body: str, live: bool = False, depth: int = 0) -> str:
    up = "../" * depth
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark">'
            f'<title>{esc(title)}</title>{FONTS}<link rel="stylesheet" href="{up}wire.css?v={ASSET_V}">'
            f'</head><body{LIVE_ATTR if live else ""}>{BANNER}{body}'
            f'<script src="{up}wire.js?v={ASSET_V}"></script></body></html>')


# ------------------------------------------------------------------ pieces

def stage_mark(thread: dict) -> str:
    stage = thread["_stage"]
    bars = max(1, min(4, thread.get("_independent", 1)))
    return (f'<span class="stage st-{stage}" title="{bars if bars < 4 else "4+"} independent '
            f'newsroom{"s" if bars > 1 else ""}"><span class="sig" data-n="{bars}">'
            f'<i></i><i></i><i></i><i></i></span>{STAGE_WORD[stage]}</span>')


def _langs(thread: dict) -> str:
    codes = sorted({m.get("lang", "en") for m in thread["members"]} - {"en"})
    names = [LANGS.get(c, c.upper()) for c in codes]
    return f'Translated from {", ".join(names)}' if names else ""


def _others(thread: dict) -> str:
    extra = thread.get("_independent", 1) - 1
    if extra <= 0:
        return ""
    return f'+{extra} other newsroom{"s" if extra > 1 else ""}'


def _attrs(thread: dict) -> str:
    blob = " ".join([thread["title"], thread["source"]]
                    + thread.get("countries", []) + thread.get("entities", [])
                    + [m["source"] for m in thread["members"][:12]]).lower()
    return (f'data-id="{thread["id"]}" data-tags="{esc(" ".join(thread.get("tags", [])))}" '
            f'data-q="{esc(blob)}"')


def clean_title(title: str, source: str) -> str:
    """Search feeds tack " - Outlet" onto headlines; some feeds send paragraphs."""
    head, sep, tail = (title or "").rpartition(" - ")
    if sep and head and (tail.strip().lower() == (source or "").lower() or len(tail) <= 24
                         and "." in tail):
        title = head.strip()
    title = re.sub(r"\s*(https?://\S+|\b[a-z0-9-]+\.[a-z]{2,6}/\S+)", "", title).strip()
    if len(title) > 170:
        title = title[:167].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return title


def _headline(thread: dict, cls: str = "hl") -> str:
    return (f'<a class="{cls}" href="{esc(thread["url"])}" target="_blank" '
            f'rel="noopener">{esc(clean_title(thread["title"], thread["source"]))}</a>')


def _orig(thread: dict) -> str:
    lead = next((m for m in thread["members"] if m["url"] == thread["url"]), None)
    if lead and lead.get("original"):
        return f'<div class="orig" lang="{esc(lead.get("lang", ""))}">{esc(lead["original"])}</div>'
    return ""


def log_row(thread: dict, prefix: str = "") -> str:
    """
    One line of the Latest log. Timed by the newest report, so a fresh
    development on last night's story lands at the top, not buried.
    """
    newest = thread.get("_newest")
    developing = (newest is not None and newest["url"] != thread["url"]
                  and (parse_ts(thread["_last"]) - parse_ts(thread["_first"])).total_seconds() > 1200)
    bits = [stage_mark(thread), f'<span class="src">{esc(thread["source"])}</span>']
    if _others(thread):
        bits.append(f'<span>{_others(thread)}</span>')
    if _langs(thread):
        bits.append(f'<span class="lang">{_langs(thread)}</span>')
    if thread.get("access") in ("paywall", "metered"):
        bits.append('<span class="lang">Paywall</span>')
    bits.append(f'<a class="more" href="{prefix}t/{thread["id"]}.html">How it unfolded</a>')
    update = ""
    if developing:
        update = (f'<div class="upd"><span>Latest from {esc(newest["source"])}</span> '
                  f'<a href="{esc(newest["url"])}" target="_blank" rel="noopener">'
                  f'{esc(clean_title(newest["title"], newest["source"]))}</a>'
                  f'<span class="since-first">Developing since {_time(thread["_first"], "clock")}'
                  f'</span></div>')
    return (f'<li {_attrs(thread)} data-first="{esc(thread["_last"])}">'
            f'{_time(thread["_last"])}<div>{_headline(thread)}{update}'
            f'<div class="by">{"".join(bits)}</div></div></li>')


def rail_row(thread: dict, fact: str, prefix: str = "") -> str:
    return (f'<li {_attrs(thread)}>{_headline(thread)}'
            f'<div class="fact st-{thread["_stage"]}">{fact} '
            f'<a class="more" href="{prefix}t/{thread["id"]}.html" '
            f'style="color:var(--ink-3);margin-left:6px">How it unfolded</a></div></li>')


def _fact_spreading(t: dict) -> str:
    return (f'<b>{t["_velocity"]:.1f} newsrooms an hour</b>, '
            f'{t["_outlets"]} so far, first seen {_time(t["_first"], "ago")}')


def _fact_confirmed(t: dict) -> str:
    if t["_official"] and t.get("_independent", 1) < 2:
        src = next(m["source"] for m in t["members"] if m["source"] in OFFICIAL)
        return f'<b>Official source</b>: {esc(src)}'
    n = t.get("_independent", 1)
    return f'<b>{n} independent newsrooms</b>, latest {_time(t["_last"], "ago")}'


def _fact_changed(t: dict) -> str:
    flag = t.get("_flag") or {"kind": "PULLED", "detail": ""}
    word = CHANGE_WORD.get(flag["kind"], flag["kind"].title())
    detail = f' {flag["detail"]}' if flag.get("detail") and flag["kind"] != "PULLED" else ""
    who = f' by {esc(flag["source"])}' if flag.get("source") else ""
    return f'<b>{word}</b>{detail}{who}, {_time(flag.get("ts", t["_last"]), "ago")}'


def _fact_abroad(t: dict) -> str:
    return (f'<b>{_langs(t).replace("Translated from ", "")} press</b>, '
            f'not yet in major English-language outlets')


def lane(key: str, title: str, why: str, rows: list[str], cap: int, empty: str,
         ordered: bool = False, optional: bool = False) -> str:
    opt = ' data-optional="1"' if optional else ""
    cls = "log" if ordered else ""
    body = (f'<ol class="{cls}">{"".join(rows)}</ol>'
            f'<p class="empty empty-filter" hidden>Nothing here for this topic right now.</p>'
            if rows else f'<p class="empty">{empty}</p>')
    return (f'<section class="lane" id="{key}" data-cap="{cap}"{opt}>'
            f'<header><h2>{title}</h2><span class="why">{why}</span></header>{body}</section>')


def _curve_svg(curve: list[dict], width: int = 260, height: int = 64, axis: bool = False,
               extend: bool = True) -> str:
    """Step chart of how many outlets had the story, over time."""
    if len(curve) < 3 or len({p["n"] for p in curve}) < 3:
        return ""
    times = [parse_ts(p["ts"]).timestamp() for p in curve]
    now = now_utc().timestamp()
    start, end = times[0], (max(times[-1], now) if extend else times[-1])
    span = max(end - start, 1)
    peak = max(max(p["n"] for p in curve), 1)
    pad_b = 18 if axis else 2
    inner = height - pad_b - 4

    def x(t): return (t - start) / span * (width - 2) + 1
    def y(n): return height - pad_b - (n / peak) * inner

    pts = []
    for i, (t, p) in enumerate(zip(times, curve)):
        if i:
            pts.append(f"{x(t):.1f},{y(curve[i - 1]['n']):.1f}")
        pts.append(f"{x(t):.1f},{y(p['n']):.1f}")
    pts.append(f"{x(end):.1f},{y(curve[-1]['n']):.1f}")
    line = " ".join(pts)
    area = f"{x(start):.1f},{height - pad_b} {line} {x(end):.1f},{height - pad_b}"
    labels = ""
    if axis:
        labels = (f'<text x="1" y="{height - 3}">{_clock(curve[0]["ts"])}</text>'
                  f'<text x="{width - 1}" y="{height - 3}" text-anchor="end">'
                  f'{_clock(curve[-1]["ts"])}</text>'
                  f'<text x="{width - 1}" y="12" text-anchor="end">{peak} outlets</text>')
    return (f'<svg viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="Outlets carrying the story over time, peaking at {peak}">'
            f'<polygon points="{area}" fill="var(--c)" opacity=".12"/>'
            f'<polyline points="{line}" fill="none" stroke="var(--c)" stroke-width="2" '
            f'stroke-linejoin="round"/>{labels}</svg>')


def _topics(cfg: dict) -> str:
    buttons = ['<button data-topic="all" aria-pressed="true">Everything</button>']
    for section in cfg["sections"]:
        label = {"argument": "Opinion"}.get(section["id"],
                                            section["label"].capitalize().replace("&", "and"))
        buttons.append(f'<button data-topic="{esc(section["tags"][0])}">{esc(label)}</button>')
    return f'<nav class="topics" aria-label="Topics">{"".join(buttons)}</nav>'


def _top(cfg: dict, search: bool = True, prefix: str = "") -> str:
    now = now_utc().isoformat()
    find = ('<div class="find"><input id="q" type="search" placeholder="Filter by place, '
            'person, outlet" aria-label="Filter stories">'
            '<button class="btn" id="hide-read" aria-pressed="false">Hide read</button></div>'
            if search else "")
    return (f'<div class="top"><h1 class="wordmark"><a href="{prefix}index.html">The Wire'
            f'<span class="live" aria-hidden="true"></span></a></h1>'
            f'<span class="stamp">Updated <b>{_time(now, "clock")}</b></span>{find}</div>')


def _footer(cfg: dict, extra: str = "", prefix: str = "") -> str:
    return (f'<footer><span>{extra}</span>'
            f'<a href="{prefix}sources.html">Source ledger</a>'
            f'<a href="{prefix}beats.html">Beats</a>'
            f'<a href="{prefix}feed.xml">RSS</a>'
            f'<button class="btn" id="theme">Light or dark</button></footer>')


# --------------------------------------------------------------- front page

def pick_lead(threads: list[dict], cfg: dict) -> dict | None:
    pool = [t for t in threads if t["_stage"] in (SPREADING, CONFIRMED)
            and hours_since(t["_first"]) <= 18
            and (t.get("_independent", 1) >= 3 or t["_score"] >= cfg["siren"]["score"])]
    return max(pool, key=lambda t: t["_score"]) if pool else None


def _notable(t: dict) -> bool:
    """Single-source items earn a place in Latest; everything else is in already."""
    if t["_stage"] != SPOTTED or t["_official"]:
        return True
    if {"philly", "alert"} & set(t.get("tags", [])):
        return True
    foreign = any(m.get("lang", "en") != "en" for m in t["members"])
    return t["_score"] >= (5 if foreign else 0)


def _latest(newest: list[dict]) -> list[dict]:
    """Notable stories, newest first, and no outlet gets more than two in a row."""
    out = []
    for t in newest:
        if not _notable(t):
            continue
        if len(out) >= 2 and out[-1]["source"] == out[-2]["source"] == t["source"]:
            continue
        out.append(t)
        if len(out) >= LATEST_MAX:
            break
    return out


def render_index(threads: list[dict], cfg: dict, errors: dict, feed_count: int,
                 state: dict) -> str:
    lead = pick_lead(threads, cfg)
    rest = [t for t in threads if t is not lead]

    latest = _latest([t for t in latest_activity(threads) if hours_since(t["_last"]) <= 24])
    spreading = sorted([t for t in rest if t["_stage"] == SPREADING],
                       key=lambda t: t["_velocity"], reverse=True)[:40]
    confirmed = sorted([t for t in rest if t["_stage"] == CONFIRMED
                        and hours_since(t["_last"]) <= 12],
                       key=lambda t: t["_score"], reverse=True)[:60]
    changed = sorted([t for t in rest if t["_stage"] == CHANGED],
                     key=lambda t: (t.get("_flag") or {}).get("ts", t["_last"]),
                     reverse=True)[:30]
    abroad = sorted([t for t in rest if t["_abroad"] and t.get("_independent", 1) >= 2
                     and hours_since(t["_first"]) <= 24],
                    key=lambda t: (t.get("_independent", 1), t["_score"]), reverse=True)[:30]

    LINKED.clear()
    LINKED.update(t["id"] for group in (latest, spreading, confirmed, changed, abroad)
                  for t in group)
    if lead:
        LINKED.add(lead["id"])

    body = [f'<div class="page">{_top(cfg)}{_topics(cfg)}',
            '<div class="since" id="since" role="status"><div><b></b><span></span></div>'
            '<button class="btn">Mark as seen</button></div>']

    if lead:
        n = lead.get("_independent", 1)
        dek = (f'First reported by {esc(lead["starter"])} at {_time(lead["_first"], "clock")}. '
               f'{n} independent newsrooms have it now, and {lead["_outlets"]} outlets in all.')
        curve = _curve_svg(lead.get("pickup", []))
        curve_html = (f'<div class="curve st-{lead["_stage"]}">{curve}'
                      f'<div class="cap">Outlets carrying it since first report</div></div>'
                      if curve else "")
        body.append(
            f'<article class="lead{"" if curve else " solo"}"><div><ol style="list-style:none;margin:0;padding:0">'
            f'<li {_attrs(lead)}>{stage_mark(lead)}{_headline(lead)}</li></ol>'
            f'<p>{dek} <a href="t/{lead["id"]}.html">See how it unfolded</a>.</p></div>'
            f'{curve_html}</article>')

    rail = "".join([
        lane("spreading", "Spreading", "Picking up fast right now",
             [rail_row(t, _fact_spreading(t)) for t in spreading], 6,
             "Nothing is spreading fast at the moment."),
        lane("confirmed", "Confirmed", "Two or more independent newsrooms, or an official source",
             [rail_row(t, _fact_confirmed(t)) for t in confirmed], 8,
             "No confirmed stories in the last 12 hours."),
        lane("changed", "Changed", "Numbers revised, claims walked back, stories pulled",
             [rail_row(t, _fact_changed(t)) for t in changed], 6,
             "No corrections or revisions in the last 12 hours."),
        lane("abroad", "Abroad first", "Local press, before English-language outlets",
             [rail_row(t, _fact_abroad(t)) for t in abroad], 5,
             "Nothing from local foreign press right now.", optional=True),
    ])
    log = lane("latest", "Latest", "Newest development first, rebuilt every few minutes",
               [log_row(t) for t in latest], 60,
               "No new stories in the last 24 hours.", ordered=True)

    now_lane = (
        '<section class="lane now" id="now" aria-live="polite">'
        '<header><h2>Right now</h2><span class="why" id="now-why">Straight from newsroom '
        'accounts, refreshed every minute</span></header>'
        '<ol class="nowlist" id="nowlist"><li class="empty">Loading the last hour of posts…</li></ol>'
        '</section>')
    body.append(f'<div class="desk"><div class="nowcol">{now_lane}</div>'
                f'<div class="latest">{log}</div>'
                f'<aside class="rail">{rail}</aside></div>'
                f'<script>window.WIRE_LIVE={json.dumps(LIVE_ACCOUNTS)};</script>')

    total = feed_count + len(errors)
    body.append(_footer(cfg, f'{len(threads)} stories tracked from {feed_count} of {total} '
                             f'sources, checked every 7 minutes.'))
    body.append("</div>")
    return _shell("The Wire", "".join(body), live=True)


# -------------------------------------------------------------- story page

def _events(thread: dict, aggregator_tiers: set[int]) -> list[dict]:
    groups = independence_groups(thread["members"], aggregator_tiers)
    events = []
    first_seen = min((m["seen"] for m in thread["members"]), default=thread["created"])
    for group in groups:
        first = min(group["members"], key=lambda m: m["seen"])
        others = sorted({m["source"] for m in group["members"]} - {first["source"]})
        what = ("First report" if first["seen"] == first_seen else
                "Wire copy" if group.get("wire") else "Independent report")
        if group["label"] == "aggregator only":
            what = "Found through a news search"
        events.append({"ts": first["seen"], "kind": "report", "what": what,
                       "member": first, "also": others, "indep": True})
    for change in thread.get("changes", []):
        events.append({"ts": change["ts"], "kind": "change", "change": change})
    return sorted(events, key=lambda e: e["ts"])


def render_thread(thread: dict, cfg: dict) -> str:
    aggregator_tiers = set(cfg["scoring"].get("aggregator_tiers", [4]))
    n = thread.get("_independent", 1)
    stage = thread["_stage"]
    meaning = {
        SPOTTED: "Only one newsroom has reported this so far. Treat it as unconfirmed.",
        SPREADING: "Independent newsrooms are picking this up quickly right now.",
        CONFIRMED: ("Reported by an official source." if thread["_official"] and n < 2 else
                    f"{n} newsrooms have reported this independently, not just reprinted it."),
        CHANGED: "Something in this story changed after it was first reported. See below.",
    }[stage]

    facts = [
        (_clock(thread["_first"]), "first reported", True),
        (str(n), "independent newsrooms", False),
        (str(thread["_outlets"]), "outlets carrying it", False),
        (f'{thread["_velocity"]:.1f}', "new outlets an hour", False),
    ]
    fact_html = "".join(
        f'<div><b>{_time(thread["_first"], "clock") if is_time else v}</b><span>{label}</span></div>'
        for v, label, is_time in facts)

    items = []
    for event in _events(thread, aggregator_tiers):
        if event["kind"] == "report":
            m = event["member"]
            also = (f'<div class="also">Also carried by {esc(", ".join(event["also"][:8]))}'
                    f'{" and others" if len(event["also"]) > 8 else ""}</div>'
                    if event["also"] else "")
            orig = (f'<div class="orig">{esc(m["original"])}</div>' if m.get("original") else "")
            items.append(
                f'<li class="indep st-{stage if event["what"] == "First report" else "confirmed"}">'
                f'{_time(event["ts"])}<span class="pin"></span><div>'
                f'<div class="what">{event["what"]}, {esc(m["source"])}</div>'
                f'<a class="hl" href="{esc(m["url"])}" target="_blank" rel="noopener">'
                f'{esc(m["title"])}</a>{orig}{also}</div></li>')
        else:
            c = event["change"]
            word = CHANGE_WORD.get(c["kind"], c["kind"].title())
            who = f', {esc(c["source"])}' if c.get("source") else ""
            body = (f'<div class="hl" style="font-weight:500">'
                    f'{diff_words(esc(c["from"]), esc(c["to"]))}</div>'
                    if c["kind"] != "PULLED" else
                    f'<div class="also">{esc(c.get("detail", ""))}</div>')
            items.append(
                f'<li class="indep st-changed">{_time(c["ts"])}<span class="pin"></span><div>'
                f'<div class="what">{word}{who}</div>{body}</div></li>')

    curve = _curve_svg(thread.get("pickup", []), width=720, height=150, axis=True, extend=False)
    chart = (f'<h2>Pickup</h2><p>How many outlets had the story, over time.</p>'
             f'<div class="chart st-{stage}">{curve}</div>' if curve else "")

    chips = "".join(
        f'<a class="chip" href="../e/{slug(name)}.html">{esc(name)}</a>'
        for name in (thread.get("countries", []) + thread.get("entities", []))[:10])

    body = (
        f'<div class="page">{_top(cfg, search=False, prefix="../")}'
        f'<article class="story"><ol style="list-style:none;margin:0;padding:0">'
        f'<li {_attrs(thread)}>{stage_mark(thread)}</li></ol>'
        f'<h1>{esc(clean_title(thread["title"], thread["source"]))}</h1>{_orig(thread)}'
        f'<p class="dek">{meaning}</p>'
        f'<a class="open" href="{esc(thread["url"])}" target="_blank" rel="noopener">'
        f'Read it at {esc(thread["source"])}</a>'
        f'<div class="facts">{fact_html}</div>'
        f'<h2>How it unfolded</h2><p>Each dot is a newsroom reporting it for themselves. '
        f'Reprints are folded in underneath.</p><ol class="unfold">{"".join(items)}</ol>'
        f'{chart}'
        + (f'<div class="chips">{chips}</div>' if chips else "")
        + f'</article>{_footer(cfg, prefix="../")}</div>')
    return _shell(thread["title"][:90], body, depth=1)


# --------------------------------------------------------------- beat pages

def render_entity(name: str, threads: list[dict], cfg: dict) -> str:
    rows = "".join(log_row(t, prefix="../") for t in newest_first(threads))
    body = (f'<div class="page">{_top(cfg, prefix="../")}'
            f'<h1 class="title">{esc(name)}</h1>'
            f'<p class="intro">Every story the desk is tracking that mentions {esc(name)}, '
            f'newest first.</p>'
            f'<section class="lane" data-cap="999"><ol class="log">{rows}</ol></section>'
            f'{_footer(cfg, prefix="../")}</div>')
    return _shell(f"{name}, The Wire", body, depth=1)


def render_beats(index: list[tuple[str, int]], found: list[dict], cfg: dict) -> str:
    spikes = ""
    if found:
        cards = []
        for item in found[:12]:
            label = item["name"] if item["kind"] == "country" else item["name"].title()
            target = (f'e/{slug(item["name"])}.html' if item["kind"] == "country"
                      else "index.html")
            cards.append(f'<a class="spike" href="{target}"><b>{esc(label)}</b>'
                         f'<span>{item["today"]} stories today, about {item["expected"]} '
                         f'is normal</span></a>')
        spikes = (f'<h2 style="font:700 17px var(--sans);margin:26px 0 0">Busier than usual'
                  f'</h2><div class="spikes">{"".join(cards)}</div>')
    chips = "".join(f'<a class="chip" href="e/{slug(name)}.html">{esc(name)} '
                    f'<span style="color:var(--ink-3)">{count}</span></a>' for name, count in index)
    body = (f'<div class="page">{_top(cfg, search=False)}'
            f'<h1 class="title">Beats</h1><p class="intro">Places, people and organizations '
            f'in the news right now. Open one to read everything on it, newest first.</p>'
            f'{spikes}<div class="chips" style="margin:22px 0 32px">{chips}</div>'
            f'{_footer(cfg)}</div>')
    return _shell("Beats, The Wire", body)


# ------------------------------------------------------------ source ledger

def render_sources(state: dict, feeds: list[dict], cfg: dict, errors: dict) -> str:
    book = state.get("sources", {})
    tiers = {(f.get("publisher") or f["name"]): f.get("tier", 3) for f in feeds}
    rows = []
    for name, stat in sorted(book.items(),
                             key=lambda kv: (reliability(kv[1]), kv[1].get("scoops", 0)),
                             reverse=True):
        if stat.get("items", 0) < 3:
            continue
        rows.append(
            f'<tr><td>{esc(name)}</td>'
            f'<td class="num">{stat.get("scoops", 0)}</td>'
            f'<td class="num">{stat.get("orphans", 0)}</td>'
            f'<td class="num">{avg_lead_minutes(stat):.0f} min</td>'
            f'<td class="num">{reliability(stat) * 100:.0f}%</td>'
            f'<td class="num">{stat.get("items", 0):,}</td></tr>')
    dead = ""
    if errors:
        dead = (f'<h2 style="font:700 17px var(--sans);margin:32px 0 6px">Not responding '
                f'right now</h2><p class="intro">{esc(", ".join(sorted(errors)))}</p>')
    body = (f'<div class="page">{_top(cfg, search=False)}'
            f'<h1 class="title">Source ledger</h1>'
            f'<p class="intro">Who breaks stories first, and whose stories hold up. A scoop '
            f'means they had it first and at least two other independent newsrooms followed. '
            f'An orphan means nobody ever followed. Head start is how far ahead of the next '
            f'newsroom they usually are.</p>'
            f'<div class="tablewrap"><table><thead><tr><th>Source</th><th class="num">Scoops</th>'
            f'<th class="num">Orphans</th><th class="num">Head start</th>'
            f'<th class="num">Holds up</th><th class="num">Stories filed</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>{dead}'
            f'{_footer(cfg)}</div>')
    return _shell("Source ledger, The Wire", body)


# ------------------------------------------------------------------ outputs

def render_opml(feeds: list[dict], cfg: dict) -> str:
    by_tag: dict[str, list[dict]] = {}
    for feed in feeds:
        by_tag.setdefault((feed.get("tags") or ["other"])[0], []).append(feed)
    body = []
    for tag, group in sorted(by_tag.items()):
        entries = "".join(
            f'<outline type="rss" text="{esc(f["name"])}" title="{esc(f["name"])}" '
            f'xmlUrl="{esc(f["url"])}"/>' for f in group)
        body.append(f'<outline text="{esc(tag)}">{entries}</outline>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head>'
            f'<title>{esc(cfg["site"]["title"])} sources</title></head>'
            f'<body>{"".join(body)}</body></opml>')


def render_rss(threads: list[dict], cfg: dict, site_url: str) -> str:
    items = []
    for thread in threads[:80]:
        desc = (f'{STAGE_WORD[thread["_stage"]]}: {thread.get("_independent", 1)} independent '
                f'of {thread["_outlets"]} outlets. First reported by {thread["starter"]}.')
        items.append(
            f'<item><title>{esc(thread["title"])}</title>'
            f'<link>{esc(thread["url"])}</link>'
            f'<guid isPermaLink="false">{thread["id"]}</guid>'
            f'<pubDate>{format_datetime(parse_ts(thread["_first"]))}</pubDate>'
            f'<description>{esc(desc)}</description>'
            + (f'<comments>{esc(site_url.rstrip("/"))}/t/{thread["id"]}.html</comments>'
               if site_url else "")
            + '</item>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>The Wire</title><link>{esc(site_url)}</link>'
            f'<description>{esc(cfg["site"]["tagline"])}</description>'
            f'<lastBuildDate>{format_datetime(now_utc())}</lastBuildDate>'
            f'{"".join(items)}</channel></rss>')


OFFICIAL: set[str] = set()
LIVE_ACCOUNTS: list[dict] = []
LATEST_MAX = 220
LINKED: set[str] = set()


def write_all(threads: list[dict], cfg: dict, errors: dict, feeds: list[dict],
              state: dict, site_url: str) -> None:
    global BANNER, OFFICIAL, TZ
    try:
        TZ = ZoneInfo(cfg["site"].get("timezone") or "America/New_York")
    except Exception:  # noqa: BLE001
        pass
    OFFICIAL = official_names(feeds)
    LIVE_ACCOUNTS[:] = [
        {"handle": f["url"].split("/profile/")[1].split("/")[0],
         "name": f.get("publisher") or f["name"], "tags": f.get("tags", [])}
        for f in feeds if f.get("social") and "/profile/" in f["url"]
        and f["name"] not in errors]
    if any("_stage" not in t for t in threads):
        annotate(threads, OFFICIAL)
    notice = cfg["site"].get("banner", "")
    BANNER = f'<div class="banner">{esc(notice)}</div>' if notice else ""
    DOCS.mkdir(exist_ok=True)
    (DOCS / "t").mkdir(exist_ok=True)
    (DOCS / "e").mkdir(exist_ok=True)
    limit = int(cfg["site"].get("thread_pages", 250))

    (DOCS / "wire.css").write_text(CSS, encoding="utf-8")
    (DOCS / "wire.js").write_text(JS, encoding="utf-8")
    (DOCS / "index.html").write_text(
        render_index(threads, cfg, errors, len(feeds) - len(errors), state), encoding="utf-8")
    (DOCS / "sources.html").write_text(render_sources(state, feeds, cfg, errors),
                                       encoding="utf-8")

    # Story pages for everything the front page can link to.
    ranked = sorted(threads, key=lambda t: t["_score"], reverse=True)
    pages = [t for t in threads if t["id"] in LINKED] + ranked[:limit]
    keep = set()
    for thread in pages:
        name = f'{thread["id"]}.html'
        if name in keep:
            continue
        keep.add(name)
        (DOCS / "t" / name).write_text(render_thread(thread, cfg), encoding="utf-8")
    for stale in (DOCS / "t").glob("*.html"):
        if stale.name not in keep:
            stale.unlink()

    top = ranked[:limit]
    index = entity_index(top)
    (DOCS / "beats.html").write_text(render_beats(index, anomalies(state), cfg),
                                     encoding="utf-8")
    keep = set()
    for name, _ in index:
        matched = [t for t in top
                   if name in t.get("countries", []) or name in t.get("entities", [])]
        if not matched:
            continue
        keep.add(f"{slug(name)}.html")
        (DOCS / "e" / f"{slug(name)}.html").write_text(
            render_entity(name, matched, cfg), encoding="utf-8")
    for stale in (DOCS / "e").glob("*.html"):
        if stale.name not in keep:
            stale.unlink()

    (DOCS / "feed.xml").write_text(render_rss(newest_first(threads), cfg, site_url),
                                   encoding="utf-8")
    (DOCS / "sources.opml").write_text(render_opml(feeds, cfg), encoding="utf-8")
    (DOCS / "feed.json").write_text(json.dumps({
        "generated": now_utc().isoformat(),
        "stories": [{
            "id": t["id"], "title": t["title"], "url": t["url"], "source": t["source"],
            "stage": t["_stage"], "first_seen": t["_first"], "score": t["_score"],
            "velocity": t["_velocity"], "independent": t.get("_independent", 1),
            "outlets": t["_outlets"], "official": t["_official"],
            "carried_by": sorted({m["source"] for m in t["members"]}),
            "countries": t.get("countries", []), "entities": t.get("entities", []),
            "tags": t["tags"], "flag": (latest_flag(t) or {}).get("kind"),
        } for t in ranked],
    }, indent=1), encoding="utf-8")
