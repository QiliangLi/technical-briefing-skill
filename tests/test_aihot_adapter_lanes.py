from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from briefing_skill.adapters.aihot import AIHOT_CONNECTOR_VERSION, upstream_story_id
from briefing_skill.adapters.aihot import AIHotCollector
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database


ENDPOINT = "https://aihot.virxact.com/api/v1/items"
API_BASE = "https://aihot.virxact.com/api/v1"
SELECTED_URL = f"{ENDPOINT}?mode=selected&window=24h&by=timeline&limit=50"
HOT_URL = f"{API_BASE}/hot-topics"
DAILY_URL = f"{API_BASE}/dailies/latest"


class Response:
    def __init__(self, body=None, *, status=200, headers=None):
        self._body = body
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, *, params=None, headers=None, retries=3):
        key = f"{url}?{urlencode(params)}" if params else url
        self.calls.append((key, dict(headers or {})))
        value = self.responses[key]
        if isinstance(value, Exception):
            raise value
        return value


def upstream_item(item_id, title, summary, original, *, story=None, reason=None, score=70):
    links = {"aihot": f"https://aihot.virxact.com/items/{item_id}", "original": original}
    if story:
        links["story"] = f"https://aihot.virxact.com/story/{story}"
    return {
        "id": item_id,
        "title": title,
        "summary": summary,
        "source": {"name": "Example（RSS）"},
        "links": links,
        "publishedAt": "2026-08-20T10:00:00.000Z",
        "category": "infra",
        "score": score,
        "reason": reason,
    }


def config() -> ConfigBundle:
    return ConfigBundle(
        topics={"topics": []},
        sources={
            "sources": [
                {
                    "id": "aihot",
                    "name": "AI HOT",
                    "type": "aihot",
                    "enabled": True,
                    "endpoint": ENDPOINT,
                    "api_base": API_BASE,
                    "window": "7d",
                    "base_selected_limit": 50,
                    "hot_topics_enabled": True,
                    "daily_enabled": True,
                }
            ]
        },
        scoring={},
        settings={},
        email={},
    )


def daily_payload(*sections):
    return {"schemaVersion": 1, "report": {"date": "2026-08-21", "sections": list(sections)}}


def hot_payload(*topics):
    return {"schemaVersion": 1, "items": list(topics)}


def lane_responses(selected=None, daily=None, hot=None) -> dict:
    return {
        SELECTED_URL: Response({"items": selected or []}),
        DAILY_URL: Response(daily or {"report": {"date": "2026-08-21", "sections": []}}),
        HOT_URL: Response(hot or {"items": []}),
    }


def make_collector(http, tmp_path: Path, run_id="run-1"):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    db.create_run(run_id, "COLLECTING")
    return AIHotCollector(config(), db, http, run_id=run_id, run_dir=run_dir), db, run_dir


def test_daily_and_hot_lanes_merge_into_single_candidates(tmp_path: Path) -> None:
    shared = upstream_item(
        "cmt1",
        "KVCache 跨节点预填调度器开源",
        "调度器把长尾预填请求偏转到解码节点分块执行，实测 SLO 维持到 9RPS。",
        "https://example.com/kv-scheduler",
        story="bca5db53-0103-4fbd-85c6-05d34c5deb4f",
    )
    daily_complete = {
        "title": "投机解码草稿模型推理提速 3.18 倍",
        "summary": "通过投机解码在不改变输出质量的前提下提升 GPU 吞吐，草稿模型约 300M 参数。",
        "links": {
            "aihot": "https://aihot.virxact.com/items/cmt2",
            "original": "https://huggingface.co/blog/dspark",
        },
    }
    daily_no_summary = {"title": "缺摘要条目", "links": {"original": "https://example.com/none"}}
    daily_no_original = {"title": "缺原文条目", "summary": "没有原始链接的条目不应进入候选。"}
    http = FakeHttp(
        lane_responses(
            selected=[shared],
            daily=daily_payload(
                {
                    "label": "模型发布/更新",
                    "items": [shared, daily_complete, daily_no_summary, daily_no_original],
                }
            ),
            hot=hot_payload(
                {
                    "rank": 1,
                    "id": "cmt1",
                    "title": shared["title"],
                    "links": {"original": "https://example.com/kv-scheduler", "aihot": "https://aihot.virxact.com/items/cmt1", "story": "https://aihot.virxact.com/story/bca5db53-0103-4fbd-85c6-05d34c5deb4f"},
                    "sourceCount": 10,
                },
                {
                    "rank": 2,
                    "id": "cmt9",
                    "title": "无法解析摘要的热点",
                    "links": {"original": "https://example.com/unmatched"},
                },
            ),
        )
    )
    collector, db, run_dir = make_collector(http, tmp_path)

    items = collector.collect()

    assert sorted(item.title for item in items) == [
        "KVCache 跨节点预填调度器开源",
        "投机解码草稿模型推理提速 3.18 倍",
    ]
    merged = next(item for item in items if item.external_id == "cmt1")
    assert merged.payload["aihot_lanes"] == ["selected", "daily", "hot"]
    assert merged.payload["aihot_hot_rank"] == 1
    assert merged.payload["aihot_story_id"] == "bca5db53-0103-4fbd-85c6-05d34c5deb4f"
    assert merged.original_url == "https://example.com/kv-scheduler"

    daily_item = next(item for item in items if item.external_id == "cmt2")
    assert daily_item.payload["aihot_lane"] == "daily"
    assert daily_item.payload["aihot_daily_section"] == "模型发布/更新"
    assert daily_item.published_at == "2026-08-21"

    records = db.list_radar_upstream_records("run-1")
    by_lane = {}
    for record in records:
        by_lane.setdefault(record["upstream_lane"], []).append(record["upstream_item_id"])
    assert sorted(by_lane["selected"]) == ["cmt1"]
    assert sorted(x or "" for x in by_lane["daily"]) == ["", "", "cmt1", "cmt2"]
    assert sorted(x or "" for x in by_lane["hot"]) == ["cmt1", "cmt9"]
    assert all(record["provider"] == "aihot" for record in records)
    assert all(record["selected_for_radar"] == 0 for record in records)
    assert (run_dir / "source-cache" / "aihot" / "freeze.json").exists()


