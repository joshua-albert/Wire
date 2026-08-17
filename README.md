# THE WIRE

*v2.1 — fixes thread chaining, non-Latin script handling, and false
correction flags found during first live calibration.*

A personal breaking-news desk. Pulls 302 feeds in 17 languages every 15
minutes, folds the same story from every outlet into one tracked thread,
measures how fast each thread is spreading, publishes a plain clickable page,
and emails you when something clears the bar.

Free to run forever on GitHub Actions + GitHub Pages. No server, no bill.

---

## What's in the box

| File | What it does |
|---|---|
| `feeds.yaml` | 302 sources with trust tier, topic tags, language and access level. |
| `config.yaml` | Every dial — urgency words, velocity, email rules, sections. |
| `wire.py` | The run: pull → translate → thread → score → publish → mail. |
| `wirelib/threads.py` | Story threading, pickup velocity, confirmation, source ledger. |
| `wirelib/scoring.py` | What floats to the top. |
| `wirelib/translate.py` | Foreign headlines into English. |
| `wirelib/render.py` | The pages. |
| `wirelib/mailer.py` | Digests and escalation alerts. |
| `check_feeds.py` | Tests every feed URL and tells you what's broken. |
| `demo.py` | Builds a labelled preview from fictional stories. |
| `setup.py` | Interactive first-run wizard. |
| `calibrate.py` | Measures clustering quality on real feeds and says what to tune. |

Three kinds of page come out: the front page, one **thread page per story**, and
a **source ledger** at `sources.html`.

---

**Getting it online: read [DEPLOY.md](DEPLOY.md).** Step by step, assumes no
GitHub experience, about 40 minutes.

---

## Setup

**See it first.**

```bash
pip install -r requirements.txt
python demo.py        # then open docs/index.html
```

Builds the whole site from invented stories so you can look at every part of
it before configuring anything. The preview is stamped in red — nothing in it
is real. `python wire.py` replaces it with actual feeds.

**Then run the wizard.**

```bash
pip install -r requirements.txt
python setup.py
```

It asks what to call it, what beats you care about, your city, and how much
mail you want — then prints exactly what to do next. No code required.

**1. Put it on GitHub**

```bash
cd wire
git init && git add . && git commit -m "the wire"
gh repo create wire --public --source=. --push   # public: free unlimited Actions
```

**2. Turn on Pages**

Settings → Pages → Source: *Deploy from a branch* → `main`, folder `/docs`.
Your page lands at `https://YOURNAME.github.io/the-wire/`.

**3. Turn on email**

Settings → Secrets and variables → Actions → *New repository secret*:

| Secret | Value (Gmail example) |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | a Google **app password**, not your login password |
| `MAIL_TO` | where alerts go |
| `SITE_URL` | your Pages URL from step 2 |

App password: Google Account → Security → 2-Step Verification → App passwords.

**4. Optional — better translation**

Add `DEEPL_API_KEY`. The free tier is 500k characters a month, far more than
this needs. Without it, translation falls back to Google's public endpoint —
works, but unofficial. Set `LIBRETRANSLATE_URL` instead if you'd rather
self-host.

**5. Kick it off**

Actions → *Update the wire* → **Run workflow**.

Locally: `pip install -r requirements.txt && python wire.py`

---

## What makes it different

Most aggregators count outlets. This one counts **newsrooms**.

When eight papers run the same Reuters copy, that is one report syndicated
eight times — not eight confirmations. The desk detects agency copy by wire
attribution and by fingerprinting the prose itself, then collapses reprints
into a single independent voice. A headline that says **3 INDEP / 8 CARRIED**
is telling you something no other reader will.

Everything downstream depends on it: the CONFIRMED badge, the corroboration
score, the siren threshold, and which sources get credited with scoops.

---

## The systems

### Story threads

A thread is one real-world event, tracked across every outlet and every
rewording. Click **thread** under any headline and you get the pickup curve,
every headline version with timestamps, who filed first and how far ahead they
were, and every outlet's link — including the untranslated original.

This is what makes "the story changed" visible instead of annoying.

### Velocity

Volume says a story is big. Velocity says it's *becoming* big. The desk records
how many distinct outlets carry a thread and when, so it can measure pickup per
hour. One outlet to eight in forty minutes looks nothing like eight outlets that
all filed yesterday, and only one of those is worth interrupting you for.

The **Breaking fastest** column ranks purely on acceleration. A red ▲ badge
marks anything above 1.5 outlets/hour.

### Non-English local press

