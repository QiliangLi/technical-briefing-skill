from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

DEFAULT_DEEP_TOPICS = (
    "tpn", "memory_dsa", "dpu_inline", "agent_acceleration",
    "cross_region", "optical_network",
)
DEFAULT_RADAR_TOPICS = ("ai_infra_horizontal",)


@dataclass(frozen=True)
class RelevancePlan:
    accepted: tuple[dict[str, Any], ...]
    rejected: tuple[dict[str, Any], ...]
    radar: tuple[dict[str, Any], ...]
    batches: tuple[tuple[dict[str, Any], ...], ...]

    @property
    def agent_task_count(self) -> int:
        return len(self.batches)


def _policy(settings: dict[str, Any]) -> dict[str, Any]:
    return dict(settings.get("efficiency") or {})


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def plan_relevance_rows(rows: Iterable[dict[str, Any]], settings: dict[str, Any]) -> RelevancePlan:
    policy = _policy(settings)
    accept_at = _number(policy.get("auto_accept_rule_score"), 85)
    reject_below = _number(policy.get("auto_reject_rule_score"), 15)
    promote_at = _number(policy.get("radar_promotion_rule_score"), 88)
    batch_size = max(1, int(settings.get("max_relevance_batch", 12)))
    radar_topics = set(policy.get("radar_topics") or DEFAULT_RADAR_TOPICS)
    accepted, rejected, radar = [], [], []
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
    batches = []
    for topic_id in sorted(ambiguous):
        ordered = sorted(ambiguous[topic_id], key=lambda row: (-_number(row.get("rule_score")), str(row.get("id") or "")))
        batches.extend(tuple(ordered[i:i + batch_size]) for i in range(0, len(ordered), batch_size))
    return RelevancePlan(tuple(accepted), tuple(rejected), tuple(radar), tuple(batches))


