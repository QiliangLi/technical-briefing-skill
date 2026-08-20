# 技术情报系统 Roadmap、Idea Bank 与 GitHub Pages 重构设计

文档日期 2026-08-20  
状态 已完成需求澄清，等待进入实现  
适用仓库 `technical-briefing-skill`

## 一、背景与目标

领导反馈重新确定了这套系统的用途。日报负责给团队持续输入外部技术信息，并为三个月后的技术立项积累材料。真正需要长期保存的内容包括外部技术演进、可以验证的研究问题、可能形成方案的技术 Idea，以及这些判断所依赖的日报和原始来源。

目标流程如下。

```text
学术界、工业界、Builder、开源社区
                ↓
              日报
                ↓
        已发布证据持续积累
                ↓
      外部技术 Roadmap 更新
                ↓
   Research Hypothesis 与 Idea
                ↓
  仿真、数据分析、基准或原型建议
                ↓
      继续观察、淘汰、立项候选
```

日报仍是必要入口。Roadmap 和 Idea Bank 承担跨期整理与立项准备。GitHub Pages 用来阅读、比较和溯源，知识图谱降为辅助证据浏览工具。

## 二、已经确认的产品决定

### 2.1 Roadmap 只表达外部技术演进

第一阶段不叠加内部项目路线。Roadmap 展示学术界和工业界如何推进某个技术方向，包括阶段、分支、转折、收敛迹象、争议和开放问题。

页面以现有大专题为入口，真正的演进分支落到 Direction 或稳定的技术假设层。一个大专题可以同时拥有多条分支。

Roadmap 只使用已发布日报中的证据。旧候选、未发送内容和后来重新发现的文章不能倒灌进历史 Roadmap，也不能冒充当时已经进入团队视野的信息。

### 2.2 Roadmap 随日报增量更新

新日报涉及某个 Topic 时，只触发该 Topic 的 Roadmap 更新。更新过程读取该 Topic 的全部已发布历史证据并重新物化，不能只在旧文案末尾追加内容。

新证据没有改变阶段、分支或判断时，保存一次 `no_material_change` 记录。新证据带来实质变化时，生成新版本，并保存变化说明、证据引用和判断时间。

AI 可以判断多个来源是否属于同一阶段、某个方向是否发生转折，以及证据是否支持收敛。每个判断都要能回到日报条目和原始来源，并标明证据状态。建议使用以下状态。

- `supported`，已有多项证据支持。
- `emerging`，刚出现的趋势，证据仍少。
- `contested`，来源之间存在冲突。
- `inferred`，属于系统基于已发布证据作出的归纳。

当材料只够说明出现过哪些信息，不足以识别技术阶段时，页面应显示“证据时间线”，不能强行生成 Roadmap 阶段。

### 2.3 边界探索先聚类，再形成 Roadmap 分支

边界探索不维护一条包罗所有内容的统一 Roadmap。系统先把已发布的边界信号聚成临时方向，例如新型运行时、数据库并发机制、新存储层级和编译器机制。

某个临时方向持续出现、形成稳定机制或产生 Idea 后，才升级为独立 Roadmap 分支。升级记录需要保存来源聚类、首次进入日报的时间和触发升级的证据。

### 2.4 Idea Bank 同时保存研究假设和技术方案

Idea Bank 包含两种一等对象。

- `research_hypothesis`，可以通过仿真、数据分析、基准测试或原型初步回答的研究问题。
- `solution_concept`，具有明确问题、技术机制和预期效果，可能继续发展成立项方案的 Idea。

“补测 P95”“增加一项报表”“继续跟踪样片”属于验证动作，不能单独成为 Idea。验证动作必须挂在某个研究假设或技术 Idea 下面。

单篇强信息可以产生 Idea Seed。后续学术证据、工业证据、边界探索信号和人工反馈可以增强、修正或反对它。相似 Idea 可以由 AI 提出合并建议，不能仅因为属于同一个 Topic 或同一个项目问题就直接合并。

### 2.5 AI 可以自动淘汰 Idea，记录必须完整

