#!/usr/bin/env python3
"""One-time, deterministic review ledger for the 2026-09-03 Candidate design.

The curated groups are the human-reviewed shortlist in the accepted design. The
script resolves each group against the published archive, persists five promoted
Ideas and one deferred Candidate, and records a reasoned result for every archive
item. It never reads full text, Reader prose, or unpublished candidates.
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.idea_discovery import (  # noqa: E402
    _candidate_semantic_errors,
    candidate_to_idea,
    commit_candidate_updates,
    stable_candidate_id,
)
from briefing_skill.knowledge_materialization import (  # noqa: E402
    EVIDENCE_SCOPE,
    FRONTIER_TOPIC_ID,
    SCHEMA_VERSION,
    PublishedArchive,
    _validate_schema,
    idea_semantic_errors,
)
from briefing_skill.utils import read_json, source_identity_key, stable_hash  # noqa: E402


GROUPS: list[dict[str, Any]] = [
    {
        "identity": {"problem_key": "cross_model_kv_recomputation", "mechanism_key": "latent_kv_migration_refresh", "target_key": "heterogeneous_model_serving"},
        "idea_type": "research_hypothesis",
        "title": "跨模型 KV 迁移需要把映射误差与刷新频率一起调度",
        "problem": "异构模型协作时无法直接复用 KV 状态，重复 Prefill 会抵消多模型路由收益。",
        "hypothesis": "若把潜空间 KV 映射误差、迁移成本与周期性刷新联合建模，可找到优于重复 Prefill 的可用边界。",
        "mechanism": "为模型对学习或构造 KV 潜空间映射，在误差或会话漂移超过阈值时局部刷新，并由调度器选择迁移或重算。",
        "target": "异构模型级联、路由和协作推理服务",
        "expected_effect": "在质量约束内降低重复 Prefill 时间与跨模型状态传输成本，并明确失效阈值。",
        "evidence_ids": ["aea2c5f288fa3cb1f1c150fd", "3a70069639846632bc128f55", "aec0bff49869dc80b9a03c53", "2c397aec024504c233edf92f"],
        "unknowns": ["不同架构与层数差异下映射误差何时不可接受", "刷新频率是否会吞掉迁移节省", "长上下文与多轮漂移的质量边界"],
        "validation": {"mode": "benchmark", "minimal_model": "构造两组异构模型对，在相同提示与质量阈值下比较重算、一次映射和阈值刷新。", "inputs": ["多轮长上下文请求", "至少两组异构模型对"], "baselines": ["每次完整 Prefill", "无刷新 KV 映射"], "metrics": ["首 token 延迟", "迁移字节", "输出质量偏差", "刷新次数"], "support_criteria": ["质量偏差受控且端到端延迟稳定下降"], "reject_criteria": ["刷新或映射成本在主要负载上不低于完整 Prefill"], "limitations": ["公开结果尚不足以覆盖所有模型架构"]},
        "accept": True,
    },
    {
        "identity": {"problem_key": "generated_kernel_deployment_gap", "mechanism_key": "hardware_aware_closed_loop_optimization", "target_key": "gpu_and_npu_kernels"},
        "idea_type": "solution_concept",
        "title": "把硬件知识与真实部署验收接成内核优化闭环",
        "problem": "自动生成的加速器内核常在语法或离线基准上通过，却无法稳定达到真实设备和部署环境的性能要求。",
        "hypothesis": "将设备约束检索、候选生成、编译运行和部署内验收闭环，可提高可用内核比例并减少纸面加速。",
        "mechanism": "按目标 GPU 或 NPU 注入硬件知识，生成多个候选，以真实编译器、设备计数器和服务负载反馈迭代。",
        "target": "GPU 与 NPU 上的模型算子和稀疏内核",
        "expected_effect": "提高编译成功率和部署内加速命中率，同时控制回归与搜索成本。",
        "evidence_ids": ["f682b45f4e2f6eed337331d3", "a58adb4322d178c37bfe538a", "56669f597b366c481995590f"],
        "unknowns": ["跨设备硬件知识能否复用", "真实服务验收所需的最小流量和计数器集合"],
        "validation": {"mode": "prototype", "minimal_model": "在一组 GPU 与 NPU 算子上运行知识增强生成、编译、设备基准和服务回放闭环。", "inputs": ["代表性算子集", "目标设备约束", "真实请求回放"], "baselines": ["无硬件知识的单轮生成", "仅离线微基准选择"], "metrics": ["编译成功率", "部署内加速命中率", "性能回归率", "搜索成本"], "support_criteria": ["成功率与部署收益同时提升且回归可控"], "reject_criteria": ["离线收益无法在服务回放中复现"], "limitations": ["首版只覆盖少量设备和算子类别"]},
        "accept": True,
    },
    {
        "identity": {"problem_key": "kv_capacity_beyond_local_dram", "mechanism_key": "cxl_hybrid_memory_service", "target_key": "multi_turn_kv_cache"},
        "idea_type": "solution_concept",
        "title": "用 CXL 混合内存构建可控的多轮 KV 容量层",
        "problem": "多轮会话 KV 容量超过本地 HBM 和 DRAM 后，简单外溢会受到带宽争用、公平性和尾延迟限制。",
        "hypothesis": "将 CXL 内存池、热度分层和公平传输联合成服务层，可在尾延迟边界内扩大 KV 复用容量。",
        "mechanism": "按会话热度在本地与 CXL 池间放置 KV，并用公平传输调度限制租户争用和回迁突发。",
        "target": "多租户多轮 LLM 推理的 KV 缓存服务",
        "expected_effect": "提高可复用 KV 容量和命中率，同时限制 p99 延迟与跨租户干扰。",
        "evidence_ids": ["aad3ac6d44c9280e0f9b3ae3", "d05f67d474b98cf028645985", "ab820b3c0433c2eae0500436"],
        "unknowns": ["不同 CXL 拓扑下的带宽拐点", "同源 HyMCache 复报不能视为独立确认", "公平调度对总体吞吐的代价"],
        "validation": {"mode": "simulation", "minimal_model": "回放多租户会话轨迹，模拟本地内存与 CXL 池容量、链路和公平调度。", "inputs": ["会话 KV 生命周期轨迹", "CXL 延迟带宽参数", "租户权重"], "baselines": ["本地容量内 LRU", "无公平控制的 CXL 外溢"], "metrics": ["KV 命中率", "p99 延迟", "链路利用率", "租户 slowdown"], "support_criteria": ["容量收益显著且 p99 与公平性满足预算"], "reject_criteria": ["链路争用使主要负载尾延迟劣于重算"], "limitations": ["仿真不能替代真实 CXL 设备验证"]},
        "accept": True,
    },
    {
        "identity": {"problem_key": "coding_agent_repository_search_cost", "mechanism_key": "structured_repository_retrieval_service", "target_key": "coding_agent_context"},
        "idea_type": "solution_concept",
        "title": "为 Coding Agent 提供结构化、分阶段的仓库检索服务",
        "problem": "Coding Agent 在仓库中反复探索，既消耗上下文和工具调用，也容易遗漏跨文件结构证据。",
        "hypothesis": "代码对象索引、多跳结构查询与分阶段模型分工可能降低搜索成本，但需先厘清它与现有工具接口分层 Idea 的 lineage。",
        "mechanism": "把代码对象去重索引、关系多跳查询和低成本探索阶段封装为检索服务，再向执行阶段交付受控上下文。",
        "target": "大型仓库中的 Coding Agent 上下文构建",
        "expected_effect": "减少重复搜索、工具调用与 token 消耗，同时维持任务成功率和关键证据召回。",
        "evidence_ids": ["fbd868593a77683d93084640", "2df30f2aad79d219cb0c0edb", "c37bbb0e061ba80f732084f3", "da847a709df41e3cd1c15eb4"],
        "unknowns": ["是否只是现有 capability-matched tool interface Idea 的派生实现", "跨语言仓库的结构索引成本", "低成本探索模型的错误如何隔离"],
        "validation": {"mode": "benchmark", "minimal_model": "在同一 Coding Agent 和任务集上比较文本搜索、结构索引、多跳查询与分阶段探索。", "inputs": ["多语言仓库", "修复与理解任务集"], "baselines": ["纯文本搜索", "统一模型直接探索"], "metrics": ["任务成功率", "工具调用数", "token 消耗", "关键证据召回率"], "support_criteria": ["成本下降且成功率与证据召回不退化"], "reject_criteria": ["索引维护成本或错误传播抵消搜索收益"], "limitations": ["需人工确认与现有正式 Idea 的身份边界"]},
        "accept": False,
        "related_idea_ids": ["idea_6e6886675f61e74dd472"],
    },
    {
        "identity": {"problem_key": "distributed_agent_memory_conflict", "mechanism_key": "versioned_auditable_memory_merge", "target_key": "shared_agent_state"},
        "idea_type": "solution_concept",
        "title": "用版本化冲突保留实现可审计的分布式 Agent 记忆合并",
        "problem": "多个 Agent 并发写入共享记忆时，覆盖式同步会丢失冲突来源，也难以按查询场景重建一致视图。",
        "hypothesis": "无协调者合并、版本化冲突保留与查询条件化视图结合，可提高共享状态的可审计性和任务连续性。",
        "mechanism": "将记忆写入建模为带版本与来源的操作，合并时保留冲突分支，并在读取时按查询和治理策略生成视图。",
        "target": "跨节点、跨会话的多 Agent 共享状态",
        "expected_effect": "减少静默覆盖和状态分叉，支持冲突追踪、回放和面向任务的稳定读取。",
        "evidence_ids": ["9c3c1121c0f97dba985dc9cc", "925d9e03c6b9914c790dadf7", "3f5542f2d0953600ae2066fb"],
        "unknowns": ["冲突保留的存储放大", "查询条件化视图是否会隐藏关键矛盾", "治理策略的收敛条件"],
        "validation": {"mode": "prototype", "minimal_model": "实现带来源与版本的共享记忆日志，注入并发更新、离线重连和冲突查询。", "inputs": ["多 Agent 并发写入轨迹", "冲突与重连故障注入"], "baselines": ["最后写入获胜", "集中式协调写入"], "metrics": ["丢失更新数", "冲突可追踪率", "读取一致性", "存储与延迟开销"], "support_criteria": ["无静默丢失且审计收益高于额外开销"], "reject_criteria": ["冲突分支持续膨胀或读取无法稳定收敛"], "limitations": ["原型不证明大规模网络分区下的生产可用性"]},
        "accept": True,
    },
    {
        "identity": {"problem_key": "unsafe_repeated_tool_calls", "mechanism_key": "pre_call_state_resource_supervision", "target_key": "agent_tool_execution"},
        "idea_type": "solution_concept",
        "title": "在工具调用前加入状态与资源监督层",
        "problem": "长链路 Agent 容易在状态漂移、容量不足或失败重试中重复调用工具并越过安全边界。",
        "hypothesis": "在分派前检查意图、状态和资源契约，并提供明确中止原语，可减少重复失败与越界调用。",
        "mechanism": "在工具路由前维护有界状态，执行意图一致性、容量和权限检查，对重复失败触发降级或中止。",
        "target": "具有多轮工具调用的自主 Agent 执行器",
        "expected_effect": "降低重复调用、资源超限和操作性幻觉，同时保持可解释的中止与恢复路径。",
        "evidence_ids": ["4aacfff6b9b7808c286ad598", "f5a9fafbe8d1f875de954234"],
        "unknowns": ["监督层误拒绝正常调用的比例", "状态预算与任务成功率的关系", "中止后恢复协议"],
        "validation": {"mode": "prototype", "minimal_model": "在带故障注入的工具任务上比较无监督、仅权限检查和状态资源联合监督。", "inputs": ["多轮工具任务", "容量与权限约束", "重复失败故障注入"], "baselines": ["无调用前监督", "仅静态权限检查"], "metrics": ["重复失败调用数", "越界调用数", "任务成功率", "误拒绝率"], "support_criteria": ["显著减少重复和越界且成功率下降在预算内"], "reject_criteria": ["误拒绝或监督延迟抵消安全收益"], "limitations": ["任务集无法覆盖所有真实工具副作用"]},
        "accept": True,
    },
]


def _candidate(spec: dict[str, Any], evidence: dict[str, dict[str, Any]], accepted_issue: str) -> dict[str, Any]:
    refs = []
    for item_id in spec["evidence_ids"]:
        item = evidence[item_id]
        urls = list(item["source_urls"])
        refs.append({
            "item_id": item_id,
            "issue_date": item["issue_date"],
            "source_urls": urls,
            "reason": f"《{item['title']}》为该候选的问题、机制或边界提供已发布依据。",
            "independence_group": source_identity_key(urls[0]),
        })
    candidate_id = stable_candidate_id(spec["identity"])
    trigger_issue = max(row["issue_date"] for row in refs)
    disposition = "accepted" if spec["accept"] else "deferred"
    disposition_reason = (
        f"初步审阅通过，并于 {accepted_issue} 创建正式 Idea。"
        if spec["accept"] else
        "框架完整，但与现有工具接口分层 Idea 的身份和派生关系仍需单独人工判断。"
    )
    events = [{
        "event_id": f"candidate_decision_{stable_hash(candidate_id, trigger_issue, 'proposed', length=20)}",
        "issue_date": trigger_issue,
        "decision": "proposed" if spec["accept"] else "deferred",
        "from_disposition": None,
        "to_disposition": "proposed" if spec["accept"] else "deferred",
        "reason": "历史公开证据逐期审阅后形成可追踪候选。" if spec["accept"] else disposition_reason,
        "evidence_item_ids": list(spec["evidence_ids"]),
        "actor": "migration",
    }]
    related_ideas = list(spec.get("related_idea_ids") or [])
    if spec["accept"]:
        idea_id = "idea_" + candidate_id.removeprefix("candidate_")
        related_ideas.append(idea_id)
        events.append({
            "event_id": f"candidate_decision_{stable_hash(candidate_id, accepted_issue, 'accepted', length=20)}",
            "issue_date": accepted_issue,
            "decision": "accepted",
            "from_disposition": "proposed",
            "to_disposition": "accepted",
            "reason": disposition_reason,
            "evidence_item_ids": list(spec["evidence_ids"]),
            "actor": "human",
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "identity": copy.deepcopy(spec["identity"]),
        "idea_type": spec["idea_type"],
        "title": spec["title"],
        "problem": spec["problem"],
        "hypothesis": spec["hypothesis"],
        "mechanism": spec["mechanism"],
        "target": spec["target"],
        "expected_effect": spec["expected_effect"],
        "topic_ids": list(dict.fromkeys(evidence[item_id]["topic_id"] for item_id in spec["evidence_ids"])),
        "origin": {"kind": "cross_issue_synthesis", "trigger_issue": trigger_issue, "rationale": "将逐期公开记录按共同问题、机制和目标对象综合，并保留同源复报的单一独立分组。"},
        "evidence": refs,
        "evidence_item_ids": list(spec["evidence_ids"]),
        "source_urls": list(dict.fromkeys(url for row in refs for url in row["source_urls"])),
        "independence_groups": list(dict.fromkeys(row["independence_group"] for row in refs)),
        "unknowns": list(spec["unknowns"]),
        "validation_plan": {**copy.deepcopy(spec["validation"]), "execution_status": "suggestion_only"},
        "disposition": disposition,
        "disposition_reason": disposition_reason,
        "related_candidate_ids": [],
        "related_idea_ids": list(dict.fromkeys(related_ideas)),
        "first_seen_issue": min(row["issue_date"] for row in refs),
        "last_updated_issue": accepted_issue if spec["accept"] else trigger_issue,
        "decision_log": events,
    }


def build(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    archive = PublishedArchive(root)
    dates = archive.issue_dates()
    if not dates:
        raise ValueError("published archive is empty")
    all_evidence = archive.evidence_through(dates[-1])
    evidence = {str(row["item_id"]): row for row in all_evidence}
    candidates = [_candidate(spec, evidence, dates[-1]) for spec in GROUPS]
    candidate_by_item: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        for item_id in candidate["evidence_item_ids"]:
            candidate_by_item[item_id].append(candidate["candidate_id"])

    existing_idea_items = set()
    for path in (root / "knowledge" / "ideas").glob("idea_*.json"):
        idea = read_json(path, {})
        existing_idea_items.update(str(ref.get("item_id")) for field in ("evidence_for", "evidence_against") for ref in idea.get(field) or [])

    issue_rows = []
    for issue_date in dates:
        rows = []
        for item in PublishedArchive.evidence(archive.load_issue(issue_date)):
            item_id = str(item["item_id"])
            candidate_ids = candidate_by_item.get(item_id, [])
            if candidate_ids:
                result, code, reason = "candidate", "candidate_evidence", "该条证据进入初筛候选的显式证据链。"
            elif item.get("evidence_kind") == "discovery_signal" or item.get("claim_strength") == "unverified":
                result, code, reason = "no_op", "ineligible_radar", "Radar 是未验证 discovery signal，不能直接支持 Candidate 或正式 Idea。"
            elif item.get("topic_id") == FRONTIER_TOPIC_ID:
                result, code, reason = "no_op", "unstable_frontier_topic", "该正式 Machine 记录仍在临时 Frontier Topic，需先完成稳定 Topic 晋升后再参与 Candidate 发现。"
            elif item_id in existing_idea_items:
                result, code, reason = "no_op", "existing_idea_evidence", "该条证据已经进入现有正式 Idea，不重复创建候选。"
            else:
                result, code, reason = "no_op", "no_new_semantics", "首轮逐期审阅未形成同时具备独立问题、机制、目标和可验证效果的新对象；保留供后续证据重新评估。"
            rows.append({"item_id": item_id, "result": result, "candidate_ids": candidate_ids, "reason_code": code, "reason": reason})
        issue_rows.append({"issue_date": issue_date, "items": rows})
    generated_at = datetime.now(timezone.utc).isoformat()
    previous_report = read_json(root / "knowledge" / "candidate-backfill.json", {})
    if (
        previous_report.get("evidence_scope") == EVIDENCE_SCOPE
        and previous_report.get("through_issue") == dates[-1]
        and previous_report.get("issues") == issue_rows
        and previous_report.get("generated_at")
    ):
        generated_at = str(previous_report["generated_at"])
    report = {"schema_version": 1, "evidence_scope": EVIDENCE_SCOPE, "through_issue": dates[-1], "issues": issue_rows, "generated_at": generated_at}
    ideas = [candidate_to_idea(candidate, issue_date=dates[-1]) for candidate in candidates if candidate["disposition"] == "accepted"]
    return candidates, ideas, report


def validate(root: Path, candidates: list[dict[str, Any]], ideas: list[dict[str, Any]], report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    evidence_rows = PublishedArchive(root).evidence_through(report["through_issue"])
    evidence = {str(row["item_id"]): row for row in evidence_rows}
    candidate_ids = {row["candidate_id"] for row in candidates}
    idea_ids = {path.stem for path in (root / "knowledge" / "ideas").glob("idea_*.json")} | {row["idea_id"] for row in ideas}
    for candidate in candidates:
        errors.extend(_validate_schema(root, "idea-candidate.schema.json", candidate))
        errors.extend(_candidate_semantic_errors(candidate, evidence=evidence, known_candidate_ids=candidate_ids, known_idea_ids=idea_ids))
    for idea in ideas:
        errors.extend(_validate_schema(root, "idea.schema.json", idea))
        errors.extend(idea_semantic_errors(idea, issue_date=report["through_issue"], evidence=evidence_rows))
    errors.extend(_validate_schema(root, "idea-candidate-backfill.schema.json", report))
    covered = [str(row["item_id"]) for issue in report["issues"] for row in issue["items"]]
    expected = [str(row["item_id"]) for row in evidence_rows]
    if covered != expected:
        errors.append("backfill ledger must cover every published item exactly once and in archive order")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="write the reviewed Candidate, Idea, and ledger objects")
    args = parser.parse_args()
    root = args.root.resolve()
    candidates, ideas, report = build(root)
    errors = validate(root, candidates, ideas, report)
    if errors:
        raise ValueError("invalid Candidate backfill: " + "; ".join(errors[:20]))
    print(f"reviewed={sum(len(row['items']) for row in report['issues'])} candidates={len(candidates)} promoted={len(ideas)} deferred={sum(row['disposition'] == 'deferred' for row in candidates)}")
    if not args.apply:
        print("dry-run only; pass --apply to persist")
        return 0
    updates: dict[Path, Any] = {}
    for candidate in candidates:
        updates[root / "knowledge" / "idea-candidates" / f"{candidate['candidate_id']}.json"] = candidate
    for idea in ideas:
        path = root / "knowledge" / "ideas" / f"{idea['idea_id']}.json"
        if path.is_file() and read_json(path) != idea:
            raise ValueError(f"refusing to overwrite a different formal Idea: {idea['idea_id']}")
        updates[path] = idea
    updates[root / "knowledge" / "candidate-backfill.json"] = report
    commit_candidate_updates(root, updates)
    print("Candidate backfill applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