def select_deep_budget(rows: Iterable[dict[str, Any]], settings: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    policy = _policy(settings)
    total_max = max(1, int(policy.get("max_fact_candidates_total", 10)))
    per_topic_max = max(1, int(policy.get("max_fact_candidates_per_topic", 3)))
    ordered = sorted(rows, key=lambda row: (
        -_number(row.get("relevance_score")), -_number(row.get("rule_score")),
        -_number(row.get("priority")), str(row.get("id") or ""),
    ))
    selected, deferred = [], []
    counts: dict[str, int] = defaultdict(int)
    for row in ordered:
        topic_id = str(row.get("topic_id") or "unknown")
        if len(selected) >= total_max or counts[topic_id] >= per_topic_max:
            deferred.append(row)
        else:
            selected.append(row)
            counts[topic_id] += 1
    return selected, deferred


def direction_is_covered(raw_rows: Iterable[dict[str, Any]], topic_id: str, direction: dict[str, Any]) -> bool:
    direction_id = str(direction.get("id") or "")
    terms = [str(term).strip().lower() for term in direction.get("include_terms") or [] if str(term).strip()]
    for row in raw_rows:
        if row.get("topic_hint") == topic_id and row.get("direction_hint") == direction_id:
            return True
        text = f"{row.get('title') or ''} {row.get('summary') or ''}".lower()
        matches = sum(term in text for term in terms)
        if terms and matches >= (1 if len(terms) <= 2 else 2):
            return True
    return False


def radar_category(title: str, summary: str) -> str:
    text = f" {title} {summary} ".lower()
    groups = (
        ("存储与介质", ("ssd", "nvme", "nand", "qlc", "tlc", "zns", "hdd", "persistent memory", "cxl memory", "hbm", "computational storage", "存储介质", "闪存", "持久内存")),
        ("KVCache生态", ("kv cache", "kvcache", "prefix cache", "lmcache", "cache-aware routing", "remote prefill", "prefill decode", "前缀缓存", "kv缓存")),
        ("Agent生态", ("agent", "agentic", "mcp", "computer use", "browser agent", "coding agent", "multi-agent", "agent memory", "tool call", "智能体")),
        ("AI Infra", ("serving", "inference", "runtime", "compiler", "kernel", "gpu", "accelerator", "distributed training", "collective", "cluster", "observability", "interconnect", "fabric", "推理", "运行时", "编译器", "加速器", "集群", "互联")),
    )
    for name, terms in groups:
        if any(term in text for term in terms):
            return name
    return "其他"


def estimate_task_reduction(*, candidates: int, ambiguous_candidates: int, batch_size: int,
                            fact_candidates_before: int, fact_budget: int,
                            item_candidates_before: int, item_budget: int,
                            search_before: int, search_after: int) -> dict[str, int | float]:
    relevance_after = (max(0, ambiguous_candidates) + max(1, batch_size) - 1) // max(1, batch_size)
    before = search_before + candidates + fact_candidates_before + item_candidates_before * 2
    after = search_after + relevance_after + min(fact_candidates_before, fact_budget) + min(item_candidates_before, item_budget) * 2
    return {
        "tasks_before": before,
        "tasks_after": after,
        "task_reduction_ratio": round(0.0 if not before else (before - after) / before, 4),
        "relevance_tasks_before": candidates,
        "relevance_tasks_after": relevance_after,
    }


def install_pipeline_optimizations() -> None:
    from . import demo as demo_module, emailer as emailer_module, pipeline as pipeline_module
    from .fulltext import FulltextService
    from .paths import Paths
    from .utils import read_json, stable_hash

    Pipeline = pipeline_module.Pipeline
    if getattr(Pipeline, "_efficiency_policy_installed", False):
        return
    original_apply = Pipeline._apply_task
    original_demo = demo_module._demo_output

    def prepare_agent_search(self, max_queries: int = 4) -> int:
        policy = _policy(self.config.settings)
        limit = min(max(0, int(max_queries)), int(self.config.settings.get("agent_web_search_max_queries", 4)))
        if not limit:
            return 0
        deep_topics = set(policy.get("deep_topics") or DEFAULT_DEEP_TOPICS)
        raw_rows = self.db.fetchall("SELECT title,summary,topic_hint,direction_hint FROM raw_items WHERE run_id=?", (self.run_id,))
        priority = {"highest": 100, "high": 80, "medium": 55, "low": 30}
        gaps = [(topic, direction) for topic, direction in self.config.iter_directions()
                if topic.get("id") in deep_topics and not direction_is_covered(raw_rows, topic["id"], direction)]
        gaps.sort(key=lambda pair: (-priority.get(pair[0].get("aihot_priority", "low"), 30), pair[0]["id"], pair[1]["id"]))
        absolute_days = pipeline_module.freshness_limits(self.config)["absolute"]
        date_to = datetime.now(timezone.utc).date()
        date_from = date_to - timedelta(days=absolute_days)
        created = 0
        for topic, direction in gaps[:limit]:
            queries = direction.get("queries") or []
            if not queries:
                continue
            domains = []
            if topic["id"] == "agent_acceleration":
                domains = ["arxiv.org", "openreview.net", "github.com", "simonwillison.net", "latent.space"]
            elif topic["id"] == "optical_network":
                domains = ["ofcconference.org", "dl.acm.org", "arxiv.org", "research.google"]
            self.tasks.create(self.run_id, "agent_web_search", f"{topic['id']}:{direction['id']}", {
                "topic_id": topic["id"], "topic_name": topic["name"],
                "direction_id": direction["id"], "direction_name": direction["name"],
                "query": queries[0], "preferred_domains": domains,
                "freshness_days": absolute_days, "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(), "max_results": 10,
                "search_reason": "fixed-source coverage gap",
            }, prompt="agent-web-search.md", schema="web-search-results.schema.json",
               priority=priority.get(topic.get("aihot_priority", "low"), 30))
            created += 1
        if created:
            self.db.update_run(self.run_id, stage="AWAITING_AGENT_SEARCH")
        return created

    def prepare_relevance(self) -> int:
        pipeline_module.RuleMatcher(self.config, self.db).create_candidates(self.run_id)
        rows = self.db.fetchall("""
            SELECT c.*,r.title,r.summary,r.original_url,r.aihot_url,r.published_at,r.discovered_at,
                   r.discovery_source,r.source_level,r.discovery_only,r.payload_json,r.priority
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.status='PENDING_RELEVANCE'
            ORDER BY c.rule_score DESC,c.id
        """, (self.run_id,))
        plan = plan_relevance_rows(rows, self.config.settings)
        for row in plan.accepted:
            self.db.execute("UPDATE candidates SET relevant=1,relevance_score=?,relevance_reason='high-confidence A-level rule match',fulltext_required=1,status='RELEVANT' WHERE id=?", (max(85.0, _number(row.get("rule_score"))), row["id"]))
        for row in plan.rejected:
            self.db.execute("UPDATE candidates SET relevant=0,relevance_score=?,relevance_reason='below deterministic relevance floor',fulltext_required=0,status='REJECTED' WHERE id=?", (_number(row.get("rule_score")), row["id"]))
        for row in plan.radar:
            self.db.execute("UPDATE candidates SET relevant=NULL,relevance_reason='retained in horizontal radar without deep processing',fulltext_required=0,status='RADAR' WHERE id=?", (row["id"],))
        for index, batch in enumerate(plan.batches, 1):
            topic_id = str(batch[0]["topic_id"])
            topic = self.config.topic(topic_id)
            entity_id = stable_hash(self.run_id, "relevance-batch", topic_id, index)
            self.tasks.create(self.run_id, "relevance_batch", entity_id, {
                "batch_id": f"{topic_id}-{index}", "topic": topic,
                "project_context_path": str(self.config.context_path(Paths(self.root), topic_id).relative_to(self.root)),
                "candidates": [{
                    "candidate_id": row["id"], "title": row["title"], "summary": row["summary"],
                    "rule_score": row["rule_score"],
                    "direction": self.config.direction(topic_id, row["direction_id"]),
                    "source": {"discovery_source": row["discovery_source"], "source_level": row["source_level"],
                               "discovery_only": bool(row["discovery_only"]), "original_url": row["original_url"],
                               "published_at": row["published_at"]},
                } for row in batch],
                "constraints": {"do_not_read_fulltext_yet": True, "deep_channel_requires_a_level": True},
            }, prompt="relevance-batch.md", schema="relevance-batch.schema.json",
               priority=max(_number(row.get("rule_score")) for row in batch))
            for row in batch:
                self.db.execute("UPDATE candidates SET status='RELEVANCE_TASKED' WHERE id=?", (row["id"],))
        if plan.agent_task_count:
            self.db.update_run(self.run_id, stage="AWAITING_RELEVANCE")
        return plan.agent_task_count

    def apply_task(self, task: dict[str, Any]) -> None:
        if task["task_type"] != "relevance_batch":
            return original_apply(self, task)
        output = self.tasks.read_result(task)
        task_input = read_json(self.root / task["input_path"], {})
        expected = {str(row.get("candidate_id")) for row in task_input.get("candidates", [])}
        for result in output.get("results", []):
            candidate_id = str(result.get("candidate_id") or "")
            if candidate_id not in expected:
                continue
            relevant = bool(result.get("relevant"))
            deep = relevant and bool(result.get("fulltext_required", True))
            self.db.execute("""
                UPDATE candidates SET relevant=?,relevance_score=?,relevance_reason=?,fulltext_required=?,status=? WHERE id=?
            """, (int(relevant), result.get("score"), result.get("reason"), int(deep),
                    "RELEVANT" if deep else ("RADAR" if relevant else "REJECTED"), candidate_id))

    def maybe_prepare_facts(self) -> None:
        unfinished = self.db.fetchone("""
            SELECT COUNT(*) AS n FROM tasks WHERE run_id=? AND task_type IN ('relevance_review','relevance_batch')
            AND status IN ('PENDING','INVALID','COMPLETED')
        """, (self.run_id,))["n"]
        if unfinished:
            return
        rows = self.db.fetchall("""
            SELECT c.*,r.title,r.summary,r.original_url,r.aihot_url,r.published_at,
                   r.discovery_source,r.source_level,r.discovery_only,r.payload_json,r.priority
            FROM candidates c JOIN raw_items r ON r.id=c.raw_item_id
            WHERE c.run_id=? AND c.status='RELEVANT' AND c.fulltext_required=1
              AND r.source_level='A' AND r.discovery_only=0
            ORDER BY c.relevance_score DESC,c.rule_score DESC,r.priority DESC
        """, (self.run_id,))
        selected, deferred = select_deep_budget(rows, self.config.settings)
        for row in deferred:
            self.db.execute("UPDATE candidates SET status='DEFERRED_BUDGET' WHERE id=?", (row["id"],))
        if not selected:
            return
        fulltext = FulltextService(self.config, self.db, self.run_dir)
        try:
            for row in selected:
                if self.db.fetchone("SELECT 1 FROM tasks WHERE run_id=? AND task_type='fact_extraction' AND entity_id=?", (self.run_id, row["id"])):
                    continue
                manifest = fulltext.fetch_candidate(self.run_id, row)
                topic = self.config.topic(row["topic_id"])
                self.tasks.create(self.run_id, "fact_extraction", row["id"], {
                    "candidate_id": row["id"],
                    "source": {"title": row["title"], "summary": row["summary"],
                               "url": row["original_url"] or row["aihot_url"], "published_at": row["published_at"],
                               "discovery_source": row["discovery_source"], "source_level": row["source_level"],
                               "discovery_only": bool(row["discovery_only"])},
                    "topic": {"id": topic["id"], "name": topic["name"],
                              "current_questions": topic.get("current_questions", []),
                              "valuable_evidence": topic.get("valuable_evidence", [])},
                    "direction": self.config.direction(row["topic_id"], row["direction_id"]),
                    "project_context_path": str(self.config.context_path(Paths(self.root), topic["id"]).relative_to(self.root)),
                    "document": {**manifest, "text_path": str(Path(manifest["text_path"]).relative_to(self.root)),
                                 "chunks": [str(Path(path).relative_to(self.root)) for path in manifest["chunks"]]},
                }, prompt="fact-extraction.md", schema="facts.schema.json", priority=_number(row.get("relevance_score")))
                self.db.execute("UPDATE candidates SET status='FACT_TASKED' WHERE id=?", (row["id"],))
        finally:
            fulltext.close()
        self.db.update_run(self.run_id, stage="AWAITING_FACTS")

    def radar_groups(self, issue_date: str | None, *, issue_id: str | None = None, issue_data: dict[str, Any] | None = None):
        if issue_id:
            persisted = self._persisted_radar_groups(issue_id)
            if persisted:
                return persisted
        self._backfill_radar_history()
        zone = ZoneInfo(str(self.config.settings.get("timezone", "Asia/Shanghai")))
        end = datetime.fromisoformat(f"{issue_date}T23:59:59").replace(tzinfo=zone).astimezone(timezone.utc) if issue_date else datetime.now(timezone.utc)
        radar = self.config.scoring.get("radar", {})
        start = end - timedelta(days=int(radar.get("max_age_days", 7)))
        total_max, per_category = int(radar.get("total_max", 8)), int(radar.get("max_per_category", 2))
        issue_row = self.db.fetchone("SELECT run_id FROM issues WHERE id=?", (issue_id,)) if issue_id else None
        run_id = issue_row.get("run_id") if issue_row else None
        where, params = ("WHERE run_id=?", (run_id,)) if run_id else ("", ())
        rows = self.db.fetchall(f"""
            SELECT title,summary,original_url,canonical_url,published_at,priority,discovery_source
            FROM raw_items {where}
            ORDER BY priority DESC,published_at DESC,LENGTH(COALESCE(summary,'')) DESC,title
        """, params)
        order = ("AI Infra", "Agent生态", "KVCache生态", "存储与介质")
        groups: dict[str, list[dict[str, Any]]] = {name: [] for name in order}
        seen_urls = {str(row["canonical_url"]) for row in self.db.fetchall("SELECT canonical_url FROM radar_history")}
        seen_titles = {str(row["normalized_title"]) for row in self.db.fetchall("SELECT normalized_title FROM radar_history")}
        for item in (issue_data or {}).get("items", []):
            seen_urls.update(str(source["url"]) for source in item.get("sources", []) if source.get("url"))
        for row in rows:
            url = str(row.get("original_url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            published = self._parse_source_time(row.get("published_at"))
            if not published or not start <= published <= end:
                continue
            title_key = self._normalise_reference(row["title"])
            canonical = str(row.get("canonical_url") or url)
            if canonical in seen_urls or title_key in seen_titles or not self._radar_is_technical(row["title"], row.get("summary") or ""):
                continue
            category = radar_category(row["title"], row.get("summary") or "")
            if category not in groups or len(groups[category]) >= per_category:
                continue
            groups[category].append({"title": row["title"], "summary": self._complete_excerpt(row.get("summary"), 120),
                                     "url": url, "source_name": str(row.get("discovery_source") or parsed.hostname),
                                     "published_at": published.date().isoformat()})
            seen_urls.add(canonical)
            seen_titles.add(title_key)
            if sum(map(len, groups.values())) >= total_max:
                break
        result = [{"name": name, "items": groups[name]} for name in order if groups[name]]
        if issue_id:
            position = 0
            for group in result:
                for item in group["items"]:
                    position += 1
                    self.db.execute("""INSERT OR REPLACE INTO issue_radar_items(
                        issue_id,canonical_url,normalized_title,category,title,summary,source_name,published_at,position
                    ) VALUES (?,?,?,?,?,?,?,?,?)""", (issue_id, item["url"], self._normalise_reference(item["title"]),
                        group["name"], item["title"], item["summary"], item["source_name"], item["published_at"], position))
        return result

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == "relevance_batch":
            return {"results": [{"candidate_id": row["candidate_id"], "relevant": True, "score": 88,
                                  "reason": "与指定方向直接相关，并包含可验证机制。", "fulltext_required": True,
                                  "matched_signals": ["机制", "端到端加速"]} for row in data.get("candidates", [])]}
        return original_demo(task_type, data)

    Pipeline.prepare_agent_search = prepare_agent_search
    Pipeline.prepare_relevance = prepare_relevance
    Pipeline._apply_task = apply_task
    Pipeline._maybe_prepare_facts = maybe_prepare_facts
    Pipeline._efficiency_policy_installed = True
    emailer_module.EmailService._aihot_groups = radar_groups
    demo_module._demo_output = demo_output
