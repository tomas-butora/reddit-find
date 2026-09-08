"""Arctic Shift backend — free, unauthenticated Reddit data.

Reddit closed anonymous .json access in 2026 and gated new OAuth registration behind
manual approval, which killed the original oauth.reddit.com backend in fetch.py.

Arctic Shift (https://arctic-shift.photon-reddit.com) is a public mirror that ingests
Reddit continuously and serves it back with no key and no account. Measured 2026-09-06:
newest posts were 13-15 minutes behind live, and it returns Reddit's NATIVE field names
(created_utc, selftext, permalink, num_comments), so the parsing here is the same shape
fetch.py always produced.

TWO LIMITATIONS, both measured 2026-09-06:

1. SCORE IS UNRELIABLE AS A FILTER. Arctic Shift captures a post ~15 min after
   creation, before it has votes. Some posts get re-crawled later and backfilled;
   most never do. Measured across 400 r/sales posts on 2026-09-06:

       age      n    median score   max
       <6h      13        1           1     never backfilled
       6-24h    22        1           1     never backfilled
       1-3d     87        1         267     a few backfilled
       3-7d    248        1         236     a few backfilled
       >7d      30        1           8     a few backfilled

   The median is 1 at EVERY age. So a real 267-point thread and a dead one both read
   1 most of the time, and `--min-score 5` would discard almost everything including
   the best threads. min_score is therefore ignored on this backend rather than
   silently returning nothing.

   The signal that IS reliable is the live comment count, which the comments endpoint
   serves current (a post storing num_comments=1 returned 65 real comments).
   `enrich_engagement()` fetches that, and ranking uses it by default.

   min_score is still honoured when set above 1, as an OPT-IN PRECISION FILTER: a score
   that IS present is trustworthy, so `--min-score 50` returns genuinely popular threads.
   It just cannot see the rest. Measured over 600 r/sales posts across 90 days:

       have a real score (>1)    96   (16%)
       stuck at 1               504   (84%)
       score >= 20               31
       score >= 50               17
       score >= 100              10

   So use it when you want confirmed winners and can accept missing things; leave it off
   (the default) when you want coverage and are ranking on comments instead.

2. Server-side full-text search always times out ("Timeout. Maybe slow
down a bit", HTTP 422), even over a one-week window. Their search index is too expensive
to serve for free. So `search_posts` pulls the subreddit and filters locally instead.

That is not a downgrade. It matches the rule the rest of this repo already follows: pull
once, filter locally, never re-query for a slice you can derive from what is on disk.
Once a subreddit is pulled, any number of phrases can be mined from it for free.

Rate limit is roughly 120k requests/hour, so pagination is cheap. Be polite anyway.

Caveat worth knowing: Arctic Shift is a free community project with no SLA. If it goes
away, the fallback is a paid backend (Apify trudax/reddit-scraper-lite, ~$3.40/1k results).
"""

import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from .errors import BackendUnavailableError, RedditBlockedError, RedditRateLimitError
from .ratelimit import get_limiter

BASE_URL = "https://arctic-shift.photon-reddit.com/api"
TIMEOUT = 45
PAGE_SIZE = 100          # max the API reliably returns per call
# Pacing now lives in ratelimit.RateLimiter, which every _get() call goes through.
# POLITE_DELAY is kept only so old callers importing it do not break; the limiter
# is the single place that decides spacing.
POLITE_DELAY = 0.0
MAX_RETRIES = 4          # attempts on a 429 before giving up
BACKOFF_BASE = 1.5       # seconds; doubles each retry, plus jitter


class ArcticShiftError(RuntimeError):
    """Arctic Shift returned an error or could not be reached."""


