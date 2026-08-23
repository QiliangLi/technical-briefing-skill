from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .business_time import briefing_date
from .config import ConfigBundle
from .collection import CollectionService
from .adapters.base import CollectedItem
from .db import Database
from .dedup import EventClusterer
from .fulltext import FulltextService
from .expanded import normalise_legacy_item, select_expanded_rows
from .freshness import freshness_limits
from .matching import RuleMatcher
from .scoring import Scorer
from .tasks import TaskService, synthesis_item_payload
from .utils import now_iso, parse_datetime, read_json, source_url_is_resolved, stable_hash, write_json
from .visuals import VisualAssetService

LOGGER = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, root: Path, config: ConfigBundle, db: Database, run_id: str):
        self.root = root
        self.config = config
        self.db = db
        self.run_id = run_id
        self.run_dir = root / "workspace" / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = TaskService(db, root, self.run_dir)
        self.scorer = Scorer(config)

    def _report_date(self) -> str:
        """The report date: fixed at run creation, interpreted in the
        configured timezone, reused by selection/issue/radar and resume.

        Anchoring on ``runs.created_at`` (persisted when the run was created)
        means a Shanghai-midnight run keeps its local date on every later
        stage instead of re-reading a UTC calendar day.
        """
        run = self.db.fetchone("SELECT created_at FROM runs WHERE id=?", (self.run_id,))
        anchor = parse_datetime(run.get("created_at")) if run and run.get("created_at") else None
        return briefing_date(self.config, anchor).isoformat()

    def prepare_agent_search(self, max_queries: int = 18) -> int:
        created = 0
        max_age_days = freshness_limits(self.config)["absolute"]
        # Search windows are reader/report-facing calendar dates: use the
        # configured timezone, not the UTC calendar day.
        search_end = briefing_date(self.config)
        search_start = search_end - timedelta(days=max_age_days)
        priority_map = {"highest": 100, "high": 80, "medium": 55, "low": 30}
        for topic, direction in self.config.iter_directions():
            if created >= max_queries:
                break
            queries = direction.get("queries") or []
            if not queries:
                continue
            query = queries[0]
            domains = []
            # Open technical sources first; the current Agent may broaden when needed.
            if topic["id"] == "agent_acceleration":
                domains = ["arxiv.org", "openreview.net", "github.com", "simonwillison.net", "latent.space"]
            elif topic["id"] == "optical_network":
                domains = ["ofcconference.org", "dl.acm.org", "arxiv.org", "research.google"]
            input_data = {
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "direction_id": direction["id"],
                "direction_name": direction["name"],
                "query": query,
                "preferred_domains": domains,
                "freshness_days": max_age_days,
                "date_from": search_start.isoformat(),
                "date_to": search_end.isoformat(),
                "max_results": 10,
            }
            self.tasks.create(
                self.run_id,
                "agent_web_search",
                f"{topic['id']}:{direction['id']}",
                input_data,
                prompt="agent-web-search.md",
                schema="web-search-results.schema.json",
                priority=priority_map.get(topic.get("aihot_priority", "low"), 30),
            )
            created += 1
        if created:
            self.db.update_run(self.run_id, stage="AWAITING_AGENT_SEARCH")
        return created

    def prepare_relevance(self) -> int:
        matcher = RuleMatcher(self.config, self.db)
        matcher.create_candidates(self.run_id)
        candidates = self.db.fetchall(
            """
            SELECT c.*, r.title, r.summary, r.original_url, r.aihot_url, r.published_at,
                   r.discovered_at, r.discovery_source, r.source_level, r.discovery_only,
                   r.payload_json
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.status='PENDING_RELEVANCE'
            ORDER BY c.rule_score DESC
            """,
            (self.run_id,),
        )
        count = 0
        for candidate in candidates:
            topic = self.config.topic(candidate["topic_id"])
            direction = self.config.direction(candidate["topic_id"], candidate["direction_id"])
            context_path = self.config.context_path(__import__("briefing_skill.paths", fromlist=["Paths"]).Paths(self.root), candidate["topic_id"])
            input_data = {
                "candidate_id": candidate["id"],
                "title": candidate["title"],
                "summary": candidate["summary"],
                "source": {
                    "discovery_source": candidate["discovery_source"],
                    "source_level": candidate["source_level"],
                    "discovery_only": bool(candidate["discovery_only"]),
                    "original_url": candidate["original_url"],
                    "aihot_url": candidate["aihot_url"],
                    "published_at": candidate["published_at"],
                    "discovered_at": candidate["discovered_at"],
                },
                "topic": topic,
                "direction": direction,
                "rule_score": candidate["rule_score"],
                "project_context_path": str(context_path.relative_to(self.root)),
                "constraints": {
                    "do_not_read_fulltext_yet": True,
                    "aihot_is_discovery_only": candidate["discovery_source"] == "AI HOT",
                },
            }
            self.tasks.create(
                self.run_id,
                "relevance_review",
                candidate["id"],
                input_data,
                prompt="relevance-review.md",
                schema="relevance.schema.json",
                priority=float(candidate["rule_score"]),
            )
            self.db.execute("UPDATE candidates SET status='RELEVANCE_TASKED' WHERE id=?", (candidate["id"],))
            count += 1
        if count:
            self.db.update_run(self.run_id, stage="AWAITING_RELEVANCE")
        return count

    def advance(self) -> dict[str, Any]:
        completed, invalid = self.tasks.sync(self.run_id)
        applied = 0
        for task in self.db.fetchall(
            "SELECT * FROM tasks WHERE run_id=? AND status='COMPLETED' ORDER BY created_at",
            (self.run_id,),
        ):
            self._apply_task(task)
            self.db.execute("UPDATE tasks SET status='APPLIED', updated_at=? WHERE id=?", (now_iso(), task["id"]))
            applied += 1

        # Open-web discovery is a separate phase.  Do not start relevance or
        # full-text work until every Agent search result has been applied, or the
        # late results would miss the candidate pipeline.
        search_unfinished = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='agent_web_search' "
            "AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        if not search_unfinished:
            self.prepare_relevance()
            self._maybe_prepare_facts()
            self._maybe_prepare_items()
            self._maybe_prepare_checks()
            self._maybe_prepare_issue()
            self._maybe_prepare_illustrations()
            self._maybe_finalize_issue()

        pending = self.tasks.list(self.run_id, "PENDING")
        invalid_rows = self.tasks.list(self.run_id, "INVALID")
        run = self.db.fetchone("SELECT * FROM runs WHERE id=?", (self.run_id,))
        return {
            "synced": completed,
            "applied": applied,
            "invalid": invalid + len(invalid_rows),
            "pending": len(pending),
            "stage": run["stage"] if run else None,
            "next_task": self.tasks.instructions(pending[0]) if pending else None,
        }

    def _apply_task(self, task: dict[str, Any]) -> None:
        output = self.tasks.read_result(task)
        task_type = task["task_type"]
        if task_type == "agent_web_search":
            metadata = read_json(self.root / task["input_path"])
            collected = []
            for result in output.get("results", []):
                collected.append(CollectedItem(
                    source_id="agent_web_search",
                    discovery_source="Agent Web Search",
                    source_level=result.get("source_level", "B"),
                    discovery_only=not bool(result.get("primary")),
                    title=result.get("title", "Untitled"),
                    summary=result.get("summary", ""),
                    original_url=result.get("url", ""),
                    published_at=result.get("published_at"),
                    topic_hint=metadata.get("topic_id", ""),
                    direction_hint=metadata.get("direction_id", ""),
                    priority=18.0 if result.get("primary") else 10.0,
                    payload={"publisher": result.get("publisher"), "agent_search_query": metadata.get("query")},
                ))
            service = CollectionService(self.config, self.db, self.run_dir)
            try:
                service.persist(self.run_id, collected)
            finally:
                service.close()
        elif task_type == "relevance_review":
            self.db.execute(
                """
                UPDATE candidates SET relevant=?, relevance_score=?, relevance_reason=?,
                    fulltext_required=?, status=? WHERE id=?
                """,
                (
                    int(bool(output["relevant"])),
                    output["score"],
                    output.get("reason"),
                    int(bool(output.get("fulltext_required", True))),
                    "RELEVANT" if output["relevant"] else "REJECTED",
                    task["entity_id"],
                ),
            )
        elif task_type == "fact_extraction":
            candidate_id = task["entity_id"]
            facts_path = self.run_dir / "facts" / f"{candidate_id}.json"
            task_input = read_json(self.root / task["input_path"], {})
            source = task_input.get("source") or {}
            document = task_input.get("document") or {}
            write_json(
                facts_path,
                {
                    **output,
                    "_provenance": {
                        "task_id": task["id"],
                        "candidate_id": candidate_id,
                        "source_title": source.get("title"),
                        "source_url": source.get("url"),
                        "document_id": document.get("document_id"),
                    },
                },
            )
            self.db.execute(
                """
                INSERT OR REPLACE INTO facts(id, run_id, candidate_id, json_path, quality_score, event_hint, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_hash(self.run_id, "facts", candidate_id),
                    self.run_id,
                    candidate_id,
                    str(facts_path.relative_to(self.root)),
                    output.get("quality_score", 70),
                    output.get("event_hint") or output.get("title"),
                    now_iso(),
                ),
            )
            self.db.execute("UPDATE candidates SET status='FACTS_READY' WHERE id=?", (candidate_id,))
        elif task_type == "item_writing":
            event_id = task["entity_id"]
            item_path = self.run_dir / "items" / f"{event_id}.json"
            task_input = read_json(self.root / task["input_path"], {})
            write_json(
                item_path,
                {
                    **output,
                    "_provenance": {
                        "task_id": task["id"],
                        "event_id": event_id,
                        "source_urls": [source.get("url") for source in task_input.get("sources", [])],
                    },
                },
            )
            self.db.execute(
                """
                INSERT OR REPLACE INTO brief_items(id, run_id, event_id, json_path, score, fact_check_status, approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_hash(self.run_id, "item", event_id),
                    self.run_id,
                    event_id,
                    str(item_path.relative_to(self.root)),
                    output.get("score", 0),
                    "PENDING",
                    0,
                    now_iso(),
                ),
            )
        elif task_type == "fact_check":
            item = self.db.fetchone("SELECT * FROM brief_items WHERE id=?", (task["entity_id"],))
            if not item:
                raise KeyError(task["entity_id"])
            if output.get("corrected_item"):
                current_item = read_json(self.root / item["json_path"], {})
                corrected = dict(output["corrected_item"])
                if current_item.get("_provenance"):
                    corrected["_provenance"] = current_item["_provenance"]
                write_json(self.root / item["json_path"], corrected)
            self.db.execute(
                "UPDATE brief_items SET fact_check_status=? WHERE id=?",
                ("PASS" if output["pass"] else "FAIL", item["id"]),
            )
        elif task_type == "issue_synthesis":
            issue = self.db.fetchone("SELECT * FROM issues WHERE id=?", (task["entity_id"],))
            path = self.run_dir / "issue" / "synthesis.json"
            write_json(path, output)
            self.db.execute("UPDATE issues SET synthesis_path=?, updated_at=? WHERE id=?", (str(path.relative_to(self.root)), now_iso(), issue["id"]))
        elif task_type == "visual_routing":
            brief_item_id = task["entity_id"]
            item_row = self.db.fetchone("SELECT * FROM issue_items WHERE brief_item_id=?", (brief_item_id,))
            path = self.run_dir / "visuals" / f"{brief_item_id}.plan.json"
            write_json(path, output)
            if item_row:
                self.db.execute("UPDATE issue_items SET visual_plan_path=? WHERE brief_item_id=?", (str(path.relative_to(self.root)), brief_item_id))
        elif task_type == "illustration_brief":
            path = self.run_dir / "visuals" / "illustrations" / f"{task['entity_id']}.json"
            write_json(path, output)

    def _maybe_prepare_facts(self) -> None:
        pending_relevance = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='relevance_review' AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        if pending_relevance:
            return
        rows = self.db.fetchall(
            """
            SELECT c.*, r.title, r.summary, r.original_url, r.aihot_url, r.published_at,
                   r.discovery_source, r.source_level, r.discovery_only, r.payload_json
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.status='RELEVANT'
            ORDER BY c.relevance_score DESC
            """,
            (self.run_id,),
        )
        if not rows:
            return
        fulltext = FulltextService(self.config, self.db, self.run_dir)
        try:
            for candidate in rows:
                if self.db.fetchone("SELECT 1 FROM tasks WHERE run_id=? AND task_type='fact_extraction' AND entity_id=?", (self.run_id, candidate["id"])):
                    continue
                manifest = fulltext.fetch_candidate(self.run_id, candidate)
                topic = self.config.topic(candidate["topic_id"])
                direction = self.config.direction(candidate["topic_id"], candidate["direction_id"])
                input_data = {
                    "candidate_id": candidate["id"],
                    "source": {
                        "title": candidate["title"],
                        "summary": candidate["summary"],
                        "url": candidate["original_url"] or candidate["aihot_url"],
                        "published_at": candidate["published_at"],
                        "discovery_source": candidate["discovery_source"],
                        "source_level": candidate["source_level"],
                        "discovery_only": bool(candidate["discovery_only"]),
                    },
                    "topic": {"id": topic["id"], "name": topic["name"], "current_questions": topic.get("current_questions", []), "valuable_evidence": topic.get("valuable_evidence", [])},
                    "direction": direction,
                    "project_context_path": str(self.config.context_path(__import__("briefing_skill.paths", fromlist=["Paths"]).Paths(self.root), topic["id"]).relative_to(self.root)),
                    "document": {
                        **manifest,
                        "text_path": str(Path(manifest["text_path"]).relative_to(self.root)),
                        "chunks": [str(Path(p).relative_to(self.root)) for p in manifest["chunks"]],
                    },
                }
                self.tasks.create(
                    self.run_id,
                    "fact_extraction",
                    candidate["id"],
                    input_data,
                    prompt="fact-extraction.md",
                    schema="facts.schema.json",
                    priority=float(candidate.get("relevance_score") or 0),
                )
                self.db.execute("UPDATE candidates SET status='FACT_TASKED' WHERE id=?", (candidate["id"],))
        finally:
            fulltext.close()
        self.db.update_run(self.run_id, stage="AWAITING_FACTS")

    def _maybe_prepare_items(self) -> None:
        pending = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_extraction' AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        fact_count = self.db.fetchone("SELECT COUNT(*) AS n FROM facts WHERE run_id=?", (self.run_id,))["n"]
        if pending or not fact_count:
            return
        if self.db.fetchone("SELECT 1 FROM tasks WHERE run_id=? AND task_type='item_writing' LIMIT 1", (self.run_id,)):
            return
        clusters = EventClusterer(self.db).persist(self.run_id, EventClusterer(self.db).cluster_run(self.run_id))
        for cluster in clusters:
            members = cluster["members"]
            facts = [read_json(self.root / member["json_path"]) for member in members]
            candidates = [self.db.fetchone("SELECT * FROM candidates WHERE id=?", (member["candidate_id"],)) for member in members]
            raws = [self.db.fetchone("SELECT r.* FROM raw_items r JOIN candidates c ON c.raw_item_id=r.id WHERE c.id=?", (member["candidate_id"],)) for member in members]
            # Item writing is only safe once at least one member is backed by a
            # concrete A-level source whose fact extraction resolved the primary
            # source.  B/C and discovery-only events remain available for later
            # observation/radar handling, but must not be promoted into a core
            # item task that can never pass semantic validation.
            has_resolved_primary = any(
                raw
                and raw.get("source_level") == "A"
                and source_url_is_resolved(raw.get("original_url") or raw.get("aihot_url"))
                and bool(fact.get("primary_source_resolved"))
                for fact, raw in zip(facts, raws)
            )
            if not has_resolved_primary:
                LOGGER.info(
                    "Skipping item_writing for event %s without a resolved primary A-level source",
                    cluster["event_id"],
                )
                continue
            score = self.scorer.event_score(facts, candidates, raws)
            self.db.execute("UPDATE events SET score=? WHERE id=?", (score, cluster["event_id"]))
            input_data = {
                "event_id": cluster["event_id"],
                "topic": self.config.topic(cluster["topic_id"]),
                "direction": self.config.direction(cluster["topic_id"], cluster["direction_id"]),
                "score": score,
                "facts": facts,
                "sources": [
                    {
                        "title": raw["title"],
                        "url": raw["original_url"] or raw["aihot_url"],
                        "source_level": raw["source_level"],
                        "discovery_source": raw["discovery_source"],
                        "published_at": raw["published_at"],
                    }
                    for raw in raws
                ],
                "length": {
                    "min_chars": self.config.settings.get("brief_item_min_chars", 300),
                    "max_chars": self.config.settings.get("brief_item_max_chars", 450),
                },
            }
            self.tasks.create(
                self.run_id,
                "item_writing",
                cluster["event_id"],
                input_data,
                prompt="item-writing.md",
                schema="brief-item.schema.json",
                priority=score,
                metadata={
                    "required_skills": ["human-writing"],
                    "skill_mode": "single_item_chinese_technical_polish",
                },
            )
        self.db.update_run(self.run_id, stage="AWAITING_ITEMS")

    def _maybe_prepare_checks(self) -> None:
        pending = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='item_writing' AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        item_count = self.db.fetchone("SELECT COUNT(*) AS n FROM brief_items WHERE run_id=?", (self.run_id,))["n"]
        if pending or not item_count:
            return
        for item in self.db.fetchall("SELECT * FROM brief_items WHERE run_id=? AND fact_check_status='PENDING'", (self.run_id,)):
            if self.db.fetchone("SELECT 1 FROM tasks WHERE run_id=? AND task_type='fact_check' AND entity_id=?", (self.run_id, item["id"])):
                continue
            event_members = self.db.fetchall(
                "SELECT f.json_path FROM event_members em JOIN facts f ON f.candidate_id=em.candidate_id AND f.run_id=em.run_id WHERE em.event_id=? AND em.run_id=?",
                (item["event_id"], self.run_id),
            )
            input_data = {
                "brief_item": read_json(self.root / item["json_path"]),
                "facts": [read_json(self.root / row["json_path"]) for row in event_members],
                "length": {
                    "min_chars": self.config.settings.get("brief_item_min_chars", 300),
                    "max_chars": self.config.settings.get("brief_item_max_chars", 450),
                },
                "rules": [
                    "All numbers must be supported by facts.",
                    "Baseline and experimental conditions must not be omitted when material.",
                    "Project inference must be labelled as project judgement, not source fact.",
                    "AI HOT summaries cannot be the sole evidence.",
                    "Every field must be a complete sentence without ellipsis or dangling punctuation.",
                ],
            }
            self.tasks.create(
                self.run_id,
                "fact_check",
                item["id"],
                input_data,
                prompt="fact-check.md",
                schema="fact-check.schema.json",
                priority=float(item["score"]) + 5,
            )
        self.db.update_run(self.run_id, stage="AWAITING_FACT_CHECK")

    def _maybe_prepare_issue(self) -> None:
        pending = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='fact_check' AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        if pending:
            return
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if issue:
            return
        mode = self.config.settings.get("issue_mode", "compact")
        rows = self.db.fetchall(
            """
            SELECT bi.*, e.topic_id, e.direction_id, e.canonical_title, e.event_key,
                   COALESCE(
                     e.last_pushed_at,
                     (SELECT MAX(e2.last_pushed_at) FROM events e2
                      WHERE e.event_key IS NOT NULL AND e2.event_key=e.event_key)
                   ) AS last_pushed_at,
                   (SELECT MAX(r.published_at)
                    FROM event_members em
                    JOIN candidates c ON c.id=em.candidate_id
                    JOIN raw_items r ON r.id=c.raw_item_id
                    WHERE em.event_id=e.id) AS source_published_at
            FROM brief_items bi JOIN events e ON e.id=bi.event_id
            WHERE bi.run_id=? AND bi.fact_check_status='PASS'
            ORDER BY bi.score DESC, bi.id
            """,
            (self.run_id,),
        )
        report_date = self._report_date()
        if mode == "expanded_v2":
            from .publication_history import annotate_rows_with_publication_roles

            rows = annotate_rows_with_publication_roles(self.root, self.db, rows)
            selected, _, _, _ = select_expanded_rows(
                self.root,
                self.config,
                rows,
                reference_date=report_date,
            )
        else:
            threshold = float(self.config.scoring.get("thresholds", {}).get("issue_minimum", 70))
            max_items = int(self.config.scoring.get("thresholds", {}).get("max_issue_items", 6))
            max_per_topic = int(self.config.scoring.get("thresholds", {}).get("max_items_per_topic", 2))
            selected = []
            topic_counts: dict[str, int] = {}
            for row in rows:
                if float(row["score"]) < threshold:
                    continue
                if row.get("last_pushed_at"):
                    item = read_json(self.root / row["json_path"])
                    if not item.get("incremental_update"):
                        continue
                if topic_counts.get(row["topic_id"], 0) >= max_per_topic:
                    continue
                selected.append({**row, "item_role": "core"})
                topic_counts[row["topic_id"]] = topic_counts.get(row["topic_id"], 0) + 1
                if len(selected) >= max_items:
                    break
        if not selected or (mode == "expanded_v2" and not any(row.get("item_role") == "core" for row in selected)):
            return
        issue_id = stable_hash("issue", self.run_id)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO issues(id, run_id, status, date_from, date_to, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (issue_id, self.run_id, "DRAFT", report_date, report_date, now_iso(), now_iso()),
            )
            for position, row in enumerate(selected, 1):
                conn.execute(
                    "INSERT INTO issue_items(issue_id, brief_item_id, position, item_role) VALUES (?, ?, ?, ?)",
                    (issue_id, row["id"], position, row.get("item_role", "core")),
                )
        self.db.update_run(self.run_id, stage="AWAITING_ISSUE_SYNTHESIS", issue_id=issue_id)
        items = [read_json(self.root / row["json_path"]) for row in selected]
        synthesis_items = [
            synthesis_item_payload(row, item)
            for row, item in zip(selected, items)
            if row.get("item_role", "core") == "core"
        ]
        self.tasks.create(
            self.run_id,
            "issue_synthesis",
            issue_id,
            {"issue_id": issue_id, "items": synthesis_items, "max_judgements": 3, "audience": "公司内部领导和技术同事"},
            prompt="issue-synthesis.md",
            schema="issue-synthesis.schema.json",
            priority=100,
        )
        if mode == "expanded_v2":
            return
        for row, item in zip(selected, items):
            self.tasks.create(
                self.run_id,
                "visual_routing",
                row["id"],
                {
                    "brief_item_id": row["id"],
                    "item": item,
                    "visual_modes": ["source_figure", "official_image", "screenshot", "chart_redraw", "material_mechanism", "persona_metaphor", "text_only"],
                    "constraints": {
                        "evidence_first": True,
                        "no_decorative_ai_image": True,
                        "exact_numbers_require_programmatic_chart": True,
                        "persona_overlay": "assets/persona/ian-qiliang/overlay.md",
                        "persona_reference_manifest": "assets/persona/ian-qiliang/reference-manifest.yaml",
                        "persona_role": "技术侦察员",
                    },
                },
                prompt="visual-routing.md",
                schema="visual-plan.schema.json",
                priority=float(row["score"]),
            )

    def _maybe_prepare_illustrations(self) -> None:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if not issue:
            return
        pending_routes = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type='visual_routing' AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        if pending_routes:
            return
        visual_service = VisualAssetService(
            self.root,
            self.run_dir,
            timeout=float(self.config.settings.get("http_timeout_seconds", 25)),
        )
        try:
            rows = self.db.fetchall("SELECT * FROM issue_items WHERE issue_id=?", (issue["id"],))
            for row in rows:
                if not row.get("visual_plan_path"):
                    continue
                plan_path = self.root / row["visual_plan_path"]
                plan = visual_service.materialize(row["brief_item_id"], plan_path)
                if plan.get("visual_mode") not in {"material_mechanism", "persona_metaphor"}:
                    continue
                if self.db.fetchone(
                    "SELECT 1 FROM tasks WHERE run_id=? AND task_type='illustration_brief' AND entity_id=?",
                    (self.run_id, row["brief_item_id"]),
                ):
                    continue
                item = self.db.fetchone("SELECT * FROM brief_items WHERE id=?", (row["brief_item_id"],))
                self.tasks.create(
                    self.run_id,
                    "illustration_brief",
                    row["brief_item_id"],
                    {
                        "brief_item": read_json(self.root / item["json_path"]),
                        "visual_plan": plan,
                        "illustration_style_skill": "ian-xiaohei-illustrations",
                        "persona_overlay_path": "assets/persona/ian-qiliang/overlay.md",
                        "persona_reference_manifest_path": "assets/persona/ian-qiliang/reference-manifest.yaml",
                        "output_directory": str((self.run_dir / "visuals" / "generated").relative_to(self.root)),
                        "fallback_allowed": True,
                    },
                    prompt="illustration-brief.md",
                    schema="illustration-brief.schema.json",
                    priority=float(item["score"]),
                )
        finally:
            visual_service.close()

    def _maybe_finalize_issue(self) -> None:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if not issue or not issue.get("synthesis_path"):
            return
        unfinished = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type IN ('issue_synthesis','visual_routing','illustration_brief') AND status IN ('PENDING','INVALID','COMPLETED')",
            (self.run_id,),
        )["n"]
        if unfinished:
            return
        item_rows = self.db.fetchall(
            """
            SELECT ii.position, ii.visual_plan_path, ii.item_role, bi.*, e.topic_id, e.direction_id
            FROM issue_items ii JOIN brief_items bi ON bi.id=ii.brief_item_id
            JOIN events e ON e.id=bi.event_id
            WHERE ii.issue_id=? ORDER BY ii.position
            """,
            (issue["id"],),
        )
        issue_data = {
            "id": issue["id"],
            "run_id": self.run_id,
            "date_from": issue["date_from"],
            "date_to": issue["date_to"],
            "synthesis": read_json(self.root / issue["synthesis_path"]),
            "layout_mode": self.config.settings.get("issue_mode", "compact"),
            "core_items": [],
            "observations": [],
            "items": [],
        }
        for row in item_rows:
            item = read_json(self.root / row["json_path"])
            if self.config.settings.get("issue_mode", "compact") == "expanded_v2":
                item = normalise_legacy_item(item, self.config)
            plan = read_json(self.root / row["visual_plan_path"], {}) if row.get("visual_plan_path") else {"visual_mode": "text_only"}
            illustration = read_json(self.run_dir / "visuals" / "illustrations" / f"{row['id']}.json", {})
            item_role = row.get("item_role") or "core"
            rebuilt_item = {
                **item,
                "brief_item_id": row["id"],
                "topic_id": row["topic_id"],
                "direction_id": row["direction_id"],
                "item_role": item_role,
                "fact_check_status": row.get("fact_check_status"),
                "anchor_id": f"item-{row['id']}",
                "visual_plan": plan,
                "illustration": illustration,
            }
            issue_data["items"].append(rebuilt_item)
            issue_data["core_items" if item_role == "core" else "observations"].append(rebuilt_item)
        path = self.run_dir / "issue" / "issue.json"
        write_json(path, issue_data)
        self.db.execute("UPDATE issues SET issue_json_path=?, status='READY_FOR_RENDER', updated_at=? WHERE id=?", (str(path.relative_to(self.root)), now_iso(), issue["id"]))
        self.db.update_run(self.run_id, stage="READY_FOR_RENDER")
