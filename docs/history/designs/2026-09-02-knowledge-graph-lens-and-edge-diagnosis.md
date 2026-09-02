# 知识图谱长边与透镜区分度诊断

- Status: implemented
- Created: 2026-09-02
- Last updated: 2026-09-02

> 实现记录(2026-09-02):P0 与 P1 已实现并吸收进当前文档——透镜局部布局、
> 默认焦点、首屏集合、透镜状态条、空状态与边长验收见
> `docs/contracts/editorial-workbench-ui.md`(Lens layout, focus, and
> empty-state contract 一节);`site/knowledge-layout.js` 的模块所有权见
> `docs/architecture.md`;线上/仓库联合发布检查见
> `docs/operations/knowledge-freshness.md`。`knowledge/graph.json.position`
> 保留为兼容/调试坐标,Topic 局部视图不再使用。持久规则以当前文档为准,
> 本文保留为诊断记录。

## Problem and evidence

### 结论

当前现象由三个相互叠加的问题造成，不是单纯的边样式或缩放参数问题：

1. **局部筛选仍复用全图坐标**：日报条目、期次和编辑判断按全图顺序排布。筛选到单个 Topic 后，中间大量不可见节点留下坐标空洞，边仍跨越这些空洞。
2. **三个透镜使用同一个首屏焦点与一跳视口**：结构、演化、编辑判断都以 Topic 为默认焦点，而 Topic 的一跳邻居只有 Direction。演化新增的 Item/Issue、编辑判断新增的 Item/Judgement 位于二跳或三跳之外，首屏被压暗并裁到视口之外。
3. **部分 Topic 确实没有透镜专属数据**：在所选期次没有 Item 或 Judgement 时，当前页面退化为同一份 Topic/Direction 骨架，却没有说明“本透镜无数据”，因此数据为空和切换失败在视觉上完全相同。

因此，继续调 `spacingFactor`、字体大小或边曲率只能改变症状，不能解决透镜的语义和可读性。需要按透镜生成**当前筛选范围内的局部布局**，并为每个透镜定义不同的默认焦点、首屏范围和空状态。

### 复现范围

本诊断以 2026-09-02 当前工作区的未提交实现和 `knowledge/graph.json` 为准，使用以下路由复现：

- `#knowledge?lens=structure&topic=agent_acceleration&range=recent3`
- `#knowledge?lens=evolution&topic=agent_acceleration&range=recent3`
- `#knowledge?lens=judgements&topic=agent_acceleration&range=recent3`

当前本地发布数据为：

| 项目 | 值 |
| --- | ---: |
| 归档水位 | 2026-08-29 |
| 长期知识水位 | 2026-08-29 |
| 全图节点 | 338 |
| 全图边 | 750 |
| Topic | 9 |
| Direction | 31 |
| 日报条目 | 228 |
| 编辑判断 | 24 |

线上 `https://qiliangli.github.io/technical-briefing-skill/` 在本次检查时仍是旧发布：长期知识水位为 2026-08-17，并仍显示截断的 SHA 构建摘要。它没有包含当前工作区的新实现，所以线上状态是一个独立的部署缺口，不能拿来否定或确认本地新布局是否正确。

### 证据一：三个透镜的数据其实不同，但首屏一跳完全相同

`agent_acceleration` 最近三期的显示模型为：

| 透镜 | 节点 | 边 | 节点构成 | 关系构成 |
| --- | ---: | ---: | --- | --- |
| 结构 | 5 | 4 | Topic 1、Direction 4 | `has_direction` 4 |
| 演化 | 20 | 28 | Topic 1、Direction 4、Item 12、Issue 3 | `has_direction` 4、`has_item` 12、`published_in` 12 |
| 编辑判断 | 21 | 24 | Topic 1、Direction 4、Item 12、Judgement 4 | `has_direction` 4、`has_item` 12、`supports_judgement` 8 |

说明透镜投影本身确实增加了不同对象。问题发生在投影之后：

