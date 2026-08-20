from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .tasks import COMPLETE_ENDING_RE, INCOMPLETE_ENDING_RE
from .utils import normalize_text, read_json, write_json


FIXED_BRIEFING_TITLE = "AI语义Fabric技术情报（公测版）"
HEADING_LABELS: dict[str, str] = {
    "mechanism": "怎么做的",
    "scheduling": "调度怎么判断",
    "cache": "缓存怎么处理",
    "code_relation": "关系怎么查询",
    "engineering": "实际改了什么",
    "result": "关键结果",
    "boundary": "需要注意",
    "contradiction": "为什么会这样",
    "implication": "可以怎么验证",
}
ALLOWED_HEADING_KEYS = frozenset(HEADING_LABELS)


def normalise_blocks(value: Any) -> list[dict[str, str | None]]:
    blocks: list[dict[str, str | None]] = []
    for row in value or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        raw_key = row.get("heading_key")
        key = str(raw_key).strip() if raw_key is not None else None
        blocks.append({"heading_key": key or None, "text": text})
    return blocks


def reader_for_legacy_template(reader: dict[str, Any]) -> dict[str, Any]:
    """Project v2 blocks into the old Jinja slots without changing the v2 contract.

    The template compatibility fields are render-local. The persisted sidecar keeps
    blocks as the editorial source of truth, while existing email/archival code can
    continue to consume lead/body until those presentation layers are retired.
    """

    blocks = normalise_blocks(reader.get("blocks"))
    if not blocks:
        return dict(reader)
    return {
        **reader,
        "lead": blocks[0]["text"],
        "body": [row["text"] for row in blocks[1:]],
        "takeaway": None,
        "display_blocks": [
            {
                **row,
                "heading": HEADING_LABELS.get(str(row.get("heading_key") or ""), ""),
            }
            for row in blocks
        ],
    }


def _reader_text(result: dict[str, Any]) -> str:
    parts = [str(result.get("title") or "")]
    parts.extend(str(row.get("text") or "") for row in normalise_blocks(result.get("blocks")))
    return "\n".join(parts)


def reader_contract_errors_v2(result: dict[str, Any], machine_item: dict[str, Any]) -> list[str]:
    """Keep factual constraints hard while leaving prose shape to the writer."""

    from . import reader_projection

    errors: list[str] = []
    title = str(result.get("title") or "").strip()
    blocks = normalise_blocks(result.get("blocks"))
    if not any("\u3400" <= ch <= "\u9fff" for ch in title):
        errors.append("reader title must contain Chinese reader-facing wording")
    for index, block in enumerate(blocks):
        text = str(block.get("text") or "")
        if text and not COMPLETE_ENDING_RE.search(text):
            errors.append(f"reader blocks[{index}].text must end with a complete sentence")
        key = block.get("heading_key")
        if key is not None and key not in ALLOWED_HEADING_KEYS:
            errors.append(f"reader blocks[{index}].heading_key is unknown: {key}")

    reader_text = _reader_text(result)
    if reader_projection.SLOT_LABEL_RE.search(reader_text):
        errors.append("reader copy must not reproduce the machine 机制/证据/边界/启发 slot layout")
    leaked = [term for term in reader_projection.INTERNAL_TAXONOMY_TERMS if term in reader_text]
    if leaked:
        errors.append("reader copy leaks internal topic-card shorthand: " + ", ".join(leaked))

    machine_text = "\n".join(
        str(machine_item.get(field) or "") for field in reader_projection.MACHINE_FIELDS
    )
    machine_numbers = set(reader_projection.NUMBER_RE.findall(machine_text))
    invented_numbers = sorted(
        set(reader_projection.NUMBER_RE.findall(reader_text)) - machine_numbers
    )
    if invented_numbers:
        errors.append(
            "reader copy introduces numbers absent from the fact-checked item: "
            + ", ".join(invented_numbers)
        )

    used_fields = [str(value) for value in result.get("used_fields") or []]
    if not used_fields:
        errors.append("reader item must declare at least one supporting machine field")
    unknown = sorted(set(used_fields) - reader_projection.READER_USED_FIELDS)
    if unknown:
        errors.append("reader item references unknown supporting fields: " + ", ".join(unknown))
    if not set(used_fields) & {"core_conclusion", "mechanism", "result"}:
        errors.append("reader item must be grounded in at least one substantive fact field")
    return errors


