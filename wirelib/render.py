"""The pages. Plain, fast, keyboard-driven."""

from __future__ import annotations

import html
import json
from email.utils import format_datetime

from .assets import CSS, HELP, JS
from .beats import anomalies, entity_index, slug
from .common import DOCS, content_words, now_utc, parse_ts
from .threads import avg_lead_minutes, reliability
from .verify import (diff_words, independence_confidence, independence_groups,
                     latest_flag)


# Set from config. Used to stamp the demo build so invented stories can never
# be mistaken for reporting.
BANNER = ""


def esc(text: str) -> str:
    return html.escape(text or "")


def _shell(title: str, body: str, refresh: int | None = None, depth: int = 0) -> str:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'{meta}<title>{esc(title)}</title><style>{CSS}</style></head>'
            f'<body>{BANNER}{body}{HELP}<script>{JS}</script></body></html>')


# ------------------------------------------------------------------ badges

ACCESS_LABEL = {"metered": "METERED", "paywall": "PAYWALL"}


def signal_class(thread: dict) -> str:
    """The rail colour. Verification state, readable without reading."""
    if thread.get("_flag") or thread.get("_pulled"):
        return "s-flagged"
    return {"PRIMARY": "s-primary", "CONFIRMED": "s-confirmed",
            "UNCONFIRMED": "s-unconfirmed"}.get(thread["_status"], "")


def _badges(thread: dict) -> str:
    """
    Only what the rail can't say.

    The rail already carries verification state, so repeating it as a badge
    on every headline would be noise at this volume. Badges are reserved for
    the things that vary: how many newsrooms, how fast, what changed, whether
    you'll hit a wall when you click.
    """
    out = []
    independent = thread.get("_independent", 1)
    carried = thread.get("_outlets", 1)
    if independent > 1:
        label = f"{independent} INDEP"
        if carried > independent:
            label += f" / {carried}"
        out.append(f'<span class="badge b-indep">{label}</span>')
    if thread["_velocity"] >= 1.5:
        out.append(f'<span class="badge b-fast">&#9650; {thread["_velocity"]:.1f}/H</span>')
    flag = thread.get("_flag")
    if flag:
        out.append(f'<span class="badge b-flag">{esc(flag["kind"])}</span>')
    langs = {m.get("lang", "en") for m in thread["members"]} - {"en"}
    if langs:
        out.append(f'<span class="badge b-lang">{esc("/".join(sorted(langs)).upper())}</span>')
    access = ACCESS_LABEL.get(thread.get("access", "free"))
    if access:
        out.append(f'<span class="badge b-pay">{access}</span>')
    return "".join(out)


def render_row(thread: dict, prefix: str = "") -> str:
    hot = " hot" if thread["_score"] >= 26 else ""
    blob = " ".join([thread["title"], thread["source"]]
                    + thread.get("countries", []) + thread.get("entities", [])
                    + thread.get("tags", []))
    age = thread["_age"]
    when = f"{int(age * 60)}m" if age < 1 else f"{age:.0f}h"
    return (
        f'<li class="item {signal_class(thread)}{hot}" data-id="{thread["id"]}" '
        f'data-q="{esc(blob)}" data-pay="{esc(thread.get("access", "free"))}">'
        f'<a class="head" href="{esc(thread["url"])}" target="_blank" rel="noopener">'
        f'{esc(thread["title"])}</a>{_badges(thread)}'
        f'<span class="src">{esc(thread["source"])}<span class="dot">&middot;</span>{when}'
        f'<span class="dot">&middot;</span>'
        f'<a href="{prefix}t/{thread["id"]}.html">thread</a></span></li>'
    )


ACCENTS = {"philly": "var(--violet)", "uspol": "var(--blue)", "elections": "var(--blue)",
           "war": "var(--red)", "world": "var(--green)", "justice": "var(--amber)",
           "money": "var(--green)", "argument": "var(--violet)", "env": "var(--green)",
           "sci": "var(--blue)"}


