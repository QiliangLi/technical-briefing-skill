# 日报知识图谱与 Idea Hub 证据视图设计

- Status: implemented
- Implemented: 2026-09-01；耐久规则已迁入 docs/contracts/editorial-workbench-ui.md、docs/contracts/knowledge-materialization.md 与 docs/architecture.md
- Created: 2026-09-01
- Last updated: 2026-09-01

## Problem and evidence

当前站点把 `#evidence` 作为一级页面，并在其中提供 Evidence Path、Evidence Graph、Evidence Gaps 与 Archive Atlas。已实现的关系图能够回答“某个 Idea 的证据来自哪里”，但它围绕 Idea、证据和假设展开，本质是证据审计视图，不是用户期待的“根据历期日报信息形成的知识图谱”。

当前公开数据已经具备另一张图所需的显式结构：

- 每期 `archive/issues/<date>/issue.json` 提供日报条目、Topic、Direction、编辑判断及其 `evidence_item_ids`；
- `archive/issues/<date>/papers.json` 提供条目稳定 ID、Topic、Direction、来源等级和发布时间；
- `knowledge/roadmaps/*.json` 以 Topic、Direction 和证据条目组织长期 Roadmap；
- `knowledge/ideas/*.json` 提供 Idea、Topic、支持证据和反对证据之间的显式关系。

因此，下一阶段需要把两个不同问题拆开：

1. **Idea Hub 证据视图**回答“一个 Idea 为什么存在、由什么支持或反对、还缺什么证据”。
2. **日报知识图谱**回答“历期日报形成了哪些 Topic 和 Direction、各方向积累了什么条目和编辑判断、这些知识如何影响 Roadmap 与 Idea”。

当前关系图使用自定义 DOM/SVG 渲染和手工边路由。节点位置、端点锚定、箭头方向和平行边偏移由本地算法共同承担，关系图和证据缺口中的箭头已经出现错位、交叉和语义方向难以辨认的问题。继续扩展同一套手写渲染器，会让图谱数据模型、布局和交互相互耦合。

本设计是以下已实现记录和现有草案的后继设计：

- [Evidence 图谱 UI 像素级还原实施方案](./2026-08-31-evidence-graph-ui-implementation-spec.md)
- [Roadmap、Idea Bank 与证据图谱：现状诊断与优化方案](../../designs/2026-08-29-roadmap-idea-bank-evidence-model-redesign.md)
- [Roadmap、Idea Bank 与证据图谱：最终呈现蓝图与差距分析](../../designs/2026-08-29-roadmap-idea-bank-evidence-workbench-blueprint.md)

若上述文档与本设计在图谱产品定位、一级导航或前端渲染技术上冲突，以本设计为准；现行行为在实现完成前仍以 [Editorial workbench UI contract](../contracts/editorial-workbench-ui.md) 为准。

## Goals and non-goals

### Goals

- 新增一张由历期日报显式结构生成的全局知识图谱，而不是把 Evidence Graph 改名。
- 默认以 `Topic → Direction` 作为稳定骨架，按需展开日报条目、编辑判断、Roadmap 与 Idea。
- 将现有 Evidence Path、Evidence Graph 和 Evidence Gaps 合并进 Idea Hub 的单个 Idea 详情。
- 使用同一个图谱渲染适配层呈现“日报知识图谱”和“Idea 证据子图”，但让两者保持独立的数据投影和语义合同。
- 通过构建期校验和稳定排序保证同一份输入生成相同节点、边、坐标与截图。
- 修复箭头方向、端点、平行边和选择状态混乱的问题；图和关系列表必须表达同一事实。
- 保持 GitHub Pages 为只读静态站点，不引入在线图数据库、服务端图查询或浏览器侧 LLM。

### Non-goals

- 不从标题相似度、关键词共现或向量距离自动推断实体关系。
- 不在本阶段从正文抽取人物、公司、模型、数据集、方法或 Claim 实体。
- 不引入 Neo4j、OpenSPG、GraphRAG 或其他在线知识库服务。
- 不把 Roadmap、Idea 或编辑判断改造成新的持久化 Schema。
- 不把图谱作为唯一浏览方式；移动端、键盘和读屏场景必须有列表或路径降级。
- 不用力导向布局制造每次加载都变化的“星云图”。

