from __future__ import annotations

from datetime import datetime, timezone

import httpx

from briefing_skill.db import Database
from briefing_skill.historical_backfill import HistoricalBackfillService, historical_backfill_status


FIXED_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


class FakeConfig:
    def __init__(self, *, arxiv=True, github=False, directions=1, unsupported=False):
        self.settings = {
            "efficiency": {
                "deep_topics": ["tpn"],
                "deep_lookback_days": 60,
                "historical_backfill": {
                    "enabled": True,
                    "lookback_days": 60,
                    "arxiv_page_size": 5,
                    "github_page_size": 2,
                },
            }
        }
        self._sources = []
        if arxiv:
            self._sources.append(
                {
                    "id": "arxiv",
                    "name": "arXiv",
                    "type": "arxiv",
                    "enabled": True,
                    "source_level": "A",
                    "endpoint": "https://export.arxiv.org/api/query",
                    "request_interval_seconds": 0,
                    "categories": ["cs.DC"],
                }
            )
        if github:
            self._sources.append(
                {
                    "id": "github_releases",
                    "name": "GitHub Releases",
                    "type": "github_releases",
                    "enabled": True,
                    "source_level": "A",
                    "repositories": [
                        {"repo": "org/repo-a", "topic": "tpn", "direction": "d0"},
                        {"repo": "org/repo-b", "topic": "tpn", "direction": "d0"},
                    ],
                }
            )
        if unsupported:
            self._sources.append(
                {
                    "id": "openreview_agent_search",
                    "name": "OpenReview",
                    "type": "agent_web",
                    "enabled": True,
                    "source_level": "A",
                }
            )
        self._directions = directions

    def source_list(self):
        return list(self._sources)

    def iter_directions(self):
        topic = {"id": "tpn"}
        for index in range(self._directions):
            yield topic, {
                "id": f"d{index}",
                "include_terms": [f"kv cache {index}"],
            }


class FakeHTTP:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, *, headers=None, params=None, retries=3):
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}})
        return self.handler(url, params or {})


def response(url: str, *, status=200, content=b"", json_data=None):
    request = httpx.Request("GET", url)
    if json_data is not None:
        return httpx.Response(status, json=json_data, request=request)
    return httpx.Response(status, content=content, request=request)


def atom(entries):
    body = ["<?xml version='1.0' encoding='UTF-8'?><feed xmlns='http://www.w3.org/2005/Atom'>"]
    for ident, title, published in entries:
        body.append(
            f"<entry><id>http://arxiv.org/abs/{ident}v1</id>"
            f"<title>{title}</title><summary>summary {title}</summary>"
            f"<published>{published}</published>"
            f"<link rel='alternate' href='https://arxiv.org/abs/{ident}v1'/>"
            f"<link title='pdf' type='application/pdf' href='https://arxiv.org/pdf/{ident}v1'/>"
            "<author><name>Alice</name></author></entry>"
        )
    body.append("</feed>")
    return "".join(body).encode()


