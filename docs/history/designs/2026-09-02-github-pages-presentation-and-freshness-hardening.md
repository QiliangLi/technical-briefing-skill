# GitHub Pages 呈现、新鲜度与分析补全方案

- Status: implemented
- Created: 2026-09-02
- Last updated: 2026-09-02

> 实现记录(2026-09-02):P0 与 P1 已实现并吸收进当前文档——manifest、
> freshness gate 与 Issue Change Projection 见 `docs/contracts/knowledge-materialization.md`
> 与 `docs/operations/knowledge-freshness.md`;首页/Roadmap 总览/Idea 诚实模式/
> 图谱概览与局部聚焦/对齐合同见 `docs/contracts/editorial-workbench-ui.md`;
> 数据流见 `docs/architecture.md`。2026-08-23/26/29 三期知识积压已按期次
> 顺序回填,manifest 处于 `knowledge_complete`。P2(真实 Idea 漏斗对象)
> 仍为后续工作。持久规则以当前文档为准,本文保留为设计记录。

## Problem and evidence

### 结论

当前问题不是一组可以只靠 CSS 收尾的“小瑕疵”，而是三类问题叠加：

1. **数据新鲜度问题**：公开归档已经到 `2026-08-29`，长期知识仍停在 `2026-08-17`；Roadmap、Idea 与首页判断因此天然落后三期。
2. **呈现投影问题**：首页直接把 Roadmap 首版 seed summary 当作“当前一句话判断”，没有独立的本期变化摘要；Idea Hub 也把尚不存在的 Candidate / Validation 数据结构画成了流程。
3. **布局和响应式问题**：部分组件的网格定义、不可换行状态标签、断点和画布适配互相冲突，造成越界、一字一行、图谱缩小到不可读和视觉错位。

修复顺序必须是：先让页面读取最新且语义正确的数据，再修任务流和信息架构，最后统一组件布局。否则只是把陈旧或含糊的内容排得更整齐。

### 1. 首页“本期最重要变化”同时存在内容和布局错误

线上首页显示“发生实质变化的 Topic = 0”，但下面仍列出 4 个 Topic，并把 `2026-08-17` 的首版知识摘要放在“本期最重要变化”中。这不是单纯文案不好，而是选择逻辑与标题语义冲突：

- `site/workbench-view.js` 中 `changedTopics` 按最新归档期次计算；
- 表格内容却使用 `roadmaps.slice(0, 4)`，只取最近更新的 4 个 Roadmap，不要求它们属于本期，也不要求发生实质变化；
- “本期新产生或更新的 Idea”也始终展示排序后的前三个 Idea，即使本期 Idea 状态变化为 0。

当前“一句话判断”来自 `knowledge/index.json` 的 `summary`。这些 summary 是首版 seed 文案，结构基本相同：已有 N 条专题证据，但不足以划分阶段，先保留证据时间线。它诚实地说明证据边界，但不能回答“当前技术判断是什么”或“本期改变了什么”。

布局上，首页表格声明的列宽合计为 `18% + 45% + 13% + 15% + 12% = 103%`，状态徽标又使用 `white-space: nowrap`。自动渲染检查显示：

- 1586px 和 1280px 时尚可容纳；
- 1024px 时“长期知识已更新”徽标宽 104px，所在单元格只有 92px，徽标越过单元格右边界；
- 768px 仍沿用桌面表格，徽标继续越界；只有 767px 以下才切换为定义卡片。

因此需要同时修正数据选择、显示字段和响应式断点，不能只加 `overflow: hidden` 掩盖问题。

### 2. Roadmap 入口只有下拉选择，不支持先浏览再进入

`#roadmaps` 当前没有 Roadmap 总览页。路由进入后自动选择第一个 Topic，并在详情页顶部提供原生 `<select>`。这要求用户先知道系统有哪些 Topic，再从下拉框中寻找目标；也无法快速比较哪些 Roadmap 最近变化、哪些长期未更新、哪些仍是 Signal Timeline。

Roadmap 当前还重复使用同一份 seed summary 作为“当前一句话判断”。即使去掉下拉框，如果没有 Current State、本期 diff 和证据状态的独立字段，总览卡片仍会重复展示无信息量的模板句。

