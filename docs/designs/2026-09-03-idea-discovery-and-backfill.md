# Idea 持续发现与历史回填设计

| Field | Value |
| --- | --- |
| Status | draft |
| Created | 2026-09-03 |
| Last updated | 2026-09-03 |

## Problem and evidence

线上 Idea Hub 截至 2026-09-03 只有 6 个正式 Idea，最近一期没有新增对象或状态变化。知识新鲜度已经追上归档，因此数量停滞不能归因于 Pages 没有发布最新数据。

本次检查覆盖 `archive/index.json` 列出的 10 期归档、全部正式 Machine 条目、23 个长期知识任务输出，以及当前 6 个 Idea 文件。检查结果如下。

- 10 期归档共有 177 条正式 Machine 条目。
- 21 条进入过 Idea 的支持或反对证据，156 条从未被任何 Idea 引用。
- 6 个 Idea 的初始对象都来自 `scripts/seed_knowledge.py`。后续任务只更新已有对象，没有创建新的 Idea ID。
- 9 个正式 Roadmap Topic 中只有 `agent_acceleration`、`cross_region`、`storage_media` 和 `tpn` 拥有 Idea。
- 现有物化 Prompt 允许返回新 Idea，但输出只保存最终对象。Agent 没有义务列出考虑过的候选，也不用解释候选被判定为重复、证据不足或不具备可验证性的原因。
- Candidate Inbox 目前没有数据模型，页面明确显示为“未启用”。

156 条未引用记录不能直接换算成 156 个遗漏 Idea。例行版本发布、同一论文跨期复报、只有结果没有可迁移机制的条目，都可能不适合生成 Idea。当前缺少的是一份能回答“考虑过什么、为什么接受或放弃”的候选台账。没有这份台账，连续多期返回空数组时，维护者无法区分确实没有新意、模型过于保守、身份去重误判和任务输入不足。

## Goals and non-goals

本设计希望让每期已发布证据都经过显式 Idea 发现，并让历史归档可以按同一规则回填。最终页面应能区分候选和正式 Idea，维护者也能追查每次接受、合并、延后或放弃的依据。

具体目标包括以下内容。

- 建立单条证据发现和跨来源、跨期综合两条候选通道。
- 为每个候选保存来源、触发期次、问题、机制、目标对象和可验证效果。
- 在候选进入正式 Idea 前完成稳定身份、相似对象和 lineage 检查。
- 为未进入正式 Idea 的候选保存明确 disposition 和理由。
- 用逐期、可恢复的任务回填当前 10 期归档。
- 给 GitHub Pages 提供真实 Candidate Inbox 数据，不再展示没有数据来源的流程说明。

本设计不要求每期产生固定数量的 Idea，也不把证据覆盖率当成增长指标。它暂不执行实验，不改变 `validation_plan.execution_status=suggestion_only`，也不允许 Radar discovery signal 直接支持正式 Idea。

## Constraints and invariants

- 证据范围继续使用 `published_archive_only`。发现任务只读取 `archive/index.json` 已列出的 `issue.json` 与 `papers.json` Machine 记录。
- 候选池、全文、Reader 文案、网页分组和未发送材料不能进入正式证据链。
- 每个候选引用的 `item_id`、期次和 URL 必须能回到已发布记录。
- Radar 保持 `discovery_signal / unverified`。它只能进入 Frontier cluster，经过原始来源事实流程重新进入稳定 Topic 后才可支持 Idea。
- 同一来源或同一论文的跨期复报不能伪装成独立证据。独立来源数需要单独计算。
- Candidate 只是提案。它不能出现在正式 Idea Portfolio、知识图谱的确认关系或本期 Idea 状态变化中。
- 正式 Idea 的身份继续由问题、核心机制和目标对象共同决定。Topic 相同、标题相似或 project question 相同都不足以合并对象。
- 历史回填必须逐期执行。后一期任务绑定前一期 Candidate 与 Idea snapshot，不能把十期材料一次混入同一上下文。
- apply 保持幂等。失败不能留下半写入 Candidate、Idea、索引或派生图谱。

## Proposed design

### Candidate 成为独立对象

新增 `IdeaCandidate`，保存于 `knowledge/idea-candidates/<candidate_id>.json`。候选对象至少包含以下信息。

- `candidate_id` 和稳定的候选身份键
- `origin.kind`，取值为 `single_evidence`、`cross_source_synthesis`、`cross_issue_synthesis` 或 `roadmap_gap`
- `trigger_issue`、`evidence_item_ids`、`source_urls` 和独立来源分组
- `problem`、`mechanism`、`target`、`testable_effect` 和 `synthesis_rationale`
- 与已有 Candidate、正式 Idea 的相似对象及 lineage 建议
- `disposition`、决定理由、决定者和决定时间

