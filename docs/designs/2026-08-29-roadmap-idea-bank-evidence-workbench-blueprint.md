# Roadmap、Idea Bank 与证据图谱：最终呈现蓝图与差距分析

- Status: draft
- Created: 2026-08-29
- Last updated: 2026-08-30

- 文档日期：2026-08-29
- 适用仓库：`technical-briefing-skill`
- 文档定位：目标产品形态、运行机制、界面效果与体验验收说明
- 关联文档：
  - [Roadmap、Idea Bank 与证据图谱：现状诊断与优化方案](./2026-08-29-roadmap-idea-bank-evidence-model-redesign.md)
  - [技术情报工作台：UI 页面内容 Brief](./2026-08-30-technical-intelligence-ui-screen-content-brief.md)
  - [日报知识图谱与 Idea Hub 证据视图设计](../history/designs/2026-09-01-daily-briefing-knowledge-graph-design.md)

> 2026-09-01 更新：全局知识图谱改为直接投影日报已有 Topic、Direction、条目和编辑判断；原 Evidence Graph 合并进 Idea Hub。涉及图谱定位、导航和渲染组件时，以新增设计为准。

## 一、这份文档回答什么问题

上一份文档主要回答：

- 当前设计为什么显得粗糙；
- 数据模型和运行链路存在哪些风险；
- 应该引入哪些知识对象；
- 应按什么优先级实施重构。

这份文档换一个视角，主要回答：

- 三部分最终应该让用户看到什么；
- 用户进入页面后应该能完成什么任务；
- 页面背后的机制如何保证这些内容可信、及时和可追溯；
- 低证据、冲突、过期、未验证等状态应该怎样呈现；
- 当前产品距离这个最终效果还有多远；
- 哪些内容应作为 UI 和产品验收标准。

可以把两份文档理解为：

```text
上一份：为什么改、底层改什么、按什么顺序改
                         ↓
这一份：改完以后应该长什么样、怎样使用、怎样验收
```

本文件不会重复上一份中的完整 Schema 设计和所有工程风险；涉及 Evidence Registry、Claim Ledger、原子快照、对象级版本锁等底层方案时，以关联文档为详细技术依据。

## 二、最终产品不应是三个孤立页面

Roadmap、Idea Bank 和证据图谱最终应是同一条技术决策链的三个工作视图：

```text
Roadmap：外部技术发生了什么变化，还有什么没有解决
    ↓ 产生问题、机会和观察触发器
Idea Bank：我们可以提出什么假设或方案，值不值得验证
    ↓ 需要证明、否定或收窄关键假设
Evidence Explorer：这些判断分别由什么证据支持、反对或限制
    ↺ 新证据再推动 Roadmap 和 Idea 状态变化
```

最终用户不需要理解底层 JSON 文件，更不需要在三个页面之间自己拼接信息。系统应支持以下自然跳转：

- 从 Roadmap 的某个 Milestone 打开支持它的 Claim；
- 从 Roadmap 的 Open Question 查看由它产生的 Idea；
- 从 Idea 的某个 Assumption 查看支持和反对证据；
- 从一条证据反向查看它影响了哪些 Roadmap 判断与 Idea；
- 从一次 Idea 状态变化查看当时使用的证据快照和实验结果；
- 从任意页面回到对应日报和原始来源。

最终效果不是“数据更多”，而是任何重要判断都能回答三个问题：

1. 现在的判断是什么？
2. 为什么这样判断？
3. 什么新证据会让判断改变？

## 三、整体体验的北极星

### 3.1 三类主要用户

#### 领导或技术负责人

希望快速知道：

- 哪些外部方向发生了实质变化；
- 哪些 Idea 已经接近可验证或立项；
- 哪些判断仍然证据不足；
- 当前最值得投入的验证是什么。

不希望先阅读几十篇论文或浏览一张巨大关系图。

#### 专题负责人或架构师

希望快速知道：

- 某条技术路线的机制、成熟度和边界；
- 多条 Approach 的差异；
- 当前结论依赖哪些硬件、工作负载和 baseline；
- 哪些问题值得继续跟踪或安排实验。

#### 研究与工程执行者

希望快速知道：

- Idea 的关键假设是什么；
- 应如何验证；
- 使用什么输入、baseline、metric 和阈值；
- 过去做过什么、结果如何、下一步由谁负责。

### 3.2 最终体验指标

产品达到目标形态后，应满足：

- 30 秒内看懂某个 Topic 当前最重要的外部变化；
- 2 分钟内从一个 Roadmap 判断追到具体 Claim、条件和原始来源；
- 1 分钟内看懂一个 Idea 为什么存在、现在处于什么状态、下一步做什么；
- 3 次点击以内从 Roadmap 或 Idea 到达原始来源；
- 页面任何位置都能看到知识更新到哪一期；
- 证据不足时能明确知道“缺什么”，而不是只看到空白；
- 冲突证据出现时，页面能并列展示冲突及适用条件，而不是强行给出单一结论；
- 新一期日报发布后，受影响 Topic 和 Idea 能形成可审计更新，不依赖人工记忆。

### 3.3 全局设计原则

#### 判断优先，文章后置

页面先展示“现在知道什么、发生了什么变化、下一步是什么”，文章列表作为证据展开，而不是成为主界面。

#### 事实、推理、决策使用不同视觉语言

- 来源事实：原始来源明确声称或测量的内容；
- 系统推理：跨来源综合出的 Roadmap / Idea 判断；
- 决策：是否继续观察、验证、暂停或立项。

三者不能只靠文案语气区分，必须有固定标签和样式。

#### 任何“当前”都带水位线

页面必须同时显示：

- 最新归档日期；
- 长期知识物化到哪一期；
- 当前对象最后一次实质变化时间；
- 当前是否落后、部分完成或完整。

#### 不把证据数量冒充证据强度

10 篇同一团队、同一假设、相近实验条件的文章，不等于 10 份独立验证。页面应突出直接性、独立性、适用性、是否有反对证据，而不只显示数量。

#### 图谱服务问题，不服务炫技

默认展示一个对象附近的必要关系，不一上来绘制全局“毛线团”。

#### 低证据状态也必须有用

当不能形成 Milestone 或 Idea 决策时，页面应展示当前 Landscape、证据缺口和 Watch Trigger，而不是只写“证据不足”。