def render_block(label: str, threads: list[dict], limit: int, anchor: str = "",
                 empty: str = "", prefix: str = "") -> str:
    if not threads and not empty:
        return ""
    aid = f' id="{anchor}"' if anchor else ""
    accent = ACCENTS.get(anchor)
    style = f' data-accent="1" style="--accent:{accent}"' if accent else ""
    inner = ("<ul>" + "".join(render_row(t, prefix) for t in threads[:limit]) + "</ul>"
             if threads else f'<p class="note">{empty}</p>')
    count = f'<span class="count">{len(threads)}</span>' if threads else ""
    return (f'<div class="block"{aid}{style}><h2><span>{esc(label)}</span>'
            f'{count}</h2>{inner}</div>')


# --------------------------------------------------------------- front page

def _toolbar() -> str:
    return (
        '<div class="bar">'
        '<input id="q" type="search" placeholder="Filter \u2014 country, source, anything (/)" '
        'aria-label="Filter headlines">'
        '<button id="save-beat">Save beat</button>'
        '<button id="toggle-read" aria-pressed="false">Hide read</button>'
        '<button id="toggle-pay" aria-pressed="false">All sources</button>'
        '<button id="toggle-theme">Theme</button>'
        '<button id="toggle-help">?</button>'
        '<button id="reset-read">Reset</button>'
        '<span class="tally" id="tally"></span></div>'
    )


def _masthead(cfg: dict, threads: list, feed_count: int, errors: dict,
              state: dict, prefix: str = "") -> str:
    site = cfg["site"]
    spikes = anomalies(state)
    flagged = sum(1 for t in threads if t.get("_flag"))
    moving = sum(1 for t in threads if t.get("_velocity", 0) >= 1.5)
    stamp = now_utc().astimezone().strftime("%H:%M %Z &middot; %a %d %b")

    cells = [("threads live", len(threads), False),
             ("sources up", feed_count, False),
             ("moving now", moving, moving > 0),
             ("unusual beats", len(spikes), bool(spikes)),
             ("corrections", flagged, flagged > 0)]
    status = "".join(
        f'<div class="{"lit" if lit else ""}"><b>{value}</b><span>{label}</span></div>'
        for label, value, lit in cells)

    nav = "".join(
        f'<a href="{prefix}index.html#{s["id"]}">{esc(s["label"])}</a>'
        for s in cfg["sections"])

    return (
        f'<header class="masthead"><div class="wrap">'
        f'<div class="brand"><h1><a href="{prefix}index.html">'
        f'<span class="mark"></span>{esc(site["title"])}</a></h1>'
        f'<div class="tagline">{esc(site["tagline"])} &middot; {stamp}</div></div>'
        f'<div class="status">{status}</div>'
        f'<nav class="sections"><a href="{prefix}index.html#unusual">Unusual</a>'
        f'<a href="{prefix}index.html#early">Early signal</a>'
        f'<a href="{prefix}index.html#fast">Fastest</a>'
        f'<a href="{prefix}index.html#flags">Corrections</a>{nav}'
        f'<a href="{prefix}beats.html">Beats</a>'
        f'<a href="{prefix}sources.html">Sources</a>'
        f'<a href="{prefix}feed.xml">RSS</a></nav>'
        f'</div></header>')


def _anomaly_block(found: list[dict], prefix: str = "") -> str:
    if not found:
        return ""
    cards = []
    for item in found[:12]:
        label = item["name"] if item["kind"] == "country" else item["name"].title()
        target = (f'{prefix}e/{slug(item["name"])}.html' if item["kind"] == "country"
                  else f'{prefix}index.html')
        cards.append(
            f'<a class="spike" href="{target}"><b>{esc(label)}</b>'
            f'<span class="n">{item["today"]} today <s>vs {item["expected"]} '
            f'expected &middot; {item.get("sources", 1)} sources</s></span></a>')
    return (
        f'<div class="unusual" id="unusual"><h2><span>Unusual activity</span></h2>'
        f'<p class="note">Filing well above their own three-week baseline. Nobody '
        f'has written the analysis piece yet — the volume moved first.</p>'
        f'<div class="spikes">{"".join(cards)}</div></div>')


