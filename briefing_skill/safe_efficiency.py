from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .utils import now_iso, read_json, stable_hash, write_json

LOGGER = logging.getLogger(__name__)


PRIMARY_IDENTITY_PREFIXES = (
    "arxiv:",
    "doi:",
    "github:",
    "github-release:",
    "github-commit:",
)


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("payload_json")
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _is_exact_primary(row: dict[str, Any]) -> bool:
    identity = str(row.get("identity_key") or "").lower()
    return (
        str(row.get("source_level") or "").upper() == "A"
        and not bool(row.get("discovery_only"))
        and identity.startswith(PRIMARY_IDENTITY_PREFIXES)
    )


def dedupe_exact_primary_candidates(db, run_id: str) -> int:
    """Suppress duplicate relevance work for one exact primary in one routing lane.

    The same source may still be analysed under different topic/direction contexts;
    only duplicate discovery paths that resolve to the exact same primary identity
    *and* the same topic/direction are collapsed.
    """

    rows = db.fetchall(
        """
        SELECT c.*, r.identity_key, r.source_id, r.discovery_source,
               r.source_level, r.discovery_only, r.priority AS raw_priority,
               r.payload_json
        FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
        WHERE c.run_id=? AND c.status='PENDING_RELEVANCE'
        ORDER BY c.rule_score DESC, r.priority DESC, c.id
        """,
        (run_id,),
    )
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not _is_exact_primary(row):
            continue
        key = (
            str(row.get("identity_key") or "").lower(),
            str(row.get("topic_id") or ""),
            str(row.get("direction_id") or ""),
        )
        groups.setdefault(key, []).append(row)

    suppressed = 0
    for members in groups.values():
        if len(members) <= 1:
            continue

        def rank(row: dict[str, Any]) -> tuple[float, int, float, str]:
            payload = _payload(row)
            direct_primary = 0 if payload.get("primary_source_resolution") else 1
            return (
                float(row.get("rule_score") or 0),
                direct_primary,
                float(row.get("raw_priority") or 0),
                str(row.get("id") or ""),
            )

        winner = max(members, key=rank)
        discovered_via: list[str] = []
        for member in members:
            payload = _payload(member)
            for value in [*(payload.get("discovered_via") or []), member.get("discovery_source")]:
                label = str(value or "").strip()
                if label and label not in discovered_via:
                    discovered_via.append(label)
        winner_payload = _payload(winner)
        if discovered_via:
            winner_payload["discovered_via"] = discovered_via
            db.execute(
                "UPDATE raw_items SET payload_json=? WHERE id=?",
                (json.dumps(winner_payload, ensure_ascii=False), winner["raw_item_id"]),
            )

        for member in members:
            if member["id"] == winner["id"]:
                continue
            db.execute(
                """
                UPDATE candidates
                SET status='DUPLICATE_PRIMARY', relevant=0,
                    relevance_reason=?
                WHERE id=?
                """,
                (f"exact primary duplicate of candidate {winner['id']}", member["id"]),
            )
            suppressed += 1
    return suppressed


def _editorial_score_floor(config) -> float:
    mode = str(config.settings.get("issue_mode") or "compact")
    if mode == "expanded_v2":
        expanded = dict(config.scoring.get("expanded_v2") or {})
        return float(expanded.get("observation_score", 60))
    thresholds = dict(config.scoring.get("thresholds") or {})
    return float(thresholds.get("issue_minimum", 70))


def _defer_fallback_fact_input(input_data: dict[str, Any]) -> bool:
    document = input_data.get("document") or {}
    return (
        str(document.get("fetch_status") or "").upper() == "FALLBACK"
        and not bool(document.get("fact_cache_hit"))
    )