22 feeds in 16 languages — Ukrainska Pravda, Novaya Gazeta Europe, RFI Afrique,
Kompas, Prachatai, Yonhap, Al-Araby and more. Headlines are machine-translated;
originals are kept and shown on the thread page.

This is the closest thing to what you were actually after. A Kyrgyz story breaks
in Russian, gets picked up in Ukrainian, and reaches Reuters ninety minutes
later — the thread starts at minute zero, not at Reuters.

### Confirmation state

- **PRIMARY** — straight from the source: a court, an agency, a seismograph.
- **CONFIRMED** — two or more independent outlets.
- **UNCONFIRMED** — one outlet so far. Shown, not hidden, but marked and pushed
  down slightly.

You see the story immediately *and* you see how much weight it holds. When a
second outlet picks it up, the badge flips on the next run.

### Read and dismiss

Click a headline and it goes grey. Hit **×** to kill it outright. **Hide read**
collapses to unread only. All of it lives in your browser's storage — nothing
leaves the device and the site stays a static file with no backend. Per-device,
so phone and laptop keep separate state.

### Corrections and walk-backs

A headline that changes is not automatically a story developing. Sometimes it's
a retreat. The desk classifies every revision:

- **REVISED UP / DOWN** — a number moved. `12 → 4`, with the diff shown.
- **HEDGED** — a qualifier appeared. "reportedly", "allegedly", "claims".
- **FIRMED UP** — a qualifier was dropped.
- **CORRECTION** — the outlet used correction language itself.
- **REWRITTEN** — substantially different text.
- **PULLED** — the original URL now 404s. Single-source stories get re-checked;
  a story quietly deleted is worth knowing about.

Revisions are caught per newsroom, not just on the leading headline — because
corrections arrive as the same outlet refiling with a different number in it,
which no headline-list aggregator notices. Thread pages show a word-level diff.

### Unusual activity

The part nothing else does. Every country and beat carries a rolling
three-week baseline. When somewhere that normally produces one story a day
starts producing seven, it gets flagged at the top of the page — before any
outlet has written the analysis piece.

This is "the small thing that could be big" measured at the level of a place
rather than a headline. In testing, a country going from 0.3 stories/day to 3
flagged immediately, while the US going from 9 to 10 correctly did not.

### Argument

67 feeds of political writing and analysis, deliberately spanning the
spectrum — Jacobin, Dissent, n+1, The Baffler, New Left Review, Le Monde
Diplomatique and The American Prospect alongside The Economist, Foreign
Affairs, The Atlantic, National Review, Reason and Compact. Reading only
people who agree with you is how you get surprised.

Plus 13 feeds on elections and voting rights, and 20 more on Washington
specifically — committee action, the Federal Register, CBO scores, inspector
general reports, the Supreme Court order list.

### Beats and entities

Places, people and organisations are pulled out of headlines against a
built-in gazetteer of ~135 countries plus proper-noun detection. Every subject
gets its own page: read Sudan or Rafael Grossi or SEPTA end to end instead of
scrolling for them. `beats.html` indexes the lot.

### Built for reading fast

- **Keyboard**: `j`/`k` move, `o` open, `t` thread, `x` dismiss, `s` star,
  `u` unread only, `/` search, `?` help.
- **Live filter** across headline, source, country and entity.
- **Saved beats** — type a term, press `+`, and it becomes a standing lane on
  your front page that fills automatically.
- Dark mode, density toggle, print stylesheet.

### Source ledger

`sources.html` keeps score on the feeds themselves:

- **Started** — threads this source opened first.
- **Scoops** — it was first, and at least two other outlets went on to confirm.
- **Orphans** — it filed alone and nobody ever followed.
- **Lead** — average head start over the second outlet, in minutes.
- **Score** — 0-1, scoops against orphans.

After a few weeks this stops being decorative. A source with a strong record
gets a small automatic scoring boost (`reliability_weight`), and you'll be able
to see which of the 145 feeds actually earn their slot.

---

## Paywalls

Every source carries an `access` level and headlines are labelled before you
click:

- **free** — no label. 263 of the 302 sources.
- **METERED** — a few articles a month, then a wall.
- **PAYWALL** — subscribers only. 11 sources, mostly The Economist, FT,
  Foreign Affairs, LRB and NYRB.

The **All sources / Free only** button in the command bar hides paywalled
items entirely when you just want to read.

The tool doesn't bypass paywalls, and that's deliberate — the reporting this
whole thing depends on is what subscriptions pay for. Three legitimate routes
to the good stuff:

- **Your library card.** The Free Library of Philadelphia gives cardholders
  free digital access to The Economist, NYT, WSJ and others through
  PressReader and Libby. Most US library systems do something similar. This
  is the single best answer and almost nobody uses it.
- **Free accounts.** The Atlantic, Foreign Policy and Le Monde Diplomatique
  all give registered readers a monthly allowance.
- **The free tier is enormous.** Jacobin, Dissent, The Baffler, The American
  Prospect, Mother Jones, Boston Review, Lawfare, Just Security, New Lines,
  Aeon, Noema, openDemocracy, Democracy Docket, Votebeat, Bolts, Brennan
  Center and Phenomenal World are all fully open, and they're most of the
  political writing here.

---

## Email behaviour

Three reasons you get mail:

1. **Breaking** — a siren-level story. Sent immediately, ignores the cooldown.
2. **Escalating** — something you were already told about crossed 6 outlets and
   2.0 outlets/hour. One follow-up only; you won't get pestered about the same
   thread all day.
3. **Digest** — 6+ ordinary new stories, no more than once every 45 minutes.

All under `email:` in `config.yaml`. If the inbox floods, raise `min_score`. If
it's too quiet, lower `batch_size`.

---

## Feeds break. Here's the maintenance.

Outlets move URLs and drop RSS without warning. Some feeds here will be dead on
arrival — normal, and the page just runs with the rest.

```bash
python check_feeds.py           # test all 302
python check_feeds.py --prune   # comment out the dead ones
```

Do this on day one, then whenever the page looks thin. The footer shows how many
feeds failed on the last run.

---

## Tuning

| Symptom | Dial |
|---|---|
| Front page too samey | raise `novelty_weight` |
| Too much obscure noise | lower `novelty_weight` |
| Same story appearing twice | lower `cluster_threshold` |
| Unrelated stories merging | raise `cluster_threshold` |
| Not enough urgency up top | raise `velocity_weight` |
| Too many single-source rumours | make `unconfirmed_penalty` more negative |
| Too many emails | raise `email.min_score` |

---

## Using it as anything but a personal desk

Everything personal — read state, stars, dismissals, saved beats — lives in
browser storage. That means **anyone can use the published site** with their
own filters and lanes, no accounts and no backend, and the whole thing stays
static files on free hosting.

The honest limit: per-visitor *email* is the one thing that needs a real
backend, because sending mail requires credentials the browser can't hold.
Three ways around it, in order of effort:

1. **RSS** (`feed.xml`) — already generated, works in any reader, gives any
   visitor push alerts today. This covers most people.
2. **Fork per person** — each reader runs their own copy with their own
   config. Free, five minutes, fully independent.
3. **Real multi-tenant** — swap `state.json` for Postgres, add auth and a
   mail queue, run the fetcher on a worker. That's a hosted product with a
   monthly bill, not a static site.

---

## Calibrate it in week one

Every threshold here was tuned against invented stories, which is the honest
weak point of the whole project. `calibrate.py` is how you close it:

```bash
python calibrate.py --live      # pull feeds, then measure
python calibrate.py --sweep     # try a range of thresholds side by side
```

It reports four things — how many stories nobody else carried, which clusters
look over-merged, which pairs probably should have merged, and how much of the
corroboration count is syndicated reprint. Each one maps to a number in
`config.yaml`. Full table in DEPLOY.md step 12.

It works: running it against the demo immediately caught the anchor rule
merging three unrelated court stories, which is why that rule is now much
harder to satisfy.

---

## Two operational notes

**Repo size.** State is committed every run, ~96 commits a day. `threads.json`
is capped at 5 days, but the repo still grows. Once a quarter:

```bash
git checkout --orphan fresh && git add -A && git commit -m "squash" && \
git branch -D main && git branch -m main && git push -f
```

**Timing.** GitHub's scheduler is best-effort — a 15-minute cron often lands
closer to 20 during busy hours. For tighter, the same code runs under a normal
crontab on any always-on box.

---

## About the Twitter accounts

Lookner, Spectator Index and the rest can't be pulled directly — X killed free
API access and the RSS bridges. Two things cover most of the gap:

- **The alert tier** in `feeds.yaml` is where those accounts get their material:
  USGS, GDACS, ReliefWeb, ProMED, WHO outbreak notices, ACLED, State and Defense
  press releases. You read the same wire they do, without waiting for the tweet.
- **The non-English feeds and Google News queries** cover the long tail and the
  Philly crime beat. Your old police-misconduct alert terms are already in there.

If you want the accounts themselves, a self-hosted
[RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) instance slots straight
into `feeds.yaml`.