### 3. 知识图谱的“乱码”、左栏和画布问题都有明确原因

#### 构建输入摘要不是乱码，但不应作为用户级状态

页面显示的 `sha256:458da83cc0` 是 `knowledge/graph.json.input_digest` 的截断校验摘要。它对构建诊断有用，但“构建输入摘要”这个名称会让普通读者以为它是内容摘要。用户第一屏真正需要的是归档水位、知识水位、是否完成分析和构建时间；原始 digest 应进入可展开的技术诊断区。

#### 左栏“一行只有一个字”是网格子元素错位

`.graph-filter-row` 定义了 `18px minmax(0, 1fr) auto` 三列，但透镜和期次链接只渲染 `<span>` 与 `<b>` 两个子元素。文字 `<span>` 因而进入第一列，实际宽度只有 18px。自动渲染检查显示：

- “结构”在 18px 宽度中渲染为 34px 高；
- “编辑判断”渲染为 68px 高；
- “仅最近一期”渲染为 85px 高。

这是确定的组件 bug，不是字体或浏览器兼容问题。

#### 默认结构图把 40 个节点强行 fit 到狭窄画布

默认结构透镜包含 9 个 Topic、31 个 Direction，共 40 个节点和 31 条边。其预设坐标跨度约为 `848 × 1176`，而实际画布宽度为：

- 1586px 视口：约 920px；
- 1280px 视口：约 654px；
- 1024px 视口：约 458px。

全量 `fit` 后，节点和文字必然缩小；图虽然“完整地存在”，但不能阅读。右侧详情和左侧筛选进一步挤压了画布。当前默认焦点只把其他节点变淡，没有把视口聚焦到可读的一跳范围，所以既看不清全局，也看不清局部。

#### 移动端虽不挂载画布，但列表过长

767px 以下改用分层路径与关系列表，避免了小屏画布，但当前结构视图仍可能把大量节点和关系一次铺开。自动检查中，知识图谱页面高度约为：

- 767px 宽：4394px；
- 414px 宽：10378px；
- 320px 宽：21212px。

这说明移动降级虽然技术上完整，实际浏览成本仍过高，需要按当前对象分组、折叠和分页，而不是把完整关系表纵向展开。

### 4. “文字没有居中”应拆成组件对齐合同

当前 `.data-table th, td` 统一使用 `text-align: left; vertical-align: top`，状态徽标、日期、短枚举和操作入口也继承这套规则；其他卡片则混用 `grid`、`flex` 和不同高度。因此视觉上会出现状态悬在单元格左上角、图标与文字基线不一致、同一行控件上下错位。

不建议把所有文字一律居中：长判断、证据摘要和来源标题居中会明显降低阅读性。需要建立语义化对齐规则：

- 长文本、标题、判断、证据摘要：左对齐、顶部对齐；
- 状态、类型、短枚举、日期：水平与垂直居中；
- 数量：右对齐或按指标卡统一居中；
- 图标与单行标签：垂直居中；
- CTA：点击区域至少 44px，高度和文字基线一致。

### 5. Idea Hub 目前不是一个真实的三阶段漏斗

用户无法理解 Candidate Inbox → Idea Portfolio → Validation 的迁移，是因为当前实现没有对应的持久化状态流：

- `candidates` 在前端被硬编码为 `[]`；
- Portfolio 是除少数 validation 状态外的所有正式 Idea；
- Validation 只是按 Idea status 枚举过滤；
- 每个 Idea 虽有 `validation_plan`，但合同要求 `execution_status = suggestion_only`，没有 Experiment Run 或 Result；
- 页面没有 Transition Event、进入条件、离开条件、阻塞原因或箭头说明。

因此三个并排栏目目前只是三个集合，不是一个可观察的流程。继续用空的左栏和右栏暗示漏斗，会让用户误以为数据漏了或功能坏了。

### 6. “没有同步到最新一期”包含两个不同层次

#### 已确认：长期知识没有同步到最新已发布归档

当前仓库和线上页面一致：

