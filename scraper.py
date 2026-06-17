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

# Titles containing any of these phrases are dropped at the source — roles
# you will never want regardless of company or fit score.
EXCLUDE_TITLE_TERMS = [
    # grant / fundraising
    "grant writer", "grant writing", "grants writer",
    # clinical / medical / nursing
    "physician", "doctor", "nurse", "nursing", "surgeon", "surgery",
    "pharmacist", "pharmacy", "radiolog", "patholog", "anesthes",
    "medical assistant", "clinical assistant", "dental assistant",
    "physical therapist", "occupational therapist", "speech therapist",
    "sonographer", "ultrasound tech", "lab technician", "lab tech",
    "medical technologist", "phlebotom", "sterile processing",
    "clinical trial", "clinical research coordinator", "clinical data",
    "medical director", "chief medical", "chief nursing",
    "home health aide", "home health", "direct support",
    "patient care", "patient services", "care coordinator",
    "medical billing", "medical coder", "medical coding",
    "front office", "front desk", "medical receptionist",
    "vet tech", "veterinary tech", "veterinarian",
    # software / engineering
    "software engineer", "software developer", "frontend engineer",
    "backend engineer", "fullstack engineer", "full stack engineer",
    "data engineer", "data scientist", "machine learning engineer",
    "devops", "site reliability", "platform engineer",
    "mobile engineer", "ios developer", "android developer",
    "qa engineer", "quality assurance engineer", "test engineer",
    # administrative / ops
    "administrative assistant", "executive assistant", "office manager",
    "operations manager", "operations coordinator", "program coordinator",
    "facilities manager", "warehouse", "driver", "delivery driver",
    "stockroom", "supply chain",
    # hr / finance / legal
    "compensation analyst", "recruiter", "talent acquisition",
    "human resources", "hr generalist", "hr business partner",
    "payroll", "accounts payable", "accounts receivable",
    "financial analyst", "accountant", "controller",
    "paralegal", "attorney", "legal counsel",
    # sales
    "account executive", "sales representative", "sales manager",
    "business development", "account manager",
]

# For ATS boards (company-specific), we require the title to contain at least
# one writing/content signal before keeping the listing — otherwise a pharma
# company's physician and lab tech roles flood the feed.
WRITING_TITLE_REQUIRED_SOURCES = {
    # all Greenhouse, Lever, Ashby, Jobvite, Breezy company boards
    # populated dynamically from the board lists below
}

_WRITING_TITLE_PATTERN = re.compile(
    r"\b(writer|writing|copywriter|editor|editorial|content|communications|"
    r"journalist|reporter|strategist|copywriting|publicist|pr\b|brand voice|"
    r"technical writer|ux writer|creative director|creative lead|storytell)\b",
    re.IGNORECASE
)

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
    ("We Work Remotely — Contract",  "https://weworkremotely.com/categories/remote-contract-jobs.rss",      "writing"),
    ("Jobicy — Content",             "https://jobicy.com/?feed=job_feed&search_keywords=content+writer",    "writing"),
    ("Jobicy — Marketing",           "https://jobicy.com/?feed=job_feed&search_keywords=marketing",         "marketing"),
    ("Jobicy — Copywriter",          "https://jobicy.com/?feed=job_feed&search_keywords=copywriter",        "writing"),
    ("Jobicy — Editor",              "https://jobicy.com/?feed=job_feed&search_keywords=editor",            "writing"),
    ("Jobicy — Healthcare",          "https://jobicy.com/?feed=job_feed&search_keywords=healthcare",        "writing"),
    ("Jobicy — Communications",      "https://jobicy.com/?feed=job_feed&search_keywords=communications",    "marketing"),
    ("RemoteOK — Writing",           "https://remoteok.com/remote-writing-jobs.rss",                        "writing"),
    ("RemoteOK — Marketing",         "https://remoteok.com/remote-marketing-jobs.rss",                      "marketing"),
    ("RemoteOK — Content",           "https://remoteok.com/remote-content-writing-jobs.rss",                "writing"),
    ("JournalismJobs",               "https://www.journalismjobs.com/rss",                                  "journalism"),
    ("Working Nomads — Writing",     "https://www.workingnomads.com/jobsrss?category=writing",              "writing"),
    ("Working Nomads — Marketing",   "https://www.workingnomads.com/jobsrss?category=marketing",            "marketing"),
]

