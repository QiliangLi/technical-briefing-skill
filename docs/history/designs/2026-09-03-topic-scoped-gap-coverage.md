# Coverage-gap 覆盖判定按 Topic 收口

- Status: implemented
- Created: 2026-09-03
- Last updated: 2026-09-03

## Implementation evidence (2026-09-03)

- 共享谓词:`briefing_skill/quality_guard.py` 新增 `primary_row_matches_direction(row, topic_id, direction)`,Topic 边界(要求 `topic_hint` 属于目标 Topic)置于精确 hint 与关键词兜底之前;`quality_guard.primary_direction_is_covered` 改为对该谓词的首行命中。
- 运行时路径:`briefing_skill/coverage_policy.py` 的 `primary_direction_is_diversely_covered` 改为逐行调用共享谓词,仅对通过行计 `_project_key`,保留 TPN 两项目阈值;`coverage_policy` 单向导入 `quality_guard`,无循环依赖。bootstrap 替换(coverage_policy.py 的 install 覆盖 `quality_guard.primary_direction_is_covered`)保持不变,生产路径经替换后的函数生效。
- 测试:`tests/test_topic_coverage_policy.py` 新增跨 Topic 泛词不可覆盖、同 Topic 精确 hint 与关键词兜底可覆盖、同 Topic B 级/discovery-only/未解析 URL 不可覆盖、TPN 两项目必须同属 TPN、bootstrap 替换路径 topic-scoped 五组断言;并把原 `cross_region` 兜底断言按新契约反转为不可覆盖。`tests/test_discovery_stage.py` 新增 planner 级回归:以本期等价 fixture(其他方向均有同 Topic A 级覆盖、两条真实缺口、跨 Topic 泛词 A 级记录、预算 4)断言前四条 lane 正为新 Topic 四方向。
- 只读重放:对 `2026-09-03-003948` 的 SQLite 副本执行修复后的 planner,输出前四条 lane 为 `accelerator_io_datapath` 的 `accelerator_initiated_io`、`accelerator_storage_controller`、`accelerator_storage_stack`、`direct_storage_path`(priority 80),与设计预测一致。
- 完整测试套件:559 通过、4 失败。4 个失败均与本修复无关且在未含本修复的干净工作树上复现:
  - `test_demo` / `test_approval`:间歇性 `unable to open database file`(共享生产 workspace 的既有环境脆弱点,干净树先 2 次通过后又 3 次失败,与代码版本无关);
  - `test_knowledge_graph`:既有断言失败(干净树同样失败);
  - `test_publication_manifest_roundtrip`:共享状态相关的偶发失败(单测隔离重跑通过)。
- 定向验证全部通过:`tests/test_topic_coverage_policy.py` + `tests/test_discovery_stage.py` 26 个断言通过。
- `SKILL.md` 规则 5 已同步为"只由同 Topic 的可用 A 级来源证明 Direction 覆盖,其他 Topic 的条目即使包含方向词也不能兜底"。

## Problem and evidence

最新已发布 run `2026-09-03-003948` 在提交 `552fea6` 之后启动：提交时间为
2026-09-02 23:49:32 +08:00，run 创建时间为 2026-09-03 00:40:18 +08:00。
因此 `accelerator_io_datapath` 的配置、来源路由、Direction 和 Deep 容量已经进入本期运行，
“本期没有该专题内容”不是旧配置恢复或提交时序造成的。

对本期 SQLite、任务输入和运行时代码复核后，原分析的核心结论成立，但需要两处精确化：

| 原结论 | 复核结果 |
| --- | --- |
| 新 Topic 配置已生效 | 正确。候选表中有 7 条候选被路由到 `accelerator_io_datapath`。 |
| 7 条均为 B 级，来自 YeeKal 6 条和 SemiAnalysis 1 条 | 正确。7 条候选最终状态全部为 `RADAR`，`fulltext_required=0`，没有进入 relevance batch 或事实抽取。SemiAnalysis 条目虽然 `discovery_only=0`，但来源等级仍是 B。 |
| 60 天池没有该 Topic 的历史 A 级候选 | 对候选和历史存量而言正确。此前 run 中 `topic_hint=accelerator_io_datapath` 的 A 级 raw item 为 0；四条新 arXiv 历史回填 lane 在本期均为 `NOT_STARTED`。但本期当前采集另有 1 条 YeeKal 外链被标为 A 且带该 Topic hint，标题为“GitHub。”、无 Direction hint，未形成 candidate，因此不改变最终结果。 |
| 四个方向被其他 Topic 的 A 级条目假阳性覆盖 | 正确。运行时实际使用 `coverage_policy.primary_direction_is_diversely_covered`；它和 `quality_guard.primary_direction_is_covered` 都会在精确 hint 未命中时，对所有 Topic 的 A 级 raw item 做方向词表匹配。 |
| 本期两个 gap-search lane 因此给了其他方向 | 正确。任务输入只包含 `storage_media:magnetic_recording` 和 `optical_network:hybrid_network`。 |
| 下一期必然同样如此、永远不会触发搜索 | 表述过强。覆盖每期按当前 run 重算，没有永久“已覆盖”状态；但只要当前采集或 60 天回填继续带入含泛词的其他 Topic A 级条目，四个方向就会稳定被误判，所以下一期高度可能复现。另一方面，四条新 arXiv 历史回填 lane 后续轮转到时也可能带来真正的同 Topic A 级来源。 |

