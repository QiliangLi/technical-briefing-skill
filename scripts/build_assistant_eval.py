#!/usr/bin/env python3
"""Build ``eval/assistant-questions.json`` for the group assistant.

Two question families:

- Hand-written colloquial questions with an explicit expected set. ``expected``
  lists title prefixes or document ids, any of which counts as a hit. An empty
  list marks a question the corpus cannot answer, where abstaining is correct.
- Template questions generated deterministically from published items, so the
  lexical layer is exercised on every topic without hand-picked examples.

Run from the repository root: ``.venv/bin/python3 scripts/build_assistant_eval.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TEMPLATE_COUNT = 24
TEMPLATE_STRIDE = 29

HAND_WRITTEN = [
    ("KV cache 放不下显存的时候，能不能分层卸载到内存和 SSD", [
        "三星在OCP 2026展示CXL内存池与SSD KV Cache分层卸载",
        "vLLM v0.26.0:KV 分层卸载获得对象存储层与副本感知",
        "HBF直接替换SSD做KV卸载反而更慢",
    ]),
    ("多智能体流水线里上下文总是超长，有什么压缩办法", ["FlexComp单模型支持任意比率的上下文压缩"]),
    ("agent 工具调用太慢，有没有针对语义的加速方案", [
        "SPECMEM：用持续更新的按用户工具调用记忆加速Agent解码",
        "弱模型起草工具轨迹、强模型单次预填充验证",
        "ToolMinimize中间件按必要性改写Agent工具调用参数",
    ]),
    ("光交换机在智算中心到底能不能落地", ["Flux按整负载结构最优调度光交换机", "Callosal以解耦内存与可编程交换机重建集群级内核页缓存"]),
    ("权重不更新，让 agent 自己改自己的 harness 靠谱吗", [
        "idea:idea_fe6623eb4e10956f7e86",
        "Evo2让权重与Harness协同进化以自改进编码Agent",
        "MESH-Harness在固定模型权重下自改进Agent Harness",
    ]),
    ("测试时扩展到底有没有用", ["ATEST按GPU实时负载调节LLM测试时扩展采样预算"]),
    ("HBF 直接换 SSD 做 KV 卸载效果怎么样", ["HBF直接替换SSD做KV卸载反而更慢"]),
    ("DPU 随路卸载有人做过吗", ["BlueField-4面向智能体AI工厂的随路卸载", "roadmap:dpu_inline"]),
    ("昨天说的那个 CXL 内存池的事有相关报道吗", [
        "三星在OCP 2026展示CXL内存池与SSD KV Cache分层卸载",
        "MemChannel：CXL内存池化的公平传输层",
        "Cairn用共享CXL内存池把Serverless LLM冷启动缩短4.",
        "HyMCache用CXL混合内存机架支撑多轮LLM的KV缓存服务",
    ]),
    ("谁做过 agent 记忆压缩", ["MASW:压缩draft记忆的长上下文投机解码", "FlexComp单模型支持任意比率的上下文压缩"]),
    ("今天午饭吃什么", []),
    ("这个报销流程怎么走", []),
    ("团队下周要讨论量子纠错路线，先看看资料", []),
    ("有讲智算中心液冷的吗", []),
]

TEMPLATES = (
    lambda first, second: f"有没有关于「{first}」的工作",
    lambda first, second: f"{first} 最近有什么进展",
    lambda first, second: f"求 {first} 和 {second} 相关的论文",
    lambda first, second: f"有人做过 {first} 吗，想参考一下",
)


def _load_index_documents(root: Path) -> list[dict]:
    index = json.loads((root / "archive" / "index.json").read_text(encoding="utf-8"))
    items = []
    for issue in sorted(index["issues"], key=lambda row: row["date"]):
        path = root / "archive" / "issues" / issue["date"] / "issue.json"
        if path.exists():
            items.extend(json.loads(path.read_text(encoding="utf-8")).get("items") or [])
    return items


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from briefing_skill.assistant.config import AssistantConfig
    from briefing_skill.assistant.retrieval import ensure_index

    index, _ = ensure_index(root, AssistantConfig.load(root))
    titles = {doc["id"]: doc["title"] for doc in index.docs}
    questions = []
    for number, (question, expected) in enumerate(HAND_WRITTEN, 1):
        resolved = []
        for target in expected:
            if target in index.by_id:
                resolved.append(target)
                continue
            matches = [doc_id for doc_id, title in titles.items() if title.startswith(target)]
            if len(matches) != 1:
                raise SystemExit(f"Expected title must match exactly one document: {target!r} -> {matches}")
            resolved.append(matches[0])
        questions.append({"id": f"hand-{number:02d}", "source": "hand-written", "question": question, "expected": resolved})

    candidates = [
        item
        for item in _load_index_documents(root)
        if len(item.get("keywords") or []) >= 2 and len(item.get("title") or "") <= 40
    ]
    picked = candidates[::TEMPLATE_STRIDE][:TEMPLATE_COUNT]
    for number, item in enumerate(picked, 1):
        first, second = item["keywords"][0], item["keywords"][1]
        questions.append(
            {
                "id": f"template-{number:02d}",
                "source": "template",
                "question": TEMPLATES[number % len(TEMPLATES)](first, second),
                "expected": [f"item:{item['brief_item_id']}"],
                # The question names a keyword, so any document titled with that
                # keyword is a relevant answer, not only the source item.
                "keywords": [first, second],
            }
        )

    output = root / "eval" / "assistant-questions.json"
    output.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(questions)} questions to {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