# Company boards on Greenhouse (use the slug from boards.greenhouse.io/SLUG).
GREENHOUSE_BOARDS = [
    # ── existing ──────────────────────────────────────────────────────
    ("RVO Health (freelance)", "rvohcontentfreelance", "writing"),
    ("Axios",                  "axios",                "journalism"),
    ("Grist",                  "grist",                "journalism"),
    ("The Arena Group",        "thearenagroup",        "writing"),
    ("The Daily Beast",        "thedailybeast31",      "journalism"),
    ("VSA Partners",           "vsapartners",          "writing"),
    # ── discovered via OpenJobData ────────────────────────────────────
    ("Axsome Therapeutics",    "axsometherapeutics",   "writing"),
    ("Accanto Health",         "accantohealth858accanto858", "writing"),
    ("Boulder Care",           "bouldercare",          "writing"),
    ("ClinChoice",             "clinchoice",           "writing"),
    ("Omnicom Health",         "omnicomhealth",        "writing"),
    ("Real Chemistry",         "realchemistry",        "writing"),
    ("Recursion Pharma",       "recursionpharmaceuticals", "writing"),
    ("Spring Health",          "springhealth66",       "writing"),
    ("Lotte Biologics USA",    "lottebiologicsusallc", "writing"),
    ("Human Rights Watch",     "humanrightswatch",     "writing"),
    ("Guidepoint",             "guidepoint",           "writing"),
    ("The New York Times",     "thenewyorktimes",      "journalism"),
    ("Forbes",                 "forbes",               "journalism"),
    ("WPP Media",              "wppmedia",             "writing"),
    ("Landor",                 "landor",               "writing"),
    ("Critical Mass",          "criticalmass",         "writing"),
    ("RAPP",                   "rapp",                 "writing"),
    ("Tenneo",                 "teneolinkedin",        "writing"),
]

# Company boards on Lever (use the slug from jobs.lever.co/SLUG).
LEVER_BOARDS = [
    # ── existing ──────────────────────────────────────────────────────
    ("Solutions Journalism", "solutionsjournalism", "journalism"),
    ("MissionWired",         "MissionWired",        "writing"),
    ("Bisnow",               "bisnow",              "journalism"),
    ("Modern Age",           "modern-age",          "writing"),
    ("Artera",               "artera",              "writing"),
    # ── discovered via OpenJobData ────────────────────────────────────
    ("Avalere Health",       "avalerehealth",       "writing"),
    ("Brafton",              "brafton",             "writing"),
    ("The Athletic",         "theathletic",         "journalism"),
    ("Sunshine Sachs",       "sunshinesachs",       "writing"),
    ("Sierra Club",          "sierraclub",          "writing"),
    ("Digital Media Mgmt",   "digitalmediamanagement", "writing"),
    ("Afar Media",           "AfarMedia",           "journalism"),
]

# Company boards on Ashby (use the slug from jobs.ashbyhq.com/SLUG).
ASHBY_BOARDS = [
    ("Fira Health",          "fira-health",         "writing"),
    ("Mytomorrows",          "mytomorrows",         "writing"),
    ("Rowan",                "rowan",               "writing"),
    ("Quorum",               "quorum",              "writing"),
    ("Scribe",               "scribe",              "writing"),
    ("Payscale",             "payscale",            "writing"),
    ("Notion",               "notion",              "writing"),
]

