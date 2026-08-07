from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .cost_schema import ensure_cost_schema
from .deep_efficiency import _cache_eligible, _section_score, _sections, _safe_excerpt
from .utils import now_iso, read_json, stable_hash, write_json


def _gap_terms(gaps: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    literal: list[str] = []
    expanded: list[str] = []
    seen: set[str] = set()
    for gap in gaps:
        for value in gap.get("terms") or []:
            term = str(value or "").strip().lower()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            literal.append(term)
            expanded.append(term)
        question = str(gap.get("question") or "").lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+./-]{2,}|[\u4e00-\u9fff]{2,8}", question):
            if token not in seen:
                seen.add(token)
                expanded.append(token)
    return literal[:24], expanded[:48]


def _existing_locators(evidence_text: str) -> set[str]:
    return {
        match.group(1).strip().lower()
        for match in re.finditer(r"(?m)^## Evidence locator:\s*(.+?)\s*$", evidence_text)
    }


def _unread_suffix(raw_text: str, existing_evidence: str) -> str:
    """Return only source text that follows the initial front-evidence prefix.

    Old runs may contain the previous section-selected Evidence Pack, so fail back to
    the full raw source for those runs and rely on locator exclusion rather than
    incorrectly assuming prefix alignment.
    """

    raw = raw_text.strip()
    evidence = existing_evidence.strip()
    if evidence and raw.startswith(evidence):
        return raw[len(evidence) :].lstrip()
    return raw_text


