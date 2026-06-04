# The Brief — Roadmap

A prioritized plan for evolving the tool from a solid aggregator into a true
matcher that pulls its weight. Phases are ordered by leverage: the things near
the top do the most to improve match quality and day-to-day usefulness.

Each item notes its **value**, rough **effort**, and any **tradeoff** worth
knowing before committing to it.

---

## Where the tool stands today

What it does well:
- Pulls from JobSpy (Indeed, Google, LinkedIn, Glassdoor, ZipRecruiter), niche
  RSS boards, and company ATS boards — refreshed automatically every morning.
- Filters by freshness, category, employment type, location, and keyword.
- Ranks by a keyword + category + remote scoring system.
- Excludes unwanted roles (grant writing, sales, etc.) at the source.

The honest gap: relevance is decided by **keyword counting**, not by
understanding the role. The tool aggregates and filters well; it doesn't yet
*judge fit*. That's what Phase 1 is about.

> **Update — built since this roadmap was written:** AI relevance scoring (1.1),
> Save/Applied/Dismiss tracking (1.2), the one-click pitch generator (3.1), the
> rate calculator, the shared `profile.json`, and the command-center hub are all
> live. The next reopened work is backend-side (salary extraction, then the
> email digest) plus the voice-notes distillation. See the marked items below.

---

## Phase 1 — Better matches (highest leverage)

### 1.1 AI relevance scoring  ★ top priority
**Value: very high. Effort: medium. Tradeoff: small cost + an API key.**

