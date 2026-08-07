from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .cost_schema import ensure_cost_schema
from .paths import Paths
from .utils import now_iso, read_json, stable_hash, write_json


EVIDENCE_SIGNALS = (
    "abstract", "introduction", "overview", "background", "motivation",
    "method", "design", "architecture", "implementation", "algorithm",
    "evaluation", "experiment", "results", "benchmark", "performance",
    "latency", "throughput", "bandwidth", "p99", "speedup", "overhead",
    "limitation", "limitations", "discussion", "conclusion",
    "方法", "设计", "架构", "实现", "实验", "评估", "性能", "时延",
    "吞吐", "带宽", "开销", "限制", "局限", "结论",
)

HEADING_WEIGHTS = {
    "abstract": 9,
    "evaluation": 9,
    "experiment": 9,
    "results": 9,
    "benchmark": 9,
    "method": 7,
    "design": 7,
    "architecture": 7,
    "implementation": 6,
    "limitation": 8,
    "discussion": 5,
    "conclusion": 5,
    "introduction": 4,
    "实验": 9,
    "评估": 9,
    "性能": 8,
    "方法": 7,
    "设计": 7,
    "架构": 7,
    "实现": 6,
    "限制": 8,
    "局限": 8,
    "结论": 5,
}


def _payload(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(raw.get("payload_json") or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _source_fingerprint(raw: dict[str, Any]) -> str:
    payload = _payload(raw)
    return stable_hash(
        "facts-source-v1",
        raw.get("identity_key"),
        raw.get("external_id"),
        raw.get("content_hash"),
        raw.get("canonical_url") or raw.get("original_url"),
        payload.get("pdf_url"),
        payload.get("tag"),
        length=32,
    )


def _cache_eligible(raw: dict[str, Any]) -> bool:
    """Allow zero-fetch reuse only for sources with a strong immutable version identity."""

    payload = _payload(raw)
    external_id = str(raw.get("external_id") or "")
    identity = str(raw.get("identity_key") or "").lower()
    source_id = str(raw.get("source_id") or "").lower()
    if source_id == "arxiv" and re.search(r"v\d+$", external_id, flags=re.IGNORECASE):
        return True
    if payload.get("repo") and (payload.get("tag") or external_id):
        return True
    if identity.startswith("doi:"):
        return True
    return False


def _extractor_version(config) -> str:
    policy = dict(config.settings.get("efficiency") or {})
    return str(policy.get("fact_extractor_version") or "front-evidence-v2")


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


def _runtime_extractor_version(
    config,
    root: Path,
    topic_id: str | None = None,
    direction_id: str | None = None,
) -> str:
    """Invalidate facts when source interpretation context or extraction policy changes.

    Facts include project-specific interpretation, so a cache produced for one topic or
    direction must never be reused under another. The version also captures the exact
    project context card and front-evidence policy in addition to prompt/schema changes.
    """

    policy = dict(config.settings.get("efficiency") or {})
    parts = [
        _extractor_version(config),
        "front-evidence-v2",
        str(policy.get("evidence_pack_max_chars", 18000)),
        str(bool(policy.get("evidence_repair_enabled", True))),
        str(policy.get("evidence_repair_max_chars", 9000)),
    ]
    for relative in ("prompts/fact-extraction.md", "schemas/facts.schema.json"):
        path = root / relative
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))

    if topic_id and direction_id:
        try:
            topic = config.topic(topic_id)
            direction = config.direction(topic_id, direction_id)
            parts.append(json.dumps(_compact_topic(topic), ensure_ascii=False, sort_keys=True))
            parts.append(json.dumps(_compact_direction(direction), ensure_ascii=False, sort_keys=True))
            context = config.context_path(Paths(root), topic_id)
            if context.is_file():
                parts.append(context.read_text(encoding="utf-8"))
        except Exception:
            # Fail closed for cache reuse: even a minimal/diagnostic config gets a
            # context-specific version instead of accidentally sharing generic facts.
            parts.extend([str(topic_id), str(direction_id)])

    return f"{parts[0]}:{stable_hash(*parts, length=16)}"


