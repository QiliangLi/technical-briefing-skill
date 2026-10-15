# ZCode workflow 编排 briefing 执行（止于 READY_TO_SEND）

- Status: accepted
- Created: 2026-10-15
- Last updated: 2026-10-15

## Problem and evidence

当前 SKILL.md 的正常运行把全部语义任务放进**一个主会话**顺序执行：`tasks next` → 读 Prompt/输入 → 产出 → `advance` 循环，直到 `READY_FOR_RENDER`。所有中间产物（执行说明卡、Evidence Pack、facts、Machine Item、reader 文案、校验输出）都流经同一会话上下文；一次端到端运行（数十个任务）后主会话上下文特别长，后续轮次输出精度下降。

代码考察定位出的主要膨胀点（均由主会话内联执行）：

| 膨胀点 | 单次载荷上限 | 频次 |
| --- | --- | --- |
| `fact_extraction` 会话组 | 组内 Evidence 合计 ≤72k 字符 | 每期多组 |
| `relevance_batch` | ≤48k 字符/批（≤24 候选） | 每 topic ≥1 批 |
| `item_writing_batch` | ≤65k 字符/批（≤4 events） | 多批 |
| `reader_projection` | 整期最终条目单任务 | 1 次/期 |
| 循环开销 | 每轮 instruction card + advance 结果 + Prompt/Schema 回读 | 数十轮/期 |

与膨胀并存的事实是：流水线**状态早已全量落盘**（`workspace/briefing.sqlite` + `workspace/runs/<run_id>/` 下的任务输入/输出/缓存/校验产物），`tasks next` 返回的执行说明卡自带输入路径、输出路径、Schema 与证据边界引用——它本身就是一份按任务隔离的子代理工作合约。缺的只是把"执行者"从主会话换成一批全新上下文的子代理，并把"循环驱动"交给一个只持有路径与状态的编排器。

ZCode 宿主内建 dynamic workflow 编排（`CreateWorkflow`/`SaveWorkflow` + TypeScript 编排脚本），能力与诉求逐条对上：

| 诉求 | workflow 原语 |
| --- | --- |
| 子代理全新上下文、互不污染 | `agent().ask()` 每次调用即新上下文 |
| 编排器不搬运正文 | 类型化结果只传路径/状态（"pass paths, not file contents"） |
| 确定性步骤归 CLI | `world.run`（命令为编译期字面量、args 数组传参、journal 确定性重放） |
| 运行进度实时可视 | `phase()` 阶段图 + `report()` 实时结果流 + `artifact.*` |
| 主会话释放 | 后台运行，完成通知携带最终 `return` 值 |
| 中断恢复 | `ResumeWorkflowRun` journal 重放；盘上流水线状态本身幂等 |

### CLI 输出格式核实（2026-10-15，实现依据）

- `advance`（`pipeline.py:183-190`，经 `session_grouping.install_session_grouping` 补丁组感知化）打印 JSON：`{synced, applied, invalid, pending, stage, next_task}`；`invalid` 是**计数**（`invalid + len(invalid_rows)`）；`next_task` 为组感知执行卡或 `null`；有 invalid 时退出码 1。`run` 与 `resume` 内部以 `cmd_advance` 收尾，同样打印该 JSON。
- `tasks next`（补丁后，`session_grouping.py:313-333`）打印组感知执行卡；无任务时打印 `No pending tasks`；同时调用 `_mark_group_started` 记录遥测尝试计数——编排循环沿用 `tasks next`（而非仅靠 `advance.next_task`）以与手动路径的遥测语义一致。
- 单任务卡首行 `Task {id} ({task_type})`（`tasks.py:471-480`）；fact 会话组卡首行 `Fact-extraction execution batch: {n} independent tasks...`，组内任务行 `   Task {index}: {id} ({entity_id})`（`session_grouping.py:194-224`）。
- `tasks list --status INVALID` 按行打印 `{status:9} {task_type:20} {id} -> {output_path}`，可解析出 INVALID 任务 ID 与输出路径。
- `render --execute` 打印含 `email` 路径的 JSON，退出码恒 0；`validate` 打印校验报告 JSON，存在 `failures` 时退出码 1（`cli.py:230-254`）。

## Goals and non-goals

Goals:

1. 主会话零语义载荷：一期运行结束后，主会话只收到最终 `WorkflowReport`（结论 + 校验摘要 + 产物路径 + 未覆盖项）。
2. 实时进度可视：阶段图（`phase`）+ 每任务完成上报（`report`）+ 发布 email.html/validation.json 为 artifact。
3. 质量门禁零回归：Evidence Gate、`validate`、Schema/语义校验、`--confirm-send` 全部仍由 Python CLI 强制。
4. Python 侧零改动：不改任务图、调度、Schema、门禁、输出格式；编排只消费既有 CLI。
5. 可恢复：任一时刻中断都能从盘上状态继续（workflow resume 或新起 workflow 均可）。

