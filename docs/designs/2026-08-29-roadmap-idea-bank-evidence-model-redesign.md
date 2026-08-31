# Roadmap、Idea Bank 与证据图谱：现状诊断与优化方案

- Status: draft
- Created: 2026-08-29
- Last updated: 2026-08-30

- 文档日期：2026-08-29
- 适用仓库：`technical-briefing-skill`
- 分析范围：当前代码、Schema、Prompt、物化数据、Pages 实现与相关测试
- 文档性质：设计诊断与下一版方案，不直接修改现有生产数据

> 2026-09-01 更新：全局图谱与 Idea 证据视图的后续产品定位、一级导航和渲染技术，见 [日报知识图谱与 Idea Hub 证据视图设计](./2026-09-01-daily-briefing-knowledge-graph-design.md)。若两份文档在这些范围内冲突，以后者为准。

## 一、结论先行

当前设计的主要问题不是页面不够精致，而是三套能力仍停留在“文章管理”层，没有形成统一的“证据—判断—决策”模型：

- Roadmap 实际上是按 Topic / Direction 分组的已发布条目时间线；
- Idea Bank 实际上是少量预先挑选、人工写入种子脚本的 Idea 对象；
- 证据图谱实际是 `日报 → Topic → 条目` 或 `关键词 → Topic → 条目` 的归档浏览图；
- Roadmap 和 Idea 各自内嵌一份证据引用，图谱却不读取这两类长期知识对象，三者没有共享的 Claim 层；
- 知识物化没有进入正常发布闭环，当前长期知识已经落后于归档三期，但 `knowledge validate` 仍然返回通过。

因此，用户感受到的“粗糙”不是单一 UI 问题，而是产品对象、知识语义和运行闭环三层同时不完整。

下一版建议围绕一个核心重构：

```text
原始来源 / 已发布 Machine Item
              ↓
       Evidence Registry
              ↓
          Claim Ledger
        ↙       ↓       ↘
  Roadmap    Idea Bank   Evidence Graph
        ↘       ↓       ↙
       Experiment / Decision Log
```

其中：

- Evidence Registry 保存不可变来源、已发布身份和证据定位；
- Claim Ledger 保存原子化、带适用条件的技术断言；
- Roadmap 是 Claim 在“技术方向与演进事件”上的投影；
- Idea Bank 是 Claim 在“问题、假设、方案与验证决策”上的投影；
- 证据图谱是上述对象和关系的只读投影，不再由浏览器临时猜边。

优先级上，建议先修复知识层落后、静默漏更新、跨对象并发覆盖和非原子 apply，再建设 Claim 层。否则即使 Roadmap 和图谱做得更漂亮，也只是在展示一份可能过期、不完整且无法稳定复现的知识快照。

## 二、检查到的当前事实

以下结论均来自本仓库当前状态，不是对未来设计的推测。

### 2.1 数据新鲜度已经失真

- `archive/index.json` 当前有 9 期归档，最新一期为 `2026-08-29`；
- `knowledge/` 仍是根据截至 `2026-08-17` 的前 6 期归档生成的首版数据；
- `2026-08-23`、`2026-08-26`、`2026-08-29` 三期均包含多个已有 Roadmap Topic，但尚未进入长期知识层；
- `knowledge/applications/` 中当前没有 application 记录；
- `python3 briefing.py knowledge status` 返回空数组，表示没有准备中的知识任务；
- `python3 briefing.py knowledge validate` 却返回 `valid: true`。

这说明当前 `validate` 只能验证“现有引用是否合法”，不能验证“知识是否已经覆盖到最新归档”。对产品来说，这是比字段缺失更危险的问题：页面可以在完全不报错的情况下展示过期判断。

对应实现位置：

- 手工执行增量更新的说明：`docs/contracts/knowledge-materialization.md:22-47`；
- Topic 任务准备：`briefing_skill/knowledge_materialization.py:600-738`；
- 当前知识校验：`briefing_skill/knowledge_materialization.py:1065-1122`；
- 正常发送、归档、发布流程中没有自动触发 `knowledge prepare/apply`。

### 2.2 Roadmap 仍然全部是证据列表

当前共有 8 个 Roadmap：

- 全部为 `version = 1`；
- 全部为 `view_mode = evidence_timeline`；
- 总阶段数为 0；
- 总开放问题数为 0；
- 每个 branch 的状态基本都是 `emerging`；
- 首版 branch 直接来自现有 `direction_id` 分组。

这套数据是诚实的——它没有在证据不足时编造阶段——但它目前只能回答“我们在哪一期收录过什么”，不能回答真正的 Roadmap 问题：

- 这个技术方向在解决什么稳定问题？
- 主流技术路线有哪些，它们在竞争什么？
- 哪些能力或部署边界发生了变化？
- 哪些证据代表转折，哪些只是又一篇相似工作？
- 学术原型、工程集成、产品采用和标准化分别走到哪里？
- 下一次什么信号出现时，应改变当前判断？

首版生成逻辑明确地只按 Direction 分组，并为每篇条目写入“当前仅记录其出现”的通用 reason，见 `scripts/seed_knowledge.py:36-118`。因此当前 Roadmap 更准确的产品名称应是“专题证据时间线”，还不是“外部技术 Roadmap”。

### 2.3 Idea Bank 目前主要是人工种子，不是持续运行的漏斗

当前共有 6 个 Idea：

- 4 个 `observing`，2 个 `seed`；
- 没有 `ready_for_validation`、`promising`、`rejected` 或 `proposal_candidate`；
- 没有任何 `evidence_against`；
- 最新更新时间仍停在 `2026-08-17`；
- 6 个对象均由 `scripts/seed_knowledge.py` 中的固定内容生成，而不是由已运行的增量 application 产生。

