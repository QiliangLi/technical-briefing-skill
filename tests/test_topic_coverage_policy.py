from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from briefing_skill.config import ConfigBundle
from briefing_skill import quality_guard
from briefing_skill.coverage_policy import (
    _project_key,
    collect_topic_appendix,
    materialize_deep_backlog,
    primary_direction_is_diversely_covered,
    select_diverse_deep_budget,
)
from briefing_skill.db import Database
from briefing_skill.expanded import collect_historical_brief_rows, select_expanded_rows
from briefing_skill.fact_cache_provenance import set_run_execution_mode
from briefing_skill.paths import Paths


ROOT = Path(__file__).resolve().parents[1]


def _settings():
    return {
        "efficiency": {
            "max_fact_candidates_total": 6,
            "max_fact_candidates_per_topic": 4,
            "max_fact_candidates_per_direction": 2,
            "max_fact_candidates_per_project": 1,
        }
    }


def _row(index: int, *, topic="tpn", direction="kv_transfer", score=80, repo=None, url=None):
    payload = {"repo": repo} if repo else {}
    return {
        "id": f"c{index}",
        "topic_id": topic,
        "direction_id": direction,
        "relevance_score": score,
        "rule_score": score,
        "priority": 20,
        "payload_json": json.dumps(payload),
        "original_url": url or f"https://example.com/{index}",
        "canonical_url": url or f"https://example.com/{index}",
        "identity_key": f"id:{index}",
    }


def test_deep_selector_prevents_one_project_from_occupying_tpn():
    rows = [
        _row(1, score=99, repo="LMCache/LMCache"),
        _row(2, score=98, repo="LMCache/LMCache"),
        _row(3, score=97, repo="LMCache/LMCache"),
        _row(4, score=96, repo="vllm-project/vllm"),
        _row(5, score=95, url="https://arxiv.org/abs/2608.12345"),
        _row(6, topic="dpu_inline", direction="inline_datapath", score=90, url="https://arxiv.org/abs/2608.10001"),
    ]
    selected, deferred = select_diverse_deep_budget(rows, _settings())
    selected_projects = [_project_key(row) for row in selected if row["topic_id"] == "tpn"]
    assert selected_projects.count("github:lmcache/lmcache") == 1
    assert "github:vllm-project/vllm" in selected_projects
    assert any(row["topic_id"] == "dpu_inline" for row in selected)
    assert len([row for row in deferred if _project_key(row) == "github:lmcache/lmcache"]) == 2


def test_tpn_search_requires_two_distinct_primary_projects():
    direction = {"id": "kv_transfer", "include_terms": ["kv cache", "transfer", "network"]}
    lmcache = {
        "title": "LMCache KV cache transfer compatibility",
        "summary": "network transfer update",
        "topic_hint": "tpn",
        "direction_hint": "kv_transfer",
        "source_level": "A",
        "discovery_only": False,
        "original_url": "https://github.com/LMCache/LMCache/releases/tag/v1",
        "payload_json": json.dumps({"repo": "LMCache/LMCache"}),
    }
    assert not primary_direction_is_diversely_covered([lmcache], "tpn", direction)
    vllm = {
        **lmcache,
        "title": "vLLM KV transfer connector",
        "original_url": "https://github.com/vllm-project/vllm/releases/tag/v2",
        "payload_json": json.dumps({"repo": "vllm-project/vllm"}),
    }
    assert primary_direction_is_diversely_covered([lmcache, vllm], "tpn", direction)
    # Topic evidence boundary: a TPN-hinted row cannot prove cross_region coverage.
    assert not primary_direction_is_diversely_covered([lmcache], "cross_region", direction)


IO_DIRECTION_TERMS = {
    "direct_storage_path": ["gpu", "accelerator", "storage", "nvme", "direct data path", "gpudirect storage", "bounce buffer", "p2p"],
    "accelerator_initiated_io": ["gpu-initiated", "accelerator", "storage", "nvme", "control path", "scada", "storage-next", "bam", "gids"],
    "accelerator_storage_stack": ["gpu", "accelerator", "storage", "cufile", "storage stack", "fast path", "kernel bypass", "userspace"],
    "accelerator_storage_controller": ["ssd controller", "nvme controller", "gpu", "accelerator", "fine-grained", "small-block", "ecc", "queue"],
}