Non-goals:

1. 不改任务图结构与 `tasks next` 串行语义（不引入任务级并行）。
2. 不把发送与归档纳入 workflow（止于 `READY_TO_SEND`，决策 1）。
3. 不把发布后 knowledge 队列（materialization/graph/idea）纳入本期设计。
4. 不在 workflow 内做任何定时/调度（ZCode workflow 明确禁止；宿主 Cron 触发列为后续扩展）。
5. 不改跨宿主行为（Claude Code 宿主的 `codex:codex-rescue` 桥接路径不受影响）。

## Constraints and invariants

1. **门禁不变**：`docs/contracts/code-review-invariants.md` 的 run 隔离、`advance` 幂等、Evidence Gate / 必要 Fact Check / Reader Projection 完整性门，编排不得绕过；`validate` 仍是唯一发布门（`READY_TO_SEND` 的唯一晋级路径）。
2. **发送治理**：无 `--confirm-send` 必须拒绝；Agently 两步令牌流程原样保留在主会话人工环节（AGENTS.md、change-governance）。
3. **证据边界逐字入 ask**：SKILL.md「上下文与成本硬规则」对各任务类型的读取范围限制，必须写入对应子代理指令；fact 会话组的组内隔离规则（前序任务证据不可采信、禁止合并输出/batch 数组、逐任务 `_task` 绑定）同样传递。执行卡本身已携带这些约束，ask 只叠加"不运行 CLI、不扩大读取"的编排边界。
4. **状态迁移单一所有权**：`tasks next` / `advance` / `reopen-invalid` / `render` / `validate` 只由编排脚本的 `world.run` 执行；子代理只读输入、只写自己的任务输出文件，不得运行 CLI 子命令。这同时保证 journal 重放的确定性与 `advance` 的幂等。
5. **用户显式发起**：ZCode 规则要求 workflow 只能由用户显式请求启动（`CreateWorkflow saved`）；编排器不得自我触发。
6. **循环有界**：任务轮次、单任务 INVALID 修复次数、validate 修复循环次数均设硬上限，超限停止并汇报，等待人工介入。
7. **可回退**：任何时刻可放弃 workflow，切回 SKILL.md 手动循环；盘上状态无需任何迁移。

## Proposed design

### 执行模式定位：双模式（决策 2）

SKILL.md 增设「ZCode workflow 执行模式」一节：ZCode 宿主下默认以 `CreateWorkflow saved: briefing-run` 发起编排运行；现有手动循环（`tasks next` → 执行 → `advance`）保留为回退与调试路径（`tasks next-single` 语义不变）。Python CLI 与任务图对两种模式完全无感知。

### Workflow 总体结构

三段 `phase()` 即用户看到的进度图：

```
初始化 briefing 运行 → 逐个执行 Agent 任务（循环体为同一 phase） → 渲染并做发布前校验 → 发布产物并 return（终止于 READY_TO_SEND）
```

| 阶段 | 编排动作 | 子代理动作 |
| --- | --- | --- |
| 初始化 | `world.run` 执行 `briefing.py run`（新一轮）或 `resume --run latest`（续跑），由参数 `mode` 选择；解析末尾 advance JSON 取初始 stage | 无 |
| 处理Agent任务 | 循环：`tasks next` → 解析执行卡 → 为该任务/组派发一个全新匿名子代理 → `advance` → 处理 INVALID | 读 Prompt/输入/引用证据，写输出 JSON，返回窄类型 `{task_ids, outputs_written, notes}` |
| 渲染与校验 | `render --execute` → `validate`；FAIL 时有界修复循环；通过后 `artifact.file` 发布 email.html（primary）与 validation.json | 修复子代理读 `validation.json` FAIL 项做最小修复 |

### Agent 任务循环（核心）

```
phase("逐个执行 Agent 任务")
while 轮次 < 80:
    next = world.run(tasks next --run latest)
    card = parseCard(next.stdout)        # "No pending tasks" → 退出循环
    outcome = agent().ask<TaskOutcome>(card 原文 + 编排硬边界)
    report({轮次, 任务类型, task_ids, ok})
    adv = world.run(advance --run latest) # JSON: stage/invalid/pending
    若 invalid > 0 → 有界修复（见下）
```

要点：