从现有 6 个种子对象的证据组成看，当前数据已经隐含了不同的 Idea 产生方式：2 个只引用单条、单期证据，1 个联合了同一期的两条证据，3 个联合了 2～3 个期次的证据。但这只是种子脚本人工写出的结果，不代表运行链路已经实现“单条发现”和“跨期综合”两条生成通道。

Idea 本身的文本质量并不差，问题在于它还没有形成持续决策闭环：

- 没有 Owner、下一次复查日期、资源预算和业务约束；
- 没有已执行 Experiment / Result 对象；
- 没有状态门槛，理论上可以跨级跳转；
- 没有假设级证据，只能把整篇日报条目整体标成支持或反对；
- 没有 Idea 之间的依赖、替代、拆分、合并和继承关系；
- 没有“为什么现在值得占用验证资源”的组合判断；
- 没有真正把 Idea 送到立项候选的运营节奏。

### 2.4 “证据图谱”目前是结构化归档浏览器

当前图谱的实际节点和边如下：

```text
按专题：日报 ──包含数量──> Topic ──包含──> Brief Item

按关键词：关键词 ──匹配──> Topic ──包含──> Brief Item
```

对应实现：

- 页面临时从所有归档装配 Item：`site/app.js:25-124`；
- 页面根据标题、摘要和少量硬编码技术词推导关键词：`site/app.js:20-31`；
- Topic / Keyword 模型：`site/atlas-interaction-v3.js:92-120`；
- 布局和结构边：`site/atlas-layout-v2.js:48-132`；
- 图中节点只有 issue、topic、keyword、item 和 UI aggregate：`site/atlas-layout-v2.js:135-201`。

当前图中没有：

- Source Document 节点；
- Claim 节点；
- 支持、反驳、收窄、限定等证据关系；
- Roadmap branch / milestone 节点；
- Idea / Assumption / Experiment / Decision 节点；
- “这条 Roadmap 判断为什么变化”的可追溯路径；
- “这个 Idea 为什么仍然值得继续”的支持与反对路径。

所以它是一个好用的 Archive Atlas 雏形，但不是严格意义上的 Evidence Graph。当前页面文案已经谨慎地说明“不推断 EXTENDS / USES”，这个边界应该保留；下一步不应简单增加更多由标题或关键词推断的边，而应先建设有来源的显式关系。

### 2.5 当前模型中已经有一些值得保留的正确基础

下一版不应全部推倒重来。以下设计是正确的：

- 长期知识只读取已发布 archive，不读取候选池和 Reader 文案；
- Roadmap 证据不足时允许退化为 evidence timeline；
- Radar 被明确标为 `discovery_signal / unverified`，不能直接支持 Roadmap stage 或 Idea；
- 单 Topic 有界任务避免一次把全部来源装进 Agent 上下文；
- output 与 task binding、旧 Roadmap digest 绑定；
- Idea 使用明确的问题、机制和目标，不再用 `project_question` 或 `next_action` 冒充身份；
- Roadmap 有版本历史，Idea 有追加式 decision log；
- `apply` 已经有幂等 application 的设计意图；
- Pages 中 Reader 文案与 Machine 分析数据保持分离。

这些约束应成为 v2 的底线，而不是重构时被削弱。

## 三、为什么当前设计会显得粗糙

### 3.1 最小知识单元选错了：把“文章”当成“证据”

当前 Evidence Ref 只有：

```json
{
  "item_id": "...",
  "issue_date": "...",
  "source_urls": ["..."],
  "reason": "..."
}
```

它能证明某个已发布条目被引用过，但不能回答：

- 到底引用了这篇来源中的哪一个 claim？
- claim 是机制事实、性能数字、限制、部署信息，还是系统自己的归纳？
- 这个 claim 的 workload、硬件、baseline 和测量条件是什么？
- 一篇来源同时支持 Idea 的某个假设、却反对另一个假设时如何表达？
- 两篇文章是否来自独立团队，能否算独立证据？
- 来源后来修订或撤回时，哪些 Roadmap / Idea 判断会受影响？

仓库上游其实已经有更细的事实结构。`schemas/facts.schema.json` 中的 `evidence[]` 已包含 `claim`、`value`、`baseline`、`condition` 和 `source_locator`。但 archive 物化时只保留 Machine Item 的五段文本和 URL，`PublishedArchive.evidence()` 没有把这些 claim 与 locator 带入长期知识层，见 `briefing_skill/knowledge_materialization.py:138-177`。

这导致事实抽取阶段已经支付过的高质量结构，在 Roadmap 和 Idea 阶段丢失了。

### 3.2 Roadmap 的时间轴使用“进入日报时间”，不是“外部技术发生时间”

当前 Evidence Ref 和 stage 主要保存 `issue_date / first_seen_issue`。虽然 archive loader 读取了 `published_at`，但 Roadmap Schema 的引用没有保留它。

真正的外部技术演进至少需要三种时间：

- `source_published_at`：论文、Release 或官方公告何时发生；
- `first_observed_issue`：系统何时第一次把它发布给团队；
- `judgement_valid_from`：系统从哪一期开始持有某个综合判断。

如果只使用 issue date，Roadmap 表达的是“团队观察史”，不是“外部技术史”。这两个时间都重要，但不能混为一个字段。

### 3.3 Roadmap 状态枚举混合了不同维度

当前 `supported / emerging / contested / inferred` 同时混入了：

- 证据置信度：supported / inferred；
- 技术成熟度或趋势：emerging；
- 证据一致性：contested。

一个方向完全可能同时满足：

- 技术仍处于 research prototype；
- 外部动量快速上升；
- 核心机制的证据置信度高；
- 性能收益的跨来源结论仍然 contested。

用一个 `status` 无法表达这种状态，最终只能得到大量笼统的 `emerging`。

### 3.4 “阶段”不是稀疏情报下最自然的 Roadmap 单元

