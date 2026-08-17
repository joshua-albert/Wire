"""Email. Quiet by default, loud when it should be."""

from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage

from .common import now_utc, parse_ts


def _row(thread: dict, site_url: str) -> tuple[str, str]:
    extra = f" (+{thread['_outlets'] - 1} outlets)" if thread["_outlets"] > 1 else ""
    flag = ""
    if thread["_status"] == "UNCONFIRMED":
        flag = " [UNCONFIRMED]"
    elif thread["_velocity"] >= 1.5:
        flag = f" [{thread['_velocity']:.1f} outlets/hr]"

    text = (f"{thread['title']}{flag}\n  {thread['source']}{extra}\n"
            f"  {thread['url']}\n  thread: {site_url.rstrip('/')}/t/{thread['id']}.html\n")

    colour = "#a50" if thread["_status"] == "UNCONFIRMED" else "#555"
    markup = (
        f'<p style="margin:0 0 14px">'
        f'<a href="{html.escape(thread["url"])}" style="color:#00c;font-weight:bold;'
        f'text-transform:uppercase;text-decoration:none;font-size:15px">'
        f'{html.escape(thread["title"])}</a><br>'
        f'<span style="color:{colour};font-size:11px;text-transform:uppercase">'
        f'{html.escape(thread["source"])}{html.escape(extra)}{html.escape(flag)}</span> '
        f'<a href="{site_url.rstrip("/")}/t/{thread["id"]}.html" '
        f'style="font-size:11px;color:#555">thread</a></p>'
    )
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
    message["Subject"] = f"WIRE: {picked[0]['title'][:110]}"
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(
        f"{kicker}\n\n" + "\n".join(text_rows) + f"\nFull page: {site_url}\n")
    message.add_alternative(
        f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px">'
        f'<div style="border-bottom:3px double #000;padding-bottom:6px;margin-bottom:14px;'
        f'letter-spacing:.2em;font-weight:bold">THE WIRE &middot; {html.escape(kicker.upper())}</div>'
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


def decide_and_send(fresh: list[dict], cfg: dict, state: dict, site_url: str) -> None:
    """
    Three reasons to mail you:
      1. A siren-level story broke.
      2. A story you were already told about escalated hard.
      3. Enough ordinary new stories piled up, and the cooldown has passed.
    """
    conf = cfg["email"]
    if not conf["enabled"]:
        return

    # Email is a convenience; the site is the product. Anything unscored gets
    # dropped rather than allowed to abort the run.
    fresh = [t for t in fresh if "_score" in t]
    if not fresh:
        return

    siren_score = cfg["siren"]["score"]

    sirens = [t for t in fresh if t["_score"] >= siren_score and t.get("email_level", 0) < 2]
    escalated = [
        t for t in fresh
        if t.get("email_level", 0) == 1
        and t["_outlets"] >= conf.get("escalate_outlets", 6)
        and t["_velocity"] >= conf.get("escalate_velocity", 2.0)
    ]
    ordinary = [t for t in fresh
                if t["_score"] >= conf["min_score"] and t.get("email_level", 0) == 0]

    last = state.get("last_email")
    cooled = True
    if last:
        gap = (now_utc() - parse_ts(last)).total_seconds() / 60
        cooled = gap >= conf["min_minutes_between"]

    batch, kicker = [], ""
    if sirens:
        batch, kicker = sirens, "breaking"
    elif escalated:
        batch, kicker = escalated, "escalating"
    elif ordinary and len(ordinary) >= conf["batch_size"] and cooled:
        batch, kicker = ordinary, f"{len(ordinary)} new"

    if not batch:
        held = len(ordinary)
        if held:
            print(f"email: holding {held} stories "
                  f"(need {conf['batch_size']}, or wait out the cooldown)")
        return

    if send(batch, cfg, site_url, kicker):
        state["last_email"] = now_utc().isoformat()
        for thread in batch:
            thread["email_level"] = 2 if kicker in ("breaking", "escalating") else 1