# Company boards on Jobvite (RSS feed per company).
# URL pattern: https://jobs.jobvite.com/{slug}/jobs/feed
JOBVITE_BOARDS = [
    ("Ornge",                "ornge",               "writing"),
    ("System C",             "system-c",            "writing"),
    ("USANA Health",         "usana",               "writing"),
    ("Tyler Technologies",   "tylertech",           "writing"),
]

# Company boards on Breezy HR (JSON endpoint per company).
BREEZY_BOARDS = [
    ("Gastro Health",        "gastro-health",       "writing"),
    ("Highlights Healthcare","highlights-healthcare","writing"),
    ("Kaniksu Community",    "kaniksu-community-health", "writing"),
    ("Cardahealth",          "cardahealth",         "writing"),
    ("Allcares",             "allcares",            "writing"),
    ("Vetsez",               "vetsez",              "writing"),
]

# ─── AI RELEVANCE SCORING ───────────────────────────────────────────────────
# Each listing is scored 0–100 for fit against the profile below, with a short
# reason. Scoring is skipped automatically if no API key is present, so the
# scraper still works without it.
#
# The API key is read from the ANTHROPIC_API_KEY environment variable — set it
# as a GitHub repository secret (see SETUP, "Turning on AI scoring"). Never put
# the key directly in this file.

ENABLE_AI_SCORING = True

# Model used for scoring. Haiku is fast and cheap — ideal for high volume.
SCORING_MODEL = "claude-haiku-4-5-20251001"

# Your profile — this is the fallback used for scoring if profile.json is
# missing. Normally the scraper reads profile.json (the shared file every tool
# uses), so you only have to describe yourself in one place.
PROFILE = """
Freelance healthcare communications writer, editor, and content strategist with
15+ years of experience. Specialties: translating clinical complexity into
plain, accessible language; health literacy; content strategy; writing for both
lay/patient audiences and executive/clinical (HCP) audiences. Past clients
include GE HealthCare, HCA Healthcare, Mass General, Beth Israel Lahey.
Open to: freelance, contract, and part-time. Also open to UX writing / content
design and technical writing in health contexts.
Strong preference for REMOTE; hybrid is acceptable.
Not interested in: grant writing, full-time in-office roles, sales, recruiting.
"""


def load_profile():
    """Build the scoring profile from profile.json (shared across all tools).
    Falls back to the inline PROFILE above if the file is missing."""
    try:
        with open("profile.json", encoding="utf-8") as f:
            p = json.load(f)
    except Exception:
        return PROFILE.strip()
    parts = []
    if p.get("headline"):
        exp = f" with {p['years_experience']} years of experience" if p.get("years_experience") else ""
        parts.append(p["headline"] + exp + ".")
    if p.get("specialties"):
        parts.append("Specialties: " + "; ".join(p["specialties"]) + ".")
    if p.get("clients"):
        parts.append("Past clients include " + ", ".join(p["clients"]) + ".")
    if p.get("open_to"):
        parts.append("Open to: " + ", ".join(p["open_to"]) + ".")
    if p.get("location_preference"):
        parts.append(p["location_preference"])
    if p.get("not_interested_in"):
        parts.append("Not interested in: " + ", ".join(p["not_interested_in"]) + ".")
    return "\n".join(parts) if parts else PROFILE.strip()

# Only send the top N candidates (by keyword/category pre-score) to the AI, to
# control cost. Set to 0 to score everything.
MAX_TO_SCORE = 120

# How many jobs to score per API call (batched to save cost/time).
SCORE_BATCH_SIZE = 10

# ─── EMAIL DIGEST ────────────────────────────────────────────────────────────
# Sends a morning digest of top new matches after each scrape.
# Requires two GitHub secrets: DIGEST_EMAIL_ADDRESS and DIGEST_APP_PASSWORD.
# See SETUP.md "Turning on the email digest" for setup instructions.
#
# DIGEST_EMAIL_ADDRESS — your Gmail address (sender and recipient)
# DIGEST_APP_PASSWORD  — a Gmail App Password (not your regular password)
#                        Create at: myaccount.google.com/apppasswords

