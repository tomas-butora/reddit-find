---
name: reddit-find
when_to_use: When the user says reddit research, buyer voice, voice of customer, pain phrases, buyer language, what are people saying about, competitor sentiment, or reddit-find.
last_reviewed: 2026-09-08
description: GTM research from Reddit. Three commands: `search` (keyword search across Reddit history — use when researching specific pain like "MCA debt" or "cold email is dead"), `fetch` (top/hot posts from known subs — use for broad ICP landscape), `post` (deep dive single thread). Two-pass workflow: Pass 1 scan titles fast (--titles-only), Pass 2 deep-dive with `post`. Built-in recency filter. Pre-built GTM subreddit clusters. No API key required (Arctic Shift backend). `-s <subreddit>` is required, there is no global search.
---

# reddit-find

> ✅ **STATUS (2026-09-06): working again, free, no API key.** Reddit's own API stayed shut
> (anonymous `.json` blocked, self-service OAuth registration closed behind manual approval), so the
> backend was switched to **Arctic Shift**, a public Reddit mirror. No key, no account, ~15 min
> behind live, history back to 2005. Two behaviour changes, both real:
>
> - **`--min-score` is now opt-in precision, off by default.** Arctic Shift captures posts before
>   they have votes and backfills only some: across 600 r/sales posts over 90 days, **16% carry a
>   real score and 84% sit at 1**. A score that IS there is trustworthy, so `--min-score 50` returns
>   genuinely popular threads (17 of those 600) — it just cannot see the other 84%. Use it when you
>   want confirmed winners; leave it off for coverage. Default ranking is the **live comment count**,
>   which is always accurate (a post storing `num_comments=1` returned 65 real comments).
> - **`search` needs `-s <subreddit>`.** Server-side full-text search times out on this backend, so
>   matching is done locally over a pulled subreddit. There is no all-of-Reddit firehose to filter,
>   so global search is gone. Run `discover` first if you don't know the subs.
>
> To fall back to the old Reddit path (needs approved OAuth credentials): `REDDIT_FIND_BACKEND=reddit`.

Pure data fetcher for Reddit GTM research. Three commands cover the full research workflow: `search` for targeted keyword mining, `fetch` for broad subreddit scanning, `post` for deep thread dives. Claude in session handles analysis — no Anthropic API key required.

## Install

```bash
pip install git+https://github.com/tomas-butora/reddit-find.git
```

Python 3.9+. Do not use plain `pip install reddit-find`: that is the old PyPI release on the dead Reddit API.

No required API keys. Optional for richer subreddit discovery:
```bash
export SERPER_API_KEY="your_serper_key"    # serper.dev (2,500 free searches/month)
```

## Commands

### `search` — Keyword search across Reddit history

Use when you know the pain phrase. Matches keywords against title + selftext.

> ⛔ **Two things that surprise people on this backend. Both bite.**
>
> **1. It is an AND-of-terms match, not a phrase match.** The query is split on spaces and every
> term must appear somewhere in title or body. `"cold email is dead"` needs the literal words
> `is` and `dead` too, and returns **0**; `"cold email"` returns **35** on the same sub and window.
> **Use 2-3 content words, never a sentence.** A zero result is usually the query, not the market.
>
> **2. It does NOT search all history.** It pulls the most recent **1,500 posts per sub** inside the
> age window and matches locally. On a busy sub like r/sales that is roughly the last two weeks —
> `--max-age-days 3650` returned nothing older than 12 days. So `--max-age-days` can only ever
> *narrow* that window, never widen it past 1,500 posts. For genuinely old threads, search a
> smaller/slower sub where 1,500 posts spans years.

```bash
# Targeted EDP mining — finds posts wherever they exist historically
reddit-find search "merchant cash advance" -s smallbusiness --titles-only -o /tmp/scan.md
reddit-find search "MCA debt payments" -s smallbusiness -s Entrepreneur --max-age-days 730
reddit-find search "cold email is dead" -s sales --sort top --limit 50 --titles-only
```

> ⛔ Every example needs `-s`. There is no global search on this backend — matching runs locally
> over a pulled subreddit. Run `discover` first if you do not know the subs.

**Options:**
```
--subreddit / -s     REQUIRED. Scope to subreddits (multiple OK). No global search exists.
--max-age-days N     Filter posts older than N days (default: 1825 / 5yr — search mines history)
--min-score N        Minimum upvote score (default: 1, off). Raise to 50 for popular-only.
--limit N            Posts to fetch per subreddit (default: 50)
--sort               relevance | top | new | comments (default: relevance)
--titles-only        Skip comments — just titles, scores, dates, URLs
--output / -o        Save output to file
```

