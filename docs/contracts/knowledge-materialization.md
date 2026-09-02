# Roadmap 与 Idea Bank 物化层

`knowledge/` 是 GitHub Pages 可直接发布的权威知识目录。它只从
`archive/index.json` 已列出的 `issue.json` 与 `papers.json` Machine 记录更新，
不读取候选池、全文、`reader.json` 或网页临时分组。

## 目录契约

```text
knowledge/
├── index.json
├── graph.json                        # 派生发布物，可随时删除重建
├── manifest.json                     # 派生发布投影：新鲜度清单，可重建
├── issue-diffs/<issue_date>.json     # 派生发布投影：单期 Issue Change Projection
├── roadmaps/<topic_id>.json
├── ideas/<idea_id>.json
├── frontier-clusters.json
├── history/roadmaps/<topic_id>/vN.json
└── applications/<task_id>.json       # apply 后生成，可用于幂等审计
```

`index.json` 中的 `path` 均从站点根目录开始，例如
`knowledge/roadmaps/agent_acceleration.json`。`manifest.json` 与
`issue-diffs/` 是可重新生成的发布投影，不是新的权威知识来源；
删除后可用下文命令重建。

## 新日报后的增量更新

先为一期日报中实际出现的 Topic 准备有界任务：

```bash
python3 briefing.py knowledge prepare --issue 2026-08-21
python3 briefing.py knowledge next --issue 2026-08-21
```

每个任务只含一个 Topic 截至该期的全部已发布 Machine 证据、该期新增证据 ID、
旧 Roadmap 和相关旧 Idea。Agent 按命令提示写入唯一输出后执行：

```bash
python3 briefing.py knowledge apply --task <task_id>
```

`apply` 会校验任务绑定、旧 Roadmap 摘要、JSON Schema、Idea 稳定身份、所有证据
ID 和 URL。它从该 Topic 的完整已发布证据重新物化 Roadmap。新增证据没有改变
分支、阶段、状态或开放问题时，版本不增加，但 `change_log` 追加
`no_material_change`。同一任务重复 apply 只返回已有 application，不会重复写入。

检查任务与持久数据：

```bash
python3 briefing.py knowledge status --issue 2026-08-21
python3 briefing.py knowledge validate
```

## 发布新鲜度 manifest 与 Issue Change Projection

`briefing_skill/knowledge_publication.py` 生成两份派生发布投影：

`knowledge/manifest.json` 回答“长期知识追上归档了吗”。字段包括归档水位
`archive_head_issue`、分析目标 `analysis_target_issue`、物化水位
`materialized_through_issue`、`publication_state`、`pending_issues`、
`affected_topics`/`completed_topics` 和与 graph 同源的 `snapshot_id`。
`publication_state` 区分：

- `archive_only`：归档已发布，尚未为待分析期次准备知识任务；
- `analysis_pending`：待分析期次的任务已 prepare 或执行中；
- `knowledge_complete`：物化水位等于归档水位，无待分析期次；
- `analysis_failed`：运维显式标记的失败态，保留上一份完整知识继续可读。

`knowledge/issue-diffs/<issue_date>.json`（Issue Change Projection）把首页的
“当前判断/本期变化”绑定到显式 application、Roadmap 版本快照与已发布证据。
它从持久状态确定性推导：`change_kind`、`what_changed`（比较相邻版本快照的
分支/阶段/开放问题差异）、`current_judgement`（该期次生效的 Roadmap
summary）、`evidence_state`、`evidence_item_ids` 与 `idea_events`。约束：

- 每期 diff 必须在该期次任务全部 apply 后立即构建；`status=partial` 的投影
  不得展示为完成分析。
- seed 基线行 `origin=seed_baseline`、`change_kind=baseline_seed`，不携带
  首页判断字段。
- 语义校验拒绝“现有公开归档…积累了 N 条专题证据”“首版先保留…时间线”等
  seed 模板句出现在 `current_judgement`/`what_changed`/`why_it_matters`；
  `material_change` 行必须携带非模板 `current_judgement`，否则该行退出首页
  判断列，而不是回退到模板句。
- 前端只渲染投影原文，不在浏览器内综合判断。

命令：

```bash
python3 briefing.py knowledge manifest build    # graph build 之后运行
python3 briefing.py knowledge manifest validate # 重算图谱 digest 并交叉核对
python3 briefing.py knowledge diff build --issue 2026-08-29
python3 briefing.py knowledge diff validate [--issue 2026-08-29]
```

完整的新一期流程（回填与常规增量相同，必须逐期执行以保留逐期 change log）：

```text
prepare → 逐任务 apply → knowledge validate
→ knowledge graph build → knowledge graph validate
→ knowledge diff build --issue <本期> → knowledge diff validate
→ knowledge manifest build → knowledge manifest validate
```

