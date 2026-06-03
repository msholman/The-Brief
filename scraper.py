#!/usr/bin/env python3
"""
The Brief — job scraper
Runs on a schedule (via GitHub Actions) and writes jobs.json,
which the dashboard reads. Pulls from JobSpy (LinkedIn, Indeed,
Glassdoor, Google, ZipRecruiter), RSS feeds, and ATS APIs.

You can edit the CONFIG section below — no other changes needed.
"""

import json
import re
import sys
import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ============================================================================
# CONFIG — edit these to change what gets searched. Nothing else needs editing.
# ============================================================================

# Search terms sent to LinkedIn / Indeed / Glassdoor / Google / ZipRecruiter.
SEARCH_TERMS = [
    "healthcare content writer",
    "health content strategist",
    "medical writer",
    "health communications",
    "healthcare copywriter",
    "content designer healthcare",
    "ux writer",
    "technical writer healthcare",
]

# Titles containing any of these phrases are dropped — roles you don't want.
EXCLUDE_TITLE_TERMS = [
    "grant writer",
    "grant writing",
    "grants writer",
    "compensation analyst",
    "recruiter",
    "account executive",
    "sales representative",
    "sales manager",
]

# Which big boards to scrape via JobSpy.
# NOTE: from GitHub's servers, "indeed" and "google" are the most reliable.
# "linkedin" and "glassdoor" sometimes get rate-limited from cloud IPs — keep
# them on and see how they do; remove any that consistently return nothing.
JOBSPY_SITES = ["indeed", "google", "zip_recruiter", "linkedin", "glassdoor"]

# How far back to look (in hours). 720 = 30 days, 336 = 14 days.
HOURS_OLD = 720

# Results to request per search term, per site.
RESULTS_PER_TERM = 20

# Country for Indeed/Glassdoor (JobSpy needs this).
COUNTRY_INDEED = "usa"

# RSS feeds — niche writing/marketing boards with real feeds.
RSS_FEEDS = [
    ("ProBlogger",                   "https://jobs.problogger.com/feed/",                                   "writing"),
    ("We Work Remotely — Writing",   "https://weworkremotely.com/categories/remote-writing-jobs.rss",       "writing"),
    ("We Work Remotely — Marketing", "https://weworkremotely.com/categories/remote-marketing-jobs.rss",     "marketing"),
    ("Jobicy — Content",             "https://jobicy.com/?feed=job_feed&search_keywords=content+writer",    "writing"),
    ("Jobicy — Marketing",           "https://jobicy.com/?feed=job_feed&search_keywords=marketing",         "marketing"),
    ("RemoteOK — Writing",           "https://remoteok.com/remote-writing-jobs.rss",                        "writing"),
    ("JournalismJobs",               "https://www.journalismjobs.com/rss",                                  "journalism"),
]

# Company boards on Greenhouse (use the slug from boards.greenhouse.io/SLUG).
GREENHOUSE_BOARDS = [
    ("RVO Health (freelance)", "rvohcontentfreelance", "writing"),
    ("Axios",                  "axios",                "journalism"),
    ("Grist",                  "grist",                "journalism"),
]

# Company boards on Lever (use the slug from jobs.lever.co/SLUG).
LEVER_BOARDS = [
    ("Solutions Journalism", "solutionsjournalism", "journalism"),
]

# ============================================================================
# END CONFIG
# ============================================================================

UA = "Mozilla/5.0 (compatible; TheBriefBot/1.0)"


def detect_type(text):
    t = text.lower()
    types = []
    if re.search(r"freelanc", t): types.append("freelance")
    if re.search(r"\bcontract\b|contractor|\b1099\b", t): types.append("contract")
    if re.search(r"part[\s-]?time", t): types.append("part-time")
    if re.search(r"full[\s-]?time", t): types.append("full-time")
    return types


def detect_location(text):
    t = text.lower()
    locs = []
    if re.search(r"\bremote\b|work from home|\bwfh\b|anywhere|distributed", t): locs.append("remote")
    if re.search(r"\bhybrid\b", t): locs.append("hybrid")
    if re.search(r"on[\s-]?site|in[\s-]?office|in[\s-]?person", t): locs.append("onsite")
    return locs


def detect_category(title, text, source_cat):
    """Category is decided primarily from the TITLE. Scanning the full
    description produces false positives (e.g. a 'Compensation Analyst' whose
    description happens to mention 'growth' or 'communications')."""
    t = title.lower()
    if re.search(r"\b(journalist|reporter|correspondent|newsroom|news editor)\b", t):
        return "journalism"
    if (re.search(r"\b(writer|writing|copywriter|copywriting|editor|editorial|"
                  r"proofread|author|ux writer|technical writer)\b", t)
            or re.search(r"content (strateg|design|market|writ|lead|manager|specialist)", t)):
        return "writing"
    if re.search(r"\b(marketing|brand|social media|seo|public relations|"
                 r"communications|demand gen|growth marketing|campaign manager)\b", t):
        return "marketing"
    # Fall back to the feed's declared category (RSS feeds set this).
    # Do NOT scan the description — that's what created the noise.
    return source_cat if source_cat and source_cat != "mixed" else "other"


def enrich(job, source_cat):
    title = job.get("title", "")
    text = f"{title} {job.get('description','')} {job.get('company','')}"
    job["types"] = detect_type(text)
    job["locations"] = detect_location(text)
    job["category"] = detect_category(title, text, source_cat)
    return job