## Constraints and invariants

### 1. 两张图、一个渲染层

- 日报知识图谱是跨期知识结构视图，中心对象是 Topic、Direction、条目和编辑判断。
- Idea Hub 证据图是单个 Idea 的证据审计视图，中心对象是 Idea、证据、假设和缺口。
- 两者可以共用 Cytoscape.js renderer、样式 token、选择模型和无障碍关系列表，但不能共用一个含糊的 `buildGraph()`。
- 两个投影分别由 `buildKnowledgeGraphModel()` 与 `buildIdeaEvidenceGraphModel()` 负责，测试和关系枚举独立。

### 2. 显式关系优先

只有以下关系可以进入已确认图谱：

- Archive 中明确存在的 issue、item、Topic 和 Direction 字段；
- `synthesis.judgements[].evidence_item_ids` 指向的条目；
- Roadmap branch 中显式存在的 `direction_id`、`evidence_item_ids` 或证据时间线引用；
- Idea 中显式存在的 `topic_ids`、`evidence_for` 和 `evidence_against`；
- 现有合同允许的来源 URL、Reader 定位和 provenance。

缺少目标、关系类型或 provenance 的边进入 `unresolved`，不能绘制成已确认边。Topic 名称、Direction 名称和关键词只用于显示与搜索，不用于补边。

### 3. 派生物不是新的事实来源

`knowledge/graph.json` 是从 Archive 与 materialized knowledge 生成的发布派生物，不是新的权威知识库。权威来源仍然是：

```text
archive/index.json
archive/issues/<date>/issue.json
archive/issues/<date>/papers.json
knowledge/index.json
knowledge/roadmaps/*.json
knowledge/ideas/*.json
```

任何图谱节点必须能反向定位到上述至少一个对象。前端不在浏览器里修复、扩写或持久化图数据。

### 4. 新鲜度必须分层表达

Archive 与 materialized knowledge 可能更新到不同期次。图谱必须分别显示：

- `archive_through_issue`：日报结构更新到哪一期；
- `knowledge_through_issue`：Roadmap 与 Idea 物化更新到哪一期。

不能用一个“图谱已更新”掩盖长期知识落后。图谱构建失败或输入摘要不匹配时，站点不能静默展示旧图并声称已经更新。

### 5. 图形不是语义

- 箭头方向由关系枚举决定，不由节点当前所在左右位置决定。
- 颜色不能成为关系的唯一区分；每类关系同时使用标签、线型或图标。
- 节点距离、线长和聚类紧密程度不表达相关性强弱，除非数据合同提供对应数值。
- `contains`、`tracks` 等结构关系不得被描述为支持、因果或演进结论。
- 图谱永远配套可筛选的关系列表和节点详情。

### 6. 静态发布和依赖边界

- 浏览器不加载 CDN 脚本，不产生运行时第三方请求。
- Cytoscape.js 以锁定版本的自托管静态资源进入站点，并保留上游许可证与版本记录。
- NetworkX 仅在 Python 构建和测试阶段使用，不进入浏览器。
- 图谱生成失败不得影响邮件内容生成或发送；它必须阻止发布一份声称为最新、实际却陈旧的站点图谱。

## Proposed design

### 1. 产品信息架构

一级导航从：

```text
首页 / Roadmap / Idea Hub / Evidence / 归档
```

调整为：

```text
首页 / Roadmap / Idea Hub / 知识图谱 / 归档
```

#### 日报知识图谱

新增一级路由：

```text
#knowledge
#knowledge?lens=structure&topic=<topic_id>&direction=<direction_id>&node=<node_id>
#knowledge?lens=evolution&topic=<topic_id>&from=<date>&to=<date>&node=<node_id>
#knowledge?lens=judgements&topic=<topic_id>&node=<node_id>
```

