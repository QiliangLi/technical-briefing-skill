from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.publication_manifest import finalize_radar_groups
from briefing_skill.radar_direct import (
    direct_copy_enabled,
    direct_copy_groups,
    normalized_radar_candidates,
    select_public_summary,
    verify_copy_integrity,
)
from briefing_skill.utils import canonicalize_url, write_json

NOW = datetime.now(timezone.utc)
# Direct-copy freshness is measured against the active run report date, never
# the wall clock, so tests pin the reference to "today" of the test run.
REFERENCE_DATE = NOW.date().isoformat()


def _days_ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def make_service(tmp_path: Path, *, direct_copy: bool = True, total_max: int = 8, per_category: int = 2):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    service = SimpleNamespace(
        db=db,
        root=tmp_path,
        config=ConfigBundle(
            topics={
                "topics": [
                    {
                        "id": "tpn",
                        "name": "TPN",
                        "aihot_priority": "high",
                        "directions": [{"id": "kv", "aihot_queries": ["KV cache"]}],
                    }
                ]
            },
            sources={"sources": []},
            scoring={"radar": {"total_max": total_max, "max_per_category": per_category, "direct_copy": direct_copy}},
            settings={},
            email={},
        ),
        _topic_appendix_cache={},
    )
    service._normalise_reference = lambda value: "".join(ch.lower() for ch in str(value or "") if ch.isalnum())
    return service, db


def insert_raw(
    db: Database,
    run_id: str,
    *,
    url: str,
    title: str,
    summary: str,
    external_id: str = "",
    lanes: list[str] | None = None,
    story_id: str = "",
    age_days: float = 1,
    published_at: str | None = None,
    no_published_at: bool = False,
    source_id: str = "aihot",
    source_level: str = "B",
    topic_hint: str = "",
    raw_extra: dict[str, Any] | None = None,
    copy_variants: list[dict[str, Any]] | None = None,
    daily_date: str = "",
) -> str:
    from briefing_skill.utils import stable_hash

    raw_id = stable_hash(run_id, source_id, external_id, url, title)
    canonical = canonicalize_url(url)
    lanes = lanes or ["selected"]
    raw = {
        "id": external_id or raw_id,
        "title": title,
        "summary": summary,
        "score": 70,
        "links": {"aihot": f"https://aihot.virxact.com/items/{external_id or raw_id}", "original": url},
    }
    raw.update(raw_extra or {})
    payload = {
        "aihot": raw,
        "upstream_source": "Example（RSS）",
        "aihot_lane": lanes[0],
        "aihot_lanes": lanes,
        "aihot_canonical_original": canonical,
    }
    if story_id:
        payload["aihot_story_id"] = story_id
    if copy_variants is not None:
        payload["aihot_copy_variants"] = copy_variants
    if daily_date:
        payload["aihot_daily_date"] = daily_date
    db.execute(
        """
        INSERT OR IGNORE INTO raw_items(
            id, run_id, source_id, discovery_source, source_level, discovery_only,
            title, summary, original_url, aihot_url, canonical_url, published_at,
            discovered_at, authors_json, external_id, topic_hint, direction_hint,
            priority, content_hash, payload_json, created_at, identity_key
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id,
            run_id,
            source_id,
            "AI HOT",
            source_level,
            1,
            title,
            summary,
            url,
            f"https://aihot.virxact.com/items/{external_id or raw_id}",
            canonical,
            None if no_published_at else (published_at or _days_ago(age_days)),
            _days_ago(age_days),
            "[]",
            external_id,
            topic_hint,
            "",
            15.0,
            "hash",
            json.dumps(payload, ensure_ascii=False),
            _days_ago(0),
            canonical,
        ),
    )
    return raw_id


def seed_issue(db: Database, tmp_path: Path, run_id: str, issue_id: str) -> None:
    issue_dir = tmp_path / "workspace" / "runs" / run_id / "issue"
    issue_dir.mkdir(parents=True, exist_ok=True)
    write_json(issue_dir / "synthesis.json", {"judgements": [], "radar_signals": []})
    write_json(
        issue_dir / "issue.json",
        {"id": issue_id, "run_id": run_id, "synthesis": {"judgements": [], "radar_signals": []}},
    )
    db.execute(
        """
        INSERT INTO issues(id, run_id, status, date_from, date_to, synthesis_path,
                           issue_json_path, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            issue_id,
            run_id,
            "READY_FOR_RENDER",
            "2026-08-21",
            "2026-08-21",
            f"workspace/runs/{run_id}/issue/synthesis.json",
            f"workspace/runs/{run_id}/issue/issue.json",
            _days_ago(0),
            _days_ago(0),
        ),
    )