当前模型在 stage 和 evidence timeline 之间二选一。对只有数周历史的技术情报系统，这个选择太硬：

- 强行 stage 会制造伪历史；
- 不强行 stage 就只剩文章列表。

更合适的中间层是：

- 当前技术 Landscape；
- 稳定 Track / Approach；
- 有明确前后差异的 Milestone / Inflection；
- Open Question 与 Watch Trigger；
- 当证据足够时再把多个 milestone 归纳成 phase。

也就是说，`stage` 应是较高阶的可选归纳，而不是 Roadmap 唯一的价值载体。

### 3.5 Idea 的“对象身份”和“状态机”都过于刚性

当前 `idea_id` 由三个由 Agent 编写的 lower_snake_case key 哈希得到。这避免了直接用 project question 合并，但也有新问题：

- 同义 key 改写会产生一个新 ID；
- Idea 的问题边界正常收窄时，无法判断是同一 Idea 更新还是另建对象；
- ID 的“稳定”依赖 Agent 对英文 key 的措辞稳定，而不是对象首次创建后永久分配；
- `idea_type` 被设为不可变，research hypothesis 不能自然长成 solution concept；
- 没有显式的 split / merge / supersede 关系来处理演化。

更合理的方式是：对象创建时铸造不可变 ID，另存可版本化的 `identity_signature` 用于相似度和去重建议。语义变化通过 decision event 记录，不让内容哈希承担对象身份。

### 3.6 Idea 状态没有可验证的进入条件

当前状态列表看起来像流程，但 Schema 和校验器没有定义完整合法迁移与门槛。例如：

- `seed` 是否可以直接变成 `proposal_candidate`？
- `ready_for_validation` 至少需要哪些字段完整？
- `promising` 是外部证据看起来不错，还是内部实验已经通过？
- `rejected` 是核心假设被外部证据否定，还是因为内部资源、成本或战略不匹配？
- 多久没有新增证据或复查后应进入 parked？

当前 `validation_plan.execution_status` 永远是 `suggestion_only`，所以 Idea 永远不会真正进入验证执行和结果回流。

### 3.7 Roadmap 完整输出允许静默丢内容

Prompt 要求 Agent 返回完整 Roadmap，但验证器只检查“返回的引用是否合法”，没有检查：

- 本 Topic 的所有旧 branch 是否仍在；
- branch 被删除、合并或改名是否有显式 change event；
- 所有本期新增证据是否已被吸收，或有明确 `not_material / unclassified` 原因；
- 旧证据是否被无意遗漏；
- 已有 open question 是否被静默删除。

因此，一个少返回 branch 的合法 JSON 可能通过校验、触发 `material_change` 并覆盖当前 Roadmap。对于完整重物化流程，这是高优先级正确性风险。

### 3.8 多 Topic Idea 存在覆盖风险

一个 Idea 可以属于多个 `topic_ids`，而知识任务按 Topic 切分。每个 Topic 任务都可能携带并更新同一个 Idea，但 task binding 只绑定旧 Roadmap digest，没有绑定每个旧 Idea 的 digest。

如果两个 Topic 任务先后基于同一个旧 Idea 生成更新，后 apply 的任务可能覆盖前一个任务的 Idea 修改。当前 apply 也没有对 Idea 做对象级乐观锁或版本比较。

建议把 Idea 更新从 Topic Roadmap 任务中拆出来，使用独立 Idea task；或者至少为每个输出 Idea 绑定 `previous_idea_version / previous_idea_digest` 并执行 compare-and-swap。

### 3.9 apply 不是跨文件原子提交

当前 apply 的写入顺序大致是：

```text
写 Roadmap
→ 写 Idea
→ 写 Frontier
→ 重建 index
→ 最后写 application
```

每个 JSON 文件可以单独安全写入，但整个知识快照不是一个事务。如果中途失败，重试时 application 尚不存在，旧 Roadmap digest 却已经变化，任务会被判 stale，形成“部分成功但不能幂等恢复”的状态。

更稳妥的方式是先在 staging 目录生成完整 snapshot，做全量校验后再一次性切换 manifest 指针；或者使用 SQLite 事务保存权威对象，再确定性导出 Pages JSON。

### 3.10 Frontier Cluster 实际仍是 Radar 大类桶

首版 cluster 直接按 `AI Infra / Agent生态 / KVCache生态 / 存储与介质 / 其他技术前沿` 分组。它反映的是栏目分类，不是语义上的临时技术簇。

例如“KVCache生态”下的多个 release、网络论文和缓存机制不应天然属于一个可晋升 cluster。一个真正的 Frontier Cluster 至少应共享：

- 具体问题；
- 稳定机制或能力变化；
- 可解释的相似依据；
- 跨期持续性；
- 与目标 Roadmap branch 的明确关系。

### 3.11 质量校验只看 URI 格式，不看来源可用性

当前公开 archive 与 `knowledge/frontier-clusters.json` 中仍存在 `https://example.com/kv-network-paper`。它满足 JSON Schema 的 URI 格式，所以知识校验不会报错。

这说明 Evidence Registry 还需要来源级质量门：

- 禁止 `example.com`、localhost、相对路径和已知 fixture 域；
- 校验 canonical URL 与公开可访问性状态；
- 保留 source level、publisher、版本身份、抓取/验证时间；
- 对失效链接显示状态，不静默继续当成有效证据。

## 四、建议的统一知识模型

### 4.1 Source Document：外部来源对象

来源对象只描述“谁在什么时候发布了什么”，不直接代表系统采信其结论。

建议字段：

```json
{
  "source_id": "src_arxiv_2608_10450_v2",
  "canonical_identity": "arxiv:2608.10450:v2",
  "source_type": "paper",
  "publisher": "arXiv",
  "url": "https://arxiv.org/abs/2608.10450v2",
  "source_level": "A",
  "source_published_at": "2026-08-17",
  "content_fingerprint": "...",
  "verification_status": "resolved",
  "last_verified_at": "..."
}
```

