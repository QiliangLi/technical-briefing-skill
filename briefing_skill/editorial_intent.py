from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


CONTRADICTION_TERMS = (
    "反而", "却", "悖论", "反直觉", "更少", "去掉", "取消", "不增反降", "不需要",
)
# Engineering is intentionally narrow. Generic words such as “实现” occur in
# almost every systems paper and used to collapse unrelated cards into the same
# “实际改了什么” heading. These terms indicate an actual release/deployment or
# interface/runtime engineering event rather than merely describing an algorithm.
ENGINEERING_TERMS = (
    "release", "版本发布", "发布版本", "正式发布", "候选发布", "开源", "上线",
    "production deployment", "生产部署", "接口新增", "新增接口", "runtime更新", "运行时更新",
)
SCHEDULING_TERMS = ("调度", "scheduler", "路由", "routing", "队列", "排队")
CACHE_TERMS = ("kv", "cache", "缓存", "前缀")
BOUNDARY_TERMS = ("但", "仅", "只", "没有", "未", "缺少", "依赖", "局限")
TITLE_FAMILY_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9+._-]{1,28}(?:用|让|把|靠|按|以|通过|借|将|去掉|取消)[^：:]{4,}$"
)


def _text(item: dict[str, Any], *fields: str) -> str:
    return " ".join(str(item.get(field) or "") for field in fields).lower()


def _stable_variant(value: str, options: tuple[str, ...]) -> str:
    if not options:
        return "plain"
    score = sum((index + 1) * ord(ch) for index, ch in enumerate(str(value or "")))
    return options[score % len(options)]


def _is_engineering_event(machine_item: dict[str, Any]) -> bool:
    """Recognize actual release/deployment events without matching generic paper prose."""

    item_type = _text(machine_item, "type")
    title_and_conclusion = _text(machine_item, "title", "core_conclusion")
    if any(token in item_type for token in ("release", "版本", "工程", "产品")):
        return True
    return any(term in title_and_conclusion for term in ENGINEERING_TERMS)


def derive_editorial_intent(
    machine_item: dict[str, Any],
    *,
    item_role: str = "core",
    brief_item_id: str = "",
) -> dict[str, Any]:
    """Choose what the reader card should emphasize without asking another model.

    This is an editorial plan, not a fact model.  It deliberately decides what to
    foreground and what not to force into the visible card.
    """

    conclusion = _text(machine_item, "title", "core_conclusion")
    mechanism = _text(machine_item, "mechanism")
    result = _text(machine_item, "result")
    boundary = _text(machine_item, "boundary")
    all_text = " ".join((conclusion, mechanism, result, boundary))

    if any(term in all_text for term in CONTRADICTION_TERMS):
        primary = "contradiction"
    elif _is_engineering_event(machine_item):
        primary = "engineering"
    elif mechanism:
        primary = "mechanism"
    elif result:
        primary = "result"
    else:
        primary = "explanation"

    if primary != "result" and result:
        secondary = "result"
    elif boundary:
        secondary = "boundary"
    else:
        secondary = None

    # When the first paragraph already explains a counter-intuitive result, a
    # limitation is usually more useful than repeating another result paragraph.
    if primary == "contradiction" and boundary:
        secondary = "boundary"

    title_style = (
        "question"
        if primary == "contradiction"
        else _stable_variant(brief_item_id or str(machine_item.get("title") or ""), ("plain", "finding", "project_colon"))
    )
    depth = "deep" if str(item_role) == "core" else "normal"
    section_plan = [primary]
    if depth == "deep" and secondary and secondary != primary:
        section_plan.append(secondary)

    return {
        "reader_depth": depth,
        "primary_focus": primary,
        "secondary_focus": secondary,
        "section_plan": section_plan[:2],
        "title_style": title_style,
        "allow_takeaway": bool(str(machine_item.get("project_relevance") or "").strip()),
    }


def section_heading(role: str, machine_item: dict[str, Any], paragraph: str = "") -> str:
    """Map semantic section roles to a small, non-generative heading vocabulary."""

    text = f"{_text(machine_item, 'mechanism', 'result', 'boundary')} {str(paragraph or '').lower()}"
    if role == "contradiction":
        return "为什么会这样"
    if role == "engineering":
        return "实际改了什么"
    if role == "result":
        return "关键结果"
    if role == "boundary":
        return "实验边界"
    if role == "implication":
        return "值得试什么"
    if role == "mechanism":
        if any(term in text for term in SCHEDULING_TERMS):
            return "调度怎么判断"
        if any(term in text for term in CACHE_TERMS):
            return "缓存怎么处理"
        return "怎么做的"
    return "具体怎么回事"


def reader_sections(
    reader: dict[str, Any],
    machine_item: dict[str, Any],
    *,
    item_role: str = "core",
    brief_item_id: str = "",
) -> list[dict[str, str]]:
    paragraphs = [str(value or "").strip() for value in reader.get("body") or [] if str(value or "").strip()]
    if not paragraphs:
        return []
    intent = derive_editorial_intent(
        machine_item,
        item_role=item_role,
        brief_item_id=brief_item_id,
    )
    roles = list(intent.get("section_plan") or [])
    sections: list[dict[str, str]] = []
    for index, paragraph in enumerate(paragraphs[:2]):
        role = roles[index] if index < len(roles) else ("result" if index else "mechanism")
        sections.append(
            {
                "role": role,
                "heading": section_heading(role, machine_item, paragraph),
                "text": paragraph,
            }
        )
    return sections