def iso_date(value):
    """Normalize various date inputs to YYYY-MM-DD or None."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            # epoch — guess ms vs s
            secs = value / 1000 if value > 1e12 else value
            return datetime.datetime.utcfromtimestamp(secs).strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        s = str(value)
        # try ISO-ish
        return s[:10]
    except Exception:
        return None


def fetch_json(url):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ---------------------------------------------------------------------------
# Source scrapers
# ---------------------------------------------------------------------------

def scrape_jobspy_all():
    jobs = []
    try:
        from jobspy import scrape_jobs
        import pandas as pd
    except ImportError:
        print("  ! jobspy not installed — skipping big boards", file=sys.stderr)
        return jobs

    for term in SEARCH_TERMS:
        try:
            print(f"  JobSpy: '{term}'")
            df = scrape_jobs(
                site_name=JOBSPY_SITES,
                search_term=term,
                google_search_term=f"{term} jobs remote",
                location="Remote",
                results_wanted=RESULTS_PER_TERM,
                hours_old=HOURS_OLD,
                country_indeed=COUNTRY_INDEED,
                is_remote=True,
            )
            if df is None or len(df) == 0:
                continue
            for _, row in df.iterrows():
                title = str(row.get("title", "") or "")
                url = str(row.get("job_url", "") or "")
                if not title or not url or url == "nan":
                    continue
                desc = str(row.get("description", "") or "")[:320]
                company = str(row.get("company", "") or "")
                site = str(row.get("site", "") or "").replace("_", " ").title()
                loc = str(row.get("location", "") or "")
                jtype = str(row.get("job_type", "") or "")
                job = enrich({
                    "title": title.strip(),
                    "url": url.strip(),
                    "description": (loc + " · " + desc).strip(" ·"),
                    "date": iso_date(row.get("date_posted")),
                    "source": site or "JobSpy",
                    "company": company.strip(),
                }, "mixed")
                # fold structured fields into detection
                for k in detect_type(jtype + " " + loc):
                    if k not in job["types"]:
                        job["types"].append(k)
                for k in detect_location(jtype + " " + loc):
                    if k not in job["locations"]:
                        job["locations"].append(k)
                jobs.append(job)
        except Exception as e:
            print(f"  ! JobSpy term '{term}' failed: {e}", file=sys.stderr)
    return jobs


def scrape_rss():
    jobs = []
    try:
        import feedparser
    except ImportError:
        print("  ! feedparser not installed — skipping RSS", file=sys.stderr)
        return jobs

    for name, url, cat in RSS_FEEDS:
        try:
            print(f"  RSS: {name}")
            feed = feedparser.parse(url, request_headers={"User-Agent": UA})
            for e in feed.entries:
                title = getattr(e, "title", "")
                link = getattr(e, "link", "")
                if not title or not link:
                    continue
                desc = re.sub(r"<[^>]*>", " ", getattr(e, "summary", ""))[:320]
                date = None
                if getattr(e, "published_parsed", None):
                    date = datetime.datetime(*e.published_parsed[:6]).strftime("%Y-%m-%d")
                jobs.append(enrich({
                    "title": title.strip(),
                    "url": link.strip(),
                    "description": re.sub(r"\s+", " ", desc).strip(),
                    "date": date,
                    "source": name,
                    "company": getattr(e, "author", ""),
                }, cat))
        except Exception as ex:
            print(f"  ! RSS {name} failed: {ex}", file=sys.stderr)
    return jobs


def scrape_greenhouse():
    jobs = []
    for name, slug, cat in GREENHOUSE_BOARDS:
        try:
            print(f"  Greenhouse: {name}")
            data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            for j in data.get("jobs", []):
                loc = (j.get("location") or {}).get("name", "")
                jobs.append(enrich({
                    "title": j.get("title", "").strip(),
                    "url": j.get("absolute_url", f"https://boards.greenhouse.io/{slug}/jobs/{j.get('id')}"),
                    "description": loc,
                    "date": iso_date(j.get("updated_at")),
                    "source": name,
                    "company": name,
                }, cat))
        except Exception as ex:
            print(f"  ! Greenhouse {name} failed: {ex}", file=sys.stderr)
    return jobs


def scrape_lever():
    jobs = []
    for name, slug, cat in LEVER_BOARDS:
        try:
            print(f"  Lever: {name}")
            data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            for j in data:
                cats = j.get("categories", {}) or {}
                desc = " · ".join([x for x in [cats.get("location"), cats.get("team"), cats.get("commitment")] if x])
                jobs.append(enrich({
                    "title": j.get("text", "").strip(),
                    "url": j.get("hostedUrl", ""),
                    "description": desc,
                    "date": iso_date(j.get("createdAt")),
                    "source": name,
                    "company": name,
                }, cat))
        except Exception as ex:
            print(f"  ! Lever {name} failed: {ex}", file=sys.stderr)
    return jobs


def main():
    print("Scraping job sources…")
    all_jobs = []
    all_jobs += scrape_jobspy_all()
    all_jobs += scrape_rss()
    all_jobs += scrape_greenhouse()
    all_jobs += scrape_lever()

    # Deduplicate by URL and drop excluded titles
    seen = set()
    deduped = []
    for j in all_jobs:
        u = j.get("url", "")
        title = (j.get("title", "") or "").lower()
        if any(term in title for term in EXCLUDE_TITLE_TERMS):
            continue
        if u and u not in seen:
            seen.add(u)
            deduped.append(j)

    output = {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(deduped),
        "jobs": deduped,
    }
    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)

    print(f"\nDone. Wrote {len(deduped)} jobs to jobs.json")


if __name__ == "__main__":
    main()