def issue_synthesis_validation_errors_v2(
    output: dict[str, Any], input_data: dict[str, Any]
) -> list[str]:
    """Validate traceability without forcing every judgement to be cross-item prose."""

    errors: list[str] = []
    input_items = input_data.get("items") or []
    items_by_id = {
        str(item.get("brief_item_id")): item
        for item in input_items
        if item.get("brief_item_id")
    }
    for index, judgement in enumerate(output.get("judgements") or []):
        if not isinstance(judgement, dict):
            continue
        evidence_ids = [str(value) for value in judgement.get("evidence_item_ids") or []]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"judgement {index} contains duplicate evidence_item_ids")
        unknown = sorted(set(evidence_ids) - set(items_by_id))
        if unknown:
            errors.append(
                f"judgement {index} references unknown evidence_item_ids: {', '.join(unknown)}"
            )
        title = " ".join(str(judgement.get("title") or "").split())
        body = " ".join(str(judgement.get("body") or "").split())
        if "对应：" in body or "对应:" in body:
            errors.append(f"judgement {index} body must not contain 对应：")
        if INCOMPLETE_ENDING_RE.search(title):
            errors.append(f"judgement {index} title has an incomplete ending")
        if INCOMPLETE_ENDING_RE.search(body) or not COMPLETE_ENDING_RE.search(body):
            errors.append(f"judgement {index} body must end with a complete sentence")
        for item in input_items:
            if normalize_text(body) in {
                normalize_text(item.get("title")),
                normalize_text(item.get("core_conclusion")),
            }:
                errors.append(
                    f"judgement {index} body must add a judgement rather than copy one item"
                )
                break
            if normalize_text(title) == normalize_text(item.get("title")):
                errors.append(f"judgement {index} title must not copy an item title")
                break
    return errors


def issue_writing_contract_errors_v2(data: dict[str, Any]) -> list[str]:
    """Keep only broad readability limits; do not compress prose into slogans."""

    from .reader_writing_contract import text_is_generic_boilerplate

    errors: list[str] = []
    for index, judgement in enumerate(data.get("judgements") or []):
        if not isinstance(judgement, dict):
            continue
        title = str(judgement.get("title") or "").strip()
        body = str(judgement.get("body") or "").strip()
        if len(title) > 64:
            errors.append(f"judgement {index} title must be <=64 characters")
        if len(body) > 400:
            errors.append(f"judgement {index} body must be <=400 characters")
        if text_is_generic_boilerplate(title) or text_is_generic_boilerplate(body):
            errors.append(f"judgement {index} contains generic reader-facing boilerplate")
    return errors


def _heading_tag(soup: BeautifulSoup, key: str):
    heading = soup.new_tag("div")
    heading["data-reader-section-heading"] = "1"
    heading["data-reader-section-role"] = key
    heading["style"] = (
        "font:700 11px/1.35 'Microsoft YaHei','微软雅黑',Arial,sans-serif;"
        "color:#5b6475;margin:9px 0 3px;letter-spacing:.1px"
    )
    heading.string = HEADING_LABELS[key]
    return heading


def decorate_reader_blocks(
    html: str,
    readers: dict[str, dict[str, Any]],
    *,
    issue_date: str = "",
) -> str:
    """Render model-selected semantic headings; never infer them from keywords."""

    soup = BeautifulSoup(html, "html.parser")
    for item_id, reader in readers.items():
        blocks = normalise_blocks(reader.get("blocks"))
        if not blocks:
            continue
        node = soup.find(id=f"item-{item_id}")
        if node is None:
            continue
        for old in node.select('[data-reader-section-heading="1"]'):
            old.decompose()
        direct_paragraphs = node.find_all("p", recursive=False)
        for block in blocks:
            text = str(block.get("text") or "")
            target = next(
                (tag for tag in direct_paragraphs if tag.get_text(" ", strip=True) == text),
                None,
            )
            if target is None:
                continue
            target["data-reader-block"] = "1"
            key = block.get("heading_key")
            if key in HEADING_LABELS:
                target.insert_before(_heading_tag(soup, str(key)))

    # The visible H1/date are already deterministic in the email template. Keep the
    # hidden preheader deterministic too, instead of depending on synthesis prose.
    for node in soup.find_all("div"):
        style = str(node.get("style") or "")
        if "display:none" in style and "max-height:0" in style:
            node.clear()
            node.append(f"{FIXED_BRIEFING_TITLE} · {issue_date}" if issue_date else FIXED_BRIEFING_TITLE)
            break
    return str(soup)