def test_304_replays_cached_body_into_new_run(tmp_path: Path) -> None:
    cached = upstream_item("cmt1", "缓存命中的条目", "跨运行响应缓存中的完整中文摘要内容。", "https://example.com/cached")
    http = FakeHttp(
        {
            SELECTED_URL: Response(status=304, headers={"ETag": "tag-1"}),
            DAILY_URL: Response({"report": {"date": "2026-08-21", "sections": []}}),
            HOT_URL: Response({"items": []}),
        }
    )
    collector, db, _ = make_collector(http, tmp_path)
    full_url = SELECTED_URL
    db.upsert_source_state(
        f"aihot:{full_url}",
        etag="tag-1",
        payload={"params": {}, "body": {"items": [cached]}},
    )

    items = collector.collect()

    assert [item.title for item in items] == ["缓存命中的条目"]
    selected_call = next(call for call in http.calls if call[0] == SELECTED_URL)
    assert selected_call[1] == {"If-None-Match": "tag-1"}
    records = db.list_radar_upstream_records("run-1")
    assert [record["upstream_item_id"] for record in records] == ["cmt1"]


def test_304_without_cached_body_forces_refetch(tmp_path: Path) -> None:
    fresh = upstream_item("cmt2", "强制重取的条目", "旧缓存没有响应体时必须强制重新拉取。", "https://example.com/fresh")
    responses: dict[str, Response | RuntimeError] = {
        DAILY_URL: Response({"report": {"date": "2026-08-21", "sections": []}}),
        HOT_URL: Response({"items": []}),
    }

    class TwoPhaseHttp(FakeHttp):
        def get(self, url, *, params=None, headers=None, retries=3):
            key = f"{url}?{urlencode(params)}" if params else url
            if key == SELECTED_URL:
                self.calls.append((key, dict(headers or {})))
                if headers:
                    return Response(status=304, headers={"ETag": "tag-legacy"})
                return Response({"items": [fresh]}, headers={"ETag": "tag-new"})
            return super().get(url, params=params, headers=headers, retries=retries)

    collector, db, _ = make_collector(TwoPhaseHttp(responses), tmp_path)
    db.upsert_source_state(f"aihot:{SELECTED_URL}", etag="tag-legacy", payload={"params": {}})

    items = collector.collect()

    assert [item.title for item in items] == ["强制重取的条目"]
    selected_calls = [call for call in collector.http.calls if call[0] == SELECTED_URL]
    assert len(selected_calls) == 2
    assert selected_calls[0][1] == {"If-None-Match": "tag-legacy"}
    assert selected_calls[1][1] == {}
    state = db.get_source_state(f"aihot:{SELECTED_URL}")
    assert state["etag"] == "tag-new"
    assert state["payload"]["body"]["items"][0]["id"] == "cmt2"


