from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import ConfigBundle
from .utils import parse_datetime


class Scorer:
    def __init__(self, config: ConfigBundle):
        self.config = config
        self.weights = config.scoring.get("weights", {})

    def event_score(self, facts: list[dict[str, Any]], candidates: list[dict[str, Any]], raw_items: list[dict[str, Any]]) -> float:
        if not facts:
            return 0.0
        relevance = max(float(candidate.get("relevance_score") or 0) for candidate in candidates)
        project_relevance = relevance / 100 * float(self.weights.get("project_relevance", 30))
        mechanisms = [fact.get("mechanism") for fact in facts if fact.get("mechanism")]
        evidence_count = sum(len(fact.get("evidence") or []) for fact in facts)
        limitations = sum(1 for fact in facts if fact.get("limitations"))
        novelty = min(1.0, 0.4 + 0.2 * len(mechanisms)) * float(self.weights.get("novelty", 20))
        evidence = min(1.0, evidence_count / 3) * float(self.weights.get("evidence_quality", 20))
        depth = min(1.0, (len(mechanisms) + limitations) / 3) * float(self.weights.get("technical_depth", 15))
        actionability = min(1.0, sum(1 for fact in facts if fact.get("project_relevance")) / 2) * float(self.weights.get("actionability", 10))
        freshness = self._freshness(raw_items) * float(self.weights.get("freshness", 5))
        primary_bonus = 5 if any(item.get("source_level") == "A" for item in raw_items) else 0
        multi_source_bonus = 3 if len({item.get("canonical_url") for item in raw_items if item.get("canonical_url")}) >= 2 else 0
        return round(min(100.0, project_relevance + novelty + evidence + depth + actionability + freshness + primary_bonus + multi_source_bonus), 2)

    @staticmethod
    def _freshness(raw_items: list[dict[str, Any]]) -> float:
        now = datetime.now(timezone.utc)
        ages = []
        for item in raw_items:
            dt = parse_datetime(item.get("published_at") or item.get("discovered_at"))
            if dt:
                ages.append((now - dt).days)
        age = min(ages) if ages else 30
        if age <= 2:
            return 1.0
        if age <= 7:
            return 0.8
        if age <= 30:
            return 0.4
        if age <= 90:
            return 0.2
        return 0.0