- `structure` 是默认透镜，展示 Topic 与 Direction 骨架。
- `evolution` 按期次展开 Direction 下的日报条目，强调“何时出现、何时改变”。
- `judgements` 展示编辑判断与其显式证据条目。
- Roadmap 和 Idea 作为可关闭的影响叠层，不在默认首屏同时展开。

#### Idea Hub

单个 Idea 详情增加稳定视图参数：

```text
#ideas?idea=<idea_id>&view=overview
#ideas?idea=<idea_id>&view=evidence&mode=path
#ideas?idea=<idea_id>&view=evidence&mode=graph&node=<node_id>&depth=<1|2>
#ideas?idea=<idea_id>&view=gaps
```

- `overview` 展示 Idea 身份、状态、问题、机制、预期影响和决策记录。
- `evidence` 承接当前 Evidence Path 与 Evidence Graph。
- `gaps` 承接当前 Evidence Gaps，并保持“缺口来自 Idea 字段”的真实性说明。
- Idea Hub 列表页不加载图谱，只在进入具体 Idea 后加载对应证据子图。

#### 兼容路由

旧书签按下列规则归一化：

| 旧路由 | 新路由 |
| --- | --- |
| `#evidence?idea=<id>&view=path` | `#ideas?idea=<id>&view=evidence&mode=path` |
| `#evidence?idea=<id>&view=graph` | `#ideas?idea=<id>&view=evidence&mode=graph` |
| `#evidence?idea=<id>&view=gaps` | `#ideas?idea=<id>&view=gaps` |
| `#graph?...` | 有 `idea` 时进入 Idea 证据图，否则进入 `#knowledge` |
| `#atlas?...` | `#knowledge?lens=evolution`，保留可转换的期次和 Topic 参数 |

兼容入口只做 URL 归一化，不同时维护两套页面。

### 2. 日报知识图谱语义模型

#### 节点类型

| kind | 稳定 ID | 来源 | 默认可见 |
| --- | --- | --- | --- |
| `topic` | `topic:<topic_id>` | Archive / Roadmap Topic | 是 |
| `direction` | `direction:<direction_id>` | 日报条目 Direction | 是 |
| `item` | `item:<brief_item_id>` | `issue.json` / `papers.json` | 按需 |
| `judgement` | `judgement:<issue_date>:<digest>` | `synthesis.judgements[]` | 按需 |
| `issue` | `issue:<date>` | `archive/index.json` | 仅演化透镜 |
| `roadmap` | `roadmap:<topic_id>` | materialized Roadmap | 叠层 |
| `roadmap_branch` | `branch:<topic_id>:<branch_id>` | Roadmap branch | 叠层 |
| `idea` | `idea:<idea_id>` | materialized Idea | 叠层 |

Judgement 当前没有一等 ID。Graph Builder 使用以下稳定材料计算 digest：

```text
issue_date + normalized title + sorted evidence_item_ids
```

不得使用数组下标作为持久节点身份。

#### 关系类型

| relation | source → target | 中文标签 | 语义 |
| --- | --- | --- | --- |
| `has_direction` | Topic → Direction | 包含方向 | 分类结构 |
| `has_item` | Direction → Item | 收录条目 | 分类结构 |
| `published_in` | Item → Issue | 发布于 | 时间定位 |
| `supports_judgement` | Item → Judgement | 支持判断 | 显式 judgement evidence |
| `tracks` | Roadmap → Topic | 跟踪 | 长期知识结构 |
| `organizes` | Roadmap Branch → Direction | 组织方向 | Roadmap 显式结构 |
| `uses_evidence` | Roadmap Branch → Item | 引用证据 | Roadmap 显式引用 |
| `relates_to` | Idea → Topic | 关联专题 | Idea `topic_ids` |
| `supports_idea` | Item → Idea | 支持 | Idea `evidence_for` |
| `challenges_idea` | Item → Idea | 反对 | Idea `evidence_against` |

同一个事实不能同时以两个方向重复写边。关系标签属于数据合同，前端不能为了让箭头“看起来顺”而交换 source 和 target。

#### 节点详情

节点详情不复制整篇日报，只提供完成判断所需的信息：