注意：任务绑定包含前一期次 apply 后的 Roadmap digest，因此下一期必须在本期
全部 apply 之后重新 `prepare`；上一期次的 diff 已按当时状态固化，不要在后续
期次 apply 后重建旧期 diff（判断字段以构建当时的 Roadmap 状态为准）。

## 派生知识图谱（knowledge/graph.json）

`knowledge/graph.json` 是由 Graph Builder 从权威输入生成的发布派生物，
不是新的权威知识库。权威来源仍然只有 `archive/`、`knowledge/index.json`
指向的 Roadmap 与 Idea 文件；任何图谱节点都必须能反向定位到其中至少一个对象。

构建与校验：

```bash
python3 briefing.py knowledge graph build      # 确定性重建并原子替换
python3 briefing.py knowledge graph validate   # 与当前输入比对新鲜度
```

构建规则：

- 构建前先运行完整的长期知识仓库校验（与 `knowledge validate` 同一套 Schema
  与语义校验）。Roadmap 或 Idea 文件无效时构建直接失败，不会把残缺输入
  伪装成一张符合 graph Schema 的图；因此知识侧的悬空引用是构建失败，
  `unresolved` 主要承载 Archive 侧（如编辑判断引用）的悬空引用。
- 关系只来自显式字段（`direction_id`、`synthesis.judgements[].evidence_item_ids`、
  Roadmap branch 的 `direction_ids`/`evidence_item_ids`/evidence_timeline、
  Idea 的 `topic_ids`/`evidence_for`/`evidence_against`）；Topic 名、Direction 名
  和关键词只用于显示与搜索，不用于补边。
- 缺少目标、关系类型或 provenance 的引用进入 `unresolved`，不绘制成已确认边；
  超过允许阈值（当前 20 条）时构建失败，不覆盖上一份有效文件。
- NetworkX 只做构建期结构校验（重复、悬空端点、关系端点 kind、自环与连通分析）；
  坐标由稳定分层算法计算，输出顺序固定为
  `kind rank → topic_id → direction_id → issue_date → stable id`。
- 同一输入连续构建两次，除 `generated_at` 外必须字节等价；测试可用
  `SOURCE_DATE_EPOCH` 固定时间。
- 文档携带 `archive_through_issue` 与 `knowledge_through_issue` 两个独立水位，
  分别来自归档期次和 Roadmap/Idea 的更新期次，不得合并成一个“已更新”标签。
- `input_digest` 覆盖所有参与构图的输入文件；前端只用它诊断构建版本，
  不计算、不修补。

发布时机：GitHub Pages 工作流在组装站点前依次执行三道门禁：

1. `knowledge validate`——权威知识仓库自身必须有效；
2. `knowledge graph build` 与 `knowledge graph validate`——图谱与当前输入
   一致，不一致时停止发布陈旧图谱；
3. `knowledge manifest build` 与 `knowledge manifest validate`（含
   `knowledge diff validate`）——manifest 与归档水位、物化水位、graph
   snapshot 交叉一致；manifest 声明 `knowledge_complete` 而水位未追平、
   graph 过期或 head 期次 diff 缺失/不一致时，构建必须失败。
   `archive_only`/`analysis_pending` 允许发布，但首页必须展示明确的
   pending 状态，不得把旧 Roadmap 摘要伪装成本期变化。

图谱构建器、Schema 或依赖文件的变化同样触发 Pages 部署，保证 `gh-pages`
不会继续运行旧代码构建的图。本地归档发布后应同样运行 build 保持工作区新鲜；
图谱构建失败不影响邮件生成或发送。

## 判断边界

- 证据不足时必须使用 `view_mode=evidence_timeline`，不得为了展示强造阶段。
- Idea 分为 `research_hypothesis` 与 `solution_concept`。单独补测指标不是 Idea。
- Idea 身份由问题、核心机制和目标对象共同确定，不使用 `project_question` 代替。
- `validation_plan.execution_status` 固定为 `suggestion_only`，只给仿真、数据分析、
  benchmark、原型或持续观察建议，不保存虚构结果。
- AI 可以将 Idea 标为 `rejected`，但必须有反对证据和追加式决策记录；新证据允许
  用 `reopened` 决策重新打开。
- 所有已发布 Radar 先作为 `frontier_exploration` 证据，保留原 Radar category，形成
  temporary cluster。Frontier 任务的 `roadmap` 必须为 `null`。
- cluster 只有跨期持续出现、形成稳定机制或已经产生 Idea 后才能显式升级；升级时
  必须绑定一个非 Frontier 的稳定 Topic 和 branch。之后由目标 Topic 的有界任务吸收
  证据，系统不会创建包罗万象的 `frontier_exploration` Roadmap。

## 首版数据

`scripts/seed_knowledge.py` 使用当前六期公开归档生成首版数据。所有 Roadmap 都
保守地采用证据时间线；脚本只建立具有明确问题、机制和验证方法的少量 Idea。
它不会重新选择旧日报内容。
