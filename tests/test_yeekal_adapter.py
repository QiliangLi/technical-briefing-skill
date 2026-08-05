from __future__ import annotations

from pathlib import Path

import pytest

from briefing_skill.adapters.yeekal import YeeKalDailyCollector
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.source_metadata import extract_published_at


RSS_URL = "https://yeekal.com/rss/daily.xml"
INDEX_URL = "https://yeekal.com/daily/"


class Response:
    def __init__(self, text="", *, status=200, headers=None):
        self.text = text
        self.content = text.encode()
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def config() -> ConfigBundle:
    return ConfigBundle(
        topics={
            "topics": [
                {
                    "id": "tpn",
                    "name": "TPN",
                    "directions": [
                        {"id": "kv", "include_terms": ["KVCache", "prefill decode"], "aihot_boost_terms": ["cache transfer"], "queries": ["KVCache network scheduling"]}
                    ],
                }
            ]
        },
        sources={
            "sources": [
                {
                    "id": "yeekal_daily",
                    "type": "yeekal_daily",
                    "enabled": True,
                    "rss_url": RSS_URL,
                    "index_url": INDEX_URL,
                    "max_issue_pages": 3,
                    "max_external_links_per_issue": 40,
                    "base_priority": 14,
                    "topic_boosts": {"tpn": 1.2},
                }
            ]
        },
        scoring={},
        settings={},
        email={},
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<script type="application/ld+json">{"datePublished":"2026-08-01"}</script>', "2026-08-01"),
        ('<meta property="article:published_time" content="2026-08-02T03:00:00Z">', "2026-08-02"),
        ('<time datetime="2026-08-03">3 Aug</time>', "2026-08-03"),
    ],
)
def test_extract_published_at(html: str, expected: str) -> None:
    assert extract_published_at(html, "https://example.com/post").startswith(expected)


def test_yeekal_resolves_external_links_and_keeps_dates_separate(tmp_path: Path) -> None:
    rss = """<rss><channel><item><title>Daily</title><link>https://yeekal.com/daily/2026-08-05</link><pubDate>Wed, 05 Aug 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
    issue = """
      <main><h2>GitHub Trending</h2><div>
        <a href="https://example.com/kv?utm_source=yeekal">KVCache network scheduler</a>
        <p>KVCache locations coordinate prefill decode transfers.</p>
        <a href="https://example.com/kv?utm_source=duplicate">duplicate</a>
        <a href="/daily/archive">internal</a><a href="https://cdn.example.com/a.png">image</a>
      </div><h2>Other</h2><a href="https://example.com/cooking">cooking recipe</a></main>
    """
    http = FakeHttp(
        {
            RSS_URL: Response(rss, headers={"ETag": "rss-tag"}),
            "https://yeekal.com/daily/2026-08-05": Response(issue),
            "https://example.com/kv": Response('<meta property="article:published_time" content="2026-08-04T01:00:00Z">'),
        }
    )
    db = Database(tmp_path / "briefing.sqlite")
    db.init()

    items = YeeKalDailyCollector(config(), db, http).collect()

    assert len(items) == 1
    item = items[0]
    assert item.original_url == "https://example.com/kv"
    assert item.published_at.startswith("2026-08-04")
    assert item.discovered_at == "Wed, 05 Aug 2026 00:00:00 GMT"
    assert item.source_level == "B" and item.discovery_only is True
    assert item.payload["issue_url"].startswith("https://yeekal.com/daily/")
    assert "https://example.com/cooking" not in http.calls


def test_yeekal_falls_back_to_index_and_preserves_unknown_publication_date(tmp_path: Path) -> None:
    index = '<a href="/daily/2026-08-05">2026-08-05</a>'
    issue = '<main><h2>Infra</h2><p>KVCache transfer <a href="https://example.com/no-date">source</a></p></main>'
    http = FakeHttp(
        {
            RSS_URL: RuntimeError("rss down"),
            INDEX_URL: Response(index),
            "https://yeekal.com/daily/2026-08-05": Response(issue),
            "https://example.com/no-date": Response("<html><body>no date</body></html>"),
        }
    )
    db = Database(tmp_path / "briefing.sqlite")
    db.init()

    items = YeeKalDailyCollector(config(), db, http).collect()

    assert len(items) == 1
    assert items[0].published_at is None
    assert items[0].discovered_at.startswith("2026-08-05")
    assert items[0].original_url != "https://yeekal.com/daily/2026-08-05"