ENABLE_DIGEST = True

# Only include listings at or above this fit score.
DIGEST_MIN_FIT = 70

# Maximum listings to include in one digest.
DIGEST_MAX_LISTINGS = 10

# Tracks which URLs have already been sent — prevents duplicates.
# This file is committed back to the repo by the Action.
SEEN_URLS_FILE = "seen_urls.json"

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
    # If no structured pay was injected (RSS/ATS sources), try parsing description
    if not job.get("pay_display"):
        pay = extract_salary_description(job.get("description", ""))
        job.update(pay)
    return job


def extract_salary_structured(row):
    """Pull salary from JobSpy's structured fields (most reliable source)."""
    try:
        mn = row.get("min_amount")
        mx = row.get("max_amount")
        interval = str(row.get("interval") or "").lower()
        currency = str(row.get("currency") or "USD").upper()
        if mn is None and mx is None:
            return {}
        mn = float(mn) if mn is not None else None
        mx = float(mx) if mx is not None else None
        # Normalize interval to our standard terms
        period = "annual"
        if "hour" in interval:
            period = "hourly"
        elif "month" in interval:
            period = "annual"
            if mn: mn *= 12
            if mx: mx *= 12
        elif "week" in interval:
            period = "annual"
            if mn: mn *= 52
            if mx: mx *= 52
        elif "contract" in interval or "project" in interval:
            period = "project"
        sym = "$" if currency == "USD" else currency + " "
        def fmt(v): return sym + f"{v:,.0f}"
        if mn and mx and abs(mx - mn) > 1:
            display = f"{fmt(mn)}–{fmt(mx)}/{period[:2]}"
        elif mx:
            display = f"Up to {fmt(mx)}/{period[:2]}"
        elif mn:
            display = f"{fmt(mn)}+/{period[:2]}"
        else:
            display = ""
        return {
            "pay_min": int(mn) if mn else None,
            "pay_max": int(mx) if mx else None,
            "pay_period": period,
            "pay_display": display,
        }
    except Exception:
        return {}


# Salary regex patterns for description parsing
_PAY_PATTERNS = [
    # $X,XXX – $X,XXX per hour / hourly / /hr / /h
    (r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:–|-|to)\s*\$\s*([\d,]+(?:\.\d+)?)\s*(?:per\s*hour|/\s*h(?:our|r)?|hourly)", "hourly"),
    # $XXX,XXX – $XXX,XXX (annually / per year / salary)
    (r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:–|-|to)\s*\$\s*([\d,]+(?:\.\d+)?)\s*(?:per\s*year|annually|/\s*year|/\s*yr|salary)?", "annual"),
    # $XX/hr or $XX/hour (single number)
    (r"\$\s*([\d,]+(?:\.\d+)?)\s*/\s*h(?:our|r)?", "hourly"),
    # Rate: $X.XX per word
    (r"\$\s*([\d.]+)\s*(?:per|/)\s*word", "per_word"),
]

def extract_salary_description(text):
    """Parse salary from listing description text — used for RSS and ATS sources."""
    if not text:
        return {}
    for pattern, period in _PAY_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        try:
            def clean(s): return float(s.replace(",", ""))
            if period == "per_word":
                rate = clean(m.group(1))
                return {"pay_min": None, "pay_max": None,
                        "pay_period": "per_word",
                        "pay_display": f"${rate:.2f}/word"}
            mn = clean(m.group(1))
            mx = clean(m.group(2)) if len(m.groups()) >= 2 else None
            # Sanity check: hourly rates should be < 1000; annual > 10000
            if period == "hourly" and mn > 1000:
                continue
            if period == "annual" and mn < 10000:
                # Probably hourly expressed as a flat number — skip
                continue
            sym = "$"
            def fmt(v): return sym + f"{v:,.0f}"
            if mx and mx > mn:
                display = f"{fmt(mn)}–{fmt(mx)}/{'hr' if period == 'hourly' else 'yr'}"
            else:
                display = f"{fmt(mn)}+/{'hr' if period == 'hourly' else 'yr'}"
            return {
                "pay_min": int(mn),
                "pay_max": int(mx) if mx else None,
                "pay_period": period,
                "pay_display": display,
            }
        except Exception:
            continue
    return {}


