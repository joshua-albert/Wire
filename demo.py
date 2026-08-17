#!/usr/bin/env python3
"""
Build a preview of the site using made-up stories.

  python demo.py        then open docs/index.html

Nothing here touches the network. It runs the real pipeline — clustering,
syndication detection, velocity, corrections, anomaly detection — over a
scripted set of invented stories, so you can see what every part of the page
looks like with a full desk running.

EVERYTHING IN THE PREVIEW IS FICTIONAL. It is not news. The page is stamped
as sample data so it can't be mistaken for the real thing. Run `wire.py` to
replace it with actual feeds.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from wirelib import beats, common, mailer, render, scoring, sources, threads, translate, verify  # noqa: E402

MODULES = [beats, common, mailer, render, scoring, sources, threads, translate, verify]

# ---------------------------------------------------------------- fake clock

CLOCK = {"now": dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)}


def fake_now() -> dt.datetime:
    return CLOCK["now"]


def install_clock() -> None:
    """Each module imported now_utc by name, so patch every one of them."""
    for module in MODULES:
        if hasattr(module, "now_utc"):
            module.now_utc = fake_now
    common.now_utc = fake_now


# ------------------------------------------------------------- the scenario

WIRE_BODY = ("Reuters reported that a section of the eastern rail bridge gave way "
             "shortly after dawn, according to two transport officials who spoke on "
             "condition of anonymity. Emergency crews were deployed to the site and "
             "the line was suspended in both directions pending an inspection.")
LOCAL_BODY = ("Our reporter at the scene counted six ambulances on the access road. "
              "Residents of the valley said they heard a prolonged metallic groan "
              "before the span dropped into the river below.")
MINISTRY_BODY = ("The transport ministry said in a statement that an investigation "
                 "had been opened and that maintenance records from the past four "
                 "years would be reviewed by an independent panel.")

# (title, url, source, tier, tags, lang, body, translated_from)
SCRIPT: dict[int, list[tuple]] = {
    0: [
        ("Rail bridge partially collapses in eastern Kyrgyzstan, line suspended",
         "https://ex.test/wire1", "Reuters World", 1, ["world"], "en", WIRE_BODY, ""),
        ("Rail bridge partially collapses in eastern Kyrgyzstan (Reuters)",
         "https://ex.test/synd1", "Straits Times Asia", 3, ["world"], "en", WIRE_BODY, ""),
        ("Rail bridge partially collapses in eastern Kyrgyzstan",
         "https://ex.test/synd2", "Japan Times", 3, ["world"], "en", WIRE_BODY, ""),
        ("Rail bridge partially collapses in eastern Kyrgyzstan",
         "https://ex.test/synd3", "Africanews", 3, ["world"], "en", WIRE_BODY, ""),
        ("Rail bridge collapse halts eastern Kyrgyzstan freight line",
         "https://ex.test/agg1", "GNews: evacuation", 4, ["alert", "env"], "en", WIRE_BODY, ""),
    ],
    1: [
        ("Мост обрушился в Кыргызстане: шесть машин скорой помощи на месте",
         "https://ex.test/ru1", "Novaya Gazeta Europe", 3, ["world"], "ru", LOCAL_BODY,
         "Bridge collapse in Kyrgyzstan: six ambulances at the scene"),
    ],
    2: [
        ("Kyrgyz ministry says 14 injured in rail bridge collapse, opens inquiry",
         "https://ex.test/aj1", "Al Jazeera", 2, ["world"], "en", MINISTRY_BODY, ""),
        ("Bridge collapse: valley residents describe prolonged groan before span fell",
         "https://ex.test/eur1", "Eurasianet", 3, ["world"], "en", LOCAL_BODY, ""),
    ],
    3: [
        ("Kyrgyz ministry says 6 reportedly injured as bridge inquiry widens",
         "https://ex.test/aj2", "Al Jazeera", 2, ["world"], "en", MINISTRY_BODY, ""),
    ],
}

# A steady background desk, so every section and column has something in it.
BACKGROUND = [
    ("Philadelphia council advances bill on vacant property registration",
     "https://ex.test/p1", "Billy Penn", 3, ["philly"], "en", "City hall reporting."),
    ("SEPTA board defers vote on regional rail fare restructuring",
     "https://ex.test/p2", "Philadelphia Inquirer", 2, ["philly"], "en", "Transit desk."),
    ("Philadelphia police officer charged over 2024 traffic stop",
     "https://ex.test/p3", "Spotlight PA", 2, ["philly", "justice"], "en", "Own investigation."),
    ("Court filing shows city settled three excessive force claims last quarter",
     "https://ex.test/p4", "The Philadelphia Citizen", 3, ["philly", "justice"], "en", "Records request."),
    ("Mali army reports clashes with armed group near Gao",
     "https://ex.test/m1", "AllAfrica", 3, ["world", "war"], "en", "Regional desk."),
    ("Mali suspends two mining licences in Kayes region",
     "https://ex.test/m2", "Jeune Afrique", 3, ["world", "money"], "en", "Own reporting."),
    ("Fuel shortage protests spread to third Malian city",
     "https://ex.test/m3", "Premium Times (Nigeria)", 3, ["world"], "en", "Correspondent."),
    ("Malian central bank governor replaced without explanation",
     "https://ex.test/m4", "RFI Afrique", 3, ["world", "money"], "en", "Own reporting."),
    ("Bamako airport closed to civilian traffic for six hours",
     "https://ex.test/m5", "Africanews", 3, ["world"], "en", "Staff report."),
    ("Federal Reserve schedules unscheduled board meeting on discount window",
     "https://ex.test/f1", "Federal Reserve Press", 1, ["money", "uspol"], "en", "Official notice."),
    ("Regional lender halts withdrawals pending liquidity review",
     "https://ex.test/f2", "MarketWatch Top", 2, ["money"], "en", "Markets desk."),
    ("Treasury sanctions shipping network over sanctions evasion",
     "https://ex.test/f3", "US Treasury Press", 1, ["money", "uspol"], "en", "Press release."),
    ("Supreme Court declines emergency application in redistricting case",
     "https://ex.test/u1", "SCOTUSblog", 1, ["uspol", "justice"], "en", "Docket analysis."),
    ("Senate committee subpoenas records from federal contractor",
     "https://ex.test/u2", "The Hill", 2, ["uspol"], "en", "Congressional desk."),
    ("Justice Department opens civil rights review of county jail",
     "https://ex.test/u3", "DOJ Press", 1, ["justice", "uspol"], "en", "Announcement."),
    ("Wildfire forces evacuation of two villages in northern Portugal",
     "https://ex.test/e1", "Euronews", 3, ["env"], "en", "Staff report."),
    ("Magnitude 5.4 earthquake recorded off Vanuatu, no tsunami warning",
     "https://ex.test/e2", "USGS Quakes M4.5+", 1, ["alert", "env"], "en", "Automated bulletin."),
    ("Drought emergency declared across four provinces in Zambia",
     "https://ex.test/e3", "Daily Maverick (S. Africa)", 3, ["env", "world"], "en", "Own reporting."),
    ("Avian influenza confirmed in poultry flock in Cambodian province",
     "https://ex.test/s1", "ProMED-mail", 1, ["alert", "sci"], "en", "Moderator post."),
    ("Cholera cases climb in displacement camps, agency says",
     "https://ex.test/s2", "ReliefWeb", 1, ["alert", "world"], "en", "Situation report."),
    ("Undersea cable fault slows connectivity across three island states",
     "https://ex.test/s3", "Rest of World", 3, ["sci", "world"], "en", "Own reporting."),
    ("Coalition talks collapse in Moldova after fourth round",
     "https://ex.test/w1", "Balkan Insight", 3, ["world"], "en", "Correspondent."),
    ("Copper miners in Zambia begin strike over unpaid wages",
     "https://ex.test/w2", "AllAfrica", 3, ["world", "money"], "en", "Regional desk."),
    ("Ceasefire monitors report violations along disputed border",
     "https://ex.test/w3", "Crisis Group", 3, ["war", "world"], "en", "Field briefing."),
    ("Naval patrol vessel seized in territorial waters dispute",
     "https://ex.test/w4", "Naval News", 3, ["war"], "en", "Defence desk."),
    ("Peace talks adjourn without agreement on prisoner exchange",
     "https://ex.test/w5", "UN News", 1, ["war", "world"], "en", "Briefing."),
    ("Artillery exchanges resume along the northern front, monitors say",
     "https://ex.test/w6", "Kyiv Independent", 2, ["war"], "en", "Front-line desk."),
    ("Drone strike reported on port infrastructure, no casualties confirmed",
     "https://ex.test/w7", "Militarnyi", 3, ["war"], "en", "Open-source analysis."),
    ("Peacekeeping mandate renewal stalls over troop contributions",
     "https://ex.test/w8", "UN News", 1, ["war", "world"], "en", "Council briefing."),
    ("Arms shipment intercepted in Gulf of Aden, navy says",
     "https://ex.test/w9", "Naval News", 3, ["war"], "en", "Defence desk."),
    ("Border demarcation talks collapse for third time this year",
     "https://ex.test/w10", "Eurasianet", 3, ["world", "war"], "en", "Correspondent."),
    ("Opposition leader detained ahead of provincial elections",
     "https://ex.test/w11", "Global Voices", 3, ["world", "justice"], "en", "Contributor."),
    ("Fishing fleet standoff escalates in contested waters",
     "https://ex.test/w12", "The Diplomat (Asia)", 3, ["world"], "en", "Analysis."),
    ("Currency hits record low as import cover falls below two months",
     "https://ex.test/w13", "MercoPress (S. America)", 3, ["world", "money"], "en", "Wire."),
    ("Constitutional court strikes down emergency powers decree",
     "https://ex.test/w14", "Balkan Insight", 3, ["world", "justice"], "en", "Court reporting."),
    ("Rail workers announce nationwide strike from Monday",
     "https://ex.test/w15", "Le Monde", 2, ["world"], "fr", "Desk report."),

    # --- argument / political writing
    ("The case against the new industrial policy consensus",
     "https://ex.test/a1", "Jacobin", 3, ["argument", "money"], "en", "Essay."),
    ("What the tenant movement learned from three failed campaigns",
     "https://ex.test/a2", "Dissent", 3, ["argument", "justice"], "en", "Essay."),
    ("Why deficit hawks changed the subject",
     "https://ex.test/a3", "The American Prospect", 3, ["argument", "money"], "en", "Column."),
    ("Europe's rearmament is running into its own supply chains",
     "https://ex.test/a4", "The Economist", 2, ["argument", "world", "war"], "en", "Briefing."),
    ("Sahel after the withdrawal: who actually governs now",
     "https://ex.test/a5", "Le Monde Diplomatique (EN)", 2, ["argument", "world"], "en", "Feature."),
    ("The quiet consolidation of state election law",
     "https://ex.test/a6", "Bolts", 3, ["argument", "elections"], "en", "Analysis."),
    ("Against the productivity story",
     "https://ex.test/a7", "Boston Review", 3, ["argument"], "en", "Forum essay."),
    ("A conservative case for breaking up the agencies",
     "https://ex.test/a8", "National Review", 3, ["argument", "uspol"], "en", "Column."),
    ("The permitting fight is the climate fight",
     "https://ex.test/a9", "The Atlantic", 2, ["argument", "env"], "en", "Feature."),
    ("What sanctions actually did to the shipping market",
     "https://ex.test/a10", "Chartbook (Adam Tooze)", 3, ["argument", "money"], "en", "Newsletter."),
    ("Reading the new labour militancy",
     "https://ex.test/a11", "New Left Review", 3, ["argument"], "en", "Essay."),
    ("The court's shadow docket, five years on",
     "https://ex.test/a12", "Lawfare", 2, ["argument", "justice"], "en", "Analysis."),
    ("Foreign policy without a doctrine",
     "https://ex.test/a13", "Foreign Affairs", 2, ["argument", "world"], "en", "Essay."),
    ("Why the housing theory of everything keeps losing elections",
     "https://ex.test/a14", "Slow Boring", 3, ["argument", "uspol"], "en", "Newsletter."),
    ("The mutual aid networks that outlasted the emergency",
     "https://ex.test/a15", "In These Times", 3, ["argument", "justice"], "en", "Report."),

    # --- elections & voting
    ("State supreme court hears challenge to mail ballot deadline",
     "https://ex.test/el1", "Democracy Docket", 2, ["elections", "justice"], "en", "Litigation tracker."),
    ("County certifies results after two-week delay",
     "https://ex.test/el2", "Votebeat", 2, ["elections"], "en", "Election admin desk."),
    ("Redistricting commission deadlocks ahead of filing deadline",
     "https://ex.test/el3", "Stateline", 2, ["elections", "uspol"], "en", "Statehouse desk."),
    ("New voter roll maintenance rules face federal challenge",
     "https://ex.test/el4", "Brennan Center", 2, ["elections", "justice"], "en", "Analysis."),
    ("Third-party filing shifts two competitive districts",
     "https://ex.test/el5", "Sabato's Crystal Ball", 3, ["elections"], "en", "Ratings note."),
    ("Small-dollar fundraising outpaces PAC money in six races",
     "https://ex.test/el6", "OpenSecrets", 2, ["elections", "money"], "en", "Data note."),
    ("Primary turnout falls sharply in off-year contests",
     "https://ex.test/el7", "The Downballot", 3, ["elections"], "en", "Analysis."),

    # --- more Washington
    ("Appropriations markup slips as leadership counts votes",
     "https://ex.test/d1", "Politico — Congress", 2, ["uspol"], "en", "Hill desk."),
    ("Agency inspector general opens review of contracting office",
     "https://ex.test/d2", "Inspectors General", 1, ["uspol", "justice"], "en", "Report."),
    ("Nomination advances out of committee on party lines",
     "https://ex.test/d3", "The Hill — Senate", 2, ["uspol"], "en", "Hill desk."),
    ("Executive order directs review of federal procurement rules",
     "https://ex.test/d4", "White House Briefing Room", 1, ["uspol"], "en", "Official text."),
    ("CBO scores the health package at lower cost than sponsors claimed",
     "https://ex.test/d5", "Congressional Budget Office", 1, ["uspol", "money"], "en", "Score."),
    ("Court grants stay in agency rulemaking challenge",
     "https://ex.test/d6", "Supreme Court Opinions", 1, ["uspol", "justice"], "en", "Order list."),
    ("Federal workforce attrition hits ten-year high, data shows",
     "https://ex.test/d7", "Government Executive", 3, ["uspol"], "en", "Data report."),
    ("Defense authorization conference stalls over basing language",
     "https://ex.test/d8", "Politico — Defense", 2, ["uspol", "war"], "en", "Defense desk."),

    # --- more philly, justice, money, earth
    ("Zoning board approves mixed-use tower over neighborhood objections",
     "https://ex.test/px1", "WHYY — PlanPhilly", 3, ["philly"], "en", "Development desk."),
    ("School district faces budget gap after enrollment revision",
     "https://ex.test/px2", "Chalkbeat Philadelphia", 3, ["philly"], "en", "Education desk."),
    ("City controller flags overtime spending in two departments",
     "https://ex.test/px3", "Billy Penn", 3, ["philly", "money"], "en", "City hall."),
    ("State senate committee advances transit funding bill",
     "https://ex.test/px4", "PA Capital-Star", 3, ["philly", "uspol"], "en", "Statehouse."),
    ("Public defender caseloads exceed state guidelines, filing shows",
     "https://ex.test/j1", "The Marshall Project", 2, ["justice"], "en", "Investigation."),
    ("Prosecutors drop charges in three cases tied to former detective",
     "https://ex.test/j2", "Injustice Watch", 3, ["justice"], "en", "Court reporting."),
    ("Immigration detention contract renewed without public comment",
     "https://ex.test/j3", "The Appeal", 3, ["justice"], "en", "Report."),
    ("Insurers signal premium increases after catastrophe season",
     "https://ex.test/mo1", "Reuters Markets", 1, ["money"], "en", "Markets."),
    ("Central bank holds rates, signals no cuts before spring",
     "https://ex.test/mo2", "ECB Press", 1, ["money", "world"], "en", "Statement."),
    ("Jobless claims tick up in three states",
     "https://ex.test/mo3", "BLS Releases", 1, ["money"], "en", "Release."),
    ("Chip fabricator delays plant opening by two quarters",
     "https://ex.test/mo4", "Nikkei Asia", 3, ["money", "world"], "en", "Business desk."),
    ("Glacier lake outburst risk rises across three valleys, study finds",
     "https://ex.test/en1", "Carbon Brief", 3, ["env", "sci"], "en", "Science desk."),
    ("Illegal logging concessions cancelled after satellite review",
     "https://ex.test/en2", "Mongabay", 3, ["env", "world"], "en", "Investigation."),
    ("Heat advisory extended across four states",
     "https://ex.test/en3", "NWS Philadelphia Alerts", 1, ["alert", "env", "philly"], "en", "Alert."),
    ("Measles cluster confirmed in under-vaccinated district",
     "https://ex.test/sc1", "CDC Newsroom", 1, ["alert", "sci"], "en", "Health advisory."),
    ("Undersea cable repair ship delayed by weather",
     "https://ex.test/sc2", "The Register", 3, ["sci"], "en", "Tech desk."),
]


def build_feed(run: int):
    rows = []
    for entry in BACKGROUND:
        title, url, source, tier, tags, lang, body = entry
        rows.append((title, url, source, tier, tags, lang, body, ""))
    for step, items in SCRIPT.items():
        if step <= run:
            rows.extend(items)

    import yaml
    access_by_source = {f["name"]: f.get("access", "free")
                        for f in yaml.safe_load(
                            (ROOT / "feeds.yaml").read_text(encoding="utf-8"))["feeds"]}
    out = []
    for title, url, source, tier, tags, lang, body, translated in rows:
        out.append({
            "access": access_by_source.get(source, "free"),
            "title": title,
            "title_en": translated,
            "lang": lang,
            "url": url,
            "source": source,
            "tier": tier,
            "tags": tags,
            "published": (fake_now() - dt.timedelta(minutes=random.randint(20, 200))).isoformat(),
            "summary": body,
        })
    return out, {"Reuters Business": "HTTP 404", "Haaretz": "timeout"}


def seed_state() -> None:
    """
    A desk that has been reading for three weeks.

    Novelty scoring and the anomaly detector both need history to mean
    anything, so the preview starts with a plausible one — including a quiet
    baseline for Mali, which then has a busy day.
    """
    vocabulary = ("government report police city state official said plan court "
                  "minister bill vote board committee company market bank report "
                  "council district county federal agency review filing hearing "
                  "border talks troops forces region province village district "
                  "collapse bridge rail line inspection ministry inquiry").split()
    terms = {word: random.randint(300, 4000) for word in vocabulary}
    terms.update({"kyrgyzstan": 6, "kyrgyz": 8, "vanuatu": 3, "moldova": 12,
                  "zambia": 14, "mali": 30, "cambodian": 5, "bamako": 9, "gao": 7})

    today = fake_now().date()
    activity = {}
    for key, daily in [("country:Mali", 1), ("country:United States", 9),
                       ("country:Kyrgyzstan", 0), ("tag:world", 14), ("tag:philly", 4)]:
        activity[key] = {
            (today - dt.timedelta(days=i)).isoformat(): max(0, daily + random.randint(-1, 1))
            for i in range(1, 16)
        }

    (ROOT / "state.json").write_text(json.dumps({
        "terms": terms, "docs_counted": 11000, "last_email": None,
        "http_cache": {}, "dead_feeds": {}, "sources": {}, "translations": {},
        "activity": activity,
    }), encoding="utf-8")
    (ROOT / "threads.json").unlink(missing_ok=True)


def main() -> int:
    random.seed(7)
    install_clock()
    seed_state()

    import wire
    wire.now_utc = fake_now

    original = wire.load_yaml

    def stamped(name):
        cfg = original(name)
        if name == "config.yaml":
            cfg["site"]["banner"] = ("Sample data — every story below is invented. "
                                     "Run wire.py for real feeds.")
            cfg["email"]["enabled"] = False
        return cfg

    wire.load_yaml = stamped
    wire.translate.translate_headlines = lambda items, state, enabled: 0
    wire.verify.check_link_rot = lambda live, limit=25, min_age_hours=1.0: 0

    print("Building preview — 8 runs, 15 simulated minutes apart\n")
    for step in range(8):
        run = min(step, max(SCRIPT))
        wire.sources.collect = lambda feeds, state, r=run: build_feed(r)
        wire.main()
        CLOCK["now"] += dt.timedelta(minutes=15)
        print()

    print("Preview built. Open docs/index.html")
    print("Every story in it is invented. Run `python wire.py` for real feeds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
