from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .utils import now_iso, read_json, stable_hash, write_json


FACT_CACHE_PROVENANCE_VERSION = 2
TRUSTED_MODES = {"production", "replay"}
SYNTHETIC_MODES = {"demo", "fixture", "test"}


def production_source_run_condition(alias: str) -> str:
    """SQL condition restricting cross-run reads to production-namespace runs.

    Cross-run history (historical brief upgrades, deep backlog materialization)
    must never import items produced by demo/fixture/test/replay runs. Runs with
    no provenance row fall back to the same heuristic as `execution_mode`: only
    the `demo-` id prefix marks them synthetic.
    """

    modes = ",".join(f"'{mode}'" for mode in sorted(SYNTHETIC_MODES | {"replay"}))
    return (
        f"NOT EXISTS (SELECT 1 FROM run_execution_provenance p "
        f"WHERE p.run_id={alias}.run_id AND p.execution_mode IN ({modes})) "
        f"AND {alias}.run_id NOT LIKE 'demo-%' "
        f"AND {alias}.run_id NOT LIKE '%-replay-%'"
    )

FACT_CACHE_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_execution_provenance (
    run_id TEXT PRIMARY KEY,
    execution_mode TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_cache_v2 (
    cache_key TEXT PRIMARY KEY,
    cache_namespace TEXT NOT NULL,
    producer_mode TEXT NOT NULL,
    producer_run_id TEXT NOT NULL,
    provenance_version INTEGER NOT NULL,
    source_fingerprint TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    source_url TEXT,
    source_identity TEXT,
    external_id TEXT,
    source_content_hash TEXT NOT NULL DEFAULT '',
    source_text_hash TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    facts_hash TEXT NOT NULL,
    json_path TEXT NOT NULL,
    quality_score REAL,
    event_hint TEXT,
    raw_char_count INTEGER NOT NULL DEFAULT 0,
    evidence_char_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    UNIQUE(
        cache_namespace, source_fingerprint, extractor_version,
        source_content_hash, source_text_hash, evidence_hash
    )
);

CREATE INDEX IF NOT EXISTS idx_fact_cache_v2_lookup
ON fact_cache_v2(
    cache_namespace, source_fingerprint, extractor_version,
    source_content_hash, source_text_hash, evidence_hash
);
"""


def ensure_fact_cache_provenance_schema(db) -> None:
    with db.connect() as conn:
        conn.executescript(FACT_CACHE_V2_SCHEMA)


def set_run_execution_mode(db, run_id: str, mode: str) -> None:
    mode = str(mode or "").strip().lower()
    if mode not in TRUSTED_MODES | SYNTHETIC_MODES:
        raise ValueError(f"unsupported briefing execution mode: {mode}")
    ensure_fact_cache_provenance_schema(db)
    db.execute(
        """
        INSERT INTO run_execution_provenance(run_id,execution_mode,updated_at)
        VALUES (?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET
          execution_mode=excluded.execution_mode,updated_at=excluded.updated_at
        """,
        (run_id, mode, now_iso()),
    )


def _payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    value = raw.get("payload_json")
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def execution_mode(db, run_id: str, raw: dict[str, Any] | None = None) -> str:
    """Resolve producer mode conservatively; synthetic source payload always wins."""

    payload = _payload(raw)
    if payload.get("fixture"):
        return "fixture"
    ensure_fact_cache_provenance_schema(db)
    row = db.fetchone(
        "SELECT execution_mode FROM run_execution_provenance WHERE run_id=?",
        (run_id,),
    )
    if row and str(row.get("execution_mode") or ""):
        return str(row["execution_mode"])
    if str(run_id or "").startswith("demo-"):
        return "demo"
    if os.environ.get("BRIEFING_OFFLINE_REPLAY"):
        return "replay"
    return "production"


def readable_namespaces(mode: str) -> tuple[str, ...]:
    mode = str(mode or "production")
    if mode == "replay":
        # Replay may reuse facts proven in production, but production never consumes
        # replay outputs. This keeps acceptance experiments from poisoning live runs.
        return ("production", "replay")
    return (mode,)


def cache_namespace(mode: str) -> str:
    return str(mode or "production")


def _text_hash(text: str) -> str:
    return stable_hash("fact-cache-text-v2", text, length=32)


def _facts_hash(facts: dict[str, Any]) -> str:
    encoded = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return stable_hash("fact-cache-facts-v2", encoded, length=32)


def _source_content_hash(raw: dict[str, Any]) -> str:
    return str(raw.get("content_hash") or "")


def _read_text(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return value if value else None


def _resolve_local_fulltext(root: Path, run_dir: Path, raw: dict[str, Any]) -> str | None:
    payload = _payload(raw)
    value = payload.get("local_fulltext_path")
    if not value:
        return None
    source = Path(str(value))
    candidates = [source] if source.is_absolute() else [run_dir / source, root / source]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_relative_to(root.resolve()) and resolved.is_file():
                return _read_text(resolved)
        except (OSError, ValueError):
            continue
    return None


def _cached_fulltext(root: Path, run_dir: Path, raw: dict[str, Any], fingerprint: str) -> str | None:
    """Read exact already-materialized source text without network access."""

    payload = _payload(raw)
    if payload.get("fixture"):
        from .fulltext import FulltextService

        return FulltextService._sanitize_text(FulltextService._fallback_text(raw))
    local = _resolve_local_fulltext(root, run_dir, raw)
    if local:
        return local
    raw_cache_key = stable_hash("raw-fulltext-v1", fingerprint, length=32)
    return _read_text(root / "workspace" / "cache" / "fulltext" / f"{raw_cache_key}.md")


def _evidence_from_source(config, source_text: str, topic_id: str, direction_id: str) -> str | None:
    try:
        from .deep_efficiency import build_evidence_pack

        topic = config.topic(topic_id)
        direction = config.direction(topic_id, direction_id)
    except Exception:
        return None
    policy = dict(config.settings.get("efficiency") or {})
    max_chars = max(4000, int(policy.get("evidence_pack_max_chars", 18000)))
    return build_evidence_pack(source_text, topic, direction, max_chars=max_chars)


def expected_source_and_evidence_hashes(
    config,
    root: Path,
    run_dir: Path,
    raw: dict[str, Any],
    fingerprint: str,
    topic_id: str,
    direction_id: str,
) -> tuple[str, str] | None:
    source_text = _cached_fulltext(root, run_dir, raw, fingerprint)
    if not source_text:
        return None
    evidence = _evidence_from_source(config, source_text, topic_id, direction_id)
    if not evidence:
        return None
    return _text_hash(source_text), _text_hash(evidence)


def _cache_payload_is_valid(row: dict[str, Any], root: Path) -> dict[str, Any] | None:
    if int(row.get("provenance_version") or 0) != FACT_CACHE_PROVENANCE_VERSION:
        return None
    path = root / str(row.get("json_path") or "")
    payload = read_json(path, {}) if path.is_file() else {}
    provenance = payload.get("_cache_provenance") if isinstance(payload, dict) else None
    facts = payload.get("facts") if isinstance(payload, dict) else None
    if not isinstance(provenance, dict) or not isinstance(facts, dict):
        return None
    expected = {
        "provenance_version": FACT_CACHE_PROVENANCE_VERSION,
        "cache_namespace": row.get("cache_namespace"),
        "producer_mode": row.get("producer_mode"),
        "producer_run_id": row.get("producer_run_id"),
        "source_fingerprint": row.get("source_fingerprint"),
        "extractor_version": row.get("extractor_version"),
        "source_content_hash": row.get("source_content_hash") or "",
        "source_text_hash": row.get("source_text_hash"),
        "evidence_hash": row.get("evidence_hash"),
    }
    if any(provenance.get(key) != value for key, value in expected.items()):
        return None
    if _facts_hash(facts) != str(row.get("facts_hash") or ""):
        return None
    return facts


def lookup_fact_cache_v2(
    db,
    root: Path,
    *,
    mode: str,
    source_fingerprint: str,
    extractor_version: str,
    source_content_hash: str,
    source_text_hash: str,
    evidence_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    ensure_fact_cache_provenance_schema(db)
    for namespace in readable_namespaces(mode):
        row = db.fetchone(
            """
            SELECT * FROM fact_cache_v2
            WHERE cache_namespace=? AND source_fingerprint=? AND extractor_version=?
              AND source_content_hash=? AND source_text_hash=? AND evidence_hash=?
            ORDER BY last_used_at DESC LIMIT 1
            """,
            (
                namespace,
                source_fingerprint,
                extractor_version,
                source_content_hash,
                source_text_hash,
                evidence_hash,
            ),
        )
        if not row:
            continue
        facts = _cache_payload_is_valid(row, root)
        if facts is None:
            continue
        db.execute(
            "UPDATE fact_cache_v2 SET last_used_at=? WHERE cache_key=?",
            (now_iso(), row["cache_key"]),
        )
        return dict(row), facts
    return None


def _synthetic_fact_output(facts: dict[str, Any]) -> bool:
    notes = " ".join(str(value) for value in facts.get("source_notes") or []).lower()
    context = str(facts.get("evaluation_context") or "").lower()
    if "demo only" in notes or "offline fixture" in context or "离线fixture" in context or "离线夹具" in context:
        return True
    for evidence in facts.get("evidence") or []:
        text = " ".join(
            str(evidence.get(key) or "")
            for key in ("condition", "source_locator", "claim")
        ).lower()
        if "fixture" in text or "夹具" in text:
            return True
    return False


def _store_fact_cache_v2(
    service,
    task: dict[str, Any],
    task_input: dict[str, Any],
    facts: dict[str, Any],
    raw: dict[str, Any],
) -> None:
    document = task_input.get("document") or {}
    if not document.get("fact_cache_v2_eligible") or document.get("fact_cache_hit"):
        return
    if not facts.get("primary_source_resolved"):
        return

    mode = str(document.get("fact_cache_v2_mode") or execution_mode(service.db, service.run_id, raw))
    namespace = str(document.get("fact_cache_v2_namespace") or cache_namespace(mode))
    if mode in TRUSTED_MODES and _synthetic_fact_output(facts):
        # A demo/fixture executor must never be able to mint a trusted cache record,
        # even if the surrounding run was accidentally labelled production/replay.
        return

    fingerprint = str(document.get("source_fingerprint") or "")
    version = str(document.get("extractor_version") or "")
    source_text_hash = str(document.get("source_text_hash") or "")
    evidence_hash = str(document.get("evidence_hash") or "")
    content_hash = str(document.get("source_content_hash") or "")
    if not all((fingerprint, version, source_text_hash, evidence_hash)):
        return

    clean_facts = dict(facts)
    clean_facts.pop("_provenance", None)
    facts_hash = _facts_hash(clean_facts)
    cache_key = stable_hash(
        "fact-cache-v2",
        namespace,
        fingerprint,
        version,
        content_hash,
        source_text_hash,
        evidence_hash,
        length=32,
    )
    cache_path = service.root / "workspace" / "cache" / "facts-v2" / namespace / f"{cache_key}.json"
    provenance = {
        "provenance_version": FACT_CACHE_PROVENANCE_VERSION,
        "cache_namespace": namespace,
        "producer_mode": mode,
        "producer_run_id": service.run_id,
        "source_fingerprint": fingerprint,
        "extractor_version": version,
        "source_content_hash": content_hash,
        "source_text_hash": source_text_hash,
        "evidence_hash": evidence_hash,
    }
    write_json(cache_path, {"_cache_provenance": provenance, "facts": clean_facts})
    source = task_input.get("source") or {}
    now = now_iso()
    ensure_fact_cache_provenance_schema(service.db)
    service.db.execute(
        """
        INSERT INTO fact_cache_v2(
          cache_key,cache_namespace,producer_mode,producer_run_id,provenance_version,
          source_fingerprint,extractor_version,source_url,source_identity,external_id,
          source_content_hash,source_text_hash,evidence_hash,facts_hash,json_path,
          quality_score,event_hint,raw_char_count,evidence_char_count,created_at,last_used_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(
          cache_namespace,source_fingerprint,extractor_version,
          source_content_hash,source_text_hash,evidence_hash
        ) DO UPDATE SET
          cache_key=excluded.cache_key,
          producer_mode=excluded.producer_mode,
          producer_run_id=excluded.producer_run_id,
          provenance_version=excluded.provenance_version,
          source_url=excluded.source_url,
          source_identity=excluded.source_identity,
          external_id=excluded.external_id,
          facts_hash=excluded.facts_hash,
          json_path=excluded.json_path,
          quality_score=excluded.quality_score,
          event_hint=excluded.event_hint,
          raw_char_count=excluded.raw_char_count,
          evidence_char_count=excluded.evidence_char_count,
          last_used_at=excluded.last_used_at
        """,
        (
            cache_key,
            namespace,
            mode,
            service.run_id,
            FACT_CACHE_PROVENANCE_VERSION,
            fingerprint,
            version,
            source.get("url"),
            raw.get("identity_key"),
            raw.get("external_id"),
            content_hash,
            source_text_hash,
            evidence_hash,
            facts_hash,
            str(cache_path.relative_to(service.root)),
            clean_facts.get("quality_score"),
            clean_facts.get("event_hint"),
            int(document.get("raw_char_count") or 0),
            int(document.get("evidence_char_count") or 0),
            now,
            now,
        ),
    )


def install_fact_cache_provenance() -> None:
    """Replace legacy fact-cache reads/writes with provenance-isolated v2 cache."""

    from . import demo as demo_module
    from .collection import CollectionService
    from .db import Database
    from .deep_efficiency import _cache_eligible, _runtime_extractor_version, _source_fingerprint
    from .fulltext import FulltextService
    from .pipeline import Pipeline
    from .tasks import TASK_BINDING_KEY, TaskService

    if getattr(Pipeline, "_fact_cache_provenance_installed", False):
        return

    original_db_init = Database.init

    def db_init(self) -> None:
        original_db_init(self)
        ensure_fact_cache_provenance_schema(self)

    Database.init = db_init

    original_collect = CollectionService.collect

    def collect(self, run_id: str, *args, **kwargs):
        offline_fixture = bool(kwargs.get("offline_fixture"))
        if len(args) >= 1:
            offline_fixture = bool(args[0])
        if offline_fixture:
            set_run_execution_mode(self.db, run_id, "fixture")
        return original_collect(self, run_id, *args, **kwargs)

    CollectionService.collect = collect

    original_demo_complete = demo_module.complete_pending_demo_tasks

    def complete_pending_demo_tasks(root: Path, db, run_id: str) -> int:
        set_run_execution_mode(db, run_id, "demo")
        return original_demo_complete(root, db, run_id)

    demo_module.complete_pending_demo_tasks = complete_pending_demo_tasks

    original_fetch = FulltextService.fetch_candidate

    def fetch_candidate(self, run_id: str, candidate: dict) -> dict:
        effective = dict(candidate)
        if not effective.get("topic_id") or not effective.get("direction_id"):
            lane = self.db.fetchone(
                "SELECT topic_id,direction_id FROM candidates WHERE id=?",
                (effective["id"],),
            )
            if lane:
                effective.setdefault("topic_id", lane.get("topic_id"))
                effective.setdefault("direction_id", lane.get("direction_id"))
        raw = self.db.fetchone("SELECT * FROM raw_items WHERE id=?", (effective["raw_item_id"],))
        if not raw:
            raise KeyError(effective["raw_item_id"])
        root = self.run_dir.parents[2]
        topic_id = str(effective.get("topic_id") or "")
        direction_id = str(effective.get("direction_id") or "")
        fingerprint = _source_fingerprint(raw)
        version = _runtime_extractor_version(self.config, root, topic_id, direction_id)
        mode = execution_mode(self.db, run_id, raw)
        content_hash = _source_content_hash(raw)
        eligible = bool((self.config.settings.get("efficiency") or {}).get("fact_cache_enabled", True)) and _cache_eligible(raw)

        expected_hashes = None
        if eligible and topic_id and direction_id:
            expected_hashes = expected_source_and_evidence_hashes(
                self.config, root, self.run_dir, raw, fingerprint, topic_id, direction_id
            )
        if expected_hashes:
            source_text_hash, evidence_hash = expected_hashes
            hit = lookup_fact_cache_v2(
                self.db,
                root,
                mode=mode,
                source_fingerprint=fingerprint,
                extractor_version=version,
                source_content_hash=content_hash,
                source_text_hash=source_text_hash,
                evidence_hash=evidence_hash,
            )
            if hit:
                row, _facts = hit
                url = raw.get("original_url") or raw.get("canonical_url") or raw.get("aihot_url")
                document_id = stable_hash(run_id, effective["id"], url)
                stub = self.run_dir / "documents" / f"{document_id}.evidence.md"
                stub.parent.mkdir(parents=True, exist_ok=True)
                stub.write_text(
                    "# Fact cache v2 hit\n\nValidated facts are reused only after exact source/evidence provenance match.\n",
                    encoding="utf-8",
                )
                return {
                    "document_id": document_id,
                    "candidate_id": effective["id"],
                    "url": url,
                    "media_type": "application/x-fact-cache-v2",
                    "fetch_status": "FETCHED",
                    "text_path": str(stub),
                    "chunks": [str(stub)],
                    "char_count": int(row.get("evidence_char_count") or 0),
                    "raw_char_count": int(row.get("raw_char_count") or 0),
                    "evidence_char_count": int(row.get("evidence_char_count") or 0),
                    "fact_cache_hit": True,
                    "fact_cache_v2_hit": True,
                    "fact_cache_key": row["cache_key"],
                    "fact_cache_v2_key": row["cache_key"],
                    "fact_cache_v2_namespace": row["cache_namespace"],
                    "fact_cache_v2_mode": mode,
                    "source_fingerprint": fingerprint,
                    "extractor_version": version,
                    "source_content_hash": content_hash,
                    "source_text_hash": source_text_hash,
                    "evidence_hash": evidence_hash,
                    "evidence_strategy": "front-evidence-v2",
                    "error": None,
                }

        # The legacy fact_cache table is intentionally never consulted again. Disable
        # only that inner layer while preserving raw-fulltext and all other fetch caches.
        policy = self.config.settings.setdefault("efficiency", {})
        sentinel = object()
        previous = policy.get("fact_cache_enabled", sentinel)
        policy["fact_cache_enabled"] = False
        try:
            manifest = original_fetch(self, run_id, effective)
        finally:
            if previous is sentinel:
                policy.pop("fact_cache_enabled", None)
            else:
                policy["fact_cache_enabled"] = previous

        # Never let the old apply wrapper write legacy cache rows.
        manifest["fact_cache_eligible"] = False
        manifest["fact_cache_v2_eligible"] = False
        manifest["fact_cache_v2_mode"] = mode
        manifest["fact_cache_v2_namespace"] = cache_namespace(mode)
        manifest["source_content_hash"] = content_hash

        if eligible and topic_id and direction_id and str(manifest.get("fetch_status") or "").upper() != "FALLBACK":
            evidence_text = _read_text(Path(str(manifest.get("text_path") or "")))
            source_text = _cached_fulltext(root, self.run_dir, raw, fingerprint)
            if source_text is None:
                source_text = _read_text(
                    self.run_dir / "documents" / f"{manifest.get('document_id')}.md"
                )
            if source_text and evidence_text:
                manifest["source_text_hash"] = _text_hash(source_text)
                manifest["evidence_hash"] = _text_hash(evidence_text)
                manifest["fact_cache_v2_eligible"] = True
        write_json(
            self.run_dir / "documents" / f"{manifest['document_id']}.json",
            manifest,
        )
        return manifest

    FulltextService.fetch_candidate = fetch_candidate

    original_create = TaskService.create

    def create(self, run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
        row = original_create(self, run_id, task_type, entity_id, input_data, **kwargs)
        if task_type != "fact_extraction":
            return row
        document = input_data.get("document") or {}
        if not document.get("fact_cache_v2_hit"):
            return row
        ensure_fact_cache_provenance_schema(self.db)
        cache = self.db.fetchone(
            "SELECT * FROM fact_cache_v2 WHERE cache_key=?",
            (document.get("fact_cache_v2_key"),),
        )
        if not cache:
            return row
        facts = _cache_payload_is_valid(cache, self.root)
        if facts is None:
            return row
        task_input = read_json(self.root / row["input_path"], {})
        binding = task_input.get(TASK_BINDING_KEY)
        if not binding:
            return row
        write_json(self.root / row["output_path"], {TASK_BINDING_KEY: binding, **facts})
        return row

    TaskService.create = create

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task.get("task_type") != "fact_extraction":
            return
        task_input = read_json(self.root / task["input_path"], {})
        document = task_input.get("document") or {}
        if document.get("fact_cache_v2_hit") or not document.get("fact_cache_v2_eligible"):
            return
        facts_row = self.db.fetchone(
            "SELECT * FROM facts WHERE run_id=? AND candidate_id=?",
            (self.run_id, task["entity_id"]),
        )
        if not facts_row:
            return
        facts = read_json(self.root / facts_row["json_path"], {})
        candidate = self.db.fetchone(
            "SELECT raw_item_id FROM candidates WHERE id=?",
            (task["entity_id"],),
        )
        raw = self.db.fetchone(
            "SELECT * FROM raw_items WHERE id=?",
            (candidate["raw_item_id"],),
        ) if candidate else None
        if not raw:
            return
        _store_fact_cache_v2(self, task, task_input, facts, raw)

    Pipeline._apply_task = apply_task

    Pipeline._fact_cache_provenance_installed = True
    FulltextService._fact_cache_provenance_installed = True
    TaskService._fact_cache_provenance_installed = True
