"""A broken backend must never be presented as 'no results'.

This is the whole point of the guardrails: if the mirror is rate limiting,
blocked, or down, the run has to say so loudly. Rendering it as an empty
result set means a quiet backend gets read as a quiet market, and that
misreading becomes campaign evidence.
"""

import pytest
import requests

from reddit_find import arctic
from reddit_find.errors import (
    BackendUnavailableError,
    RedditBlockedError,
    RedditRateLimitError,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, text="{}"):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def _no_sleep(monkeypatch):
    monkeypatch.setattr(arctic.time, "sleep", lambda _s: None)


def test_persistent_429_raises_rather_than_returning_empty(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(arctic.requests, "get", lambda *a, **k: FakeResponse(429))

    with pytest.raises(RedditRateLimitError):
        arctic._get("posts/search", {})


def test_429_then_success_recovers(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(429)
        return FakeResponse(200, {"data": [{"id": "abc"}]})

    monkeypatch.setattr(arctic.requests, "get", flaky)

    assert arctic._get("posts/search", {}) == [{"id": "abc"}]
    assert calls["n"] == 3, "should have retried through the 429s"


def test_403_raises_blocked(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(arctic.requests, "get", lambda *a, **k: FakeResponse(403))

    with pytest.raises(RedditBlockedError):
        arctic._get("posts/search", {})


def test_unreachable_backend_raises(monkeypatch):
    _no_sleep(monkeypatch)

    def boom(*_a, **_k):
        raise requests.exceptions.ConnectionError("dns failure")

    monkeypatch.setattr(arctic.requests, "get", boom)

    with pytest.raises(BackendUnavailableError):
        arctic._get("posts/search", {})


def test_non_json_response_raises(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(
        arctic.requests, "get", lambda *a, **k: FakeResponse(200, None, "<html>502</html>")
    )

    with pytest.raises(BackendUnavailableError):
        arctic._get("posts/search", {})


def test_genuine_empty_result_is_still_empty(monkeypatch):
    """The contrast case: a healthy backend with nothing to say returns []."""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(arctic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": []}))

    assert arctic._get("posts/search", {}) == []


def test_every_request_draws_from_the_shared_limiter(monkeypatch):
    """Pacing must be central, so no code path can bypass the budget."""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(arctic.requests, "get", lambda *a, **k: FakeResponse(200, {"data": []}))

    limiter = arctic.get_limiter()
    before = limiter.requests_this_run
    arctic._get("posts/search", {})
    arctic._get("posts/search", {})

    assert limiter.requests_this_run == before + 2