## 四、整个 Workbench 最终应该是什么样

### 4.1 全局框架

桌面端建议继续使用当前三栏 Workbench，但每一栏承担稳定职责：

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 技术情报工作台 │ 已同步至 2026-08-29 ✓ │ 全局搜索 │ 本期变化 7 │ 用户/权限 │
├──────────────┬─────────────────────────────────────┬───────────────────────┤
│ 左栏         │ 中栏                                │ 右栏                  │
│ 导航与筛选   │ 当前任务的主体                      │ 证据、差异与决策详情  │
│              │                                     │                       │
│ 首页         │ Roadmap / Idea / Evidence 主内容   │ 点击对象后的上下文    │
│ Roadmap      │                                     │ 不打开新页面也能溯源  │
│ Idea Bank    │                                     │                       │
│ Evidence     │                                     │                       │
│ 日报归档     │                                     │                       │
└──────────────┴─────────────────────────────────────┴───────────────────────┘
```

### 4.2 顶部全局状态条

始终显示：

- `归档最新：2026-08-29`
- `知识已物化：2026-08-29`
- `状态：完整 / 落后 2 期 / 部分失败`
- 当前 snapshot ID 或版本入口；
- 全局搜索；
- “本期变化”入口。

当知识落后时，顶部使用明确警告：

```text
⚠ 长期知识目前只更新到 2026-08-17，最新三期日报尚未进入 Roadmap 与 Idea。
```

不能继续显示“当前判断”而没有任何提示。

### 4.3 全局搜索

搜索对象不仅包括标题，还包括：

- Topic / Track；
- Claim；
- Idea / Assumption；
- Source / 项目名；
- 机制、指标、硬件、工作负载和关键词。

结果按对象类型分组，并允许直接执行：

- 查看 Roadmap 中的位置；
- 查看 Idea 中的使用关系；
- 打开 Evidence Path；
- 打开原始来源或日报。

### 4.4 一致的视觉标签

建议所有页面统一使用以下标签：

- `来源事实`
- `系统推理`
- `内部决策`
- `已验证`
- `待验证`
- `存在冲突`
- `仅发现信号`
- `历史版本`
- `知识已过期`

支持、反对、限制不能只靠绿色、红色和灰色区分，还要有文字、图标和可访问说明。

### 4.5 只读公开面与内部决策面

如果继续使用 GitHub Pages，建议明确它是只读知识展示面。以下内容可以安全发布到只读面：

- 外部 Roadmap；
- 公开来源和 Claim；
- 不包含敏感信息的 Idea 摘要；
- 证据路径；
- 历史版本。

以下能力需要内部认证服务、PR 工作流或其他可审计写入机制：

- Owner；
- 内部资源与成本；
- Experiment 结果；
- Idea 状态审批；
- 多人反馈；
- 涉及内部架构的项目判断。

最终界面可以保持一致，但必须清楚区分“只读公开视图”和“内部可操作视图”，不能让 `localStorage` Mock 看起来像真实团队决策。

## 五、Roadmap 的最终呈现效果

### 5.1 Roadmap 最终要回答的问题

一个成熟的 Roadmap 页面，打开后应立即回答：

- 当前有哪些稳定 Track / Approach；
- 哪一条正在上升、哪一条停滞或存在冲突；
- 现在处于研究原型、工程验证还是生产采用；
- 本期真正改变了什么；
- 当前主要瓶颈和开放问题是什么；
- 哪些 Idea 由这些问题产生；
- 以上判断由哪些 Claim 支撑。

### 5.2 Roadmap 背后的运行机制

#### 输入边界

Roadmap 只读取：

- 已发布的 Machine Evidence Record；
- 已通过事实门禁的 Claim；
- 已确认的 Evidence Link；
- 上一个 Roadmap snapshot。

不读取：

- 未发布候选；
- Reader 润色文案；
- 仅由关键词推测的关系；
- 未回到 A 级来源的 Radar 摘要。

#### 更新触发

新一期归档后：

1. 找出本期受影响 Topic；
2. 为本期新增 Machine Item 物化 Claim；
3. 把 Claim 路由到已有 Track、候选新 Track 或 unclassified ledger；
4. 判断它是新增证据、收窄、挑战还是改变现有判断；
5. 生成结构化 diff；
6. 通过完整性与删除保护校验；
7. 在所有受影响 Topic 完成后发布新 snapshot。

#### 判断维度

每个 Track 分别维护：

- `maturity`：技术成熟度；
- `momentum`：外部进展动量；
- `evidence_confidence`：判断证据强度；
- `consensus`：来源之间是否一致；
- `applicability`：对当前关注场景的适用程度。

这些维度必须分别计算和展示，不能重新压回一个 `status`。

#### 双时间轴

Roadmap 同时保留：

- 外部事件时间：来源何时发布、Release 何时发生；
- 内部观察时间：何时进入日报、何时改变系统判断。

默认时间线以外部事件时间排序；“我们的观察历史”作为可切换视图。

#### 变化判定

新文章本身不自动算 Roadmap 变化。只有以下情况才计入“实质变化”：

- 新 Track 出现；
- 已有 Track 发生 split / merge；
- 出现新的 Milestone；
- maturity、momentum、consensus 或 applicability 改变；
- Open Question 被打开、收窄或解决；
- 关键 Claim 被挑战、替代或失效。

其他情况写入 `evidence_only_no_judgement_change`，避免页面不断制造假变化。

### 5.3 Roadmap 桌面端界面

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Roadmap / Agent 语义加速                         已同步 08-29 · 当前完整 ✓ │
│ 当前判断：一句可以复述的综合判断                 本期 2 项实质变化          │
├──────────────┬─────────────────────────────────────┬───────────────────────┤
│ Topic        │ 当前 Landscape                      │ 为什么这样判断        │
│              │                                     │                       │
│ Agent 加速  2│ [Track A] 上下文构建               │ 系统推理              │
│ TPN         1│ 成熟度：工程验证  动量：上升        │ 当前判断文本          │
│ 跨域传输    0│ 置信度：中      共识：混合          │                       │
│ AI 芯片     1│ ── Milestone ──●────●────          │ 支持 Claim 3          │
│ ...          │                                     │ 反对 Claim 1          │
│              │ [Track B] 工具执行链               │ 限制 2                │
│ Track 筛选   │ 成熟度：研究原型  动量：稳定        │                       │
│ 证据类型     │ ── Milestone ──●────               │ 原始来源 / 日报       │
│ 时间范围     │                                     │ [打开 Evidence Path]  │
│              │ Open Questions                     │                       │
│              │ 1. ……                     → 2 Ideas│                       │
└──────────────┴─────────────────────────────────────┴───────────────────────┘
```