- `buildKnowledgeGraphModel()` 在三个透镜中都把 `topic:agent_acceleration` 设为默认 `focusId`；
- `GraphRenderer.applyFocus()` 只保留焦点节点的 `closedNeighborhood()` 为高亮，其余节点透明度降为 0.32、其余边降为 0.1；
- `knowledge-graph-view.js` 对任何带 `topic` 的路由都执行 `handle.fitFocus()`，没有限制为结构透镜；
- Topic 的一跳邻居在三个模型中都是同样的 4 个 Direction；Item、Issue 和 Judgement 至少在二跳以外。

所以三个透镜首屏都被适配成同一个“Topic + 4 个 Direction”画面。演化和编辑判断的专属节点虽然存在于模型和关系列表中，却不在首屏可读区域内。这正是“切了透镜但看不出差别”的主要原因。

### 证据二：`≤12` 的布局阈值造成不连续切换

当前实现仅在满足以下条件时使用局部 `breadthfirst` 布局：

```text
有 topic 参数，并且当前模型节点数 ≤ 12
```

因此同一个 Topic 会出现不连续行为：

- 结构透镜 5 个节点，使用 `breadthfirst`；
- 演化透镜 20 个节点，改用 `preset`；
- 编辑判断透镜 21 个节点，改用 `preset`。

节点数 12/13 并不是语义边界。它使页面在切换透镜、期次或 Direction 时突然换用完全不同的坐标体系，也使小数据 Topic 看起来正常、大数据 Topic 突然出现极长边。`spacingFactor` 只作用于 `breadthfirst`，对出现问题的两个 `preset` 透镜没有作用。

### 证据三：全图绝对坐标制造了 1–2 万单位的长边

构建器对节点位置的分配方式是：

- Topic/Direction 按 Topic 分组放在左侧；
- 228 个 Item 按全图的 `issue_date + id` 统一排序，纵向间距为 90；
- Issue 按全图期次统一排序，纵向间距为 110；
- Judgement 按全图统一排序，每列 10 个，纵向间距为 130；
- 筛选后的显示模型原样保留这些绝对坐标，不压缩被过滤掉的行。

`agent_acceleration` 最近三期的边长统计直接反映了这个问题：

| 透镜 / 关系 | 数量 | 最短 | 中位数 | 最长 |
| --- | ---: | ---: | ---: | ---: |
| 结构 / `has_direction` | 4 | 260 | 652 | 848 |
| 演化 / `has_item` | 12 | 11,792 | 15,591 | 19,441 |
| 演化 / `published_in` | 12 | 11,139 | 14,807 | 18,565 |
| 编辑判断 / `has_item` | 12 | 11,792 | 15,591 | 19,441 |
| 编辑判断 / `supports_judgement` | 8 | 11,608 | 15,606 | 19,339 |

最长的 `has_item` 边从“Agent工具执行链优化”连到“失败反馈反使小模型Agent重复失败调用”，横向只差 212，纵向却差 19,440。它不是一个需要更漂亮曲线的正常长关系，而是全图排序坐标在局部过滤后留下约 216 个 Item 行距造成的空洞。

使用 `bezier` 只会把这条长线画成一条更长的曲线；把整个模型 `fit` 进画布则会把节点和文字缩到不可读。两者都不是可接受的修复。

### 证据四：部分 Topic 在当前期次确实没有透镜差异

最近三期数据中：

- `ai_infra_horizontal` 的结构、演化、编辑判断均为 3 节点 / 2 边，只有 Topic 1 + Direction 2；
- `dpu_inline` 的三种透镜也均为 3 节点 / 2 边；
- `tpn` 的编辑判断透镜有 17 节点 / 16 边，但没有任何 Judgement 或 `supports_judgement`，实际只是 Topic/Direction/Item 骨架；
- `frontier_exploration` 的演化和编辑判断都达到 60 节点软上限并被裁剪，透镜专属节点更容易被共同骨架淹没。

这些情况需要诚实的透镜空状态或范围提示。当前页面继续展示共同骨架，会让用户无法区分“没有符合条件的数据”和“透镜切换没有生效”。

### 根因分级