def takeaway_label(reader: dict[str, Any], machine_item: dict[str, Any]) -> str:
    text = str(reader.get("takeaway") or "").strip()
    if not text:
        return ""
    if any(term in text for term in BOUNDARY_TERMS):
        return "需要注意"
    if str(machine_item.get("project_relevance") or "").strip():
        return "值得试什么"
    return "补充说明"


def _direct_candidates(node: Tag) -> list[Tag]:
    return [child for child in node.find_all(["p", "div"], recursive=False)]


def decorate_reader_cards(
    html: str,
    machine_items: dict[str, dict[str, Any]],
    readers: dict[str, dict[str, Any]],
) -> str:
    """Add scan-friendly dynamic headings without changing reader prose or links."""

    soup = BeautifulSoup(html, "html.parser")
    for item_id, reader in readers.items():
        machine = machine_items.get(str(item_id)) or {}
        node = soup.find(id=f"item-{item_id}")
        if node is None:
            continue
        # Idempotency for rebuilds.
        for old in node.select('[data-reader-section-heading="1"]'):
            old.decompose()
        role = str(reader.get("role") or machine.get("item_role") or "core")
        sections = reader_sections(
            reader,
            machine,
            item_role=role,
            brief_item_id=str(item_id),
        )
        direct = _direct_candidates(node)
        for section in sections:
            target = next(
                (
                    tag for tag in direct
                    if tag.get_text(" ", strip=True) == section["text"]
                ),
                None,
            )
            if target is None:
                continue
            heading = soup.new_tag("div")
            heading["data-reader-section-heading"] = "1"
            heading["data-reader-section-role"] = section["role"]
            heading["style"] = (
                "font:700 11px/1.35 'Microsoft YaHei','微软雅黑',Arial,sans-serif;"
                "color:#5b6475;margin:9px 0 3px;letter-spacing:.1px"
            )
            heading.string = section["heading"]
            target.insert_before(heading)

        takeaway = str(reader.get("takeaway") or "").strip()
        if takeaway:
            target = next(
                (tag for tag in _direct_candidates(node) if tag.get_text(" ", strip=True).endswith(takeaway)),
                None,
            )
            if target is not None:
                label = takeaway_label(reader, machine)
                bold = target.find("b", recursive=False)
                if bold is not None:
                    bold.string = label
    return str(soup)


def reader_projection_repetition_errors(data: dict[str, Any]) -> list[str]:
    """Reject issue-wide title rhythm collapse, not individual vocabulary choices."""

    results = [row for row in data.get("results") or [] if isinstance(row, dict)]
    if len(results) < 4:
        return []
    formulaic = [row for row in results if TITLE_FAMILY_RE.match(str(row.get("title") or "").strip())]
    if len(formulaic) / len(results) >= 0.45:
        return [
            "reader_projection title rhythm is too uniform: >=45% use the same Project+verb family"
        ]
    return []


def install_editorial_intent() -> None:
    """Install deterministic editorial planning after Reader Projection is present."""

    from . import reader_projection
    from .emailer import EmailService
    from .pipeline import Pipeline
    from .tasks import TaskService
    from .utils import read_json

    if getattr(Pipeline, "_editorial_intent_installed", False):
        return

    original_payload = reader_projection._reader_projection_payload

    def projection_payload(pipeline, selected):
        payload = original_payload(pipeline, selected)
        for row in payload.get("items") or []:
            row["editorial_intent"] = derive_editorial_intent(
                row.get("machine_item") or {},
                item_role=str(row.get("item_role") or "core"),
                brief_item_id=str(row.get("brief_item_id") or ""),
            )
        payload.setdefault("constraints", {})["editorial_intent_is_binding"] = True
        payload["constraints"]["body_paragraphs_follow_section_plan_order"] = True
        return payload

    reader_projection._reader_projection_payload = projection_payload

    original_semantic_errors = TaskService._semantic_errors

    def semantic_errors(self, task, input_data, data):
        errors = list(original_semantic_errors(self, task, input_data, data))
        if task.get("task_type") == reader_projection.TASK_TYPE:
            errors.extend(reader_projection_repetition_errors(data))
        return list(dict.fromkeys(errors))

    TaskService._semantic_errors = semantic_errors

    original_build = EmailService.build

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL"):
        path = original_build(self, run_id, status_after=status_after)
        issue_row = self.db.fetchone("SELECT issue_json_path FROM issues WHERE run_id=?", (run_id,)) or {}
        issue = read_json(self.root / issue_row.get("issue_json_path", ""), {}) if issue_row.get("issue_json_path") else {}
        machine_items = {
            str(item.get("brief_item_id") or ""): item
            for item in [*(issue.get("core_items") or []), *(issue.get("observations") or [])]
            if item.get("brief_item_id")
        }
        readers: dict[str, dict[str, Any]] = {}
        for item_id in machine_items:
            sidecar = read_json(reader_projection.reader_item_path(self.root, run_id, item_id), {})
            if sidecar:
                readers[item_id] = {**sidecar, "role": machine_items[item_id].get("item_role") or "core"}
        if readers and path.is_file():
            path.write_text(
                decorate_reader_cards(path.read_text(encoding="utf-8"), machine_items, readers),
                encoding="utf-8",
            )
        return path

    EmailService.build = build
    Pipeline._editorial_intent_installed = True