首版 disposition 使用 `proposed`、`accepted`、`duplicate`、`deferred` 和 `dismissed`。`duplicate` 必须指向已有 Candidate 或 Idea。`dismissed` 必须说明缺的是问题、机制、目标、可验证效果或证据资格中的哪一项。`deferred` 用于框架完整但仍缺独立来源、适用边界或人工判断的对象。

Candidate 记录保持追加式决策历史。后续证据可以让 `deferred` 候选重新进入 `proposed`，但不能覆盖旧理由。

### 每期运行两个发现步骤

正常增量在归档完成后执行下列有界流程。

```text
本期每条新增正式证据
  -> Direct Candidate Extraction
  -> 单条强证据候选或带理由的 no-op

本期新增证据加同 Topic 历史证据加 Roadmap open question
  -> Topic Candidate Synthesis
  -> 跨来源、跨期或 roadmap gap 候选

候选提案
  -> Identity and Lineage Resolution
  -> proposed / duplicate / deferred / dismissed

人工确认 proposed 候选
  -> accepted
  -> 创建正式 Idea 或更新、拆分、关联已有 Idea
```

Direct Candidate 只有在一条证据同时给出明确问题、可说明的机制、目标对象和可验证效果时才创建候选。普通测量建议继续归入 validation plan。

Topic Candidate Synthesis 至少包含一条本期新增证据。`cross_issue_synthesis` 至少覆盖两个 `issue_date`。多条记录属于同一 Topic 只说明它们可以一起检查，不构成综合理由。

Identity and Lineage Resolution 单独运行，避免 Topic Roadmap 任务同时修改多 Topic Idea。它输出候选处置建议，不直接改写正式对象。正式 Idea 的创建或更新由每个 Idea 独占的任务完成，并绑定旧对象 digest。

### 历史回填

当前 10 期从 2026-08-02 开始按时间顺序回填。每一期只读取截至该期的公开证据和前一期已经落盘的 Candidate、Idea 与 Roadmap snapshot。

回填分成两轮。第一轮生成 Candidate 和 disposition，不改正式 Idea。维护者审阅 proposed 候选，确认哪些应当进入正式集合。第二轮为已接受候选创建或更新正式 Idea，再重建 index、graph、issue diff 和 manifest。

历史回填不得改写已经发送的日报，也不重建旧期的编辑判断。若旧期候选在较晚一期才获得足够证据，正式 Idea 的 `first_seen_issue` 继续取最早被引用的证据期次，Origin Event 则记录候选被提出和被接受的真实期次。

### GitHub Pages

Idea Hub 增加真实 Candidate Inbox。默认展示 `proposed` 和 `deferred`，并允许查看 duplicate 与 dismissed 的审计记录。候选卡片需要明确标出“尚未成为正式 Idea”，避免与 Portfolio 混合计数。

页面增加以下真实指标。

- 当前待审 Candidate 数
- 本期新增 Candidate 数
- 本期接受、合并和放弃数量
- 正式 Idea 数及本期状态变化

证据覆盖率可以进入技术诊断页，但不作为首页目标。低覆盖可能代表发现遗漏，也可能说明大部分条目只适合 Roadmap。

## Preliminary backfill audit

对现有公开 Machine 条目做的只读初筛已经发现几组具有明确问题、机制和验证方向的候选。它们还没有经过正式身份与 lineage resolution，不能直接写入 Idea Portfolio。

| 候选方向 | 初步类型 | 主要公开证据 | 初步判断 |
| --- | --- | --- | --- |
| 跨模型 KV 迁移与刷新 | research hypothesis | `aea2c5f288fa3cb1f1c150fd`、`3a70069639846632bc128f55`、`aec0bff49869dc80b9a03c53`、`2c397aec024504c233edf92f` | 已有多条独立机制证据，适合研究迁移误差、刷新频率和收益边界 |
| 硬件感知并经过部署验收的内核优化 | solution concept | `f682b45f4e2f6eed337331d3`、`a58adb4322d178c37bfe538a`、`56669f597b366c481995590f` | GPU、NPU 和部署内验收构成可组合方案 |
| CXL 混合内存 KV 容量层 | solution concept | `aad3ac6d44c9280e0f9b3ae3`、`d05f67d474b98cf028645985`、`ab820b3c0433c2eae0500436` | HyMCache 两次报道来自同一论文，独立证据实际是 HyMCache 与 MemChannel 两组 |
| 面向 Coding Agent 的结构化检索服务 | solution concept | `fbd868593a77683d93084640`、`2df30f2aad79d219cb0c0edb`、`c37bbb0e061ba80f732084f3`、`da847a709df41e3cd1c15eb4` | 需先判断它是现有工具分层 Idea 的派生方案，还是独立对象 |
| 可审计的分布式 Agent 记忆合并 | solution concept | `9c3c1121c0f97dba985dc9cc`、`925d9e03c6b9914c790dadf7`、`3f5542f2d0953600ae2066fb` | 冲突保留、版本化合并和查询条件化视图可以形成清晰验证计划 |
| 工具调用前的状态与资源监督 | solution concept | `4aacfff6b9b7808c286ad598`、`f5a9fafbe8d1f875de954234` | 适合验证意图检查、容量契约与中止原语能否减少重复失败和越界调用 |

