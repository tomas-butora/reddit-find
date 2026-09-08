"""Typed errors for the Arctic Shift request path.

These exist so the CLI can tell a hard failure (mirror down, rate limited,
blocked) apart from a genuinely empty result. They must never be swallowed and
rendered as "No posts found" — a broken backend and a quiet market look
identical to the reader otherwise, and that misreads as market evidence.
"""


class RedditBlockedError(RuntimeError):
    """Raised when the backend refuses this client (HTTP 403 / block page)."""


class RedditRateLimitError(RuntimeError):
    """Raised when 429s persist after exhausting backoff retries."""


class BackendUnavailableError(RuntimeError):
    """Raised when the mirror is unreachable or returns a non-JSON error page."""