**When to use search vs fetch:**
- `search` — you have a specific pain phrase or keyword to mine ("merchant cash advance debt", "SDR quota missed"). Finds historical posts by relevance.
- `fetch` — you want to see what's trending in a sub right now (hot + top posts). Good for broad ICP landscape.

### `fetch` — Hot/top posts from known subs

```bash
# Pass 1: titles-only scan (fast, decide what to deep-dive)
reddit-find fetch "<topic>" -s <sub> --titles-only --max-age-days 365 -o /tmp/scan.md

# Pass 2 prep: full fetch with comments on top threads
reddit-find fetch "<topic>" -s <sub> --max-age-days 365 --min-score 50 --top-threads 3 -o /tmp/full.md
```

**Options:**
```
--subreddit / -s     Target specific subreddits (multiple OK, skips discovery)
--max-age-days N     Filter posts older than N days (default: 365)
--titles-only        Skip comments — just titles, scores, dates, URLs
--min-score N        Minimum upvote score (default: 1, off). Raise to 50 for popular-only.
--top-threads N      Top threads to fetch per sub (default: 8)
--posts-per-sub N    Posts to fetch per sub before filtering (default: 20)
--output / -o        Save output to file
```

### `post` — Single-post deep dive

```bash
reddit-find post https://reddit.com/r/sales/comments/1abc23/title/ -o /tmp/post.md
reddit-find post 1abc23 --sub sales -o /tmp/post.md
```

Fetches the full thread: post body + all comments (up to 50). Use after a titles scan to deep-dive high-signal posts.

### `discover` — Find subreddits

```bash
reddit-find discover "b2b cold email" --top 8
```

```
--top N              Subreddits to return (default: 8)
--serper-key TEXT    SerperDev key (env: SERPER_API_KEY). Optional, widens discovery.
```

Run this before `search` whenever the subs are not obvious and the cluster table below has no row
for the topic.

---

## Output Format

Titles scan (Pass 1) — a table, one row per post:
```markdown
| Score | Comments | Date | Title | URL |
|-------|----------|------|-------|-----|
| 1 | 84 | 2026-03-15 | "Cold email is dead..." | https://... |
```
Score is usually 1 and means nothing. **Sort your read by the Comments column.**

Full fetch / `post` (Pass 2):
```markdown
## [342 pts] "Title of post here"
r/sales | 45 comments | https://reddit.com/...
Post: {selftext}

Top comments:
- [89 pts] u/author: comment text
```

---

## Recency Guidance

Always filter by recency. Stale pain points produce stale copy.

| Scenario | Flag |
|----------|------|
| Default GTM research | `--max-age-days 365` |
| "Recent trends" / "what's happening now" | `--max-age-days 90` |
| "This week" / "latest" | `--max-age-days 7` |

**Never skip recency filtering for GTM research.**

---

## Standard Workflow (Two-Pass + Optional Search)

### Option A: Targeted EDP mining (use `search`)

When you have a specific pain phrase — "merchant cash advance", "SDR burnout", "churn rate" — use `search` so you find posts from across Reddit's history, not just current hot.

```bash
# Pass 1 — keyword scan
reddit-find search "<pain phrase>" -s <sub1> -s <sub2> --titles-only --max-age-days 730 -o /tmp/scan.md

# Pass 2 — deep dive on selected posts
reddit-find post <url-from-scan> -o /tmp/post-1.md
reddit-find post <url-from-scan> -o /tmp/post-2.md
```

### Option B: Broad ICP landscape (use `fetch`)

When you want to see what's trending in a subreddit right now — no specific search term.

```bash
# Pass 1 — hot/top titles scan
reddit-find fetch "<topic>" -s <sub1> -s <sub2> --titles-only --max-age-days 365 -o /tmp/scan.md

# Pass 2 — deep dive on selected posts
reddit-find post <url-from-scan> -o /tmp/post-1.md
reddit-find post <url-from-scan> -o /tmp/post-2.md
```

### Scoring guide (Pass 1)

Read the scan output and score each post.

**Rank on comments, not score.** Arctic Shift leaves 84% of posts at score 1, so a score
threshold silently deletes most of the corpus. Comment count is always accurate.

- **HIGH**: >30 comments AND the title signals buyer pain / frustration / comparison / venting.
  A 3-upvote post with 80 comments is a dogpile of shared pain — that is the best thread on the
  page, not the worst.
- **BONUS**: a real score >50 when one is present. Trust it when it is there; never require it.
- **SKIP**: memes, humour, off-topic, obvious self-promotion. **Never skip on score alone.**

