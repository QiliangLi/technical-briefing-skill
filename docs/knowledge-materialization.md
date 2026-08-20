# Roadmap 与 Idea Bank 物化层

`knowledge/` 是 GitHub Pages 可直接发布的权威知识目录。它只从
`archive/index.json` 已列出的 `issue.json` 与 `papers.json` Machine 记录更新，
不读取候选池、全文、`reader.json` 或网页临时分组。

## 目录契约

```text
knowledge/
├── index.json
├── roadmaps/<topic_id>.json
├── ideas/<idea_id>.json
├── frontier-clusters.json
├── history/roadmaps/<topic_id>/vN.json
└── applications/<task_id>.json       # apply 后生成，可用于幂等审计
```

`index.json` 中的 `path` 均从站点根目录开始，例如
`knowledge/roadmaps/agent_acceleration.json`。

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