def render_index(threads: list[dict], cfg: dict, errors: dict, feed_count: int,
                 state: dict) -> str:
    site = cfg["site"]
    ranked = sorted(threads, key=lambda t: t["_score"], reverse=True)

    lead = None
    if ranked:
        top = ranked[0]
        if (top["_score"] >= cfg["siren"]["score"]
                or top.get("_independent", 1) >= cfg["siren"]["min_sources"]):
            lead = top

    body = [_masthead(cfg, threads, feed_count, errors, state), _toolbar(), '<div class="wrap">']

    if lead:
        groups = independence_groups(
            lead["members"], set(cfg["scoring"].get("aggregator_tiers", [4])))
        voices = ", ".join(g["label"] for g in groups[:4])
        body.append(
            f'<div class="lead"><div class="eyebrow">Leading the wire</div>'
            f'<a class="head" href="{esc(lead["url"])}" target="_blank" rel="noopener">'
            f'{esc(lead["title"])}</a>'
            f'<div class="meta">{lead.get("_independent", 1)} independent of '
            f'{lead["_outlets"]} carrying &nbsp;&middot;&nbsp; {esc(voices)} '
            f'&nbsp;&middot;&nbsp; <a href="t/{lead["id"]}.html">follow the thread</a>'
            f'</div></div>')

    body.append(_anomaly_block(anomalies(state)))

    rest = [t for t in ranked if t is not lead]
    early = sorted([t for t in rest if t["_novelty"] > 0 and t["_age"] <= 12],
                   key=lambda t: (t["_novelty"], t["_score"]), reverse=True)
    fastest = sorted([t for t in rest if t["_velocity"] > 0],
                     key=lambda t: (t["_velocity"], t.get("_independent", 1)), reverse=True)
    flagged = [t for t in ranked if t.get("_flag")]

    body.append('<div class="cols">')
    body.append(render_block("Top of the wire", rest, 40))
    body.append(render_block(
        "Early signal", early, 30, "early",
        empty="Learning what normal reads like. Fills in once the desk has a few "
              "hundred headlines to compare against \u2014 give it a day."))
    body.append(render_block(
        "Moving fastest", fastest, 25, "fast",
        empty="Nothing accelerating. Stories land here when independent newsrooms "
              "start piling on within the hour."))
    body.append(render_block(
        "Corrections", flagged, 25, "flags",
        empty="No revisions detected. Death tolls moving, qualifiers appearing and "
              "stories going dead all surface here."))
    body.append('<div class="block" id="beats"><h2><span>Your beats</span></h2>'
                '<div id="beats-lane"></div></div>')
    body.append("</div>")

    body.append('<div class="cols">')
    for section in cfg["sections"]:
        tags = set(section["tags"])
        picked = [t for t in ranked if tags & set(t["tags"])]
        body.append(render_block(section["label"], picked, site["per_section"],
                                 section["id"]))
    body.append("</div>")

    dead = f" &middot; {len(errors)} not responding" if errors else ""
    body.append(
        f'<footer>{len(threads)} threads from {feed_count} live sources{dead} '
        f'&middot; rebuilt every {site["refresh_seconds"] // 60} min &middot; '
        f'press ? for keys<br>'
        f'Read state, stars and beats stay in this browser. '
        f'<a href="feed.xml">RSS</a> &middot; <a href="feed.json">JSON</a> '
        f'&middot; <a href="sources.html">source ledger</a></footer></div>')

    return _shell(site["title"], "".join(body), site["refresh_seconds"])


# -------------------------------------------------------------- thread page