- Topic：名称、Direction 数量、条目数量、覆盖期次、关联 Roadmap 与 Idea；
- Direction：名称、所属 Topic、首见/末见期次、条目与判断数量；
- Item：标题、核心结论、机制、结果、边界、项目相关性、来源等级和原文入口；
- Judgement：标题、正文、证据条目、所在期次；
- Roadmap / Idea：当前状态、摘要、更新时间和进入对应详情页的入口。

### 3. 发布图谱合同

新增派生文件：

```text
knowledge/graph.json
```

顶层结构：

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-01T00:00:00Z",
  "archive_through_issue": "2026-08-29",
  "knowledge_through_issue": "2026-08-17",
  "input_digest": "sha256:...",
  "stats": {
    "node_count": 0,
    "edge_count": 0,
    "unresolved_count": 0
  },
  "nodes": [],
  "edges": [],
  "unresolved": []
}
```

节点采用 Cytoscape 兼容的 `data`，同时保留显示模型与 provenance：

```json
{
  "data": {
    "id": "item:024c392223c77989a9a4fedd",
    "kind": "item",
    "label": "VPP：V形虚拟stage优化chunked prefill",
    "topic_id": "tpn",
    "direction_id": "kv_network_scheduling",
    "issue_date": "2026-08-29",
    "href": "#archive?date=2026-08-29&item=024c392223c77989a9a4fedd"
  },
  "position": { "x": 0, "y": 0 },
  "provenance": [
    {
      "path": "archive/issues/2026-08-29/issue.json",
      "object_id": "024c392223c77989a9a4fedd"
    }
  ]
}
```

边采用：

```json
{
  "data": {
    "id": "edge:supports_judgement:item:...:judgement:...",
    "source": "item:...",
    "target": "judgement:...",
    "relation": "supports_judgement",
    "label": "支持判断",
    "confirmation": "explicit"
  },
  "provenance": [
    {
      "path": "archive/issues/2026-08-29/issue.json",
      "field": "synthesis.judgements[].evidence_item_ids"
    }
  ]
}
```

`input_digest` 覆盖所有参与构图文件的规范化内容。前端不计算或修补该摘要，只用它判断缓存和诊断构建版本。

### 4. Graph Builder

Graph Builder 位于 Python 构建层，建议新增：

```text
briefing_skill/knowledge_graph.py
schemas/knowledge-graph.schema.json
tests/test_knowledge_graph.py
```

命令入口：

```bash
python3 briefing.py knowledge graph build
python3 briefing.py knowledge graph validate
```

构建流程：

```text
读取 archive/index.json
  → 逐期读取 issue.json 与 papers.json
  → 读取 knowledge/index.json 指向的 Roadmap / Idea
  → 规范化并生成稳定节点和边
  → 使用 NetworkX 校验图结构
  → 计算确定性分层坐标
  → 导出 Cytoscape 兼容 JSON
  → JSON Schema 与语义校验
  → 原子替换 knowledge/graph.json