**Why two passes:** Comment fetching is slow (2s sleep per post). On a 5-sub scan with 8 threads each, fetching all comments takes 80+ seconds. Titles scan takes 5-10 seconds. Read first, fetch deep only what matters.

---

## Pre-Built GTM Subreddit Clusters

Use these instead of running `discover` for common research topics.

| Research Topic | Primary Subs | Secondary Subs |
|---|---|---|
| B2B cold outreach / SDR pain | `sales`, `b2bmarketing`, `sdr` | `b2b_sales`, `SaaSSales`, `Entrepreneur` |
| Cold email specifically | `sales`, `emailmarketing`, `b2bmarketing` | `sdr`, `growthHacking` |
| SaaS churn / customer success | `CustomerSuccess`, `SaaS` | `startups`, `saasmarketing` |
| SaaS growth / pipeline generation | `SaaS`, `saasmarketing`, `startups` | `Entrepreneur`, `sales` |
| LinkedIn outreach / social selling | `sales`, `LinkedInTips`, `b2bmarketing` | `linkedin`, `sdr` |
| Marketing ops / RevOps | `marketing`, `b2bmarketing`, `salesforce` | `hubspot`, `RevOps` |
| Founder / early-stage GTM | `startups`, `Entrepreneur`, `SaaS` | `smallbusiness`, `growthhacking` |
| Agency / consulting pain | `consulting`, `marketing`, `freelance` | `agency`, `Entrepreneur` |
| Recruiting / hiring signal | `recruiting`, `humanresources` | `jobs`, `cscareerquestions` |
| Product-led growth / PLG | `SaaS`, `ProductManagement` | `saasmarketing`, `startups` |
| Data / analytics buyers | `datascience`, `analytics`, `BusinessIntelligence` | `dataengineering`, `SQL` |
| Fintech / finance buyers | `fintech`, `personalfinance` | `investing`, `smallbusiness` |
| E-commerce / DTC pain | `ecommerce`, `Entrepreneur` | `shopify`, `digitalnomad` |
| HR tech / people ops | `humanresources`, `hrtechnology` | `recruiting`, `PeopleAnalytics` |
| IT / security buyers | `sysadmin`, `netsec`, `ITManagers` | `cybersecurity`, `devops` |
| Developer tools | `programming`, `devops`, `webdev` | `ExperiencedDevs`, `SoftwareEngineering` |

---

## The 7 GTM Use Cases

Each one is a worked pattern, not a synonym for "do research". Pick the motion first, then the command.

### 1. Cold email hook mining
The exact words prospects use become subject lines and opening lines.
```bash
reddit-find search "outbound is dead" -s sales -s sdr --titles-only -o scan.md
```
Extract: pain phrases for subjects, objections to preempt in the body, trigger events.
A comment reading `"I've sent 5,000 cold emails this quarter and booked 3 meetings"` is the hook —
the email opens with that number, not with our product.

### 2. ICP pain point discovery
New vertical, no priors. Find the real problems before guessing.
```bash
reddit-find fetch "HR software frustration" -s humanresources -s hrtechnology --max-age-days 365 -o pain.md
```
Extract: pains ranked by comment volume, job titles posting, what they already tried and rejected,
what "good enough" means to them.

### 3. Competitor intelligence
What users say when they are not on a sales call.
```bash
reddit-find search "Clay vs Apollo" -s sales -s b2bmarketing --titles-only -o scan.md
```
Extract: feature gaps they actually care about, pricing objections, switching triggers, and the
moment someone starts looking for an alternative. Feeds displacement angles.

### 4. Content angle discovery
Threads with outsized engagement are validated angles with proof of demand attached.
```bash
reddit-find fetch "LinkedIn outreach" -s sales -s LinkedInTips --titles-only -o content.md
```
These are ready-made post topics.

### 5. Offer validation
Before building an offer, check the market wants it.
```bash
reddit-find search "fractional CMO" -s marketing -s startups -s Entrepreneur --titles-only -o scan.md
```
"I wish someone would just..." and "why does nobody offer..." are signal. Crickets or negative
sentiment saves months.

### 6. Voice of customer for messaging
```bash
reddit-find fetch "CRM is a nightmare" -s sales -s salesforce -s hubspot -o voice.md
```
Verbatim phrases, metaphors and complaints, used directly in copy, landing pages and decks.

### 7. Signal detection for outbound timing
Reddit surfaces buying signals in the open: tool migrations, team expansion, funding-driven hiring.
Short windows only — this one is worthless at 365 days.
```bash
reddit-find fetch "switching from HubSpot" -s salesforce -s sales --max-age-days 30 -o signals.md
reddit-find fetch "just raised series A" -s startups --titles-only --max-age-days 7 -o funding.md
```