- **每任务/组一个全新匿名子代理**：不命名、不跨任务复用上下文（匿名即天然无重名风险）；fact 会话组按执行卡原样整体交付给一个子代理，组内隔离规则已在卡内。
- **指令 = 执行卡原文 + 固定硬边界段**：只读卡内引用文件、写指定输出路径、符合 Schema、**不运行 briefing.py 子命令**（执行卡末步"Run advance"由编排器代执行，ask 中显式覆盖）、无法合规时升级提问而非伪造。卡文本属于工作合约本身，直接插值。
- **类型化结果只含标识与状态**，编排器永远不搬运正文。
- 循环天然幂等：`tasks next` 只发下一个待办，`advance` 从盘上同步输出；中断后无论 resume 还是新起 workflow，都不重做已完成任务；relevance/facts cache fast path 语义不变。
- **解析器**（正则，纯脚本逻辑）：单任务卡 `^Task (\S+) \((\S+)\)$` 取首行 id/type；会话组卡 `^ {3}Task \d+: (\S+) \(` 收集全部任务 id，`task_type` 取 `fact_extraction`；`advance` 输出直接 `JSON.parse`。

特殊任务类型：

- `agent_web_search`：子代理用宿主工具做开放搜索，按卡内规则写 `web-search-results` 输出。
- `illustrated_publication`（1 次/期）：整任务交付单个子代理。ZCode 子代理具备全工具，直接按 SKILL.md 默认路径调 `python -m briefing_skill.image_api` 像素通道并完成 QA、manifest 与资产提交；Claude Code 宿主的 codex 桥接路径不变。
- `reader_projection`（1 次/期）：执行卡已带 `required_skills: ["human-writing"]`，子代理按卡加载 `$human-writing`。

### INVALID 与修复

`advance` 返回 `invalid` 计数 >0 时：`tasks list --status INVALID` 解析出任务 ID 与输出路径 → 派发修复子代理读取各任务输入与输出、按 `schema_path` 自检并做**最小定向修复**（不得扩大证据读取范围、不运行 CLI）→ `tasks reopen-invalid` → `advance` 重新同步。同一任务修复次数 ≤2，超限停止并汇报。`invalid_repair.py` 自动创建的定向修复任务会作为普通任务出现在队列中，编排器无需特判。修复子代理若删除了无可救药的输出文件，任务回到 PENDING，由下一轮 `tasks next` 重新发卡，天然自愈。

### 渲染与校验

`render --execute --run latest`（Playwright 截图，`timeoutMs` 放宽到 10 分钟）→ `validate --run latest`。退出码 1（存在 `failures`）时进入有界修复循环（≤3 次）：修复子代理读 `validation.json` FAIL 项做最小修复，重渲染重校验；仍失败则停止并在返回值附完整 FAIL 清单。校验通过即 issue 处于 `READY_TO_SEND`，编排脚本把 `email.html`（`primary: true`）与 `validation.json` 发布为 artifact，供人工预发送评审。

### 终止与交接（决策 1）

Workflow 终止于 `READY_TO_SEND`，不执行 `send`。`WorkflowReport` 附 `email.html`、`email-illustrated.html`、`validation.json` 路径与摘要，主会话转述给用户；人工阅读确认后由主会话执行 `send --confirm-send` 两步令牌流程，发送成功后的自动归档/推送流程不变。发送确认**不**使用子代理 escalation——留在主会话是对"邮件必须人工确认"治理底线的最直接兑现。

无任务且 stage 处于终态（如 `NO_EDITORIAL_ELIGIBLE`、`FETCH_DEFERRED`）时跳过渲染直接返回说明，不伪装为成功。

### 进度可视

- `phase()` 三阶段图（运行确认对话框按 phase 绘制，用户启动前即看到整体结构）。注意：阶段线的节点是 phase 而非单个任务，任务循环整体是一个节点。
- 每张执行卡派发与完成各一次 `report()`（打 `tasks` tag）——实时进入运行结果流，并驱动任务看板。
- 任务看板：`artifact.board("tasks")`，每张执行卡一张卡片，在 执行中/修复中/完成/修复后完成 列间移动，resume 后原样重建（2026-10-15 增补）。
- `log()` 人类可读叙事线（每轮开始/关键分支）。
- 终态发布 `artifact.file`：`email.html`（primary）+ `validation.json`。

### 交付形态与触发扩展

`.zcode/workflows/briefing-run.dwf.ts`（project scope，随仓库提交，声明参数 `mode: "run" | "resume"`，默认 `resume`）。日常以 `CreateWorkflow saved: briefing-run` 一键发起；用户确认脚本与 `world.run` 命令集后后台运行，主会话在完成通知到达前可做其他工作。

定时触发的扩展方向：宿主 Cron（ZCode `CronCreate`）在约定时间向会话发送"发起今日 briefing workflow"的提示，由主会话调用 `CreateWorkflow`——workflow 自身禁止调度，Cron 位于编排之外，与 SKILL.md"触发由 Cron/宿主任务系统负责"的既有分工一致。