def _ainfer_pd_like_row(*, topic_hint: str, direction_hint: str | None):
    """Mirror the run-2026-09-03-003948 false positive: a TPN abstract whose
    title/summary mention accelerator + storage (and fine-grained + queue)."""
    return {
        "title": "AInfer-PD: Communication-Safe In-Place Prefill-Decode Multiplexing",
        "summary": "Distributed MoE rollouts keep accelerator storage and fine-grained queue state safe while prefill and decode share one device.",
        "topic_hint": topic_hint,
        "direction_hint": direction_hint,
        "source_level": "A",
        "discovery_only": False,
        "original_url": "https://arxiv.org/abs/2609.00993",
    }


def test_cross_topic_generic_words_cannot_cover_accelerator_io_directions():
    row = _ainfer_pd_like_row(topic_hint="tpn", direction_hint="kv_network_scheduling")
    for direction_id, terms in IO_DIRECTION_TERMS.items():
        direction = {"id": direction_id, "include_terms": terms}
        assert not quality_guard.primary_direction_is_covered([row], "accelerator_io_datapath", direction)
        assert not primary_direction_is_diversely_covered([row], "accelerator_io_datapath", direction)


def test_same_topic_exact_hint_and_keyword_fallback_cover():
    exact = _ainfer_pd_like_row(topic_hint="accelerator_io_datapath", direction_hint="direct_storage_path")
    direction = {"id": "direct_storage_path", "include_terms": IO_DIRECTION_TERMS["direct_storage_path"]}
    assert quality_guard.primary_direction_is_covered([exact], "accelerator_io_datapath", direction)
    assert primary_direction_is_diversely_covered([exact], "accelerator_io_datapath", direction)

    keyword_only = _ainfer_pd_like_row(topic_hint="accelerator_io_datapath", direction_hint=None)
    controller = {"id": "accelerator_storage_controller", "include_terms": IO_DIRECTION_TERMS["accelerator_storage_controller"]}
    assert quality_guard.primary_direction_is_covered([keyword_only], "accelerator_io_datapath", controller)
    assert primary_direction_is_diversely_covered([keyword_only], "accelerator_io_datapath", controller)


def test_same_topic_unusable_rows_still_cannot_cover():
    direction = {"id": "direct_storage_path", "include_terms": IO_DIRECTION_TERMS["direct_storage_path"]}
    base = _ainfer_pd_like_row(topic_hint="accelerator_io_datapath", direction_hint="direct_storage_path")
    assert not quality_guard.primary_direction_is_covered([{**base, "source_level": "B"}], "accelerator_io_datapath", direction)
    assert not quality_guard.primary_direction_is_covered([{**base, "discovery_only": True}], "accelerator_io_datapath", direction)
    assert not quality_guard.primary_direction_is_covered([{**base, "original_url": "example.com/not-a-url"}], "accelerator_io_datapath", direction)


def test_tpn_two_projects_must_both_belong_to_tpn():
    direction = {"id": "kv_transfer", "include_terms": ["kv cache", "transfer", "network"]}
    tpn_project = _ainfer_pd_like_row(topic_hint="tpn", direction_hint="kv_transfer")
    other_topic_project = {
        **_ainfer_pd_like_row(topic_hint="cross_region", direction_hint="kv_transfer"),
        "original_url": "https://github.com/other/repo/releases/tag/v1",
    }
    assert not primary_direction_is_diversely_covered([tpn_project, other_topic_project], "tpn", direction)


def test_bootstrap_replaced_path_is_topic_scoped():
    replaced = quality_guard.primary_direction_is_covered
    try:
        quality_guard.primary_direction_is_covered = primary_direction_is_diversely_covered
        row = _ainfer_pd_like_row(topic_hint="tpn", direction_hint="kv_network_scheduling")
        direction = {"id": "direct_storage_path", "include_terms": IO_DIRECTION_TERMS["direct_storage_path"]}
        assert not quality_guard.primary_direction_is_covered([row], "accelerator_io_datapath", direction)
        same_topic = _ainfer_pd_like_row(topic_hint="accelerator_io_datapath", direction_hint="direct_storage_path")
        assert quality_guard.primary_direction_is_covered([same_topic], "accelerator_io_datapath", direction)
    finally:
        quality_guard.primary_direction_is_covered = replaced