def _sparkline(curve: list[dict]) -> str:
    if len(curve) < 2:
        return '<p class="note">Not enough history yet.</p>'
    width, height = 280, 44
    values = [p["n"] for p in curve]
    times = [parse_ts(p["ts"]).timestamp() for p in curve]
    span = max(times[-1] - times[0], 1)
    peak = max(max(values), 1)
    points = " ".join(
        f'{(t - times[0]) / span * width:.1f},{height - (v / peak * (height - 6)) - 3:.1f}'
        for t, v in zip(times, values))
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'role="img" aria-label="Outlet pickup over time" '
            f'style="max-width:340px;border:1px solid var(--edge)">'
            f'<polyline points="{points}" fill="none" stroke="#c00" stroke-width="2"/>'
            f'</svg><div class="when">outlet pickup &middot; peak {peak}</div>')


def render_thread(thread: dict, cfg: dict) -> str:
    site_title = cfg["site"]["title"]
    aggregator_tiers = set(cfg["scoring"].get("aggregator_tiers", [4]))
    members = sorted(thread["members"], key=lambda m: m["seen"])
    groups = independence_groups(thread["members"], aggregator_tiers)

    changes = []
    for change in reversed(thread.get("changes", [])):
        changes.append(
            f'<li><span class="badge b-flag">{esc(change["kind"])}</span> '
            f'<span class="when">{esc(change["ts"][:16].replace("T", " "))} UTC'
            + (f' &middot; {esc(change["detail"])}' if change.get("detail") else "")
            + f'</span><div>{diff_words(esc(change["from"]), esc(change["to"]))}</div></li>'
        )

    voices = []
    for group in groups:
        first = min(group["members"], key=lambda m: m["seen"])
        others = [m for m in group["members"] if m is not first]
        tail = (f'<div class="when">also carried by '
                f'{esc(", ".join(sorted({m["source"] for m in others})))}</div>'
                if others else "")
        voices.append(
            f'<li><a class="head" href="{esc(first["url"])}" target="_blank" rel="noopener">'
            f'{esc(first["title"])}</a>'
            + (f'<div class="orig">{esc(first["original"])}</div>' if first.get("original") else "")
            + f'<span class="src">{esc(group["label"])} &middot; '
              f'{esc(first["seen"][:16].replace("T", " "))} UTC</span>{tail}</li>'
        )

    chips = "".join(
        f'<a class="chip" href="../e/{slug(name)}.html">{esc(name)}</a>'
        for name in (thread.get("countries", []) + thread.get("entities", []))[:10])

    status_class = {"UNCONFIRMED": "b-unconf", "PRIMARY": "b-primary"}.get(thread["_status"], "")
    first_seen = parse_ts(members[0]["seen"]) if members else parse_ts(thread["created"])

    body = (
        f'<header><h1><a href="../index.html">{esc(site_title)}</a></h1>'
        f'<div class="tagline">story thread</div></header>'
        f'<div class="siren"><div class="kicker">'
        f'<span class="badge {status_class}">{thread["_status"]}</span></div>'
        f'<a class="head" href="{esc(thread["url"])}" target="_blank" rel="noopener">'
        f'{esc(thread["title"])}</a>'
        f'<div class="meta">{thread.get("_independent", 1)} independent reports '
        f'&middot; {thread["_outlets"]} outlets carrying &middot; '
        f'broken by {esc(thread["starter"])} &middot; '
        f'{esc(first_seen.strftime("%b %d %H:%M"))} UTC &middot; '
        f'{thread["_velocity"]:.1f} outlets/hr</div>'
        f'<div style="margin-top:8px">{chips}</div></div>'
        f'<div class="cols">'
        f'<div class="block"><h2>Pickup</h2>{_sparkline(thread.get("pickup", []))}</div>'
        + (f'<div class="block"><h2>What changed</h2>'
           f'<ul class="timeline">{"".join(changes)}</ul></div>' if changes else
           '<div class="block"><h2>What changed</h2><p class="note">'
           'No revisions detected. Wording changes, revised numbers and pulled '
           'links would appear here.</p></div>')
        + f'<div class="block"><h2>Independent reports'
          f'<span class="count">{len(groups)}</span></h2><ul>{"".join(voices)}</ul></div>'
          f'</div>'
        f'<footer><a href="../index.html">Back to the wire</a></footer></div>')
    return _shell(thread["title"][:80], body)


# --------------------------------------------------------------- beat pages

