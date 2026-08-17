from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .cost_schema import ensure_cost_schema
from .efficiency import DEFAULT_RADAR_TOPICS, RelevancePlan
from .freshness import published_age_days
from .paths import Paths
from .reader_writing_contract import summary_is_reader_chinese
from .utils import complete_sentence_excerpt, now_iso, read_json, stable_hash


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _policy(settings: dict[str, Any]) -> dict[str, Any]:
    return dict(settings.get("efficiency") or {})


def _summary_limit(settings: dict[str, Any]) -> int:
    return max(800, int(_policy(settings).get("relevance_summary_max_chars", 5000)))


def _bounded_summary_excerpt(value: str, limit: int) -> str:
    """Prefer complete sentences but never let a pathological summary bypass the hard cap."""

    excerpt = complete_sentence_excerpt(value, limit)
    if len(excerpt) <= limit:
        return excerpt
    # Some release notes are one enormous unpunctuated line. In that case the
    # generic sentence helper intentionally returns the whole unit, which is not
    # appropriate for a relevance-task budget. Fall back to a word/line boundary.
    clipped = value[: max(1, limit - 1)].rstrip()
    boundary = max(clipped.rfind("\n"), clipped.rfind(" "), clipped.rfind("\t"))
    if boundary >= limit // 2:
        clipped = clipped[:boundary].rstrip()
    return clipped.rstrip("，,:：;；、 ") + "。"


def _compact_topic(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        key: topic[key]
        for key in ("id", "name", "current_questions", "valuable_evidence")
        if key in topic and topic.get(key) not in (None, [], "")
    }


def _compact_direction(direction: dict[str, Any]) -> dict[str, Any]:
    return {
        key: direction[key]
        for key in ("id", "name", "include_terms", "exclude_terms")
        if key in direction and direction.get(key) not in (None, [], "")
    }


def _row_cost(row: dict[str, Any], settings: dict[str, Any]) -> int:
    summary = str(row.get("summary") or "")
    return (
        len(str(row.get("title") or ""))
        + min(len(summary), _summary_limit(settings))
        + len(str(row.get("original_url") or ""))
        + 520
    )


def plan_relevance_rows_bounded(
    rows: Iterable[dict[str, Any]],
    settings: dict[str, Any],
) -> RelevancePlan:
    """Preserve per-candidate judgement while amortising one topic context per larger batch.

    Count and character caps are both enforced. The character estimate is deliberately
    conservative and is applied before TaskService compacts repeated topic/direction data.
    """

    policy = _policy(settings)
    accept_at = _number(policy.get("auto_accept_rule_score"), 85)
    reject_below = _number(policy.get("auto_reject_rule_score"), 15)
    promote_at = _number(policy.get("radar_promotion_rule_score"), 88)
    batch_size = max(1, int(settings.get("max_relevance_batch", 24)))
    batch_chars = max(8000, int(policy.get("relevance_batch_max_input_chars", 48000)))
    radar_topics = set(policy.get("radar_topics") or DEFAULT_RADAR_TOPICS)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    radar: list[dict[str, Any]] = []
    ambiguous: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        score = _number(row.get("rule_score"))
        topic_id = str(row.get("topic_id") or "")
        if str(row.get("source_level") or "C").upper() != "A" or bool(row.get("discovery_only")):
            radar.append(row)
        elif topic_id in radar_topics and score < promote_at:
            radar.append(row)
        elif score < reject_below:
            rejected.append(row)
        elif score >= accept_at:
            accepted.append(row)
        else:
            ambiguous[topic_id].append(row)

    batches: list[tuple[dict[str, Any], ...]] = []
    for topic_id in sorted(ambiguous):
        ordered = sorted(
            ambiguous[topic_id],
            key=lambda row: (-_number(row.get("rule_score")), str(row.get("id") or "")),
        )
        current: list[dict[str, Any]] = []
        current_chars = 1400
        for row in ordered:
            cost = _row_cost(row, settings)
            if current and (len(current) >= batch_size or current_chars + cost > batch_chars):
                batches.append(tuple(current))
                current = []
                current_chars = 1400
            current.append(row)
            current_chars += cost
        if current:
            batches.append(tuple(current))

    return RelevancePlan(tuple(accepted), tuple(rejected), tuple(radar), tuple(batches))