### 附录：TS 编排脚本

实现在 `.zcode/workflows/briefing-run.dwf.ts`（随本设计一起落地），结构即上述三段 phase + 解析函数 + 有界修复循环 + `WorkflowReport` 返回。

## Compatibility and migration

1. **双模式并存**：SKILL.md 手动循环保留原样，作为回退/调试路径；任何进行中或历史 run 都可用任一模式继续（状态只在盘上）。
2. **旧 run 无迁移**：workflow 首步即 `resume --run latest`（或 `run` 开新期），从既有 SQLite + 运行目录续跑。
3. **Python 零改动**：已核实全部所需输出（advance JSON、组感知执行卡、`tasks list --status INVALID`、render/validate JSON）均为现网格式，正则/JSON 解析即可，无需 `--format json` 开关。
4. **跨宿主**：Claude Code 宿主的 `illustrated_publication` codex 桥接、发送两步令牌、归档推送流程全部不变。
5. **knowledge 队列**：发布后的 materialization/graph 仍走独立队列与会话，不受影响。

## Failure, recovery, and rollback

| 故障 | 处置 |
| --- | --- |
| workflow 被中断（进程退出/用户停止） | `ResumeWorkflowRun` journal 重放 `world.run`；或直接新起 workflow——盘上流水线状态幂等，`tasks next` 只发下一个待办 |
| 编排脚本自身缺陷 | 修订 `.zcode/workflows/briefing-run.dwf.ts` 后 `AmendWorkflow` 热缓存续跑（已完成的 ask/world.run 零成本重放） |
| 子代理反复 INVALID | 单任务修复 ≤2 次后停止并汇报，转人工（`tasks next-single` 手动路径接手） |
| `validate` 反复 FAIL | 修复循环 ≤3 次后停止，返回完整 FAIL 清单 |
| provider 限流/网络抖动 | 运行时自动重试，编排不写重试循环（ZCode 规则） |
| 回滚 | 放弃 workflow 切回手动循环即可；无状态迁移、无数据格式变化 |

## Verification

1. `EvalWorkflowSnippet` 对真实卡片样本（单任务卡、会话组卡、`No pending tasks`、`tasks list --status INVALID` 行）排练解析函数。
2. 干跑一期真实运行（`mode: "run"`）：全程观察 phase 图与 report 流；`validation.json` 结果与手动路径语义一致。
3. 幂等：中途停止 workflow 后 resume，确认不重做已完成任务。
4. 主会话零膨胀：运行结束后主会话仅见 WorkflowReport。
5. 回退演练：workflow 停止后用 `tasks next-single` 手动接手一个任务。
6. 成本对比：`python briefing.py stats --run latest`。

## Documentation impact

随本实现更新：

- `SKILL.md`：新增「ZCode workflow 执行模式」一节（双模式定位，决策 2）。
- `docs/operations/zcode-workflow-run.md`：新增（发起、进度观察、resume/amend、故障处置、回退演练）。
- `docs/README.md`：Active designs 补登本设计与漏登的 2026-09-24 设计；Operations 补登新手册。
- `.zcode/workflows/briefing-run.dwf.ts`：随仓库提交（SaveWorkflow 产物）。
- 契约文件无需变更（无行为/接口变化）。

## Decision log

- 2026-10-15：运行边界定为**止于 READY_TO_SEND**——发送确认与两步令牌流程留在主会话人工环节，不使用子代理 escalation 代确认（用户选定）。
- 2026-10-15：执行模式定位为**双模式**——ZCode 宿主默认 workflow，手动循环保留为回退与调试路径（用户选定）。
- 2026-10-15：design 与 implementation 合并请求；实质选择已全部解决，状态直接 `accepted`。
- 2026-10-15：状态迁移单一所有权——CLI 子命令只由编排脚本 `world.run` 执行，子代理只读输入/只写输出，保证 journal 确定性与 `advance` 幂等。
- 2026-10-15：Python 零改动——已核实全部所需输出为现网格式（advance JSON、组感知卡、`tasks list --status INVALID`、render/validate JSON），解析用正则 + `JSON.parse`，不加 `--format json` 开关。
- 2026-10-15：循环用 `tasks next` 驱动（而非仅靠 `advance.next_task`），保持 `_mark_group_started` 遥测语义与手动路径一致。
- 2026-10-15：不引入任务级并行，保持 `tasks next` 串行调度语义；并行化留待后续设计。
- 2026-10-15：增补任务看板（`artifact.board` + `report` 打 `tasks` tag）——阶段线的节点是 phase 而非单个任务，任务级"一个任务一个点"的可视由看板与结果流承担。