| 优先级 | 根因 | 所属层 |
| --- | --- | --- |
| P0 | 过滤后的局部模型复用全图绝对坐标 | 图谱布局投影 |
| P0 | 所有 Topic 路由无条件执行 Topic 一跳聚焦 | 视口与交互 |
| P0 | `≤12` 节点阈值在 `breadthfirst` 与 `preset` 间切换 | 布局选择 |
| P1 | 演化和编辑判断没有透镜专属默认焦点与首屏语法 | 信息架构 |
| P1 | 透镜专属对象为零时仍渲染共同骨架 | 空状态 |
| P1 | 指标区始终展示全图总量，缺少当前透镜对象统计 | 状态反馈 |
| 独立发布问题 | GitHub Pages 尚未部署当前工作区版本 | 发布流程 |

## Goals and non-goals

### Goals

- 每个透镜的首屏直接呈现该透镜要回答的问题，而不是都停留在 Topic 一跳骨架。
- 单个 Topic/Direction 的局部图不再携带全图过滤后的坐标空洞。
- 演化透镜能直接看出“哪些 Direction 在哪些期次出现了什么条目”。
- 编辑判断透镜能直接看出“判断是什么、由哪些显式证据条目支持”。
- 没有透镜专属数据时显示明确空状态，不能伪装成另一种成功图谱。
- 保持现有显式关系、证据边界、关系列表完整性和深链兼容。
- 用自动化边长、焦点和截图检查防止同类问题回归。

### Non-goals

- 不改变 `has_direction`、`has_item`、`published_in`、`supports_judgement` 的方向或语义。
- 不为了缩短边而推断、合并或删除真实关系。
- 不要求一个视口同时展示全图 338 个节点。
- 不在前端根据标题或关键词生成新的演化、支持或因果关系。
- 本文只完成诊断和设计，不直接修改页面实现或部署 GitHub Pages。

## Constraints and invariants

- `knowledge/graph.json` 继续是可重建的派生发布物，Archive、Roadmap、Idea 保持各自证据边界。
- 画布和关系列表必须来自同一份过滤后的显示模型；布局可以改变位置，不能改变节点与边集合。
- 每条已绘制边必须具有两个已解析端点和 provenance；未解析引用继续单独展示。
- 前端布局只能使用显示模型中已经存在的 kind、relation、issue date 和稳定 ID，不得生成新的语义关系。
- URL 中显式给出的有效 `node` 优先于透镜默认焦点；无效节点继续显示回退说明。
- 移动端仍使用分层路径和关系列表，不因桌面布局调整而重新挂载大画布。
- 关系表的完整性、20 行分页、键盘选择、节点详情和 URL 同步不能回归。

## Proposed design

### 1. 把“显示模型”和“局部布局”分开

新增一个纯函数式的局部布局层，例如 `site/knowledge-layout.js`：

```text
knowledge/graph.json
  → buildKnowledgeGraphModel()       只决定当前可见节点与边
  → buildKnowledgeLensLayout(model)  只为当前模型生成确定性坐标与初始视口
  → GraphRenderer                    只挂载、选择、缩放和绘制
```

布局层可以读取现有节点 kind、关系、期次和稳定 ID来排序，但不得新增或改写边。这样既不破坏 `site/data-contract.js` “不生成布局坐标”的职责，也避免把语义推断塞进通用渲染器。

`knowledge/graph.json.position` 暂时保留为兼容或调试坐标，但 Topic 局部视图不再把它作为首选。不能再用节点数量阈值决定布局算法；布局由 `lens` 和当前明确范围决定。

### 2. 为三个透镜定义不同的视觉语法

#### 结构透镜

- 内容：Topic + Direction；叠层开启时再加入 Roadmap/Idea 影响对象。
- 布局：Topic 在左或上，Direction 使用紧凑的两行/多列树状布局。
- 默认焦点：Topic，适配整个局部骨架；只有显式选中节点时才聚焦该节点一跳。
- 首屏回答：这个 Topic 由哪些稳定 Direction 构成。

#### 演化透镜

- 内容：Direction、最近范围内的 Item、Issue；Topic 作为标题上下文，不必占据画布中心。
- 布局：Issue 作为时间列，Direction 作为泳道；Item 放在“Direction × Issue”的对应区域。
- 边路由：`has_item` 沿 Direction 泳道连接，`published_in` 连接到相邻期次表头或短垂线，不能跨越多个空泳道。
- 默认焦点：若 URL 指定 Direction，则聚焦该 Direction 的时间片；否则选最近一期有活动的 Direction，并在界面上明确显示“自动聚焦：…”。
- 首屏回答：最近三期哪些方向发生了什么变化，而不是先重复 Topic 骨架。