### 5.4 Roadmap 页面层级

#### 第一屏：Current State

第一屏不先展示长时间线，而是展示：

- 一句话当前判断；
- 最后一次实质变化；
- Track 数；
- maturity / momentum / confidence / consensus 摘要；
- 本期新增变化；
- 最大 Open Question；
- 关联 Idea 数。

#### 第二屏：Track 对比

使用矩阵或并列卡片比较：

- 解决的问题；
- 核心机制；
- 成熟度；
- 当前主要边界；
- 代表 Milestone；
- 支持与冲突证据；
- 最近变化。

用户不需要在多条时间线之间来回猜差异。

#### 第三屏：Trajectory

时间线只显示有信息增量的事件：

- Milestone；
- 关键负面结果；
- 生产或标准采用；
- 分支的建立、拆分与合并；
- 判断变化。

普通文章收录进入 Evidence Drawer，不占据主时间线。

#### 第四屏：Open Questions 与 Watch Triggers

每个问题显示：

- 为什么尚未解决；
- 当前缺失的 Claim 类型；
- 什么新信号会改变判断；
- 是否已有 Idea；
- 下一次复查日期。

### 5.5 Roadmap 右侧 Evidence Drawer

点击任何 Track、Milestone 或状态时，右栏展示：

```text
系统推理
“该方向已经从研究原型进入工程验证。”

支持
✓ Claim A  直接证据  A级来源  独立团队 1
✓ Claim B  部署证据  A级来源  独立团队 2

挑战与限制
! Claim C  只在特定硬件和负载下成立

适用边界
硬件 / 工作负载 / baseline / 时间有效性

时间
来源发布：08-21
首次进入日报：08-23
判断生效：08-26

[查看完整证据链] [打开日报] [打开原文]
```

### 5.6 Roadmap 的特殊状态

#### 证据稀疏

不显示空的 Stage 容器，改为：

```text
当前处于 Technology Landscape 模式。
已有证据能区分 3 条 Approach，但不足以确认阶段迁移。
还需要：生产部署证据、跨团队复现、长期稳定性数据。
```

#### 证据冲突

并列显示冲突 Claim、条件差异和系统当前如何处理冲突。不能把其中一边隐藏在详情深处。

#### 知识过期

页面冻结当前 snapshot，并在标题下明确显示“后续三期尚未物化”，同时禁止把摘要称为最新判断。

#### Track 改名或拆分

保留 alias 和 lineage，旧链接仍可访问，并显示“已拆分为 A / B”。

### 5.7 Roadmap 的界面验收标准

- 第一屏能看到当前判断、本期变化和知识水位线；
- 每个 Track 同时显示四个分离维度，而不是单一状态；
- 每个 Milestone 都说明“什么能力或边界变了”；
- 任何状态可在右栏追溯到 Claim；
- 普通新文章不会自动出现在主时间线；
- 低证据模式能说明还缺什么；
- 来源时间、观察时间和判断时间不会混淆；
- 从 Open Question 可以跳到关联 Idea。

## 六、Idea Bank 的最终呈现效果

### 6.1 Idea Bank 最终要回答的问题

Idea Bank 不是灵感收藏夹，而是验证与资源分配漏斗。它应回答：

- 这个 Idea 想解决什么问题；
- 核心机制与关键 Assumption 是什么；
- 哪些证据支持、挑战或限制它；
- 当前为什么处于这个状态；
- 最小验证是什么；
- 谁负责，何时复查；
- 做过哪些实验，结果如何；
- 是否应该继续、暂停、淘汰或进入立项准备。

### 6.2 Idea 背后的运行机制

#### Idea 的来源

外部情报驱动的 Idea 有两条主要生成通道：单条信息直接触发，以及多条信息联合综合。为了避免把“同一期多来源”和“真正跨期”混在一起，界面与数据契约使用三个自动来源标签：

- `单条证据触发`：一条强 Claim 形成 Idea Seed；
- `同一期跨来源综合`：同一期多个独立 Claim 暴露共同瓶颈、组合机会或冲突；
- `跨期综合`：至少两个不同期次的 Claim 共同形成新判断。

Idea 还可以来自：

- Roadmap Open Question；
- 内部人工提出的问题或方案；
- Experiment 结果产生的新分支。

来源必须作为不可变 Origin Event 显式记录，包括来源类型、触发期次、Claim、Evidence Record、综合理由、知识 snapshot 和生成者。后续增加支持证据不会改变 Idea 最初的产生方式。系统不能因为多篇文章属于同一 Topic 就自动制造 Idea，也不能用当前证据数量反推它是单条触发还是跨期产生。

#### 两段自动发现机制

新一期归档后，系统先对每个新增 Claim 运行单条候选发现，再把本期新增 Claim、同 Topic 历史 Claim 和 Roadmap Open Question 交给跨来源/跨期综合：

```text
新增 Claim → 单条候选发现 ───────────────┐
                                         ├→ 去重与 lineage 判断 → create / update / split / merge / no-op
新增 Claim + 历史 Claim + Roadmap Gap    │
              → 跨来源 / 跨期综合 ───────┘
```

跨期候选必须引用至少两个不同 issue，并包含至少一个本期触发 Claim；同一期多条材料只能标为跨来源综合。候选先与已有 Idea 比较问题、机制和目标，不能绕过去重直接落库。

产生方式和证据成熟度相互独立：单条 Seed 后续可以获得跨期支持，但其 Origin 仍是单条触发；跨期 Idea 也不能仅凭文章数量自动表现为高置信或进入更高状态。

#### Idea 身份

Idea 首次创建时获得不可变 ID。问题、机制和目标形成可版本化 identity signature，用于相似检测，不直接决定对象 ID。

当语义变化明显时，系统提出：

- 保持同一 Idea 并更新 frame；
- split 为多个 Idea；
- merge 到已有 Idea；
- 创建新的 Solution Concept 并链接原 Research Hypothesis。