def _get(path: str, params: Dict) -> List[Dict]:
    """GET an Arctic Shift endpoint and return the `data` array.

    Every request is paced by the shared cross-run limiter, and a 429 is retried
    with exponential backoff plus jitter rather than failing the run. Anything
    that is still a failure after that is raised as a typed error, never as an
    empty list — a broken mirror must not read as a quiet market.
    """
    limiter = get_limiter()
    delay = BACKOFF_BASE

    for attempt in range(1, MAX_RETRIES + 1):
        limiter.acquire()
        try:
            resp = requests.get(f"{BASE_URL}/{path}", params=params, timeout=TIMEOUT)
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise BackendUnavailableError(
                    f"could not reach Arctic Shift after {MAX_RETRIES} attempts: {exc}"
                ) from exc
            time.sleep(delay + random.uniform(0, delay / 2))
            delay *= 2
            continue

        if resp.status_code == 429:
            if attempt == MAX_RETRIES:
                raise RedditRateLimitError(
                    f"Arctic Shift is still rate limiting after {MAX_RETRIES} attempts. "
                    "Wait a few minutes, or lower --max-per-minute."
                )
            time.sleep(delay + random.uniform(0, delay / 2))
            delay *= 2
            continue

        if resp.status_code == 403:
            raise RedditBlockedError(
                "Arctic Shift returned 403 (blocked). This is the backend refusing us, "
                "not an empty result."
            )

        if resp.status_code >= 500:
            if attempt == MAX_RETRIES:
                raise BackendUnavailableError(
                    f"Arctic Shift returned HTTP {resp.status_code} after {MAX_RETRIES} attempts."
                )
            time.sleep(delay + random.uniform(0, delay / 2))
            delay *= 2
            continue

        try:
            payload = resp.json()
        except ValueError:
            raise BackendUnavailableError(
                f"Arctic Shift returned a non-JSON response (HTTP {resp.status_code})."
            )

        if payload.get("error"):
            raise ArcticShiftError(str(payload["error"]))

        return payload.get("data") or []

    raise BackendUnavailableError("Arctic Shift request failed with no response.")


def _normalise_post(p: Dict, fallback_sub: str = "") -> Dict:
    """Map an Arctic Shift post onto the dict shape the CLI already renders."""
    return {
        "id": p.get("id", ""),
        "title": p.get("title", ""),
        "score": p.get("score", 0) or 0,
        "upvote_ratio": p.get("upvote_ratio", 0) or 0,
        "num_comments": p.get("num_comments", 0) or 0,
        "author": p.get("author") or "[deleted]",
        "url": f"https://reddit.com{p.get('permalink', '')}",
        "selftext": (p.get("selftext") or "")[:600],
        "subreddit": p.get("subreddit") or fallback_sub,
        "created_utc": p.get("created_utc", 0) or 0,
        "flair": p.get("link_flair_text") or "",
    }


def _normalise_comment(c: Dict) -> Dict:
    return {
        "author": c.get("author") or "[deleted]",
        "score": c.get("score", 0) or 0,
        "body": (c.get("body") or "").strip(),
        "created_utc": c.get("created_utc", 0) or 0,
    }


def _cutoff(max_age_days: Optional[int]) -> Optional[float]:
    if max_age_days is None:
        return None
    return datetime.now(timezone.utc).timestamp() - max_age_days * 86400


def fetch_subreddit_posts(
    subreddit: str,
    sort: str = "hot",
    limit: int = 25,
    time_filter: str = "month",
    max_age_days: Optional[int] = None,
    min_score: int = 0,
) -> List[Dict]:
    """Posts from one subreddit, newest first, then re-sorted by score.

    `sort` and `time_filter` are accepted for signature compatibility with the old
    Reddit backend. Arctic Shift serves chronologically; ranking happens locally, so
    "hot" and "top" both resolve to "highest score inside the requested window".
    """
    # over-pull so ranking has something to choose from, since stored scores are useless
    rows = _pull_posts(subreddit, want=max(limit * 3, 60), cutoff_ts=_cutoff(max_age_days))
    posts = [_normalise_post(p, subreddit) for p in rows]
    if min_score > 1:
        posts = [p for p in posts if p["score"] >= min_score]
    posts = enrich_engagement(posts, max_posts=min(len(posts), 60))
    return sorted(posts, key=lambda x: (x["num_comments"], x["score"]), reverse=True)[:limit]