这轮初筛支持一个保守预期。现有十期数据可能产生 8 到 15 个 Candidate，经去重、来源独立性和可验证性检查后，约有 5 到 8 个可以进入正式 Idea。这个范围只用于安排回填审阅工作量，不作为验收配额。

## Compatibility and migration

现有 `knowledge/ideas/*.json` 保持有效，ID 和 decision log 不变。Candidate 使用独立目录和索引字段，旧前端忽略未知字段时仍可读取现有 Portfolio。

首版迁移不强迫现有 6 个 Idea 补齐 Candidate 对象。可以为它们生成只读的 `legacy_seed` Origin 迁移记录，明确数据来自种子脚本，避免伪造当时不存在的发现过程。

知识任务需要加入 Candidate snapshot digest 和 Idea 对象 digest。已经 applied 的 23 个任务保持原样，历史回填使用新的任务类型和新 task ID，不修改旧 application。

## Failure, recovery, and rollback

发现任务失败时保留上一份完整 Candidate 与 Idea snapshot，manifest 显示 candidate analysis pending 或 failed。正式 Portfolio 和 Archive 继续可读。

单期回填可以从该期未完成任务继续。由于每期绑定前一期 snapshot，恢复时不能跳过失败期直接处理后一期。

回滚 Candidate 功能时，前端隐藏 Candidate Inbox，并停止调度新发现任务。现有正式 Idea 不回滚。尚未 accepted 的候选可以整体移出发布包，权威 Archive、Roadmap 和 Idea 文件不受影响。

## Verification

实现前先建立一组人工标注样本，至少覆盖强单条候选、跨期综合、同源复报、已有 Idea 更新、重复候选、只有测量建议和 Radar 不合格证据。

自动测试需要验证下列行为。

- 同一期同一输入重跑不会新增重复 Candidate 或决策事件。
- 同一论文跨期复报不会增加独立来源数。
- 每条新增正式证据都会得到候选或带理由的 no-op 结果。
- Candidate 不能直接出现在正式 Idea index 和确认关系图中。
- duplicate 必须指向有效 Candidate 或 Idea。
- accepted Candidate 通过独占 Idea task 写入，旧 Idea digest 不匹配时 apply 失败。
- Radar discovery signal 直接支持 Candidate 升格时校验失败。
- 历史回填逐期完成后，graph、issue diff 和 manifest 与最新知识 snapshot 一致。

人工验收使用当前 10 期归档。验收不规定新增 Idea 数量，但要求初筛表中的每组候选都有可追踪的 disposition，并能解释最终是否进入正式 Portfolio。

## Documentation impact

实现时需要同步更新以下位置。

- `SKILL.md` 中的长期知识任务顺序与证据边界
- `docs/architecture.md` 中的 Candidate、Idea 和派生发布数据流
- `docs/contracts/knowledge-materialization.md` 中的任务、状态、幂等与回填合同
- `docs/contracts/editorial-workbench-ui.md` 中的 Candidate Inbox 展示合同
- 新增 Candidate Prompt、Schema、语义校验、fixtures 和测试
- `README.md` 中的常用命令与 Idea Hub 说明
- `docs/operations/knowledge-freshness.md` 中的失败恢复和新鲜度状态

## Decision log

- 2026-09-03 依据线上页面、10 期公开归档、23 个知识任务输出和 6 个正式 Idea 完成现状检查。
- 2026-09-03 决定先形成设计草案，不修改代码、Schema、Prompt 或生产知识数据。
- 2026-09-03 建议用独立 Candidate 对象承接发现结果，并把历史回填与正式 Idea 写入分成两轮。
- 2026-09-03 保留 `published_archive_only`、Radar 不得直接支持 Idea、正式 Idea 稳定身份和逐期回填等现有边界。