def render_entity(name: str, threads: list[dict], cfg: dict) -> str:
    body = (
        f'<header class="masthead"><div class="wrap"><div class="brand">'
        f'<h1><a href="../index.html"><span class="mark"></span>'
        f'{esc(cfg["site"]["title"])}</a></h1>'
        f'<div class="tagline">beat &middot; {esc(name)}</div></div></div></header>'
        + _toolbar()
        + f'<div class="wrap"><div class="cols">'
          f'{render_block(name, threads, 150, prefix="../")}</div>'
          f'<footer><a href="../beats.html">All beats</a> &middot; '
          f'<a href="../index.html">Back to the wire</a></footer></div>')
    return _shell(f'{cfg["site"]["title"]} \u2014 {name}', body)


def render_beats(index: list[tuple[str, int]], found: list[dict], cfg: dict) -> str:
    chips = "".join(
        f'<a class="chip" href="e/{slug(name)}.html">{esc(name)} '
        f'<span class="base">{count}</span></a>' for name, count in index)
    body = (
        f'<header class="masthead"><div class="wrap"><div class="brand">'
        f'<h1><a href="index.html"><span class="mark"></span>'
        f'{esc(cfg["site"]["title"])}</a></h1>'
        f'<div class="tagline">beats</div></div></div></header>'
        f'<div class="wrap">' + _anomaly_block(found)
        + f'<div class="block"><h2><span>Everything the desk is tracking</span>'
          f'<span class="count">{len(index)}</span></h2>'
          f'<p class="note">Places, people and organisations pulled out of recent '
          f'headlines. Open one to read that subject end to end.</p>'
          f'<div style="margin-top:12px">{chips}</div></div>'
          f'<footer><a href="index.html">Back to the wire</a></footer></div>')
    return _shell(f'{cfg["site"]["title"]} \u2014 beats', body)


# ------------------------------------------------------------ source ledger

def render_sources(state: dict, feeds: list[dict], cfg: dict) -> str:
    book = state.get("sources", {})
    tiers = {f["name"]: f.get("tier", 3) for f in feeds}
    rows = []
    for name, stat in sorted(book.items(),
                             key=lambda kv: (reliability(kv[1]), kv[1].get("scoops", 0)),
                             reverse=True):
        if stat.get("items", 0) < 3:
            continue
        rows.append(
            f'<tr><td>{esc(name)}</td><td class="num">{tiers.get(name, "-")}</td>'
            f'<td class="num">{stat.get("items", 0)}</td>'
            f'<td class="num">{stat.get("started", 0)}</td>'
            f'<td class="num">{stat.get("scoops", 0)}</td>'
            f'<td class="num">{stat.get("orphans", 0)}</td>'
            f'<td class="num">{avg_lead_minutes(stat):.0f}m</td>'
            f'<td class="num">{reliability(stat):.2f}</td></tr>')

    body = (
        f'<header class="masthead"><div class="wrap"><div class="brand">'
        f'<h1><a href="index.html"><span class="mark"></span>'
        f'{esc(cfg["site"]["title"])}</a></h1>'
        f'<div class="tagline">source ledger</div></div></div></header>'
        f'<div class="wrap"><div class="block"><p class="note">Who breaks stories first, and whose '
        f'stories hold up. <b>Scoops</b> = filed first on something at least two '
        f'other <i>independent</i> newsrooms went on to confirm — syndicated '
        f'reprints don\'t count. <b>Orphans</b> = filed alone and nobody followed. '
        f'<b>Lead</b> = average head start over the second newsroom. Needs a few '
        f'weeks before it means much.</p>'
        f'<table><thead><tr><th>Source</th><th>Tier</th><th>Items</th><th>Started</th>'
        f'<th>Scoops</th><th>Orphans</th><th>Lead</th><th>Score</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<footer><a href="index.html">Back to the wire</a></footer></div>')
    return _shell(f'{cfg["site"]["title"]} \u2014 sources', body)


# ------------------------------------------------------------------ outputs