def _insert_raw(db: Database, *, row_id: str, run_id: str, days_old: int, identity: str, url: str):
    published = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    db.execute(
        """
        INSERT INTO raw_items(
            id, run_id, source_id, discovery_source, source_level, discovery_only,
            title, summary, original_url, aihot_url, canonical_url, identity_key,
            published_at, discovered_at, authors_json, external_id, topic_hint,
            direction_hint, priority, content_hash, payload_json, created_at
        ) VALUES (?, ?, 'arxiv', 'arXiv', 'A', 0, ?, ?, ?, '', ?, ?, ?, ?, '[]', ?, 'tpn', 'kv_transfer', 18, ?, '{}', ?)
        """,
        (
            row_id,
            run_id,
            f"paper {row_id}",
            "KV cache transfer over network",
            url,
            url,
            identity,
            published,
            published,
            row_id,
            row_id,
            published,
        ),
    )


def _insert_relevant_candidate(db: Database, *, candidate_id: str, run_id: str, raw_id: str, score: float, reason: str):
    db.execute(
        """
        INSERT INTO candidates(
            id, run_id, raw_item_id, topic_id, direction_id, rule_score,
            relevant, relevance_score, relevance_reason, fulltext_required,
            status, created_at
        ) VALUES (?, ?, ?, 'tpn', 'kv_transfer', ?, 1, ?, ?, 0, 'RADAR', ?)
        """,
        (candidate_id, run_id, raw_id, score, score, reason, datetime.now(timezone.utc).isoformat()),
    )