```

NetworkX 负责：

- 重复节点、重复边和悬空端点检测；
- 指定关系允许的 source/target kind 校验；
- 连通分量、孤立节点、可达路径和影响传播等构建期分析；
- 通过 `cytoscape_data()` 或等价适配导出前端结构；
- 测试 fixture 中的确定性比较。

NetworkX 不负责决定业务关系，也不直接使用无种子的 spring layout。坐标由节点层级、稳定排序和固定间距计算；NetworkX 只提供图结构能力。

输出顺序固定为：

```text
kind rank → topic_id → direction_id → issue_date → stable id
```

同一输入连续构建两次，除 `generated_at` 外必须字节等价。测试比较时可排除该字段，或者从 `SOURCE_DATE_EPOCH` 注入固定时间。

### 5. 前端渲染架构

#### Cytoscape.js

使用 [Cytoscape.js](https://js.cytoscape.org/) 作为两张图的浏览器渲染器。采用原因：

- 适合现有静态 HTML/JS；
- 原生支持节点、边、箭头、选择、筛选、缩放和平移；
- 数据格式可与构建期 Graph Builder 直接衔接；
- 支持 preset、breadthfirst 和扩展布局；
- 不要求在线服务或图数据库。

站点新增自托管、锁定版本的资源，不从 CDN 加载。第一阶段不引入 Dagre、ELK 等额外布局扩展；优先使用构建期输出的 `preset` 坐标。只有当真实 fixture 证明 preset 无法满足动态展开时，才单独评估布局扩展。

#### 文件职责

| 文件 | 职责 |
| --- | --- |
| `site/graph-renderer.js` | Cytoscape 初始化、元素增删、选择、视口、键盘、事件和销毁 |
| `site/graph-styles.js` | 节点/边 selector、关系箭头、聚焦和降级样式 |
| `site/knowledge-graph-view.js` | 全局图谱透镜、筛选、详情、叠层和 URL 同步 |
| `site/idea-evidence-view.js` | Idea 证据 path/graph/gaps 编排 |
| `site/data-contract.js` | 路由解析、发布 JSON 校验和显示模型适配；不再承担布局算法 |
| `site/evidence-graph.js` | 迁移期间保留；新渲染器验收后移除或降为兼容薄层 |

Renderer 只接收已经验证的显示模型：

```js
mountGraph(container, {
  nodes,
  edges,
  positions,
  focusId,
  visibleKinds,
  onSelect,
  onNavigate
});
```

它不读取 Archive、Roadmap 或 Idea 原始文件，也不推断关系。

### 6. 布局与箭头规则

#### 默认知识图谱

默认首屏只显示 Topic 与 Direction，目标是 20 至 40 个稳定节点，而不是一次展示全部历史条目。

```text
Topic
  → Direction
      → 按需展开 Item
          → Judgement
          → Idea / Roadmap 影响叠层
```

- Topic 按配置或稳定 ID 纵向排列；Direction 在右侧分组排列。
- 点击 Direction 展开最近或筛选期次内的 Item；再次点击收起。
- Item 展开 Judgement 时，只加入引用它的显式判断。
- Roadmap 与 Idea 叠层默认关闭，避免与日报结构混成一张无法阅读的全量图。
- 首屏自动 `fit` 一次，之后用户平移缩放不会被数据筛选以外的事件重置。

#### 边路由

- 层级结构边优先使用正交 `taxi` 路由，箭头位于 target 端。
- 同一 source/target 的多条关系使用稳定编号的平行曲线，不相互覆盖。
- 反向关系使用路径另一侧，禁止共用同一条视觉路径。
- 边端点由 Cytoscape 根据节点几何计算，不使用 DOM `getBoundingClientRect()` 手工锚定。
- 边标签靠近路径中段并带画布色衬底；聚焦节点的一跳关系标签始终可见。
- 非聚焦边可以降低透明度，但不能把支持和反对压成无法区分的同色细线。

#### 有界展开

- 默认视图不超过 60 个节点、120 条边。
- 单次展开如果超过上限，先保留聚焦节点的一跳、较近期次和显式判断关系，再按稳定 ID 裁剪。
- 用户可以切换“仅最近一期 / 最近三期 / 全部期次”，但“全部”仍受 250 节点、500 边硬上限约束。
- 达到上限时显示真实数量和裁剪原因，不静默丢弃。

### 7. 页面结构与视觉语言

这是高密度产品工作台，不是装饰性网络可视化。沿用现有暖纸色、深海军蓝、砖红与橄榄绿语义色，以及 serif 标题加 sans UI 的编辑资料册语言。

桌面采用固定弹性固定的三栏结构：

```text
248px 筛选与透镜 | minmax(0, 1fr) 图谱画布 | 344px 节点详情
```

画布下方是关系列表和未解析关系入口。第一屏优先回答：

1. 目前有哪些稳定 Topic 和 Direction？
2. 当前聚焦方向积累了多少条目、跨多少期？
3. 最近增加了什么判断？
4. 它影响了哪些 Roadmap 或 Idea？

视觉要求：

- Topic、Direction、Item、Judgement、Roadmap 和 Idea 使用不同轮廓、图标和文字标签；
- 节点不使用发光、玻璃、渐变文字或无意义粒子动画；
- 状态变化只使用 120 至 180ms 的透明度、边框和位移反馈；
- 数量必须来自真实数据，不能用示例 KPI 填充；
- 图谱背景可以使用低对比度定位网格，但不模拟未来感 HUD。

本页面不需要摄影、生成图片或装饰插图；图形资产仅使用现有单色 SVG 图标。

### 8. 搜索、筛选和详情联动

左侧筛选包括：

- 搜索 Topic、Direction、条目或判断；
- 透镜：结构、演化、编辑判断；
- 期次：最新、最近三期、自定义范围、全部；
- 节点类型；
- Topic / Direction；
- Roadmap 与 Idea 影响叠层；
- 只看存在未解析关系的对象。

交互合同：

- 选择节点同时更新图谱高亮、右侧详情、关系列表和 URL；
- 选择边同时更新关系详情与关系列表行；
- 搜索结果先列出匹配对象，确认后再改变画布焦点，避免输入过程中不断重排；
- 双击或“展开一跳”只加载当前节点的直接邻居；
- 返回按钮恢复上一选择和透镜，而不是重新进入默认图；
- 任何节点都能在三次操作内到达对应日报条目或长期知识详情。

### 9. 移动端与无障碍

在宽度低于 768px 时不挂载可平移缩放的完整画布，改为以当前节点为中心的分层路径与关系列表：

```text
当前 Topic / Direction 摘要
  → 相邻方向
  → 最近条目
  → 编辑判断
  → Roadmap / Idea 影响
