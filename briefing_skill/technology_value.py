from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable

from .utils import now_iso


DIMENSIONS = ("novelty", "architecture_impact", "industry_signal", "project_alignment")


TECHNOLOGY_VALUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS technology_value_cache (
    source_fingerprint TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    direction_id TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    technology_value_score REAL NOT NULL DEFAULT 0,
    technology_value_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    PRIMARY KEY(source_fingerprint, topic_id, direction_id, evaluator_version)
);
"""


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalise_technology_value(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    dimensions: dict[str, dict[str, Any]] = {}
    for name in DIMENSIONS:
        item = raw.get(name) if isinstance(raw.get(name), dict) else {}
        score = max(0.0, min(5.0, _number(item.get("score"))))
        dimensions[name] = {
            "score": score,
            "reason": str(item.get("reason") or "").strip(),
        }
    total = round(sum(item["score"] for item in dimensions.values()), 2)
    return {**dimensions, "total_score": total}


def technology_selection_score(row: dict[str, Any]) -> float:
    """Blend topic relevance with structural technology value without replacing relevance.

    Relevance remains 80% of the normalized ranking signal when a technology-value
    assessment exists. Legacy/unfinished tasks without the new signal fall back exactly
    to the original relevance score so rollout cannot silently penalise them.
    """

    relevance = max(0.0, min(100.0, _number(row.get("relevance_score"))))
    if row.get("technology_value_score") is None:
        return round(relevance, 3)
    tech = max(0.0, min(20.0, _number(row.get("technology_value_score"))))
    return round(relevance * 0.80 + tech, 3)


def ensure_technology_value_schema(db) -> None:
    with db.connect() as conn:
        candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
        if "technology_value_score" not in candidate_columns:
            conn.execute("ALTER TABLE candidates ADD COLUMN technology_value_score REAL")
        if "technology_value_json" not in candidate_columns:
            conn.execute("ALTER TABLE candidates ADD COLUMN technology_value_json TEXT")
        conn.executescript(TECHNOLOGY_VALUE_SCHEMA)


def _cache_identity(config, root, row: dict[str, Any]) -> tuple[str, str, str, str]:
    from . import relevance_efficiency

    topic_id = str(row.get("topic_id") or "")
    direction_id = str(row.get("direction_id") or "")
    fingerprint = relevance_efficiency.relevance_source_fingerprint(row)
    version = relevance_efficiency.relevance_evaluator_version(
        config,
        root,
        topic_id,
        direction_id,
        row.get("published_at"),
    )
    return fingerprint, topic_id, direction_id, version


def store_technology_value_cache(config, db, root, candidate_id: str) -> bool:
    ensure_technology_value_schema(db)
    row = db.fetchone(
        """
        SELECT c.*, r.source_id, r.identity_key, r.external_id, r.content_hash,
               r.canonical_url, r.original_url, r.title, r.summary, r.payload_json, r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.id=?
        """,
        (candidate_id,),
    )
    if not row or row.get("technology_value_score") is None:
        return False
    from . import relevance_efficiency

    if not relevance_efficiency._cache_eligible(row):
        return False
    fingerprint, topic_id, direction_id, version = _cache_identity(config, root, row)
    now = now_iso()
    db.execute(
        """
        INSERT INTO technology_value_cache(
            source_fingerprint,topic_id,direction_id,evaluator_version,
            technology_value_score,technology_value_json,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(source_fingerprint,topic_id,direction_id,evaluator_version) DO UPDATE SET
            technology_value_score=excluded.technology_value_score,
            technology_value_json=excluded.technology_value_json,
            last_used_at=excluded.last_used_at
        """,
        (
            fingerprint,
            topic_id,
            direction_id,
            version,
            row.get("technology_value_score") or 0,
            row.get("technology_value_json") or "{}",
            now,
            now,
        ),
    )
    return True


def _apply_cached_technology_value(config, db, root, row: dict[str, Any]) -> None:
    ensure_technology_value_schema(db)
    fingerprint, topic_id, direction_id, version = _cache_identity(config, root, row)
    cache = db.fetchone(
        """
        SELECT * FROM technology_value_cache
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (fingerprint, topic_id, direction_id, version),
    )
    if not cache:
        return
    db.execute(
        "UPDATE candidates SET technology_value_score=?,technology_value_json=? WHERE id=?",
        (cache.get("technology_value_score"), cache.get("technology_value_json"), row["id"]),
    )
    db.execute(
        """
        UPDATE technology_value_cache SET last_used_at=?
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (now_iso(), fingerprint, topic_id, direction_id, version),
    )


def select_deep_budget_with_technology_value(
    rows: Iterable[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use technology value only as a ranking signal; preserve existing diversity policy."""

    from . import coverage_policy

    prepared: list[dict[str, Any]] = []
    originals: dict[str, float] = {}
    for source in rows:
        row = dict(source)
        row_id = str(row.get("id") or "")
        originals[row_id] = _number(row.get("relevance_score"))
        row["relevance_score"] = technology_selection_score(row)
        prepared.append(row)

    selected, deferred = coverage_policy.select_diverse_deep_budget(prepared, settings)
    for row in [*selected, *deferred]:
        row["technology_selection_score"] = _number(row.get("relevance_score"))
        row["relevance_score"] = originals.get(str(row.get("id") or ""), _number(row.get("relevance_score")))
    return selected, deferred


def _technology_stats(db, run_id: str) -> dict[str, Any]:
    ensure_technology_value_schema(db)
    rows = db.fetchall(
        """
        SELECT topic_id,technology_value_score
        FROM candidates
        WHERE run_id=? AND technology_value_score IS NOT NULL
        """,
        (run_id,),
    )
    by_topic: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_topic[str(row.get("topic_id") or "unknown")].append(_number(row.get("technology_value_score")))
    values = [value for group in by_topic.values() for value in group]
    return {
        "assessed_candidates": len(values),
        "average_score_0_20": round(sum(values) / len(values), 3) if values else None,
        "high_value_candidates_ge_15": sum(value >= 15 for value in values),
        "by_topic": {
            topic: {
                "count": len(scores),
                "average_score_0_20": round(sum(scores) / len(scores), 3),
                "max_score_0_20": round(max(scores), 3),
            }
            for topic, scores in sorted(by_topic.items())
        },
        "note": "Technology value is a ranking signal separate from topical relevance; 20 is the maximum.",
    }


def install_technology_value_assessment() -> None:
    """Install structural technology-value scoring without weakening existing relevance guards."""

    from . import demo as demo_module
    from . import efficiency
    from . import relevance_efficiency
    from . import telemetry
    from .db import Database
    from .pipeline import Pipeline
    from .scoring import Scorer

    if getattr(Pipeline, "_technology_value_installed", False):
        return

    original_db_init = Database.init

    def db_init(self) -> None:
        original_db_init(self)
        ensure_technology_value_schema(self)

    Database.init = db_init

    original_cached_relevance = relevance_efficiency.apply_cached_relevance

    def apply_cached_relevance(config, db, root, row: dict[str, Any]) -> bool:
        hit = original_cached_relevance(config, db, root, row)
        if hit:
            _apply_cached_technology_value(config, db, root, row)
        return hit

    relevance_efficiency.apply_cached_relevance = apply_cached_relevance

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "relevance_batch":
            return
        output = self.tasks.read_result(task)
        for result in output.get("results") or []:
            candidate_id = str(result.get("candidate_id") or "")
            # Backward compatibility: an unfinished pre-PR17 task may validate without
            # technology_value. Leave its new columns NULL so ranking falls back exactly
            # to the pre-PR17 relevance path instead of fabricating a zero-value score.
            if not candidate_id or not isinstance(result.get("technology_value"), dict):
                continue
            value = normalise_technology_value(result.get("technology_value"))
            self.db.execute(
                "UPDATE candidates SET technology_value_score=?,technology_value_json=? WHERE id=?",
                (value["total_score"], json.dumps(value, ensure_ascii=False), candidate_id),
            )
            store_technology_value_cache(self.config, self.db, self.root, candidate_id)

    Pipeline._apply_task = apply_task

    # Keep every existing topic/project/direction constraint; only change the ordering
    # presented to the already-tested diversity selector.
    efficiency.select_deep_budget = select_deep_budget_with_technology_value

    original_event_score = Scorer.event_score

    def event_score(self, facts, candidates, raw_items):
        base = float(original_event_score(self, facts, candidates, raw_items))
        values = [
            _number(candidate.get("technology_value_score"))
            for candidate in candidates
            if candidate.get("technology_value_score") is not None
        ]
        if not values:
            return base
        tech_norm = max(values) * 5.0
        return round(max(0.0, min(100.0, base + (tech_norm - 50.0) * 0.12)), 2)

    Scorer.event_score = event_score

    original_demo = demo_module._demo_output

    def demo_output(task_type: str, data: dict[str, Any]):
        output = original_demo(task_type, data)
        if task_type == "relevance_batch" and isinstance(output, dict):
            for result in output.get("results") or []:
                result.setdefault(
                    "technology_value",
                    {
                        "novelty": {"score": 4, "reason": "fixture contains a distinct mechanism"},
                        "architecture_impact": {"score": 4, "reason": "fixture changes an execution or scheduling path"},
                        "industry_signal": {"score": 3, "reason": "fixture represents an emerging systems direction"},
                        "project_alignment": {"score": 4, "reason": "fixture maps to a configured project question"},
                    },
                )
        return output

    demo_module._demo_output = demo_output

    original_run_stats = telemetry.run_stats

    def run_stats(db, root, run_id: str):
        payload = original_run_stats(db, root, run_id)
        payload["technology_value"] = _technology_stats(db, run_id)
        return payload

    telemetry.run_stats = run_stats
    Pipeline._technology_value_installed = True