def test_backlog_carries_unpushed_forty_day_item_but_not_stale_or_sent(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("old")
    db.create_run("new")
    _insert_raw(db, row_id="fresh-old", run_id="old", days_old=40, identity="arxiv:40", url="https://arxiv.org/abs/2606.00040")
    _insert_raw(db, row_id="stale", run_id="old", days_old=70, identity="arxiv:70", url="https://arxiv.org/abs/2605.00070")
    _insert_raw(db, row_id="already-shown", run_id="old", days_old=20, identity="arxiv:20", url="https://arxiv.org/abs/2607.00020")
    db.execute(
        "INSERT INTO radar_history(canonical_url, normalized_title, last_pushed_at, issue_id) VALUES (?, 'shown', ?, 'issue-old')",
        ("https://arxiv.org/abs/2607.00020", datetime.now(timezone.utc).isoformat()),
    )
    config = SimpleNamespace(settings={"efficiency": {"deep_lookback_days": 60, "backlog_materialize_per_run": 20}})
    copied = materialize_deep_backlog(config, db, "new")
    assert copied == 1
    rows = db.fetchall("SELECT identity_key FROM raw_items WHERE run_id='new'")
    assert [row["identity_key"] for row in rows] == ["arxiv:40"]


def test_topic_appendix_excludes_selected_deep_item_and_keeps_remaining_relevant_a_sources(tmp_path):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("run")
    selected_url = "https://arxiv.org/abs/2608.00001"
    extra_url = "https://arxiv.org/abs/2607.00002"
    _insert_raw(db, row_id="selected-raw", run_id="run", days_old=1, identity="arxiv:selected", url=selected_url)
    _insert_raw(db, row_id="extra-raw", run_id="run", days_old=20, identity="arxiv:extra", url=extra_url)
    _insert_relevant_candidate(db, candidate_id="selected-c", run_id="run", raw_id="selected-raw", score=90, reason="入选深度解读。")
    _insert_relevant_candidate(db, candidate_id="extra-c", run_id="run", raw_id="extra-raw", score=72, reason="提出一种新的KVCache传输路径，具有明确网络机制，但优先级低于本期Top4。")
    config = ConfigBundle.load(Paths(ROOT))
    service = SimpleNamespace(config=config, db=db)
    appendix = collect_topic_appendix(
        service,
        "run",
        {"items": [{"sources": [{"url": selected_url}]}]},
    )
    assert [item["url"] for item in appendix["tpn"]] == [extra_url]
    assert "新的KVCache传输路径" in appendix["tpn"][0]["summary"]


def test_final_issue_ranks_value_before_recency(tmp_path):
    config = ConfigBundle.load(Paths(ROOT))
    high_value = {
        "title": "older architecture paper",
        "published_at": "2026-07-08T00:00:00+00:00",
        "sources": [{"url": "https://arxiv.org/abs/2607.00001", "source_level": "A"}],
        "incremental_update": False,
    }
    fresh_weak = {
        "title": "fresh routine release",
        "published_at": "2026-08-06T00:00:00+00:00",
        "sources": [{"url": "https://github.com/example/project/releases/tag/v1", "source_level": "A"}],
        "incremental_update": False,
    }
    (tmp_path / "high.json").write_text(json.dumps(high_value), encoding="utf-8")
    (tmp_path / "fresh.json").write_text(json.dumps(fresh_weak), encoding="utf-8")
    rows = [
        {"id": "fresh", "score": 75, "json_path": "fresh.json", "fact_check_status": "PASS", "topic_id": "tpn", "direction_id": "kv_transfer", "source_published_at": fresh_weak["published_at"], "last_pushed_at": None},
        {"id": "high", "score": 95, "json_path": "high.json", "fact_check_status": "PASS", "topic_id": "tpn", "direction_id": "token_metric_network", "source_published_at": high_value["published_at"], "last_pushed_at": None},
    ]
    selected, _, _, _ = select_expanded_rows(tmp_path, config, rows, reference_date="2026-08-07")
    assert [row["id"] for row in selected[:2]] == ["high", "fresh"]


def test_repo_config_uses_sixty_day_deep_window_and_disables_rule_auto_accept():
    config = ConfigBundle.load(Paths(ROOT))
    assert config.scoring["freshness_gates"]["absolute_max_age_days"] == 60
    assert config.scoring["radar"]["max_age_days"] == 7
    assert config.scoring["radar"]["total_max"] == 16
    assert config.scoring["radar"]["max_per_category"] == 5
    assert config.scoring["radar"]["industry_builder_min"] == 8
    assert config.settings["efficiency"]["deep_lookback_days"] == 60
    assert config.settings["efficiency"]["auto_accept_rule_score"] > 100
    assert config.settings["efficiency"]["max_fact_candidates_per_project"] == 1
    assert config.settings["efficiency"]["topic_appendix_max_per_topic"] == 8
    assert config.scoring["expanded_v2"]["topic_target"] == 4
    assert config.scoring["expanded_v2"]["topic_floor_allow_brief_upgrade"] is True


def test_topic_target_upgrades_available_short_items_without_exceeding_cap(tmp_path):
    """Current brief rows fill the topic target without exceeding the cap."""
    config = ConfigBundle.load(Paths(ROOT))
    items = []
    # tpn is thin (3 core-grade + 1 sub-bar); agent has 5 core-grade (overflow capped).
    for topic, scores in (("tpn", (88, 84, 80, 62)), ("agent_acceleration", (88, 84, 80, 78, 76))):
        for index, score in enumerate(scores):
            published = "2026-08-0%d" % (index + 1)
            payload = {
                "title": f"item {topic} {index}",
                "published_at": published,
                "sources": [{"url": f"https://arxiv.org/abs/2608.0{index}{len(topic)}{index}", "source_level": "A"}],
                "incremental_update": False,
            }
            path = tmp_path / f"{topic}-{index}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            items.append(
                {
                    "id": f"{topic}-{index}",
                    "score": score,
                    "json_path": path.name,
                    "fact_check_status": "PASS",
                    "topic_id": topic,
                    "direction_id": "kv_transfer",
                    "source_published_at": published,
                    "last_pushed_at": None,
                }
            )
    selected, excluded, counts, limits = select_expanded_rows(
        tmp_path, config, items, reference_date="2026-08-09"
    )
    per_topic = {}
    for row in selected:
        per_topic.setdefault(row["topic_id"], []).append((row["item_role"], row["score"]))
    assert len(per_topic["tpn"]) == limits["topic_target"]
    assert [role for role, _ in per_topic["tpn"]] == ["core"] * 3 + ["observation"]
    assert per_topic["tpn"][-1][1] == 62
    assert len(per_topic["agent_acceleration"]) == limits["max_per_topic"]
    assert all(role == "core" for role, _ in per_topic["agent_acceleration"])
    overflow = {row["id"] for row in excluded if row["reason"] == "expanded-v2 capacity"}
    assert overflow == {"agent_acceleration-4"}