任何操作都保留 lineage。

#### Assumption 是证据挂载点

一个 Idea 不再只有一个大段 hypothesis，而是拆成若干关键 Assumption，例如：

- 机制在目标负载下成立；
- 端到端收益不会被额外开销抵消；
- 所需数据或接口可获得；
- 部署复杂度在可接受范围；
- 收益能够迁移到内部场景。

Evidence Link 和 Experiment Result 均挂到具体 Assumption。

#### 状态迁移

状态迁移由确定性门槛检查，AI 可以提出建议，但高影响状态需要人工确认：

```text
seed → framed → evidence_building → ready_to_validate → validating
                                                    ├→ validated_positive
                                                    ├→ validated_negative
                                                    └→ inconclusive

validated_positive → proposal_candidate
任意状态 → parked
parked / rejected → reopened
```

每次迁移保存：

- before / after；
- 触发 Assumption、Claim 或 Result；
- actor；
- 规则和模型版本；
- reason；
- snapshot hash；
- 下一次复查时间。

#### 验证闭环

Validation Plan、Experiment Run 和 Result 是独立版本对象：

```text
Idea
├── Assumption A ── Claim / Evidence
├── Assumption B ── Claim / Evidence
├── Validation Plan v1
│   └── Experiment Run 1 ── Result
├── Validation Plan v2
│   └── Experiment Run 2 ── Result
└── Decision Log
```

结果必须回流到 Assumption 和 Idea 状态，不能只作为附件存在。

### 6.3 Idea Bank 组合视图

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Idea Bank                      12 个活跃 · 3 个待验证 · 2 个本周需复查    │
├──────────────┬─────────────────────────────────────┬───────────────────────┤
│ 筛选         │ 组合看板 / 表格                     │ Idea 快速预览         │
│              │                                     │                       │
│ Topic        │ 标题          状态      证据  验证  │ 为什么存在            │
│ 类型         │ Idea A        待验证    中    低成本│ 关键 Assumption       │
│ 状态         │ Idea B        观察中    低    中成本│ 当前阻塞              │
│ Owner        │ Idea C        验证中    高    运行中│ 下一步                │
│ Review Due   │                                     │ 关联 Roadmap          │
│ 证据强度     │ [高价值/快信号] [高不确定性]       │ [打开完整详情]        │
│ 验证成本     │                                     │                       │
└──────────────┴─────────────────────────────────────┴───────────────────────┘
```

### 6.4 组合视图默认展示的字段

每张 Idea 卡或每一行至少显示：

- 标题；
- Idea 类型；
- 产生方式：单条触发 / 跨来源综合 / 跨期综合 / Roadmap gap / 人工 / Experiment；
- 触发期次，以及涉及的 issue / Claim / 独立来源数量；
- 当前状态；
- 关联 Topic / Roadmap gap；
- 支持、反对、限定证据摘要；
- Assumption 完整度；
- 验证成本；
- time-to-signal；
- Owner；
- review due；
- 当前 blocker；
- 下一步动作。

不建议只展示状态和更新时间。

### 6.5 Idea 详情页

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Idea：用……解决……                evidence_building · Owner 李× · 09-10复查│
│ 产生方式：跨期综合 · 3期 / 4 Claims / 3独立来源                            │
│ 来源路径：Roadmap / Track A / Open Question 3                              │
├───────────────────────────────────────────────┬────────────────────────────┤
│ 当前决策摘要                                  │ 为什么是这个状态           │
│ 价值：……  最大不确定性：……  下一步：……      │ Decision Event             │
├───────────────────────────────────────────────┼────────────────────────────┤
│ Assumption                                    │ Evidence Drawer             │
│ A1 机制有效                  支持2 / 反对1     │ Claim、条件、来源定位       │
│ A2 端到端收益不被开销抵消    支持1 / 待验证   │                            │
│ A3 可部署                    未知              │                            │
├───────────────────────────────────────────────┴────────────────────────────┤
│ Validation Plans                                                           │
│ v1 建议验证 · 尚未执行  [输入] [baseline] [metric] [支持/否定阈值]         │
│ v2 执行中 · Run 2 · 进度 60%                                               │
├────────────────────────────────────────────────────────────────────────────┤
│ Decision Timeline：created → framed → evidence_added → ready_to_validate    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 6.6 Idea 页面最重要的四个区块

#### 当前决策摘要

用一小段话回答：

- 现在为什么值得继续或为什么暂停；
- 最大不确定性；
- 下一次决策需要什么信号。

#### Assumption Ledger

按 Assumption 展示：

- 当前状态：supported / challenged / unknown / validated；
- 支持与反对 Claim；
- 适用条件；
- 是否已有实验覆盖；
- 下一步证据需求。

#### Validation / Experiment

把“建议怎样验证”和“已经做了什么”完全分开：

- suggestion；
- approved plan；
- running；
- completed；
- inconclusive；
- invalidated run。

#### Decision Timeline

每条记录必须能展开看到：

- 谁做的；
- 根据什么；
- 当时有哪些证据；
- 状态为什么变化；
- 后来是否被新证据修正。

### 6.7 人工操作

内部可操作版本支持：

- 接受或拒绝 AI 的状态建议；
- 指派 Owner；
- 设置 review due；
- 创建 Validation Plan；
- 登记 Experiment Run / Result；
- 标记 Assumption 需要更多证据；
- 发起 merge / split；
- parked / reopen；
- 导出立项材料。

所有操作写入审计日志，不能直接修改历史状态。

### 6.8 Idea 的特殊状态

#### 只有一条强证据

允许创建 Seed，但明确显示“单条证据触发、尚未独立验证”，同时列出触发 Claim 和缺失证据，不能表现成已形成共识。后续获得跨期支持时更新证据成熟度，不改写 Origin。

#### 跨期综合但来源并不独立

显示“跨期综合”与“独立来源不足”两个并存标签。跨期出现次数不等于证据强度，不能因为同一团队、同一数据或同一假设在多期重复出现而自动升级状态。

#### 支持和反对证据并存

按 Assumption 和适用条件拆开，不用简单票数决定。

#### 很久没有新证据

显示 stale / review overdue，不自动 rejected。可建议 parked。

#### 验证失败

区分：

- 核心假设被否定；
- 实验设计无效；
- 数据不足；
- 当前环境不适用；
- 工程成本过高。

#### Idea 被合并或拆分

旧 ID 仍可访问，页面显示完整 lineage 和迁移原因。

### 6.9 Idea Bank 的界面验收标准

- 组合视图能直接看出哪些 Idea 需要行动；
- Idea 详情第一屏能回答“为什么存在、现在怎样、下一步是什么”；
- 每个 Idea 都能看见产生方式、最初触发 Claim 和不可变 Origin Event；
- 单条触发、同一期跨来源和跨期综合在界面上可区分，且与当前证据成熟度分开；
- 证据挂在具体 Assumption，而不是整张卡；
- 建议验证和实际结果视觉上明确分开；
- 每个状态变化都能展开到证据快照；
- proposal candidate 必须能看到已完成验证或人工豁免；
- 从 Idea 能跳回 Roadmap gap，也能打开 Evidence Path；
- 公开只读面和内部操作面边界清楚。

## 七、Evidence Explorer 的最终呈现效果

### 7.1 最终名称和定位

建议把最终模块命名为 `Evidence Explorer`，中文可用“证据浏览器”或“证据链”。

它不是为了证明系统“有一个知识图谱”，而是为了回答：

- 某个判断依据什么；
- 哪些证据互相冲突；
- 某条来源影响了哪些对象；
- 某个 Idea 的关键证据缺口是什么；
- 某次状态变化是否有充分依据。

当前 Archive Atlas 可以保留为 Evidence Explorer 下的“按日报浏览”视图。

### 7.2 Evidence Explorer 背后的运行机制

#### 图谱是确定性投影

权威对象来自：

- Source Document；
- Published Evidence Record；
- Claim；
- Roadmap Track / Milestone / Open Question；
- Idea / Assumption；
- Validation Plan / Experiment Result；
- Decision Event。

Graph Builder 根据显式 ID 和 Relation 生成 node / edge。浏览器只负责布局和交互，不在前端猜测语义边。

#### 显式边和候选边分开

- 实线：已确认、可追溯的 typed relation；
- 虚线：相似度或 AI 提出的候选关系；
- 候选边默认不参与 Roadmap 和 Idea 判断；
- 用户必须能看到边的产生方式、模型/规则版本和确认状态。

#### 变更传播

来源版本更新、撤回或 Claim 失效时：

1. 标记受影响 Claim；
2. 沿显式边找出受影响 Milestone、Assumption 和 Decision；
3. 生成复查任务；
4. 在对象页面显示 impact warning；
5. 经重新物化后更新状态。

图谱不仅用于浏览，也用于影响分析。

#### 有界加载

默认只加载：

- 当前对象；
- 上下游 1 跳；
- 用户选择后再扩展第 2 跳；
- 同时限制节点数和关系类型。

不要求 Pages 一次加载全部归档和全部关系。

### 7.3 Evidence Explorer 首页

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Evidence Explorer                                                         │
│ [搜索一个判断、Idea、Claim、来源或技术机制________________] [搜索]         │
├───────────────────────────────┬────────────────────────────────────────────┤
│ 常用入口                      │ 最近需要关注                              │
│                               │                                            │
│ • Roadmap 为什么变化          │ 3 个 Claim 出现冲突                        │
│ • Idea 为什么值得继续         │ 2 个 Idea 依赖的来源已更新                 │
│ • 当前有哪些证据缺口          │ 5 个 Open Question 到期复查                │
│ • 按日报浏览 Archive Atlas    │                                            │
└───────────────────────────────┴────────────────────────────────────────────┘
```