---

## Claude's Job After Fetching

After reading the output from `fetch` (full) or `post`:

1. **Pain Points** — what are people actually struggling with? Quote verbatim with score attribution.
2. **Buyer Language** — exact phrases ready for cold email subject lines and hooks. Format: `"[exact phrase]"`
3. **Viral Moments** — threads with outsized engagement relative to sub size. Why did it hit?
4. **ICP Archetypes** — who's posting? Their role, situation, what they're trying to solve.
5. **Tool & Competitor Mentions** — what comes up, and what's the sentiment?
6. **Content Angles** — 5 specific post ideas derived from actual thread language.

---

## When to Use

| Situation | Command |
|-----------|---------|
| You have a specific pain phrase to mine | `search "<phrase>" -s <sub> --titles-only` then `post` |
| New ICP — find pain and buyer language | `search "<ICP problem>" -s <sub> --titles-only` then `post` |
| Broad ICP landscape / what's trending | `fetch "<topic>" -s <sub> --titles-only` then `post` |
| Cold email hooks for a specific market | `search "<ICP problem>" --sort top --titles-only` then `post` |
| Content batch for a new topic | `fetch "<topic>" -s <sub> --titles-only` then `post` high-signal |
| Researching a competitor | `search "<competitor name>" -s <relevant_sub>` |
| Validating a new offer angle | `search "<offer premise>" --titles-only` |
| Voice of market for playbook research | Full `fetch`, 3-5 subs, `--max-age-days 365` |

---

## Example: Targeted EDP Mining (search-first)

```bash
# Pass 1 — keyword scan for specific pain phrase
reddit-find search "merchant cash advance" -s smallbusiness -s Entrepreneur \
  --titles-only --max-age-days 730 -o /tmp/scan.md

# Claude reads scan.md, marks HIGH-signal posts

# Pass 2 — deep dive on 2-3 selected posts
reddit-find post https://reddit.com/r/smallbusiness/comments/1abc23/ -o /tmp/post-1.md
reddit-find post https://reddit.com/r/Entrepreneur/comments/1xyz99/ -o /tmp/post-2.md

# Claude reads post-1.md and post-2.md and extracts full GTM intel
```

## Example: Broad ICP Landscape (fetch-first)

```bash
# Pass 1 — scan hot/top across core GTM subs
reddit-find fetch "b2b cold email" -s sales -s b2bmarketing -s sdr \
  --titles-only --max-age-days 365 -o /tmp/scan.md

# Pass 2 — deep dive on 2-3 selected posts
reddit-find post https://reddit.com/r/sales/comments/1abc23/ -o /tmp/post-1.md
reddit-find post https://reddit.com/r/sales/comments/1xyz99/ -o /tmp/post-2.md
```

---

## Reading a Zero (exit codes)

The tool now distinguishes the two zeros, because they mean opposite things:

| Exit | Meaning | What to conclude |
|---|---|---|
| **0** | results returned | proceed |
| **1** | real zero — the backend answered, nothing matched | usually the query. Retry with 2-3 content words before concluding the market is quiet. |
| **2** | **BACKEND FAILURE** — rate limited, blocked, or unreachable | **nothing.** Prints a banner saying so. Never report this as "no discussion found". Retry in a few minutes. |

Requests are paced by a shared budget that persists across runs
(`~/.reddit-find/ratelimit.json`), default 300/min, override with `--max-per-minute` or
`REDDIT_FIND_MAX_PER_MINUTE`. 429s and 5xx retry with exponential backoff and jitter.
Every run prints what it spent. A typical titles scan is ~50 requests / ~33s.

---

## If Arctic Shift Goes Down

Arctic Shift is a free volunteer mirror with no SLA. Reddit's own API is not a fallback:
it returned 403 to anonymous and OAuth requests as of 2026-09-08, and self-service app
registration is closed.

If `reddit-find` errors or returns nothing on a query you know should hit:

1. Confirm it is the backend, not a filter. Re-run with `--min-score 1 --max-age-days 3650`.
2. Check the mirror is up: `curl -s "https://arctic-shift.photon-reddit.com/api/subreddits/search?subreddit=sales&limit=1"`
3. Paid fallback is Apify `trudax/reddit-scraper-lite` at roughly $3.40 per 1k results. It
   cannot combine a keyword with a subreddit, which is this tool's main pattern, so expect
   to filter locally.

---

## Cost

No API costs. Arctic Shift is free and unauthenticated. SerperDev optional, free tier covers 2,500 searches/month.