def _historical_selection_row(
    tmp_path: Path,
    index: int,
    *,
    previously_brief: bool,
    previously_detailed: bool,
) -> dict:
    published = "2026-08-01"
    payload = {
        "title": f"historical item {index}",
        "published_at": published,
        "sources": [
            {
                "url": f"https://arxiv.org/abs/2608.10{index:03d}",
                "source_level": "A",
            }
        ],
        "incremental_update": False,
    }
    path = tmp_path / f"historical-{index}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "id": f"historical-{index}",
        "score": 80 - index,
        "json_path": path.name,
        "fact_check_status": "PASS",
        "topic_id": "tpn",
        "direction_id": "kv_transfer",
        "source_published_at": published,
        "last_pushed_at": "2026-08-02T00:00:00+00:00",
        "previously_brief": previously_brief,
        "previously_detailed": previously_detailed,
    }


def test_only_brief_only_history_can_be_upgraded_and_available_count_is_respected(tmp_path):
    config = ConfigBundle.load(Paths(ROOT))
    rows = [
        _historical_selection_row(
            tmp_path,
            index,
            previously_brief=True,
            previously_detailed=False,
        )
        for index in range(3)
    ]
    rows.extend(
        [
            _historical_selection_row(
                tmp_path,
                10,
                previously_brief=False,
                previously_detailed=True,
            ),
            # Once an identity has ever been detailed, an earlier brief appearance
            # cannot make it eligible for another detailed replay.
            _historical_selection_row(
                tmp_path,
                11,
                previously_brief=True,
                previously_detailed=True,
            ),
        ]
    )

    selected, excluded, counts, limits = select_expanded_rows(
        tmp_path,
        config,
        rows,
        reference_date="2026-08-09",
    )

    assert limits["topic_target"] == 4
    assert counts["total"] == counts["observations"] == 3
    assert {row["id"] for row in selected} == {
        "historical-0",
        "historical-1",
        "historical-2",
    }
    assert all(row["brief_upgrade"] is True for row in selected)
    excluded_by_id = {row["id"]: row["reason"] for row in excluded}
    assert excluded_by_id["historical-10"] == "previously published as detailed without incremental update"
    assert excluded_by_id["historical-11"] == "previously published as detailed without incremental update"


def test_brief_only_upgrades_fill_only_the_shortfall_to_four(tmp_path):
    config = ConfigBundle.load(Paths(ROOT))
    rows = []
    for index in range(2):
        row = _historical_selection_row(
            tmp_path,
            index,
            previously_brief=False,
            previously_detailed=False,
        )
        row["last_pushed_at"] = None
        row["score"] = 90 - index
        rows.append(row)
    rows.extend(
        _historical_selection_row(
            tmp_path,
            index,
            previously_brief=True,
            previously_detailed=False,
        )
        for index in range(2, 7)
    )

    selected, excluded, counts, _ = select_expanded_rows(
        tmp_path,
        config,
        rows,
        reference_date="2026-08-09",
    )

    assert counts["topics"]["tpn"] == 4
    assert {row["id"] for row in selected if row.get("brief_upgrade")} == {
        "historical-2",
        "historical-3",
    }
    assert {
        row["id"]
        for row in excluded
        if row["reason"] == "brief upgrade capacity"
    } == {"historical-4", "historical-5", "historical-6"}


