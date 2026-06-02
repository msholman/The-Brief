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

## A few honest notes

- **Big boards from cloud servers:** Indeed and Google Jobs are the most
  reliable from GitHub's servers. LinkedIn and Glassdoor sometimes block
  requests coming from datacenters — if you notice they return little, that's
  why. The niche RSS boards and company ATS boards always work.
- **If LinkedIn matters a lot to you:** you can also run `scraper.py` on your
  own computer (which uses your home internet and gets blocked far less), then
  upload the resulting jobs.json. Ask and I'll walk you through it.
- **Cost:** everything here is free on GitHub's standard plan.