- `archive/index.json` 最新期次为 `2026-08-29`；
- `knowledge/graph.json.archive_through_issue` 为 `2026-08-29`；
- `knowledge/graph.json.knowledge_through_issue` 为 `2026-08-17`；
- `workspace/knowledge/` 没有 `2026-08-23`、`2026-08-26`、`2026-08-29` 的任务；
- `knowledge/applications/` 为空。

归档发布路径只提交 `archive/index.json` 与本期 archive 目录。Pages workflow 会重新 build graph，但 `knowledge validate` 只验证 Schema 和引用正确性，不要求知识水位追上 archive head。因此发布可以成功，图谱也可以“新鲜地重建一份陈旧知识”。

#### 尚未确认：是否还应存在 2026-08-29 之后的新日报

当前主机的生产 run 最晚为 `2026-08-29-092621`，没有更晚的 run 目录；用户 crontab 也未安装任何任务，仓库中只有 `scripts/install-cron.example`。如果“最新一期”指 8 月 29 日之后应生成的新日报，这是生产调度/日报生成缺口，不是 Pages 同步问题，需要单独诊断运行入口和调度所有者。

### 7. 当前确实缺少面向呈现的后处理分析

现有前端只能在以下两种不理想方案中二选一：

- 直接展示长期 Roadmap seed summary，得到模板化“废话”；
- 在浏览器根据条目标题临时推断“本期变化”，破坏证据边界和可追溯性。

正确方案是在长期知识完成物化后，生成一份有证据绑定的 **Issue Change Projection**。它是面向首页和 Roadmap 总览的发布投影，不是新的事实来源，也不由前端自由总结。

## Goals and non-goals

### Goals

- 首页只展示本期真实 material change、明确的 no-op 或“等待分析”，不再用旧 Roadmap 填满表格。
- Roadmap 提供可浏览总览，详情页不再依赖下拉框作为唯一入口。
- 知识图谱默认可读，筛选器不再一字一行，技术 digest 不再冒充内容摘要。
- Idea Hub 诚实表达当前已有的数据能力，并为未来真实 Candidate / Validation 流保留清晰迁移路径。
- 统一状态、日期、数字、长文本和 CTA 的对齐规则，并用多视口自动检查防止回归。
- 新归档发布后自动产生可观察的知识更新任务；Pages 不再把“Schema 合法”误当成“知识已最新”。
- 当已有数据不足以支撑展示时，通过有界分析任务补全发布投影，而不是在前端猜测。

### Non-goals

- 本设计不改变邮件发送必须显式确认的规则。
- 不让邮件发送等待长期知识分析；Archive 可以先发布，但必须明确显示 `analysis_pending`。
- 不从 Reader 文案、候选池或浏览器关键词推断正式 Roadmap / Idea 关系。
- 不在静态 GitHub Pages 中实现真实审批、实验执行或写回。
- 不追求在一个视口中同时显示全部 335 个图谱节点；“完整”指当前明确范围内不静默缺失，并提供可达的总览与列表。
- 本次为设计文档，不直接修改生产代码、数据或发布状态。

## Constraints and invariants

- Archive、Roadmap、Idea 和图谱的证据边界继续遵守现有 materialization 合同。
- 邮件运输、归档发布和知识发布保持三个独立、幂等的状态；知识失败不能触发邮件重发。
- 旧知识 snapshot 在新 snapshot 完整校验前继续可读，不能逐文件暴露半更新状态。
- 每个 affected Topic 必须有 `applied`、`no_material_change` 或显式 `deferred/error` 结果，不能静默跳过。
- 前端不生成“支持、反对、演进、因果”等新关系。
- 当前公开站点继续只读；用户操作如果只是浏览器本地状态，必须明确标注。
- 旧深链继续可访问；Roadmap 总览和图谱聚焦不能破坏 `topic`、`branch`、`lens`、`node` 等参数。

## Proposed design

### 1. 新鲜度状态从两个日期升级为可执行 manifest

新增发布级 `knowledge/manifest.json`，至少包含：

```json
{
  "archive_head_issue": "2026-08-29",
  "analysis_target_issue": "2026-08-29",
  "materialized_through_issue": "2026-08-17",
  "publication_state": "analysis_pending",
  "pending_issues": ["2026-08-23", "2026-08-26", "2026-08-29"],
  "affected_topics": 0,
  "completed_topics": 0,
  "snapshot_id": "knowledge-...",
  "generated_at": "..."
}
```