同一论文新版本、同一项目新 release、同一 URL 内容变化应有明确版本关系，不要只靠 URL 字符串。

### 4.2 Published Evidence Record：团队已看到的不可变发布记录

这一层保持当前 `published_archive_only` 的产品原则，区分外部来源和内部发布身份。

```json
{
  "evidence_record_id": "ev_...",
  "brief_item_id": "...",
  "issue_date": "2026-08-29",
  "role": "core",
  "topic_id": "agent_acceleration",
  "direction_id": "tool_chain",
  "source_ids": ["src_..."],
  "machine_item_hash": "...",
  "fact_check_status": "passed",
  "evidence_gate_version": "..."
}
```

它回答的是“团队在哪一期正式看到并采纳了这条材料”，不是“外部技术何时发生”。

### 4.3 Claim：真正的原子知识单元

Claim 应从已经通过 Evidence Gate / Fact Check 的结构化 facts 派生，而不是再次从 Reader 文案中抽取。

```json
{
  "claim_id": "claim_...",
  "claim_type": "performance_result",
  "statement": "在给定硬件和工作负载下，方案 X 将 P95 TTFT 降低到……",
  "subject": "system_x",
  "predicate": "improves_p95_ttft",
  "object": "baseline_y",
  "qualifiers": {
    "hardware": "...",
    "workload": "...",
    "metric": "P95 TTFT",
    "condition": "..."
  },
  "source_id": "src_...",
  "source_locator": "Section 4.2 / Table 3",
  "evidence_record_id": "ev_...",
  "verification": "fact_checked",
  "valid_time": {"from": "2026-08-17", "to": null}
}
```

建议的 `claim_type` 至少包括：

- `problem_observation`
- `mechanism`
- `performance_result`
- `deployment_fact`
- `limitation`
- `negative_result`
- `compatibility_change`
- `standard_or_interface_change`
- `system_inference`

`system_inference` 必须与来源事实分开，并引用它所综合的 Claim。

### 4.4 Evidence Link：证据与判断之间的显式关系

Roadmap 和 Idea 不再复制 URL 和 reason，而是引用 Claim，并在 Link 上保存关系语义：

```json
{
  "link_id": "link_...",
  "claim_id": "claim_...",
  "target_type": "idea_assumption",
  "target_id": "assumption_...",
  "relation": "supports",
  "directness": "direct",
  "independence_group": "research_team_x",
  "applicability": "partial",
  "rationale": "该实验直接验证了带宽约束下的机制，但未覆盖跨云 RTT。"
}
```

关系建议限定为：

- `supports`
- `challenges`
- `narrows`
- `contradicts`
- `supersedes`
- `contextualizes`
- `does_not_apply`

不要让 free-text reason 独自承担全部语义。

### 4.5 置信度不要压成一个神秘分数

建议保留可解释向量，再确定性映射为 low / medium / high：

- 来源等级与是否为原始来源；
- Claim 是否有精确 locator；
- 证据是直接还是间接；
- 是否有独立团队重复；
- 条件是否覆盖当前项目场景；
- 是否存在反对或收窄证据；
- 来源版本是否仍有效。

单一总分可以用于排序，但页面必须能展开看到构成，不能把模型主观评分伪装成客观概率。

## 五、Roadmap v2 设计

### 5.1 重新定义 Roadmap 的产品问题

Roadmap 不应回答“最近有哪些文章”，而应回答：

1. 这个方向在解决哪些稳定问题？
2. 当前有哪些互相竞争或互补的 Approach？
3. 外部能力、成熟度和采用状态发生了什么变化？
4. 当前判断依赖哪些 Claim，哪些地方仍有冲突？
5. 哪些新信号会让我们改变判断？
6. 这些变化产生了哪些可验证 Idea？

### 5.2 三种展示模式，而不是 stage / timeline 二选一

建议支持三个有明确门槛的 mode：

- `signal_timeline`：材料稀疏，只展示已观察事件；
- `technology_landscape`：已经能区分问题、Approach、成熟度和主要边界，但不足以断言阶段迁移；
- `capability_trajectory`：存在多个有序 milestone，且能说明能力或部署边界如何变化。

只有在多项跨期证据支持时，才在 trajectory 上进一步归纳 phase。

### 5.3 Track 和 Milestone 应成为核心对象

建议 Roadmap 结构：

```text
Topic
├── Problem Space
├── Track / Approach A
│   ├── Current State
│   ├── Milestone 1
│   ├── Milestone 2
│   ├── Bottlenecks
│   ├── Open Questions
│   └── Watch Triggers
├── Track / Approach B
└── Cross-track Comparison
```

Milestone 必须说明“什么能力或边界改变了”，不能只是“又出现一篇论文”。

建议字段分离：

```json
{
  "maturity": "research_prototype",
  "momentum": "rising",
  "evidence_confidence": "medium",
  "consensus": "mixed"
}
```

可选枚举：

- maturity：`concept / research_prototype / engineering_validation / production_adoption / standardizing`
- momentum：`rising / stable / declining / uncertain`
- consensus：`aligned / mixed / contested / insufficient`
- evidence confidence：由 Evidence Link 规则确定

### 5.4 Roadmap 必须有结构化 diff

每次更新不只写一句通用的“本期改变了判断”，而应输出：

- `branch_created`
- `branch_renamed`
- `branch_split`
- `branch_merged`
- `milestone_added`
- `maturity_changed`
- `momentum_changed`
- `question_opened`
- `question_resolved`
- `claim_supported`
- `claim_challenged`
- `evidence_only_no_judgement_change`

每个 change event 都要包含 before / after、触发 Claim、系统推理和生成版本。删除 branch、milestone、open question 或证据关联必须是显式事件，不能靠完整 JSON 覆盖来暗中发生。