def install_reader_projection_v2() -> None:
    """Replace structural writing rules with a fact-constrained block contract."""

    from . import demo as demo_module
    from . import reader_projection
    from . import reader_writing_contract
    from . import tasks as tasks_module
    from .emailer import EmailService
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(Pipeline, "_reader_projection_v2_installed", False):
        return

    # Reader task payload: facts stay immutable, but the model owns ordering, length,
    # emphasis and heading-key selection.
    original_payload = reader_projection._reader_projection_payload

    def projection_payload(pipeline, selected):
        payload = original_payload(pipeline, selected)
        for row in payload.get("items") or []:
            row.pop("editorial_intent", None)
        payload["constraints"] = {
            "reader_copy_is_selective_not_lossless": True,
            "machine_fact_fields_remain_immutable": True,
            "model_owns_editorial_structure": True,
            "heading_key_is_optional_and_model_selected": True,
            "heading_text_is_rendered_by_code_not_generated": True,
            "facts_may_come_from_local_sqlite_cache_but_reader_copy_must_be_current_run": True,
        }
        return payload

    reader_projection._reader_projection_payload = projection_payload
    reader_projection._reader_contract_errors = reader_contract_errors_v2

    # Do not require another style skill. The reader task itself is the editorial pass.
    original_create = TaskService.create

    def create(
        self,
        run_id,
        task_type,
        entity_id,
        input_data,
        *,
        prompt,
        schema,
        priority=0,
        metadata=None,
        replace_existing=False,
    ):
        if task_type == reader_projection.TASK_TYPE:
            metadata = dict(metadata or {})
            metadata.pop("required_skills", None)
            metadata["skill_mode"] = "direct_fact_constrained_reader_v2"
            metadata["reader_contract_shape"] = "blocks"
        return original_create(
            self,
            run_id,
            task_type,
            entity_id,
            input_data,
            prompt=prompt,
            schema=schema,
            priority=priority,
            metadata=metadata,
            replace_existing=replace_existing,
        )

    TaskService.create = create

    # The base TaskService looks up this global at runtime; replacing it removes the
    # old requirement that a multi-item issue must contain cross-item judgements.
    tasks_module.issue_synthesis_validation_errors = issue_synthesis_validation_errors_v2
    # Reader-writing contract was installed earlier; its wrapper also resolves this
    # module global at runtime.
    reader_writing_contract.issue_writing_contract_errors = issue_writing_contract_errors_v2

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        if task.get("task_type") == reader_projection.TASK_TYPE:
            output = self.tasks.read_result(task)
            input_data = read_json(self.root / task["input_path"], {})
            inputs = {
                str(row.get("brief_item_id") or ""): row
                for row in input_data.get("items") or []
            }
            for result in output.get("results") or []:
                brief_item_id = str(result.get("brief_item_id") or "")
                source = inputs.get(brief_item_id)
                if not source:
                    raise KeyError(brief_item_id)
                blocks = normalise_blocks(result.get("blocks"))
                compat = reader_for_legacy_template({"blocks": blocks})
                sidecar = {
                    "brief_item_id": brief_item_id,
                    # Keep the existing numeric version for archive/interrupted-run
                    # compatibility; the schema shape is explicitly recorded below.
                    "reader_version": reader_projection.CONTRACT_VERSION,
                    "reader_shape": "blocks_v2",
                    "title": str(result.get("title") or "").strip(),
                    "blocks": blocks,
                    "lead": compat.get("lead", ""),
                    "body": compat.get("body", []),
                    "takeaway": None,
                    "used_fields": [str(value) for value in result.get("used_fields") or []],
                    "_provenance": {
                        "task_id": task["id"],
                        "run_id": self.run_id,
                        "source_item_hash": source["source_item_hash"],
                        "reader_contract_version": reader_projection.CONTRACT_VERSION,
                        "reader_contract_shape": "blocks_v2",
                        "cache_scope": "current_run_only",
                    },
                }
                write_json(
                    reader_projection.reader_item_path(self.root, self.run_id, brief_item_id),
                    sidecar,
                )
            return

        original_apply(self, task)
        if task.get("task_type") == "issue_synthesis":
            # `headline` is no longer generated. Preserve the legacy downstream field
            # as deterministic compatibility metadata until archive/site contracts are
            # versioned independently.
            issue = self.db.fetchone("SELECT synthesis_path FROM issues WHERE id=?", (task["entity_id"],))
            if issue and issue.get("synthesis_path"):
                path = self.root / issue["synthesis_path"]
                synthesis = read_json(path, {})
                synthesis["headline"] = FIXED_BRIEFING_TITLE
                write_json(path, synthesis)

    Pipeline._apply_task = apply_task

    # Render v2 blocks through the existing email template, then add only the
    # model-selected headings. Old v1 sidecars remain renderable.
    original_topic_groups = EmailService._topic_groups

    def topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        groups = original_topic_groups(self, data)
        for group in groups:
            for item in [*(group.get("items") or []), *(group.get("observations") or [])]:
                reader = item.get("reader")
                if isinstance(reader, dict) and reader.get("blocks"):
                    item["reader"] = reader_for_legacy_template(reader)
        return groups

    EmailService._topic_groups = topic_groups

    original_build = EmailService.build

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL"):
        path = original_build(self, run_id, status_after=status_after)
        if not path.is_file():
            return path
        issue_row = self.db.fetchone(
            "SELECT issue_json_path FROM issues WHERE run_id=?", (run_id,)
        ) or {}
        issue = (
            read_json(self.root / issue_row.get("issue_json_path", ""), {})
            if issue_row.get("issue_json_path")
            else {}
        )
        readers: dict[str, dict[str, Any]] = {}
        legacy_readers: dict[str, dict[str, Any]] = {}
        machine_items: dict[str, dict[str, Any]] = {}
        for item in [*(issue.get("core_items") or []), *(issue.get("observations") or [])]:
            item_id = str(item.get("brief_item_id") or "")
            if not item_id:
                continue
            machine_items[item_id] = item
            sidecar = read_json(reader_projection.reader_item_path(self.root, run_id, item_id), {})
            if sidecar.get("blocks"):
                readers[item_id] = sidecar
            elif sidecar:
                legacy_readers[item_id] = {**sidecar, "role": item.get("item_role") or "core"}
        html = path.read_text(encoding="utf-8")
        if legacy_readers:
            from .editorial_intent import decorate_reader_cards

            html = decorate_reader_cards(html, machine_items, legacy_readers)
        html = decorate_reader_blocks(
            html,
            readers,
            issue_date=str(issue.get("date_to") or ""),
        )
        path.write_text(html, encoding="utf-8")
        return path

    EmailService.build = build

    original_demo_output = demo_module._demo_output

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type != reader_projection.TASK_TYPE:
            return original_demo_output(task_type, data)
        results = []
        for row in data.get("items") or []:
            item = row.get("machine_item") or {}
            first = str(
                item.get("core_conclusion")
                or item.get("mechanism")
                or "离线样例用于验证读者层可以独立组织事实。"
            ).strip()
            if first and not COMPLETE_ENDING_RE.search(first):
                first = first.rstrip("，,：:；;") + "。"
            blocks = [{"heading_key": None, "text": first}]
            mechanism = str(item.get("mechanism") or "").strip()
            if mechanism and normalize_text(mechanism) != normalize_text(first):
                if not COMPLETE_ENDING_RE.search(mechanism):
                    mechanism = mechanism.rstrip("，,：:；;") + "。"
                blocks.append({"heading_key": "mechanism", "text": mechanism})
            used = [
                field
                for field in ("core_conclusion", "mechanism", "result")
                if str(item.get(field) or "").strip()
            ] or ["title"]
            results.append(
                {
                    "brief_item_id": row["brief_item_id"],
                    "title": str(item.get("title") or "技术进展"),
                    "blocks": blocks[:3],
                    "used_fields": used,
                }
            )
        return {"results": results}

    demo_module._demo_output = demo_output
    Pipeline._reader_projection_v2_installed = True