```

- 320、375、414 和 768px 为固定验收宽度；
- 筛选进入原生 dialog 或底部 sheet；
- 所有可见交互目标至少 44×44px；
- Tab、按钮、面包屑和 CTA 不换成两行；
- `html` 与 `body` 使用 `overflow-x: clip`，图谱容器不能撑宽页面；
- SVG/Canvas 图形对读屏隐藏，完整关系由 DOM 列表表达；
- 键盘可以选择节点、沿入边/出边移动、打开详情并回到关系列表；
- `prefers-reduced-motion` 下关闭适应画布动画和节点过渡，直接进入终态。

### 10. 大规模渲染与未来知识抽取边界

#### Sigma.js + Graphology

[Sigma.js](https://www.sigmajs.org/docs/) 作为大规模 WebGL 渲染预案，不进入第一阶段依赖。只有满足以下任一条件才启动替换评估：

- 产品明确要求同屏展示数千节点，而不能继续渐进展开；
- 250 节点、500 边的验收 fixture 在目标设备上持续达不到交互性能门槛；
- 标签、hover 与选择优化后，Cytoscape 仍出现可复现的主线程卡顿。

Graph model 与 renderer adapter 必须保持分离，使未来更换渲染器时不改业务图谱合同。

#### Microsoft GraphRAG

[Microsoft GraphRAG](https://github.com/microsoft/graphrag) 只作为未来非结构化文本候选关系生成的研究参考。当前第一种图谱已有结构化 Topic、Direction、Item 和 Judgement，不引入 LLM 再抽取一遍。

#### OpenSPG KAG

[OpenSPG KAG](https://github.com/OpenSPG/KAG) 的 Schema 约束和“知识节点与原文 Chunk 互索引”是长期设计参考。当前阶段只落实 provenance、原文回链和 typed relation，不引入 OpenSPG server、向量模型或推理服务。

#### Neo4j LLM Graph Builder

[Neo4j LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder) 只参考“候选抽取 → Schema 限制 → 人工预览 → 确认入库”的未来工作流。当前静态只读站点不引入 Neo4j、APOC、后端服务或在线凭据。

## Compatibility and migration

### 数据迁移

- Archive、Reader、Roadmap 和 Idea 文件不迁移；Graph Builder 只读取它们。
- 首次生成 `knowledge/graph.json` 时对全部已发布期次做一次确定性回填。
- 图谱文件是可重新生成的派生物，删除后可以从权威输入完整恢复。
- 当前没有一等 ID 的 Judgement 使用稳定 digest；未来 Schema 增加一等 ID 后，必须提供旧 digest 到新 ID 的兼容映射或显式重建说明。

### 前端迁移

迁移分三步：

1. 引入 Graph Builder、发布 JSON 和 Cytoscape renderer，但保留旧 Evidence 页面作为对照。
2. 在 `#knowledge` 上线日报知识图谱，在 Idea 详情内上线新的 Evidence 子视图；旧 URL 归一化到新位置。
3. 视觉、路由、无障碍和数据一致性验收后，从一级导航移除 Evidence，并移除旧 DOM/SVG 布局实现。