可复现的最小假阳性是 AInfer-PD：它的真实 hint 是
`tpn/kv_network_scheduling`，但标题与摘要同时包含 `accelerator` 和 `storage`。
`accelerator_io_datapath` 的前三个 Direction 都包含这两个泛词，现有“词表超过两个时命中任意两个词”规则便把它们判为已覆盖；同一条目还因
`accelerator`、`fine-grained` 和 `queue` 命中 controller Direction。实际数据中并非只有这一条，
还有多条其他 Topic 的 arXiv 和 GitHub Release 记录能以 `gpu + storage`、
`gpu + accelerator`、`fine-grained + queue` 等组合通过兜底。

按拟议的 Topic 约束重放本期 search planning，并排除 gap search 自己后来写入的结果后，
缺口排序的前四条会变为该 Topic 的四个 Direction：

1. `accelerator_initiated_io`
2. `accelerator_storage_controller`
3. `accelerator_storage_stack`
4. `direct_storage_path`

这与 `aihot_priority: high`、全局最多 4 条 gap lane 的当前排序契约一致。

该缺陷是旧逻辑的潜在问题，不是 `552fea6` 新增的函数错误：基础关键词兜底来自
`a1e7e00`，TPN 多项目版本来自 `e37d440`。`552fea6` 新增的 Direction 使用了
`gpu`、`accelerator`、`storage`、`queue` 等高频词，使跨 Topic 假阳性从偶发变成稳定触发。

## Goals and non-goals

### Goals

- 一个 A 级来源只能证明其 `topic_hint` 所属 Topic 内的 Direction 已覆盖。
- 保留同 Topic 内的 Direction 精确 hint 和关键词兜底，以兼容只提供 Topic hint、没有 Direction hint 的来源适配器。
- 保留 A 级、非 `discovery_only`、可解析原始 URL 三个现有必要条件。
- 保留 TPN 同一 Direction 至少两个不同项目才算覆盖的多样性规则。
- 让直接调用的基础判定、运行时多项目判定和 gap-search planner 使用同一条 Topic 边界，避免测试通过但实际 monkey patch 路径仍错误。
- 用回归测试证明跨 Topic 泛词不能压掉新 Topic 的 gap lane。

### Non-goals

- 不要求每期覆盖全部 Topic，也不保证该 Topic 一定产生 Deep 条目。
- 不改变 gap-search 全局 4 lane 预算、Topic 优先级或当前排序方式。
- 不降低 Deep 的 A 级来源、相关性、Technology Value、Evidence Pack、Fact Check、专题 Top4 或项目多样性门槛。
- 不重跑、重写或补发 `2026-09-03-003948`，不修改已发布邮件、归档和知识数据。
- 不在本修复中重做 Topic/Direction 分类器，也不以全文语义模型替代确定性覆盖判定。
- 不把历史回填 lane 的调度与轮转问题并入本缺陷；四条新 lane 已正确注册，只是本期尚未轮转执行。

## Constraints and invariants

- **Topic 证据边界**：其他 Topic 的标题、摘要或 release note 即使包含目标 Direction 的词，也不能证明目标 Topic 已有固定来源覆盖。
- **来源可用性**：只有 `source_level=A`、`discovery_only=false` 且原始 URL 已解析的记录能参与覆盖。
- **Direction 兼容性**：同 Topic 且 Direction hint 精确一致时直接覆盖；同 Topic 但 Direction hint 为空或不同的记录，仍可按现有词表阈值做兜底。
- **多项目规则**：TPN 仍要求两个不同 `_project_key`；其他 Topic 要求一个。
- **运行隔离**：只检查活动 run 中的 raw rows。60 天 backlog 必须先按现有逻辑物化到该 run，不能在判定函数内跨 run 扫描。
- **搜索独立性**：每个已选 gap lane 仍独立搜索，不跨 lane 转移结果。
- **发布完整性**：修复只改变 gap lane 是否创建，不绕过后续选择和事实门禁，不触发邮件或归档外部效果。
- **保守失败方向**：无法确定 Topic 归属时宁可把 Direction 视为未覆盖并消耗一条受限搜索 lane，也不能用其他 Topic 的证据静默阻止搜索。

