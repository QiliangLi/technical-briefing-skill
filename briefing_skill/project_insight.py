from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .config import ConfigBundle
from .paths import Paths
from .utils import read_json


PROJECT_EFFECTS = ("supports", "challenges", "narrows", "opens")
CONFIDENCE_LEVELS = ("high", "medium", "low")
MAX_INSIGHTS = 4
MAX_CONTEXT_CHARS = 3200
COMPLETE_ENDING_RE = re.compile(r"[。！？.!?](?:[”’\"）)\]]*)$")
INCOMPLETE_ENDING_RE = re.compile(r"(?:…|\.\.\.|[，,:：;；、])(?:[”’\"）)\]]*)$")


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_project_context_cards(
    root: Path,
    config: ConfigBundle,
    topic_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Build compact configured project cards only for topics present in the issue."""

    paths = Paths(root)
    cards: list[dict[str, Any]] = []
    for topic_id in _ordered_unique(topic_ids):
        topic = config.topic(topic_id)
        context_path = config.context_path(paths, topic_id)
        if not context_path.is_file():
            raise RuntimeError(f"Missing project context for configured topic: {topic_id}")
        context = context_path.read_text(encoding="utf-8").strip()
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS].rstrip()
        cards.append(
            {
                "topic_id": topic_id,
                "topic_name": str(topic.get("name") or topic_id),
                "current_questions": [
                    str(question).strip()
                    for question in topic.get("current_questions") or []
                    if str(question).strip()
                ],
                "valuable_evidence": [
                    str(value).strip()
                    for value in topic.get("valuable_evidence") or []
                    if str(value).strip()
                ],
                "judgement_card": context,
            }
        )
    return cards


def enrich_issue_synthesis_input(root: Path, input_data: dict[str, Any]) -> dict[str, Any]:
    """Attach project questions to the existing issue-synthesis Agent task."""

    payload = dict(input_data)
    config = ConfigBundle.load(Paths(root))
    topic_ids = [str(item.get("topic_id") or "") for item in payload.get("items") or []]
    payload["project_contexts"] = build_project_context_cards(root, config, topic_ids)
    payload["project_insight_policy"] = {
        "max_insights": MAX_INSIGHTS,
        "allowed_effects": list(PROJECT_EFFECTS),
        "require_configured_question": True,
        "require_exact_evidence_item_ids": True,
        "allow_empty_when_no_material_change": True,
        "source_fact_and_project_judgement_must_be_separated": True,
    }
    return payload


def _task_metadata(task: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(task.get("metadata_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _complete_sentence(value: Any) -> bool:
    text = " ".join(str(value or "").split())
    return bool(text) and not INCOMPLETE_ENDING_RE.search(text) and bool(COMPLETE_ENDING_RE.search(text))


def project_insight_semantic_errors(
    task: dict[str, Any],
    input_data: dict[str, Any],
    data: dict[str, Any],
) -> list[str]:
    """Fail closed for new Project Insight tasks while keeping legacy runs resumable."""

    if task.get("task_type") != "issue_synthesis":
        return []
    if not _task_metadata(task).get("project_insights_required"):
        return []

    insights = data.get("project_insights")
    if not isinstance(insights, list):
        return ["issue synthesis requires project_insights"]
    if len(insights) > MAX_INSIGHTS:
        return [f"project_insights exceeds maximum {MAX_INSIGHTS}"]

    contexts = {
        str(card.get("topic_id") or ""): card
        for card in input_data.get("project_contexts") or []
        if isinstance(card, dict) and card.get("topic_id")
    }
    items = {
        str(item.get("brief_item_id") or ""): item
        for item in input_data.get("items") or []
        if isinstance(item, dict) and item.get("brief_item_id")
    }
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for index, insight in enumerate(insights):
        if not isinstance(insight, dict):
            errors.append(f"project insight {index} must be an object")
            continue
        topic_id = str(insight.get("topic_id") or "")
        context = contexts.get(topic_id)
        if not context:
            errors.append(f"project insight {index} references unknown topic_id {topic_id}")
            continue
        if str(insight.get("topic_name") or "") != str(context.get("topic_name") or ""):
            errors.append(f"project insight {index} topic_name must exactly match project context")

        question = str(insight.get("project_question") or "").strip()
        configured_questions = {str(value).strip() for value in context.get("current_questions") or []}
        if question not in configured_questions:
            errors.append(f"project insight {index} must use an exact configured project_question")

        effect = str(insight.get("effect") or "")
        if effect not in PROJECT_EFFECTS:
            errors.append(f"project insight {index} has unsupported effect {effect}")
        confidence = str(insight.get("confidence") or "")
        if confidence not in CONFIDENCE_LEVELS:
            errors.append(f"project insight {index} has unsupported confidence {confidence}")

        evidence_ids = [str(value) for value in insight.get("evidence_item_ids") or []]
        if not evidence_ids:
            errors.append(f"project insight {index} requires evidence_item_ids")
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"project insight {index} contains duplicate evidence_item_ids")
        unknown = sorted(set(evidence_ids) - set(items))
        if unknown:
            errors.append(
                f"project insight {index} references unknown evidence_item_ids: {', '.join(unknown)}"
            )
        known_evidence = [items[item_id] for item_id in evidence_ids if item_id in items]
        if known_evidence and not any(str(item.get("topic_id") or "") == topic_id for item in known_evidence):
            errors.append(f"project insight {index} requires at least one same-topic evidence item")

        if not _complete_sentence(insight.get("insight")):
            errors.append(f"project insight {index} insight must be a complete sentence")
        if not _complete_sentence(insight.get("next_action")):
            errors.append(f"project insight {index} next_action must be a complete sentence")

        identity = (topic_id, question, effect)
        if identity in seen:
            errors.append(f"project insight {index} duplicates the same topic/question/effect")
        seen.add(identity)
    return errors


def render_project_insight_email_block(issue: dict[str, Any]) -> str:
    """Legacy renderer retained for archived callers; active publication does not call it."""

    insights = issue.get("synthesis", {}).get("project_insights") or []
    if not insights:
        return ""

    core_items = issue.get("core_items") or [
        item for item in issue.get("items", []) if item.get("item_role", "core") == "core"
    ]
    items_by_id = {
        str(item.get("brief_item_id")): item
        for item in core_items
        if item.get("brief_item_id")
    }
    effect_labels = {
        "supports": "加强判断",
        "challenges": "挑战判断",
        "narrows": "收窄边界",
        "opens": "打开新方向",
    }
    confidence_labels = {"high": "高置信", "medium": "中置信", "low": "低置信"}
    rows: list[str] = []
    for index, insight in enumerate(insights, 1):
        refs: list[str] = []
        for item_id in insight.get("evidence_item_ids") or []:
            item = items_by_id.get(str(item_id))
            if not item:
                continue
            anchor = html.escape(str(item.get("anchor_id") or f"item-{item_id}"), quote=True)
            title = html.escape(str(item.get("title") or item_id))
            refs.append(f'<a href="#{anchor}" style="color:#002fa7;text-decoration:none">{title}</a>')
        refs_html = " · ".join(refs)
        meta = " · ".join(
            part
            for part in (
                str(insight.get("topic_name") or ""),
                effect_labels.get(str(insight.get("effect") or ""), str(insight.get("effect") or "")),
                confidence_labels.get(
                    str(insight.get("confidence") or ""), str(insight.get("confidence") or "")
                ),
            )
            if part
        )
        rows.append(
            """
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" data-project-insight-ref-count="{ref_count}" style="border-top:1px solid #c8c8c2"><tr>
    <td width="30" valign="top" style="padding:10px 0;color:#002fa7;font:700 12px 'Microsoft YaHei','微软雅黑',Arial,sans-serif">{index:02d}</td>
    <td style="padding:10px 0;font-size:13px;line-height:1.5;color:#222">
      <div style="font-size:10px;letter-spacing:.4px;color:#777;font-weight:700;margin-bottom:3px">{meta}</div>
      <div style="font-weight:700;margin-bottom:4px">项目问题：{question}</div>
      <div>{insight}</div>
      <div style="margin-top:4px;color:#444"><b>下一步：</b>{next_action}</div>
      {refs}
    </td>
  </tr></table>""".format(
                ref_count=len(refs),
                index=index,
                meta=html.escape(meta),
                question=html.escape(str(insight.get("project_question") or "")),
                insight=html.escape(str(insight.get("insight") or "")),
                next_action=html.escape(str(insight.get("next_action") or "")),
                refs=(
                    f'<div style="margin-top:5px;font-size:11px;line-height:1.5;color:#777">证据解读：{refs_html}</div>'
                    if refs_html
                    else ""
                ),
            )
        )
    return (
        f'<tr><td class="pad-x" data-project-insight-count="{len(insights)}" '
        'style="padding:10px 28px 10px">'
        '<div style="font-size:11px;letter-spacing:1.4px;font-family:\'Microsoft YaHei\',\'微软雅黑\',Arial,sans-serif;color:#002fa7;font-weight:bold;margin-bottom:5px">项目影响</div>'
        + "".join(rows)
        + "</td></tr>\n"
    )


def _project_insight_stats(db, root: Path, run_id: str) -> dict[str, Any]:
    issue = db.fetchone("SELECT synthesis_path FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("synthesis_path"):
        return {
            "count": 0,
            "by_effect": {},
            "by_topic": {},
            "evidence_item_refs": 0,
            "note": "No issue synthesis is available for this run.",
        }
    synthesis = read_json(root / issue["synthesis_path"], {})
    insights = synthesis.get("project_insights") or []
    by_effect = Counter(str(item.get("effect") or "unknown") for item in insights if isinstance(item, dict))
    by_topic = Counter(str(item.get("topic_id") or "unknown") for item in insights if isinstance(item, dict))
    evidence_refs = sum(
        len(item.get("evidence_item_ids") or []) for item in insights if isinstance(item, dict)
    )
    return {
        "count": len(insights),
        "by_effect": dict(sorted(by_effect.items())),
        "by_topic": dict(sorted(by_topic.items())),
        "evidence_item_refs": evidence_refs,
        "note": "Project insights are evidence-bound project judgements, not source facts.",
    }


def install_project_insight_layer() -> None:
    """Add Project Insight to Issue Synthesis without patching publication or validation."""

    from . import demo as demo_module
    from . import telemetry
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_project_insight_installed", False):
        return

    original_create = TaskService.create

    def create(self, *args, **kwargs):
        values = list(args)
        task_type = values[1] if len(values) > 1 else kwargs.get("task_type")
        if task_type == "issue_synthesis":
            if len(values) > 3:
                values[3] = enrich_issue_synthesis_input(self.root, dict(values[3]))
            else:
                kwargs["input_data"] = enrich_issue_synthesis_input(
                    self.root, dict(kwargs.get("input_data") or {})
                )
            metadata = dict(kwargs.get("metadata") or {})
            metadata["project_insights_required"] = True
            metadata["project_insight_version"] = 1
            kwargs["metadata"] = metadata
        return original_create(self, *values, **kwargs)

    TaskService.create = create

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        errors.extend(project_insight_semantic_errors(task, input_data, data))
        return errors

    TaskService._semantic_errors = semantic_errors

    original_demo = demo_module._demo_output

    def demo_output(task_type: str, data: dict[str, Any]):
        output = original_demo(task_type, data)
        if task_type != "issue_synthesis" or not isinstance(output, dict):
            return output
        if "project_insights" in output:
            return output
        insights: list[dict[str, Any]] = []
        for context in data.get("project_contexts") or []:
            topic_id = str(context.get("topic_id") or "")
            question_list = context.get("current_questions") or []
            item = next(
                (
                    candidate
                    for candidate in data.get("items") or []
                    if str(candidate.get("topic_id") or "") == topic_id
                ),
                None,
            )
            if not item or not question_list:
                continue
            insights.append(
                {
                    "topic_id": topic_id,
                    "topic_name": str(context.get("topic_name") or topic_id),
                    "project_question": str(question_list[0]),
                    "effect": "narrows",
                    "confidence": "medium",
                    "insight": "本期证据进一步限定了该项目问题的适用边界，当前判断应优先以已核验的机制和条件为准。",
                    "next_action": "下一步应围绕该项目问题补充一项可复核的端到端实验，并记录对应基线与边界条件。",
                    "evidence_item_ids": [str(item.get("brief_item_id"))],
                }
            )
            break
        output["project_insights"] = insights
        return output

    demo_module._demo_output = demo_output

    original_run_stats = telemetry.run_stats

    def run_stats(db, root, run_id: str):
        payload = original_run_stats(db, root, run_id)
        payload["project_insights"] = _project_insight_stats(db, root, run_id)
        return payload

    telemetry.run_stats = run_stats
    Pipeline._project_insight_installed = True
