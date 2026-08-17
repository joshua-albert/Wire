# Getting The Wire live

Start to finish, assuming you've never used GitHub. About 40 minutes, most of
it waiting. Everything here is free.

At the end you'll have a site at `https://YOURNAME.github.io/wire/` that
rebuilds itself every 15 minutes and emails you when something breaks.

---

## Before you start: make the repository PUBLIC

This matters and it's the one thing people get wrong.

GitHub gives you **unlimited free build minutes on public repositories**.
Private repos get 2,000 minutes a month — and running every 15 minutes uses
roughly 2,900. You'd hit the ceiling in about three weeks and the site would
silently stop updating. GitHub Pages on a private repo also needs a paid plan.

So: **public**. Nothing sensitive lives in the code. Your email password goes
in GitHub Secrets, which stay private even on a public repo.

---

## Step 1 — Install Python

**Mac.** Open Terminal (Cmd+Space, type "terminal"). Paste:

```bash
python3 --version
```

If you see 3.10 or higher, skip ahead. Otherwise install from
[python.org/downloads](https://www.python.org/downloads/) — the big yellow
button. Run the installer, accept the defaults.

**Windows.** Install from
[python.org/downloads](https://www.python.org/downloads/). **Tick "Add Python
to PATH" on the first screen** — it's easy to miss and everything downstream
breaks without it. Then open PowerShell (Start menu, type "powershell") and
check:

```powershell
python --version
```

Everywhere below, Mac users type `python3` and Windows users type `python`.

---

## Step 2 — Put the files somewhere and open a terminal there

Unzip `the-wire.zip`. Put the `the-wire` folder in your home directory or
Documents — somewhere you'll find it again.

Now point your terminal at it:

```bash
cd ~/Documents/the-wire        # Mac — adjust if you put it elsewhere
```
```powershell
cd $HOME\Documents\the-wire    # Windows
```

Check you're in the right place:

```bash
ls          # Mac        — should list wire.py, feeds.yaml, config.yaml
dir         # Windows
```

---

## Step 3 — Install the three libraries it needs

```bash
python3 -m pip install -r requirements.txt
```

Takes about twenty seconds. If pip isn't found on Mac, try
`python3 -m ensurepip --upgrade` first.

---

## Step 4 — Look at it before configuring anything

```bash
python3 demo.py
```

Then open `docs/index.html` in your browser (double-click it). This is the
site running on invented stories — stamped in red so it can't be mistaken for
real. It's how you check the layout works on your screen before committing to
anything.

---

## Step 5 — Make it yours

```bash
python3 setup.py
```

Eight questions: what to call it, which beats lead, your city, extra keywords,
how much email. Press enter to accept any default. Run it again any time.

---

## Step 6 — Find out which feeds actually work

```bash
python3 check_feeds.py --prune
```

This tests all 302 URLs and comments out the dead ones. **Expect 20 to 50
failures.** News outlets move and drop RSS constantly, and I couldn't test
these from where I built them. That's normal, and the remaining ~260 is far
more than you need.

Takes two or three minutes. Read the list at the end — if a source you
particularly want is dead, search for its current RSS URL and fix that line in
`feeds.yaml`.

---

## Step 7 — The first real run

```bash
python3 wire.py
```

Two to four minutes the first time. You'll see feeds being pulled, then a line
like `wrote docs/ — 400 threads, 400 new`. Open `docs/index.html` again — now
it's real news.

The first run looks thin in places, and that's expected rather than broken.
Early Signal needs a day of reading before novelty means anything, Unusual
Activity needs about a week to build baselines, and the source ledger needs a
few weeks. Corrections and independence work immediately.

---

## Step 8 — Put it on GitHub

**Create the account.** [github.com/signup](https://github.com/signup). Free.
Your username becomes part of the URL, so pick something you'll be happy
typing.

**Then pick one of these two paths.**

### Path A — GitHub Desktop (no terminal)

1. Install [GitHub Desktop](https://desktop.github.com/) and sign in.
2. **File → Add Local Repository**, choose your `the-wire` folder.
3. It'll say the folder isn't a repository — click **create a repository**.
   Name it `wire`. Leave everything else alone. **Create Repository.**
4. Bottom left: type "first commit" in the summary box, click **Commit to
   main**.
5. Top of the window: **Publish repository**. **Untick "Keep this code
   private."** Click Publish.

### Path B — Command line

```bash
git init
git add .
git commit -m "first commit"
git branch -M main
```

Go to [github.com/new](https://github.com/new). Repository name: `wire`.
Select **Public**. Don't add a README or .gitignore. **Create repository.**

Then paste the two lines GitHub shows you, which look like:

```bash
git remote add origin https://github.com/YOURNAME/wire.git
git push -u origin main
```

---

## Step 9 — Turn on the website

In your repo on github.com:

1. **Settings** (top right of the repo, not your account settings)
2. **Pages** in the left sidebar
3. Under "Build and deployment", Source: **Deploy from a branch**
4. Branch: **main**, folder: **/docs**. Click **Save**.

Wait two or three minutes, then reload the Pages settings screen. Your URL
appears at the top: `https://YOURNAME.github.io/wire/`. Open it. That's your
site, live on the internet.

---

## Step 10 — Turn on the 15-minute schedule

1. **Actions** tab. If it asks, click **I understand my workflows, go ahead
   and enable them.**
2. Left sidebar: **Update the wire**.
3. **Run workflow → Run workflow** to trigger one immediately.
4. Wait a minute, refresh. A green tick means it worked. Click into the run to
   read the log if you want to see what it pulled.

From now on it runs itself. GitHub's scheduler is best-effort — a 15-minute
cron often lands closer to 20 when GitHub is busy.

**One thing to know:** GitHub disables scheduled workflows after 60 days of no
activity in the repo. If you go two months without touching it, open the
Actions tab and click Run workflow to wake it up.

---

## Step 11 — Email alerts

You need an app password, not your normal email password. Gmail instructions;
any SMTP provider works the same way.

**Get the app password:**

1. [myaccount.google.com/security](https://myaccount.google.com/security)
2. Turn on **2-Step Verification** if it isn't already. Required.
3. Search that page for **App passwords** (or go to
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))
4. Name it "wire", click Create. Copy the 16-character code — you only see it
   once.

**Put it in GitHub:**

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add these seven, one at a time:

| Name | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | your full Gmail address |
| `SMTP_PASS` | the 16-character app password, no spaces |
| `MAIL_TO` | where alerts should go |
| `MAIL_FROM` | your Gmail address again |
| `SITE_URL` | `https://YOURNAME.github.io/wire` |

Then Actions → Run workflow again. Check the log for `email: sent` or
`email: holding` — holding just means nothing cleared the bar yet, which is
normal and correct.

**Don't want email?** Skip this entirely and subscribe to
`https://YOURNAME.github.io/wire/feed.xml` in any RSS reader. Same alerts,
no setup.

---

## Step 12 — The first week: calibrate it

This is the step that separates a working tool from an impressive one. Every
threshold in this thing was tuned against invented stories. Real news will
behave differently.

**After three days of it running,** pull the latest state and measure:

```bash
git pull
python3 calibrate.py
```

You'll get a report. What to do with it:

| It says | Do this in `config.yaml` |
|---|---|
| Singletons above 80% | Lower `cluster_threshold` toward 0.36 |
| Singletons below 45% | Raise `cluster_threshold` toward 0.50 |
| SUSPECT clusters listed, and they're genuinely different stories | Raise `anchor_threshold` toward 0.30 |
| SPLITS listed, and they're genuinely the same story | Lower `cluster_threshold` |
| Confidence mostly "low" | Nothing to fix — those feeds ship no summary text |
| Too much email | Raise `email.min_score` |
| Front page too samey | Raise `novelty_weight` |
| Too much obscure noise | Lower `novelty_weight` |

Then see how a change would land before committing to it:

```bash
python3 calibrate.py --sweep
```

Edit `config.yaml`, then push the change:

```bash
git add config.yaml && git commit -m "tune clustering" && git push
```

Or in GitHub Desktop: the change shows up automatically, write a summary,
Commit to main, Push origin.

Expect to do this twice in the first fortnight and then rarely.

---

## When something goes wrong

| Symptom | Cause and fix |
|---|---|
| `python3: command not found` (Windows) | Use `python`. If that fails, reinstall Python with "Add to PATH" ticked. |
| `No module named feedparser` | You skipped step 3, or installed to a different Python. Rerun `python3 -m pip install -r requirements.txt`. |
| Page is nearly empty | Most feeds failed. Run `python3 check_feeds.py`. If almost everything fails, it's your network or a proxy. |
| Action fails with "Permission denied" pushing | Repo → Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save. |
| Pages URL shows 404 | Give it five minutes. Then confirm Settings → Pages says branch `main`, folder `/docs`, and that `docs/index.html` exists in the repo. |
| Site stopped updating | Actions tab — look for red X runs. Also check the 60-day sleep rule above. |
| `email: send failed` | Almost always the app password. Regenerate it, remove spaces, re-save the secret. |
| Same story appears three times | Clustering is too strict. Step 12. |
| Unrelated stories merged together | Clustering is too loose. Step 12. |
| Repo getting large | Once a quarter: `git checkout --orphan fresh && git add -A && git commit -m squash && git branch -D main && git branch -m main && git push -f` |

---

## The rhythm after that

- **Weekly:** glance at `sources.html`. After a month it tells you which feeds
  earn their place.
- **Monthly:** `python3 check_feeds.py --prune`, then push. Feeds rot.
- **Quarterly:** squash the repo history (see above).
- **Whenever:** add feeds to `feeds.yaml`. Copy any existing line, change the
  name, URL and tags. Export your whole source list to another reader any time
  from `sources.opml`.
