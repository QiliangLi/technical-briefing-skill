# 飞书群 Idea 反馈回路（idea-feishu-feedback）

- Status: draft
- Created: 2026-11-13
- Last updated: 2026-11-13

## Problem and evidence

Idea 价值目前不可衡量：`evidence_for` / `evidence_against` 是 AI 对已发布证据的机器分类，不是人类反馈；43 个正式 idea（24 seed / 19 observing）没有一个经过人工反馈或实验验证，0 个反对证据平衡（用户 2026-11-12 确认的痛点，另见 idea 表述抽象到难读的问题）。部门同事是现成的人类反馈来源，用户已计划把部门同事拉进一个飞书群。

本机 feishu 工具验证（2026-11-13）：

- `lark-cli` 1.0.60 可用（上游 1.0.97 可更新，不阻塞）。
- bot 身份 ready（应用「MacBook的飞书 CLI」，`cli_aac810dfc25d1cdd`）；user 身份 refresh token 已于 2026-10-18 过期。
- bot 已授予：`im:message`（发送）、`im:message.reactions:read`（读表情回应）、`im:message:readonly`、`im:chat:read`、`im:chat.members:read`、`contact:user.base:readonly`（姓名解析）。
- bot 缺 `im:message.group_msg`（读取群内全部消息，只影响文字回复收集，不影响表情回应）。
- bot 当前不在任何群（`+chat-list --as bot` 为空）；dry-run 发送路径正常，`+messages-send` 支持 `--idempotency-key`。
- `+chat-messages-list` / `+messages-mget` 自动附带每条消息的 reactions 块，一次调用可同时取回复与回应。

## Goals and non-goals

目标：

1. 每期（可配置节奏）向一个固定飞书群推送少量 idea 的通俗化卡片，每条 idea 独立成消息，使表情回应可按 idea 归因。
2. 低摩擦结构化反馈：表情回应为主信号（👍/👎/🌱/🔁），话题回复为定性信号；一次点按即可反馈。
3. 确定性、幂等的收集：本地私有台账按 idea 聚合，`stats` 可见参与率与分布。
4. 闭环：下一期推送头部展示上一期反馈速览，让同事看到反馈被消费。
5. 观察优先：反馈不自动改 idea 状态，不进入公开 `knowledge/`，不影响机器证据边界。

非目标（v1）：

- 不做交互卡片按钮回调（`card.action.trigger` 需要长连接守护进程，与批处理架构不符）。
- 不做飞书多维表格/问卷通道（后续可选分层）。
- 不自动变更 idea `status`，不写任何反馈数据进 `knowledge/` 公开目录。
- 不做按个人的分析或对外展示；台账仅本地。

## Constraints and invariants

- **外发门禁**：推送到群是外发效果，与邮件同规则——没有用户显式确认 + `--confirm-send` 不发送；cron 自动化止于 READY_TO_PUSH。
- **隐私边界**：`knowledge/` 是 PUBLIC GitHub Pages 权威目录。同事姓名、open_id、回复原文只进 gitignore 的 `workspace/idea-feedback/` 台账；v1 不发布任何聚合到公开站点（含匿名计数，另行决策）。
- **证据边界**：人类反馈永不写入 `evidence_for`/`evidence_against`，永不伪装为 Machine 证据；只作为知识阶段任务的只读上下文出现，引用时显式标注为人类反馈。
- **knowledge/ 权威契约不变**：`knowledge/` 仍只从 `archive/index.json` 已列出的 Machine 记录更新（见 `docs/contracts/knowledge-materialization.md`）。
- **幂等**：推送按 `(issue_date, idea_id)` 幂等（lark-cli idempotency key + 本地注册表）；收集为全量快照重拉 + 差分入账，重跑不产生重复事件。
- **身份**：推送与表情收集走 bot（现有 scope 足够）；文字回复收集在缺 `im:message.group_msg` 时优雅降级（见 D2）。
- **可读性门槛**：推送文案必须通过通俗化（人话）处理，直接回应「idea 表述抽象」痛点。

## Proposed design

### 组件与数据流

```text
knowledge stage (第五步, idea 已物化)
   └─ feedback prepare --issue <date>   生成推送载荷（头部 + ≤N 条 idea 卡片文案）
        └─ feedback push --confirm-send  bot 发送到配置群；message_id 写入注册表
             └─ （同事点表情 / 话题回复，反馈窗口 = 到下次收集前）
下一期自动化开始 / 手动
   └─ feedback collect                  重拉注册表内全部消息的快照 → 差分入账 → 聚合
        └─ feedback status              参与率 / 分布 / top idea
下一次 push 头部                       「上期速览」= 上期各 idea 反馈计数
```

### 配置 `config/idea-feedback.yaml`（默认 `enabled: false`）

`chat_id`、`push_every_n_issues`（默认 3，≈每周）、`max_ideas_per_push`（默认 3）、reaction 语义映射、`collect_lookback_messages`、宿主 `lark-cli` 路径检查。

### 消息形态

