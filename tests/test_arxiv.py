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
