from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlencode

import pytest

from briefing_skill.adapters.aihot import AIHOT_CONNECTOR_VERSION, upstream_story_id
from briefing_skill.adapters.aihot import AIHotCollector
from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database


ENDPOINT = "https://aihot.virxact.com/api/v1/items"
API_BASE = "https://aihot.virxact.com/api/v1"


def _request_key(url: str, params: dict | None) -> str:
    if not params:
        return url
    from urllib.parse import parse_qsl

    base, _, existing = url.partition("?")
    merged = dict(parse_qsl(existing, keep_blank_values=True))
    merged.update({str(k): str(v) for k, v in params.items()})
    return f"{base}?{urlencode(sorted(merged.items()))}"


SELECTED_URL = _request_key(ENDPOINT, {"mode": "selected", "window": "24h", "by": "timeline", "limit": 50})
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
        key = _request_key(url, params)
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
    # The daily date is an internal recall bound only; it must never be
    # presented as the original page's publication date.
    assert daily_item.published_at is None
    assert daily_item.payload["aihot_daily_date"] == "2026-08-21"

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
            key = _request_key(url, params)
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
    # Build normalized keys the same way the fake matches request params.
    all_key = _request_key(
        ENDPOINT,
        {"mode": "all", "window": "7d", "by": "timeline", "limit": 15, "q": query},
    )
    paper_key = _request_key(
        ENDPOINT,
        {"mode": "all", "category": "paper", "window": "7d", "by": "timeline", "limit": 15, "q": query},
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


def test_config_lane_plan_change_invalidates_freeze(tmp_path: Path) -> None:
    shared = upstream_item("cmt1", "冻结条目一", "该条目在旧 lane 计划下已冻结。", "https://example.com/frozen-1")
    http = FakeHttp(lane_responses(selected=[shared]))
    collector, db, run_dir = make_collector(http, tmp_path, run_id="run-plan")
    first = collector.collect()
    assert [item.external_id for item in first] == ["cmt1"]

    # Same connector version but a changed query-lane plan: the freeze is
    # invalid as a whole and must be refetched, never partially replayed.
    extra_query = "agent harness"
    extra_key = _request_key(
        ENDPOINT,
        {"mode": "all", "window": "7d", "by": "timeline", "limit": 15, "q": extra_query},
    )
    extra_item = upstream_item("cmt2", "新查询条目", "新 lane 计划下的补充条目。", "https://example.com/frozen-2")

    def config_with_extra_query():
        return ConfigBundle(
            topics={
                "topics": [
                    {
                        "id": "tpn",
                        "name": "TPN",
                        "aihot_priority": "medium",
                        "directions": [{"id": "kv", "aihot_queries": [extra_query]}],
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

    # A frozen run is immutable: a changed lane plan must fail loudly instead
    # of refetching in place, which would leave a new freeze next to stale
    # INSERT OR IGNORE raw_items (split-brain).
    http2 = FakeHttp(
        {
            **lane_responses(selected=[shared]),
            extra_key: Response({"items": [extra_item]}),
        }
    )
    replay = AIHotCollector(config_with_extra_query(), db, http2, run_id="run-plan", run_dir=run_dir)
    with pytest.raises(RuntimeError, match="lane plan changed"):
        replay.collect()
    assert http2.calls == []
    freeze_doc = json.loads((run_dir / "source-cache" / "aihot" / "freeze.json").read_text(encoding="utf-8"))
    assert "all:tpn:kv:agent harness" not in freeze_doc["lanes"]

    # A NEW run under the new plan refetches cleanly and materializes fully
    # through the real persistence path.
    from briefing_skill.collection import CollectionService

    run2_dir = tmp_path / "runs" / "run-plan-2"
    run2_dir.mkdir(parents=True)
    db.create_run("run-plan-2", "COLLECTING")
    http3 = FakeHttp(
        {
            **lane_responses(selected=[shared]),
            extra_key: Response({"items": [extra_item]}),
        }
    )
    fresh = AIHotCollector(config_with_extra_query(), db, http3, run_id="run-plan-2", run_dir=run2_dir)
    service = CollectionService(config_with_extra_query(), db, run2_dir)
    persisted = service.persist("run-plan-2", fresh.collect())
    assert {row["external_id"] for row in persisted} == {"cmt1", "cmt2"}
    freeze2 = json.loads((run2_dir / "source-cache" / "aihot" / "freeze.json").read_text(encoding="utf-8"))
    assert "all:tpn:kv:agent harness" in freeze2["lanes"]
    summaries = {
        row["external_id"]: row["summary"]
        for row in db.fetchall("SELECT external_id, summary FROM raw_items WHERE run_id='run-plan-2'")
    }
    assert summaries["cmt2"] == extra_item["summary"]


def test_single_lane_failure_keeps_successful_lanes(tmp_path: Path) -> None:
    good = upstream_item("cmt-ok", "可用的推理条目", "该条目来自精选 lane，摘要完整可用。", "https://example.com/ok")
    http = FakeHttp(
        {
            SELECTED_URL: Response({"items": [good]}),
            DAILY_URL: RuntimeError("daily 429"),
            HOT_URL: Response({"items": []}),
        }
    )
    collector, db, _ = make_collector(http, tmp_path)
    items = collector.collect()
    assert [item.external_id for item in items] == ["cmt-ok"]

    # Every planned lane failing is a provider-level failure.
    http_all_down = FakeHttp(
        {
            SELECTED_URL: RuntimeError("selected down"),
            DAILY_URL: RuntimeError("daily down"),
            HOT_URL: RuntimeError("hot down"),
        }
    )
    collector2, _, _ = make_collector(http_all_down, tmp_path, run_id="run-all-down")
    with pytest.raises(RuntimeError, match="provider failure"):
        collector2.collect()


def test_reason_only_item_never_carries_public_summary(tmp_path: Path) -> None:
    reason_only = {
        "id": "cmt-reason",
        "title": "只有推荐理由的条目",
        "reason": "上游编辑认为该推理调度变化值得关注，推荐理由不是原文摘要。",
        "links": {"aihot": "https://aihot.virxact.com/items/cmt-reason", "original": "https://example.com/reason"},
    }
    http = FakeHttp(
        lane_responses(
            selected=[reason_only],
            daily=daily_payload({"label": "模型发布/更新", "items": [reason_only]}),
        )
    )
    collector, db, _ = make_collector(http, tmp_path)

    items = collector.collect()

    # The item survives as an internal observation but carries NO public
    # copy: reason is never promoted into the summary field.
    assert len(items) == 1 and items[0].summary == ""
    assert items[0].payload["aihot_copy_variants"] == []
    records = {r["upstream_lane"]: r for r in db.list_radar_upstream_records("run-1")}
    # The reason is preserved internally for audit, but no public copy exists.
    assert records["selected"]["reason"].startswith("上游编辑认为")
    assert records["selected"]["summary"] is None


def test_two_all_query_lanes_hitting_same_item_do_not_crash_ledger(tmp_path: Path) -> None:
    # Reviewer repro: two same-type (all) query lanes hit the same item; the
    # legacy UNIQUE(run_id, provider, upstream_lane, upstream_item_id) made
    # the second ledger row raise and zero out the whole provider batch.
    shared = upstream_item("cmt-dup", "Agent harness 并行工具调用", "该 harness 在仓库级任务中并行执行工具调用并共享上下文缓存。", "https://example.com/dup")
    q1, q2 = "agent harness", "agentic workflow"
    key1 = _request_key(ENDPOINT, {"mode": "all", "window": "7d", "by": "timeline", "limit": 15, "q": q1})
    key2 = _request_key(ENDPOINT, {"mode": "all", "window": "7d", "by": "timeline", "limit": 15, "q": q2})

    def topic_config():
        return ConfigBundle(
            topics={"topics": [{"id": "agent_x", "name": "Agent", "aihot_priority": "medium",
                                "directions": [{"id": "harness", "aihot_queries": [q1, q2]}]}]},
            sources={"sources": [{"id": "aihot", "type": "aihot", "enabled": True, "endpoint": ENDPOINT,
                                   "api_base": API_BASE, "window": "7d", "base_selected_limit": 50,
                                   "query_limits": {"medium": 15}, "hot_topics_enabled": True,
                                   "daily_enabled": True}]},
            scoring={}, settings={}, email={},
        )

    http = FakeHttp({SELECTED_URL: Response({"items": []}), key1: Response({"items": [shared]}),
                     key2: Response({"items": [shared]}),
                     DAILY_URL: Response({"report": {"date": "2026-08-21", "sections": []}}),
                     HOT_URL: Response({"items": []})})
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    run_dir = tmp_path / "runs" / "run-dup"
    run_dir.mkdir(parents=True)
    db.create_run("run-dup", "COLLECTING")
    collector = AIHotCollector(topic_config(), db, http, run_id="run-dup", run_dir=run_dir)

    items = collector.collect()

    assert [item.external_id for item in items] == ["cmt-dup"]
    records = db.fetchall(
        "SELECT lane_key FROM radar_upstream_records WHERE run_id=? AND upstream_item_id=?",
        ("run-dup", "cmt-dup"),
    )
    assert sorted(row["lane_key"] for row in records) == [
        f"all:agent_x:harness:{q1}",
        f"all:agent_x:harness:{q2}",
    ]


def test_legacy_ledger_unique_constraint_is_rebuilt(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "briefing.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE radar_upstream_records (
            record_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, provider TEXT NOT NULL,
            upstream_lane TEXT NOT NULL, upstream_item_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, provider, upstream_lane, upstream_item_id)
        );
        INSERT INTO radar_upstream_records VALUES ('r1', 'run-m', 'aihot', 'all', 'cmt-x', '2026-08-21');
        """
    )
    conn.commit()
    conn.close()

    db = Database(path)
    db.init()  # rebuilds the table onto the lane_key-based unique constraint

    with db.connect() as conn:
        sql = " ".join(
            conn.execute("SELECT sql FROM sqlite_master WHERE name='radar_upstream_records'").fetchone()[0].split()
        )
    assert "UNIQUE(run_id, provider, lane_key, upstream_item_id)" in sql
    # Same provider/lane/item under two distinct lane keys now coexist.
    def row(record_id: str, lane_key: str) -> dict:
        return {
            "record_id": record_id, "run_id": "run-m", "provider": "aihot", "upstream_lane": "all",
            "lane_key": lane_key, "lane_query": None, "topic_hint": None, "direction_hint": None,
            "upstream_item_id": "cmt-x", "upstream_story_id": None, "upstream_url": None,
            "original_url": None, "canonical_original_url": None, "published_at": None,
            "discovered_at": None, "retrieved_at": "2026-08-21", "retrieved_at_first": "2026-08-21",
            "etag": None, "title": None, "summary": None, "reason": None, "title_hash": None,
            "summary_hash": None, "raw_payload_json": None, "selected_for_radar": 0,
            "radar_id": None, "decision_reason": None, "created_at": "2026-08-21",
        }

    db.upsert_radar_upstream_records([row("r1", "all:t:d:q1"), row("r2", "all:t:d:q2")])
    rows = db.fetchall("SELECT record_id FROM radar_upstream_records WHERE run_id='run-m'")
    assert sorted(row["record_id"] for row in rows) == ["r1", "r2"]


def test_ledger_write_failure_keeps_collected_items(tmp_path: Path) -> None:
    shared = upstream_item("cmt-ok2", "可用的KV条目", "该条目摘要完整且来自精选 lane。", "https://example.com/ok2")
    http = FakeHttp(lane_responses(selected=[shared]))
    collector, db, _ = make_collector(http, tmp_path, run_id="run-ledger")

    def broken_upsert(self, rows):
        raise sqlite3.IntegrityError("simulated ledger failure")

    import briefing_skill.db as db_module

    original = db_module.Database.upsert_radar_upstream_records
    db_module.Database.upsert_radar_upstream_records = broken_upsert
    try:
        items = collector.collect()
    finally:
        db_module.Database.upsert_radar_upstream_records = original

    # The audit failure must not zero out the successfully collected items.
    assert [item.external_id for item in items] == ["cmt-ok2"]
    freeze_doc = json.loads(
        (collector.run_dir / "source-cache" / "aihot" / "freeze.json").read_text(encoding="utf-8")
    )
    assert "simulated ledger failure" in str(freeze_doc.get("ledger_error"))
