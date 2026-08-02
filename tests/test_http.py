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