### 5.5 当前只有数周历史时，不要急着声称“外部技术史”

如果继续坚持 Roadmap 只使用已发布日报，系统在启动早期必然缺少历史基线。可以有两种诚实方案：

1. 在证据积累足够前把页面称为“技术演进观察 / Technology Trajectory”；
2. 单独建立经过审核、可公开追溯的 `baseline dossier`，作为一次特殊发布事件加入证据账本。

不建议偷偷回填未发布来源，更不建议根据常识补写技术史。

## 六、Idea Bank v2 设计

### 6.1 把 Idea 从“卡片”升级为“决策对象”

Idea 至少应包含五组内容：

- Frame：问题、目标对象、预期效果；
- Assumptions：可以逐条被证伪的关键假设；
- Evidence：每个假设的支持、反对、限定和不适用 Claim；
- Validation：一个或多个版本化 Experiment；
- Decision：状态变化、责任人、资源和复查时间。

Solution Concept 不必强塞一个总 `hypothesis` 字段，而应包含一组 testable assumptions。Research Hypothesis 如果逐步形成方案，可以：

- 创建一个关联的 solution concept，并用 `DERIVED_FROM` 连接；或
- 通过显式 `type_changed` decision 升级，而不是因为 Schema 不可变被迫制造一个无关联的新 Idea。

### 6.2 把“Idea 内容类型”“产生方式”和“证据成熟度”分开

`research_hypothesis / solution_concept` 描述 Idea 是什么，不应同时承担“它怎样产生”的语义。Idea 的产生方式需要在创建时形成不可变的 Origin Event；后续新增证据只改变 Assumption、证据成熟度和决策状态，不回写它的出生方式。

外部情报驱动的 Idea 以两条主通道为核心，但自动来源应细分为三类：

- `single_evidence`：一条已发布 Evidence Record 中的强 Claim 直接触发 Idea Seed；
- `cross_source_synthesis`：同一期内多个独立来源或 Claim 联合暴露共同瓶颈、组合机会或冲突；
- `cross_issue_synthesis`：至少两个不同 issue 的 Claim 形成新的跨期判断。

此外保留三类补充来源：

- `roadmap_gap`：由 Roadmap Open Question 或 Watch Trigger 产生；
- `human_proposal`：内部人员提出问题、假设或方案；
- `experiment_branch`：Experiment Result 产生新的研究分支或 Solution Concept。

Origin 不能由当前 `evidence_for` 的数量动态推断。一个 `single_evidence` Seed 在后续几期可能积累多项证据，但它最初仍由单条信息触发。建议的数据结构如下：

```json
{
  "origin": {
    "origin_event_id": "idea_origin_...",
    "kind": "cross_issue_synthesis",
    "trigger_issue": "2026-08-29",
    "claim_ids": ["claim_a", "claim_b"],
    "evidence_record_ids": ["ev_a", "ev_b"],
    "issue_dates": ["2026-08-17", "2026-08-29"],
    "independence_groups": ["team_a", "team_b"],
    "rationale": "两期证据共同表明同一瓶颈已从局部优化问题变成可调度边界。",
    "snapshot_id": "knowledge_2026-08-29_...",
    "generator": {"type": "agent", "policy_version": "idea-origin-v1"}
  }
}
```

证据成熟度另行计算并展示，例如 issue 数、独立来源数、直接/间接证据、支持/反对/限定关系和适用性。`cross_issue_synthesis` 不自动代表高置信，重复出现也可能来自同一团队、同一数据或同一未经验证的假设。

### 6.3 建立“单条候选发现 + 跨期综合发现”两段生成机制

每次新归档完成后，Idea 发现分为两个有界步骤：

```text
每个新增 Claim
→ Direct Candidate Extraction
→ 发现 single_evidence 候选

本期新增 Claim + Topic 历史 Claim + Roadmap Open Question
→ Topic Synthesis
→ 发现 cross_source_synthesis / cross_issue_synthesis / roadmap_gap 候选

全部候选
→ Identity / Similarity / Lineage Resolution
→ create / update / split / merge_suggested / no-op
```

Direct Candidate 只有在单条证据同时给出明确问题、机制、目标对象和可验证效果时才能建立 Seed；“建议补测一个指标”仍然只是 Validation Plan。

Synthesis Candidate 必须保存参与综合的 Claim 集合和 synthesis rationale。`cross_issue_synthesis` 至少包含两个不同 `issue_date`，且一次增量任务至少有一个触发 Claim 来自当前 issue；否则只是在旧证据上重复生成候选。多篇材料仅仅属于同一 Topic，不构成综合关系。

候选不应直接写入权威 Idea 文件。系统先与已有 Idea 比较身份和 lineage，再提出：

- 创建新 Idea；
- 为已有 Idea 增加证据或收窄 Frame；
- 将 Research Hypothesis 派生为关联的 Solution Concept；
- split / merge 建议；
- 因没有新增语义而 no-op。

单条来源通常从 `seed` 开始并显示“尚未独立验证”；跨来源或跨期综合也不能仅凭数量跨越状态门槛。Idea 状态继续由 Frame 完整度、Assumption 证据和 Experiment Result 决定。

### 6.4 建议的状态机

```text
seed
  ↓
framed
  ↓
evidence_building
  ↓
ready_to_validate
  ↓
validating
  ├── validated_positive → proposal_candidate
  ├── validated_negative → rejected
  └── inconclusive → evidence_building / parked
```

任何状态都可以通过明确 decision 进入 `parked`；新证据可触发 `reopened`。

建议的硬门槛：

- `framed`：问题、目标、机制/假设和边界完整；
- `ready_to_validate`：baseline、metric、支持阈值、否定阈值、最小模型、成本估计完整；
- `validating`：存在已启动 Experiment、Owner 和时间窗口；
- `validated_positive/negative`：存在结果对象与可复现产物；
- `proposal_candidate`：验证通过，且战略相关性、投入与风险评审完成；
- `rejected`：明确记录被否定的 assumption，不能只写“暂无工具”或“暂时没资源”。