def _evidence_terms(topic: dict[str, Any], direction: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(str(value) for value in direction.get("include_terms") or [])
    values.extend(str(value) for value in direction.get("queries") or [])
    values.extend(str(value) for value in topic.get("current_questions") or [])
    values.extend(str(value) for value in topic.get("valuable_evidence") or [])
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+./-]{2,}|[\u4e00-\u9fff]{2,8}", value.lower()):
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= 60:
                return tokens
    return tokens


def _sections(text: str) -> list[tuple[int, str, str]]:
    heading = re.compile(r"(?m)^(#{1,4})\s+(.+?)\s*$\n?")
    matches = list(heading.finditer(text))
    if not matches:
        size = 4200
        return [
            (index, f"Text block {index + 1}", text[index * size : (index + 1) * size])
            for index in range((len(text) + size - 1) // size)
        ]
    result: list[tuple[int, str, str]] = []
    if matches[0].start() > 0:
        result.append((0, "Document preface", text[: matches[0].start()]))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((len(result), match.group(2).strip(), text[start:end].strip()))
    return result


def _section_score(index: int, title: str, body: str, terms: list[str]) -> float:
    lower_title = title.lower()
    lower = body.lower()
    score = 0.0
    if index <= 1:
        score += 4.0 - index
    for signal, weight in HEADING_WEIGHTS.items():
        if signal in lower_title:
            score += weight
    term_hits = sum(1 for term in terms if term and term in lower)
    score += min(10.0, term_hits * 1.25)
    signal_hits = sum(1 for signal in EVIDENCE_SIGNALS if signal in lower)
    score += min(5.0, signal_hits * 0.6)
    number_hits = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|ms|us|µs|s|gbps|mbps|gb/s|x|×)\b", lower))
    score += min(6.0, number_hits * 0.8)
    if re.search(r"\b(?:figure|fig\.|table|baseline|workload|hardware|dataset)\b", lower):
        score += 3.0
    return score


def _safe_excerpt(text: str, limit: int) -> str:
    value = text.strip()
    if len(value) <= limit:
        return value
    clipped = value[:limit]
    sentence_matches = list(re.finditer(r"[。！？.!?](?:[”’\"）)\]]*)", clipped))
    if sentence_matches and sentence_matches[-1].end() >= max(120, int(limit * 0.55)):
        return clipped[: sentence_matches[-1].end()].strip()
    paragraph = clipped.rfind("\n\n")
    if paragraph >= max(120, int(limit * 0.55)):
        return clipped[:paragraph].strip()
    return clipped.rstrip()


def build_evidence_pack(
    text: str,
    topic: dict[str, Any],
    direction: dict[str, Any],
    *,
    max_chars: int = 18000,
) -> str:
    """Return the beginning of the primary source, bounded at a clean sentence/paragraph.

    Abstract + introduction normally establish problem, mechanism and claimed
    contribution. Evaluation details that are material to the final briefing are
    retrieved later through the existing one-shot targeted Evidence Repair path.
    Topic/direction arguments remain in the signature for compatibility and for the
    context-aware cache version, but they no longer reorder source text.
    """

    del topic, direction
    return _safe_excerpt(text, max_chars)


