from __future__ import annotations

from typing import Any


def install_topic_appendix_rendering() -> None:
    """Attach Top4 remainder summaries to their owning topic before Jinja rendering."""

    from . import coverage_policy
    from .emailer import EmailService

    if getattr(EmailService, "_topic_appendix_rendering_installed", False):
        return

    original_topic_groups = EmailService._topic_groups

    def topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        groups = original_topic_groups(self, data)
        appendix = getattr(self, "_topic_appendix_cache", {}) or {}
        by_id = {str(group.get("id")): group for group in groups}

        for topic in self.config.topic_list():
            topic_id = str(topic.get("id") or "")
            extra = list(appendix.get(topic_id) or [])
            if not extra:
                continue
            group = by_id.get(topic_id)
            if group is None:
                group = {
                    "id": topic_id,
                    "name": topic.get("name") or topic_id,
                    "description": topic.get("description", ""),
                    "items": [],
                    "observations": [],
                    "total_count": 0,
                }
                groups.append(group)
                by_id[topic_id] = group
            group["appendix"] = extra
            group["appendix_count"] = len(extra)
            group["total_count"] = int(group.get("total_count") or 0) + len(extra)

        for group in groups:
            group.setdefault("appendix", [])
            group.setdefault("appendix_count", len(group["appendix"]))

        order = {str(topic.get("id")): index for index, topic in enumerate(self.config.topic_list())}
        groups.sort(key=lambda group: order.get(str(group.get("id")), len(order)))
        return groups

    def no_legacy_appendix_html(service, appendix):
        return ""

    coverage_policy._appendix_html = no_legacy_appendix_html
    EmailService._topic_groups = topic_groups
    EmailService._topic_appendix_rendering_installed = True
