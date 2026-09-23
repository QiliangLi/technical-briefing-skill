from datetime import datetime, timezone

import httpx

from briefing_skill.adapters.arxiv import ArxivCollector
from briefing_skill.config import ConfigBundle


def _feed() -> bytes:
    published = datetime.now(timezone.utc).isoformat()
    return f'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Useful Paper</title><id>arxiv:1234.5678</id><published>{published}</published>
      <link href="https://arxiv.org/abs/1234.5678"/><summary>Evidence</summary><author><name>A</name></author></entry>
    </feed>'''.encode()


def test_arxiv_direction_failure_preserves_prior_results_and_deduplicates():
    directions = [
        {"id": "one", "include_terms": ["agent"]},
        {"id": "two", "include_terms": ["cache"]},
        {"id": "three", "include_terms": ["network"]},
    ]
    config = ConfigBundle(
        topics={"topics": [{"id": "topic", "directions": directions}]},
        sources={
            "sources": [
                {
                    "id": "arxiv",
                    "endpoint": "https://export.arxiv.org/api/query",
                    "max_results_per_direction": 5,
                    "request_interval_seconds": 0.25,
                    "categories": ["cs.AI"],
                }
            ]
        },
        scoring={},
        settings={},
        email={},
    )

    class FakeHttp:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params):
            self.calls += 1
            if self.calls == 3:
                raise httpx.ConnectError("offline", request=httpx.Request("GET", url))
            return httpx.Response(200, content=_feed(), request=httpx.Request("GET", url, params=params))

    sleeps = []
    http = FakeHttp()
    items = ArxivCollector(config, http, sleep_fn=sleeps.append).collect()

    assert http.calls == 3
    assert sleeps == [0.25, 0.25]
    assert len(items) == 1
    assert items[0].external_id == "arxiv:1234.5678"


def _rate_limit_config(directions):
    return ConfigBundle(
        topics={"topics": [{"id": "topic", "directions": directions}]},
        sources={
            "sources": [
                {
                    "id": "arxiv",
                    "endpoint": "https://export.arxiv.org/api/query",
                    "max_results_per_direction": 5,
                    "request_interval_seconds": 0.25,
                    "rate_limit_retry_attempts": 2,
                    "rate_limit_backoff_seconds": 30,
                    "rate_limit_circuit_breaker": 2,
                    "categories": ["cs.AI"],
                }
            ]
        },
        scoring={},
        settings={},
        email={},
    )


def test_rate_limited_direction_recovers_with_growing_backoff():
    directions = [{"id": "one", "include_terms": ["agent"]}, {"id": "two", "include_terms": ["cache"]}]

    class FakeHttp:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params):
            self.calls += 1
            if self.calls == 1:
                return httpx.Response(406, request=httpx.Request("GET", url, params=params))
            return httpx.Response(200, content=_feed(), request=httpx.Request("GET", url, params=params))

    sleeps = []
    http = FakeHttp()
    items = ArxivCollector(_rate_limit_config(directions), http, sleep_fn=sleeps.append).collect()

    assert http.calls == 3  # 406, retry, success on direction one; direction two succeeds first try
    assert sleeps == [30.0, 0.25]
    assert len(items) == 1


def test_persistent_rate_limit_opens_circuit_breaker_and_stops_the_lane():
    directions = [
        {"id": f"d{i}", "include_terms": [f"term{i}"]} for i in range(5)
    ]

    class FakeHttp:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params):
            self.calls += 1
            return httpx.Response(406, request=httpx.Request("GET", url, params=params))

    sleeps = []
    http = FakeHttp()
    items = ArxivCollector(_rate_limit_config(directions), http, sleep_fn=sleeps.append).collect()

    # breaker_limit=2 directions, each retried rate_limit_retry_attempts=2 times
    assert http.calls == 6
    assert items == []
    assert sleeps.count(30.0) == 2  # first backoff of each blocked direction
    assert sleeps.count(60.0) == 2  # second backoff of each blocked direction
    assert sleeps.count(0.25) == 1  # inter-direction interval before direction two


def test_transport_failure_counts_toward_the_circuit_breaker():
    directions = [
        {"id": f"d{i}", "include_terms": [f"term{i}"]} for i in range(4)
    ]

    class FakeHttp:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params):
            self.calls += 1
            raise httpx.ConnectError("offline", request=httpx.Request("GET", url, params=params))

    http = FakeHttp()
    items = ArxivCollector(_rate_limit_config(directions), http, sleep_fn=lambda _s: None).collect()

    assert http.calls == 2  # two consecutive blocked directions stop the lane
    assert items == []