def install_deep_efficiency() -> None:
    """Install front evidence and conservative, context-aware cross-run fact reuse."""

    from .fulltext import FulltextService
    from .pipeline import Pipeline
    from .tasks import TASK_BINDING_KEY, TaskService

    if getattr(FulltextService, "_evidence_pack_installed", False):
        return

    original_fetch = FulltextService.fetch_candidate
    original_create = TaskService.create
    original_apply = Pipeline._apply_task

    def fetch_candidate(self, run_id: str, candidate: dict) -> dict:
        ensure_cost_schema(self.db)
        effective_candidate = dict(candidate)
        if not effective_candidate.get("topic_id") or not effective_candidate.get("direction_id"):
            candidate_row = self.db.fetchone(
                "SELECT topic_id,direction_id FROM candidates WHERE id=?",
                (effective_candidate["id"],),
            )
            if candidate_row:
                effective_candidate.setdefault("topic_id", candidate_row.get("topic_id"))
                effective_candidate.setdefault("direction_id", candidate_row.get("direction_id"))
        raw = self.db.fetchone("SELECT * FROM raw_items WHERE id=?", (effective_candidate["raw_item_id"],))
        if not raw:
            raise KeyError(effective_candidate["raw_item_id"])
        root = self.run_dir.parents[2]
        topic_id = effective_candidate.get("topic_id")
        direction_id = effective_candidate.get("direction_id")
        fingerprint = _source_fingerprint(raw)
        version = _runtime_extractor_version(self.config, root, topic_id, direction_id)
        cache_enabled = bool((self.config.settings.get("efficiency") or {}).get("fact_cache_enabled", True)) and _cache_eligible(raw)
        if cache_enabled:
            cached = self.db.fetchone(
                "SELECT * FROM fact_cache WHERE source_fingerprint=? AND extractor_version=?",
                (fingerprint, version),
            )
            if cached:
                cache_path = root / cached["json_path"]
                if cache_path.is_file():
                    url = raw.get("original_url") or raw.get("canonical_url") or raw.get("aihot_url")
                    document_id = stable_hash(run_id, effective_candidate["id"], url)
                    stub = self.run_dir / "documents" / f"{document_id}.evidence.md"
                    stub.parent.mkdir(parents=True, exist_ok=True)
                    stub.write_text(
                        "# Fact cache hit\n\nThe fact extraction result for this exact source and judging context is reused.\n",
                        encoding="utf-8",
                    )
                    self.db.execute(
                        "UPDATE fact_cache SET last_used_at=? WHERE cache_key=?",
                        (now_iso(), cached["cache_key"]),
                    )
                    return {
                        "document_id": document_id,
                        "candidate_id": effective_candidate["id"],
                        "url": url,
                        "media_type": "application/x-fact-cache",
                        "fetch_status": "FETCHED",
                        "text_path": str(stub),
                        "chunks": [str(stub)],
                        "char_count": int(cached.get("evidence_char_count") or 0),
                        "raw_char_count": int(cached.get("raw_char_count") or 0),
                        "evidence_char_count": int(cached.get("evidence_char_count") or 0),
                        "fact_cache_hit": True,
                        "fact_cache_key": cached["cache_key"],
                        "source_fingerprint": fingerprint,
                        "extractor_version": version,
                        "evidence_strategy": "front-evidence-v2",
                        "error": None,
                    }

        manifest = original_fetch(self, run_id, effective_candidate)
        raw_text_path = Path(manifest["text_path"])
        text = raw_text_path.read_text(encoding="utf-8")
        if not topic_id or not direction_id:
            return manifest
        try:
            topic = self.config.topic(topic_id)
            direction = self.config.direction(topic_id, direction_id)
        except Exception:
            return manifest
        policy = dict(self.config.settings.get("efficiency") or {})
        max_chars = max(4000, int(policy.get("evidence_pack_max_chars", 18000)))
        pack = build_evidence_pack(text, topic, direction, max_chars=max_chars)
        evidence_path = self.run_dir / "documents" / f"{manifest['document_id']}.evidence.md"
        evidence_path.write_text(pack, encoding="utf-8")
        enriched = {
            **manifest,
            "text_path": str(evidence_path),
            "chunks": [str(evidence_path)],
            "char_count": len(pack),
            "raw_char_count": len(text),
            "evidence_char_count": len(pack),
            "evidence_reduction_ratio": round(max(0.0, 1.0 - len(pack) / max(1, len(text))), 4),
            "evidence_strategy": "front-evidence-v2",
            "fact_cache_hit": False,
            "source_fingerprint": fingerprint,
            "extractor_version": version,
            "fact_cache_eligible": cache_enabled,
        }
        write_json(self.run_dir / "documents" / f"{manifest['document_id']}.json", enriched)
        return enriched

    def create(self, run_id: str, task_type: str, entity_id: str, input_data: dict[str, Any], **kwargs):
        row = original_create(self, run_id, task_type, entity_id, input_data, **kwargs)
        if task_type != "fact_extraction":
            return row
        document = input_data.get("document") or {}
        cache_key = document.get("fact_cache_key") if document.get("fact_cache_hit") else None
        if not cache_key:
            return row
        ensure_cost_schema(self.db)
        cache = self.db.fetchone("SELECT * FROM fact_cache WHERE cache_key=?", (cache_key,))
        if not cache:
            return row
        cache_path = self.root / cache["json_path"]
        if not cache_path.is_file():
            return row
        task_input = read_json(self.root / row["input_path"], {})
        binding = task_input.get(TASK_BINDING_KEY)
        cached_output = read_json(cache_path, {})
        if not binding or not cached_output:
            return row
        write_json(self.root / row["output_path"], {TASK_BINDING_KEY: binding, **cached_output})
        return row

    def apply_task(self, task: dict[str, Any]) -> None:
        original_apply(self, task)
        if task["task_type"] != "fact_extraction":
            return
        ensure_cost_schema(self.db)
        task_input = read_json(self.root / task["input_path"], {})
        document = task_input.get("document") or {}
        if document.get("fact_cache_hit") or not document.get("fact_cache_eligible"):
            return
        fingerprint = str(document.get("source_fingerprint") or "")
        version = str(document.get("extractor_version") or "")
        if not fingerprint or not version or document.get("fetch_status") != "FETCHED":
            return
        facts_row = self.db.fetchone("SELECT * FROM facts WHERE run_id=? AND candidate_id=?", (self.run_id, task["entity_id"]))
        if not facts_row:
            return
        facts = read_json(self.root / facts_row["json_path"], {})
        if not facts.get("primary_source_resolved"):
            return
        facts.pop("_provenance", None)
        source = task_input.get("source") or {}
        candidate = self.db.fetchone("SELECT raw_item_id FROM candidates WHERE id=?", (task["entity_id"],))
        raw = self.db.fetchone("SELECT * FROM raw_items WHERE id=?", (candidate["raw_item_id"],)) if candidate else None
        if not raw or not _cache_eligible(raw):
            return
        cache_key = stable_hash("fact-cache", fingerprint, version, length=32)
        cache_path = self.root / "workspace" / "cache" / "facts" / f"{cache_key}.json"
        write_json(cache_path, facts)
        now = now_iso()
        self.db.execute(
            """
            INSERT INTO fact_cache(
                cache_key,source_fingerprint,extractor_version,source_url,source_identity,
                external_id,source_content_hash,json_path,quality_score,event_hint,
                raw_char_count,evidence_char_count,created_at,last_used_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_fingerprint,extractor_version) DO UPDATE SET
                cache_key=excluded.cache_key,
                source_url=excluded.source_url,
                source_identity=excluded.source_identity,
                external_id=excluded.external_id,
                source_content_hash=excluded.source_content_hash,
                json_path=excluded.json_path,
                quality_score=excluded.quality_score,
                event_hint=excluded.event_hint,
                raw_char_count=excluded.raw_char_count,
                evidence_char_count=excluded.evidence_char_count,
                last_used_at=excluded.last_used_at
            """,
            (
                cache_key,
                fingerprint,
                version,
                source.get("url"),
                raw.get("identity_key"),
                raw.get("external_id"),
                raw.get("content_hash"),
                str(cache_path.relative_to(self.root)),
                facts.get("quality_score"),
                facts.get("event_hint"),
                int(document.get("raw_char_count") or 0),
                int(document.get("evidence_char_count") or 0),
                now,
                now,
            ),
        )

    FulltextService.fetch_candidate = fetch_candidate
    FulltextService._evidence_pack_installed = True
    TaskService.create = create
    TaskService._fact_cache_installed = True
    Pipeline._apply_task = apply_task
    Pipeline._fact_cache_installed = True