## Proposed design

### 1. 先按 Topic 过滤，再做 Direction 判定

覆盖谓词按以下顺序执行：

```text
for row in active_run_raw_rows:
    require source_level == A
    require discovery_only == false
    require resolved primary URL
    require row.topic_hint == requested_topic_id

    if row.direction_hint == requested_direction_id:
        count row as a match
    else if current direction include_terms reach the existing threshold:
        count row as a fallback match
```

关键变化只有第四个 `require`。关键词兜底继续存在，但候选集合从“活动 run 的所有 A 级来源”
收口为“活动 run 中已归属于当前 Topic 的 A 级来源”。

不接受仅在关键词分支中临时排除 `accelerator_io_datapath` 的专题特例。该错误对任何使用泛词的
新旧 Topic 都成立，Topic 证据边界应是通用契约。

### 2. 统一基础匹配，保留多项目聚合

当前存在两份近似实现：

- `briefing_skill.quality_guard.primary_direction_is_covered`
- `briefing_skill.coverage_policy.primary_direction_is_diversely_covered`

bootstrap 先安装 quality guard，随后 coverage policy 用第二个函数替换第一个，
discovery stage 最终读取被替换后的函数。因此只修改 `quality_guard.py` 不足以修复生产路径。

实施时应提取一个无状态、单行级的共享谓词，例如
`primary_row_matches_direction(row, topic_id, direction)`，由两条聚合路径共同调用：

- 基础覆盖函数在第一条匹配行时返回 `True`；
- 多项目覆盖函数只对共享谓词通过的行计算 `_project_key`，并保留 TPN 的两项目阈值。

共享谓词放在 `quality_guard.py` 即可，`coverage_policy.py` 单向导入它；不要反向导入
`coverage_policy`，以免引入循环依赖。现有运行时替换可暂时保留，本修复不需要重构整个安装层。

### 3. 搜索计划保持现有预算语义

`plan_coverage_gap_searches` 无需新增 Topic 特例。修正谓词后，当前 run 的拟议结果会自然产生
多个未覆盖 Direction，其中四个 `accelerator_io_datapath` Direction 因 high 优先级排在最前，
并占用本期最多 4 个 search lane。

这是当前优先级与预算配置的预期结果，不是“保证新 Topic 四方向全搜”的新产品承诺。
后续 run 若已有同 Topic A 级来源，或其他更高优先级缺口出现，实际 lane 仍可变化。

### 4. 不使用 candidate 反推覆盖

本期 7 条 B 级 candidate 证明 RuleMatcher 已能把线索路由到新 Topic，但 candidate 不是固定来源覆盖证据。
覆盖判定继续基于 raw item 的来源等级、可解析 URL 与 hint，不把 relevance、Radar 状态或
`candidate.topic_id` 反写成覆盖。这样可避免 B 级线索或尚未评审的候选提前阻止 gap search。

## Compatibility and migration

- 不新增或修改 SQLite 表、任务 Schema、Prompt 输入字段、缓存版本和配置键。
- 已完成与进行中的旧任务保持原输入与结果；修复只在下一次调用 gap-search planning 时生效。
- 旧 run 不重算，不回写任务或来源 hint。
- 现有正确提供 `topic_hint + direction_hint` 的 arXiv、GitHub Release 和 Agent Search 记录行为不变。
- 只提供 Topic hint 的来源仍可依靠同 Topic 关键词兜底；没有 Topic hint 的 A 级来源会被保守地视为不能证明任何 Topic 的覆盖，可能多消耗受限 gap-search lane。这是为消除跨 Topic 假阳性接受的兼容性变化。
- TPN 的两项目阈值与 `_project_key` 计算保持不变。

## Failure, recovery, and rollback

### Expected failures

- 修改基础函数但漏掉运行时多项目函数，导致单元测试通过而真实 planner 仍误判。
- 误删同 Topic 关键词兜底，使只有 Topic hint 的合法 A 级来源不能覆盖 Direction。
- 把 Topic 过滤放在精确 Direction 分支之后，仍允许跨 Topic 关键词进入。
- 修复后多个 high-priority 缺口占满四条预算，低优先级 Topic 本期没有搜索机会。

### Recovery