迁移期间不允许同一路由随机选择新旧 renderer。使用单一、显式的功能开关或分支验收。

### 依赖迁移

- Python 依赖增加经过测试的 NetworkX 3.x 版本范围，并同步 `pyproject.toml` 与 `requirements.txt`。
- 浏览器依赖增加锁定版本的 Cytoscape.js 自托管文件、来源说明和许可证。
- 不把 Playwright 的开发依赖当作站点运行时依赖。

## Failure, recovery, and rollback

### 构建失败

- 输入 JSON 或 Schema 无效时，Graph Builder 失败并列出文件和对象 ID；不得覆盖上一份有效 `knowledge/graph.json`。
- 悬空引用进入 `unresolved`。超过允许阈值或涉及核心 Topic/Direction 骨架时验证失败。
- 构建先写临时文件，完整校验后原子替换正式文件。
- 站点发布前比较 `input_digest` 与当前输入；不一致时停止图谱发布，而不是继续发布陈旧图谱。

### 浏览器失败

- Cytoscape 资源加载或初始化失败时，显示同一显示模型生成的关系列表和节点详情。
- URL 中节点不存在时，保留筛选条件并回到对应 Topic 或默认结构视图，同时显示诊断提示。
- 超出节点上限时保留已显示图，并提供收窄期次、Topic 或节点类型的操作。
- 关系解析异常不得阻止 Idea Overview、Roadmap 或 Archive 页面工作。

### 回滚

回滚顺序：

1. 恢复旧一级 Evidence 导航和路由；
2. 停止加载 Cytoscape renderer 与 `knowledge/graph.json`；
3. 恢复旧 `evidence-graph.js` 入口；
4. 保留 `knowledge/graph.json` 或安全删除，因为它不是权威数据；
5. 移除新增依赖前确认没有其他调用者。

回滚不修改 Archive、Roadmap、Idea 或邮件产物。

## Verification

### Graph Builder

- 同一 fixture 连续构建两次，节点、边、排序和坐标完全一致；
- 每条边的端点存在，且 source/target kind 符合关系枚举；
- 重复 ID、重复边、跨 Topic 错接和缺失 provenance 会失败；
- 所有 `judgement.evidence_item_ids` 均能解析或进入带原因的 `unresolved`；
- 图谱的 Topic、Direction、Item、Judgement 数量与 Archive 的独立统计一致；
- Archive 与 knowledge 新鲜度分别计算，不相互冒充；
- `knowledge/graph.json` 通过 JSON Schema；
- 临时写入、失败保留旧文件和重复 build 幂等性通过测试。

### 前端合同

- `#knowledge` 三种透镜、筛选、节点深链、前进后退和无效参数行为通过测试；
- 所有旧 Evidence / Graph / Atlas 深链按映射进入新位置；
- Idea Overview、Evidence Path、Evidence Graph 与 Gaps 的状态不会相互丢失；
- 图、详情和关系列表始终选择同一节点或关系；
- Cytoscape 实例在切换路由时销毁，不残留监听器或重复 canvas；
- 关闭 JavaScript 图形能力时仍能从列表访问全部可见关系和来源；
- 前端不会从标题、名称或关键词补边。

### 箭头与视觉回归

固定以下 fixture：

- 单 Topic、多 Direction；
- 单 Direction、多期 Item；
- 多 Item 汇入一个 Judgement；
- 同一 Item 同时关联 Judgement 与 Idea；
- 同一 source/target 的平行关系；
- 支持与反对同时存在的 Idea；
- 存在 unresolved 端点；
- 达到节点和边上限。