def pay_summary(job):
    """Return a short pay string for the AI scoring prompt, or empty string."""
    d = job.get("pay_display", "")
    p = job.get("pay_period", "")
    if d:
        return f"Pay: {d}"
    return ""


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
                pay = extract_salary_structured(row)
                job = enrich({
                    "title": title.strip(),
                    "url": url.strip(),
                    "description": (loc + " · " + desc).strip(" ·"),
                    "date": iso_date(row.get("date_posted")),
                    "source": site or "JobSpy",
                    "company": company.strip(),
                    **pay,
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


def scrape_ashby():
    """Ashby has the same clean JSON pattern as Greenhouse."""
    jobs = []
    for name, slug, cat in ASHBY_BOARDS:
        try:
            print(f"  Ashby: {name}")
            data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
            for j in data.get("jobPostings", []):
                comp = j.get("compensationTiers") or []
                pay = {}
                if comp:
                    tier = comp[0]
                    pay_min = tier.get("minValue")
                    pay_max = tier.get("maxValue")
                    interval = str(tier.get("interval") or "").lower()
                    period = "hourly" if "hour" in interval else "annual"
                    if pay_min or pay_max:
                        sym = "$"
                        def fmt(v): return sym + f"{v:,.0f}"
                        sfx = "hr" if period == "hourly" else "yr"
                        if pay_min and pay_max:
                            display = f"{fmt(pay_min)}–{fmt(pay_max)}/{sfx}"
                        elif pay_max:
                            display = f"Up to {fmt(pay_max)}/{sfx}"
                        else:
                            display = f"{fmt(pay_min)}+/{sfx}"
                        pay = {"pay_min": int(pay_min or 0) or None,
                               "pay_max": int(pay_max or 0) or None,
                               "pay_period": period, "pay_display": display}
                loc = j.get("location") or j.get("locationName") or ""
                jobs.append(enrich({
                    "title": j.get("title", "").strip(),
                    "url": j.get("jobUrl", f"https://jobs.ashbyhq.com/{slug}/{j.get('id','')}"),
                    "description": loc,
                    "date": iso_date(j.get("publishedAt") or j.get("updatedAt")),
                    "source": name,
                    "company": name,
                    **pay,
                }, cat))
        except Exception as ex:
            print(f"  ! Ashby {name} failed: {ex}", file=sys.stderr)
    return jobs


def scrape_jobvite_boards():
    """Jobvite exposes an RSS feed per company — works with feedparser."""
    jobs = []
    try:
        import feedparser
    except ImportError:
        print("  ! feedparser not installed — skipping Jobvite boards", file=sys.stderr)
        return jobs
    for name, slug, cat in JOBVITE_BOARDS:
        try:
            print(f"  Jobvite: {name}")
            url = f"https://jobs.jobvite.com/{slug}/jobs/feed"
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
                    "company": name,
                }, cat))
        except Exception as ex:
            print(f"  ! Jobvite {name} failed: {ex}", file=sys.stderr)
    return jobs