def test_frozen_run_replays_without_http_and_stays_idempotent(tmp_path: Path) -> None:
    shared = upstream_item("cmt1", "冻结条目", "冻结后 resume 不得重新请求上游。", "https://example.com/frozen")
    http = FakeHttp(
        lane_responses(
            selected=[shared],
            daily=daily_payload({"label": "模型发布/更新", "items": [shared]}),
            hot=hot_payload({"rank": 3, "id": "cmt1", "links": {"original": "https://example.com/frozen"}}),
        )
    )
    collector, db, run_dir = make_collector(http, tmp_path)

    first = collector.collect()
    freeze_path = run_dir / "source-cache" / "aihot" / "freeze.json"
    frozen_at = json.loads(freeze_path.read_text(encoding="utf-8"))["frozen_at"]

    replay_collector = AIHotCollector(
        config(),
        db,
        FakeHttp({}),  # any HTTP attempt raises KeyError
        run_id="run-1",
        run_dir=run_dir,
    )
    second = replay_collector.collect()

    def fingerprint(items):
        return sorted(
            (item.external_id, item.title, tuple(item.payload.get("aihot_lanes") or []), item.payload.get("aihot_hot_rank"))
            for item in items
        )

    assert fingerprint(first) == fingerprint(second)
    assert json.loads(freeze_path.read_text(encoding="utf-8"))["frozen_at"] == frozen_at
    records = db.list_radar_upstream_records("run-1")
    keys = [(record["upstream_lane"], record["upstream_item_id"]) for record in records]
    assert len(keys) == len(set(keys))


def test_freeze_from_other_run_is_not_reused(tmp_path: Path) -> None:
    shared = upstream_item("cmt1", "他 run 冻结", "其他 run 的冻结响应不能进入本期。", "https://example.com/other")
    http = FakeHttp(lane_responses(selected=[shared]))
    collector, db, run_dir = make_collector(http, tmp_path)
    run_dir.joinpath("source-cache", "aihot").mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("source-cache", "aihot", "freeze.json").write_text(
        json.dumps({"connector_version": AIHOT_CONNECTOR_VERSION, "run_id": "run-other", "lanes": {}}),
        encoding="utf-8",
    )

    items = collector.collect()

    assert [item.title for item in items] == ["他 run 冻结"]
    assert any(call[0] == SELECTED_URL for call in http.calls)
    assert json.loads((run_dir / "source-cache" / "aihot" / "freeze.json").read_text(encoding="utf-8"))["run_id"] == "run-1"


@pytest.mark.parametrize(
    ("links", "expected"),
    [
        ({"story": "https://aihot.virxact.com/story/abc-123"}, "abc-123"),
        ({"aihot": "https://aihot.virxact.com/items/cmt1"}, ""),
        ({}, ""),
    ],
)
def test_story_id_only_from_official_links(links, expected) -> None:
    assert upstream_story_id({"links": links}) == expected


def test_all_query_lane_collects_with_direction_hint_and_story(tmp_path: Path) -> None:
    query = "KV cache prefill"
    # Build the exact keys the adapter produces for the all/paper lanes.
    from urllib.parse import urlencode as _encode

    all_key = f"{ENDPOINT}?{_encode({'mode': 'all', 'window': '7d', 'by': 'timeline', 'limit': 15, 'q': query})}"
    paper_key = (
        f"{ENDPOINT}?{_encode({'mode': 'all', 'category': 'paper', 'window': '7d', 'by': 'timeline', 'limit': 15, 'q': query})}"
    )
    queried = upstream_item(
        "cmt7",
        "KVCache 预填分段传输论文",
        "论文提出把预填阶段 KV cache 分段跨节点传输，降低首 token 延迟。",
        "https://arxiv.org/abs/2608.11111",
        story="story-7",
    )
    http = FakeHttp(
        {
            SELECTED_URL: Response({"items": []}),
            all_key: Response({"items": [queried]}),
            paper_key: Response({"items": [queried]}),
            DAILY_URL: Response({"report": {"date": "2026-08-21", "sections": []}}),
            HOT_URL: Response({"items": []}),
        }
    )
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_dir = tmp_path / "runs" / "run-all"
    run_dir.mkdir(parents=True)
    db.create_run("run-all", "COLLECTING")
    topic_config = ConfigBundle(
        topics={
            "topics": [
                {
                    "id": "tpn",
                    "name": "TPN",
                    "aihot_priority": "medium",
                    "directions": [{"id": "kv", "aihot_queries": [query]}],
                }
            ]
        },
        sources={
            "sources": [
                {
                    "id": "aihot",
                    "type": "aihot",
                    "enabled": True,
                    "endpoint": ENDPOINT,
                    "api_base": API_BASE,
                    "window": "7d",
                    "base_selected_limit": 50,
                    "query_limits": {"medium": 15},
                    "hot_topics_enabled": True,
                    "daily_enabled": True,
                }
            ]
        },
        scoring={},
        settings={},
        email={},
    )
    collector = AIHotCollector(topic_config, db, http, run_id="run-all", run_dir=run_dir)

    items = collector.collect()

    assert [item.external_id for item in items] == ["cmt7"]
    merged = items[0]
    assert merged.topic_hint == "tpn" and merged.direction_hint == "kv"
    assert set(merged.payload["aihot_lanes"]) == {"all", "paper"}
    assert merged.payload["aihot_story_id"] == "story-7"
    assert merged.priority > 15.0  # query boost applied
    lanes = {record["upstream_lane"] for record in db.list_radar_upstream_records("run-all")}
    # Empty lanes record no observations; only lanes with items appear.
    assert lanes == {"all", "paper"}
