# 技术情报工作台：UI 页面内容 Brief

- Status: draft
- Created: 2026-08-30
- Last updated: 2026-08-30
- 视觉风格：未决定，不属于本文范围

关联设计：

- [Roadmap、Idea Bank 与证据图谱：现状诊断与优化方案](./2026-08-29-roadmap-idea-bank-evidence-model-redesign.md)
- [Roadmap、Idea Bank 与证据图谱：最终呈现蓝图与差距分析](./2026-08-29-roadmap-idea-bank-evidence-workbench-blueprint.md)
- [技术情报工作台：UI Style Brief Pack](./2026-08-30-technical-intelligence-ui-style-brief-pack.md)

## Problem and evidence

UI 设计需要先固定“页面里有什么”，再比较“页面长什么样”。内容和风格混在同一份 Brief 中，会让生图模型被某一种审美锁定，也无法公平比较卡通、可爱、编辑部或专业工具等方案。

本文只定义页面内容，不指定颜色、字体、组件形态、布局、画布比例、插画和视觉气质。

## Goals and non-goals

### Goals

- 明确需要设计的页面；
- 明确每个页面要回答的问题；
- 明确每个页面必须出现的信息；
- 提供一套跨页面一致的示例数据；
- 作为所有视觉风格方案共享的内容基线。

### Non-goals

- 不定义风格和布局；
- 不定义后端 Schema；
- 不设计内部审批、评论和项目管理；
- 不要求对每篇论文提取完整实验参数。

## Constraints and invariants

### 内容与风格分离

后续生成设计图时使用：

```text
本内容 Brief + 一份独立 Style Brief = 一套 UI 设计图
```

更换 Style Brief 时，页面内容和对象关系保持不变。

### 最小证据原则

普通论文只展示日报实际使用的信息：

- 结论；
- 机制；
- 关键结果；
- 最重要的边界；
- 原始来源。

workload、硬件、baseline、数据集和指标仅在理解当前 Claim 必不可少时出现。不存在时直接省略，不为了填满 UI 重新精读论文。

### Idea 的三个独立维度

Idea 必须分别表达：

- `产生方式`：单条触发、同一期跨来源、跨期综合、Roadmap 问题、人工或实验分支；
- `证据成熟度`：单来源、多来源、是否独立、是否存在反对证据；
- `当前状态`：Candidate、Seed、Evidence Building、Ready to Validate 等。

### 公开只读边界

当前目标是 GitHub Pages 只读页面。默认不展示内部 Owner、预算、私有项目、审批意见和敏感实验结果。

## Proposed design

### 1. 页面清单

每张设计图只表现一个页面。

| 页面 | 页面需要回答的问题 |
|---|---|
| 首页 | 本期真正发生了什么变化 |
| Roadmap 详情 | 一个技术方向现在走到哪里 |
| Idea Hub | 有哪些候选、正式 Idea 和验证项 |
| Idea 详情 | 一个 Idea 为什么存在、现在怎样、下一步是什么 |
| Evidence Explorer | 一个判断由什么证据支持 |
| Archive | 一期日报后来影响了什么长期知识 |

### 2. 所有页面共享的内容

#### 产品与导航

- 产品名：`技术情报工作台`
- 一级入口：`首页 / Roadmap / Idea Hub / Evidence / 归档`
- 搜索范围：`Topic、Roadmap、Idea、Claim、论文或来源`

#### 知识状态

- 最新归档期次；
- 长期知识物化到哪一期；
- 完整、落后或部分失败；
- 当前 Snapshot 或版本。

示例：`归档最新 2026-08-30 · 知识物化 2026-08-29 · 落后 1 期`

#### 统一语义

设计需要能够区分：

- 来源事实；
- 系统综合；
- 内部判断；
- 单条证据触发；
- 同一期跨来源综合；
- 跨期综合；
- 尚未独立验证；
- 存在冲突；
- 仅发现信号；
- 知识已过期。

本文不规定这些状态使用什么颜色、图标或组件。

### 3. 首页

#### 必须回答

- 本期哪些 Topic 的长期判断发生了变化；
- 本期产生或更新了哪些 Idea；
- 当前有哪些风险或异常。

#### 必须包含

