from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from briefing_skill import publication_manifest
from briefing_skill.config import ConfigBundle
from briefing_skill.cost_schema import ensure_cost_schema
from briefing_skill.db import Database
from briefing_skill.paths import Paths
from briefing_skill.reader_writing_contract import (
    relevance_reason_contract_errors,
    summary_is_reader_chinese,
    text_contains_chinese,
)
from briefing_skill.radar_signal_synthesis import radar_semantic_errors
from briefing_skill.relevance_efficiency import (
    apply_cached_relevance,
    store_relevance_candidate,
)


ROOT = Path(__file__).resolve().parents[1]

FILLER_REASON = "与指定方向直接相关，并包含可验证机制。"
CONCRETE_REASON = "锚点残差压缩在二十倍压缩下保留长上下文检索精度。"


def test_relevance_reason_contract_rejects_filler_and_english() -> None:
    data = {
        "results": [
            {"candidate_id": "c1", "relevant": True, "score": 88, "reason": FILLER_REASON},
            {"candidate_id": "c2", "relevant": True, "score": 70, "reason": "Directly relevant with verifiable mechanism."},
            {"candidate_id": "c3", "relevant": True, "score": 65, "reason": CONCRETE_REASON},
            {"candidate_id": "c4", "relevant": True, "score": 60, "reason": ""},
        ]
    }
    errors = relevance_reason_contract_errors(data)
    assert any("c1" not in error and "filler" in error for error in errors)
    assert any("must be written in Chinese" in error for error in errors)
    assert len(errors) == 2


def test_summary_language_helpers() -> None:
    assert text_contains_chinese(CONCRETE_REASON)
    assert not text_contains_chinese("An English abstract with concrete facts.")
    assert not text_contains_chinese(None)
    assert summary_is_reader_chinese(CONCRETE_REASON)
    assert not summary_is_reader_chinese(FILLER_REASON)
    assert not summary_is_reader_chinese("English only summary.")


class _AppendixDB:
    def __init__(self, raw_summary: str) -> None:
        self.raw_summary = raw_summary

    def fetchone(self, sql, params=None):
        if "raw_items" in sql:
            return {"summary": self.raw_summary}
        return None


class _AppendixService:
    _clean_text = staticmethod(lambda value: str(value or "").strip())

    def __init__(self, raw_summary: str) -> None:
        self.db = _AppendixDB(raw_summary)


def _appendix_item(summary: str) -> dict:
    return {
        "topic_id": "tpn",
        "title": "Kairos: Prefill Rerouting",
        "summary": summary,
        "url": "https://arxiv.org/abs/2608.00001v1",
        "source_name": "arXiv",
        "published_at": "2026-08-01",
        "score": 88.0,
    }


def test_appendix_boilerplate_fallback_drops_english_keeps_chinese() -> None:
    from briefing_skill.reader_writing_contract import _clean_appendix_boilerplate

    def collect(_service, _run_id, _issue_data):
        return {"tpn": [_appendix_item(FILLER_REASON)]}

    english = _clean_appendix_boilerplate(_AppendixService("A repository graph indexes symbols and files."), collect, "r", {})
    assert english == {}

    chinese = _clean_appendix_boilerplate(_AppendixService("把多轮远程依赖链压缩到单次往返,减少重复探索。"), collect, "r", {})
    assert chinese["tpn"][0]["summary"].startswith("把多轮远程依赖链压缩到单次往返")


def _config() -> ConfigBundle:
    return ConfigBundle.load(Paths(ROOT))


def _db(tmp_path) -> Database:
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    ensure_cost_schema(db)
    return db


def _insert_arxiv_raw(db: Database, *, raw_id: str, run_id: str) -> None:
    db.execute(
        """
        INSERT INTO raw_items(
            id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,
            original_url,canonical_url,identity_key,published_at,authors_json,external_id,
            priority,content_hash,payload_json,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            raw_id,
            run_id,
            "arxiv",
            "arXiv",
            "A",
            0,
            "Same Paper",
            "same summary",
            "https://arxiv.org/abs/2608.00001v1",
            "https://arxiv.org/abs/2608.00001v1",
            "arxiv:2608.00001",
            "2026-08-01T00:00:00Z",
            "[]",
            "http://arxiv.org/abs/2608.00001v1",
            18,
            "stable-content",
            "{}",
            "2026-08-01T00:00:00Z",
        ),
    )


def _insert_candidate(
    db: Database,
    *,
    candidate_id: str,
    raw_id: str,
    run_id: str,
    reason: str,
    status: str = "RELEVANT",
) -> None:
    db.execute(
        """
        INSERT INTO candidates(
            id,run_id,raw_item_id,topic_id,direction_id,rule_score,relevant,
            relevance_score,relevance_reason,fulltext_required,status,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            candidate_id,
            run_id,
            raw_id,
            "tpn",
            "kv_transfer",
            72,
            1,
            78,
            reason,
            1,
            status,
            "2026-08-07T00:00:00Z",
        ),
    )


def _candidate_row(db: Database, candidate_id: str):
    return db.fetchone(
        """
        SELECT c.*, r.source_id, r.title, r.summary, r.original_url, r.canonical_url,
               r.identity_key, r.external_id, r.content_hash, r.payload_json,
               r.source_level, r.discovery_only, r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.id=?
        """,
        (candidate_id,),
    )