如果一个 Topic 的 Direction 太多，先显示每条 Direction 的本期/近三期计数与最近条目，点击后进入单 Direction 时间线；不能把 60 个节点缩到一个视口。

#### 编辑判断透镜

- 内容：Judgement + 其显式 `supports_judgement` Item；Topic/Direction 只作为上下文标签或弱化的上游节点。
- 布局：以 Judgement 为中心的证据簇，证据 Item 放在其左侧或周围；多个 Judgement 按期次分组，不复用全图判断列坐标。
- 默认焦点：最新 Judgement，而不是 Topic；适配该 Judgement 与全部直接证据。
- 首屏回答：当前有哪些编辑判断，每条判断由哪些明确条目支持。

如果当前范围没有 Judgement，显示“最近三期没有带显式证据引用的编辑判断”，并提供“扩大到全部期次”或“返回结构”的入口；不能继续显示 Item 骨架并把它当作编辑判断透镜。

### 3. 修正初始焦点和适配规则

建议优先级：

1. URL 中有效的 `node`；
2. 透镜专属默认焦点；
3. 当前透镜的明确空状态；
4. 最后才回退到 Topic。

初次挂载时：

- 结构透镜适配完整局部骨架；
- 演化透镜适配当前 Direction 的最近时间片，至少包含 Direction、Item 和 Issue；
- 编辑判断透镜适配最新 Judgement 的证据簇；
- `fitFocus()` 不再对所有带 `topic` 的路由无条件执行；
- 用户点击“聚焦当前对象”时才执行与当前节点相符的一跳/两跳适配。

为了让用户能确认切换已经生效，画布状态条应从单一的“当前范围 N 节点”升级为透镜专属摘要，例如：

- 结构：`1 Topic · 4 Direction`；
- 演化：`4 Direction · 12 条目 · 3 期`；
- 编辑判断：`4 判断 · 8 条显式证据关系`。

### 4. 局部坐标和边长约束

布局验收不只检查“没有溢出”，还要检查边长和空洞：

- Topic 局部模型生成坐标后，不得保留不可见全图节点形成的行号空洞；
- `has_item`、`published_in`、`supports_judgement` 的端点应处于同一泳道或相邻语义列；
- 每种关系记录边长的最小值、中位数、95 分位和最大值；最大值若超过该关系局部中位数的 4 倍则测试失败，除非 fixture 显式说明；
- 布局包围盒与可见节点数量应随筛选范围近似增长，不能因过滤掉更多节点反而保留万级空白；
- 相同输入、透镜、范围和视口必须生成确定性坐标。

短期止血不能只把长边隐藏。若局部布局暂时未完成，可以让演化/编辑判断先进入单 Direction 或单 Judgement 范围，并明确显示范围收窄；这比绘制跨 19,000 单位的边或把节点缩成点更诚实。

### 5. 透镜空状态与范围反馈

每个透镜都先计算专属对象数量：

- 演化专属对象：Item 和 Issue；
- 编辑判断专属对象：Judgement 和 `supports_judgement`；
- 结构专属对象：Direction。

当专属对象为零时：

- 画布区域显示原因、当前 Topic、期次范围和可执行入口；
- 共同骨架可以作为折叠的“结构上下文”，但不能占据主画布并制造切换成功的假象；
- 指标、关系列表标题和移动端文案同步使用同一空状态；
- 不能自动跨 Topic 借用其他判断，也不能用无显式引用的判断补图。

### 6. 发布状态单独处理

布局修复完成不等于线上已经生效。发布验收需要同时确认：

- Pages 构建使用包含本次页面改动的提交；
- 线上 `knowledge/manifest.json` 为 `knowledge_complete`；
- 线上 `archive_head_issue` 与 `materialized_through_issue` 相同；
- 线上页面不再显示旧的“构建输入摘要”首屏卡片；
- 三个透镜的线上节点/边摘要与构建产物一致。

当前线上停在旧知识水位应作为部署/发布问题单独关闭，不能通过修改布局代码解决。

## Compatibility and migration