def build_supplement_pack(
    raw_text: str,
    existing_evidence: str,
    gaps: list[dict[str, Any]],
    *,
    max_chars: int = 9000,
) -> str:
    """Retrieve only unread source sections that directly match explicit gaps."""

    literal_terms, expanded_terms = _gap_terms(gaps)
    if not literal_terms:
        return ""

    remaining = _unread_suffix(raw_text, existing_evidence)
    # A short unread tail can still contain the exact missing baseline or hardware
    # condition. Reject only near-empty tails; never require hundreds of filler chars
    # before allowing a deterministic gap match.
    if len(remaining.strip()) < 40:
        return ""
    existing = _existing_locators(existing_evidence)
    candidates: list[tuple[float, int, str, str]] = []
    for index, title, body in _sections(remaining):
        if title.strip().lower() in existing:
            continue
        lower = body.lower()
        literal_hits = sum(1 for term in literal_terms if term in lower)
        if not literal_hits:
            continue
        score = _section_score(index, title, body, expanded_terms) + literal_hits * 8.0
        candidates.append((score, index, title, body))
    if not candidates:
        return ""

    header = (
        "# Targeted Evidence Supplement\n\n"
        "This supplement contains only previously unread source sections that match "
        "explicit material evidence-gap terms. It is not the full source.\n\n"
    )
    used = len(header)
    section_cap = max(900, max_chars // 2)
    selected: list[tuple[int, str, str]] = []
    for _, index, title, body in sorted(candidates, key=lambda row: (-row[0], row[1])):
        locator = f"## Supplemental locator: {title}\n\n"
        allowance = max_chars - used - len(locator) - 2
        if allowance <= 80:
            continue
        excerpt = _safe_excerpt(body, min(section_cap, allowance))
        if not excerpt:
            continue
        selected.append((index, title, excerpt))
        used += len(locator) + len(excerpt) + 2
    if not selected:
        return ""

    selected.sort(key=lambda row: row[0])
    blocks = [header.rstrip()]
    for _, title, excerpt in selected:
        blocks.append(f"## Supplemental locator: {title}\n\n{excerpt.strip()}")
    return "\n\n".join(blocks).strip()


def _materialize_facts(
    pipeline,
    candidate_id: str,
    output: dict[str, Any],
    *,
    task_id: str,
    source: dict[str, Any],
    document: dict[str, Any],
    status: str,
    repair_of_task_id: str | None = None,
) -> None:
    facts_path = pipeline.run_dir / "facts" / f"{candidate_id}.json"
    provenance = {
        "task_id": task_id,
        "candidate_id": candidate_id,
        "source_title": source.get("title"),
        "source_url": source.get("url"),
        "document_id": document.get("document_id"),
    }
    if repair_of_task_id:
        provenance["repair_of_task_id"] = repair_of_task_id
    write_json(facts_path, {**output, "_provenance": provenance})
    pipeline.db.execute(
        """
        INSERT OR REPLACE INTO facts(
            id,run_id,candidate_id,json_path,quality_score,event_hint,created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            stable_hash(pipeline.run_id, "facts", candidate_id),
            pipeline.run_id,
            candidate_id,
            str(facts_path.relative_to(pipeline.root)),
            output.get("quality_score", 70),
            output.get("event_hint") or output.get("title"),
            now_iso(),
        ),
    )
    pipeline.db.execute("UPDATE candidates SET status=? WHERE id=?", (status, candidate_id))


def _cache_repaired_facts(pipeline, task_input: dict[str, Any], output: dict[str, Any]) -> None:
    if output.get("evidence_gaps"):
        return
    document = task_input.get("document") or {}
    if not document.get("fact_cache_eligible") or not output.get("primary_source_resolved"):
        return
    fingerprint = str(document.get("source_fingerprint") or "")
    version = str(document.get("extractor_version") or "")
    if not fingerprint or not version:
        return

    candidate_id = str(task_input.get("candidate_id") or "")
    candidate = pipeline.db.fetchone("SELECT raw_item_id FROM candidates WHERE id=?", (candidate_id,))
    raw = pipeline.db.fetchone("SELECT * FROM raw_items WHERE id=?", (candidate["raw_item_id"],)) if candidate else None
    if not raw or not _cache_eligible(raw):
        return

    ensure_cost_schema(pipeline.db)
    pure = dict(output)
    pure.pop("_provenance", None)
    cache_key = stable_hash("fact-cache", fingerprint, version, length=32)
    cache_path = pipeline.root / "workspace" / "cache" / "facts" / f"{cache_key}.json"
    write_json(cache_path, pure)
    now = now_iso()
    source = task_input.get("source") or {}
    pipeline.db.execute(
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
            str(cache_path.relative_to(pipeline.root)),
            output.get("quality_score"),
            output.get("event_hint"),
            int(document.get("source_raw_char_count") or 0),
            int(document.get("source_evidence_char_count") or 0)
            + int(document.get("evidence_char_count") or 0),
            now,
            now,
        ),
    )


def install_evidence_repair() -> None:
    """Allow one small, explicit supplemental read instead of reopening full text."""

    from . import deep_efficiency, demo as demo_module
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_evidence_repair_installed", False):
        return

    original_runtime_version = deep_efficiency._runtime_extractor_version

    def runtime_extractor_version(
        config,
        root: Path,
        topic_id: str | None = None,
        direction_id: str | None = None,
    ) -> str:
        base = original_runtime_version(config, root, topic_id, direction_id)
        prompt = root / "prompts" / "fact-evidence-repair.md"
        if not prompt.is_file():
            return base
        return f"{base}:repair-{stable_hash(prompt.read_text(encoding='utf-8'), length=10)}"

    deep_efficiency._runtime_extractor_version = runtime_extractor_version

    original_apply = Pipeline._apply_task
    original_prepare_items = Pipeline._maybe_prepare_items
    original_semantic_errors = TaskService._semantic_errors
    original_demo_output = demo_module._demo_output

    def apply_task(self, task: dict[str, Any]) -> None:
        if task["task_type"] == "fact_extraction":
            output = self.tasks.read_result(task)
            gaps = list(output.get("evidence_gaps") or [])
            if not gaps:
                return original_apply(self, task)

            task_input = read_json(self.root / task["input_path"], {})
            source = task_input.get("source") or {}
            document = task_input.get("document") or {}
            candidate_id = str(task["entity_id"])
            _materialize_facts(
                self,
                candidate_id,
                output,
                task_id=task["id"],
                source=source,
                document=document,
                status="FACTS_PARTIAL",
            )

            policy = dict(self.config.settings.get("efficiency") or {})
            if not bool(policy.get("evidence_repair_enabled", True)) or document.get("fact_cache_hit"):
                self.db.execute("UPDATE candidates SET status='FACTS_READY' WHERE id=?", (candidate_id,))
                return

            document_id = str(document.get("document_id") or "")
            raw_path = self.run_dir / "documents" / f"{document_id}.md"
            evidence_path = self.root / str(document.get("text_path") or "")
            if not raw_path.is_file() or not evidence_path.is_file():
                self.db.execute("UPDATE candidates SET status='FACTS_READY' WHERE id=?", (candidate_id,))
                return

            raw_text = raw_path.read_text(encoding="utf-8")
            evidence_text = evidence_path.read_text(encoding="utf-8")
            max_chars = max(2000, int(policy.get("evidence_repair_max_chars", 9000)))
            supplement = build_supplement_pack(
                raw_text,
                evidence_text,
                gaps,
                max_chars=max_chars,
            )
            if not supplement:
                self.db.execute("UPDATE candidates SET status='FACTS_READY' WHERE id=?", (candidate_id,))
                return

            supplement_path = self.run_dir / "documents" / f"{document_id}.supplement.md"
            supplement_path.write_text(supplement, encoding="utf-8")
            self.tasks.create(
                self.run_id,
                "fact_evidence_repair",
                candidate_id,
                {
                    "candidate_id": candidate_id,
                    "source": source,
                    "topic": task_input.get("topic") or {},
                    "direction": task_input.get("direction") or {},
                    "project_context_path": task_input.get("project_context_path"),
                    "previous_facts": output,
                    "previous_task_id": task["id"],
                    "evidence_gaps": gaps,
                    "document": {
                        "document_id": document_id,
                        "supplement_path": str(supplement_path.relative_to(self.root)),
                        "text_path": str(supplement_path.relative_to(self.root)),
                        "chunks": [str(supplement_path.relative_to(self.root))],
                        "fetch_status": "FETCHED",
                        "evidence_char_count": len(supplement),
                        "source_raw_char_count": int(document.get("raw_char_count") or 0),
                        "source_evidence_char_count": int(document.get("evidence_char_count") or 0),
                        "source_fingerprint": document.get("source_fingerprint"),
                        "extractor_version": document.get("extractor_version"),
                        "fact_cache_eligible": bool(document.get("fact_cache_eligible")),
                    },
                    "constraints": {
                        "single_supplement_round": True,
                        "do_not_open_original_evidence_or_raw_fulltext": True,
                    },
                },
                prompt="fact-evidence-repair.md",
                schema="facts.schema.json",
                priority=float(task.get("priority") or 0) + 1,
            )
            self.db.execute("UPDATE candidates SET status='FACT_REPAIR_TASKED' WHERE id=?", (candidate_id,))
            self.db.update_run(self.run_id, stage="AWAITING_FACT_REPAIR")
            return

        if task["task_type"] == "fact_evidence_repair":
            output = self.tasks.read_result(task)
            task_input = read_json(self.root / task["input_path"], {})
            candidate_id = str(task_input.get("candidate_id") or task["entity_id"])
            source = task_input.get("source") or {}
            document = task_input.get("document") or {}
            _materialize_facts(
                self,
                candidate_id,
                output,
                task_id=task["id"],
                source=source,
                document=document,
                status="FACTS_READY",
                repair_of_task_id=str(task_input.get("previous_task_id") or "") or None,
            )
            _cache_repaired_facts(self, task_input, output)
            return

        return original_apply(self, task)

    def maybe_prepare_items(self) -> None:
        pending = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type='fact_evidence_repair'
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if pending:
            return
        return original_prepare_items(self)

    def semantic_errors(
        self,
        task: dict[str, Any],
        input_data: dict[str, Any],
        data: dict[str, Any],
    ) -> list[str]:
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task["task_type"] != "fact_evidence_repair":
            return errors

        pseudo_task = {**task, "task_type": "fact_extraction", "entity_id": input_data.get("candidate_id")}
        pseudo_input = {
            "candidate_id": input_data.get("candidate_id"),
            "source": input_data.get("source") or {},
            "document": {**(input_data.get("document") or {}), "fetch_status": "FETCHED"},
        }
        errors.extend(original_semantic_errors(self, pseudo_task, pseudo_input, data))

        requested = {
            " ".join(str(gap.get("question") or "").lower().split())
            for gap in input_data.get("evidence_gaps") or []
        }
        for gap in data.get("evidence_gaps") or []:
            question = " ".join(str(gap.get("question") or "").lower().split())
            if question not in requested:
                errors.append("fact_evidence_repair may retain only originally requested evidence gaps")
                break
        return errors

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == "fact_evidence_repair":
            result = dict(data.get("previous_facts") or {})
            result["evidence_gaps"] = []
            return result
        return original_demo_output(task_type, data)

    Pipeline._apply_task = apply_task
    Pipeline._maybe_prepare_items = maybe_prepare_items
    Pipeline._evidence_repair_installed = True
    TaskService._semantic_errors = semantic_errors
    TaskService._evidence_repair_installed = True
    demo_module._demo_output = demo_output