默认不是空白画布，也不是全局图。

### 7.4 路径视图：默认主视图

用户从 Roadmap 或 Idea 进入时，默认展示一条可读路径：

```text
原始来源
  ↓ 声明
Claim：机制 / 结果 / 限制
  ↓ supports / challenges / narrows
Roadmap Milestone 或 Idea Assumption
  ↓ caused
Roadmap Version Change 或 Idea Decision
```

每一层可以展开，但主路径始终保持可读。

### 7.5 关系图视图

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ [证据链] [关系图] [来源详情] [证据缺口]       时间 / 关系 / 来源 / 置信度 │
├───────────────────────────────────────────────┬────────────────────────────┤
│                                               │ Claim Inspector            │
│ Source A ──asserts──> Claim 1                 │                            │
│                           \                    │ 来源事实 / 系统推理         │
│                            supports            │ statement                  │
│                             \                  │ value / baseline / condition│
│                              Milestone X       │ source locator             │
│                             /                  │ verification               │
│ Source B → Claim 2 ─challenges                │ 影响对象 3                  │
│                                               │ [打开原文] [查看日报]       │
└───────────────────────────────────────────────┴────────────────────────────┘
```

### 7.6 Claim Inspector

点击 Claim 后右栏必须显示：

- Claim 类型；
- 精确 statement；
- value；
- baseline；
- condition；
- hardware / workload；
- source locator；
- source level；
- fact check / verification 状态；
- 来源版本与有效时间；
- 支持、挑战或限定哪些对象；
- 来源原文与日报入口。

系统推理型 Claim 还要列出它综合了哪些来源 Claim。

### 7.7 三个核心任务视图

#### Roadmap Change Trace

回答“为什么这个 Track 从研究原型变成工程验证”。

展示：before、after、触发 Claim、反对证据、系统推理、判断生效时间。

#### Idea Decision Trace

回答“为什么 Idea 从 observing 进入 ready_to_validate”。

展示：满足了哪些门槛、哪些 Assumption 仍未知、决策人、证据快照。

#### Evidence Gap View

回答“还缺什么才能做下一次判断”。

按以下类别组织：

- 缺 baseline；
- 缺真实硬件或负载；
- 缺独立复现；
- 缺部署证据；
- 缺反例；
- 缺内部验证。

每个 gap 可以跳到 Watch Trigger 或 Validation Plan。

### 7.8 Archive Atlas 的保留方式

当前图谱已有的能力不必删除，可以降级为一个明确命名的视图：

```text
Evidence Explorer
├── Evidence Path
├── Typed Relation Graph
├── Evidence Gaps
└── Archive Atlas
    ├── 按日报
    ├── 按 Topic
    └── 按关键词