验收要求：

- 每条箭头终点落在 target 节点边界，不穿过节点正文；
- 平行边和反向边可以分别选择，标签不完全重叠；
- 聚焦节点的一跳边在 1280px 以上视口可辨认；
- 筛选、展开、收起和窗口 resize 后不出现旧箭头残影；
- 同一输入重载后节点坐标不漂移；
- 1586×992、1440×900、1280×800、1024×768、768×1024、414×896、375×812 和 320×780 均无页面级横向溢出。

### 性能门槛

在目标桌面浏览器中使用 250 节点、500 边 fixture：

- 首次可交互时间目标小于 1 秒；
- 聚焦和一跳高亮目标在 100ms 内反馈；
- 平移缩放期间无持续性明显掉帧；
- 路由切换后旧实例、监听器和大对象可以回收。

只有在真实 fixture 无法通过且渐进展开不能满足产品需求时，才评估 Sigma.js。

## Documentation impact

实现本设计时必须同步：

- `docs/contracts/editorial-workbench-ui.md`：新导航、路由、文件所有权、移动降级和旧路由兼容；
- `docs/contracts/knowledge-materialization.md`：`knowledge/graph.json` 的派生属性、构建时机和双水位；
- `docs/architecture.md`：Archive / Knowledge → Graph Builder → static site 的数据流；
- `README.md`：公开站点入口或本地预览命令发生变化时更新；
- `schemas/`：新增 graph schema 并进入相应校验器；
- 依赖清单与第三方许可证记录；
- 本设计实施完成后标记 `implemented`，把耐久规则迁入当前合同，再移动到 `docs/history/designs/`。

旧的 implemented Evidence Graph 设计保留为历史记录，不回写成当前方案。

## Decision log

### 2026-09-01：拆分知识图谱与证据图谱

用户确认采用“第一种”知识图谱：直接使用日报已有结构化字段构图。当前 Evidence Graph 不再承担全局知识图谱职责，而是合并进 Idea Hub。

### 2026-09-01：默认骨架采用 Topic 与 Direction

全局图谱默认只展示稳定的 Topic / Direction 骨架，日报条目、编辑判断、Roadmap 和 Idea 通过透镜、展开和叠层进入，避免首屏成为全量关系毛线团。

### 2026-09-01：采用 Cytoscape.js 作为浏览器渲染器

现有手写 DOM/SVG 箭头和布局已经产生可见错位。Cytoscape.js 直接承担节点、边、箭头、选择和视口交互；业务投影和渲染器保持分离。

### 2026-09-01：采用 NetworkX 作为构建期图能力

NetworkX 负责图结构校验、分析和 Cytoscape JSON 导出。业务关系仍由显式字段决定，确定性坐标仍由本项目的稳定分层算法产生。

### 2026-09-01：其他开源项目作为边界参考

- Sigma.js + Graphology 是数千节点规模的渲染预案；
- Microsoft GraphRAG 是未来非结构化候选关系生成参考；
- OpenSPG KAG 是 Schema 和知识—原文互索引参考；
- Neo4j LLM Graph Builder 是未来候选抽取、预览和确认流程参考；
- 上述项目均不进入当前第一阶段运行时。

## Open questions

以下问题不阻止文档进入评审，但必须在实现前或第一阶段 fixture 中关闭：

1. `knowledge/graph.json` 是在每次 Archive 发布后自动重建，还是由站点发布命令显式触发；建议自动重建并把站点新鲜度校验作为发布门禁。
2. Roadmap branch 是否始终有稳定 `branch_id`；若当前对象缺失，需要在 Graph Builder 中定义兼容 ID 规则并记录迁移边界。
3. “全部期次”超过 250 节点后，默认裁剪优先级是最近期次优先，还是编辑判断关联优先；建议先保留聚焦一跳与判断关联，再按期次倒序。
4. Cytoscape.js 是提交压缩发行文件还是增加最小 bundling 步骤；两者都必须保持离线、锁版本和许可证可审计。
