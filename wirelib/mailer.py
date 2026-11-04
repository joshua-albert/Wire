"""Email. Quiet by default, loud when it should be."""

from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage

from .common import now_utc, parse_ts


STAGE_TEXT = {"spotted": "Spotted", "spreading": "Spreading", "confirmed": "Confirmed",
              "changed": "Changed"}


def _why(thread: dict) -> str:
    stage = thread.get("_stage", "spotted")
    n = thread.get("_independent", 1)
    if stage == "spreading":
        return f"Spreading: {thread['_velocity']:.1f} newsrooms an hour, {thread['_outlets']} so far"
    if stage == "confirmed":
        return (f"Confirmed: {n} independent newsrooms" if n >= 2
                else "Confirmed: official source")
    if stage == "changed":
        flag = thread.get("_flag") or {}
        detail = f" ({flag.get('detail')})" if flag.get("detail") else ""
        return f"Changed: {flag.get('kind', 'pulled').lower()}{detail}".replace("&middot;", "/")
    return "Spotted: one newsroom so far"


def _row(thread: dict, site_url: str) -> tuple[str, str]:
    why = _why(thread)
    page = f"{site_url.rstrip('/')}/t/{thread['id']}.html" if site_url.startswith("http") else ""
    text = (f"{thread['title']}\n  {why}. First: {thread['source']}\n  {thread['url']}\n"
            + (f"  How it unfolded: {page}\n" if page else ""))
    colour = {"spreading": "#d9431a", "confirmed": "#11795a",
              "changed": "#a8610b"}.get(thread.get("_stage"), "#7f8792")
    markup = (
        f'<p style="margin:0 0 18px">'
        f'<span style="color:{colour};font-size:13px;font-weight:600">{html.escape(why)}</span><br>'
        f'<a href="{html.escape(thread["url"])}" style="color:#16191d;font-family:Georgia,serif;'
        f'font-size:18px;line-height:1.3;font-weight:600;text-decoration:none">'
        f'{html.escape(thread["title"])}</a><br>'
        f'<span style="color:#4d5561;font-size:13px">{html.escape(thread["source"])}</span>'
        + (f' <a href="{page}" style="font-size:13px;color:#7f8792">How it unfolded</a>' if page else "")
        + '</p>')
    return text, markup


def setting(name: str, fallback: str = "") -> str:
    """
    Read an environment variable, treating blank as unset.

    CI systems pass secrets you haven't configured as empty strings rather
    than leaving them out, so .get(name, default) quietly returns "" and the
    default never applies.
    """
    return (os.environ.get(name) or "").strip() or fallback


def send(threads: list[dict], cfg: dict, site_url: str, kicker: str) -> bool:
    host = setting("SMTP_HOST")
    user = setting("SMTP_USER")
    password = setting("SMTP_PASS")
    to_addr = setting("MAIL_TO")

    # Checked before anything is parsed. Nothing about an unconfigured
    # optional feature should be able to fail.
    if not all([host, user, password, to_addr]):
        print("email: not configured — skipping send")
        return False

    from_addr = setting("MAIL_FROM", user)
    try:
        port = int(setting("SMTP_PORT", "465"))
    except ValueError:
        print("email: SMTP_PORT is not a number — using 465")
        port = 465

    picked = sorted(threads, key=lambda t: t["_score"],
                    reverse=True)[: cfg["email"]["max_items_per_email"]]
    if not picked:
        return False

    text_rows, html_rows = zip(*(_row(t, site_url) for t in picked))

    message = EmailMessage()
    message["Subject"] = f"{kicker.capitalize()}: {picked[0]['title'][:110]}"
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(
        f"{kicker}\n\n" + "\n".join(text_rows) + f"\nFull page: {site_url}\n")
    message.add_alternative(
        f'<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:620px">'
        f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;'
        f'border-bottom:1px solid #e4e7eb;padding-bottom:10px;margin-bottom:18px">'
        f'The Wire <span style="font-family:Arial,sans-serif;font-size:13px;font-weight:400;'
        f'color:#7f8792">{html.escape(kicker)}</span></div>'
        f'{"".join(html_rows)}'
        f'<p style="font-size:11px;color:#555;border-top:1px solid #ccc;padding-top:8px">'
        f'<a href="{site_url}" style="color:#555">Open the full page</a></p></div>',
        subtype="html")

    try:
        if port == 587:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(user, password)
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001 — mail must never kill the run
        print(f"email: send failed — {type(exc).__name__}: {exc}")
        return False

    print(f"email: sent {len(picked)} stories ({kicker})")
    return True


def decide_and_send(threads: list[dict], cfg: dict, state: dict, site_url: str) -> None:
    """
    Mail only when a story moves up a stage. Spotted to spreading, spreading
    to confirmed, or anything that changed after you might have read it.
    A plain new headline is never a reason to email.

      - big and moving (siren score or many newsrooms): sent at once
      - everything else that moved up: batched, at most every N minutes
    """
    conf = cfg["email"]
    if not conf["enabled"]:
        return
    rank = {"spotted": 0, "spreading": 1, "confirmed": 2, "changed": 3}
    if not state.get("stage_mail"):
        # First run under stage alerts: note where everything stands, send
        # nothing, so you don't get a flood of old stories.
        for t in threads:
            if "_stage" in t:
                t["mailed_stage"] = t["_stage"]
        state["stage_mail"] = True
        print("email: stage alerts set up; nothing sent this run")
        return
    siren = cfg["siren"]["score"]
    min_score = conf["min_score"]

    moved = []
    for t in threads:
        if "_stage" not in t:
            continue
        stage, before = t["_stage"], t.get("mailed_stage")
        if before is not None and rank[stage] <= rank.get(before, 0):
            continue
        if stage == "spotted":
            continue
        if stage == "changed":
            # Corrections matter on stories people actually saw.
            if t.get("_independent", 1) < 2 and not before:
                continue
        elif t["_score"] < min_score:
            continue
        if stage == "confirmed" and before is None and t.get("_independent", 1) < 3:
            continue  # wait for real weight before the first email
        moved.append(t)

    if not moved:
        return

    urgent = [t for t in moved if t["_score"] >= siren
              or t.get("_independent", 1) >= cfg["siren"]["min_sources"] and t["_stage"] == "spreading"]

    last = state.get("last_email")
    cooled = True
    if last:
        gap = (now_utc() - parse_ts(last)).total_seconds() / 60
        cooled = gap >= conf["min_minutes_between"]

    if urgent:
        batch, kicker = moved, "breaking"
    elif cooled and len(moved) >= max(1, conf.get("batch_size", 3) // 2):
        batch, kicker = moved, f"{len(moved)} stories moved up"
    else:
        print(f"email: holding {len(moved)} stage change(s) for the next batch")
        return

    if send(batch, cfg, site_url, kicker):
        state["last_email"] = now_utc().isoformat()
        for t in batch:
            t["mailed_stage"] = t["_stage"]
