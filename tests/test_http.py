from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from briefing_skill.http import HttpClient, HttpRetryError, retry_after_seconds


def _client(handler):
    client = HttpClient()
    client.client.close()
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def test_continuous_429_raises_contextual_error_and_invalid_retry_after_falls_back(monkeypatch):
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "not-a-date"}, request=request)

    monkeypatch.setattr("briefing_skill.http.time.sleep", sleeps.append)
    client = _client(handler)
    try:
        with pytest.raises(HttpRetryError) as raised:
            client.get("https://example.com/limited", retries=3)
    finally:
        client.close()

    assert len(calls) == 3
    assert sleeps == [5.0, 5.0]
    assert raised.value.status_code == 429
    assert raised.value.attempts == 3
    assert "status=429" in str(raised.value)
    assert "https://example.com/limited" in str(raised.value)


def test_continuous_5xx_raises_instead_of_returning_final_response(monkeypatch):
    monkeypatch.setattr("briefing_skill.http.time.sleep", lambda _: None)
    client = _client(lambda request: httpx.Response(503, request=request))
    try:
        with pytest.raises(HttpRetryError, match="status=503"):
            client.get("https://example.com/unavailable", retries=2)
    finally:
        client.close()


def test_retry_after_supports_seconds_http_date_and_safe_fallback():
    now = datetime(2026, 8, 2, 6, 0, tzinfo=timezone.utc)
    assert retry_after_seconds("12", fallback=5, now=now) == 12
    assert retry_after_seconds(format_datetime(now + timedelta(seconds=17)), fallback=5, now=now) == 17
    assert retry_after_seconds("invalid", fallback=7, now=now) == 7
    assert retry_after_seconds("nan", fallback=9, now=now) == 9


class _FakeRequestsResponse:
    def __init__(self, status_code, headers=None, url="https://example.com/limited"):
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url


class _FakeRequestsSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, *, headers=None, params=None, timeout=None):
        self.calls.append((url, headers, params))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


def test_requests_transport_retries_429_and_reports_contextual_error(monkeypatch):
    import requests as requests_lib

    from briefing_skill.http import HttpClient

    monkeypatch.setattr("briefing_skill.http.time.sleep", lambda _: None)
    session = _FakeRequestsSession(
        [
            _FakeRequestsResponse(429, headers={"Retry-After": "2"}),
            _FakeRequestsResponse(429, headers={"Retry-After": "2"}),
            _FakeRequestsResponse(429, headers={"Retry-After": "2"}),
        ]
    )
    client = HttpClient(transport="requests")
    client.client = session
    try:
        with pytest.raises(HttpRetryError) as raised:
            client.get("https://example.com/limited", retries=3)
    finally:
        client.close()

    assert len(session.calls) == 3
    assert raised.value.status_code == 429
    assert raised.value.attempts == 3


def test_requests_transport_returns_success_and_wraps_transport_errors(monkeypatch):
    import requests as requests_lib

    from briefing_skill.http import HttpClient

    sleeps = []
    monkeypatch.setattr("briefing_skill.http.time.sleep", sleeps.append)
    session = _FakeRequestsSession(
        [
            requests_lib.ConnectionError("boom"),
            _FakeRequestsResponse(200, headers={"Content-Type": "application/atom+xml"}),
        ]
    )
    client = HttpClient(transport="requests")
    client.client = session
    try:
        response = client.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": "cat:cs.AI"},
            headers={"Accept": "application/atom+xml"},
            retries=3,
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert sleeps == [1.0]


def test_unknown_transport_is_rejected():
    from briefing_skill.http import HttpClient

    with pytest.raises(ValueError, match="unknown http transport"):
        HttpClient(transport="grpc")
