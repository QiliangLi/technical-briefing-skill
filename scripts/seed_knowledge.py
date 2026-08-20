#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.knowledge_materialization import (  # noqa: E402
    EVIDENCE_SCOPE,
    SCHEMA_VERSION,
    PublishedArchive,
    rebuild_knowledge_index,
    stable_idea_id,
    validate_knowledge_store,
)
from briefing_skill.utils import stable_hash, write_json  # noqa: E402


def _ref(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "item_id": item["item_id"],
        "issue_date": item["issue_date"],
        "source_urls": item["source_urls"],
        "reason": reason,
    }


def _roadmaps(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        if item.get("topic_id"):
            by_topic[str(item["topic_id"])].append(item)

    result: list[dict[str, Any]] = []
    for topic_id, items in sorted(by_topic.items()):
        topic_name = next(str(item.get("topic_name") or topic_id) for item in items)
        last_issue = max(str(item["issue_date"]) for item in items)
        by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            direction_id = str(item.get("direction_id") or "unclassified")
            by_direction[direction_id].append(item)
        branches = []
        for direction_id, direction_items in sorted(by_direction.items()):
            direction_name = next(
                (
                    str(item.get("direction_name"))
                    for item in direction_items
                    if item.get("direction_name")
                ),
                direction_id,
            )
            refs = [
                _ref(
                    item,
                    f"{item['issue_date']} 已发布日报收录了《{item['title']}》；当前仅记录其出现，不据此强行划分阶段。",
                )
                for item in direction_items
                if item.get("source_urls")
            ]
            branches.append(
                {
                    "branch_id": direction_id,
                    "name": direction_name,
                    "direction_ids": [direction_id],
                    "status": "emerging",
                    "stages": [],
                    "evidence_timeline": refs,
                    "open_questions": [],
                    "evidence_item_ids": [ref["item_id"] for ref in refs],
                    "source_urls": sorted({url for ref in refs for url in ref["source_urls"]}),
                }
            )
        version_path = f"knowledge/history/roadmaps/{topic_id}/v1.json"
        roadmap = {
            "schema_version": SCHEMA_VERSION,
            "roadmap_id": f"roadmap_{topic_id}",
            "topic_id": topic_id,
            "topic_name": topic_name,
            "version": 1,
            "evidence_scope": EVIDENCE_SCOPE,
            "updated_by_issue": last_issue,
            "change_type": "material_change",
            "summary": (
                f"现有公开归档为“{topic_name}”积累了 {len(items)} 条专题证据，"
                "但时间跨度和跨期关联仍不足以可靠划分技术阶段，首版先保留可追溯的证据时间线。"
            ),
            "view_mode": "evidence_timeline",
            "branches": branches,
            "history": [
                {
                    "version": 1,
                    "issue_date": last_issue,
                    "change_type": "material_change",
                    "path": version_path,
                }
            ],
            "change_log": [
                {
                    "event_id": f"roadmap_change_{stable_hash(topic_id, last_issue, 'seed', length=20)}",
                    "issue_date": last_issue,
                    "change_type": "material_change",
                    "version": 1,
                    "summary": "根据截至本期的已发布 Machine 记录建立首版证据时间线；尚未声称存在明确阶段或转折。",
                    "evidence_item_ids": sorted(item["item_id"] for item in items),
                }
            ],
        }
        result.append(roadmap)
    return result


def _idea(
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    identity: dict[str, str],
    idea_type: str,
    title: str,
    problem: str,
    hypothesis: str,
    mechanism: str,
    expected_effect: str,
    topic_ids: list[str],
    evidence: list[tuple[str, str]],
    unknowns: list[str],
    validation_plan: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    refs = [_ref(evidence_by_id[item_id], reason) for item_id, reason in evidence]
    first_seen = min(ref["issue_date"] for ref in refs)
    last_updated = max(ref["issue_date"] for ref in refs)
    idea_id = stable_idea_id(identity)
    refs_by_issue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ref in refs:
        refs_by_issue[ref["issue_date"]].append(ref)
    decision_log = [
        {
            "event_id": f"idea_decision_{stable_hash(idea_id, first_seen, 'created', length=20)}",
            "issue_date": first_seen,
            "decision": "created",
            "from_status": None,
            "to_status": status,
            "reason": "已发布证据给出了明确问题和可检验机制，因此建立 Idea；当前没有执行仿真或实验。",
            "evidence_item_ids": [ref["item_id"] for ref in refs_by_issue[first_seen]],
        }
    ]
    for issue_date in sorted(date for date in refs_by_issue if date != first_seen):
        decision_log.append(
            {
                "event_id": f"idea_decision_{stable_hash(idea_id, issue_date, 'evidence_added', length=20)}",
                "issue_date": issue_date,
                "decision": "evidence_added",
                "from_status": status,
                "to_status": status,
                "reason": "新增已发布证据继续支持同一问题、机制和目标身份；Idea 状态暂不改变。",
                "evidence_item_ids": [ref["item_id"] for ref in refs_by_issue[issue_date]],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "idea_id": idea_id,
        "identity": identity,
        "idea_type": idea_type,
        "title": title,
        "problem": problem,
        "hypothesis": hypothesis,
        "mechanism": mechanism,
        "expected_effect": expected_effect,
        "topic_ids": topic_ids,
        "status": status,
        "evidence_for": refs,
        "evidence_against": [],
        "unknowns": unknowns,
        "validation_plan": {**validation_plan, "execution_status": "suggestion_only"},
        "first_seen_issue": first_seen,
        "last_updated_issue": last_updated,
        "decision_log": decision_log,
    }


def _ideas(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["item_id"]: item for item in evidence}
    return [
        _idea(
            by_id,
            identity={
                "problem_key": "agent_tool_interaction_efficiency",
                "mechanism_key": "capability_matched_tool_interface",
                "target_key": "coding_agent_success_cost",
            },
            idea_type="research_hypothesis",
            title="工具接口要按 Agent 能力分层，而不是统一追求更复杂",
            problem="相同工具能力在不同接口组织下会改变编码 Agent 的成功率、步骤数和 token 成本。",
            hypothesis="弱 Agent 更可能从结构化原语获益，而强 Agent 可能因额外结构付出输入成本；接口收益应按 Agent 能力分层评估。",
            mechanism="在保持底层工具能力近似不变时，分别提供结构化原语、自然语言检索和可编程接口。",
            expected_effect="找到每类 Agent 在成功一致性、端到端时延和调用成本之间更合适的接口组织。",
            topic_ids=["agent_acceleration"],
            evidence=[
                ("e1795f803462ec42b96e0512", "受控对比表明接口组织会改变不同能力 Agent 的一致性和效率。")
            ],
            unknowns=["收益能否迁移到内部代码库和任务分布。", "接口学习成本是否抵消步骤与 token 节省。"],
            validation_plan={
                "mode": "benchmark",
                "minimal_model": "固定一个模型、同一任务集和同等底层工具能力，只替换接口组织。",
                "inputs": ["弱与强两档 Agent", "真实仓库修复任务", "结构化、自然语言和可编程三类接口"],
                "baselines": ["当前默认工具接口", "仅自然语言检索接口"],
                "metrics": ["pass^k", "端到端时延", "工具调用次数", "输入与输出 token"],
                "support_criteria": ["至少一档 Agent 在成功率不下降时稳定减少步骤、时延或 token。"],
                "reject_criteria": ["不同接口在重复实验中没有稳定收益，或成功率下降抵消全部成本收益。"],
                "limitations": ["小型基准不能覆盖长任务状态漂移和多人维护的真实代码库。"],
            },
            status="seed",
        ),
        _idea(
            by_id,
            identity={
                "problem_key": "long_horizon_agent_continuity",
                "mechanism_key": "versioned_project_state_harness",
                "target_key": "software_evolution_acceptance",
            },
            idea_type="solution_concept",
            title="用版本化项目状态和可演化 Harness 承接长任务连续性",
            problem="长时程软件任务若依赖单个长寿命 Agent 进程，模型更换、上下文重建和跨路径协作都容易中断。",
            hypothesis="把连续性放入版本化项目对象，并用接受门约束 Harness 自改进，可以让有限生命的 Agent 持续推进长任务。",
            mechanism="以已接受版本、路径局部世界、显式上下文文件和父级接受门组成持久项目 Harness。",
            expected_effect="降低会话寿命对长期开发连续性的约束，同时让 Harness 变化可审计、可回退。",
            topic_ids=["agent_acceleration"],
            evidence=[
                ("239936d77241bed615ba7777", "Genesis 把持久对象放在版本化项目世界而非长寿命 Agent 进程。"),
                ("a870ad411f08f3097f03133a", "AutoDesign 展示了在接受门约束下递归改进设计 Harness 的路径。"),
            ],
            unknowns=["人工干预和失败恢复的真实成本。", "Harness 自改进是否会在不同模型之间稳定迁移。"],
            validation_plan={
                "mode": "prototype",
                "minimal_model": "选一个跨多目录、可由测试验收的开发任务，Agent 会话可随时重启。",
                "inputs": ["版本化 CONTEXT 记录", "Git 历史", "路径级任务委派", "开发集接受门"],
                "baselines": ["单一长会话 Agent", "只保存聊天摘要的重启方案"],
                "metrics": ["任务完成率", "重启恢复时间", "返工提交数", "人工介入次数", "总成本"],
                "support_criteria": ["多次会话重启后仍能通过同一接受门，且恢复与返工成本低于基线。"],
                "reject_criteria": ["状态文件持续失真，或 Harness 更新导致验收回退且无法可靠定位。"],
                "limitations": ["单仓库原型不能证明跨团队权限、安全和治理可行性。"],
            },
            status="observing",
        ),
        _idea(
            by_id,
            identity={
                "problem_key": "kv_transfer_tail_latency",
                "mechanism_key": "transfer_recompute_locality_selection",
                "target_key": "pd_disaggregated_inference",
            },
            idea_type="research_hypothesis",
            title="KV 传输、重算与就地计算存在随带宽和命中率变化的交叉点",
            problem="PD 解耦推理并非总该完整传输 KV；链路带宽、KV 重要性和请求放置会改变最优选择。",
            hypothesis="在统一负载下，必要 KV 优先传输、带宽感知重算和解码节点就地 Prefill 会在不同网络条件下各自占优。",
            mechanism="按请求估算 KV 传输、局部重算和就地计算代价，再选择执行位置与传输粒度。",
            expected_effect="在不牺牲输出正确性的前提下降低尾部 TTFT，并减少无效 KV 搬移。",
            topic_ids=["tpn"],
            evidence=[
                ("081c683d89c0a8496e81e918", "SmartGen 展示了必要 KV 先行和后台补全在受限带宽下的收益。"),
                ("d68187e106469502469bd400", "Kairos 通过 Decode 节点就地 Prefill 删除一类跨节点 KV 传输。"),
                ("ee715d6b89c2722b10eafa3e", "AAFLOW+ 将传输或重算作为带宽感知选择。"),
            ],
            unknowns=["多租户 P95/P99 下的交叉点是否稳定。", "代价预测错误与画像漂移会造成多大回退。"],
            validation_plan={
                "mode": "simulation",
                "minimal_model": "离散事件模型覆盖 Prefill、KV 传输、Decode 排队和可选重算。",
                "inputs": ["RTT 与带宽扫描", "KV 大小与可选比例", "缓存命中率", "Prefill/Decode 到达率"],
                "baselines": ["完整 KV 传输", "始终重算", "固定请求放置"],
                "metrics": ["P50/P95/P99 TTFT", "TPOT", "传输字节", "GPU 与网络利用率"],
                "support_criteria": ["联合选择策略在一段可解释参数区间内同时改善尾 TTFT 和传输量。"],
                "reject_criteria": ["策略只在极窄参数点获益，或预测开销使尾延迟不优于固定基线。"],
                "limitations": ["模拟不能覆盖真实通信栈抖动、GPU 内核干扰和调度实现开销。"],
            },
            status="observing",
        ),
        _idea(
            by_id,
            identity={
                "problem_key": "cross_node_prefix_reuse",
                "mechanism_key": "hot_prefix_replication",
                "target_key": "distributed_kv_placement",
            },
            idea_type="solution_concept",
            title="把热前缀当作可复制对象，联合路由与跨节点 KV 放置",
            problem="跨节点前缀复用若只依赖请求落点，会因缓存位置与路由割裂而重复计算或远程搬移。",
            hypothesis="根据前缀热度复制 KV，并让路由读取同一放置状态，可以提高跨节点复用并降低 TTFT。",
            mechanism="维护前缀热度、复制预算和节点目录，由路由与分布式张量池共同决定放置与检索。",
            expected_effect="减少重复 Prefill 和跨节点冷检索，同时控制复制带来的内存与更新成本。",
            topic_ids=["tpn"],
            evidence=[
                ("69f88e7cf73dab2f22f7e6f3", "PTStore 以 CDN 式热前缀复制验证了跨节点分布式检索路径。"),
                ("a93564bff4afb59e45ade272", "TensorCast 展示了把路由与 KV 放置放入统一张量生命周期层。"),
            ],
            unknowns=["热度变化下的复制抖动与目录一致性成本。", "多租户隔离和前缀隐私边界。"],
            validation_plan={
                "mode": "simulation",
                "minimal_model": "带有限显存、前缀流行度和请求路由的多节点缓存模拟器。",
                "inputs": ["Zipf 热度参数", "复制因子", "缓存容量", "节点数", "前缀更新率"],
                "baselines": ["无复制的一致性哈希", "本地 LRU", "固定复制因子"],
                "metrics": ["P95 TTFT", "跨节点传输字节", "重复 Prefill 次数", "显存占用", "复制写放大"],
                "support_criteria": ["在显存预算内持续降低重复 Prefill 和尾 TTFT，复制写放大保持可控。"],
                "reject_criteria": ["热度漂移使复制抖动抵消检索收益，或目录/同步成本高于重算。"],
                "limitations": ["模拟不能覆盖真实模型前缀可共享性、租户安全和网络故障恢复。"],
            },
            status="observing",
        ),
        _idea(
            by_id,
            identity={
                "problem_key": "wan_state_transfer_volume",
                "mechanism_key": "delta_residual_compression",
                "target_key": "kv_and_model_state",
            },
            idea_type="research_hypothesis",
            title="增量与残差压缩能否把跨域状态同步从带宽瓶颈变成可调度开销",
            problem="KV 和模型状态跨域发布体积大，但不同状态的稀疏变化与可压缩结构并不相同。",
            hypothesis="对权重变化做稀疏增量、对 KV 做锚点残差，可显著减少传输字节，但 WAN 尾延迟收益仍取决于编解码和按需访问。",
            mechanism="按状态类型选择变化检测或锚点残差表示，并在传输前后保留可恢复或可按需访问的结构。",
            expected_effect="降低跨域同步字节并形成可以纳入调度的压缩率、编解码开销和链路时延权衡。",
            topic_ids=["cross_region"],
            evidence=[
                ("d88d425cdec8fce0d0f46755", "AReaL-DTE 证明稀疏增量可压缩频繁发布的模型权重，但 WAN 时延仍非实测。"),
                ("90adc6a59fb3586708fdb7e7", "AnchorKV 给出保留 token 可达性的锚点残差 KV 表示。"),
                ("a097b982991694268bbb55b3", "C²KV 提供面向非前缀 KV 搬移的可组合压缩证据。"),
            ],
            unknowns=["真实 WAN RTT、抖动和丢包下的尾延迟。", "压缩表示对随机访问与更新频率的影响。"],
            validation_plan={
                "mode": "benchmark",
                "minimal_model": "记录真实状态变化轨迹，在可控 WAN 仿真链路上回放传输与恢复。",
                "inputs": ["权重更新稀疏度", "KV 长度与可压缩率", "RTT、带宽、丢包率", "编解码并发度"],
                "baselines": ["全量传输", "通用无损压缩", "只做应用层分片"],
                "metrics": ["传输字节", "P95 完成时间", "编码与恢复时间", "随机访问开销", "恢复正确性"],
                "support_criteria": ["在多档 WAN 条件下端到端完成时间稳定低于全量传输，且恢复结果满足正确性约束。"],
                "reject_criteria": ["编解码或随机访问开销抵消带宽节省，或收益只存在于不现实的高稀疏度。"],
                "limitations": ["链路回放不能覆盖跨云对象存储、拥塞控制和故障重试的全部行为。"],
            },
            status="observing",
        ),
        _idea(
            by_id,
            identity={
                "problem_key": "ai_storage_hierarchy_gap",
                "mechanism_key": "hbf_intermediate_tier",
                "target_key": "model_and_kv_storage",
            },
            idea_type="research_hypothesis",
            title="HBF 是否能成为 HBM 与 SSD 之间可部署的 AI 状态层级",
            problem="模型与 KV 状态需要比 SSD 更低时延、比 HBM 更大容量的层级，但开放接口、设备数据和软件集成仍不足。",
            hypothesis="若 HBF 的真实带宽、时延、耐久和 UCIe 集成成本落在合理区间，它可能承载部分模型或缓存状态。",
            mechanism="通过开放接口把 HBF 作为主加速器附近的中间容量层，并由运行时按访问热度迁移状态。",
            expected_effect="在不完全依赖 HBM 扩容的情况下提高可驻留状态容量，并降低 SSD 路径时延。",
            topic_ids=["storage_media"],
            evidence=[
                ("5ddb6069323d1bdf0849c62c", "公开归档记录了 HBF 开放规格及其位于 HBM 与 SSD 之间的目标定位。")
            ],
            unknowns=["真实样片的时延、带宽、功耗、耐久和成本。", "运行时与封装集成开销。"],
            validation_plan={
                "mode": "continued_observation",
                "minimal_model": "先建立参数化层级模型；待样片可用后用同一访问轨迹替换估算参数。",
                "inputs": ["容量", "带宽", "访问时延", "耐久", "功耗", "单位容量成本"],
                "baselines": ["HBM 扩容", "NVMe SSD 分层", "CXL 内存层"],
                "metrics": ["应用级 P95 时延", "有效带宽", "迁移字节", "功耗", "总拥有成本"],
                "support_criteria": ["真实器件参数在代表负载上形成区别于 HBM 与 SSD 的稳定收益区间。"],
                "reject_criteria": ["样片与系统数据表明其性能或成本区间被现有层级完全覆盖。"],
                "limitations": ["当前仅有规范信号，参数模型不能替代真实器件和系统测量。"],
            },
            status="seed",
        ),
    ]


def seed(root: Path, *, overwrite: bool = False) -> dict[str, int]:
    archive = PublishedArchive(root)
    dates = archive.issue_dates()
    if not dates:
        raise RuntimeError("archive/index.json has no published issues")
    evidence = archive.evidence_through(dates[-1])
    roadmaps = _roadmaps(evidence)
    ideas = _ideas(evidence)
    knowledge_root = root / "knowledge"
    existing = list((knowledge_root / "roadmaps").glob("*.json")) + list((knowledge_root / "ideas").glob("*.json"))
    if existing and not overwrite:
        raise RuntimeError("knowledge seed already exists; pass --overwrite to regenerate it")
    for roadmap in roadmaps:
        path = knowledge_root / "roadmaps" / f"{roadmap['topic_id']}.json"
        write_json(path, roadmap)
        write_json(root / roadmap["history"][0]["path"], copy.deepcopy(roadmap))
    for idea in ideas:
        write_json(knowledge_root / "ideas" / f"{idea['idea_id']}.json", idea)
    write_json(
        knowledge_root / "frontier-clusters.json",
        {"schema_version": SCHEMA_VERSION, "evidence_scope": EVIDENCE_SCOPE, "clusters": []},
    )
    rebuild_knowledge_index(root)
    errors = validate_knowledge_store(root)
    if errors:
        raise RuntimeError("seed validation failed: " + "; ".join(errors[:12]))
    return {"roadmaps": len(roadmaps), "ideas": len(ideas), "published_issues": len(dates)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the initial published-evidence knowledge seed")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    print(seed(args.root.resolve(), overwrite=args.overwrite))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