def compact_relevance_batch_input(input_data: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Remove repeated config payload while preserving every candidate and judging signal."""

    summary_limit = _summary_limit(settings)
    topic = _compact_topic(dict(input_data.get("topic") or {}))

    directions: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    for raw in input_data.get("candidates") or []:
        candidate = dict(raw)
        direction = dict(candidate.pop("direction", {}) or {})
        direction_id = str(direction.get("id") or candidate.get("direction_id") or "")
        if direction_id:
            directions.setdefault(direction_id, _compact_direction(direction))
            candidate["direction_id"] = direction_id

        summary = str(candidate.get("summary") or "")
        if len(summary) > summary_limit:
            candidate["summary"] = _bounded_summary_excerpt(summary, summary_limit)
            candidate["summary_excerpted"] = True
        candidates.append(candidate)

    return {
        **input_data,
        "topic": topic,
        "directions": list(directions.values()),
        "candidates": candidates,
        "input_policy": {
            "summary_max_chars": summary_limit,
            "direction_config_deduplicated": True,
            "fulltext_forbidden": True,
        },
    }


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("payload_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _cache_eligible(row: dict[str, Any]) -> bool:
    payload = _payload(row)
    source_id = str(row.get("source_id") or "").lower()
    identity = str(row.get("identity_key") or "").lower()
    external_id = str(row.get("external_id") or "")
    if source_id == "arxiv" and re.search(r"v\d+$", external_id, flags=re.IGNORECASE):
        return True
    if payload.get("repo") and (payload.get("tag") or external_id):
        return True
    if identity.startswith("doi:"):
        return True
    return False


# The offline demo executor answers every relevance task with this fixed filler
# verdict (briefing_skill.demo._demo_output). Such judgements must never be
# committed to the production relevance cache regardless of bookkeeping.
_DEMO_VERDICT_PREFIX = "示例判定:"


def _is_demo_verdict(reason: Any) -> bool:
    return str(reason or "").lstrip().startswith(_DEMO_VERDICT_PREFIX)


def _relevance_cache_isolated(db, run_id: Any) -> bool:
    try:
        from .fact_cache_provenance import SYNTHETIC_MODES, execution_mode

        return execution_mode(db, str(run_id or "")) in SYNTHETIC_MODES
    except Exception:
        return False


def relevance_source_fingerprint(row: dict[str, Any]) -> str:
    return stable_hash(
        "relevance-source-v1",
        row.get("source_id"),
        row.get("identity_key"),
        row.get("external_id"),
        row.get("content_hash"),
        row.get("canonical_url") or row.get("original_url"),
        row.get("title"),
        row.get("summary"),
        length=32,
    )


def relevance_freshness_bucket(
    config,
    published_at: str | None,
    *,
    reference: str | date | datetime | None = None,
) -> str:
    """Bucket cached relevance by the configured freshness-score boundaries.

    Relevance review gives freshness up to five points. Reusing a score forever would
    make an old item stop ageing, so crossing a configured age boundary forces a fresh
    Agent review while repeated runs inside the same bucket can still reuse judgement.
    """

    age = published_age_days(published_at, reference=reference)
    if age is None:
        return "unknown"
    configured = config.scoring.get("freshness_days") or {}
    boundaries: list[int] = []
    for raw in configured:
        try:
            boundaries.append(int(raw))
        except (TypeError, ValueError):
            continue
    boundaries = sorted({value for value in boundaries if value >= 0}) or [2, 7, 30, 60]
    for boundary in boundaries:
        if age <= boundary:
            return f"age<={boundary}"
    return f"age>{boundaries[-1]}"


def relevance_evaluator_version(
    config,
    root: Path,
    topic_id: str,
    direction_id: str,
    published_at: str | None,
) -> str:
    """Invalidate cache when visible judging context, rules, or freshness bucket changes."""

    parts: list[str] = [
        "relevance-evaluator-v2",
        str(_summary_limit(config.settings)),
        relevance_freshness_bucket(config, published_at),
    ]
    for relative in ("prompts/relevance-batch.md", "schemas/relevance-batch.schema.json"):
        path = root / relative
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    try:
        topic = config.topic(topic_id)
        direction = config.direction(topic_id, direction_id)
        # Hash the same compact topic/direction cards the Agent actually sees.
        # Unrelated query/feed edits should not invalidate an otherwise identical review.
        parts.append(json.dumps(_compact_topic(topic), ensure_ascii=False, sort_keys=True))
        parts.append(json.dumps(_compact_direction(direction), ensure_ascii=False, sort_keys=True))
        context = config.context_path(Paths(root), topic_id)
        if context.is_file():
            parts.append(context.read_text(encoding="utf-8"))
    except Exception:
        parts.extend([topic_id, direction_id])
    return stable_hash(*parts, length=24)


def _cache_key(source_fingerprint: str, topic_id: str, direction_id: str, evaluator_version: str) -> str:
    return stable_hash(
        "relevance-cache-v1",
        source_fingerprint,
        topic_id,
        direction_id,
        evaluator_version,
        length=32,
    )


def apply_cached_relevance(config, db, root: Path, row: dict[str, Any]) -> bool:
    ensure_cost_schema(db)
    if _relevance_cache_isolated(db, row.get("run_id")):
        return False
    if not _cache_eligible(row):
        return False
    topic_id = str(row.get("topic_id") or "")
    direction_id = str(row.get("direction_id") or "")
    fingerprint = relevance_source_fingerprint(row)
    evaluator_version = relevance_evaluator_version(
        config,
        root,
        topic_id,
        direction_id,
        row.get("published_at"),
    )
    cache = db.fetchone(
        """
        SELECT * FROM relevance_cache
        WHERE source_fingerprint=? AND topic_id=? AND direction_id=? AND evaluator_version=?
        """,
        (fingerprint, topic_id, direction_id, evaluator_version),
    )
    if not cache:
        return False

    if _is_demo_verdict(cache.get("relevance_reason")):
        # Defense in depth: a demo-filler verdict must never steer a production run,
        # even if a legacy row survived in the cache.
        return False

    cached_reason = str(cache.get("relevance_reason") or "")
    if cached_reason and not summary_is_reader_chinese(cached_reason):
        # Legacy demo runs cached filler or non-Chinese reasons. The reader layers
        # refuse them, so replaying the verdict would push an unusable summary into
        # the briefing; treat the row as a miss and let this run re-judge the source.
        return False

    relevant = bool(cache.get("relevant"))
    fulltext = relevant and bool(cache.get("fulltext_required"))
    status = "RELEVANT" if fulltext else ("RADAR" if relevant else "REJECTED")
    db.execute(
        """
        UPDATE candidates
        SET relevant=?, relevance_score=?, relevance_reason=?, fulltext_required=?, status=?
        WHERE id=?
        """,
        (
            int(relevant),
            cache.get("relevance_score"),
            cache.get("relevance_reason"),
            int(fulltext),
            status,
            row["id"],
        ),
    )
    db.execute("UPDATE relevance_cache SET last_used_at=? WHERE cache_key=?", (now_iso(), cache["cache_key"]))
    db.execute(
        """
        INSERT OR REPLACE INTO relevance_cache_usage(run_id,candidate_id,cache_key,used_at)
        VALUES (?,?,?,?)
        """,
        (row["run_id"], row["id"], cache["cache_key"], now_iso()),
    )
    return True


def store_relevance_candidate(config, db, root: Path, candidate_id: str) -> bool:
    ensure_cost_schema(db)
    row = db.fetchone(
        """
        SELECT c.*, r.source_id, r.title, r.summary, r.original_url, r.canonical_url,
               r.identity_key, r.external_id, r.content_hash, r.payload_json, r.published_at
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.id=?
        """,
        (candidate_id,),
    )
    if not row or row.get("relevant") is None or not _cache_eligible(row):
        return False
    if _relevance_cache_isolated(db, row.get("run_id")):
        return False
    if _is_demo_verdict(row.get("relevance_reason")):
        return False
    topic_id = str(row.get("topic_id") or "")
    direction_id = str(row.get("direction_id") or "")
    fingerprint = relevance_source_fingerprint(row)
    evaluator_version = relevance_evaluator_version(
        config,
        root,
        topic_id,
        direction_id,
        row.get("published_at"),
    )
    key = _cache_key(fingerprint, topic_id, direction_id, evaluator_version)
    now = now_iso()
    db.execute(
        """
        INSERT INTO relevance_cache(
            cache_key,source_fingerprint,topic_id,direction_id,evaluator_version,
            source_url,source_identity,relevant,relevance_score,relevance_reason,
            fulltext_required,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_fingerprint,topic_id,direction_id,evaluator_version) DO UPDATE SET
            relevance_score=excluded.relevance_score,
            relevance_reason=excluded.relevance_reason,
            relevant=excluded.relevant,
            fulltext_required=excluded.fulltext_required,
            source_url=excluded.source_url,
            source_identity=excluded.source_identity,
            last_used_at=excluded.last_used_at
        """,
        (
            key,
            fingerprint,
            topic_id,
            direction_id,
            evaluator_version,
            row.get("original_url") or row.get("canonical_url"),
            row.get("identity_key"),
            int(bool(row.get("relevant"))),
            row.get("relevance_score"),
            row.get("relevance_reason"),
            int(bool(row.get("fulltext_required"))),
            now,
            now,
        ),
    )
    return True


def install_relevance_efficiency() -> None:
    """Install cross-run relevance reuse and compact character-bounded batches."""

    from . import efficiency
    from .config import ConfigBundle
    from .matching import RuleMatcher
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_relevance_efficiency_installed", False):
        return

    original_prepare = Pipeline.prepare_relevance
    original_apply = Pipeline._apply_task
    original_create = TaskService.create

    efficiency.plan_relevance_rows = plan_relevance_rows_bounded

    def prepare_relevance(self) -> int:
        # The coverage-policy wrapper is installed after this function and therefore
        # materialises historical backlog before entering here.
        RuleMatcher(self.config, self.db).create_candidates(self.run_id)
        rows = self.db.fetchall(
            """
            SELECT c.*, r.source_id, r.title, r.summary, r.original_url, r.canonical_url,
                   r.identity_key, r.external_id, r.content_hash, r.payload_json,
                   r.source_level, r.discovery_only, r.published_at
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.status='PENDING_RELEVANCE'
            """,
            (self.run_id,),
        )
        for row in rows:
            apply_cached_relevance(self.config, self.db, self.root, row)
        return original_prepare(self)

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task["task_type"] != "relevance_batch":
            return
        task_input = read_json(self.root / task["input_path"], {})
        for candidate in task_input.get("candidates") or []:
            candidate_id = str(candidate.get("candidate_id") or "")
            if candidate_id:
                store_relevance_candidate(self.config, self.db, self.root, candidate_id)

    def create(self, run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
        if task_type == "relevance_batch":
            settings = getattr(self, "_relevance_settings_cache", None)
            if settings is None:
                settings = ConfigBundle.load(Paths(self.root)).settings
                self._relevance_settings_cache = settings
            input_data = compact_relevance_batch_input(input_data, settings)
        return original_create(self, run_id, task_type, entity_id, input_data, **kwargs)

    Pipeline.prepare_relevance = prepare_relevance
    Pipeline._apply_task = apply_task
    TaskService.create = create
    Pipeline._relevance_efficiency_installed = True
    TaskService._relevance_compaction_installed = True