- 保留现有 Hash 路由和 `lens`、`topic`、`direction`、`node`、`range`、`from`、`to` 参数。
- 不需要修改 Archive、Roadmap、Idea 的持久化结构，也不改变现有关系枚举。
- 第一阶段可以不修改 `knowledge/graph.json` schema；局部布局由前端从已过滤模型确定性生成。
- 旧 `position` 字段继续被全局调试视图或回滚路径读取。待所有局部布局稳定后，再决定是否从公开合同中降级为可选字段。
- 旧深链若只有 Topic，在演化和编辑判断透镜中使用新的透镜专属默认焦点；若带有效 Node，继续尊重 Node。

## Failure, recovery, and rollback

- 局部布局计算失败时，页面显示“局部布局不可用”，保留 DOM 关系列表和节点详情；不能静默回退到万级空洞的全图坐标。
- 专属对象为零不是错误，使用明确空状态。
- 模型超过安全上限时保留现有裁剪提示，并要求用户选择 Direction、Judgement 或更短期次范围。
- 回滚时可停用 `knowledge-layout.js`，恢复原 `preset`/`breadthfirst` 路径；数据文件不需要迁移或回滚。
- Pages 部署失败不改变本地知识快照；继续保留上一个可用站点并报告线上/仓库版本差异。

## Verification

### 单元与合同测试

- 对三个透镜分别断言默认焦点和首屏集合，不再只断言最终节点/边数量。
- `agent_acceleration + recent3` fixture 应得到本文表格中的 5/20/21 节点与 4/28/24 边，并分别进入结构树、演化泳道、判断证据簇。
- 断言演化首屏包含至少一个 Item 和一个 Issue；编辑判断首屏包含至少一个 Judgement 和其证据 Item。
- 对 `ai_infra_horizontal`、`dpu_inline` 和 `tpn` 断言正确的透镜空状态。
- 对 `frontier_exploration` 断言达到软上限时有显式裁剪/收窄提示。
- 对所有 Topic、`latest|recent3|all` 运行局部边长统计，禁止万级坐标空洞。
- 相同输入构建两次，坐标与首屏焦点必须相同。

### 浏览器验收

在 1586、1440、1280、1024px 桌面宽度检查：

- 切换三个透镜后，首屏的核心节点种类和布局明显不同；
- 节点文字在初始视口可读，不需要先点“适应画布”；
- 没有贯穿整个画布却连接到视口外节点的淡色长边；
- 选择节点、关系表行、详情面板和 URL 同步；
- 收起筛选栏后重新计算画布尺寸和适配范围；
- 关系表节点/边数量与画布显示模型一致。

在 320、375、414、767px 检查移动分层路径、透镜空状态和关系列表，不挂载 Cytoscape 画布。

### 发布验收

- 部署后再次访问三个复现 URL，而不是只检查构建成功状态；
- 验证线上水位均为 2026-08-29 或当时最新归档期次；
- 验证线上静态资源版本包含新的局部布局模块；
- 将线上节点/边摘要与本地 `knowledge/graph.json` 构建结果对照。

## Documentation impact

实现时需要同步更新：

- `docs/contracts/editorial-workbench-ui.md`：三个透镜的默认焦点、局部布局、空状态和视口合同；
- `docs/contracts/knowledge-materialization.md`：仅在决定调整或废弃图谱 `position` 字段时更新；
- `docs/architecture.md`：若新增 `site/knowledge-layout.js`，补充模块所有权和数据流；
- `docs/operations/knowledge-freshness.md`：补充线上 Pages 版本与知识水位的联合发布检查；
- 图谱相关测试说明与视觉回归 fixture。

## Decision log

- 2026-09-02：根据用户反馈，对当前工作区三个透镜进行本地渲染和数据投影对照，确认问题发生在布局与初始视口，不是透镜查询参数未生效。
- 2026-09-02：确认 `≤12` 节点阈值导致结构透镜使用局部布局、演化和编辑判断复用全图坐标；该阈值不再作为长期设计。
- 2026-09-02：确认透镜缺少专属对象时必须显示空状态，不再用共同 Topic/Direction 骨架掩盖数据空档。
- 2026-09-02：本次请求止于诊断设计文档，不修改实现，也不提交或部署。