### 6.5 把自动淘汰改成自动提出决策

AI 可以自动做：

- 发现反对证据；
- 将 Idea 标记为 `challenged`；
- 生成 `rejection_proposed`；
- 提醒复查。

但对于仍可能影响内部资源分配的 `rejected / proposal_candidate`，建议保留人工确认，或者至少区分：

- `externally_falsified`：核心假设被强证据直接否定；
- `internally_not_viable`：内部实验失败；
- `strategically_deprioritized`：不是技术错误，只是当前不投入。

三者不能都压缩成一个 rejected。

### 6.6 增加组合管理字段

建议增加：

- `owner`
- `review_due_at`
- `strategic_question_ids`
- `expected_value`
- `time_to_signal`
- `estimated_effort`
- `reversibility`
- `dependencies`
- `risks`
- `similar_idea_ids`
- `supersedes / superseded_by`
- `split_from / merged_into`
- `origin.kind / origin_event_id`

不建议用这些字段生成一个看似精确的综合分。更实用的是做二维或三维组合视图，例如：

- 高价值 / 低验证成本；
- 高不确定性 / 快速出信号；
- 证据强 / 战略相关性弱；
- 长期观察 / 当前可行动。

### 6.7 Experiment 必须是独立、版本化对象

当前 `validation_plan` 嵌在 Idea 中，只能表达建议。建议拆成：

```text
Idea
├── Validation Plan v1
│   └── Experiment Run 1 → Result
├── Validation Plan v2
│   └── Experiment Run 2 → Result
└── Decision Log
```

Experiment 需要保存：

- plan version；
- 输入数据和代码版本；
- 环境与参数；
- baseline；
- metric 和预注册阈值；
- 结果与产物路径；
- 结果是否支持哪些 assumption；
- 已知限制；
- 执行者和时间。

这样 Idea 才能真正从“建议验证”进入“已经验证”。

## 七、真正的 Evidence Graph 应该怎样设计

### 7.1 图谱是投影，不是新的权威数据库

权威数据仍应是 Evidence Registry、Claim、Roadmap、Idea、Experiment 和 Decision 对象。Graph 由这些对象确定性导出：

```text
knowledge/graph/
├── manifest.json
├── nodes/<shard>.json
├── edges/<shard>.json
└── ego/<object_id>.json
```

第一阶段不需要 Neo4j，也不需要把全部对象塞进一个超大前端 JSON。GitHub Pages 可以按 Topic 或对象加载 1～2 跳 ego graph。

### 7.2 建议的节点类型

- `SourceDocument`
- `PublishedEvidenceRecord`
- `Claim`
- `Topic`
- `Track`
- `Milestone`
- `OpenQuestion`
- `Idea`
- `Assumption`
- `ValidationPlan`
- `ExperimentRun`
- `DecisionEvent`

### 7.3 建议的显式边类型

- `SOURCE_ASSERTS_CLAIM`
- `ITEM_PUBLISHES_CLAIM`
- `CLAIM_SUPPORTS_MILESTONE`
- `CLAIM_CHALLENGES_MILESTONE`
- `MILESTONE_ADVANCES_TRACK`
- `TRACK_BELONGS_TO_TOPIC`
- `IDEA_ADDRESSES_QUESTION`
- `IDEA_DERIVED_FROM_MILESTONE`
- `CLAIM_TRIGGERS_IDEA`
- `CLAIM_SET_SYNTHESIZES_IDEA`
- `CLAIM_SUPPORTS_ASSUMPTION`
- `CLAIM_CONTRADICTS_ASSUMPTION`
- `EXPERIMENT_TESTS_ASSUMPTION`
- `RESULT_SUPPORTS_ASSUMPTION`
- `RESULT_REJECTS_ASSUMPTION`
- `DECISION_CHANGES_IDEA_STATUS`
- `IDEA_DEPENDS_ON_IDEA`
- `IDEA_SUPERSEDES_IDEA`

关键词只用于搜索和候选关联。由关键词或标题相似度生成的关系必须标为 `proposed_relation`，不能与已确认边混在一起。

### 7.4 页面默认不应展示全局“毛线团”

证据图谱最有价值的不是一次看到所有节点，而是回答具体问题。建议提供三种任务视图：

#### 视图 A：为什么 Roadmap 变了

```text
Source → Claim → Milestone / Track Change → Roadmap Version
```

#### 视图 B：为什么这个 Idea 值得继续或应该停止

```text
支持 Claim ─┐
反对 Claim ─┼→ Assumption → Idea → Decision
实验 Result ┘
```

#### 视图 C：我们缺什么证据

```text
Open Question → 缺失 Claim 类型 → Watch Trigger / Validation Plan
```

每个视图默认限制节点数，支持按时间、来源类型、证据关系、置信度和 Topic 过滤。全局 Atlas 可以保留，但应是次级入口。

## 八、运行闭环与工程治理

### 8.1 给知识快照增加明确水位线

建议新增 `knowledge/manifest.json`：

```json
{
  "schema_version": 2,
  "snapshot_id": "knowledge_2026-08-29_...",
  "archive_head_issue": "2026-08-29",
  "materialized_through_issue": "2026-08-29",
  "archive_index_digest": "...",
  "status": "complete",
  "affected_topics": ["..."],
  "completed_topics": ["..."],
  "deferred_topics": [],
  "generated_at": "..."
}
```

`knowledge validate` 至少应检查：

- `archive_head_issue == materialized_through_issue`，否则 FAIL 或明确 LAGGING；
- 最新一期所有 affected Topic 都有 materialization result 或显式 deferred 记录；
- Pages 顶部展示知识更新时间与落后期数；
- 发布站点不能静默把旧 Roadmap 标成“当前判断”。