def test_current_brief_upgrades_precede_higher_scored_history(tmp_path):
    config = ConfigBundle.load(Paths(ROOT))
    rows = []
    for index in range(2):
        row = _historical_selection_row(
            tmp_path,
            index,
            previously_brief=False,
            previously_detailed=False,
        )
        row["last_pushed_at"] = None
        row["score"] = 95 - index
        rows.append(row)

    for index, score in ((2, 70), (3, 69)):
        row = _historical_selection_row(
            tmp_path,
            index,
            previously_brief=True,
            previously_detailed=False,
        )
        row["score"] = score
        rows.append(row)

    for index, score in ((4, 90), (5, 89)):
        row = _historical_selection_row(
            tmp_path,
            index,
            previously_brief=True,
            previously_detailed=False,
        )
        row["score"] = score
        row["historical_brief_candidate"] = True
        rows.append(row)

    selected, excluded, counts, _ = select_expanded_rows(
        tmp_path,
        config,
        rows,
        reference_date="2026-08-09",
    )

    assert counts["topics"]["tpn"] == 4
    assert {row["id"] for row in selected} == {
        "historical-0",
        "historical-1",
        "historical-2",
        "historical-3",
    }
    assert {
        row["id"]
        for row in excluded
        if row["reason"] == "brief upgrade capacity"
    } == {"historical-4", "historical-5"}


def test_historical_brief_pool_is_independent_of_current_run_materialisation(tmp_path, monkeypatch):
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("old")
    db.create_run("current")

    for event_id, event_key in (
        ("event-brief", "arxiv:brief"),
        ("event-detailed", "arxiv:detailed"),
        ("event-current", "arxiv:current"),
    ):
        db.execute(
            """
            INSERT INTO events(
                id,topic_id,direction_id,canonical_title,fingerprint,score,
                first_seen_at,last_updated_at,last_pushed_at,payload_json,event_key
            ) VALUES (?, 'tpn', 'kv_transfer', ?, ?, 80, ?, ?, ?, '{}', ?)
            """,
            (event_id, event_id, event_key, "2026-08-01", "2026-08-02", "2026-08-03", event_key),
        )
        path = tmp_path / f"{event_id}.json"
        path.write_text(
            json.dumps(
                {
                    "title": event_id,
                    "core_conclusion": "该方案验证了跨节点缓存传输能够减少重复计算，并给出了可复现、可审计且可迁移的系统结论。",
                    "mechanism": "系统通过分层索引、异步传输与拥塞感知调度，把远端缓存安全地送到目标节点。",
                    "result": "实验覆盖多种请求规模和网络条件，显示端到端时延与资源占用均有稳定改善。",
                    "boundary": "收益依赖缓存命中率、链路带宽和工作负载稳定性，不能外推到所有线上环境。",
                    "project_relevance": "这为跨域推理中的缓存复用、容量规划和一致性设计提供了直接参考。",
                    "published_at": "2026-08-01",
                    "sources": [
                        {
                            "url": f"https://arxiv.org/abs/{event_id}",
                            "source_level": "A",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db.execute(
            """
            INSERT INTO brief_items(
                id,run_id,event_id,json_path,score,fact_check_status,approved,created_at
            ) VALUES (?, 'old', ?, ?, 80, 'PASS', 1, '2026-08-03')
            """,
            (f"brief-{event_id}", event_id, path.name),
        )

    def annotate(_root, _db, rows):
        result = []
        for row in rows:
            key = row["event_key"]
            result.append(
                {
                    **row,
                    "previously_brief": key in {"arxiv:brief", "arxiv:current"},
                    "previously_detailed": key == "arxiv:detailed",
                }
            )
        return result

    monkeypatch.setattr(
        "briefing_skill.publication_history.annotate_rows_with_publication_roles",
        annotate,
    )
    config = SimpleNamespace(
        settings={
            "efficiency": {"deep_topics": ["tpn"]},
            "brief_item_min_chars": 230,
            "historical_brief_upgrade_min_chars": 180,
            "brief_item_max_chars": 330,
        }
    )
    historical = collect_historical_brief_rows(
        tmp_path,
        config,
        db,
        "current",
        [{"event_key": "arxiv:current", "topic_id": "tpn"}],
    )

    assert [row["event_key"] for row in historical] == ["arxiv:brief"]
    assert historical[0]["historical_brief_candidate"] is True

    set_run_execution_mode(db, "current", "demo")
    assert collect_historical_brief_rows(
        tmp_path,
        config,
        db,
        "current",
        [{"event_key": "arxiv:current", "topic_id": "tpn"}],
    ) == []
