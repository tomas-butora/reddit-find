"""Backend router for post/comment fetching.

Two backends exist:

  arctic  (default) -- Arctic Shift, a free public Reddit mirror. No key, no account,
          ~15 min behind live. See arctic.py. Server-side search is unavailable there,
          so keyword search is done locally over a pulled subreddit.

  reddit  -- the original oauth.reddit.com path, kept in fetch_reddit_oauth.py. Reddit
          closed self-service OAuth registration in 2026, so this only works if you
          hold approved credentials. Opt in with REDDIT_FIND_BACKEND=reddit.

Everything below just dispatches. The dict shapes returned are identical either way, so
cli.py and the markdown rendering did not change.
"""

import os

_BACKEND = os.getenv("REDDIT_FIND_BACKEND", "arctic").strip().lower()

if _BACKEND == "reddit":
    from .fetch_reddit_oauth import (  # noqa: F401
        fetch_post_comments,
        fetch_single_post,
        fetch_subreddit_posts,
        search_posts,
    )
else:
    from .arctic import (  # noqa: F401
        fetch_post_comments,
        fetch_single_post,
        fetch_subreddit_posts,
        search_posts,
    )

# _parse_post_ref stays here: arctic.py imports it to parse Reddit URLs, and it is
# backend-agnostic string handling.
from .fetch_reddit_oauth import _parse_post_ref  # noqa: E402,F401


def active_backend() -> str:
    return "reddit-oauth" if _BACKEND == "reddit" else "arctic-shift"