### 8.2 把知识更新接入 archive 发布后流程

建议流程：

```text
邮件发送成功
→ archive 写入并校验
→ 生成 affected-topic / claim tasks
→ 逐个完成有界任务
→ 在 staging 中生成完整 knowledge snapshot
→ 全量 validate
→ 原子切换 current manifest
→ Pages 部署
```

知识更新不必阻塞邮件发送，但 Pages 的“当前知识版本”只能在完整 snapshot 成功后切换。失败时保留上一版并明确显示 lagging，而不是部分更新。

### 8.3 增加覆盖账本，阻止静默删除

每个 Topic task 应对全部 in-scope evidence 给出以下之一：

- `assigned_to_track`
- `supports_milestone`
- `challenges_milestone`
- `supports_idea`
- `not_material`
- `duplicate`
- `unclassified`

非采用项也要有 reason。Roadmap branch、milestone、open question 的删除、合并和拆分必须在 change set 中逐项声明。

### 8.4 采用知识快照提交，而不是多文件直接落盘

建议实现方式：

1. 读取旧 snapshot；
2. 在 `workspace/knowledge/builds/<snapshot_id>/` 生成完整新对象；
3. 运行 Schema、语义、覆盖、图完整性和 URL 质量校验；
4. 生成 manifest 与所有对象 hash；
5. 一次性发布 snapshot；
6. 更新 `knowledge/current.json` 指针；
7. 再记录 application。

如果继续以多个 JSON 为权威存储，也应增加事务日志和 recovery marker，保证 crash 后可以继续，而不是进入半应用状态。

### 8.5 分离 Topic Synthesis 与 Idea Update

建议任务顺序：

```text
Claim Materialization（每个 Brief Item）
→ Topic Roadmap Synthesis（每个受影响 Topic）
→ Direct Idea Candidate（每个新增 Claim）
→ Cross-source / Cross-issue Idea Synthesis（每个受影响 Topic）
→ Candidate Identity / Lineage Resolution
→ Idea Update（每个受影响 Idea）
→ Graph Projection（确定性）
→ Snapshot Validation
```

Direct Candidate 与 Synthesis Candidate 都只是提案，不直接写权威对象。Synthesis task 必须绑定本期触发 Claim、历史 Claim 水位和 Roadmap snapshot；Idea task 绑定 `previous_idea_version / digest`，一次只更新一个 Idea。多 Topic 只作为输入关系，不再由多个 Topic task 竞争写同一文件。

### 8.6 需要新增的质量指标

建议持续统计：

- knowledge lag：落后期数与天数；
- affected Topic 完成率；
- 新证据覆盖率与 `unclassified` 比例；
- 有 source locator 的 Claim 比例；
- Claim 的独立来源数；
- 反对/限定证据占比；
- Roadmap no-op 与 material change 比例；
- branch / milestone 非预期 churn；
- Idea 各状态停留时间；
- 各 `origin.kind` 的候选数、采纳率、重复率与人工改写率；
- 单条 Seed 获得独立证据所需期数，以及跨期综合的平均 issue/source 跨度；
- 到期未复查 Idea 数；
- orphan Idea、orphan Claim、dangling edge 数；
- 页面证据路径可解析率；
- fixture / placeholder / 不可公开 URL 数。

## 九、Pages 信息架构优化

当前三栏 Workbench 可以保留，但页面应从“对象列表”转向“决策任务”。

### 9.1 首页

优先展示：

- 知识水位线：最新归档、已物化至哪一期、是否落后；
- 本期真正改变的 Roadmap 判断；
- 新增或被挑战的 Idea；
- 到期需要复查或验证的 Idea；
- 当前最大证据缺口；
- 来源和 Claim 覆盖健康度。

不要把条目数、平均分或节点数当作主要价值指标。

### 9.2 Roadmap 页面

主区建议采用：

- Topic 状态摘要；
- Track 对比矩阵；
- Milestone / Inflection 时间线；
- maturity、momentum、confidence、consensus 四个分离维度；
- Open Questions 与 Watch Triggers；
- 本期 diff。

右侧详情展示 Claim Ledger，而不是只列原文链接。

### 9.3 Idea Bank 页面

默认视图建议是组合看板：

- 产生方式与触发期次；
- 状态；
- 证据强度；
- 验证成本；
- time-to-signal；
- Owner 与 review due；
- 与哪个 Roadmap gap / milestone 关联。

Idea 详情页按 Assumption 展示支持和反对证据，并把“建议验证”与“已执行结果”分开。

### 9.4 Evidence 页面

建议将“证据图谱”改名为“Evidence Explorer”，默认提供：

- Claim 搜索；
- 支持/反对矩阵；
- 来源与 Claim 的定位信息；
- 从 Roadmap / Idea 反向进入的 1～2 跳关系图；
- 原始 Archive Atlas 作为“按日报浏览”子视图。

这样既保留现在 Atlas 的价值，也避免把结构浏览图误称为语义证据图谱。

## 十、分阶段实施建议

### P0：先修 correctness 和新鲜度

目标：让现有 v1 数据至少可靠、完整、不会静默落后。

- 增加 `knowledge/manifest.json` 和 archive watermark；
- `validate` 检查知识是否覆盖最新归档；
- 发布后自动准备所有 affected Topic；
- 所有 Topic 完成后才切换 Pages 当前知识 snapshot；
- 增加 evidence coverage ledger，阻止旧 branch / 新 evidence 静默丢失；
- 给 Idea 增加 version / digest 乐观锁；
- 把 apply 改为 snapshot 原子提交；
- 增加 placeholder / local URL 负向校验；
- 补充真正验证更新完整性、崩溃恢复和多 Topic 并发的测试。