def _pull_posts(
    subreddit: str,
    want: int,
    cutoff_ts: Optional[float] = None,
    hard_cap: int = 5000,
) -> List[Dict]:
    """Page backwards through a subreddit until `want` rows, the cutoff, or the cap."""
    collected: List[Dict] = []
    before: Optional[str] = None
    seen = set()

    while len(collected) < want and len(collected) < hard_cap:
        params: Dict = {
            "subreddit": subreddit,
            "limit": min(PAGE_SIZE, want - len(collected) if want < hard_cap else PAGE_SIZE),
            "sort": "desc",
        }
        if before:
            params["before"] = before

        batch = _get("posts/search", params)
        if not batch:
            break

        oldest = None
        for p in batch:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            created = p.get("created_utc", 0) or 0
            oldest = created if oldest is None else min(oldest, created)
            if cutoff_ts is not None and created < cutoff_ts:
                continue
            collected.append(p)

        # stop once the page itself has fallen past the cutoff
        if cutoff_ts is not None and oldest is not None and oldest < cutoff_ts:
            break
        if len(batch) < params["limit"]:
            break

        before = datetime.fromtimestamp(oldest, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return collected


def enrich_engagement(posts: List[Dict], max_posts: int = 40) -> List[Dict]:
    """Replace the frozen num_comments with the real, live count.

    Costs one request per post, so it is capped. Posts beyond the cap keep their stored
    value and are marked engagement_checked=False so callers can tell the difference.
    """
    for i, post in enumerate(posts):
        if i >= max_posts or not post.get("id"):
            post["engagement_checked"] = False
            continue
        try:
            rows = _get("comments/search", {"link_id": post["id"], "limit": PAGE_SIZE})
        except ArcticShiftError:
            post["engagement_checked"] = False
            continue
        real = [c for c in rows if (c.get("body") or "").strip() not in ("", "[deleted]", "[removed]")]
        post["num_comments"] = len(real)
        post["engagement_checked"] = True
    return posts


def fetch_post_comments(subreddit: str, post_id: str, limit: int = 25) -> List[Dict]:
    """Top comments on one post, highest score first."""
    rows = _get("comments/search", {"link_id": post_id, "limit": min(limit * 3, PAGE_SIZE)})
    comments = [_normalise_comment(c) for c in rows]
    comments = [c for c in comments if c["body"] and c["body"] not in ("[deleted]", "[removed]")]
    return sorted(comments, key=lambda x: x["score"], reverse=True)[:limit]


def fetch_single_post(post_url_or_id: str, subreddit: Optional[str] = None) -> Optional[Dict]:
    """One post by full URL or bare id."""
    from .fetch import _parse_post_ref  # reuse the existing URL parser

    sub, post_id = _parse_post_ref(post_url_or_id, subreddit)
    if not post_id:
        return None

    rows = _get("posts/ids", {"ids": post_id})
    if not rows:
        return None

    post = _normalise_post(rows[0], sub or "")
    # the CLI's `post` command expects the full body, not the 600-char preview
    post["selftext"] = (rows[0].get("selftext") or "").strip()
    created = post.get("created_utc") or 0
    post["post_date"] = (
        datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%d") if created else "unknown"
    )

    # ...and a `comments` list, which is what the old backend attached here
    raw = _get("comments/search", {"link_id": post_id, "limit": PAGE_SIZE})
    comments = []
    for c in raw:
        body = (c.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        comments.append(
            {
                "author": c.get("author") or "[deleted]",
                "score": c.get("score", 0) or 0,
                "body": body[:1200],
            }
        )
    post["comments"] = sorted(comments, key=lambda x: x["score"], reverse=True)[:50]
    post["num_comments"] = len(comments)
    return post


def search_posts(
    query: str,
    subreddits: Optional[List[str]] = None,
    limit: int = 25,
    sort: str = "relevance",
    max_age_days: Optional[int] = 365,
    min_score: int = 5,
    scan_depth: int = 1500,
) -> List[Dict]:
    """Keyword search, done locally.

    Arctic Shift's server-side full-text search times out, so this pulls up to
    `scan_depth` posts per subreddit inside the age window and matches the query against
    title + selftext here. Every term must appear (AND), case-insensitive.

    A global search with no `subreddits` is not possible on this backend: there is no
    all-of-Reddit firehose to filter. Pass at least one subreddit, or run `discover`
    first to find them.
    """
    if not subreddits:
        raise ArcticShiftError(
            "this backend cannot search all of Reddit at once. Pass -s <subreddit> "
            "(repeatable), or run `reddit-find discover \"<topic>\"` to find subs first."
        )

    terms = [t for t in query.lower().split() if t]
    cutoff_ts = _cutoff(max_age_days)
    hits: List[Dict] = []

    for sub in subreddits:
        rows = _pull_posts(sub, want=scan_depth, cutoff_ts=cutoff_ts, hard_cap=scan_depth)
        for p in rows:
            haystack = f"{p.get('title', '')} {p.get('selftext', '')}".lower()
            if not all(t in haystack for t in terms):
                continue
            post = _normalise_post(p, sub)
            # min_score is opt-in precision: it keeps only posts with a CONFIRMED score,
            # which is ~16% of the pool. See limitation 1 at the top of this file.
            if min_score > 1 and post["score"] < min_score:
                continue
            hits.append(post)

    if sort == "new":
        hits.sort(key=lambda x: x["created_utc"], reverse=True)
    else:
        # relevance, top and comments all rank on real engagement, since score is frozen
        hits = enrich_engagement(hits, max_posts=min(len(hits), 60))
        hits.sort(key=lambda x: (x["num_comments"], x["score"]), reverse=True)

    return hits[:limit]