AI 可以根据新增公开证据自动把 Idea 标为淘汰。淘汰不等于删除。系统必须保存淘汰原因、支持证据、反对证据、判断版本和发生时间。

新证据推翻旧判断时，Idea 可以重新打开。建议采用以下状态。

```text
seed
  ↓
observing
  ↓
ready_for_validation
  ↓
promising / rejected / proposal_candidate
```

没有足够材料时保持 `observing`。不能因为暂时没有仿真工具或数据就自动淘汰。

### 2.6 第一阶段只给验证建议，不实际执行仿真

当前阶段不建设真实仿真平台，也不生成虚构的仿真结果。每个研究假设或技术 Idea 可以给出一份具体的验证建议，至少包含以下内容。

- 推荐使用仿真、数据分析、基准测试、原型验证或持续观察中的哪一种方式。
- 需要建立什么最小模型。
- 输入参数和合理的扫描范围。
- 对照基线。
- 需要观察的指标。
- 支持该 Idea 的判据。
- 否定该 Idea 的判据。
- 该验证方法无法覆盖的现实条件。

页面必须把“建议怎样验证”和“已经完成验证”清楚分开。

### 2.7 来源多样化与边界探索只影响未来日报

旧归档只做表达迁移，不重新选择当期内容。旧评分机制曾经筛掉的博客和工业文章没有进入 archive，公开阅读版不能把后来找到的内容补进旧日报。

新一期开始执行 Academic Primary、Industry Builder 和 Frontier Exploration 的新规则。Roadmap 后续可以同时展示学术与工业证据，但证据等级、材料性质和结论边界必须保留。

### 2.8 Fact Check 使用现有风险触发方案

现有设计保留确定性 Evidence Gate，高风险条目才进入 LLM 复核。此次重构不恢复全量 Fact Check，也不把历史读者层迁移变成一次完整事实流程重跑。

## 三、当前实现的主要偏差

当前 Roadmap 按 `Topic → 日报日期 → Direction → 条目标题` 排列，更接近专题证据时间线。它没有技术阶段、分支变化、转折原因和开放问题。

当前 Idea Bank 用 `Topic + project_question` 合并多期 `project_insights`，并把最新 `next_action` 当作 Idea 标题。不同技术方案可能因为回答同一个问题而被错误合并。`next_action` 本身也可能只是实验动作，不能直接代表 Idea。

Roadmap 和 Idea Bank 都在浏览器中临时扫描 archive 后生成。仓库里没有持久化的 Roadmap 对象、Idea 对象、版本历史和增量物化过程。

GitHub Pages 仍是一张较长的单页。Roadmap、Idea Bank、知识图谱和归档顺序堆叠，用户很难完成“看方向变化、选择 Idea、检查证据”的连续操作。

页面数据加载还有一项需要修复。`papers.json` 已经包含 Radar 时，前端又从 `issue.json` 重建一遍 Radar，可能造成统计和图谱重复。

## 四、旧归档读者层迁移

### 4.1 迁移目的

当前 6 期 archive 保留了 98 条结构化 core 或 supplement 条目，以及 22 条 Radar。所有正式条目仍保存 `core_conclusion`、`mechanism`、`result`、`boundary`、`project_relevance`、来源和稳定 ID，因此可以直接生成最新版读者表达。

迁移只改展示层。采集、相关性、事实抽取、Top4 选择、角色、分数、日期、来源和图片规划都不重跑。

### 4.2 文件布局

旧的已发送版本需要永久保存。根目录继续使用稳定文件名，避免 Pages 和外部链接变化。

```text
archive/issues/2026-08-17/
├── original/
│   ├── email.html
│   └── email-illustrated.html
├── email.html
├── email-illustrated.html
├── issue.json
├── papers.json
├── reader.json
└── publication-manifest.json
```

现有 archive 只有一个 `email.html`，而旧归档脚本可能把 illustrated 版本复制后命名为 `email.html`。迁移时只能把现存文件原样保存到 `original/`，不能伪造一个没有保留下来的纯文字版本。

根目录的 `email.html` 和 `email-illustrated.html` 始终代表当前 Reader Contract 下的公开阅读版。Pages 默认打开根目录版本，同时提供“查看实际发送版”的次级入口。

