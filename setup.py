#!/usr/bin/env python3
"""
Set up your own wire.

  python setup.py

Asks a handful of questions, writes your config, and prints exactly what to
do next. Nothing here needs you to read the code. Run it again any time to
change your answers.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
CONFIG = ROOT / "config.yaml"

# Presets so a new user gets a sensible desk without inventing keywords.
PRESETS = {
    "1": ("Everything", []),
    "2": ("Foreign desk", ["war", "world"]),
    "3": ("Politics", ["uspol", "justice"]),
    "4": ("Markets", ["money"]),
    "5": ("Climate & disaster", ["env", "sci"]),
}


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)
    return answer or default


def yes(prompt: str, default: bool = True) -> bool:
    answer = ask(f"{prompt} (y/n)", "y" if default else "n").lower()
    return answer.startswith("y")


def main() -> int:
    print("\n  THE WIRE — setup\n  " + "-" * 40)
    print("  Press enter to accept the value in brackets.\n")

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    site = config["site"]

    site["title"] = ask("What's it called", site["title"])
    site["tagline"] = ask("One-line tagline", site["tagline"])
    site["timezone"] = ask("Your timezone", site["timezone"])

    print("\n  What should sit at the top? Pick a starting point:")
    for key, (label, _) in PRESETS.items():
        print(f"    {key}. {label}")
    choice = ask("  Choose", "1")
    _, favoured = PRESETS.get(choice, PRESETS["1"])
    if favoured:
        order = {tag: i for i, tag in enumerate(favoured)}
        config["sections"].sort(
            key=lambda s: order.get(s["tags"][0], len(order) + 1))

    print("\n  Local coverage. Naming your city lifts its stories up the page")
    print("  and adds it to the search feeds.")
    city = ask("  Your city (blank to skip)", "")
    if city and city.lower() not in ("philadelphia", "philly"):
        # The shipped defaults are Philadelphia's. Someone in Denver should
        # not be scoring Harrisburg headlines up their front page.
        philly = {"philadelphia", "philly", "septa", "delaware valley", "camden",
                  "harrisburg", "pennsylvania", "city council",
                  "district attorney", "krasner", "parker"}
        terms = {k: v for k, v in config["interest_terms"].items()
                 if k.lower() not in philly}
        terms[city.lower()] = 8
        config["interest_terms"] = terms
        feeds_path = ROOT / "feeds.yaml"
        text = feeds_path.read_text(encoding="utf-8")
        query = city.replace(" ", "+")
        marker = "  # ---------- NON-ENGLISH LOCAL PRESS ----------"
        addition = (
            f'  - {{name: "GNews: {city}", url: "https://news.google.com/rss/'
            f'search?q={query}+when:1d&hl=en-US&gl=US&ceid=US:en", tier: 4, '
            f'tags: [philly]}}\n\n')
        if f'GNews: {city}"' not in text:
            feeds_path.write_text(text.replace(marker, addition + marker),
                                  encoding="utf-8")
            print(f"  Added a local search feed for {city}.")

    print("\n  Extra words that should always float up (comma separated).")
    print("  Example: chip export controls, port strike, your senator's name")
    extra = ask("  Keywords (blank to skip)", "")
    for word in [w.strip().lower() for w in extra.split(",") if w.strip()]:
        config["interest_terms"][word] = 6

    print("\n  Email alerts need an SMTP account. You can skip this and still")
    print("  get everything by subscribing to the site's RSS feed.")
    config["email"]["enabled"] = yes("  Set up email alerts", True)

    volume = ask("\n  How much mail? quiet / normal / firehose", "normal").lower()
    if volume.startswith("q"):
        config["email"].update(min_score=26, batch_size=10, min_minutes_between=120)
    elif volume.startswith("f"):
        config["email"].update(min_score=12, batch_size=3, min_minutes_between=20)
    else:
        config["email"].update(min_score=18, batch_size=6, min_minutes_between=45)

    CONFIG.write_text(
        yaml.dump(config, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8")

    print("\n  " + "-" * 40)
    print("  Wrote config.yaml.\n")
    print("  Next:\n")
    print("    1. pip install -r requirements.txt")
    print("    2. python check_feeds.py --prune     (drops any dead sources)")
    print("    3. python wire.py                    (builds docs/index.html)")
    print("    4. open docs/index.html\n")
    print("  To put it online for free, forever:\n")
    print("    git init && git add . && git commit -m 'my wire'")
    print("    gh repo create my-wire --private --source=. --push\n")
    print("    Then in the repo: Settings > Pages > deploy from branch main,")
    print("    folder /docs. It rebuilds itself every 15 minutes.\n")
    if config["email"]["enabled"]:
        print("    For email, add these repo secrets under")
        print("    Settings > Secrets and variables > Actions:")
        print("      SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS MAIL_TO SITE_URL\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
