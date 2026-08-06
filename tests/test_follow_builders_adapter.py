from __future__ import annotations

import json
from pathlib import Path

from briefing_skill.adapters.follow_builders import FollowBuildersCollector
from briefing_skill.collection import CollectionService
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.fulltext import FulltextService
from briefing_skill.utils import now_iso


class Response:
    def __init__(self, payload=None, *, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def config() -> ConfigBundle:
    return ConfigBundle(
        topics={},
        sources={
            "sources": [
                {
                    "id": "follow_builders",
                    "type": "follow_builders",
                    "enabled": True,
                    "feeds": {"x": "x", "podcasts": "podcasts", "blogs": "blogs"},
                    "base_priorities": {"x": 8, "podcasts": 12, "blogs": 14},
                    "max_x_items": 40,
                    "max_podcast_items": 8,
                    "max_blog_items": 20,
                    "skip_short_x_chars": 60,
                }
            ]
        },
        scoring={},
        settings={"max_fulltext_chars": 140000, "fact_chunk_chars": 28000, "fact_chunk_overlap_chars": 1200},
        email={},
    )


def test_follow_builders_maps_x_and_podcast_without_putting_transcript_in_db(tmp_path: Path) -> None:
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    run_id = "follow-run"
    db.create_run(run_id)
    run_dir = tmp_path / "workspace" / "runs" / run_id
    long_tweet = "KVCache location should enter network scheduling so decode traffic does not compete blindly with prefill transfers."
    responses = {
        "x": Response(
            {
                "generatedAt": "2026-08-05T00:00:00Z",
                "x": [
                    {
                        "name": "Builder",
                        "handle": "builder",
                        "bio": "systems",
                        "tweets": [
                            {"id": "short", "text": "yes", "url": "https://x.example/short"},
                            {"id": "long", "text": long_tweet, "url": "https://x.example/long", "createdAt": "2026-08-04T00:00:00Z", "likes": 0},
                            {"id": "link", "text": "https://example.com", "url": "https://x.example/link"},
                        ],
                    }
                ],
            },
            headers={"ETag": "x-tag"},
        ),
        "podcasts": Response(
            {
                "generatedAt": "2026-08-05T00:00:00Z",
                "podcasts": [
                    {
                        "name": "Infra Talk",
                        "title": "Agent runtime internals",
                        "guid": "episode/1",
                        "url": "https://pod.example/1",
                        "publishedAt": "2026-08-04T00:00:00Z",
                        "transcript": "A" * 800,
                    }
                ],
            }
        ),
        "blogs": Response({"generatedAt": "2026-08-05T00:00:00Z", "blogs": []}),
    }
    collector = FollowBuildersCollector(config(), db, FakeHttp(responses), run_dir)

    items = collector.collect()

    assert [item.source_id for item in items] == ["follow_builders_x", "follow_builders_podcast"]
    assert items[0].summary == long_tweet
    assert items[0].source_level == "B" and items[0].discovery_only is True
    transcript_path = run_dir / items[1].payload["local_fulltext_path"]
    assert transcript_path.exists()
    assert "A" * 100 in transcript_path.read_text(encoding="utf-8")
    assert "transcript" not in json.dumps(items[1].payload).lower()

    service = CollectionService(config(), db, run_dir)
    service.http.close()
    service.http = FakeHttp({})
    rows = service.persist(run_id, items)
    assert "A" * 100 not in rows[1]["payload_json"]
    candidate_id = "candidate-podcast"
    db.execute(
        "INSERT INTO candidates(id,run_id,raw_item_id,topic_id,direction_id,rule_score,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (candidate_id, run_id, rows[1]["id"], "tpn", "kv", 1, "RELEVANT", now_iso()),
    )
    fulltext = FulltextService(config(), db, run_dir)
    fulltext.http.close()
    manifest = fulltext.fetch_candidate(run_id, {"id": candidate_id, "raw_item_id": rows[1]["id"]})
    assert manifest["fetch_status"] == "LOCAL_SOURCE"
    assert manifest["media_type"] == "text/markdown"


def test_follow_builders_isolates_feed_failures_and_honours_304(tmp_path: Path) -> None:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.upsert_source_state("follow-builders:x:x", etag="old")
    http = FakeHttp(
        {
            "x": Response(status=304),
            "podcasts": RuntimeError("podcast unavailable"),
            "blogs": Response({"blogs": [{"title": "CXL memory", "url": "https://example.com/cxl"}]}),
        }
    )

    items = FollowBuildersCollector(config(), db, http, tmp_path / "run").collect()

    assert [item.source_id for item in items] == ["follow_builders_blog"]
    assert http.calls[0][1]["headers"] == {"If-None-Match": "old"}