1. 本期期次；
2. 发生实质变化的 Topic 数；
3. 新 Idea Candidate 数；
4. Idea 状态变化数；
5. 冲突、来源失效和知识落后数量；
6. 2～4 条最重要的技术变化；
7. 本期新产生或更新的 Idea；
8. 需要注意的异常状态。

#### 每条技术变化包含

- Topic；
- 变化前；
- 变化后；
- 触发证据；
- 当前证据状态；
- 是否进入 Roadmap。

首页不以累计论文数、节点数和装饰性统计作为主要内容。

### 4. Roadmap 详情

#### 必须回答

- 当前有哪些主要技术路线；
- 本期哪里发生了变化；
- 哪些问题还没有解决；
- 当前判断由什么证据支持或限制。

#### 必须包含

1. Topic 名称；
2. 当前一句话判断；
3. 当前模式：Signal Timeline、Landscape 或 Trajectory；
4. 主要 Track；
5. 每条 Track 的机制、成熟度、外部动量、证据状态和主要瓶颈；
6. 真正改变判断的 Milestone；
7. Open Questions；
8. Open Question 关联的 Idea；
9. 支持、反对和限制 Claim；
10. 日报与原始来源入口。

普通新增论文不作为 Milestone；没有足够证据时允许只展示 Landscape 或 Signal Timeline。

### 5. Idea Hub

#### 必须回答

- 系统刚发现了哪些 Idea Candidate；
- 哪些已经成为正式 Idea；
- 哪些已经进入验证。

#### 必须区分

- `Candidate Inbox`：系统提出、尚未确认；
- `Idea Portfolio`：已经接受并持续维护；
- `Validation`：已经进入验证。

#### Candidate 包含

- 标题；
- 产生方式；
- 触发期次；
- 为什么产生；
- 触发 Claim；
- 与已有 Idea 的相似关系；
- 建议结果：新建、补充、合并、拆分或忽略。

#### 正式 Idea 摘要包含

- 标题；
- Research Hypothesis / Solution Concept；
- 产生方式；
- 当前状态；
- 为什么值得存在；
- 支持、反对和限制证据摘要；
- 最大未知量；
- 最小验证方式；
- 关联 Topic / Roadmap gap；
- 下一步动作。

Candidate 和正式 Idea 不能混在同一集合中。

### 6. Idea 详情

#### 必须回答

- 这个 Idea 为什么存在；
- 当前证据怎样；
- 最大未知量是什么；
- 下一步应该做什么。

#### 必须包含

1. 标题、Idea 类型和当前状态；
2. 问题、机制、目标和预期效果；
3. Origin Event：最初怎样产生；
4. 证据成熟度：当前有多少独立证据；
5. 当前决策摘要；
6. 关键 Assumptions；
7. 每个 Assumption 的支持、反对、限制或未知；
8. 最小验证建议；
9. Decision Timeline；
10. 关联 Roadmap 和证据入口。

只有 Idea 真正进入验证后，才展示完整 Plan、Run、Result 和实验条件。

### 7. Evidence Explorer

#### 必须回答

- Roadmap 为什么发生变化；
- Idea 为什么存在；
- 当前缺少什么证据。

#### 必须包含的任务入口

- Roadmap 为什么变化；
- Idea 为什么存在；
- 缺少什么证据。

#### 默认证据路径

```text
原始来源
→ 日报采用的 Claim
→ Roadmap Milestone 或 Idea Assumption
→ 系统综合判断
→ Decision
```

默认内容是可阅读的证据路径，不是全局关系网络。

#### Claim 详情包含

- Claim；
- Claim 类型；
- 原始来源；
- 首次进入日报时间；
- 它支持、反对或限制什么对象；
- 最重要的适用边界；
- 日报和原文入口。

只有当 workload、硬件、baseline 或指标会改变 Claim 含义时才补充这些条件。

#### 关系状态

- 已确认关系；
- 候选关系；
- 支持；
- 反对；
- 限制；
- 失效。

### 8. Archive

#### 必须回答

- 这一期日报包含什么；
- 哪些内容进入了长期知识；
- 哪些内容改变 Roadmap 或产生 Idea。

#### 必须包含

1. 期次列表；
2. 当前期次日期和 Reader 入口；
3. Topic 和条目数量；
4. 当前期次的日报条目；
5. 每条内容的 Topic、摘要和来源；
6. 每条内容的长期影响；
7. 本期 Roadmap 变化数；
8. 本期 Idea Candidate 数；
9. 当前期次是否已经进入知识 Snapshot。