def test_apply_cached_relevance_treats_unusable_cached_reasons_as_miss(tmp_path):
    for reason in (FILLER_REASON, "relevant English reason with facts"):
        config = _config()
        db = _db(tmp_path / ("case-" + str(abs(hash(reason)) % 10**8)))
        _insert_arxiv_raw(db, raw_id="r1", run_id="run1")
        _insert_candidate(db, candidate_id="c1", raw_id="r1", run_id="run1", reason=reason)
        assert store_relevance_candidate(config, db, ROOT, "c1")

        _insert_arxiv_raw(db, raw_id="r2", run_id="run2")
        _insert_candidate(
            db, candidate_id="c2", raw_id="r2", run_id="run2", reason=reason, status="PENDING_RELEVANCE"
        )
        assert not apply_cached_relevance(config, db, ROOT, _candidate_row(db, "c2"))
        assert (
            db.fetchone("SELECT status FROM candidates WHERE id='c2'")["status"]
            == "PENDING_RELEVANCE"
        )


def test_apply_cached_relevance_still_reuses_concrete_chinese_reason(tmp_path):
    config = _config()
    db = _db(tmp_path)
    _insert_arxiv_raw(db, raw_id="r1", run_id="run1")
    _insert_candidate(db, candidate_id="c1", raw_id="r1", run_id="run1", reason=CONCRETE_REASON)
    assert store_relevance_candidate(config, db, ROOT, "c1")

    _insert_arxiv_raw(db, raw_id="r2", run_id="run2")
    _insert_candidate(db, candidate_id="c2", raw_id="r2", run_id="run2", reason=CONCRETE_REASON)
    assert apply_cached_relevance(config, db, ROOT, _candidate_row(db, "c2"))
    assert db.fetchone("SELECT status FROM candidates WHERE id='c2'")["status"] == "RELEVANT"


def _radar_task(candidates: list[dict], signals: list[dict]) -> tuple[dict, dict, dict]:
    task = {
        "task_type": "issue_synthesis",
        "metadata_json": json.dumps({"radar_signals_required": True}),
    }
    return task, {"radar_candidates": candidates}, {"radar_signals": signals}


def test_radar_semantic_errors_requires_chinese_signals() -> None:
    url = "https://arxiv.org/abs/2608.11111v1"
    candidates = [{"url": url, "category": "AI Infra"}]
    task, input_data, data = _radar_task(
        candidates,
        [
            {
                "category": "AI Infra",
                "signal": "Some English signal title",
                "summary": "An English abstract body.",
                "source_urls": [url],
            }
        ],
    )
    errors = radar_semantic_errors(task, input_data, data)
    assert any("must be written in Chinese" in error for error in errors)

    task, input_data, data = _radar_task(
        candidates,
        [
            {
                "category": "AI Infra",
                "signal": "LMCache候选线密集交付双平台wheel",
                "summary": "连续发布CUDA与ROCm构建,属交付节奏信号。",
                "source_urls": [url],
            }
        ],
    )
    assert radar_semantic_errors(task, input_data, data) == []


class _RecorderDB:
    def __init__(self) -> None:
        self.statements: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self, sql, params=None):
        return None


class _RadarService:
    def __init__(self) -> None:
        self.db = _RecorderDB()
        self.config = SimpleNamespace(scoring={})
        self._topic_appendix_cache = {}

    def _normalise_reference(self, value: str) -> str:
        return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _radar_item(title: str, summary: str, url: str) -> dict:
    return {"title": title, "summary": summary, "url": url, "source_name": "arXiv", "published_at": "2026-08-10"}


def test_finalize_radar_groups_drops_english_summaries(monkeypatch) -> None:
    service = _RadarService()
    monkeypatch.setattr(
        publication_manifest,
        "build_radar_candidates",
        lambda _service, _run_id, _issue: [
            {
                "category": "AI Infra",
                "title": "English Reserve Candidate",
                "summary": "An English abstract that must not be reserve-filled.",
                "url": "https://arxiv.org/abs/2608.22222v1",
                "source_name": "arXiv",
                "published_at": "2026-08-10",
                "source_level": "A",
            }
        ],
    )
    groups = [
        {
            "name": "AI Infra",
            "items": [
                _radar_item("中文信号一", "解耦二级层与连接器走向值得跟踪。", "https://arxiv.org/abs/2608.33333v1"),
                _radar_item("English Signal", "English summary body.", "https://arxiv.org/abs/2608.44444v1"),
            ],
        }
    ]
    final_groups, contract = publication_manifest.finalize_radar_groups(
        service,
        groups,
        issue_id="issue-1",
        issue_data={"run_id": "run-x", "items": []},
    )

    items = final_groups[0]["items"]
    assert [item["title"] for item in items] == ["中文信号一"]
    assert contract["final_count"] == 1

    persisted = [
        params
        for sql, params in service.db.statements
        if sql.strip().startswith("INSERT OR REPLACE INTO issue_radar_items")
    ]
    assert len(persisted) == 1
    assert text_contains_chinese(persisted[0][5])
    assert persisted[0][3] == "AI Infra"