### 4.3 新日报与旧归档使用同一条路径

新日报归档前执行以下检查。

1. Reader Projection 已完成，每条 reader item 绑定当前 Machine Item hash。
2. 所有稳定 ID、Topic、Direction、角色、来源 URL 和数字通过校验。
3. `email.html` 和 `email-illustrated.html` 都按当前 Reader Contract 生成。
4. 实际发送版本复制到 `original/`。
5. 当前公开阅读版复制到根目录稳定文件名。
6. `publication-manifest.json` 记录 Reader Contract 版本、输入 hash、输出 hash 和生成时间。

归档命令重复运行时，如果输入 hash 和 Reader Contract 版本未变化，结果必须保持不变。Reader Contract 升级后只重建根目录公开版，不能改写 `original/`。

### 4.4 需要迁移的表达范围

迁移覆盖以下内容。

- headline 和本期判断。
- 深度条目的标题、导语、正文和可选 takeaway。
- 专题补充的标题与一到两句摘要。
- Radar 的 signal 和 summary。
- watch next 等直接展示给读者的文本。

迁移不得改变条目数量、角色、Topic、Direction、日期、分数、来源、URL、`brief_item_id` 和原始数字。Reader 文本可以省略次要事实，不能增加新事实。

### 4.5 Pages 读取 reader projection

只重写 HTML 无法解决 Pages 中的旧表达。当前页面主要读取 `issue.json` 和 `papers.json`。因此 `reader.json` 需要提供稳定 ID 到最新读者文案的映射，Pages 展示时合并 Machine 数据与 Reader 数据。

Roadmap 和 Idea Bank 的分析输入仍然使用 `issue.json` Machine 数据。`reader.json` 只负责让人看懂，不能成为长期判断的事实源。

## 五、Roadmap 数据模型

建议新增稳定对象，存放在 `knowledge/roadmaps/<topic_id>.json`。一个 Topic 内允许存在多个分支。

```json
{
  "roadmap_id": "roadmap_agent_acceleration",
  "topic_id": "agent_acceleration",
  "version": 3,
  "evidence_scope": "published_archive_only",
  "updated_by_issue": "2026-08-21",
  "change_type": "material_change",
  "summary": "当前外部演进判断",
  "branches": [
    {
      "branch_id": "agent_harness",
      "name": "Agent Harness 与长任务运行环境",
      "status": "emerging",
      "stages": [],
      "open_questions": [],
      "evidence_item_ids": []
    }
  ],
  "change_log": []
}
```

每个阶段至少保存阶段名称、解决的问题、代表机制、开始进入归档的时间、支持证据、反对证据和到下一阶段的变化原因。

更新算法按 Topic 运行。系统加载旧 Roadmap、当前 Topic 的全部已发布证据和本期新增证据，随后生成完整新版本与结构化 diff。旧版本永久保留。

## 六、Idea Bank 数据模型

建议新增 `knowledge/ideas/<idea_id>.json`。Idea ID 不能使用 project question 直接代替，应由稳定的问题、核心机制和目标对象形成身份。

```json
{
  "idea_id": "idea_agent_state_versioned_harness",
  "idea_type": "solution_concept",
  "title": "自然中文标题",
  "problem": "希望解决的具体问题",
  "hypothesis": "可以被证据支持或否定的判断",
  "mechanism": "计划采用或迁移的机制",
  "expected_effect": "预期改变什么",
  "topic_ids": ["agent_acceleration"],
  "status": "seed",
  "evidence_for": [],
  "evidence_against": [],
  "unknowns": [],
  "validation_plan": {
    "mode": "benchmark",
    "minimal_model": "需要搭建的最小验证对象",
    "inputs": [],
    "baselines": [],
    "metrics": [],
    "support_criteria": [],
    "reject_criteria": [],
    "limitations": []
  },
  "first_seen_issue": "2026-08-17",
  "last_updated_issue": "2026-08-17",
  "decision_log": []
}
```