def db_for(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    return db


def test_arxiv_backfill_stops_at_cutoff_and_does_not_rescan(tmp_path):
    config = FakeConfig(arxiv=True, github=False)
    payload = atom(
        [
            ("2608.00001", "Recent A", "2026-08-01T00:00:00Z"),
            ("2606.00002", "Recent B", "2026-06-20T00:00:00Z"),
            ("2606.00003", "Too Old", "2026-06-01T00:00:00Z"),
        ]
    )
    http = FakeHTTP(lambda url, params: response(url, content=payload))
    service = HistoricalBackfillService(
        config,
        db_for(tmp_path),
        http,
        sleep_fn=lambda _: None,
        now_fn=lambda: FIXED_NOW,
    )

    first = service.run(days=60, max_requests=1)
    assert [item.title for item in first.items] == ["Recent A", "Recent B"]
    assert first.report["status"] == "COMPLETE"
    assert first.report["requests_used"] == 1
    assert first.report["complete_lanes"] == 1
    state = first.report["lanes"][0]
    assert state["cursor"] == 2

    second = service.run(days=60, max_requests=1)
    assert second.items == []
    assert second.report["requests_used"] == 0
    assert len(http.calls) == 1


def test_github_backfill_resumes_pagination_across_invocations(tmp_path):
    config = FakeConfig(arxiv=False, github=True)

    def handler(url, params):
        page = int(params.get("page", 1))
        repo = url.split("/repos/", 1)[1].split("/releases", 1)[0]
        if repo == "org/repo-b":
            return response(url, json_data=[])
        if page == 1:
            return response(
                url,
                json_data=[
                    {
                        "id": 1,
                        "name": "v2",
                        "tag_name": "v2",
                        "html_url": "https://github.com/org/repo-a/releases/tag/v2",
                        "published_at": "2026-08-01T00:00:00Z",
                        "author": {"login": "alice"},
                    },
                    {
                        "id": 2,
                        "name": "v1.5",
                        "tag_name": "v1.5",
                        "html_url": "https://github.com/org/repo-a/releases/tag/v1.5",
                        "published_at": "2026-07-01T00:00:00Z",
                        "author": {"login": "alice"},
                    },
                ],
            )
        return response(
            url,
            json_data=[
                {
                    "id": 3,
                    "name": "old",
                    "tag_name": "old",
                    "html_url": "https://github.com/org/repo-a/releases/tag/old",
                    "published_at": "2026-06-01T00:00:00Z",
                    "author": {"login": "alice"},
                }
            ],
        )

    http = FakeHTTP(handler)
    db = db_for(tmp_path)
    service = HistoricalBackfillService(config, db, http, now_fn=lambda: FIXED_NOW)

    first = service.run(days=60, max_requests=1)
    assert len(first.items) == 2
    assert first.report["status"] == "IN_PROGRESS"
    assert http.calls[0]["params"]["page"] == 1

    second = service.run(days=60, max_requests=2)
    assert second.report["complete_lanes"] == 2
    repo_a_calls = [call for call in http.calls if "repo-a" in call["url"]]
    assert [call["params"]["page"] for call in repo_a_calls] == [1, 2]


def test_small_budget_rotates_across_source_families_and_directions(tmp_path):
    config = FakeConfig(arxiv=True, github=True, directions=3)

    def handler(url, params):
        if "api.github.com" in url:
            return response(url, json_data=[])
        return response(url, content=atom([]))

    http = FakeHTTP(handler)
    db = db_for(tmp_path)
    service = HistoricalBackfillService(
        config,
        db,
        http,
        sleep_fn=lambda _: None,
        now_fn=lambda: FIXED_NOW,
    )
    first = service.run(days=60, max_requests=4)
    assert first.report["requests_used"] == 4
    # Interleaving prevents a tiny budget from being consumed only by arXiv.
    assert sum("api.github.com" in call["url"] for call in http.calls) == 2
    assert sum("arxiv.org" in call["url"] for call in http.calls) == 2
    assert first.report["complete_lanes"] == 4
    assert first.report["active_lanes"] == 1

    second = service.run(days=60, max_requests=1)
    assert second.report["requests_used"] == 1
    assert second.report["status"] == "COMPLETE"
    assert second.report["complete_lanes"] == 5


def test_existing_identity_is_not_reinserted_and_unsupported_a_sources_are_visible(tmp_path):
    config = FakeConfig(arxiv=True, github=False, unsupported=True)
    db = db_for(tmp_path)
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,canonical_url,identity_key,published_at,authors_json,external_id,
            priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "old",
            "prior",
            "arxiv",
            "arXiv",
            "A",
            0,
            "Already Seen",
            "",
            "https://arxiv.org/abs/2608.00001v1",
            "https://arxiv.org/abs/2608.00001v1",
            "arxiv:2608.00001",
            "2026-08-01T00:00:00Z",
            "[]",
            "http://arxiv.org/abs/2608.00001v1",
            18,
            "x",
            "{}",
            "2026-08-01T00:00:00Z",
        ),
    )
    payload = atom([("2608.00001", "Already Seen", "2026-08-01T00:00:00Z")])
    http = FakeHTTP(lambda url, params: response(url, content=payload))
    result = HistoricalBackfillService(
        config,
        db,
        http,
        sleep_fn=lambda _: None,
        now_fn=lambda: FIXED_NOW,
    ).run(days=60, max_requests=1)

    assert result.items == []
    assert result.report["duplicates_skipped"] == 1
    status = historical_backfill_status(config, db)
    assert status["unsupported_sources"][0]["source_id"] == "openreview_agent_search"