这一阶段完成后，应先把 2026-08-23、08-26、08-29 三期补入长期知识层。

### P1：建立 Evidence Registry 与 Claim Ledger

目标：不再把整篇文章当成最小证据。

- 在发布归档时保存通过事实检查的原子 Claim 和 source locator；
- Source、Published Record、Claim 分层；
- 增加 Evidence Link 关系；
- 对旧 9 期归档做保守迁移；
- 历史缺 locator 的 Claim 标记为 `machine_summary_only`，不补造定位；
- Roadmap 和 Idea 改为引用 claim_id。

### P2：Roadmap v2 与 Idea v2

目标：从内容陈列进入技术判断和验证管理。

- Roadmap 支持 landscape、track、milestone、watch trigger 和结构化 diff；
- 分离 maturity、momentum、confidence、consensus；
- Idea 使用不可变铸造 ID、Assumption、状态门槛和对象演化关系；
- Idea 创建时保存不可变 Origin Event，并分别运行单条候选发现与跨期综合发现；
- Validation Plan 与 Experiment Run 独立版本化；
- AI 自动提出状态变化，高影响状态由人确认。

### P3：重做 Evidence Explorer

目标：让图谱直接服务判断和决策。

- 确定性生成 typed nodes / edges；
- 提供 Roadmap change trace、Idea decision trace 和 evidence gap 三种视图；
- 默认加载对象 ego graph，不绘制全局毛线团；
- 保留现有 Archive Atlas 作为次级浏览入口；
- 增加 relation provenance、时间和置信度筛选。

### P4：评估与长期治理

目标：让系统知道自己的判断质量，而不仅是 Schema 合法。

- 建立 Roadmap change、Idea merge/reject、Claim relation 的小型 golden set；
- 统计人工修改率、误合并率、漏更新率和状态 churn；
- 定期复查过期 Claim、失效来源和长期停滞 Idea；
- 对 Prompt / Schema / policy 版本变化做可重放评估；
- 为人工反馈建立真正的 actor、权限和审计接口。

## 十一、建议的 v2 验收条件

### 11.1 新鲜度与完整性

- `materialized_through_issue` 与 `archive_head_issue` 一致；
- 每期 affected Topic 都有 applied 或显式 deferred 结果；
- 所有 in-scope evidence 都有采用或不采用记录；
- 删除、合并、拆分已有知识对象必须有显式 event；
- 中途失败不会产生部分可见 snapshot；
- 重跑同一任务不会重复 change、Idea evidence 或 graph edge。

### 11.2 证据完整性

- 高置信 Claim 必须有 A 级来源、source locator 和完整适用条件；
- Reader 文案不得成为 Claim 来源；
- Radar 只能作为 discovery signal，除非原始来源重新进入事实流程；
- 支持、反对、限定和不适用关系能独立表达；
- 页面任一 Roadmap / Idea 判断都能走到 Claim、Published Record 和 Source；
- 无 placeholder、local、相对或不可公开的证据 URL。

### 11.3 Roadmap

- 稀疏材料下仍能展示 Landscape 和 Open Questions，不强造阶段；
- Milestone 必须表达能力、成熟度或部署边界变化；
- maturity、momentum、confidence 和 consensus 不混用；
- 每个 material change 都有结构化 before / after 与触发 Claim；
- source published time、first observed issue 和 judgement time 分开。

### 11.4 Idea Bank

- 每个 Idea 有独立稳定 ID 和明确 Assumption；
- 每个 Idea 都能展示不可变的产生方式、触发 Claim、触发期次和 synthesis rationale；
- `single_evidence`、`cross_source_synthesis` 与 `cross_issue_synthesis` 有确定性判定，且不会由当前证据数量反推；
- 跨期综合至少覆盖两个 issue，并在增量生成时包含本期触发 Claim；
- 单条 Seed 明示未独立验证，跨期 Idea 也不因证据数量自动升级状态；
- 状态迁移满足硬门槛；
- `proposal_candidate` 必须有已完成验证或明确人工豁免；
- rejected 能区分外部证伪、内部不可行和战略降级；
- 多 Topic 更新不会覆盖彼此；
- Experiment 结果可回流到 Assumption 和 Decision。

### 11.5 Evidence Explorer

- 图谱只展示显式 typed relation；
- 关键词相似关系与已确认关系视觉和数据上完全分开；
- 能从任一 Roadmap change 或 Idea decision 查看完整证据路径；
- 默认视图不依赖加载全部 archive；
- 所有 node / edge 无悬空引用，且 snapshot hash 可验证。

## 十二、建议立即做的五件事

如果只安排一个短迭代，建议按以下顺序执行：

1. 为 `knowledge` 增加 archive watermark，让过期状态无法再“校验通过”；
2. 把知识更新接到每次 archive 发布后的自动流程，并以完整 snapshot 切换 Pages；
3. 增加 evidence coverage ledger 和显式删除/合并事件，堵住完整重物化静默丢内容的问题；
4. 把上游 facts 中已有的 claim、condition、baseline、source locator 保存在发布归档，建立最小 Claim Ledger；
5. 将当前“证据图谱”明确定位为 Archive Atlas，等 typed Claim relation 可用后再上线真正的 Evidence Explorer。

这五项完成后，系统会从“几份结构化 JSON 加一个漂亮页面”迈进到“能够持续积累、解释判断、管理验证并可靠追溯的技术决策系统”。Roadmap、Idea Bank 和证据图谱也会自然成为同一知识底座的三个工作视图，而不是三套各自生长的功能。

## 十三、Decision log

- 2026-08-29：明确外部情报驱动 Idea 以“单条信息直接触发”和“多条信息联合综合”为两条主通道；联合综合进一步区分同一期跨来源与跨期综合。采用不可变 Origin Event 保存出生方式，并将其与 Idea 内容类型、后续证据成熟度和决策状态分离。
