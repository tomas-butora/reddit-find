"""Reddit OAuth2 — token fetch + cache.

Reddit killed anonymous .json access (403 platform-wide). All requests now go
through oauth.reddit.com with a bearer token. Credentials come from .env:

    REDDIT_CLIENT_ID=...        # required (from reddit.com/prefs/apps, "script" app)
    REDDIT_CLIENT_SECRET=...    # required
    REDDIT_USERNAME=...         # optional — enables password grant (100 QPM)
    REDDIT_PASSWORD=...         # optional

With only id+secret we use the application-only (client_credentials) grant,
which reads public subreddits/search fine. Add username+password for the
higher-rate password grant.
"""

import os
import time
from typing import Optional

import requests

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

# Reddit requires a unique, descriptive User-Agent: <platform>:<appid>:<version> (by /u/<user>)
_username = os.environ.get("REDDIT_USERNAME", "script")
USER_AGENT = f"python:gtm-find:2.0 (by /u/{_username})"

# Module-level token cache
_token: Optional[str] = None
_token_expiry: float = 0.0


class RedditAuthError(RuntimeError):
    """Raised when Reddit credentials are missing or the token request fails."""


class RedditBlockedError(RuntimeError):
    """Raised when Reddit returns 403 even with a valid token (IP/app blocked)."""


def is_configured() -> bool:
    return bool(os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"))


def _setup_hint() -> str:
    return (
        "Reddit auth is not configured. Reddit blocks anonymous access (403), so a "
        "one-time OAuth app is required:\n"
        "  1. Create a 'script' app at https://www.reddit.com/prefs/apps\n"
        "  2. Add to your repo-root .env:\n"
        "       REDDIT_CLIENT_ID=<the ~14-char id under the app name>\n"
        "       REDDIT_CLIENT_SECRET=<the secret>\n"
        "     (optional, for higher rate limits: REDDIT_USERNAME + REDDIT_PASSWORD)"
    )


def get_token(force: bool = False) -> str:
    """Return a cached bearer token, fetching a new one if needed.

    Raises RedditAuthError if credentials are missing or the grant fails.
    """
    global _token, _token_expiry

    if not force and _token and time.time() < _token_expiry:
        return _token

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RedditAuthError(_setup_hint())

    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")

    if username and password:
        data = {"grant_type": "password", "username": username, "password": password}
    else:
        data = {"grant_type": "client_credentials"}

    try:
        resp = requests.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            data=data,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
    except requests.RequestException as e:
        raise RedditAuthError(f"Could not reach Reddit token endpoint: {e}")

    if resp.status_code == 401:
        raise RedditAuthError(
            "Reddit rejected the client_id/secret (401). Double-check the values in .env "
            "and that the app type is 'script'."
        )
    if resp.status_code != 200:
        raise RedditAuthError(
            f"Token request failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RedditAuthError(f"No access_token in Reddit response: {payload}")

    _token = token
    # Refresh a minute before actual expiry (Reddit tokens last ~1h)
    _token_expiry = time.time() + payload.get("expires_in", 3600) - 60
    return token