def scrape_breezy():
    """Breezy HR exposes a simple JSON endpoint per company."""
    jobs = []
    for name, slug, cat in BREEZY_BOARDS:
        try:
            print(f"  Breezy HR: {name}")
            data = fetch_json(f"https://{slug}.breezy.hr/json")
            for j in data:
                loc = (j.get("location") or {}).get("name", "")
                jobs.append(enrich({
                    "title": j.get("name", "").strip(),
                    "url": j.get("url", f"https://{slug}.breezy.hr/p/{j.get('id','')}"),
                    "description": loc,
                    "date": iso_date(j.get("published_date") or j.get("updated_date")),
                    "source": name,
                    "company": name,
                }, cat))
        except Exception as ex:
            print(f"  ! Breezy {name} failed: {ex}", file=sys.stderr)
    return jobs


def _prescore(job):
    """Cheap heuristic to pick which jobs are worth sending to the AI."""
    s = 0
    if job.get("category") in ("writing", "marketing"):
        s += 5
    elif job.get("category") == "journalism":
        s += 2
    if "remote" in job.get("locations", []):
        s += 3
    elif "hybrid" in job.get("locations", []):
        s += 1
    if "freelance" in job.get("types", []) or "contract" in job.get("types", []):
        s += 2
    return s


def score_jobs_with_ai(jobs):
    """Add fit_score (0-100) and fit_reason to each job. Degrades gracefully:
    if the key is missing or the API errors, jobs are returned unscored."""
    import os
    if not ENABLE_AI_SCORING:
        return jobs
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("  ! ANTHROPIC_API_KEY not set — skipping AI scoring", file=sys.stderr)
        return jobs

    try:
        import anthropic
    except ImportError:
        print("  ! anthropic package not installed — skipping AI scoring", file=sys.stderr)
        return jobs

    client = anthropic.Anthropic(api_key=api_key)
    profile_text = load_profile()

    # Pick the most promising candidates to score (cost control)
    ranked = sorted(jobs, key=_prescore, reverse=True)
    to_score = ranked if MAX_TO_SCORE == 0 else ranked[:MAX_TO_SCORE]
    print(f"  Scoring {len(to_score)} of {len(jobs)} listings with {SCORING_MODEL}…")

    by_id = {id(j): j for j in jobs}
    scored_count = 0

    # Load floors from profile for salary-aware scoring
    try:
        with open("profile.json", encoding="utf-8") as f:
            _prof = json.load(f)
        rate_floor = float(_prof.get("rate_floor") or 0)
        salary_floor = float(_prof.get("salary_floor") or 0)
    except Exception:
        rate_floor = 0
        salary_floor = 0

    floor_note = ""
    if rate_floor:
        floor_note += f"Hourly/contract floor: ${rate_floor:,.0f}/hr. "
    if salary_floor:
        floor_note += f"Full-time salary floor: ${salary_floor:,.0f}/yr. "
    if floor_note:
        floor_note = "PAY FLOORS: " + floor_note + \
            "Roles with stated pay BELOW these floors should be penalized " \
            "10–20 points regardless of content fit. Roles with no stated pay " \
            "should NOT be penalized."

    for i in range(0, len(to_score), SCORE_BATCH_SIZE):
        batch = to_score[i:i + SCORE_BATCH_SIZE]
        listing_lines = []
        for n, j in enumerate(batch):
            desc = (j.get("description", "") or "")[:300]
            pay_line = pay_summary(j)
            listing_lines.append(
                f'{n}. TITLE: {j.get("title","")}\n'
                f'   COMPANY: {j.get("company","")}\n'
                + (f'   {pay_line}\n' if pay_line else '') +
                f'   DETAILS: {desc}'
            )
        listings = "\n\n".join(listing_lines)

        prompt = (
            "You are screening freelance/contract job listings for a specific "
            "person. Score each listing 0–100 for how well it fits their "
            "profile, where 100 is a perfect fit and 0 is irrelevant.\n\n"
            f"PROFILE:\n{profile_text}\n\n"
            "Scoring guidance: reward health/medical content, content strategy, "
            "plain-language/health-literacy, and remote freelance/contract work. "
            "Penalize full-time in-office, sales, grant writing, and roles "
            "outside writing/content/communications. A generic non-health "
            "writing role is a mild fit (~40-55); a strong health-content match "
            "is 80+.\n\n"
            + (f"{floor_note}\n\n" if floor_note else "") +
            f"LISTINGS:\n{listings}\n\n"
            "Respond with ONLY a JSON array, one object per listing, in order, "
            'like: [{"i":0,"score":82,"reason":"six-word reason"}]. '
            "The reason must be at most 8 words. No prose, no markdown, JSON only."
        )

        try:
            msg = client.messages.create(
                model=SCORING_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
            results = json.loads(text)
            for r in results:
                idx = r.get("i")
                if idx is None or idx >= len(batch):
                    continue
                job = batch[idx]
                job["fit_score"] = max(0, min(100, int(r.get("score", 0))))
                job["fit_reason"] = str(r.get("reason", ""))[:80]
                scored_count += 1
        except Exception as e:
            print(f"  ! scoring batch {i//SCORE_BATCH_SIZE} failed: {e}", file=sys.stderr)

    print(f"  AI scored {scored_count} listings")
    return jobs


def load_seen_urls():
    """Load the set of URLs already sent in previous digests."""
    try:
        with open(SEEN_URLS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Prune entries older than 30 days to keep the file lean
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        return {url: date for url, date in data.items() if date >= cutoff}
    except Exception:
        return {}


def save_seen_urls(seen):
    """Write the updated seen-URLs map back to disk."""
    try:
        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=1)
    except Exception as e:
        print(f"  ! Could not save seen_urls.json: {e}", file=sys.stderr)


def build_digest_html(listings, date_str):
    """Compose a clean HTML email from the top listings."""
    rows = ""
    for j in listings:
        score = j.get("fit_score", "")
        reason = j.get("fit_reason", "")
        pay = j.get("pay_display", "")
        company = j.get("company", "")
        source = j.get("source", "")
        url = j.get("url", "#")
        title = j.get("title", "Untitled")
        meta_parts = [p for p in [company, source, pay] if p]
        meta = " · ".join(meta_parts)
        score_color = "#3B6D11" if score and score >= 85 else "#C9A84C" if score and score >= 70 else "#8A8780"
        rows += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #EDE8DF;vertical-align:top;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
              <div>
                <a href="{url}" style="font-family:Georgia,serif;font-size:16px;font-weight:400;color:#2C2B29;text-decoration:none;line-height:1.3;">{title}</a>
                <div style="font-size:11px;color:#8A8780;font-family:monospace;margin-top:4px;letter-spacing:0.04em;">{meta}</div>
                {f'<div style="font-size:12px;color:#4A4845;margin-top:5px;font-style:italic;">{reason}</div>' if reason else ''}
              </div>
              {f'<span style="font-family:monospace;font-size:11px;color:{score_color};background:{"#EAF3DE" if score and score >= 85 else "#F5EDD6" if score and score >= 70 else "#EDE8DF"};padding:3px 9px;border-radius:99px;white-space:nowrap;flex-shrink:0;">{score} fit</span>' if score else ''}
            </div>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#FAF8F5;font-family:'Helvetica Neue',Arial,sans-serif;font-weight:300;">
  <div style="max-width:600px;margin:0 auto;padding:40px 24px;">
    <div style="margin-bottom:28px;">
      <div style="font-family:monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin-bottom:8px;">The Brief · Morning Digest</div>
      <div style="font-family:Georgia,serif;font-size:28px;font-weight:400;color:#2C2B29;line-height:1.1;">Your top matches, {date_str}.</div>
      <div style="font-size:13px;color:#8A8780;margin-top:8px;">{len(listings)} role{'s' if len(listings)!=1 else ''} scored {DIGEST_MIN_FIT}+ · ranked by AI fit</div>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #2C2B29;">
      {rows}
    </table>
    <div style="margin-top:28px;padding-top:16px;border-top:1px solid #EDE8DF;">
      <a href="https://msholman.github.io/The-Brief/index.html"
         style="display:inline-block;background:#2C2B29;color:#FAF8F5;font-family:monospace;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;padding:10px 20px;border-radius:4px;text-decoration:none;">
        Open The Brief →
      </a>
      <div style="font-size:10px;color:#8A8780;margin-top:12px;letter-spacing:0.06em;">
        Sent by The Brief · taylaholman.com
      </div>
    </div>
  </div>
</body></html>"""


def send_digest(jobs, seen_urls):
    """Build and send the email digest. Returns updated seen_urls dict."""
    import os
    if not ENABLE_DIGEST:
        return seen_urls
    email_addr = os.environ.get("DIGEST_EMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("DIGEST_APP_PASSWORD", "").strip()
    if not email_addr or not app_password:
        print("  ! DIGEST_EMAIL_ADDRESS or DIGEST_APP_PASSWORD not set — skipping digest",
              file=sys.stderr)
        return seen_urls

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")

    # Filter: scored above threshold, posted in last 3 days, not already sent
    candidates = [
        j for j in jobs
        if j.get("fit_score") and j.get("fit_score") >= DIGEST_MIN_FIT
        and j.get("date", "") >= cutoff
        and j.get("url") not in seen_urls
    ]
    # Sort by fit score descending, cap at max
    candidates.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
    to_send = candidates[:DIGEST_MAX_LISTINGS]

    if not to_send:
        print("  Digest: no new listings above threshold today — skipping send.")
        return seen_urls

    print(f"  Sending digest with {len(to_send)} listings to {email_addr}…")
    date_str = datetime.datetime.utcnow().strftime("%B %-d")
    html = build_digest_html(to_send, date_str)

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"The Brief · {len(to_send)} new match{'es' if len(to_send)!=1 else ''} · {date_str}"
        msg["From"] = f"The Brief <{email_addr}>"
        msg["To"] = email_addr
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(email_addr, app_password)
            smtp.sendmail(email_addr, email_addr, msg.as_string())
        print(f"  ✓ Digest sent.")
        # Mark these URLs as seen
        for j in to_send:
            if j.get("url"):
                seen_urls[j["url"]] = today
    except Exception as e:
        print(f"  ! Digest send failed: {e}", file=sys.stderr)

    return seen_urls


def main():
    print("Scraping job sources…")
    all_jobs = []
    all_jobs += scrape_jobspy_all()
    all_jobs += scrape_rss()
    all_jobs += scrape_greenhouse()
    all_jobs += scrape_lever()
    all_jobs += scrape_ashby()
    all_jobs += scrape_jobvite_boards()
    all_jobs += scrape_breezy()

    # Build the set of company-board source names that must have a writing title
    board_sources = set()
    for name, _, _ in GREENHOUSE_BOARDS + LEVER_BOARDS + ASHBY_BOARDS + JOBVITE_BOARDS + BREEZY_BOARDS:
        board_sources.add(name)

    # Deduplicate by URL, drop excluded titles, and enforce writing-title
    # requirement for company-specific boards
    seen = set()
    deduped = []
    for j in all_jobs:
        u = j.get("url", "")
        title = (j.get("title", "") or "").lower()
        # hard exclusions — never want these regardless of source
        if any(term in title for term in EXCLUDE_TITLE_TERMS):
            continue
        # company boards must show a writing/content signal in the title
        if j.get("source") in board_sources and not _WRITING_TITLE_PATTERN.search(j.get("title", "")):
            continue
        if u and u not in seen:
            seen.add(u)
            deduped.append(j)

    # AI relevance scoring (skipped automatically if no API key)
    deduped = score_jobs_with_ai(deduped)

    # Email digest (skipped if secrets not set)
    seen_urls = load_seen_urls()
    seen_urls = send_digest(deduped, seen_urls)
    save_seen_urls(seen_urls)

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