`publication_state` 至少区分：

- `archive_only`：归档已发布，尚未准备知识任务；
- `analysis_pending`：任务已准备或执行中；
- `knowledge_complete`：所有 affected Topic 已应用或显式 no-op，完整 snapshot 已发布；
- `analysis_failed`：保留旧 snapshot，并展示失败期次和恢复入口。

Pages 门禁不应简单禁止 archive 先上线，而应做到：

- `archive_only / analysis_pending` 可以发布归档和明确告警；
- 首页不得把旧 summary 伪装成本期变化；
- 只有 `knowledge_complete` 才展示本期 Roadmap / Idea diff；
- manifest 声明 `knowledge_complete` 但水位不一致时，Pages 构建必须失败。

### 2. 新日报后的知识更新流程

建议流程为：

```text
邮件发送成功
→ Archive 幂等归档并发布
→ 写入 manifest: archive_only
→ 自动 prepare 本期 affected Topic 的有界知识任务
→ 写入 manifest: analysis_pending
→ 按任务队列执行 Roadmap / Idea 分析
→ 所有任务 apply 或显式 deferred
→ 构建完整 candidate snapshot
→ Schema、语义、覆盖、新鲜度与图谱校验
→ 原子切换 current snapshot
→ 生成 Issue Change Projection
→ 写入 manifest: knowledge_complete
→ 再次部署 Pages
```

当前积压的 `2026-08-23`、`2026-08-26`、`2026-08-29` 应按期次顺序补齐，以保留逐期 change log；不能只把 8 月 29 日作为一次总回填而丢掉中间判断变化。

### 3. 增加 Issue Change Projection，补足呈现所需分析

新增例如 `knowledge/issue-diffs/<issue_date>.json` 的派生投影：

```json
{
  "issue_date": "2026-08-29",
  "knowledge_snapshot_id": "knowledge-...",
  "status": "complete",
  "topic_changes": [
    {
      "topic_id": "tpn",
      "change_kind": "material_change",
      "current_judgement": "一句可行动的当前判断",
      "what_changed": "本期相对上一快照的变化",
      "why_it_matters": "对技术选择或项目问题的影响",
      "evidence_state": "supported_with_limits",
      "confidence": "medium",
      "evidence_item_ids": ["..."],
      "roadmap_version": 2
    }
  ],
  "idea_events": []
}
```

内容约束：

- `current_judgement` 回答“现在怎么看”，不能只报告文章或证据数量；
- `what_changed` 回答“与上一快照相比变了什么”；
- `why_it_matters` 回答“为什么值得进入首页”；
- 每条变化必须绑定证据 ID 和 snapshot；
- 无 material change 时返回空数组，首页显示真实空状态；
- semantic validator 拒绝“现有公开归档积累了 N 条证据”“首版先保留时间线”等 seed 模板进入首页判断字段；
- 前端只渲染投影，不自行综合。

### 4. 首页改为“变化优先、状态诚实”

首页第一屏采用以下逻辑：

1. 顶部水位显示归档、分析目标、知识快照和当前状态。
2. “本期最重要变化”只读取本期 Issue Change Projection。
3. 若 `analysis_pending`，显示“本期已归档，长期判断正在分析”，并给出 affected / completed Topic 数；不回填旧 Roadmap。
4. 若本期无 material change，显示空状态和重要 no-op 数量，不为了视觉丰满列旧 Topic。
5. “本期 Idea 更新”同样只显示本期 event；没有 event 时不展示历史前三条。

表格列建议改为：

| Topic | 本期变化 | 当前判断 | 证据状态 | 影响对象 |
| --- | --- | --- | --- | --- |

“更新期次”不必在每行重复，因为区块已经绑定本期期次；旧知识或 pending 状态放到区块级提示。状态列使用可换行的短标签，如“已物化”“待分析”“无实质变化”，不使用可能撑破单元格的长句。

### 5. Roadmap 增加总览页，详情页取消下拉依赖

#### `#roadmaps` 总览

