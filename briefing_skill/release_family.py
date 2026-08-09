from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse


def _repo_label(project_key: str) -> str:
    return project_key.removeprefix("github:") or "GitHub project"


def _display_repo_label(project_key: str, item: dict[str, Any]) -> str:
    parsed = urlparse(str(item.get("url") or ""))
    parts = [part for part in parsed.path.split("/") if part]
    if (parsed.hostname or "").lower().endswith("github.com") and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return _repo_label(project_key)


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

    # Releases from one repository can be routed to different topics. Aggregate
    # globally, then keep the family in the topic containing its newest member.
    # This prevents vN and vN+1 from appearing as separate short items merely
    # because their release notes matched different topic keywords.
    positions: dict[str, list[tuple[int, int, str, dict[str, Any]]]] = defaultdict(list)
    passthrough: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for topic_index, (topic_id, items) in enumerate(appendix.items()):
        for item_index, item in enumerate(items):
            project = str(item.get("project_key") or "")
            if project.startswith("github:"):
                positions[project].append((topic_index, item_index, topic_id, item))
            else:
                passthrough[topic_id].append((item_index, item))

    rebuilt_by_topic: dict[str, list[tuple[int, dict[str, Any]]]] = {
        topic_id: list(items) for topic_id, items in passthrough.items()
    }
    for project, members in positions.items():
        if len(members) == 1:
            _, item_index, topic_id, item = members[0]
            rebuilt_by_topic.setdefault(topic_id, []).append((item_index, item))
            continue
        ordered = sorted(
            (item for _, _, _, item in members),
            key=lambda item: str(item.get("published_at") or ""),
            reverse=True,
        )
        newest = ordered[0]
        host = next(member for member in members if member[3] is newest)
        _, host_index, host_topic, _ = host
        links = [
            {
                "url": item.get("url"),
                "label": str(item.get("published_at") or f"更新{idx}"),
                "title": item.get("title"),
            }
            for idx, item in enumerate(ordered, 1)
            if item.get("url")
        ]
        rebuilt_by_topic.setdefault(host_topic, []).append(
            (
                host_index,
                {
                    **newest,
                    "title": f"{_display_repo_label(project, newest)}：近期 {len(ordered)} 项相关更新",
                    "summary": _compact_family_summary(ordered),
                    "published_at": max(
                        str(item.get("published_at") or "") for item in ordered
                    ),
                    "score": max(float(item.get("score") or 0) for item in ordered),
                    "links": links,
                    "family_size": len(ordered),
                },
            )
        )

    collapsed: dict[str, list[dict[str, Any]]] = {}
    for topic_id in appendix:
        rebuilt = rebuilt_by_topic.get(topic_id, [])
        rebuilt.sort(key=lambda pair: pair[0])
        if rebuilt:
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