def pick_deep_refill_rows(
    deferred_rows: Iterable[dict[str, Any]],
    *,
    existing_total: int,
    existing_topic_counts: dict[str, int],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fill only deep-budget slots vacated by fetch failures.

    This mirrors the existing total/per-topic budget and ranking. It never expands
    the configured deep budget; it only prevents an unfetchable source from silently
    reducing information volume when another already-relevant A-level candidate is
    waiting in DEFERRED_BUDGET.
    """

    policy = dict(settings.get("efficiency") or {})
    total_max = max(1, int(policy.get("max_fact_candidates_total", 10)))
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 3)))
    slots = max(0, total_max - max(0, int(existing_total)))
    if not slots:
        return []

    counts: dict[str, int] = defaultdict(int)
    counts.update({str(key): max(0, int(value)) for key, value in existing_topic_counts.items()})

    def number(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    ordered = sorted(
        [dict(row) for row in deferred_rows],
        key=lambda row: (
            -number(row.get("relevance_score")),
            -number(row.get("rule_score")),
            -number(row.get("priority")),
            str(row.get("id") or ""),
        ),
    )
    selected: list[dict[str, Any]] = []
    for row in ordered:
        if len(selected) >= slots:
            break
        topic_id = str(row.get("topic_id") or "unknown")
        if counts[topic_id] >= per_topic_max:
            continue
        selected.append(row)
        counts[topic_id] += 1
    return selected


def _annotate_event(db, event_id: str, **updates: Any) -> None:
    row = db.fetchone("SELECT payload_json FROM events WHERE id=?", (event_id,))
    if not row:
        return
    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(updates)
    db.execute(
        "UPDATE events SET payload_json=?, last_updated_at=? WHERE id=?",
        (json.dumps(payload, ensure_ascii=False), now_iso(), event_id),
    )


def install_safe_efficiency() -> None:
    """Install deterministic savings that do not weaken evidence or selection rules.

    This installer must run before deep-efficiency so the raw-fulltext cache is the
    fetch implementation captured by the later evidence-pack wrapper.
    """

    from .deep_efficiency import _cache_eligible, _source_fingerprint
    from .fulltext import FulltextService
    from .matching import RuleMatcher
    from .pipeline import Pipeline

    if getattr(Pipeline, "_safe_efficiency_installed", False):
        return

    original_create_candidates = RuleMatcher.create_candidates
    original_fetch = FulltextService._fetch
    original_fetch_candidate = FulltextService.fetch_candidate
    original_prepare_facts = Pipeline._maybe_prepare_facts
    original_prepare_items = Pipeline._maybe_prepare_items

    def create_candidates(self, run_id: str):
        rows = original_create_candidates(self, run_id)
        dedupe_exact_primary_candidates(self.db, run_id)
        return rows

    def fetch(self, url: str, raw: dict):
        self._raw_fulltext_cache_hit = False
        self._raw_fulltext_cache_key = None
        if not _cache_eligible(raw):
            return original_fetch(self, url, raw)

        root = self.run_dir.parents[2]
        fingerprint = _source_fingerprint(raw)
        cache_key = stable_hash("raw-fulltext-v1", fingerprint, length=32)
        cache_dir = root / "workspace" / "cache" / "fulltext"
        text_path = cache_dir / f"{cache_key}.md"
        meta_path = cache_dir / f"{cache_key}.json"
        if text_path.is_file() and meta_path.is_file():
            metadata = read_json(meta_path, {})
            text = text_path.read_text(encoding="utf-8")
            if text:
                self._raw_fulltext_cache_hit = True
                self._raw_fulltext_cache_key = cache_key
                return text, str(metadata.get("media_type") or "text/plain")

        text, media_type = original_fetch(self, url, raw)
        max_chars = int(self.config.settings.get("max_fulltext_chars", 140000))
        cached_text = self._sanitize_text(text)[:max_chars]
        cache_dir.mkdir(parents=True, exist_ok=True)
        text_path.write_text(cached_text, encoding="utf-8")
        write_json(
            meta_path,
            {
                "cache_key": cache_key,
                "source_fingerprint": fingerprint,
                "source_identity": raw.get("identity_key"),
                "source_url": url,
                "media_type": media_type,
                "char_count": len(cached_text),
                "created_at": now_iso(),
            },
        )
        self._raw_fulltext_cache_key = cache_key
        return cached_text, media_type

    def fetch_candidate(self, run_id: str, candidate: dict):
        self._raw_fulltext_cache_hit = False
        self._raw_fulltext_cache_key = None
        manifest = original_fetch_candidate(self, run_id, candidate)
        manifest = {
            **manifest,
            "raw_fulltext_cache_hit": bool(getattr(self, "_raw_fulltext_cache_hit", False)),
            "raw_fulltext_cache_key": getattr(self, "_raw_fulltext_cache_key", None),
        }
        write_json(self.run_dir / "documents" / f"{manifest['document_id']}.json", manifest)
        return manifest

    def maybe_prepare_facts(self) -> None:
        skipped: list[str] = []
        bound_create = self.tasks.create
        had_override = "create" in self.tasks.__dict__
        previous_override = self.tasks.__dict__.get("create")

        def create(run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
            if task_type == "fact_extraction" and _defer_fallback_fact_input(input_data):
                candidate_id = str(entity_id)
                skipped.append(candidate_id)
                audit_path = self.run_dir / "facts" / "deferred_fetch" / f"{candidate_id}.json"
                write_json(
                    audit_path,
                    {
                        "candidate_id": candidate_id,
                        "reason": "primary fulltext fetch failed; summary fallback is not eligible for deep fact extraction",
                        "source": input_data.get("source") or {},
                        "document": input_data.get("document") or {},
                        "deferred_at": now_iso(),
                    },
                )
                return {
                    "id": stable_hash(run_id, "deferred-fetch", candidate_id),
                    "run_id": run_id,
                    "task_type": task_type,
                    "entity_id": candidate_id,
                    "status": "DEFERRED_FETCH",
                }
            return bound_create(run_id, task_type, entity_id, input_data, **kwargs)

        self.tasks.create = create
        try:
            original_prepare_facts(self)
            refill_rounds = 0
            while refill_rounds < 4:
                # The underlying planner marks every attempted fact candidate
                # FACT_TASKED after create() returns. Restore failed candidates to
                # the terminal deferred state before counting occupied budget slots.
                for candidate_id in skipped:
                    self.db.execute(
                        "UPDATE candidates SET status='DEFERRED_FETCH' WHERE id=?",
                        (candidate_id,),
                    )

                occupied = self.db.fetchall(
                    """
                    SELECT c.topic_id, COUNT(*) AS n
                    FROM tasks t JOIN candidates c ON c.id=t.entity_id
                    WHERE t.run_id=? AND t.task_type='fact_extraction'
                    GROUP BY c.topic_id
                    """,
                    (self.run_id,),
                )
                topic_counts = {str(row["topic_id"]): int(row["n"]) for row in occupied}
                existing_total = sum(topic_counts.values())
                deferred = self.db.fetchall(
                    """
                    SELECT c.*, r.priority
                    FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
                    WHERE c.run_id=? AND c.status='DEFERRED_BUDGET'
                      AND c.fulltext_required=1
                      AND r.source_level='A' AND r.discovery_only=0
                    ORDER BY c.relevance_score DESC, c.rule_score DESC, r.priority DESC, c.id
                    """,
                    (self.run_id,),
                )
                fillers = pick_deep_refill_rows(
                    deferred,
                    existing_total=existing_total,
                    existing_topic_counts=topic_counts,
                    settings=self.config.settings,
                )
                if not fillers:
                    break
                for row in fillers:
                    self.db.execute("UPDATE candidates SET status='RELEVANT' WHERE id=?", (row["id"],))
                before_tasks = existing_total
                before_skipped = len(skipped)
                original_prepare_facts(self)
                refill_rounds += 1
                after_tasks = self.db.fetchone(
                    "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_extraction'",
                    (self.run_id,),
                )["n"]
                if after_tasks <= before_tasks and len(skipped) <= before_skipped:
                    break
        finally:
            if had_override:
                self.tasks.create = previous_override
            else:
                del self.tasks.create

        for candidate_id in skipped:
            self.db.execute(
                "UPDATE candidates SET status='DEFERRED_FETCH' WHERE id=?",
                (candidate_id,),
            )

        if skipped:
            fact_tasks = self.db.fetchone(
                "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_extraction'",
                (self.run_id,),
            )["n"]
            fact_count = self.db.fetchone(
                "SELECT COUNT(*) AS n FROM facts WHERE run_id=?",
                (self.run_id,),
            )["n"]
            if not fact_tasks and not fact_count:
                self.db.update_run(self.run_id, stage="FETCH_DEFERRED")

    def maybe_prepare_items(self) -> None:
        floor = _editorial_score_floor(self.config)
        skipped: list[tuple[str, float]] = []
        bound_create = self.tasks.create
        had_override = "create" in self.tasks.__dict__
        previous_override = self.tasks.__dict__.get("create")

        def create(run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
            if task_type == "item_writing":
                score = float(input_data.get("score") or 0)
                if score < floor:
                    event_id = str(entity_id)
                    skipped.append((event_id, score))
                    _annotate_event(
                        self.db,
                        event_id,
                        editorial_deferred=True,
                        editorial_deferred_reason="deterministic score below minimum selectable issue role",
                        editorial_score=score,
                        editorial_score_floor=floor,
                    )
                    return {
                        "id": stable_hash(run_id, "deferred-editorial", event_id),
                        "run_id": run_id,
                        "task_type": task_type,
                        "entity_id": event_id,
                        "status": "DEFERRED_SCORE",
                    }
            return bound_create(run_id, task_type, entity_id, input_data, **kwargs)

        self.tasks.create = create
        try:
            original_prepare_items(self)
        finally:
            if had_override:
                self.tasks.create = previous_override
            else:
                del self.tasks.create

        if skipped:
            actual_tasks = self.db.fetchone(
                """
                SELECT COUNT(*) AS n FROM tasks
                WHERE run_id=? AND task_type IN ('item_writing','item_writing_batch')
                """,
                (self.run_id,),
            )["n"]
            item_count = self.db.fetchone(
                "SELECT COUNT(*) AS n FROM brief_items WHERE run_id=?",
                (self.run_id,),
            )["n"]
            if not actual_tasks and not item_count:
                self.db.update_run(self.run_id, stage="NO_EDITORIAL_ELIGIBLE")

    RuleMatcher.create_candidates = create_candidates
    FulltextService._fetch = fetch
    FulltextService.fetch_candidate = fetch_candidate
    Pipeline._maybe_prepare_facts = maybe_prepare_facts
    Pipeline._maybe_prepare_items = maybe_prepare_items
    RuleMatcher._exact_primary_dedup_installed = True
    FulltextService._raw_fulltext_cache_installed = True
    Pipeline._safe_efficiency_installed = True
