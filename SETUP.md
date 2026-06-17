# The Brief — Setup Guide

This walks you through putting your job aggregator on GitHub so it updates
itself every morning. No coding and no command line — everything happens in
your web browser. Budget about 20 minutes for the first setup.

You'll end up with:
- A live dashboard at a web address you can bookmark (no more localhost)
- A scraper that runs automatically every morning and refreshes your listings

---

## Part 1 — Create a GitHub account (skip if you have one)

1. Go to https://github.com and click **Sign up**.
2. Follow the prompts. The free plan is all you need.

---

## Part 2 — Create your repository

A "repository" (or "repo") is just a project folder that lives on GitHub.

1. Once logged in, click the **+** in the top-right corner, then **New repository**.
2. Under **Repository name**, type: `the-brief`
3. Choose **Public**. (Public repos get unlimited free Actions minutes. Your
   dashboard will be viewable by anyone with the link, but there's nothing
   private in it — it just shows public job listings.)
4. Check the box **Add a README file**.
5. Click **Create repository**.

---

## Part 3 — Upload the files

You have a folder called `the-brief` with these files inside:
- `index.html`        (the dashboard)
- `scraper.py`        (the scraper)
- `requirements.txt`  (its dependencies)
- `jobs.json`         (placeholder data, replaced on first run)
- `.github/workflows/update-jobs.yml`  (the scheduler)

Upload them:

1. On your new repo's page, click **Add file** → **Upload files**.
2. Open the `the-brief` folder on your computer. Select `index.html`,
   `scraper.py`, `requirements.txt`, and `jobs.json` and drag them into the
   browser upload area. (Leave the `.github` folder for the next step — dot-folders
   sometimes don't drag cleanly.)
3. Scroll down and click **Commit changes**.

Now add the scheduler file (it lives in a special folder):

4. Click **Add file** → **Create new file**.
5. In the filename box at the top, type exactly:
   `.github/workflows/update-jobs.yml`
   (As you type the slashes, GitHub creates the folders automatically.)
6. Open `update-jobs.yml` from the `.github/workflows` folder on your computer
   in any text editor, copy everything, and paste it into the big text box.
7. Click **Commit changes**.

---

## Part 4 — Turn on the dashboard (GitHub Pages)

1. In your repo, click **Settings** (top menu).
2. In the left sidebar, click **Pages**.
3. Under **Build and deployment** → **Source**, choose **Deploy from a branch**.
4. Under **Branch**, pick **main** and **/ (root)**, then click **Save**.
5. Wait 1–2 minutes. The page will show a link like:
   `https://YOUR-USERNAME.github.io/the-brief/`
6. Click it — that's your live dashboard. **Bookmark it.** For now it shows
   placeholder data; that changes after the first scrape.

---

## Part 5 — Run the scraper for the first time

1. In your repo, click the **Actions** tab (top menu).
2. If GitHub asks you to enable workflows, click the green button to confirm.
3. On the left, click **Update job listings**.
4. On the right, click **Run workflow** → **Run workflow** (green button).
5. It will take 2–5 minutes. When the dot turns green, it's done.
6. Refresh your dashboard — real listings should now appear.

From now on it runs **automatically every morning** at 6 AM Eastern. You can
also hit **Run workflow** any time you want a fresh pull.

---

## Customizing what it searches

Everything you'd want to change lives at the top of `scraper.py`, in the
section marked CONFIG. To edit on GitHub: open `scraper.py` in your repo, click
the pencil icon (top-right of the file), make your change, and **Commit changes**.

- `SEARCH_TERMS` — the phrases sent to LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter.
- `HOURS_OLD` — how far back to look (720 = 30 days, 336 = 14 days).
- `GREENHOUSE_BOARDS` / `LEVER_BOARDS` — add company boards by their slug.
- `JOBSPY_SITES` — remove any big board that consistently returns nothing.

---

## Turning on AI scoring (optional but recommended)

This scores every listing 0–100 for how well it fits you, with a one-line
reason, and lets you sort and filter by fit. It needs an Anthropic API key,
stored privately as a repository secret. Without a key, everything else still
works — the scraper just skips scoring.

**Step 1 — Get an API key**
1. Go to https://console.anthropic.com and sign in (or create an account).
2. Add a small amount of credit under **Billing** (scoring is cheap — see below).
3. Under **API Keys**, click **Create Key**, name it `the-brief`, and copy it.
   You'll only see it once, so copy it now.

**Step 2 — Store it as a GitHub secret**
1. In your repo, go to **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
3. Name: `ANTHROPIC_API_KEY` (exactly, all caps with underscores).
4. Secret: paste your key.
5. Click **Add secret**.

**Step 3 — Tell the Action to use it**
1. Open `.github/workflows/update-jobs.yml` → pencil icon.
2. Find the line `run: python scraper.py` and replace that whole step with:
   ```
         - name: Run the scraper
           env:
             ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
           run: python scraper.py
   ```
3. Commit changes, then **Actions** → **Run workflow**.

After it runs, your dashboard shows a fit score on each card, a "Minimum AI fit"
filter, and a "Best AI fit" sort option.

**Personalize the scoring:** the profile the AI scores against lives in
`scraper.py` under `PROFILE`. Edit it anytime to shift what counts as a good fit.

**Cost:** scoring runs on a fast, inexpensive model and only scores your top
~120 candidates per run, batched. In practice this is a few cents per day. You
can lower `MAX_TO_SCORE` in the config to spend even less.

---

## Turning on the email digest (optional)

After each overnight scrape, The Brief can email you the top new matches —
roles scored 70+ that you haven't seen before, ranked by AI fit, delivered
before you open the dashboard. It uses Gmail and requires two GitHub secrets.

**Step 1 — Create a Gmail App Password**
You can't use your regular Gmail password here — Google requires a dedicated
App Password for this kind of programmatic access.
1. Go to **myaccount.google.com/apppasswords** (you'll need 2-step verification
   enabled on your Google account).
2. Under "Select app" choose **Mail**, under "Select device" choose **Other**,
   name it `the-brief`, and click **Generate**.
3. Copy the 16-character password shown — you'll only see it once.

**Step 2 — Add two GitHub secrets**
In your repo, go to **Settings → Secrets and variables → Actions → New
repository secret** and add these two (exactly as named):

| Name | Value |
|------|-------|
| `DIGEST_EMAIL_ADDRESS` | Your Gmail address (e.g. you@gmail.com) |
| `DIGEST_APP_PASSWORD` | The 16-character App Password from Step 1 |

**Step 3 — Update the workflow file**
The workflow already has the digest secrets wired in (as of the current version
of `update-jobs.yml`). If you updated the workflow file recently, you're done.
If you're unsure, check that your `.github/workflows/update-jobs.yml` contains
`DIGEST_EMAIL_ADDRESS` and `DIGEST_APP_PASSWORD` under the scraper step's `env:`
block.

**Step 4 — Run the workflow**
Actions → Update job listings → Run workflow. If there are 70+ fit listings
from the last 3 days that you haven't received before, a digest will arrive
in your inbox within a minute or two of the run finishing.

**Tuning the digest**
In `scraper.py` under CONFIG:
- `DIGEST_MIN_FIT` — minimum fit score to include (default 70)
- `DIGEST_MAX_LISTINGS` — maximum listings per email (default 10)

**How "new" is tracked**
The scraper writes a `seen_urls.json` file to your repo after each digest send.
This is how it knows not to send you the same listing twice. The file is
committed automatically by the Action — you may see it appear in your repo
after the first digest run. Don't edit or delete it; it's part of the system.

---

## A few honest notes

- **Big boards from cloud servers:** Indeed and Google Jobs are the most
  reliable from GitHub's servers. LinkedIn and Glassdoor sometimes block
  requests coming from datacenters — if you notice they return little, that's
  why. The niche RSS boards and company ATS boards always work.
- **If LinkedIn matters a lot to you:** you can also run `scraper.py` on your
  own computer (which uses your home internet and gets blocked far less), then
  upload the resulting jobs.json. Ask and I'll walk you through it.
- **Cost:** everything here is free on GitHub's standard plan.
