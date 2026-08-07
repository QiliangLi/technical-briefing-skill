from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from briefing_skill.config import ConfigBundle
from briefing_skill.coverage_policy import (
    _project_key,
    collect_topic_appendix,
    materialize_deep_backlog,
    primary_direction_is_diversely_covered,
    select_diverse_deep_budget,
)
from briefing_skill.db import Database
from briefing_skill.expanded import select_expanded_rows
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
    assert primary_direction_is_diversely_covered([lmcache], "cross_region", direction)


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
    assert config.settings["efficiency"]["deep_lookback_days"] == 60
    assert config.settings["efficiency"]["auto_accept_rule_score"] > 100
    assert config.settings["efficiency"]["max_fact_candidates_per_project"] == 1
    assert config.settings["efficiency"]["topic_appendix_max_per_topic"] == 8