def test_direct_copy_selection_publishes_verbatim_records(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id, issue_id = "run-1", "issue-1"
    seed_issue(db, tmp_path, run_id, issue_id)

    insert_raw(
        db,
        run_id,
        url="https://example.com/kv",
        title="KVCache 跨节点预填调度器开源",
        summary="调度器把长尾预填请求偏转到解码节点分块执行，实测 SLO 维持到 9RPS。",
        external_id="cmt1",
        lanes=["selected", "daily", "hot"],
        story_id="story-1",
        topic_hint="tpn",
    )
    insert_raw(
        db,
        run_id,
        url="https://example.com/agent",
        title="开源 Agent harness 支持并行工具调用",
        summary="该 harness 在仓库级任务中并行执行工具调用并共享上下文缓存。",
        external_id="cmt2",
        lanes=["daily"],
    )
    insert_raw(
        db,
        run_id,
        url="https://example.com/nand",
        title="QLC 闪存阵列写入放大优化",
        summary="新控制器把 QLC 写入放大降到 1.2 倍，并保持读取延迟稳定。",
        external_id="cmt3",
        lanes=["all"],
    )
    # Out of scope: financing news even though it passed upstream selection.
    insert_raw(
        db,
        run_id,
        url="https://example.com/funding",
        title="某加速器公司宣布完成新一轮融资",
        summary="该公司宣布完成 10 亿元融资，估值大幅提升，引发市场关注。",
        external_id="cmt4",
        lanes=["selected"],
    )
    # Cross-period duplicate.
    db.execute(
        "INSERT INTO radar_history(canonical_url,normalized_title,last_pushed_at,issue_id) VALUES (?,?,?,?)",
        (canonicalize_url("https://example.com/old"), "旧条目", _days_ago(3), "issue-old"),
    )
    insert_raw(
        db,
        run_id,
        url="https://example.com/old",
        title="上周已发布的存储条目",
        summary="该存储条目上周已经进入热点雷达，本期不应重复出现。",
        external_id="cmt5",
        lanes=["selected"],
    )
    # English-only summary: no usable Chinese complete sentence.
    insert_raw(
        db,
        run_id,
        url="https://example.com/english",
        title="English-only inference runtime release",
        summary="An English abstract about an inference runtime with no Chinese sentences.",
        external_id="cmt6",
        lanes=["selected"],
    )

    issue_data = {"run_id": run_id, "id": issue_id, "items": [], "date_to": REFERENCE_DATE}
    groups = direct_copy_groups(service, issue_id, issue_data)
    assert groups is not None
    final_groups, contract = finalize_radar_groups(
        service, groups, issue_id=issue_id, issue_data=issue_data
    )
    items = [dict(item, category=group["name"]) for group in final_groups for item in group["items"]]
    urls = {item["url"] for item in items}

    assert urls == {"https://example.com/kv", "https://example.com/agent", "https://example.com/nand"}
    assert all("AI HOT" not in str(item["source_name"]) for item in items)
    assert all("virxact" not in str(item["source_name"]) for item in items)
    assert contract["final_count"] == 3

    for item in items:
        assert verify_copy_integrity(item) == []
        provenance = item["copy_provenance"]
        source = provenance["source_text"]
        public = item["summary"]
        assert source[provenance["selected_span_start"] : provenance["selected_span_end"]] == public
        assert public.endswith(("。", "！", "？"))

    rows = db.fetchall("SELECT * FROM issue_radar_items WHERE issue_id=?", (issue_id,))
    assert len(rows) == 3
    assert all("virxact" not in str(row["source_name"]) for row in rows)

    provenance_doc = json.loads(
        (tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json").read_text(encoding="utf-8")
    )
    assert provenance_doc["version"] == 1
    assert len(provenance_doc["items"]) == 3
    assert all(item["copy_provenance"]["source_field"] == "summary" for item in provenance_doc["items"])

    synthesis = json.loads(
        (tmp_path / "workspace" / "runs" / run_id / "issue" / "synthesis.json").read_text(encoding="utf-8")
    )
    assert {signal["source_urls"][0] for signal in synthesis["radar_signals"]} == urls
    assert all(set(signal) == {"category", "signal", "summary", "source_urls"} for signal in synthesis["radar_signals"])
    issue_doc = json.loads(
        (tmp_path / "workspace" / "runs" / run_id / "issue" / "issue.json").read_text(encoding="utf-8")
    )
    assert issue_doc["synthesis"]["radar_signals"] == synthesis["radar_signals"]

    records = db.list_radar_upstream_records(run_id)
    assert not records  # ledger rows come from collection; none seeded here


def test_long_summary_selects_complete_sentence_span(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-span"
    sentence_one = "第一句：" + "该预填缓存传输机制在跨节点场景下复用键值段落并降低调度开销，" * 8 + "实测收益显著。"
    sentence_two = "第二句：该实现依赖 RDMA 直连与分块调度器，在多租户集群中保持尾延迟稳定。"
    sentence_three = "第三句：局限性包括对稀疏注意力场景的适配尚未完成。"
    long_summary = sentence_one + sentence_two + sentence_three
    assert len(sentence_one) <= 260 < len(sentence_one + sentence_two)
    insert_raw(
        db,
        run_id,
        url="https://example.com/span",
        title="KV cache 跨节点复用降低首 token 延迟",
        summary=long_summary,
        external_id="cmt-span",
    )
    issue_data = {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE}
    candidates = normalized_radar_candidates(service, run_id, issue_data)
    assert len(candidates) == 1
    provenance = candidates[0]["copy_provenance"]
    public = candidates[0]["summary"]
    assert len(public) <= 260
    assert public.endswith("。")
    source_text = " ".join(long_summary.split())
    assert source_text[provenance["selected_span_start"] : provenance["selected_span_end"]] == public
    assert "第二句" not in public
    assert "第三句" not in public
    assert verify_copy_integrity(candidates[0]) == []


def test_select_public_summary_rejects_unusable_text() -> None:
    assert select_public_summary("English only summary with no Chinese.") is None
    assert select_public_summary("") is None
    dangling = select_public_summary("这是一个没有句号的悬空摘要，")
    assert dangling is None


def test_story_and_url_dedup_merge(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-dedup"
    # Same upstream item in two lanes with one URL.
    insert_raw(
        db, run_id, url="https://example.com/a", title="同一条目出现在多个栏目",
        summary="该 agent 条目同时出现在精选与日报中，栏目应合并且只算一条。",
        external_id="cmt-a", lanes=["selected"],
    )
    insert_raw(
        db, run_id, url="https://example.com/a-dup", title="同一条目出现在多个栏目（日报版）",
        summary="该 agent 条目同时出现在精选与日报中，栏目应合并且只算一条。日报补充说明。",
        external_id="cmt-a", lanes=["daily"],
    )
    # Same story, different original URLs: only one card may publish.
    insert_raw(
        db, run_id, url="https://example.com/story-a", title="同一事件的第一个报道：KV cache 扩容",
        summary="该报道描述 KV cache 分层扩容机制与实测收益，内容完整。",
        external_id="cmt-b1", story_id="story-9",
    )
    insert_raw(
        db, run_id, url="https://example.com/story-b", title="同一事件的第二个报道：KV cache 扩容跟进",
        summary="跟进报道补充了 KV cache 扩容的部署细节与限制条件。",
        external_id="cmt-b2", story_id="story-9",
    )
    candidates = normalized_radar_candidates(service, run_id, {"date_to": REFERENCE_DATE})
    by_url = {c["url"]: c for c in candidates}
    # Same story collapses to a single candidate (design §8.1) keeping the
    # stronger record; both original URLs never publish together.
    assert set(by_url) == {"https://example.com/a", "https://example.com/story-a"}
    assert set(by_url["https://example.com/a"]["upstream_lanes"]) == {"selected", "daily"}


def test_category_caps_and_diversity(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-caps"
    for index in range(5):
        insert_raw(
            db, run_id, url=f"https://example.com/infra-{index}",
            title=f"推理运行时优化 {index}",
            summary=f"该推理运行时通过内核融合降低调度开销，实测提升吞吐。",
            external_id=f"cmt-i{index}",
        )
    insert_raw(
        db, run_id, url="https://example.com/storage",
        title="NAND 闪存写入放大新方案",
        summary="该存储方案降低 NAND 写入放大并保持 QLC 延迟稳定。",
        external_id="cmt-s",
    )
    issue_data = {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE}
    groups = direct_copy_groups(service, None, issue_data)
    assert groups is not None
    counts: dict[str, int] = {}
    for group in groups:
        for _ in group["items"]:
            counts[group["name"]] = counts.get(group["name"], 0) + 1
    assert counts.get("AI Infra", 0) <= 2
    assert counts.get("存储与介质", 0) == 1
    assert sum(counts.values()) <= 8


def test_deep_url_collision_excluded_from_direct_pool(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-collide"
    insert_raw(
        db, run_id, url="https://example.com/deep-covered",
        title="已被深度条目覆盖的 agent 条目",
        summary="该 agent 条目的原始链接已进入本期深度正文，雷达不得重复占位。",
        external_id="cmt-d1",
    )
    insert_raw(
        db, run_id, url="https://example.com/fresh",
        title="未被覆盖的推理调度条目",
        summary="该推理调度条目只在雷达出现，摘要为完整中文句子。",
        external_id="cmt-d2",
    )
    issue_data = {
        "run_id": run_id,
        "date_to": REFERENCE_DATE,
        "items": [{"sources": [{"url": "https://example.com/deep-covered"}]}],
    }
    groups = direct_copy_groups(service, None, issue_data)
    assert groups is not None
    urls = {item["url"] for group in groups for item in group["items"]}
    assert urls == {"https://example.com/fresh"}


def test_direct_copy_deterministic_and_idempotent(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id, issue_id = "run-idem", "issue-idem"
    seed_issue(db, tmp_path, run_id, issue_id)
    insert_raw(
        db, run_id, url="https://example.com/x1", title="确定性条目一：KV cache",
        summary="第一条 KV cache 完整中文摘要句子。", external_id="cmt-x1",
    )
    insert_raw(
        db, run_id, url="https://example.com/x2", title="确定性条目二：agent 调度",
        summary="第二条 agent 调度完整中文摘要句子。", external_id="cmt-x2",
    )

    issue_data = {"run_id": run_id, "id": issue_id, "items": [], "date_to": REFERENCE_DATE}
    first_groups = direct_copy_groups(service, issue_id, issue_data)
    finalize_radar_groups(service, first_groups, issue_id=issue_id, issue_data=issue_data)
    provenance_path = tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    first_snapshot = provenance_path.read_text(encoding="utf-8")

    second_groups = direct_copy_groups(service, issue_id, issue_data)
    finalize_radar_groups(service, second_groups, issue_id=issue_id, issue_data=issue_data)
    assert provenance_path.read_text(encoding="utf-8") == first_snapshot
    assert json.dumps(first_groups, ensure_ascii=False, sort_keys=True) == json.dumps(
        second_groups, ensure_ascii=False, sort_keys=True
    )
    rows = db.fetchall("SELECT canonical_url FROM issue_radar_items WHERE issue_id=?", (issue_id,))
    assert len(rows) == len({row["canonical_url"] for row in rows}) == 2


def test_direct_copy_disabled_falls_back(tmp_path: Path) -> None:
    service, db = make_service(tmp_path, direct_copy=False)
    assert direct_copy_enabled(service) is False
    assert direct_copy_groups(service, None, {"run_id": "run-x", "items": []}) is None


def _direct_run(tmp_path: Path, run_id="run-p1"):
    service, db = make_service(tmp_path)
    return service, db, {"run_id": run_id, "id": "issue-p1", "items": [], "date_to": REFERENCE_DATE}


def test_missing_report_date_fails_closed(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    with pytest.raises(ValueError, match="report date"):
        normalized_radar_candidates(service, "run-x", {"run_id": "run-x", "items": []})


def test_freshness_uses_report_date_not_wall_clock(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    # Six days before the report date: inside the window even though the wall
    # clock may move; eight days: outside regardless of the wall clock.
    insert_raw(db, run_id, url="https://example.com/six-day", title="六天前的推理调度条目",
               summary="六天前的完整中文摘要句子，内容保持完整。", external_id="cmt-6", age_days=6)
    insert_raw(db, run_id, url="https://example.com/eight-day", title="八天前的存储介质条目",
               summary="八天前的完整中文摘要句子，内容保持完整。", external_id="cmt-8", age_days=8)
    issue_data = {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE}
    first = normalized_radar_candidates(service, run_id, issue_data)
    second = normalized_radar_candidates(service, run_id, issue_data)
    assert [c["url"] for c in first] == ["https://example.com/six-day"]
    # Same frozen input + same report date => byte-identical replay.
    assert [c["summary"] for c in first] == [c["summary"] for c in second]
    # An earlier report date moves both items inside the window: the pinned
    # reference date, never the wall clock, decides freshness.
    earlier = (NOW - timedelta(days=6)).date().isoformat()
    widened = normalized_radar_candidates(
        service, run_id, {"run_id": run_id, "items": [], "date_to": earlier}
    )
    assert [c["url"] for c in widened] == ["https://example.com/six-day", "https://example.com/eight-day"]


def test_oversized_title_is_dropped_not_truncated(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    long_title = "超长标题条目：" + "该推理调度机制持续降低尾延迟并优化吞吐表现，" * 12
    assert len(long_title) > 160
    insert_raw(db, run_id, url="https://example.com/long-title", title=long_title,
               summary="该条目标题超过公开上限，应整条淘汰而不是按字符截断。", external_id="cmt-long")
    candidates = normalized_radar_candidates(service, run_id, {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE})
    assert candidates == []


def test_reason_field_is_never_public_copy(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    insert_raw(
        db, run_id, url="https://example.com/reason-only", title="只有推荐理由的推理条目",
        summary="上游编辑推荐理由被错误地放进摘要字段位置。", external_id="cmt-reason",
        raw_extra={"reason": "上游编辑推荐理由被错误地放进摘要字段位置。", "summary": None},
    )
    # The adapter never promotes `reason` into the summary; simulate the raw
    # row that only carries a reason and confirm the copy contract rejects it.
    from briefing_skill.radar_direct import verify_copy_integrity

    fake_item = {
        "title": "只有推荐理由的推理条目",
        "summary": "上游编辑推荐理由被错误地放进摘要字段位置。",
        "title_provenance": {"source_text": "只有推荐理由的推理条目", "selected_span_start": 0, "selected_span_end": 11, "public_text_hash": None},
        "copy_provenance": {"source_field": "reason", "source_text": "上游编辑推荐理由被错误地放进摘要字段位置。",
                            "selected_span_start": 0, "selected_span_end": 20, "public_text_hash": None},
    }
    errors = verify_copy_integrity(fake_item)
    assert any("reason" in error for error in errors)


def test_upstream_domain_or_relative_url_never_public(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    # Row whose only URL is the upstream item page (observation-only upstream).
    insert_raw(db, run_id, url="", title="只有上游链接的观察条目", summary="该条目只有上游链接，不能公开。",
               external_id="cmt-upstream", source_id="aihot")
    candidates = normalized_radar_candidates(service, run_id, {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE})
    assert all("virxact" not in c["url"] for c in candidates)
    assert all(c["url"].startswith("http") for c in candidates)


def test_cross_period_story_identity_blocks_republish(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    # Last issue published the same story under a different report URL/title.
    db.execute(
        "INSERT INTO radar_history(canonical_url,normalized_title,last_pushed_at,issue_id,upstream_item_id,story_id) VALUES (?,?,?,?,?,?)",
        ("https://example.org/old-report", "旧报道标题", "2026-08-20", "issue-old", None, "story-42"),
    )
    insert_raw(db, run_id, url="https://example.com/new-report", title="同一事件的新报道：KV cache 扩容",
               summary="跟进报道描述同一事件的部署细节与限制条件，内容完整。",
               external_id="cmt-new", story_id="story-42")
    candidates = normalized_radar_candidates(service, run_id, {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE})
    assert all(c["story_id"] != "story-42" for c in candidates)


def test_variant_fallback_rescues_chinese_summary(tmp_path: Path) -> None:
    service, db, _ = _direct_run(tmp_path)
    run_id = "run-p1"
    # High-priority all-lane row carries an English summary; the selected lane
    # variant for the same item is usable Chinese — direct copy must fall back.
    chinese = "调度器把长尾预填请求偏转到解码节点分块执行，实测收益显著。"
    db.execute(
        """
        INSERT OR IGNORE INTO raw_items(
            id, run_id, source_id, discovery_source, source_level, discovery_only,
            title, summary, original_url, aihot_url, canonical_url, published_at,
            discovered_at, authors_json, external_id, topic_hint, direction_hint,
            priority, content_hash, payload_json, created_at, identity_key
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "raw-variant", run_id, "aihot", "AI HOT", "B", 1,
            "KVCache 跨节点预填调度器开源",
            "An English abstract with no Chinese sentence for the same item.",
            "https://example.com/variant", "https://aihot.virxact.com/items/cmt-v",
            "https://example.com/variant", _days_ago(1), _days_ago(1), "[]", "cmt-v", "tpn", "kv",
            99.0, "hash",
            json.dumps({
                "aihot": {"id": "cmt-v", "title": "KVCache 跨节点预填调度器开源",
                          "summary": "An English abstract with no Chinese sentence for the same item.",
                          "links": {"original": "https://example.com/variant"}},
                "upstream_source": "Example（RSS）", "aihot_lane": "all", "aihot_lanes": ["selected", "all"],
                "aihot_canonical_original": "https://example.com/variant",
                "aihot_copy_variants": [
                    {"lane": "all", "source_field": "summary", "summary": "An English abstract with no Chinese sentence for the same item."},
                    {"lane": "selected", "source_field": "summary", "summary": chinese},
                ],
            }, ensure_ascii=False),
            _days_ago(0), "https://example.com/variant",
        ),
    )
    candidates = normalized_radar_candidates(service, run_id, {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE})
    assert len(candidates) == 1
    assert candidates[0]["summary"] == chinese
    assert candidates[0]["copy_provenance"]["source_field"] == "summary"


def _radar_html(final_groups) -> str:
    parts = ['<html><body>']
    for group in final_groups:
        parts.append(
            f'<div data-reader-role="radar-card" data-radar-category="{group["name"]}">'
        )
        for item in group["items"]:
            date_segment = f'{item.get("published_at") or ""} · ' if item.get("published_at") else ""
            parts.append(
                '<div data-reader-role="radar-item">'
                f'<a href="{item["url"]}">{item["title"]}</a>'
                f'<div data-reader-role="radar-summary">{item["summary"]}</div>'
                f'<div>{date_segment}阅读原文：<a href="{item["url"]}">{item.get("source_name") or ""}</a></div>'
                "</div>"
            )
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def _write_config_tree(root: Path, *, direct_copy: bool) -> None:
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "topics.yaml").write_text("topics: []\n", encoding="utf-8")
    (config / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    (config / "settings.yaml").write_text("{}\n", encoding="utf-8")
    (config / "email.yaml").write_text("{}\n", encoding="utf-8")
    (config / "scoring.yaml").write_text(
        f"radar:\n  total_max: 8\n  max_per_category: 2\n  direct_copy: {str(direct_copy).lower()}\n",
        encoding="utf-8",
    )


def test_release_gate_verifies_dom_summary_and_title_provenance(tmp_path: Path) -> None:
    from briefing_skill.publication_manifest import (
        publication_provenance_errors,
        write_publication_manifest,
    )

    service, db = make_service(tmp_path)
    run_id, issue_id = "run-gate", "issue-gate"
    seed_issue(db, tmp_path, run_id, issue_id)
    summary = "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。"
    title = "推理调度器开源发布"
    raw_item = {
        "id": "cmt-gate",
        "title": title,
        "summary": summary,
        "links": {
            "aihot": "https://aihot.virxact.com/items/cmt-gate",
            "original": "https://example.com/gate",
        },
    }
    # The real frozen input: the release gate anchors every public character
    # back to this file, not to radar-direct's own claims.
    freeze_dir = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    write_json(
        freeze_dir / "freeze.json",
        {
            "connector_version": 3,
            "run_id": run_id,
            "lane_plan_hash": "plan",
            "lanes": {
                "selected": {
                    "url": "https://aihot.virxact.com/api/v1/items?mode=selected",
                    "payload": {"items": [raw_item]},
                }
            },
        },
    )
    insert_raw(
        db, run_id, url="https://example.com/gate", title=title,
        summary=summary, external_id="cmt-gate",
    )
    issue_data = {"run_id": run_id, "id": issue_id, "items": [], "date_to": REFERENCE_DATE}
    groups = direct_copy_groups(service, issue_id, issue_data)
    final_groups, contract = finalize_radar_groups(
        service, groups, issue_id=issue_id, issue_data=issue_data
    )
    write_publication_manifest(service, issue_data, final_groups, contract)
    html = _radar_html(final_groups)

    assert publication_provenance_errors(tmp_path, run_id, html) == []

    tampered_summary = html.replace(summary, "模型重新改写过的全新文案，引入了上游没有的判断。")
    errors = publication_provenance_errors(tmp_path, run_id, tampered_summary)
    assert any("does not match the frozen copy provenance" in error for error in errors)

    tampered_title = html.replace(title, title + "（改）")
    errors = publication_provenance_errors(tmp_path, run_id, tampered_title)
    assert any("does not match the frozen title provenance" in error for error in errors)

    # Adversarial joint tamper: radar-direct and the DOM are made mutually
    # consistent with a brand-new text, but the frozen input, the selection
    # hash and the manifest still describe the original copy.
    forged = "一段完全自洽但从未被冻结过的联合篡改文案，包含完整中文句子。"
    provenance_path = tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    document = json.loads(provenance_path.read_text(encoding="utf-8"))
    from briefing_skill.utils import content_hash

    for item in document["items"]:
        item["summary"] = forged
        item["copy_provenance"]["source_text"] = forged
        item["copy_provenance"]["source_text_hash"] = f"sha256:{content_hash(forged)}"
        item["copy_provenance"]["public_text_hash"] = f"sha256:{content_hash(forged)}"
        item["copy_provenance"]["selected_span_start"] = 0
        item["copy_provenance"]["selected_span_end"] = len(forged)
    provenance_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    card_start = html.find('<div data-reader-role="radar-card"')
    forged_html = html[:card_start] + (
        '<div data-reader-role="radar-card" data-radar-category="AI Infra">'
        '<div data-reader-role="radar-item">'
        f'<a href="https://example.com/gate">{title}</a>'
        f'<div data-reader-role="radar-summary">{forged}</div>'
        "</div></div>"
    ) + html[html.find("</body>"):]
    errors = publication_provenance_errors(tmp_path, run_id, forged_html)
    assert any("differs from every frozen field" in error for error in errors), errors
    assert any("selection hash does not match" in error for error in errors), errors
    assert any("manifest summary hash disagrees" in error for error in errors), errors

    # A duplicated card cannot hide behind set semantics.
    card = html[html.find('<div data-reader-role="radar-card"'):html.find("</body>")]
    duplicated = html.replace(card, card + card, 1)
    errors = publication_provenance_errors(tmp_path, run_id, duplicated)
    assert any("multiplicity" in error or "final_count" in error for error in errors), errors

    # With a readable config in direct mode a missing provenance record is a
    # hard release failure, not a silent pass.
    provenance_path.unlink()
    _write_config_tree(tmp_path, direct_copy=True)
    errors = publication_provenance_errors(tmp_path, run_id, html)
    assert any("provenance record is missing" in error for error in errors)




def test_report_date_interpreted_in_configured_timezone(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-tz"
    # 2026-08-14 00:30 Shanghai == 2026-08-13 16:30 UTC. Against the report
    # day 2026-08-21 this is 7 days at Shanghai day-end (kept) but 8 days if
    # the bare date were interpreted as UTC day-end (wrongly dropped).
    insert_raw(
        db, run_id, url="https://example.com/tz-edge", title="时区边界条目：KV cache 扩容",
        summary="该条目在上海时间凌晨发布，应按配置时区日末计算新鲜度。",
        external_id="cmt-tz", published_at="2026-08-14T00:30:00+08:00",
    )
    candidates = normalized_radar_candidates(
        service, run_id, {"run_id": run_id, "items": [], "date_to": "2026-08-21"}
    )
    assert [c["url"] for c in candidates] == ["https://example.com/tz-edge"]
    assert candidates[0]["age_days"] == 7


def test_invalid_timezone_or_report_date_fails_closed(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    service.config.settings["timezone"] = "Not/AZone"
    insert_raw(db, "run-tz-bad", url="https://example.com/x", title="推理条目：调度器",
               summary="完整中文摘要句子，用于触发新鲜度计算路径。", external_id="cmt-tz2")
    with pytest.raises(ValueError, match="timezone"):
        normalized_radar_candidates(
            service, "run-tz-bad", {"run_id": "run-tz-bad", "items": [], "date_to": "2026-08-21"}
        )
    service2, _ = make_service(tmp_path)
    with pytest.raises(ValueError, match="report date"):
        normalized_radar_candidates(
            service2, "run-tz-bad", {"run_id": "run-tz-bad", "items": [], "date_to": "2026/08/21"}
        )


def test_site_root_url_is_not_a_specific_original_page(tmp_path: Path) -> None:
    service, db = make_service(tmp_path)
    run_id = "run-root"
    insert_raw(db, run_id, url="https://example.com", title="只有站点根地址的条目：推理调度",
               summary="该条目只提供站点首页，没有具体原始页面。", external_id="cmt-root")
    insert_raw(db, run_id, url="https://example.com/page", title="有具体页面的条目：推理调度",
               summary="该条目提供了具体的原始页面链接，可以公开。", external_id="cmt-page")
    candidates = normalized_radar_candidates(
        service, run_id, {"run_id": run_id, "items": [], "date_to": REFERENCE_DATE}
    )
    assert [c["url"] for c in candidates] == ["https://example.com/page"]


def _build_release_chain(tmp_path: Path, *, freeze_lanes: dict, raw_rows: list[dict]):
    """Full finalize + manifest chain over the given frozen input and raw rows."""
    from briefing_skill.publication_manifest import (
        publication_provenance_errors,
        write_publication_manifest,
    )

    service, db = make_service(tmp_path)
    run_id, issue_id = "run-chain", "issue-chain"
    seed_issue(db, tmp_path, run_id, issue_id)
    freeze_dir = tmp_path / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    write_json(
        freeze_dir / "freeze.json",
        {"connector_version": 3, "run_id": run_id, "lane_plan_hash": "plan", "lanes": freeze_lanes},
    )
    for row in raw_rows:
        insert_raw(db, run_id, **row)
    issue_data = {"run_id": run_id, "id": issue_id, "items": [], "date_to": REFERENCE_DATE}
    groups = direct_copy_groups(service, issue_id, issue_data)
    final_groups, contract = finalize_radar_groups(
        service, groups, issue_id=issue_id, issue_data=issue_data
    )
    write_publication_manifest(service, issue_data, final_groups, contract)
    html = _radar_html(final_groups)
    return service, db, run_id, final_groups, html, publication_provenance_errors


def test_daily_only_radar_passes_release_gate(tmp_path: Path) -> None:
    # Reviewer repro: a legitimate daily-only item passes collection and
    # selection but the freeze lookup only read top-level items, so the gate
    # wrongly rejected it. Daily payloads nest under report.sections[].items.
    title = "投机解码草稿模型推理提速三倍"
    summary = "通过投机解码在不改变输出质量的前提下提升 GPU 吞吐，草稿模型约三亿参数。"
    entry = {
        "title": title,
        "summary": summary,
        "links": {
            "aihot": "https://aihot.virxact.com/items/cmt-daily",
            "original": "https://huggingface.co/blog/dspark",
        },
    }
    service, db, run_id, final_groups, html, gate = _build_release_chain(
        tmp_path,
        freeze_lanes={
            "daily": {
                "url": "https://aihot.virxact.com/api/v1/dailies/latest",
                "payload": {"report": {"date": REFERENCE_DATE, "sections": [{"label": "模型发布/更新", "items": [entry]}]}},
            }
        },
        raw_rows=[
            {
                "url": "https://huggingface.co/blog/dspark",
                "title": title,
                "summary": summary,
                "external_id": "cmt-daily",
                "lanes": ["daily"],
                "no_published_at": True,
                "daily_date": REFERENCE_DATE,
            }
        ],
    )
    assert gate(tmp_path, run_id, html) == []
    assert final_groups


def test_cross_lane_chinese_fallback_passes_release_gate(tmp_path: Path) -> None:
    # Reviewer repro: selected carries an English summary, a later lane the
    # usable Chinese copy; the gate used to anchor to the first identity
    # match (English) and reject the Chinese fallback.
    title = "KVCache 跨节点预填调度器开源"
    english = "An English abstract with no complete Chinese sentence."
    chinese = "调度器把长尾预填请求偏转到解码节点分块执行，实测收益显著。"
    original = "https://example.com/multi"
    service, db, run_id, final_groups, html, gate = _build_release_chain(
        tmp_path,
        freeze_lanes={
            "selected": {"url": "s", "payload": {"items": [
                {"id": "cmt-multi", "title": title, "summary": english,
                 "links": {"aihot": "https://aihot.virxact.com/items/cmt-multi", "original": original}}
            ]}},
            "all:tpn:kv:q": {"url": "a", "payload": {"items": [
                {"id": "cmt-multi", "title": title, "summary": chinese,
                 "links": {"aihot": "https://aihot.virxact.com/items/cmt-multi", "original": original}}
            ]}},
        },
        raw_rows=[
            {
                "url": original,
                "title": title,
                "summary": english,
                "external_id": "cmt-multi",
                "lanes": ["selected", "all"],
                "copy_variants": [
                    {"lane": "selected", "lane_key": "selected", "source_field": "summary", "summary": english},
                    {"lane": "all", "lane_key": "all:tpn:kv:q", "source_field": "summary", "summary": chinese},
                ],
            }
        ],
    )
    item = final_groups[0]["items"][0]
    assert item["summary"] == chinese
    assert item["copy_provenance"]["lane_key"] == "all:tpn:kv:q"
    assert gate(tmp_path, run_id, html) == []




def test_missing_hashes_and_category_joint_rewrite_fail_closed(tmp_path: Path) -> None:
    from briefing_skill.radar_direct import recompute_selection_hash
    from briefing_skill.utils import read_json as load_json

    title = "推理调度器开源发布"
    summary = "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。"
    original = "https://example.com/chain"
    raw = {"id": "cmt-chain", "title": title, "summary": summary,
           "links": {"aihot": "https://aihot.virxact.com/items/cmt-chain", "original": original}}
    service, db, run_id, final_groups, html, gate = _build_release_chain(
        tmp_path,
        freeze_lanes={"selected": {"url": "s", "payload": {"items": [raw]}}},
        raw_rows=[{"url": original, "title": title, "summary": summary, "external_id": "cmt-chain"}],
    )
    assert gate(tmp_path, run_id, html) == []

    provenance_path = tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    manifest_path = tmp_path / "workspace" / "runs" / run_id / "publication-manifest.json"

    # Jointly rewriting the manifest AND DOM category while radar-direct and
    # the selection hash keep the old category must fail.
    manifest = load_json(manifest_path, {})
    manifest["radar"][0]["category"] = "存储与介质"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    joint_html = html.replace('data-radar-category="AI Infra"', 'data-radar-category="存储与介质"')
    errors = gate(tmp_path, run_id, joint_html)
    assert any("category in HTML does not match radar-direct" in error for error in errors), errors

    # Restore the manifest category before the next scenario.
    manifest = load_json(manifest_path, {})
    manifest["radar"][0]["category"] = "AI Infra"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    # Duplicating a direct record with a legitimately recomputed selection
    # hash still fails on layer counts / duplicate identity.
    document = load_json(provenance_path, {})
    duplicated = dict(document["items"][0])
    duplicated["radar_id"] = duplicated["radar_id"] + "-copy"
    document["items"].append(duplicated)
    document["selection_hash"] = recompute_selection_hash(document)
    provenance_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    errors = gate(tmp_path, run_id, html)
    assert any("layers disagree on records" in error for error in errors), errors

    # Deleting required hash fields is a failure, not "nothing to check".
    document = load_json(provenance_path, {})
    del document["selection_hash"]
    provenance_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    errors = gate(tmp_path, run_id, html)
    assert any("missing required field 'selection_hash'" in error for error in errors)

    document = load_json(provenance_path, {})
    del document["frozen_input_sha256"]
    provenance_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    errors = gate(tmp_path, run_id, html)
    assert any("missing required field 'frozen_input_sha256'" in error for error in errors)


def test_empty_radar_state_rejects_injected_cards(tmp_path: Path) -> None:
    # Reviewer repro: a legitimately-empty direct document plus one injected
    # manifest+DOM card used to pass because empty layers skipped comparison.
    import shutil

    from briefing_skill.radar_direct import recompute_selection_hash
    from briefing_skill.utils import read_json as load_json

    service, db, run_id, final_groups, html, gate = _build_release_chain(
        tmp_path,
        freeze_lanes={"selected": {"url": "s", "payload": {"items": []}}},
        raw_rows=[],
    )
    assert final_groups == []
    assert gate(tmp_path, run_id, html) == []

    manifest_path = tmp_path / "workspace" / "runs" / run_id / "publication-manifest.json"
    provenance_path = tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    injected_html = (
        '<html><body><div data-reader-role="radar-card" data-radar-category="AI Infra">'
        '<div data-reader-role="radar-item"><a href="https://example.com/injected">注入卡片</a>'
        '<div data-reader-role="radar-summary">一段没有任何冻结来源的注入摘要。</div></div></div></body></html>'
    )
    manifest = load_json(manifest_path, {})
    manifest["radar"].append(
        {"radar_id": "radar-x", "category": "AI Infra", "title": "注入卡片",
         "source_name": "example.com", "urls": ["https://example.com/injected"],
         "summary_sha256": "sha256:x"}
    )
    manifest["radar_contract"]["final_count"] = 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    errors = gate(tmp_path, run_id, injected_html)
    assert any("layers disagree" in error for error in errors), errors

    # Clearing a non-empty direct document and recomputing its hash must not
    # let the original manifest/DOM cards through either.
    service, db, run_id2, final_groups2, html2, gate2 = _build_release_chain(
        tmp_path / "shadow-empty",
        freeze_lanes={"selected": {"url": "s", "payload": {"items": [
            {"id": "cmt-e", "title": "推理调度器开源发布", "summary": "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。",
             "links": {"aihot": "https://aihot.virxact.com/items/cmt-e", "original": "https://example.com/e"}}
        ]}}},
        raw_rows=[{"url": "https://example.com/e", "title": "推理调度器开源发布",
                   "summary": "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。", "external_id": "cmt-e"}],
    )
    assert gate2(tmp_path / "shadow-empty", run_id2, html2) == []
    provenance2 = tmp_path / "shadow-empty" / "workspace" / "runs" / run_id2 / "issue" / "radar-direct.json"
    document = load_json(provenance2, {})
    document["items"] = []
    document["selection_contract"]["final_count"] = 0
    document["selection_hash"] = recompute_selection_hash(document)
    provenance2.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    errors = gate2(tmp_path / "shadow-empty", run_id2, html2)
    assert any("layers disagree" in error for error in errors), errors


def test_copied_run_directory_cannot_replay_into_another_run(tmp_path: Path) -> None:
    import shutil

    title = "推理调度器开源发布"
    summary = "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。"
    original = "https://example.com/replay"
    raw = {"id": "cmt-replay", "title": title, "summary": summary,
           "links": {"aihot": "https://aihot.virxact.com/items/cmt-replay", "original": original}}
    root_a = tmp_path / "run-a-root"
    service, db, run_a, final_groups, html, gate = _build_release_chain(
        root_a,
        freeze_lanes={"selected": {"url": "s", "payload": {"items": [raw]}}},
        raw_rows=[{"url": original, "title": title, "summary": summary, "external_id": "cmt-replay"}],
    )
    assert gate(root_a, run_a, html) == []

    # Copy run A's ENTIRE artifact set into a run-B directory: internally
    # consistent files from another run must not validate against run B.
    root_b = tmp_path / "run-b-root"
    (root_b / "workspace" / "runs").mkdir(parents=True)
    shutil.copytree(root_a / "workspace" / "runs" / run_a, root_b / "workspace" / "runs" / "run-B")
    errors = gate(root_b, "run-B", html)
    assert any("belongs to another run" in error for error in errors), errors


def test_tampered_rule_version_fails(tmp_path: Path) -> None:
    from briefing_skill.utils import read_json as load_json

    title = "推理调度器开源发布"
    summary = "该推理调度器把长尾请求偏转到空闲解码节点，实测收益显著。"
    original = "https://example.com/ver"
    raw = {"id": "cmt-ver", "title": title, "summary": summary,
           "links": {"aihot": "https://aihot.virxact.com/items/cmt-ver", "original": original}}
    service, db, run_id, final_groups, html, gate = _build_release_chain(
        tmp_path,
        freeze_lanes={"selected": {"url": "s", "payload": {"items": [raw]}}},
        raw_rows=[{"url": original, "title": title, "summary": summary, "external_id": "cmt-ver"}],
    )
    assert gate(tmp_path, run_id, html) == []
    provenance_path = tmp_path / "workspace" / "runs" / run_id / "issue" / "radar-direct.json"
    document = load_json(provenance_path, {})
    document["radar_taxonomy_version"] = 999
    provenance_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    errors = gate(tmp_path, run_id, html)
    assert any("newer than this code supports" in error for error in errors), errors
    assert any("selection hash does not match" in error for error in errors), errors