- 用 planner 级测试而不只用函数级测试验证 bootstrap 后的实际路径。
- 对搜索预算饥饿单独依赖现有优先级和后续 run 重算；没有 telemetry 证据前不扩大本修复范围。
- 若上线后发现大量真实 A 级来源缺少 Topic hint，应修复对应 source adapter 的 hint 归属，
  不恢复跨 Topic 全局关键词兜底。

### Rollback

- 回滚共享 Topic 过滤及相应测试即可；没有数据库迁移、缓存清理或归档恢复动作。
- 回滚前保留已经生成的 gap-search 任务和 run 产物，不能删除或重写进行中的任务。
- 回滚不会撤销新 Topic 配置；若 Topic 本身也需停用，必须按原专题设计的独立回滚步骤处理。

## Verification

### Predicate tests

- 其他 Topic 的已解析 A 级记录，即使同时含 `accelerator + storage`，也不能覆盖
  `accelerator_io_datapath/direct_storage_path`。
- 其他 Topic 的 A 级记录，即使含 `accelerator + fine-grained + queue`，也不能覆盖 controller Direction。
- 同 Topic、精确 Direction hint、A 级、非 discovery-only、已解析 URL 的记录可以覆盖。
- 同 Topic、无 Direction hint、满足现有关键词阈值的记录可以覆盖。
- 同 Topic 的 B 级、discovery-only 或未解析 URL 记录不能覆盖。
- TPN 同 Direction 的一个项目仍不足，两个不同项目仍足够；两个项目都必须属于 TPN。

### Planner regression

构造与本期等价的 fixture：

- 四个目标 Direction 没有同 Topic A 级记录；
- 其他 Topic 含 AInfer-PD 类 `accelerator + storage` 泛词记录；
- gap lane 上限为 4，目标 Topic 优先级为 high。

断言 planner 产出的前四个 `search_id` 正好是
`accelerator_io_datapath` 的四个 Direction，且任务仍只有一个 batch、四条独立 lane。

### Current-run replay

对 `2026-09-03-003948` 的 search 前 raw rows 做只读重放：

- 修复前为 `storage_media:magnetic_recording`、`optical_network:hybrid_network`；
- 修复后前四条为该 Topic 四个 Direction；
- 不创建任务、不修改 SQLite、不发送邮件，以测试或一次性只读诊断完成。

### Regression suite

- 运行 coverage、discovery、efficiency、historical backfill 和 Topic routing 的定向测试；
- 运行完整测试套件；
- 运行 `git diff --check` 并检查 `git status --short`；
- 验证本地 Markdown 链接；
- 不以真实邮件发送作为验收步骤。

## Acceptance criteria

- 生产 bootstrap 后，跨 Topic A 级记录不能让任一 Direction 返回 covered。
- 同 Topic 精确 Direction 与同 Topic 关键词兜底均保持可用。
- TPN 两项目规则不回归。
- 以本期 search 前数据重放时，新 Topic 四个 Direction 进入前四条 gap lane。
- 不改变任务 Schema、数据库结构、搜索总预算、Deep 门禁和发布行为。
- 定向测试和完整测试套件通过，当前文档与 `SKILL.md` 的覆盖规则同步。

## Documentation impact

实施时需要同步：

- `SKILL.md`：把“只补充 A 级覆盖缺口”精确为“只由同 Topic 的可用 A 级来源证明 Direction 覆盖”，并保留 TPN 两项目规则。
- 本设计文档：实现完成后记录实际文件、测试结果与只读重放证据，状态改为 `implemented`，再按设计生命周期移入 `docs/history/designs/` 并修复链接。

无需修改：

- `docs/architecture.md`：阶段所有权和数据流不变；
- `docs/operations/historical-backfill.md`：历史 lane 类型、轮转、预算和物化规则不变；
- prompts 与 schemas：Agent 输入输出契约不变；
- Topic/source/scoring 配置：本缺陷不是配置阈值或容量问题。

## Decision log

- 2026-09-03：确认核心根因是跨 Topic 关键词兜底假阳性，不是 Topic 配置未生效。
- 2026-09-03：接受“只统计 `topic_hint` 属于当前 Topic 的 A 级 item”作为最小行为修复。
- 2026-09-03：保留同 Topic 的 Direction 关键词兜底与 TPN 两项目规则。
- 2026-09-03：修复必须同时覆盖基础函数与 bootstrap 后实际生效的多项目函数；优先共享单行谓词，避免两份规则再次漂移。
- 2026-09-03：不把“下一期一定失败”写成确定事实；记录为在泛词 A 级来源持续存在时高度可复现。
- 2026-09-03：本次仅产出 draft 修复设计，不修改代码、配置、数据库或已发布 run。
