from __future__ import annotations

import json
import math
from typing import Any

from .config import ConfigBundle
from .db import Database
from .freshness import candidate_is_fresh
from .utils import normalize_text, now_iso, stable_hash, tokenize


class RuleMatcher:
    def __init__(self, config: ConfigBundle, db: Database):
        self.config = config
        self.db = db

    def create_candidates(self, run_id: str) -> list[dict[str, Any]]:
        raw_items = self.db.fetchall("SELECT * FROM raw_items WHERE run_id=? ORDER BY priority DESC", (run_id,))
        candidates: list[dict[str, Any]] = []
        for raw in raw_items:
            if not candidate_is_fresh(raw.get("published_at"), self.config):
                continue
            matches = self._matches(raw)
            limit = 1 if raw.get("direction_hint") else 2
            for topic_id, direction_id, score in matches[:limit]:
                if score < 15:
                    continue
                candidate_id = stable_hash(run_id, raw["id"], topic_id, direction_id)
                row = {
                    "id": candidate_id,
                    "run_id": run_id,
                    "raw_item_id": raw["id"],
                    "topic_id": topic_id,
                    "direction_id": direction_id,
                    "rule_score": score,
                    "status": "PENDING_RELEVANCE",
                    "created_at": now_iso(),
                }
                with self.db.connect() as conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO candidates(
                            id, run_id, raw_item_id, topic_id, direction_id, rule_score, status, created_at
                        ) VALUES (:id, :run_id, :raw_item_id, :topic_id, :direction_id, :rule_score, :status, :created_at)
                        """,
                        row,
                    )
                candidates.append(row)
        return candidates

    def _matches(self, raw: dict[str, Any]) -> list[tuple[str, str, float]]:
        text = normalize_text(f"{raw.get('title','')} {raw.get('summary','')}")
        tokens = tokenize(text)
        hints = (raw.get("topic_hint") or "", raw.get("direction_hint") or "")
        payload = json.loads(raw.get("payload_json") or "{}")
        allowlist = set(payload.get("topic_allowlist") or [])
        results: list[tuple[str, str, float]] = []
        for topic, direction in self.config.iter_directions():
            if allowlist and topic["id"] not in allowlist:
                continue
            include = [normalize_text(term) for term in direction.get("include_terms", [])]
            exclude = [normalize_text(term) for term in direction.get("exclude_terms", [])]
            if any(term and term in text for term in exclude):
                continue
            hits = sum(1 for term in include if term and term in text)
            query_terms = tokenize(" ".join(direction.get("queries", [])))
            overlap = len(tokens & query_terms)
            score = hits * 12 + min(overlap, 10) * 2
            if hints[0] == topic["id"]:
                score += 24
            if hints[1] == direction["id"]:
                score += 24
            if raw.get("source_id") == "aihot" and topic.get("aihot_priority") in {"highest", "high"}:
                score += 6
            score += min(float(raw.get("priority") or 0) / 5, 8)
            if hits or overlap or hints[0] == topic["id"]:
                results.append((topic["id"], direction["id"], round(score, 2)))
        return sorted(results, key=lambda item: item[2], reverse=True)