Idea 更新要区分新增证据、措辞调整、状态变化、合并建议和淘汰决定。页面上的“积累多期”只能表示同一个稳定 Idea 在多期得到证据，不能表示同一个项目问题在不同日报出现过几次。

## 七、Agent 语义关键词补充

现有配置已经在部分 arXiv 查询、边界探索和 Radar 分类中使用 `agentic`。`harness` 尚未进入 Agent 语义专题的正式关键词，`agentic` 也没有覆盖普通查询、boost terms 和 include terms。

需要补充以下词组。

- `harness`
- `agent harness`
- `coding harness`
- `agentic coding`
- `agentic workflow`
- `agentic system`

这些词需要进入 Agent 语义专题的发现查询、AI HOT boost、Direction 匹配和 Radar 分类。Relevance 仍需执行现有边界。泛泛使用 `agentic` 描述业务应用不能因此进入 Agent 语义加速。

建议在 Agent 语义下增加或明确一条 Harness 方向，用来覆盖长任务运行环境、Agent 状态外置、评测 Harness、Harness 自改进和接受门控制。该方向的价值判断应继续关注端到端成功率、任务时延、工具调用成本、状态一致性和 Harness 更新成本。

## 八、GitHub Pages 信息架构

### 8.1 页面不再使用超长单页

GitHub Pages 改成分栏工作台。桌面端采用固定导航、主工作区和详情区，移动端按顺序折叠。

```text
┌──────────────┬──────────────────────────────┬──────────────────────┐
│ 左栏导航     │ 中栏主工作区                 │ 右栏详情             │
│              │                              │                      │
│ 首页         │ Roadmap、Idea 或日报列表     │ 证据、变化、验证建议 │
│ Roadmap      │                              │                      │
│ Idea Bank    │                              │                      │
│ 日报归档     │                              │                      │
│ 证据图谱     │                              │                      │
└──────────────┴──────────────────────────────┴──────────────────────┘
```

### 8.2 首页

首页只展示最新一期、最近发生变化的 Roadmap、正在增强或被淘汰的 Idea，以及简短的来源分布。平均评分不再作为核心 KPI。

### 8.3 Roadmap 页面

左栏选择 Topic 和技术分支。中栏展示阶段、分支和转折。右栏展示选中阶段的来源、进入日报的时间、支持或反对证据和当前开放问题。

### 8.4 Idea Bank 页面

左栏按 Topic、Idea 类型和状态筛选。中栏展示 Idea 列表。右栏展开问题、假设、机制、证据、未知量、验证建议和决策记录。

### 8.5 日报与证据页面

日报默认打开当前 `email.html` 或 `email-illustrated.html`，并提供原始已发送版本入口。知识图谱负责跨专题和关键词浏览，不能代替 Roadmap，也不能根据标题自动制造语义边。

## 九、反馈 Mock

第一阶段不部署 Serverless 和数据库。反馈仅保存在当前浏览器 `localStorage`，页面明确标注“演示模式，仅保存在当前浏览器”。

支持以下行为。

- 日报条目的感兴趣、不感兴趣、取消和切换。
- Idea 的值得继续、暂不值得、取消和切换。
- 刷新后保留。
- 导出反馈 JSON。
- 清空演示反馈。
- 换浏览器、换设备或清理浏览器数据后允许丢失。

不展示伪造的多人统计，不让 Mock 反馈真实改变日报选择、Roadmap 或 Idea 状态。可以提供“反馈影响预览”，页面必须标明预览性质。

前端采用统一存储接口。

```text
FeedbackStore
├── LocalFeedbackStore
└── RemoteFeedbackStore
```

当前使用 `LocalFeedbackStore`。以后接入真实 API 时保留相同事件结构和 UI，只替换存储适配器。

```json
{
  "event_id": "feedback_xxx",
  "actor_id": "local_demo",
  "target_type": "brief_item",
  "target_id": "239936d77241bed615ba7777",
  "reaction": "interested",
  "action": "set",
  "created_at": "2026-08-20T10:30:00+08:00",
  "schema_version": 1
}
```

## 十、实施顺序

建议拆成五组可以独立验证的改动。

### PR 1 统一归档和 Reader Contract

