from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def _repo_label(project_key: str) -> str:
    return project_key.removeprefix("github:") or "GitHub project"


def _compact_family_summary(items: list[dict[str, Any]], limit: int = 280) -> str:
    parts: list[str] = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()
        if not text:
            continue
        parts.append(text.rstrip("。.!?；; ") + "。")
    result = " ".join(parts)
    if len(result) <= limit:
        return result
    clipped = result[:limit]
    matches = list(re.finditer(r"[。！？.!?]", clipped))
    return clipped[: matches[-1].end()].strip() if matches else clipped.rstrip("，,：:；; ") + "。"


def collapse_release_families(
    appendix: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Collapse repeated low-cost GitHub appendix updates from the same project.

    This deliberately operates only after Top4 selection. It never merges deep
    items and never merges unrelated papers merely because they share a topic.
    """

    collapsed: dict[str, list[dict[str, Any]]] = {}
    for topic_id, items in appendix.items():
        groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        passthrough: list[tuple[int, dict[str, Any]]] = []
        for index, item in enumerate(items):
            project = str(item.get("project_key") or "")
            if project.startswith("github:"):
                groups[project].append((index, item))
            else:
                passthrough.append((index, item))

        rebuilt: list[tuple[int, dict[str, Any]]] = list(passthrough)
        for project, members in groups.items():
            if len(members) == 1:
                rebuilt.append(members[0])
                continue
            ordered = sorted((item for _, item in members), key=lambda item: str(item.get("published_at") or ""), reverse=True)
            first_index = min(index for index, _ in members)
            links = [
                {
                    "url": item.get("url"),
                    "label": str(item.get("published_at") or f"更新{idx}"),
                    "title": item.get("title"),
                }
                for idx, item in enumerate(ordered, 1)
                if item.get("url")
            ]
            rebuilt.append(
                (
                    first_index,
                    {
                        **ordered[0],
                        "title": f"{_repo_label(project)}：近期 {len(ordered)} 项相关更新",
                        "summary": _compact_family_summary(ordered),
                        "published_at": max(str(item.get("published_at") or "") for item in ordered),
                        "score": max(float(item.get("score") or 0) for item in ordered),
                        "links": links,
                        "family_size": len(ordered),
                    },
                )
            )
        rebuilt.sort(key=lambda pair: pair[0])
        collapsed[topic_id] = [item for _, item in rebuilt]
    return collapsed


def install_release_family_aggregation() -> None:
    """Group repeated GitHub updates only in each topic's short appendix."""

    from . import coverage_policy

    if getattr(coverage_policy, "_release_family_installed", False):
        return
    original_collect = coverage_policy.collect_topic_appendix

    def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]):
        return collapse_release_families(original_collect(service, run_id, issue_data))

    coverage_policy.collect_topic_appendix = collect_topic_appendix
    coverage_policy._release_family_installed = True