#### 长期影响状态

- 更新 Roadmap；
- 产生 Idea Candidate；
- 支持或反对某个 Assumption；
- 新增证据但未改变判断；
- 仅归档；
- 仅发现信号。

### 9. 共用示例数据

所有风格方案使用同一组示例，避免内容差异影响风格判断。

#### Topic 与变化

```text
Topic：KV Cache 与推理解耦
变化前：以完整 KV 传输为主
变化后：开始在传输、重算和就地计算之间动态选择
触发：3 个 Claims
```

#### Track

```text
完整 KV 传输 · 工程验证 · 动量稳定
选择性传输 · 原型 · 动量上升
重算 / 就地计算 · 原型 · 存在限制
```

#### Open Questions

```text
多租户 P95/P99 下的交叉点是否稳定？
代价预测错误会造成多大回退？
```

#### Idea

```text
标题：KV 传输、重算与就地计算的动态选择
类型：Research Hypothesis
产生方式：跨期综合
证据跨度：3 期 · 4 Claims · 3 个独立来源
状态：Evidence Building
最大未知量：网络带宽与缓存命中率变化时的策略交叉点
下一步：建立轻量仿真扫描关键区间
```

#### Assumptions

```text
A1 三种执行方式存在稳定交叉区间 · 支持 2 / 限制 1
A2 动态选择开销不会抵消收益 · 未知
A3 策略可迁移到多租户尾延迟 · 待验证
```

#### Claims

```text
Claim A · 必要 KV 优先传输 · 来源事实
Claim B · 就地 Prefill 删除一类传输 · 来源事实
Claim C · 收益依赖网络条件 · 适用限制
```

#### Archive 影响

```text
选择性 KV 传输缩短关键路径 · 更新 Roadmap · 支持 Idea A1
工具接口影响 Agent 成功率与成本 · 产生 Idea Candidate
新型光互联交换方案 · 新增证据但未改变判断
AI 状态层级的新介质探索 · 仅发现信号
```

### 10. 必须覆盖的非理想状态

每套风格至少选择其中 2～3 种进行表现：

- 知识落后；
- 部分 Topic 物化失败；
- 本期有新论文但没有实质变化；
- Idea 只有一条证据；
- Idea 跨期出现但来源不独立；
- 支持与反对证据并存；
- 来源失效或修订；
- Candidate 与已有 Idea 相似；
- Topic 证据不足，不能形成阶段；
- Claim 没有 workload、硬件或 baseline 信息。

## Compatibility and migration

- 本文只定义设计图内容，不改变现有站点；
- 历史 Idea 无法确定 Origin 时显示“历史 Seed，产生方式未记录”；
- 现有数据缺字段时可以省略或显示 unknown；
- 未来风格变化不得改变本文定义的核心内容。

## Failure, recovery, and rollback

- 生图模型遗漏核心信息时，按页面“必须包含”清单补充；
- 生图模型增加无关数据时，删除不属于本文的内容；
- 某种风格导致内容不可读时，只修改 Style Brief；
- 某个字段需要批量精读论文才能获得时，优先删除或改为按需展示。

## Verification

每套风格使用同一份内容验收：

- 首页能看出本期真正变化；
- Roadmap 能看出路线、变化和 Open Questions；
- Idea Hub 能区分 Candidate、正式 Idea 和 Validation；
- Idea 详情能区分产生方式、证据成熟度和当前状态；
- Evidence 能沿路径回到日报和原文；
- Archive 能说明一期日报的长期影响；
- 落后、单来源、冲突和无实质变化不会被隐藏；
- workload、硬件和 baseline 不会成为每篇论文的固定内容；
- 更换风格不会改变以上内容。

## Documentation impact

- 本文是所有 UI 风格方案共享的内容基线；
- 后续为不同视觉方向分别创建 Style Brief；
- 选定视觉方向后，再更新 Workbench Blueprint 的布局和交互；
- 后端只适配最终被采用的内容字段。

## Decision log

- 2026-08-30：将 UI 页面内容与视觉风格完全分离。
- 2026-08-30：本文不定义配色、字体、组件形态、布局和设计气质。
- 2026-08-30：所有视觉方向使用同一组示例数据，以便只比较风格差异。
- 2026-08-30：继续遵守最小证据原则，不为满足 UI 完整度批量精读论文。