- 修复归档脚本对 `email.html` 与 `email-illustrated.html` 的命名处理。
- 增加 `original/`、`reader.json` 和 `publication-manifest.json` 契约。
- 保证新旧归档走同一条公开阅读版生成路径。
- 补充 Agent Harness 与 Agentic 关键词。
- 更新 `SKILL.md` 中已经过时的 Reader Projection 和选择性 Fact Check 描述。

### PR 2 迁移现有 6 期归档

- 一次只处理一期，避免不同日报之间移动事实。
- 生成新版 headline、judgements、core、supplement、Radar 和 watch next。
- 保存原始已发送 HTML。
- 生成当前 `email.html`、`email-illustrated.html` 和 `reader.json`。
- 更新 archive index 使用当前 reader headline。

### PR 3 建立 Roadmap 与 Idea Bank 物化层

- 新增 Roadmap、Idea、版本记录和 Schema。
- 只读取已发布 archive Machine 数据。
- 实现 Topic 级增量触发和全历史重算。
- 实现 `no_material_change`。
- 实现边界探索临时聚类。
- 生成验证建议，不执行仿真。

### PR 4 重构 GitHub Pages

- 改为分栏工作台和独立视图。
- 首页聚焦最新变化。
- Roadmap 和 Idea Bank 成为一等页面。
- 图谱降为证据浏览。
- Pages 展示 reader 文案，分析仍使用 Machine 数据。
- 修复 Radar 重复加载和误统计。

### PR 5 增加反馈 Mock

- 实现 `FeedbackStore` 接口。
- 使用 `localStorage` 保存事件。
- 增加导出、清空和演示模式提示。
- 为未来 Remote Adapter 保留稳定契约。

## 十一、验收条件

### 11.1 归档迁移

- 现有 6 期原始 HTML 均被保存且可打开。
- 根目录稳定 URL 继续使用 `email.html` 和 `email-illustrated.html`。
- 新旧归档使用同一 Reader Contract。
- 迁移前后条目 ID、数量、角色、日期、分数、来源和 URL 完全一致。
- Reader 文案没有增加 Machine Item 中不存在的数字。
- 重复迁移保持幂等。

### 11.2 Roadmap

- Roadmap 只使用已发布证据。
- 每个阶段、分支和转折都有日报与原始来源。
- 没有足够证据时显示证据时间线，不强造阶段。
- 新日报只触发涉及 Topic。
- 无实质变化时留下 no-op 记录。
- 历史版本可以回看。

### 11.3 Idea Bank

- Research Hypothesis 与 Solution Concept 能清楚区分。
- 验证动作不能单独成为 Idea。
- 不同机制不会因为同属一个 project question 而被合并。
- 每个 Idea 有稳定身份、证据、未知量、验证建议和决策记录。
- 自动淘汰有完整记录，后续可以重新打开。
- 页面不会把验证建议写成已经完成的结果。

### 11.4 GitHub Pages

- 桌面端不依赖超长滚动完成主要操作。
- Roadmap、Idea Bank、日报和证据图谱可独立进入。
- 中栏与右栏选择联动。
- 默认展示新版 reader 文案。
- 原始已发送版本仍可访问。
- Radar 不重复计数。

### 11.5 反馈 Mock

- 当前浏览器刷新后状态保留。
- 重复点击不会无限增加计数。
- 支持取消和切换。
- 可以导出完整事件 JSON。
- 页面清楚说明数据只保存在当前浏览器。
- Mock 反馈不会偷偷修改真实 Roadmap、Idea 或日报选择。

## 十二、暂不实施的内容

- 内部项目路线叠加。
- 真实仿真执行和自动生成实验结果。
- 真实多人反馈后端。
- 对旧日期重新选择被筛掉的博客或工业信息。
- 根据标题推断论文之间的 `EXTENDS`、`USES` 等关系。
- 把润色后的 reader 文案当作 Roadmap 或 Idea 的事实源。

这些能力以后可以增量加入。当前阶段先把归档阅读、外部 Roadmap、Idea 数据模型、验证建议、分栏 Pages 和本地反馈 Mock 做成一套完整且可审计的流程。