Have the scraper send each listing, plus a short profile of you, to an LLM and
get back a fit score (0–100) and a one-line reason ("Strong fit — health
content strategy, remote, contract"). The dashboard then sorts and filters by
real fit rather than keyword hits.

- Why it matters: this is the single biggest jump in match quality. It catches
  great roles that don't happen to contain your keywords, and demotes
  keyword-matching roles that aren't actually a fit.
- How: add a scoring step in `scraper.py` that calls the Anthropic API with your
  profile + each job; store `fit_score` and `fit_reason` in jobs.json. The
  dashboard gets a "minimum fit" slider and shows the reason on each card.
- Cost: scoring ~200 listings/day with a small model is a few cents per day.
  The API key lives as a private GitHub secret (never in the code).

### 1.2 Save / Applied / Dismiss tracking
**Value: high. Effort: low–medium. Tradeoff: per-device memory.**

Three actions on each card: save (shortlist), mark applied, dismiss (hide for
good). Dismissed roles never reappear; applied roles move to their own view.

- Why it matters: turns repeated refreshes from "the same wall of jobs" into a
  managed pipeline. You stop re-reading roles you've already judged.
- How: store these in the browser's localStorage. Simple and instant.
- Tradeoff: localStorage is per-device, so your saves live on the computer you
  use. If you want them synced across devices, that's a later enhancement.

### 1.3 "New since last visit"
**Value: medium–high. Effort: low.**

Quietly tag listings that appeared since you last opened the dashboard, with a
"New" badge and an optional "new only" toggle.

- Why it matters: you instantly see what changed instead of re-scanning.
- How: record the timestamp of each visit in localStorage; compare against each
  listing's first-seen date.

---

## Phase 2 — Make it come to you (automation)

### 2.1 Morning email digest
**Value: high. Effort: medium. Tradeoff: needs an email service + secret.**

After each scrape, email you the top new matches (say, the 10 highest fit
scores you haven't already seen). Turns the tool from pull to push.

- Why it matters: the "agent that works while you sleep" experience. You don't
  have to remember to check — the best matches land in your inbox.
- How: add a step to the GitHub Action that sends the digest. Pairs naturally
  with 1.1 (rank by fit) and 1.3 (only what's new).

### 2.2 Expand and harden sources
**Value: medium. Effort: low per source.**

- Add more company ATS boards from your Notion CSV (Greenhouse / Lever / Ashby
  / Workable) — especially healthcare and content shops.
- Add a documented "run it locally" path for LinkedIn, which gets blocked far
  less from a home connection than from GitHub's servers.
- Periodically prune sources that consistently return nothing.

---

## Phase 3 — Application leverage

### 3.1 One-click tailored pitch
**Value: high (plays to your strengths). Effort: medium.**

On any saved role, generate a first-draft intro pitch — drawing on your real
background (GE HealthCare, HCA, plain-language and health-literacy work) and the
specific role. You edit from a strong start rather than a blank page.

- Why it matters: you're a writer; the bottleneck isn't finding roles, it's the
  volume of tailored outreach. This compresses that.
- How: a button that sends your profile + the listing to the API and returns a
  draft you can copy.

### 3.2 Salary / rate extraction + filter  ★ next backend priority
**Value: high. Effort: medium. Tradeoff: only works where pay is stated.**

Pull pay from listings, surface it on each card, filter by a minimum, and — the
key part — feed it into the AI fit score so pay and fit stop being independent.
The motivating case: an 85-fit full-time role at $70k is a *no*, not an 85, and
the score should reflect that.

- **Extraction:** JobSpy returns structured salary fields (min/max/period) for
  some sources; capture those directly, and lightly parse "$X–$Y" patterns from
  the description for the rest. Store in `jobs.json`.
- **Use in scoring:** pass `rate_floor` (contract/hourly) and a separate
  full-time salary floor into the scoring prompt so under-paying roles are
  demoted rather than floating to the top on fit alone.
- **Apples to apples:** contract roles quote hourly/per-project, full-time roles
  quote salary — compare each against the right floor. Ties into the rate
  calculator, which already knows the hourly floor.
- **Honest limit:** many freelance/contract posts omit pay. This is a *filter
  where data exists* feature — show pay loudly when present, mark "not stated"
  otherwise, and never silently hide the unstated ones. Do salary extraction
  *before* the email digest, since the digest is far more useful leading with
  "88-fit role at $120k" than with fit alone.

### 3.4 Voice-notes distillation (from real emails)
**Value: high for pitch quality. Effort: low. Tradeoff: gather examples first.**

Sharpen how the pitch generator sounds by distilling 3–5 real outreach emails
that led to interviews or closed deals into a tighter `voice_notes` field (and
possibly lightly anonymized sample snippets in the prompt for the model to
pattern-match against).

- Why it matters: the current voice notes are a general self-description; real
  "emails that landed" are the ground truth for how you write when it works.
- **Privacy:** keep raw originals *out* of the committed files. Distill into
  `voice_notes` (a summary) rather than pasting full emails into
  `pitch-generator.html`, which would be publicly visible in the repo. Scrub
  client names/specifics regardless.
- How: gather a few examples with a one-line note on what each achieved; distill
  the patterns (openers, rhythm, warmth vs. directness, the ask, sign-off) into
  the shared profile. Improves the pitch tool — and, since every tool reads
  `profile.json`, nudges the scorer and matching too.

### 3.5 Negative-keyword controls in the dashboard
**Value: medium. Effort: low.**

Move the exclusion list out of the code and into the sidebar, so you can add a
term to mute (e.g. a role type you keep seeing) without editing `scraper.py`.

---

## Phase 4 — Polish and insight

### 4.1 Source performance view
Which sources produce your highest-fit matches and your applications, so you can
focus the scraper where it actually pays off.

### 4.2 Install on your phone (PWA)
Make the dashboard installable as an app icon for quick mobile checks.

### 4.3 Saved searches / profiles
Switch between lenses — e.g. "health content strategy" vs "UX writing" — without
re-tuning filters each time.

---

## Captured ideas — scorer & outreach (logged with reasoning, not scheduled)

These came from a brainstorming pass. Read and pressure-tested; kept here with
the verdict attached so the reasoning isn't lost.

### C.1 Sourcing audit in the Assignment Scorer  ★ high value, scope carefully
**Verdict: worth doing — but as "sourcing hygiene," NOT fact-checking.**

Reframe away from "is this claim true" (LLMs do this confidently and
unreliably; a false "all clear" on health content is worse than no check). Keep
it to what's reliable and genuinely reduces misinformation risk:
- flag claims that need a source but have none;
- check that every link resolves and points where it claims;
- spot statistics/quotes stated without attribution;
- catch vague hedges ("studies show") with no citation.
Depends on the link-extraction fixes landing first. Plays to health-literacy
expertise without the tool pretending to adjudicate medical truth.

### C.2 Export options in the Assignment Scorer
**Verdict: clean, safe, build anytime. Low effort.**

Two distinct needs, both client-side (no backend):
- export the **scorecard** (PDF to share/keep, or Markdown) — for feedback or a
  record;
- export the **edited draft** (plain text/Markdown) — the polished version after
  working from the feedback.
Offer both formats; only real decision is PDF (sharing) vs Markdown (reuse).

### C.3 Talent-pool / cold-pitch targets in the system
**Verdict: viable, but as a curated list + pitch — not automated discovery.**

A lot of freelance work is won by getting on a roster *before* a role is posted.
But "companies quietly building rosters" isn't a feed you can scrape — that
intelligence is yours (industry knowledge, the agency CSV, past clients). So the
real feature is a **target list you maintain** of companies worth pitching cold,
which the pitch generator drafts general-interest intros for (close cousin of
its existing "paste a role" path). Overlaps with the client/project tracker —
design them together.

### C.4 Junk / spam filtering
**Verdict: parked — solution waiting for a problem. Do NOT build yet.**

No spam problem observed so far, which is the key signal. Curated boards + ATS
APIs + JobSpy's mainstream sites are low-junk, and fit scoring already sinks
noise as a side effect. Can't filter a pattern you haven't seen. If a recurring
junk pattern emerges (a bad source, a scam-y listing type), add a targeted
exclusion then — a five-minute rule, not a speculative system.

---

## Someday / maybe (parked, not planned)

- **Productize the toolbox.** If the itch ever returns, the two paths that fit
  best are (a) a one-time **template / kit** sold to other freelancers who set
  it up themselves (bring-your-own API key) — lowest effort, ~$49–149, and (b)
  a **done-for-you setup service** that leans on strategy strengths rather than
  running infrastructure — ~$500–1,500 per setup. The niche angle (healthcare /
  medical content freelancers specifically) is the real edge. A managed
  subscription SaaS is deliberately *not* on this list — it would mean becoming
  a support-and-infrastructure operation, which isn't the point. Revisit only if
  genuinely curious; personal use needs none of it.

---

## Suggested order

1. **AI relevance scoring (1.1)** — biggest jump in match quality.
2. **Save / Applied / Dismiss (1.2)** — makes daily use actually manageable.
3. **Morning email digest (2.1)** — so the best matches find you.
4. Everything else as appetite and time allow.

If we do only the first two, the tool stops being a list you sift and starts
being a shortlist that understands what you're looking for. That's the line
worth crossing first.