- 头部消息（每期一条）：本期导读 + 上期反馈速览 + reaction 图例说明。
- idea 卡片（每条 idea 一条消息，`--markdown`，bot 发送）：标题（通俗化）、问题/假设各 1–2 句人话、为什么重要、一条代表证据、IdeaHub 详情页链接、引导语（点表情或在回复中 @机器人 讨论）。
- Reaction 语义（v1）：👍 值得投入验证 / 👎 不看好 / 🌱 证据还不足 / 🔁 已有人做过（知悉 prior art）。

### 选择哪些 idea 推送

优先级：本期 `status_changed` 或新增证据的 idea > 本期新建 idea > 长期零反馈旧 idea（每期至多 1 条「翻新」）。截断到 `max_ideas_per_push`。

### 本地台账 `workspace/idea-feedback/`（gitignore）

- `registry.json`：`message_id → {idea_id, issue_date, pushed_at, kind: header|idea_card}`。
- `ledger.jsonl`：追加式事件流（reaction 增/删/换、回复原文 + 作者姓名/open_id + 抓取时间），事件 ID = `message_id + operator + emoji_type`（或回复 message_id）。
- `snapshots/<collect_ts>.json`：每次收集的原始快照（可重放、可审计）。
- 聚合表进 `briefing.sqlite`（`idea_feedback_summary`），`python briefing.py stats` 新增 `idea_feedback` 块：参与人数/率、各 idea 的 👍/👎/🌱/🔁 计数与净分、回复数。

### CLI 与流水线集成

```bash
python briefing.py feedback prepare --issue 2026-11-13
python briefing.py feedback push --issue 2026-11-13 --confirm-send
python briefing.py feedback collect
python briefing.py feedback status
```

推送位于知识阶段（第五步）之后的可选第六步，受配置与确认门禁控制；收集挂在自动化运行开头（收集阶段之前）+ 随时可手动跑。宿主无 `lark-cli` 时显式报错并禁用推送，不影响其余流水线。

### 对 idea 的作用（v1）

无自动作用。收集产物作为下一期知识阶段任务的只读上下文（Agent 可在 `decision_log` 理由中引用并标注「人类反馈」，但证据仍须是 Machine 证据）。是否把匿名聚合计数公开到 IdeaHub、是否允许人类反馈触发状态迁移，均留待观察期后的独立设计。

## Compatibility and migration

纯增量：新配置文件（默认关闭）、新 workspace 台账目录、新 CLI 子命令；不改 `idea.schema.json` 与任何 knowledge 文件，不改现有任务顺序。旧运行与环境完全不受影响；无迁移。建议实现前把 lark-cli 升到 1.0.97（非阻塞）。

## Failure, recovery, and rollback

- 推送部分失败：注册表逐消息记录状态，重跑只补发缺失消息（幂等 key 防重）；头部消息最后发。
- 收集失败：逐消息隔离；缺 `im:message.group_msg` 时降级为仅表情回应并在 `status` 中告警。
- bot 被移出群 / 凭据失效：明确报错，本地台账无损失；恢复后重跑 collect 补齐。
- 回滚：`enabled: false` 或删除 `workspace/idea-feedback/` 即可，无其他状态被触碰。
- user 身份过期不影响 v1（全程 bot）。

## Verification

- 单元测试：注册表幂等、reaction 增/删/换的差分入账、聚合计算、配置校验；夹具为合成 reaction 快照（沿用 `human_review_*` 的测试排除前缀约定，合成数据不进长期统计）。
- 端到端冒烟（受门禁保护，需用户配合）：建测试群 → bot 入群 → 推 1 条测试卡片 → 用户点表情 + 回复 → `collect` → 断言台账与 `status`。同时验证两个平台行为：bot 能否读到自己消息上的 reactions（当前 scope 下）；未授 `im:message.group_msg` 时话题回复的可见性边界，实测结论写进运维文档。
- 文档：SKILL.md 新可选步骤与确认规则、`docs/operations/idea-feedback.md`、README 简述。

## Documentation impact

`SKILL.md`（第六步 + 外发确认规则扩展到群推送）、`docs/operations/idea-feedback.md`（新）、`docs/architecture.md`（一段数据流说明）、`README.md`（一句功能提及）、`config/idea-feedback.yaml`（自述注释）。

## Decision log

- 2026-11-13 创建草案。工具验证结论见 Problem 一节；v1 采用 bot-only 路线以避开 user 身份重授权。以下为待用户裁决的开放决策：
  - D1 反馈信号集：仅表情回应（推荐 v1）vs 表情+文字回复 vs 表情+卡片按钮。
  - D2 文字回复收集通道：引导回复中 @机器人（零审批，推荐 v1）vs 申请 `im:message.group_msg`（需管理员审批，读全群消息）vs user 身份重授权后读取。
  - D3 推送节奏：每 3 期一次 ≈ 每周、每次 ≤3 条（推荐）vs 每期都推（隔天，疲劳风险）vs 每期 1 条焦点 + 每周汇总。
  - D4 卡片文案：有界 Agent 任务生成通俗文案（推荐，回应可读性痛点）vs 纯模板拼接。
  - D5 推送门禁：首 2 期逐期确认后转常设授权（仅限配置的单一 chat_id，推荐，类比 gh-pages 预览页常设授权）vs 永久逐期确认。
  - D6 聚合是否公开：v1 不公开（推荐）vs 公开匿名计数到 IdeaHub。
