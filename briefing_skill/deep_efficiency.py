from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .paths import Paths
from .utils import stable_hash, write_json


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

INTRO_TERMS = ("abstract", "introduction", "overview", "motivation", "background", "摘要", "引言", "背景")
METHOD_TERMS = ("method", "design", "architecture", "implementation", "algorithm", "system", "方法", "设计", "架构", "实现", "算法")
EVAL_TERMS = ("evaluation", "experiment", "results", "benchmark", "performance", "latency", "throughput", "实验", "评估", "结果", "性能", "时延", "吞吐")
BOUNDARY_TERMS = ("limitation", "limitations", "discussion", "conclusion", "threat", "限制", "局限", "讨论", "结论")
EVIDENCE_STRATEGY = "balanced-evidence-v2"


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
    """Allow cross-run reuse only for sources with a strong immutable version identity."""

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

    Keep the historical front-evidence marker inside the hashed compatibility payload so
    existing balanced-v2 Fact Cache keys remain stable across this ownership refactor.
    Balanced Evidence is nevertheless the only runtime EvidenceBuilder.
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
            parts.extend([str(topic_id), str(direction_id)])

    base = f"{parts[0]}:{stable_hash(*parts, length=16)}"
    return f"{base}:{EVIDENCE_STRATEGY}"


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


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _normalised_heading(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _role_candidates(
    scored: list[dict[str, Any]],
    used: set[int],
    keywords: tuple[str, ...],
) -> list[dict[str, Any]]:
    available = [row for row in scored if int(row["index"]) not in used]
    heading_matches = [row for row in available if _contains(str(row["title"]), keywords)]
    matches = heading_matches or [
        row for row in available if _contains(str(row["body"])[:1200], keywords)
    ]
    matches.sort(key=lambda row: (-float(row["score"]), int(row["index"])))
    deduped: list[dict[str, Any]] = []
    seen_headings: set[str] = set()
    for row in matches:
        heading = _normalised_heading(row["title"])
        if heading in seen_headings:
            continue
        seen_headings.add(heading)
        deduped.append(row)
    return deduped


def build_evidence_pack(
    text: str,
    topic: dict[str, Any],
    direction: dict[str, Any],
    *,
    max_chars: int = 18000,
) -> str:
    """Build the single canonical first read across context/mechanism/results/bounds."""

    max_chars = max(4000, int(max_chars))
    sections = _sections(text)
    if not sections:
        return _safe_excerpt(text, max_chars)

    terms = _evidence_terms(topic, direction)
    scored = [
        {"index": index, "title": title, "body": body, "score": _section_score(index, title, body, terms)}
        for index, title, body in sections
        if str(body or "").strip()
    ]
    groups: list[tuple[str, tuple[str, ...], float]] = [
        ("context", INTRO_TERMS, 0.18),
        ("mechanism", METHOD_TERMS, 0.30),
        ("results", EVAL_TERMS, 0.38),
        ("boundary", BOUNDARY_TERMS, 0.14),
    ]
    selected: list[dict[str, Any]] = []
    used: set[int] = set()
    header = (
        "# Balanced Evidence Pack\n\n"
        "This first read intentionally spans problem context, mechanism, evaluation/results, "
        "and limitations. Evidence locators preserve the source section names.\n\n"
    )
    remaining = max_chars - len(header)

    for label, keywords, ratio in groups:
        budget = max(500, int((max_chars - len(header)) * ratio))
        candidates = _role_candidates(scored, used, keywords)
        if label == "context" and not candidates:
            candidates = [row for row in scored if row["index"] <= 1 and row["index"] not in used]
        group_used = 0
        for row in candidates[:2]:
            locator = f"## Evidence locator: {row['title']}\n\n"
            allowance = min(budget - group_used, remaining - len(locator) - 2, 5200)
            if allowance <= 180:
                break
            excerpt = _safe_excerpt(str(row["body"]), allowance)
            if not excerpt:
                continue
            selected.append({**row, "excerpt": excerpt, "group": label})
            used.add(int(row["index"]))
            consumed = len(locator) + len(excerpt) + 2
            group_used += consumed
            remaining -= consumed
            if group_used >= budget or remaining <= 300:
                break

    if remaining > 500:
        supplemental_headings = {_normalised_heading(row["title"]) for row in selected}
        for row in sorted(scored, key=lambda value: (-float(value["score"]), int(value["index"]))):
            if row["index"] in used:
                continue
            heading = _normalised_heading(row["title"])
            if heading in supplemental_headings:
                continue
            locator = f"## Evidence locator: {row['title']}\n\n"
            allowance = min(remaining - len(locator) - 2, 4200)
            if allowance <= 180:
                break
            excerpt = _safe_excerpt(str(row["body"]), allowance)
            if not excerpt:
                continue
            selected.append({**row, "excerpt": excerpt, "group": "supplemental"})
            used.add(int(row["index"]))
            supplemental_headings.add(heading)
            remaining -= len(locator) + len(excerpt) + 2
            if remaining <= 300:
                break

    if not selected:
        return _safe_excerpt(text, max_chars)
    group_order = {"context": 0, "mechanism": 1, "results": 2, "boundary": 3, "supplemental": 4}
    selected.sort(key=lambda row: (group_order.get(str(row["group"]), 9), int(row["index"])))
    blocks = [header.rstrip()]
    for row in selected:
        blocks.append(f"## Evidence locator: {row['title']}\n\n{str(row['excerpt']).strip()}")
    return "\n\n".join(blocks).strip()[:max_chars].rstrip()


def install_deep_efficiency() -> None:
    """Install the canonical Balanced EvidenceBuilder.

    Fact-cache ownership lives in Fact Cache V2. This stage performs only source-to-
    Evidence transformation and records the exact strategy/version consumed downstream.
    """

    from .fulltext import FulltextService

    if getattr(FulltextService, "_evidence_pack_installed", False):
        return

    original_fetch = FulltextService.fetch_candidate

    def fetch_candidate(self, run_id: str, candidate: dict) -> dict:
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

        manifest = original_fetch(self, run_id, effective_candidate)
        raw_text_path = Path(manifest["text_path"])
        text = raw_text_path.read_text(encoding="utf-8")
        topic_id = effective_candidate.get("topic_id")
        direction_id = effective_candidate.get("direction_id")
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
            "evidence_strategy": EVIDENCE_STRATEGY,
            "fact_cache_hit": False,
            "source_fingerprint": _source_fingerprint(raw),
            "extractor_version": _runtime_extractor_version(self.config, self.run_dir.parents[2], topic_id, direction_id),
            "fact_cache_eligible": False,
        }
        write_json(self.run_dir / "documents" / f"{manifest['document_id']}.json", enriched)
        return enriched

    FulltextService.fetch_candidate = fetch_candidate
    FulltextService._evidence_pack_installed = True