def render_opml(feeds: list[dict], cfg: dict) -> str:
    """The whole source list, portable to any reader."""
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
    """So anyone can subscribe in their own reader without an account."""
    items = []
    for thread in threads[:80]:
        link = thread["url"]
        desc = (f'{thread["_status"]} &middot; {thread.get("_independent", 1)} independent '
                f'of {thread["_outlets"]} carrying &middot; {esc(thread["source"])}')
        items.append(
            f'<item><title>{esc(thread["title"])}</title>'
            f'<link>{esc(link)}</link>'
            f'<guid isPermaLink="false">{thread["id"]}</guid>'
            f'<pubDate>{format_datetime(parse_ts(thread["created"]))}</pubDate>'
            f'<description>{esc(desc)}</description>'
            f'<comments>{esc(site_url.rstrip("/"))}/t/{thread["id"]}.html</comments>'
            f'</item>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>{esc(cfg["site"]["title"])}</title>'
            f'<link>{esc(site_url)}</link>'
            f'<description>{esc(cfg["site"]["tagline"])}</description>'
            f'<lastBuildDate>{format_datetime(now_utc())}</lastBuildDate>'
            f'{"".join(items)}</channel></rss>')


def write_all(threads: list[dict], cfg: dict, errors: dict, feeds: list[dict],
              state: dict, site_url: str) -> None:
    global BANNER
    notice = cfg["site"].get("banner", "")
    BANNER = (f'<div style="background:var(--hot);color:#fff;text-align:center;'
              f'padding:7px 10px;font-size:12px;font-weight:700;letter-spacing:.14em;'
              f'text-transform:uppercase;margin:-10px -12px 10px">{esc(notice)}</div>'
              if notice else "")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "t").mkdir(exist_ok=True)
    (DOCS / "e").mkdir(exist_ok=True)
    limit = int(cfg["site"].get("thread_pages", 250))

    (DOCS / "index.html").write_text(
        render_index(threads, cfg, errors, len(feeds) - len(errors), state), encoding="utf-8")
    (DOCS / "sources.html").write_text(render_sources(state, feeds, cfg), encoding="utf-8")

    ranked = sorted(threads, key=lambda t: t["_score"], reverse=True)[:limit]

    keep = set()
    for thread in ranked:
        keep.add(f'{thread["id"]}.html')
        (DOCS / "t" / f'{thread["id"]}.html').write_text(
            render_thread(thread, cfg), encoding="utf-8")
    for stale in (DOCS / "t").glob("*.html"):
        if stale.name not in keep:
            stale.unlink()

    index = entity_index(ranked)
    (DOCS / "beats.html").write_text(
        render_beats(index, anomalies(state), cfg), encoding="utf-8")
    keep = set()
    for name, _ in index:
        matched = [t for t in ranked
                   if name in t.get("countries", []) or name in t.get("entities", [])]
        if not matched:
            continue
        keep.add(f"{slug(name)}.html")
        (DOCS / "e" / f"{slug(name)}.html").write_text(
            render_entity(name, matched, cfg), encoding="utf-8")
    for stale in (DOCS / "e").glob("*.html"):
        if stale.name not in keep:
            stale.unlink()

    (DOCS / "feed.xml").write_text(render_rss(ranked, cfg, site_url), encoding="utf-8")
    (DOCS / "sources.opml").write_text(render_opml(feeds, cfg), encoding="utf-8")
    (DOCS / "feed.json").write_text(json.dumps({
        "generated": now_utc().isoformat(),
        "stories": [{
            "id": t["id"], "title": t["title"], "url": t["url"], "source": t["source"],
            "score": t["_score"], "novelty": t["_novelty"], "velocity": t["_velocity"],
            "status": t["_status"], "independent": t.get("_independent", 1),
            "carried_by": sorted({m["source"] for m in t["members"]}),
            "countries": t.get("countries", []), "entities": t.get("entities", []),
            "tags": t["tags"], "created": t["created"],
            "flag": (latest_flag(t) or {}).get("kind"),
        } for t in ranked],
    }, indent=1), encoding="utf-8")
