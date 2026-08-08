from pathlib import Path

import pytest

from briefing_skill.db import Database
from briefing_skill.human_feedback import (
    EDITABLE_FIELDS,
    build_review_payload,
    human_feedback_stats,
    prepare_reviewed_items,
    record_human_review,
)
from briefing_skill.paths import Paths
from briefing_skill.utils import now_iso, read_json, write_json


def _item(title: str, mechanism: str) -> dict:
    return {
        "title": title,
        "type": "论文",
        "topic_name": "测试专题",
        "published_at": "2026-08-08",
        "score": 88,
        "core_conclusion": f"{title}给出了一项可核验的系统结论。",
        "mechanism": mechanism,
        "result": "实验结果显示端到端指标改善。",
        "boundary": "结论仅适用于给定负载和部署条件。",
        "project_relevance": "该证据可用于收窄当前项目判断边界。",
        "sources": [{"publisher": "Primary", "url": "https://example.com/source"}],
        "visual_plan": {"visual_mode": "text_only", "visual_purpose": "测试"},
    }


def _seed(tmp_path: Path):
    root = tmp_path
    paths = Paths(root)
    paths.ensure()
    run_id = "run-review"
    run_dir = paths.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    db = Database(paths.db)
    db.init()
    now = now_iso()
    db.create_run(run_id, "AWAITING_APPROVAL")

    items = {
        "item-1": _item("KV-aware scheduling", "调度器联合考虑KVCache位置与链路带宽。"),
        "item-2": _item("Inline offload", "DPU在数据路径上完成随路处理。"),
    }
    topics = {"item-1": "tpn", "item-2": "dpu_inline"}
    for index, (item_id, item) in enumerate(items.items(), 1):
        event_id = f"event-{index}"
        json_path = run_dir / "items" / f"{item_id}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(json_path, item)
        db.execute(
            """
            INSERT INTO events(
                id,topic_id,direction_id,canonical_title,fingerprint,score,
                first_seen_at,last_updated_at,payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (event_id, topics[item_id], "d1", item["title"], event_id, 88, now, now, "{}"),
        )
        db.execute(
            """
            INSERT INTO brief_items(
                id,run_id,event_id,json_path,score,fact_check_status,approved,created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (item_id, run_id, event_id, str(json_path.relative_to(root)), 88, "PASS", 0, now),
        )

    synthesis_path = run_dir / "synthesis.json"
    issue_path = run_dir / "issue.json"
    write_json(synthesis_path, {"headline": "测试", "judgements": []})
    write_json(
        issue_path,
        {
            "id": "issue-1",
            "run_id": run_id,
            "date_from": "2026-08-08",
            "date_to": "2026-08-08",
            "layout_mode": "expanded_v2",
            "synthesis": {"headline": "测试", "judgements": []},
            "items": [
                {**items["item-1"], "brief_item_id": "item-1", "topic_id": "tpn"},
                {**items["item-2"], "brief_item_id": "item-2", "topic_id": "dpu_inline"},
            ],
        },
    )
    db.execute(
        """
        INSERT INTO issues(
            id,run_id,status,date_from,date_to,synthesis_path,issue_json_path,
            created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "issue-1",
            run_id,
            "AWAITING_APPROVAL",
            "2026-08-08",
            "2026-08-08",
            str(synthesis_path.relative_to(root)),
            str(issue_path.relative_to(root)),
            now,
            now,
        ),
    )
    for position, item_id in enumerate(items, 1):
        db.execute(
            "INSERT INTO issue_items(issue_id,brief_item_id,position,item_role) VALUES (?,?,?,?)",
            ("issue-1", item_id, position, "core"),
        )
    return root, db, run_id, items, issue_path


def test_human_edit_uses_sidecar_and_never_mutates_agent_json(tmp_path):
    root, db, run_id, items, _ = _seed(tmp_path)
    original_path = root / "workspace" / "runs" / run_id / "items" / "item-1.json"
    before = read_json(original_path)

    prepared = prepare_reviewed_items(
        root,
        db,
        run_id,
        {
            "item-1": {
                "mechanism": "调度器联合考虑KVCache位置、剩余链路带宽和请求优先级。",
                "project_relevance": "这条证据只支持在状态可见时采用网络侧联合调度。",
            }
        },
    )

    assert read_json(original_path) == before == items["item-1"]
    assert set(prepared["item-1"]["diffs"]) == {"mechanism", "project_relevance"}
    sidecar = root / prepared["item-1"]["reviewed_item_path"]
    assert sidecar.exists()
    reviewed = read_json(sidecar)
    assert "剩余链路带宽" in reviewed["mechanism"]


def test_validated_review_records_selection_and_field_level_diffs(tmp_path):
    root, db, run_id, _, _ = _seed(tmp_path)
    prepared = prepare_reviewed_items(
        root,
        db,
        run_id,
        {"item-1": {"mechanism": "人工修改后的机制描述。", "boundary": "人工收窄后的边界条件。"}},
    )
    record_human_review(db, run_id, {"item-1"}, prepared)

    stats = human_feedback_stats(db, run_id)["current_run"]
    assert stats["reviewed_items"] == 2
    assert stats["approved_items"] == 1
    assert stats["rejected_items"] == 1
    assert stats["approval_rate"] == 0.5
    assert stats["approved_items_with_edits"] == 1
    assert stats["approved_fields_total"] == len(EDITABLE_FIELDS)
    assert stats["approved_fields_changed"] == 2
    assert stats["approved_field_edit_rate"] == round(2 / len(EDITABLE_FIELDS), 4)
    assert stats["by_field"]["mechanism"]["changed"] == 1
    assert stats["by_field"]["boundary"]["changed"] == 1
    assert stats["by_topic"]["tpn"]["edited_approved"] == 1
    assert stats["by_topic"]["dpu_inline"]["rejected"] == 1


def test_reopen_review_restores_rejected_candidates_and_latest_edits(tmp_path):
    root, db, run_id, _, issue_path = _seed(tmp_path)
    prepared = prepare_reviewed_items(
        root,
        db,
        run_id,
        {"item-1": {"core_conclusion": "人工审核后的核心结论。"}},
    )
    record_human_review(db, run_id, {"item-1"}, prepared)

    # Simulate the post-approval issue JSON containing only approved items.
    filtered = read_json(issue_path)
    filtered["items"] = [item for item in filtered["items"] if item["brief_item_id"] == "item-1"]
    write_json(issue_path, filtered)

    payload = build_review_payload(root, db, run_id)
    assert [item["brief_item_id"] for item in payload["items"]] == ["item-1", "item-2"]
    first, second = payload["items"]
    assert first["core_conclusion"] == "人工审核后的核心结论。"
    assert first["review_checked"] is True
    assert second["review_checked"] is False


def test_reset_to_agent_text_removes_sidecar_and_diff(tmp_path):
    root, db, run_id, items, _ = _seed(tmp_path)
    prepared = prepare_reviewed_items(
        root,
        db,
        run_id,
        {"item-1": {"mechanism": "一次人工修改。"}},
    )
    sidecar = root / prepared["item-1"]["reviewed_item_path"]
    assert sidecar.exists()

    reset = prepare_reviewed_items(
        root,
        db,
        run_id,
        {"item-1": {"mechanism": items["item-1"]["mechanism"]}},
    )
    assert reset["item-1"]["diffs"] == {}
    assert reset["item-1"]["reviewed_item_path"] is None
    assert not sidecar.exists()


def test_review_edits_fail_closed_on_unknown_or_empty_fields(tmp_path):
    root, db, run_id, _, _ = _seed(tmp_path)
    with pytest.raises(ValueError, match="unsupported fields"):
        prepare_reviewed_items(root, db, run_id, {"item-1": {"score": "99"}})
    with pytest.raises(ValueError, match="cannot be empty"):
        prepare_reviewed_items(root, db, run_id, {"item-1": {"mechanism": "   "}})
    with pytest.raises(ValueError, match="unknown item IDs"):
        prepare_reviewed_items(root, db, run_id, {"missing": {"mechanism": "x"}})


def test_unrecorded_sidecar_is_not_counted_as_validated_feedback(tmp_path):
    root, db, run_id, _, _ = _seed(tmp_path)
    prepare_reviewed_items(root, db, run_id, {"item-1": {"mechanism": "尚未通过最终校验的人工稿。"}})

    stats = human_feedback_stats(db, run_id)["current_run"]
    assert stats["reviewed_items"] == 0
    assert stats["approved_fields_changed"] == 0
