from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from .db import Database
from .tasks import TASK_BINDING_KEY, TaskService
from .utils import read_json, write_json


def complete_pending_demo_tasks(root: Path, db: Database, run_id: str) -> int:
    run_dir = root / "workspace" / "runs" / run_id
    tasks = TaskService(db, root, run_dir)
    count = 0
    for task in tasks.list(run_id, "PENDING"):
        input_data = read_json(root / task["input_path"])
        output = _demo_output(task["task_type"], input_data)
        if output is None:
            continue
        write_json(
            root / task["output_path"],
            {TASK_BINDING_KEY: input_data[TASK_BINDING_KEY], **output},
        )
        count += 1
    return count


def _demo_output(task_type: str, data: dict):
    if task_type == "relevance_review":
        return {"relevant": True, "score": 88, "reason": "与指定技术方向直接相关，并包含可验证机制。", "reject_reason": None, "fulltext_required": True, "matched_signals": ["机制", "端到端加速"]}
    if task_type == "fact_extraction":
        title = data["source"]["title"]
        agent = "CodeGraph" in title or "repository" in title.lower()
        return {
            "title": title,
            "event_hint": "CodeGraph代码Agent仓库索引" if agent else "KVCache感知网络调度",
            "problem": "Agent反复搜索代码导致工具调用和上下文开销增加。" if agent else "Prefill和Decode流量竞争使KVCache传输和请求排队增加。",
            "mechanism": "预先构建符号、文件和调用关系图，先通过图查询定位代码，再调用Read/Grep读取必要文件。" if agent else "跟踪KVCache位置和Decode紧迫度，并将这些状态用于带宽与传输队列调度。",
            "evidence": [
                {"claim": "离线示例只验证流程，不代表真实论文性能数据", "value": None, "baseline": None, "condition": "offline fixture", "source_locator": "fixture summary"},
                {"claim": "夹具包含可定位的机制说明", "value": None, "baseline": None, "condition": "offline fixture", "source_locator": "fixture mechanism"},
                {"claim": "夹具包含明确的适用边界", "value": None, "baseline": None, "condition": "offline fixture", "source_locator": "fixture limitations"},
            ],
            "evaluation_context": "离线fixture，用于验证Skill工作流和数据结构。",
            "limitations": "没有真实实验数据，不应作为正式简报发送。",
            "project_relevance": "可用于验证信息抽取、事件聚类和卡片渲染链路。",
            "primary_source_resolved": True,
            "quality_score": 76,
            "source_notes": ["DEMO ONLY"]
        }
    if task_type == "item_writing":
        facts = data["facts"][0]
        agent = "CodeGraph" in facts["event_hint"]
        today = datetime.now(timezone.utc).date().isoformat()
        return {
            "title": "CodeGraph先定位再读取，减少代码Agent重复探索" if agent else "KVCache状态进入网络调度，缩短推理通信关键路径",
            "type": "流程演示",
            "topic_name": data["topic"]["name"],
            "direction_name": data["direction"]["name"],
            "published_at": today,
            "importance": "值得关注",
            "core_conclusion": facts["problem"] + facts["mechanism"] + "该样例重点验证从来源到简报条目的信息链路是否完整。",
            "mechanism": facts["mechanism"] + "任务按候选逐篇处理，并把原文事实压缩成结构化字段后再进入选刊。",
            "result": "当前为离线流程样例，没有可用于技术判断的真实性能数字。它只证明采集、逐篇抽取、稳定去重、事实检查和邮件生成链路能够顺序完成。",
            "boundary": facts["limitations"] + "样例不得用于推断真实系统的性能收益或生产可用性。",
            "project_relevance": facts["project_relevance"] + "正式运行时仍需替换为近期一手来源，并逐项核验数据、基线和适用条件。",
            "keywords": ["CodeGraph", "Agent", "代码检索"] if agent else ["KVCache", "网络调度", "Prefill/Decode"],
            "sources": [{"publisher": "Offline Fixture", "url": data["sources"][0]["url"], "source_level": "A", "primary": True, "published_at": today}],
            "discovered_via": None,
            "incremental_update": False,
            "incremental_change": None,
            "score": float(data["score"])
        }
    if task_type == "fact_check":
        return {"pass": True, "issues": [], "corrected_item": None}
    if task_type == "issue_synthesis":
        ids = [item["brief_item_id"] for item in data["items"]]
        return {"headline": "本期离线样例验证了Agent加速与KVCache网络调度可以进入同一条可追溯工作流。", "judgements": [{"title": "状态要进入执行链", "body": "Agent检索状态和KVCache位置只有进入工具选择、网络带宽与队列调度，才可能转化为可验证的系统收益。", "evidence_item_ids": ids}], "topic_names": list(dict.fromkeys(item["topic_name"] for item in data["items"])), "watch_next": ["替换fixture为真实一手来源", "补充真实原文数据与图表"]}
    if task_type == "visual_routing":
        agent = "CodeGraph" in data["item"]["title"]
        return {"visual_mode": "material_mechanism", "visual_purpose": "解释先索引后读取的Agent代码探索路径" if agent else "解释KVCache状态如何进入网络调度", "structure": "before_after" if agent else "pipeline", "labels": ["反复搜索", "代码索引", "直接定位"] if agent else ["推理状态", "缓存位置", "带宽调度", "Token输出"], "aspect_ratio": "1.9:1", "accent": "IKB Blue", "factual_constraints": ["不虚构性能数字", "只表达fixture中的机制"], "persona_mode": "observer", "persona_action": "检查证据链", "asset_path": None, "source_asset_url": None, "reason": "当前没有真实源图，机制图能帮助验证视觉流程。"}
    if task_type == "illustration_brief":
        return {"concept_name": data["brief_item"]["title"], "status": "waiting_for_image_generation", "prompt": "Guizang材质化技术机制图，1.9:1横图，IKB蓝，严格使用visual plan中的短标签，不添加性能数字，保留安全边距。", "labels": data["visual_plan"]["labels"], "generated_asset_path": None, "qa_notes": ["离线演示未调用图像生成，渲染时使用机制占位图。"]}
    return None