默认显示所有 Topic 的 Roadmap 目录卡或紧凑表格，每项至少包含：

- Topic 名；
- Current State / 当前判断；
- 当前模式（Signal Timeline / Landscape / Trajectory）；
- 最近 material change 期次；
- 证据状态和知识 lag；
- branch 数和 Open Question 数；
- “查看 Roadmap”明确入口。

支持按“本期变化、待补证据、长期未更新、Topic”筛选。用户先浏览全局，再进入详情。

#### `#roadmaps?topic=<id>` 详情

- 顶部使用面包屑返回 Roadmap 总览；
- 提供上一个 / 下一个 Topic 或搜索入口，原生下拉不再是主导航；
- 显示 Current State、本期 structured diff、Track、Milestone、Open Question 和证据边界；
- 旧链接继续直达同一 Topic / branch。

### 6. 知识图谱改成“先看清局部，再获得全局”

#### 状态区

- 第一屏显示“日报结构更新至”“长期知识更新至”“分析状态”“构建时间”；
- 把 digest 移入“技术信息”折叠区，名称改为“输入校验码”，提供复制按钮；
- 不再把 `sha256:` 值称为摘要。

#### 左栏

- 修复 filter row 子元素与三列网格不匹配的问题；无图标的链接使用 `minmax(0, 1fr) auto` 两列，或显式补齐图标列；
- 透镜和期次改成紧凑 segmented control / radio group，不与 Topic、Direction 下拉混用同一行组件；
- Topic 先筛选 Direction，避免一次展示 31 个无上下文选项；
- 桌面左栏可折叠，释放画布宽度。

#### 画布

- 无 Topic 参数时，默认“全局概览”只显示 9 个 Topic 聚类卡和数量，不同时绘制全部 31 个 Direction 标签；
- 点击 Topic 后进入完整的 `Topic → Direction` 局部图，当前范围内节点全部可读；
- 点击 Direction 再按期次展开 Item / Judgement；Roadmap 和 Idea 仍作为可选叠层；
- 初次进入局部图时 fit 当前连通分量或焦点一跳，不 fit 全部 40 个节点；
- 提供“查看全局概览”和“聚焦当前对象”两个明确动作；
- 画布状态显示“当前范围 X / 全图 Y 个节点”，达到上限时说明裁剪原因。

#### 右栏与移动端

- 右侧详情允许折叠或进入抽屉模式，1280px 以下优先保证画布宽度；
- 1024px 和 768px 不再同时固定占用左栏、窄画布和右栏；
- 移动端只加载当前 Topic / Direction 的分层路径；关系表按 20 条分页或折叠，不把数百关系一次铺成 1–2 万像素长页面；
- DOM 关系列表继续是完整、可访问的真相来源。

### 7. Idea Hub 分两阶段处理

#### 近期诚实模式

在没有真实 Candidate 对象和 Experiment Run 之前：

- 移除三个并排“漏斗栏”的暗示；
- 页面主体改为正式 Idea Portfolio，按实际状态分组；
- 每张卡显示“为什么进入当前状态”“下一道门槛”“最大阻塞”“验证建议尚未执行”；
- 页面顶部用一条只读生命周期说明解释目标流程，但把不可用阶段标为“尚未建立数据对象”；
- Candidate 和 Validation 计数如果没有数据源，显示“未启用”，不要显示看似真实的 0。

#### 完整漏斗模式

只有新增以下真实对象后，才恢复 Candidate → Portfolio → Validation 三段：

- `IdeaCandidate`：origin、触发 Claim、去重结果、接受/拒绝事件；
- `IdeaTransitionEvent`：from、to、gate、actor、reason、snapshot；
- `ValidationPlan`、`ExperimentRun`、`ExperimentResult`：建议、批准、执行和结果分离。

届时页面明确显示：

```text
Candidate 提案
  --接受且通过身份去重门槛--> 正式 Idea
  --证据与验证计划达到门槛--> Ready to Validate
  --批准并创建 Run--> Validation
  --结果回流--> Promising / Inconclusive / Rejected / Proposal Candidate
```

