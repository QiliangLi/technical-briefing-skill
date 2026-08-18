from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from briefing_skill.reader_projection import (
    CONTRACT_VERSION,
    _reader_contract_errors,
    _reader_projection_payload,
    _reader_sidecar_current,
    machine_item_hash,
    reader_item_path,
)
from briefing_skill.utils import write_json


def _machine_item() -> dict:
    return {
        "title": "ZhuLong用沙箱执行与API自探索攻克EDA脚本长尾",
        "type": "论文",
        "topic_name": "Agent语义加速",
        "published_at": "2026-08-08T00:00:00Z",
        "core_conclusion": "EDA脚本API长尾且文档缺失，静态生成无法验证副作用。ZhuLong通过沙箱执行验证API行为。",
        "mechanism": "系统提供检索、文档检查和沙箱执行工具，并把试出来的API约束保存为增强文档。",
        "result": "158项任务中Pass@1达到78.5%，API自探索使每项任务的工具调用减少22.1%。",
        "boundary": "实验集中在EDA脚本任务，交互GUI场景的效果更弱。",
        "project_relevance": "内部工具也存在文档不完整问题，可以验证把工具试错经验沉淀为增强文档是否减少重复调用。",
        "keywords": ["Agent", "API"],
        "sources": [{"publisher": "arXiv", "url": "https://arxiv.org/abs/2608.07925v1", "source_level": "A"}],
        "score": 76.2,
    }


def test_reader_schema_makes_takeaway_optional_and_body_variable() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "reader-item-writing.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    payload = {
        "results": [
            {
                "brief_item_id": "item-1",
                "title": "ZhuLong：让Agent自己试出文档里没有写的API用法",
                "lead": "内部工具的API文档经常不完整，ZhuLong尝试让Agent在沙箱里自己验证API行为。",
                "body": ["系统把试出来的参数约束和错误经验重新写入增强文档，后续任务可以直接复用这些经验。"],
                "used_fields": ["core_conclusion", "mechanism"],
            }
        ]
    }
    assert list(validator.iter_errors(payload)) == []
    assert "takeaway" not in schema["properties"]["results"]["items"]["required"]


def test_reader_contract_rejects_formulaic_slot_shaped_ai_prose() -> None:
    machine = _machine_item()
    bad = {
        "brief_item_id": "item-1",
        "title": "ZhuLong用沙箱执行与API自探索攻克EDA脚本长尾",
        "lead": "ZhuLong通过沙箱执行验证API行为，并将试错结果保存为增强文档。",
        "body": ["机制：三个工具形成检索、检查和执行闭环，随后把约束写入增强文档。"],
        "takeaway": "这给TPN卡提供了新的边界判断。",
        "used_fields": ["core_conclusion", "mechanism", "project_relevance"],
    }
    errors = _reader_contract_errors(bad, machine)
    assert any("Project+用/让/把/靠/按/以" in error for error in errors)
    assert any("机制/证据/边界/启发" in error for error in errors)
    assert any("internal topic-card shorthand" in error for error in errors)


def test_reader_contract_accepts_selective_natural_copy_and_forbids_new_numbers() -> None:
    machine = _machine_item()
    good = {
        "brief_item_id": "item-1",
        "title": "ZhuLong：让Agent自己试出未文档化API的正确用法",
        "lead": "很多Agent失败并不是模型不会写代码，而是工具API文档不完整，调用后也很难确认副作用。ZhuLong把API调用放进沙箱实际执行，再根据结果补齐工具知识。",
        "body": [
            "它给Agent提供检索、文档检查和沙箱执行三类工具。Agent可以改变参数反复试验，并把确认过的约束保存到增强文档，后面的任务不必从头踩坑。",
            "论文在158项任务上报告Pass@1为78.5%，加入API自探索后，每项任务的工具调用减少22.1%。",
        ],
        "takeaway": "这个思路可以迁移到内部文档不完整的工具链：先验证把执行反馈沉淀为工具知识，能否减少后续任务的重复调用。",
        "used_fields": ["core_conclusion", "mechanism", "result", "project_relevance"],
    }
    assert _reader_contract_errors(good, machine) == []

    invented = dict(good)
    invented["body"] = [*good["body"], "另外，系统吞吐提升了99%。"]
    errors = _reader_contract_errors(invented, machine)
    assert any("introduces numbers" in error and "99" in error for error in errors)


def test_reader_projection_is_run_scoped_even_when_facts_came_from_sqlite_cache(tmp_path: Path) -> None:
    run_id = "run-cache-hit"
    item_path = tmp_path / "workspace" / "runs" / run_id / "items" / "item-1.json"
    item = _machine_item()
    item["_provenance"] = {"fact_cache_hit": True, "cache_level": "L0"}
    write_json(item_path, item)

    class Pipeline:
        root = tmp_path

    selected = [
        {
            "id": "item-1",
            "json_path": str(item_path.relative_to(tmp_path)),
            "item_role": "core",
        }
    ]
    payload = _reader_projection_payload(Pipeline(), selected)

    assert payload["items"][0]["brief_item_id"] == "item-1"
    assert "_provenance" not in payload["items"][0]["machine_item"]
    assert payload["constraints"]["facts_may_come_from_local_sqlite_cache_but_reader_copy_must_be_current_run"] is True
    assert reader_item_path(tmp_path, run_id, "item-1") != reader_item_path(tmp_path, "another-run", "item-1")


def test_reader_sidecar_is_invalidated_when_fact_checked_machine_item_changes(tmp_path: Path) -> None:
    run_id = "run-reader"
    item_path = tmp_path / "workspace" / "runs" / run_id / "items" / "item-1.json"
    item = _machine_item()
    write_json(item_path, item)
    row = {"id": "item-1", "json_path": str(item_path.relative_to(tmp_path))}
    sidecar = {
        "brief_item_id": "item-1",
        "reader_version": CONTRACT_VERSION,
        "title": "ZhuLong：让Agent自己验证API行为",
        "lead": "ZhuLong把API调用放进沙箱执行，再把确认过的约束保存下来。",
        "body": ["这种方式让后续任务能够复用已经验证过的工具知识，而不是反复试错。"],
        "used_fields": ["core_conclusion", "mechanism"],
        "_provenance": {
            "run_id": run_id,
            "source_item_hash": machine_item_hash(item),
            "reader_contract_version": CONTRACT_VERSION,
            "cache_scope": "current_run_only",
        },
    }
    write_json(reader_item_path(tmp_path, run_id, "item-1"), sidecar)
    assert _reader_sidecar_current(tmp_path, run_id, row) is True

    changed = dict(item)
    changed["result"] = item["result"] + "补充事实检查后的修正。"
    write_json(item_path, changed)
    assert _reader_sidecar_current(tmp_path, run_id, row) is False


def test_email_template_prefers_reader_projection_but_keeps_legacy_fallback() -> None:
    template = (Path(__file__).resolve().parents[1] / "templates" / "email.html").read_text(encoding="utf-8")
    assert "{% if item.reader %}" in template
    assert "{{ item.reader.lead }}" in template
    assert "{% for paragraph in item.reader.body %}" in template
    assert "值得看的是" in template
    # Historical issues without a sidecar remain renderable.
    assert "{{ item.compact_mechanism }}" in template