```

Archive Atlas 仍然可以使用浏览器端关键词、聚合和可视化，但页面必须注明这些关系只是浏览结构，不是证据语义。

### 7.9 Evidence Explorer 的特殊状态

#### Claim 没有 locator

历史迁移对象显示 `machine_summary_only`，允许使用但不能标成高置信、精确可定位证据。

#### 来源失效或修订

保留历史快照，显示当前可访问状态和受影响对象，不删除旧关系。

#### 候选关系

用虚线、低饱和样式和“待确认”标签，默认筛选器可以完全关闭。

#### 图过大

自动切换到分组、路径或列表，不以强行渲染全部节点为目标。

### 7.10 Evidence Explorer 的界面验收标准

- 默认入口是搜索和任务视图，不是空白全局图；
- 浏览器不生成支持、反对、演进等语义边；
- 从任一判断都能看到 source locator 和适用条件；
- 明确区分来源事实、系统推理和决策；
- 实线关系全部可追溯，候选关系全部可关闭；
- 能反向查看一条 Claim 影响的 Roadmap、Idea 和 Decision；
- 能展示证据冲突和缺口；
- Archive Atlas 被明确标成结构浏览视图。

## 八、三部分联动后的完整用户旅程

### 8.1 新日报发布后的系统旅程

```text
日报归档成功
→ 新 Machine Item 形成 Evidence Record
→ 已验证 facts 物化为 Claim
→ Claim 更新受影响 Roadmap Track / Milestone
→ Roadmap 新增或收窄 Open Question
→ 新增 Claim 运行单条 Idea Candidate 发现
→ 新增 Claim、历史 Claim 与最新 Roadmap Gap 运行跨来源 / 跨期 Idea Synthesis
→ 候选经过去重、lineage 与创建门槛检查
→ 已有 Idea 的 Assumption 获得支持或反对证据
→ 系统提出 Idea 状态建议
→ 完整 snapshot 校验并发布
→ 首页展示“本期真正改变的 3 件事”
```

### 8.2 技术负责人查看某个方向

```text
首页“Roadmap 变化”
→ 打开 Topic Current State
→ 比较 Track
→ 点击本期 Milestone
→ 右栏查看支持和冲突 Claim
→ 打开 Evidence Path
→ 返回 Open Question
→ 查看关联 Idea
```

整个过程中不需要手工记住文章标题或复制 item ID。

### 8.3 团队评审一个 Idea

```text
Idea Portfolio 中筛选“本周需复查”
→ 打开 Idea
→ 查看当前决策摘要
→ 逐条审查 Assumption
→ 展开支持、反对和内部 Result
→ 检查验证门槛
→ 接受 ready_to_validate 建议
→ 指派 Owner 和 review due
→ 创建 Experiment Run
```

### 8.4 新证据推翻旧判断

```text
Source 新版本或负面结果进入日报
→ 新 Claim 标记 challenges / contradicts
→ Graph 找到受影响 Milestone 与 Assumption
→ Roadmap 显示 contested
→ Idea 显示 challenged
→ 系统提出复查，不直接删除历史
→ 人工或规则完成新 Decision
→ 新 snapshot 发布，旧版本仍可回看
```

## 九、移动端与可访问性效果

### 9.1 移动端

三栏在移动端按任务顺序折叠：

```text
顶部状态与搜索
→ 当前对象摘要
→ 主内容
→ Evidence Drawer 作为底部抽屉
→ 左侧筛选作为全屏筛选层
```

移动端不强行展示复杂全图，默认使用 Evidence Path 和列表。

### 9.2 可访问性

- 所有状态不只依赖颜色；
- 图谱提供同等信息的列表或路径文本；
- 键盘可完成节点选择、展开和返回；
- tooltip 内容可在详情栏固定；
- 动画支持 reduced motion；
- 时间、数字和单位有稳定格式；
- 链接说明是“打开原文 / 打开日报”，不使用模糊的“点击这里”。

## 十、当前与最终形态的差距

### 10.1 总体差距矩阵

| 维度 | 当前状态 | 最终状态 | 差距等级 |
|---|---|---|---|
| 知识新鲜度 | 归档 9 期，长期知识停在第 6 期；校验仍通过 | 页面与 manifest 显示准确水位，落后时明确告警 | P0 / correctness |
| 更新闭环 | `knowledge prepare/apply` 需要独立手工执行 | 归档后自动触发，有界任务完成后原子发布 snapshot | P0 / correctness |
| 最小证据单元 | 整篇 Brief Item + URL + reason | 带条件、locator 和版本的 Claim | P1 / 基础能力 |
| 三部分关系 | Roadmap、Idea、Atlas 各自装配 | 共享 Claim 与 typed relation，可相互跳转 | P1-P2 / 核心架构 |
| Roadmap | 8 个对象全部为 v1 evidence timeline | Landscape、Track、Milestone、diff、Open Question | P2 / 产品核心 |
| Roadmap 状态 | 单一 `supported/emerging/contested/inferred` | maturity、momentum、confidence、consensus 分离 | P2 / 语义 |
| Roadmap UI | Topic、branch、timeline/stage 和链接 | Current State、Track 对比、Trajectory、Watch Trigger | P2-P3 / 体验 |
| Idea 生成 | 6 个固定 seed 对象；数据中隐含单条、同一期多条和跨期组合，但未见增量 application | 单条候选发现与跨来源/跨期综合双通道持续运行，并支持去重、拆分、合并、演化 | P2 / 产品核心 |
| Idea 来源追溯 | 只能从 evidence 日期和 created log 近似反推，无法区分出生方式与后续成熟度 | 不可变 Origin Event 记录来源类型、触发 Claim、期次、综合理由和 snapshot | P1-P2 / 语义与审计 |
| Idea 证据 | 整个 Idea 级的 for / against | Assumption 级 Evidence Link | P1-P2 / 语义 |
| Idea 验证 | suggestion_only | Plan、Run、Result、Decision 闭环 | P2-P3 / 运营 |
| Idea UI | 状态、字段、证据链接和本地反馈 | 组合看板、Assumption Ledger、实验与审批 | P3 / 体验 |
| Evidence Graph | issue / topic / item / keyword 结构图 | Claim 为中心的 typed Evidence Path / Graph | P2-P3 / 核心能力 |
| 图谱边 | 浏览器端结构和关键词关系 | 后端确定性生成、带 provenance 的显式关系 | P2 / 可信度 |
| 时间语义 | 主要使用 issue date | 来源时间、观察时间、判断时间分开 | P1-P2 / 语义 |
| 冲突处理 | Schema 支持部分 against，但实际数据为 0 | 冲突、限定和适用条件成为一等展示 | P2-P3 / 体验 |
| 决策治理 | localStorage Mock，不影响真实对象 | 有 actor、权限、审批和审计的内部操作面 | P3-P4 / 治理 |
| 历史与恢复 | 单文件历史与 application 意图存在，但 bundle 非原子 | 完整 snapshot、对象版本、恢复与 impact analysis | P0-P2 / 工程 |

### 10.2 Roadmap 当前差距

当前已有的基础：

- Topic 和 branch 导航；
- evidence timeline；
- stage / timeline 详情入口；
- 支持和反对证据的展示位置；
- 证据不足时不强造阶段；
- 三栏布局。

关键缺口：

- 当前所有 Roadmap 都还没有 stage、milestone 或 open question；
- branch 主要等于配置中的 direction，尚未形成外部技术 Track；
- 没有 Current State 和 Track 对比；
- 没有 maturity、momentum、confidence、consensus 的分离表达；
- 没有真正的 structured diff；
- 没有 Watch Trigger；
- 时间线是收录史，不是清楚的外部技术轨迹；
- 无法从 Roadmap 直接看到关联 Idea；
- 页面没有知识滞后告警。

从 UI 外观上看，现有 Roadmap 已经具备“列表 + 右侧详情”的骨架；从产品能力上看，最终目标依赖的核心机制与决策信息大部分尚未落地。主要工作不在 CSS，而在长期知识对象和变化机制。

### 10.3 Idea Bank 当前差距

当前已有的基础：

- Research Hypothesis 与 Solution Concept 分类；
- 稳定 Idea 文件；
- 支持、反对证据位置；
- validation plan；
- decision log；
- Topic、类型、状态筛选；
- 页面明确 suggestion only；
- 本地反馈不会偷偷改变真实状态。

关键缺口：

- Idea 仍是预置 seed，没有持续增量漏斗；
- Prompt 虽能看到本期新增证据和 Topic 全部历史证据，但没有分别执行单条候选发现与跨期综合；
- Schema 没有 Origin Event，无法可靠区分单条触发、同一期跨来源和跨期产生；
- 页面没有产生方式、触发 Claim、综合理由或来源独立性标签；
- 证据没有挂到 Assumption；
- 没有 Owner、review due、验证成本和 time-to-signal；
- 状态没有完整迁移门槛；
- 没有 Plan / Run / Result 对象；
- 没有 merge、split、supersede lineage；
- 没有 Roadmap gap 来源关系；
- 没有真实操作和审批机制；
- 当前 6 个 Idea 只有 seed / observing，反对证据为 0，无法验证状态机是否真的运转。

现有页面已经是一个合格的“静态 Idea 详情阅读器”，但距离“技术验证与立项漏斗”仍有较大差距。

### 10.4 Evidence Explorer 当前差距

当前已有的基础：

- 按最新一期或全部归档切换；
- 按 Topic 或关键词浏览；
- core / supplement / radar 筛选；
- canonical identity 与跨期去重；
- 聚合展开、缩放和平移；
- 点击 Item 查看原始来源与日报；
- 页面明确不推断 EXTENDS / USES。

关键缺口：

- 节点没有 Source、Claim、Roadmap、Idea、Assumption、Decision；
- 边只有 issue-topic-item 和 keyword-topic-item；
- 关键词由浏览器从标题、摘要和硬编码词推导；
- 无法表达 supports、challenges、narrows、contradicts；
- 无法显示 source locator、baseline 和 condition；
- 无法做 Roadmap change trace 或 Idea decision trace；
- 无法进行来源失效后的影响分析；
- 默认入口仍然是图，而不是问题和证据路径。

因此当前模块可以保留为 Archive Atlas，但真正 Evidence Explorer 的核心语义层基本尚未开始。

### 10.5 共同差距

三部分共同缺少：

- 统一 Claim ID；
- typed Evidence Link；
- 一致的事实 / 推理 / 决策视觉语义；
- 完整知识水位线；
- 新期自动物化；
- 结构化 diff；
- 对删除、覆盖和跨对象并发的保护；
- 从判断到原文的统一 Evidence Path；
- 公开只读与内部操作的访问边界。

这些共同能力应先做成共享底座，不应由三个页面分别实现。

## 十一、与上一份文档的关系

### 11.1 两份文档的职责分工

| 文档 | 主要问题 | 主要读者 | 主要用途 |
|---|---|---|---|
| 上一份《现状诊断与优化方案》 | 为什么粗糙、底层应怎样重构、风险和优先级是什么 | 架构、后端、Agent 工作流、数据治理负责人 | 技术设计、任务拆分、正确性审查 |
| 本份《最终呈现蓝图与差距分析》 | 最终产品长什么样、用户怎样使用、机制和界面怎样验收 | 产品、设计、前端、架构、业务负责人 | 目标对齐、原型设计、体验验收 |

### 11.2 本文如何建立在上一份之上

本文中的最终效果依赖上一份提出的技术基础：

| 本文的目标效果 | 上一份提供的技术基础 |
|---|---|
| 任意判断可追到具体 Claim 和来源定位 | Evidence Registry、Claim Ledger、Evidence Link |
| Roadmap 展示 Track、Milestone 和结构化变化 | Roadmap v2、分离状态维度、structured diff |
| Idea 按 Assumption 管理证据并进入验证 | Idea v2、状态门槛、Experiment 对象 |
| Evidence Explorer 展示 typed relation | Graph 作为确定性投影，不由前端猜边 |
| 页面准确显示知识是否最新 | knowledge manifest、archive watermark |
| 多对象更新后一次发布完整版本 | 原子 snapshot、覆盖账本、对象级锁 |
| 历史判断可回看且不会静默改写 | version、decision event、append-only history |

### 11.3 本文对上一份的补充

上一份已经提出了统一知识模型和实施顺序，但没有把最终界面细化到以下程度：

- 页面第一屏应该显示什么；
- 三栏各自承担什么职责；
- Roadmap 如何比较 Track；
- Idea 如何按 Assumption 展示证据；
- Evidence Explorer 默认为什么应使用路径视图；
- 低证据、冲突、过期和来源失效如何呈现；
- 三部分之间如何形成连续用户旅程；
- 哪些内容属于公开只读面，哪些需要内部操作面；
- 用什么体验标准判断重构是否成功。

这正是本文补上的部分。

### 11.4 两份文档如何一起使用

建议实施时按以下方式使用：

1. 用本文确定目标页面、用户任务和最终验收；
2. 用上一份文档确定底层对象、流水线、版本和正确性方案；
3. 前端原型发现缺字段时，回到统一知识模型补充，而不是在浏览器临时推导；
4. 后端准备新增字段时，检查它是否支持本文中的明确用户任务；
5. 每个 PR 同时说明它推进了哪项技术能力和哪项目标体验；
6. P0 correctness 问题在任何视觉优化之前完成。

### 11.5 冲突时的优先级

如果两份文档在实施中出现表面冲突，按以下原则处理：

- 证据边界、事实隔离、发布完整性、幂等和可追溯性优先于视觉便利；
- 本文中的 UI 目标不能通过读取 Reader 文案、未发布候选或浏览器猜边来实现；
- 上一份文档中的底层方案可以因工程验证而调整，但必须继续满足本文的用户任务和验收效果；
- 如果某个界面效果无法在可信数据上实现，应显示诚实的降级状态，而不是填充推测内容。

## 十二、建议的产品交付顺序

### 第 0 阶段：让当前页面先说真话

交付效果：

- 顶部显示归档与知识水位；
- 当前落后三期时给出明确告警；
- 把当前“证据图谱”命名为 Archive Atlas 或标明其结构浏览属性；
- Roadmap 页面明确当前全部处于 evidence timeline；
- Idea 页面明确当前只有 seed / observing，且没有真实 Experiment；
- 清理 placeholder URL。

这一阶段不需要先完成 Claim Graph，但可以立即减少误解。

### 第 1 阶段：让三部分共享证据底座

交付效果：

- Claim Inspector 可用；
- Roadmap 和 Idea 都能打开统一 Evidence Path；
- 来源时间、观察时间和判断时间分开；
- 页面能显示支持、反对、限定和 locator；
- 新日报可自动生成完整知识 snapshot。

### 第 2 阶段：Roadmap 与 Idea 真正可工作

交付效果：

- Roadmap 出现 Current State、Track 对比、Milestone 和 Open Question；
- Idea 运行单条候选发现与跨来源/跨期综合两段机制，并保存不可变 Origin Event；
- Idea 出现 Assumption Ledger、状态门槛和 Roadmap gap 关联；
- 结构化 diff 和 Decision Trace 可用；
- 组合视图能帮助安排验证优先级。

### 第 3 阶段：验证与决策闭环

交付效果：

- Validation Plan / Run / Result 完整；
- 内部用户可审批状态、分配 Owner 和复查时间；
- 实验结果回流 Assumption；
- Evidence Explorer 可做 impact analysis；
- proposal candidate 可以导出可信立项材料。

### 第 4 阶段：高级探索与治理

交付效果：

- 候选关系、相似 Idea 和新 Frontier cluster 建议；
- 人工确认后进入正式知识；
- 质量指标、golden set 和历史重放；
- 过期 Claim、来源修订和长期停滞 Idea 的持续治理。

## 十三、最终验收场景

重构完成后，应使用以下真实任务验收，而不只检查页面是否渲染。

### 场景 1：查看某个 Topic 本期是否真正变化

验收人应能：

1. 在首页看到该 Topic 有 material change；
2. 打开 Roadmap 查看 before / after；
3. 看见 maturity、momentum、confidence、consensus 的变化；
4. 展开触发 Claim 和反对证据；
5. 打开原文 locator；
6. 确认普通新增文章没有被误当成 Milestone。

### 场景 2：评审一个准备验证的 Idea

验收人应能：

1. 从 Portfolio 找到 review due 的 Idea；
2. 看懂 Roadmap 来源问题；
3. 逐条查看 Assumption；
4. 确认支持和反对证据；
5. 检查 baseline、metric 和支持/否定阈值；
6. 看到 Owner、成本和 time-to-signal；
7. 接受或拒绝状态建议并留下审计记录。

### 场景 3：追查一个判断为什么成立

验收人应能：

1. 从 Roadmap 或 Idea 点击“查看证据链”；
2. 看见 Source → Claim → 判断 → Decision 路径；
3. 区分来源事实和系统推理；
4. 查看 condition、baseline 和 locator；
5. 识别候选边与已确认边；
6. 在 3 次点击内打开原始来源。

### 场景 4：新证据挑战旧判断

验收人应能：

1. 看见冲突告警；
2. 查看哪些 Claim 和对象受影响；
3. 确认旧 Roadmap / Idea 历史没有被删除；
4. 查看新旧适用条件差异；
5. 发起复查或新的 Experiment；
6. 在新 snapshot 中看到结构化状态变化。

### 场景 5：知识物化失败

验收人应能：

1. 在全局状态条看到 lagging；
2. 知道落后多少期和哪些 Topic；
3. 继续访问上一份完整 snapshot；
4. 不会看到半更新的 Roadmap、Idea 或图谱；
5. 修复后重跑不会重复 change、evidence 或 decision。

## 十四、一句话描述最终效果

最终形态不应是“Roadmap 页面、Idea 页面和一张图”，而应是一套连续的技术决策工作台：

> Roadmap 说明外部技术怎样变化和哪里仍有缺口，Idea Bank 把缺口变成可验证的假设与方案，Evidence Explorer 让每个判断、实验和决策都能回到明确证据；三者始终共享同一知识快照，并诚实展示新鲜度、冲突与未知。

达到这个效果后，日报就不再只是被归档的内容，而会持续转化为可以比较、验证、复查和最终支持立项的长期技术资产。

## 十五、Decision log

- 2026-08-29：将 Idea 的外部情报来源明确为单条触发与联合综合两条主通道，并把联合综合细分为同一期跨来源和跨期综合；界面必须同时展示不可变产生方式与可变化的证据成熟度，避免把跨期出现次数误当成证据强度。