对象可以从左向右，也可以因证据不足返回 Portfolio、因重复被合并、因结果不明确再次验证。页面应显示实际 event，不把列的位置当作状态机。

### 8. 建立统一组件对齐与溢出合同

新增以下 UI 规则并落实为共享 class / component option：

| 内容类型 | 水平对齐 | 垂直对齐 | 换行 |
| --- | --- | --- | --- |
| 标题、判断、摘要、来源 | 左 | 顶部 | 允许 |
| 状态、类型、日期、短枚举 | 中 | 中 | 必要时两行 |
| 数量 | 右或指标卡居中 | 中 | 不换行 |
| 图标 + 单行标签 | 左 | 中 | 标签可省略 |
| CTA / 操作 | 中 | 中 | 不换行，最小 44px |

具体约束：

- 列宽总和必须小于等于 100%，优先使用 `minmax()` 和内容优先级，不依赖相互冲突的百分比；
- 状态徽标使用 `max-width: 100%`，禁止溢出单元格；长状态改成短 label + tooltip / 辅助说明；
- 768px 平板宽度不再保留无法容纳的桌面表格，可提前在 1024px 或根据容器宽度切换 card layout；
- 所有 grid / flex 子项显式 `min-width: 0`；
- `overflow-x: clip` 只是最后防线，测试必须检查实际元素边界，不能以“页面没有滚动条”作为无溢出的证明。

### 9. 实施优先级

#### P0：让页面说真话

- 补齐 2026-08-23、08-26、08-29 的知识任务与 snapshot；
- 增加 manifest 和 freshness gate；
- 首页 pending / empty 状态不再回填旧 Roadmap / Idea；
- 修复表格状态越界、知识图谱 filter row 18px 错位和 1024px 画布布局；
- 将 digest 移入技术信息；
- Idea Hub 切换为诚实模式。

#### P1：补足呈现分析

- 增加 Issue Change Projection、semantic validator 和本期 diff；
- Roadmap 总览与 Current State；
- 图谱 Topic 聚类概览和局部聚焦；
- 移动关系列表折叠 / 分页。

#### P2：真实 Idea 漏斗

- Candidate、Transition、Validation Plan / Run / Result 对象；
- 基于事件的状态迁移和回流；
- 公共只读投影与内部操作面分离。

## Compatibility and migration

- 现有 `archive/`、Roadmap 和 Idea 文件不就地改写；新 manifest 和 issue diff 是可重新生成的发布投影。
- `#roadmaps?topic=<id>&branch=<id>`、`#knowledge?...` 和 Idea 深链保持兼容。
- 首次上线 Roadmap 总览时，裸 `#roadmaps` 不再自动选择第一个 Topic；带 `topic` 的旧链接行为不变。
- 在 Candidate / Validation 对象上线前，现有 Idea status 仍可读，但页面不把 `suggestion_only` 解释为正在执行实验。
- 当前三期知识积压按期次顺序重物化；每期完成后保留 application 和 snapshot 记录。
- 如果新 Issue Change Projection 不可用，页面降级为“分析未完成”，不回退到浏览器推断或 seed summary。

## Failure, recovery, and rollback

- 知识任务失败时保留上一份 `knowledge_complete` snapshot，manifest 标记 `analysis_failed`，Archive 继续可读。
- 单个 Topic 失败不能发布半更新知识；修复后从同一有界任务重试。
- Pages 若发现 manifest、知识水位、graph digest 或 issue diff snapshot 不一致，停止知识完成态发布。
- Issue Change Projection 失败不覆盖上一份文件；首页显示 pending / failed，而不是旧内容冒充本期内容。
- 前端图谱渲染失败时继续显示关系与节点列表；局部聚焦方案不改变这一降级合同。
- 回滚前端时可以恢复现有页面实现；新 manifest 和投影都是附加文件，不要求回滚 Archive。

## Verification

### 数据与新鲜度

- 发布新 Archive 后，manifest 在一次流程中可观察地经历 `archive_only → analysis_pending → knowledge_complete`；
- 最新 archive 的每个 affected Topic 都有 applied / no-op / deferred 记录；
- `materialized_through_issue == archive_head_issue` 才允许 `knowledge_complete`；
- 2026-08-23、08-26、08-29 三期顺序回填后，Roadmap / Idea change log 可逐期追溯；
- graph、issue diff 和 knowledge snapshot 使用同一 snapshot ID；
- 重跑 prepare、apply、snapshot 和 deploy 不产生重复事件。

### 首页与 Roadmap

- 本期 material change 为 0 时，表格不出现旧 Topic；
- 本期 Idea event 为 0 时，不显示历史前三条作为本期更新；
- `analysis_pending` 时只显示 pending 状态和进度；
- 首页判断字段不包含 seed 模板句；
- 裸 `#roadmaps` 展示总览，带 `topic` 的链接进入准确详情。

### 布局与响应式

在 1586、1440、1280、1024、768、767、414、375、320px 验收：首页、Roadmap 总览/详情、Idea Hub、知识图谱三透镜和归档。

- 任一可见元素的 `getBoundingClientRect()` 不越过 viewport 或所属 cell；
- 状态徽标不越界、不被裁掉；
- filter row 文本列宽大于等于可用行宽减去计数和图标，不出现一字一行；
- 1024px 下知识图谱画布可读，右栏不把画布压缩到 500px 以下；
- 默认局部图节点正文的屏幕字号不低于 12px；
- 320px 知识图谱首屏与当前对象路径不需要浏览超过 4 个屏幕高度才能到达关系列表入口；
- 表格在无法容纳时切换 card layout，而不是只隐藏溢出。

### Idea Hub

- 没有 Candidate 数据源时显示“未启用”，不显示伪 0；
- `suggestion_only` 始终标为“验证建议，尚未执行”；
- 完整漏斗上线后，每次跨栏都能展开对应 Transition Event 和 gate；
- 结果回流、重复合并、返回补证据和 inconclusive 均有测试，不能只测试单向 happy path。

## Documentation impact

实现时需要同步：

- `docs/contracts/editorial-workbench-ui.md`：Roadmap 总览、首页 diff、Idea 诚实模式、图谱局部聚焦和响应式对齐合同；
- `docs/contracts/knowledge-materialization.md`：manifest、freshness gate、Issue Change Projection、snapshot 与积压恢复；
- `docs/architecture.md`：Archive 发布后知识分析、snapshot 和二次 Pages 部署的数据流；
- `docs/operations/`：新增知识积压、调度缺失、analysis_failed 和 Pages 新鲜度诊断手册；
- `schemas/` 与 `prompts/`：manifest、issue diff，以及未来 Candidate / Transition / Experiment 对象；
- `README.md`：若公开浏览路径或运维命令发生变化，更新入口说明。

## Decision log

### 2026-09-02：呈现问题按 correctness、projection、layout 三层处理

基于线上页面、当前数据文件、发布 workflow 和多视口渲染检查，确认不能把本轮工作限定为 CSS 修补。新鲜度和展示语义优先于视觉润色。

### 2026-09-02：首页不再用旧 Roadmap 填满“本期变化”

用户明确指出当前一句话判断没有价值。设计决定新增有证据绑定的 Issue Change Projection；无变化或分析未完成时展示真实状态。

### 2026-09-02：Roadmap 先总览后详情

用户明确认为下拉选择麻烦。裸 `#roadmaps` 改为可浏览目录，详情保留深链但不再依赖 select 作为主入口。

### 2026-09-02：知识图谱默认展示可读局部

全量 fit 在当前三栏画布中不可读。设计决定用 Topic 聚类概览进入局部图，并保留关系总数、列表与全局入口，不把“同时画出全部标签”当作完整性。

### 2026-09-02：没有真实状态对象时不展示伪漏斗

Candidate 目前是前端硬编码空数组，Validation 没有执行对象。近期页面采用诚实 Portfolio 模式；只有数据模型补齐后恢复基于事件的三阶段流程。

## Open questions

1. 如果用户预期 2026-08-29 之后已经产生新日报，需要另行确认实际调度入口和运行主机；当前仓库与本机状态没有该期次。
2. Candidate、Validation Run 和 Result 的真实写入面由现有任务队列、内部管理页还是其他系统承担，需要在 P2 实现前确定；公开 GitHub Pages 继续只读。
