# briefing-run 波次并行执行（同一待办队列内的任务级并行）

- Status: draft
- Created: 2026-10-18
- Last updated: 2026-10-18

## Problem and evidence

`2026-10-15-zcode-workflow-orchestration.md` 的决策日志明确"不引入任务级并行，保持 `tasks next` 串行调度语义；并行化留待后续设计"。首次端到端运行（2026-10-16-115317 期）给出了做这件事的直接证据：

| 观测 | 数据 | 来源 |
| --- | --- | --- |
| 总时长 | 约 37 小时（10-16 16:23 → 10-18 05:17） | run 创建时间与产物 mtime |
| 无故障段均速 | 前 25 轮 2 小时 20 分，约 5.6 分钟/轮 | `GetWorkflowRun` 日志尾 |
| 提供方停滞 | ≥16.5 小时有通知记录（第 25 轮内约 9 小时、第 26 轮内 ≥6.5 小时、另有 1 小时与两次半小时级） | workflow-stall 通知 |
| 串行成本估算 | 78 轮 × 5.6 分钟 ≈ 7.3 小时纯执行，与提供方无关 | 推算 |
| 手动模式基线 | 宿主直接按 PENDING 列表委派，**并发 ≤6**（12 路触发账户速率限制）；一波后统一 `advance` | 2026-10-08 期执行记录 |
| 单步 token | fact 组卡（4 任务共用一个子代理会话顺序处理）单步 130 万–150 万 token；整次续跑约 1,730 万 token | `GetWorkflowRun` 子代理用量 |

结论：提供方故障是本次时长的主因但不可由脚本解决；串行任务循环是 workflow 模式相对手动模式**唯一的结构性退化**，可解决。

并行化的可行性已在代码层核实（均为现网实现，非假设）：

- `TaskService.list(run_id, "PENDING")` 的排序是 `ORDER BY priority DESC, created_at`（`tasks.py`），与 `TaskService.next()` 完全一致——PENDING 列表的前 K 行就是串行队列接下来会依次派发的 K 个任务。
- 每个任务在创建时即生成 canonical 执行信封 `workspace/runs/<run>/tasks/<type>/<id>.execution.json`（`execution_envelope.py:install_execution_envelope_contract` 包装 `TaskService.create`），单任务执行卡 `canonical_task_instructions` 完全由该信封与 `output_path` 决定。
- `Pipeline.advance()` 先 `sync` 盘上**所有** PENDING 任务的输出再逐个应用（`pipeline.py:152`），对"一波多任务后只跑一次 advance"天然幂等；手动模式正是这样用的。
- `tasks next` 的 `_mark_group_started` 只更新 `task_metrics` 遥测（attempts / started_at），不改任务状态；因此并行化不能靠重复调用 `tasks next`（总是返回同一张卡），需要按任务 ID 取卡的途径。
- 同时处于 PENDING 的任务彼此独立：流水线的阶段依赖通过**任务创建时机**表达（`_maybe_prepare_*` 只在前置任务全部 APPLIED 后创建下一阶段任务），`priority` 只表达派发偏好，不表达依赖。

## Goals and non-goals

Goals:

1. 同一时刻并行执行队列前 K 个待办任务，把任务循环的墙钟时间压到串行的约 1/K（K 默认 6）。
2. Python 侧改动限于**只读**的取卡命令；任务图、优先级、阶段门禁、Schema/语义校验、Evidence Gate、`validate` 发布门全部不变。
3. 可视化按任务可读：每个子代理按"波次·类型·任务 ID"命名；看板按波次或任务显示进度。
4. 可恢复、可回退：中断后 `mode: "resume"` 继续；`concurrency: 1` 退化为现行串行行为。

Non-goals:

1. 不改变任务创建顺序、优先级或阶段切换逻辑；不跨阶段"预取"任务。
2. 不在子代理间共享上下文或证据（每任务仍是全新上下文）。
3. 不处理提供方故障（运行时已无限退避重试；运营约定见 `docs/operations/zcode-workflow-run.md`）。
4. 不把发送/归档纳入 workflow（仍止于 `READY_TO_SEND`）。

## Constraints and invariants

1. 继承 10-15 设计的全部不变量：门禁不变、状态迁移只由编排脚本 `world.run` 执行、证据边界逐字入 ask、循环有界、用户显式发起、随时可回退手动循环。
2. **波内隔离**：一波内的任务各有独立信封与输出路径，子代理只写自己的输出文件；任何共享文件（SQLite、manifest、缓存）只由脚本的 `advance` 触碰。这是 `Promise.all` 并行的前提，也由现有"子代理禁止运行 briefing.py"规则保证。
3. **并发上限**：K ≤ 6（账户速率限制实测）；运行时仍会按提供方接受度自适应收缩。
4. **优先级语义**：一波取 PENDING 列表的前缀，不跳过更高优先级的任务。
5. **遥测一致**：按 ID 取卡时镜像 `tasks next` 的 `_mark_group_started` 语义（attempts 计数），避免 `briefing.py stats` 低估尝试次数。
6. **report 容量**：ZCode 一次运行最多 256 条 `report` 条目；本期 149 个任务若每任务两条上报会越界并使整个运行失败，看板粒度必须按此设计。

## Proposed design

### Python：新增只读取卡命令 `tasks card --task <id>`

在 `session_grouping.py` 的 `cmd_tasks` 补丁（或 `execution_envelope.py` 的契约安装处）增加 action `card`：按 `--task <id>` 读取任务行，打印 `service.instructions(task)`（即 canonical 单任务卡），并对该任务调用与 `tasks next` 相同的遥测标记。只读，不改任务状态，不触发任何 `_maybe_prepare_*`。

选它而不是在脚本里拼卡文本的理由：执行卡文本是工作合约，应单源于 `execution_envelope.py`；首跑已经因脚本侧正则与卡片格式漂移吃过亏，把文本生成留在 Python 一侧可避免再次漂移。

### 脚本：波次循环替换逐卡循环

```
phase("按波次并行执行 Agent 任务")
while waves < MAX_WAVES:
    rows = parse(world.run(tasks list --status PENDING))      # priority 顺序
    if rows 为空 → break
    wave = rows.slice(0, K)                                    # 前缀，不跳优先级
    cards = await Promise.all(wave.map(t => world.run(tasks card --task t.id)))
    outcomes = await Promise.allSettled(
        wave.map((t, i) => agent(`第${waves}波·${t.task_type}·${t.id.slice(0,8)}`)
                            .ask<TaskOutcome>(taskAsk(cards[i])))
    )
    adv = advance（沿用 300s → 900s 捕获重试）
    若 adv.invalid > 0：
        rows = tasks list --status INVALID → 逐任务修复预算检查
        await Promise.allSettled(rows.map(r => agent(`第${waves}波·修复·${r.task_id.slice(0,8)}`).ask(repairAsk([r]))))
        reopen-invalid → advance
```

要点：

- **波的组成**：PENDING 列表前 K 行，不限任务类型（同时 PENDING 的任务由创建时机保证互相独立）。保留一个保守开关"仅同类型成波"作为参数，默认关闭。
- **执行单位是单任务**，不再使用 `peek_group` 的 fact 会话组卡。代价是失去"一个会话顺序处理 4 个 fact 任务"的共享 Prompt/Schema/判断卡读取；收益是上下文不再跨任务累积（首跑 130 万–150 万 token 的单步正是组卡），且天然并行。预期总 token 不升反降，需用 `briefing.py stats` 实测确认。
- **`Promise.allSettled` 而非 `Promise.all`**：一个任务升级提问或失败不拖垮同波兄弟；失败任务没有输出文件，`advance` 后仍为 PENDING，下一波自然重发；INVALID 修复预算仍按任务 ≤2 次。
- **K 作为 workflow 参数 `concurrency`**（默认 6）：留在脚本控制流里、不插值进 ask 文本（避免调参导致 amend 缓存全失效）；`concurrency: 1` 即现行串行行为，也是回退路径。
- **子代理命名**：`第N波·<task_type>·<ID 前 8 位>`；修复子代理 `第N波·修复·<ID 前 8 位>`；校验修复不变。
- **看板粒度按波**：每波一张卡（key = `wave-N`，detail 列出任务 ID 与类型），执行中 → 完成 / 修复后完成；每波两条上报，上限 80 波也只有 160 条，远低于 256 条上限。任务级"谁在做什么"由命名子代理在运行流中承担。
- 其余阶段（初始化、渲染与校验、产物发布）不变。

### 待评审的实质选择

1. **取卡途径**：新增 `tasks card --task <id>`（推荐；单源、只读、约 15 行）vs 脚本内按信封路径自行拼卡（Python 零改动，但再次与卡格式耦合）。
2. **波的组成**：前缀任意类型（推荐）vs 仅同类型成波（更保守，阶段交界处并行度下降）。
3. **执行单位**：单任务（推荐）vs 保留 fact 组卡（需要 `tasks peek --limit K` 之类能返回 K 个组的命令，改动更大）。
4. **默认并发 K**：6（手动实测安全值）；是否同时在脚本里设置 `agent_web_search` 四条 lane 可全并行。
5. **看板粒度**：按波（推荐，受 256 条上限约束）vs 按任务只上报完成一条。

## Compatibility and migration

1. 任何进行中的 run 都可直接切换：波次脚本只读当前 PENDING 列表，已 APPLIED 的任务不会再出现；从串行脚本的运行中途改用波次脚本、或反之，都不需要迁移。
2. 手动循环与 `tasks next` / `tasks next-single` 语义不变；`tasks card` 是新增 action，不影响既有 action。
3. relevance / facts cache 快路径在 Python 内部，不受并行影响。
4. `task_metrics` 遥测：`tasks card` 镜像 `tasks next` 的尝试计数，`briefing.py stats` 口径不变。
5. Claude Code 宿主的手动/桥接路径不受影响。

## Failure, recovery, and rollback

| 故障 | 处置 |
| --- | --- |
| 一波中某任务失败/升级提问 | `allSettled` 隔离；该任务无输出仍为 PENDING，下一波重发；升级提问由主会话回答后该子代理继续 |
| 同波任务重复写同一输出 | 不可能发生：每任务独立 `output_path`，由信封绑定；`_task` 回显在 `sync` 时校验 |
| 账户速率限制 | K ≤ 6；运行时自适应收缩；持续限流表现为停滞通知，运行不失败 |
| `advance` 超时 | 沿用 300s → 900s 捕获重试；仍超时则主会话手动 `advance` 后 `mode: "resume"` |
| 波次上限 | `MAX_WAVES`（建议 40）到达即停止并汇报，盘上状态完整可续 |
| 回退 | `concurrency: 1` 等价串行；或停止 workflow 切回 SKILL.md 手动循环，无状态迁移 |

## Verification

1. 单元测试：`tasks card --task <id>` 输出与 `TaskService.instructions(task)` 逐字一致；对队列首任务与 `tasks next` 单卡输出一致；调用后 `task_metrics.attempts` 增 1；不改变任务状态（放在 `tests/test_session_grouping.py` 或 `tests/test_cli.py`）。
2. `EvalWorkflowSnippet`：用真实 `tasks list --status PENDING` 输出排练行解析（状态/类型/ID/输出路径）与波切分；对真实 `tasks card` 输出排练 `parseCard`。
3. 干跑一期（`concurrency: 6`）：记录任务循环墙钟与 `briefing.py stats --run` 的 token 总量，与 2026-10-16-115317 期（串行、约 1,730 万 token）对比；`validation.json` 必须零 failures。
4. 隔离核验：每个输出文件的 `_task` 绑定与其信封一致（`sync` 已强制），波内无交叉写入。
5. 幂等：波中途停止 → `mode: "resume"`，确认已完成任务不重做、未完成任务重发。
6. 回退演练：`concurrency: 1` 跑若干波，行为与现行串行脚本一致。

## Documentation impact

- `SKILL.md`「ZCode workflow 执行模式」：说明波次并行与 `concurrency` 参数；手动循环不变。
- `docs/operations/zcode-workflow-run.md`：发起参数表增 `concurrency`；进度观察改为"看板按波、子代理按任务命名"；故障处置增波内部分失败条目。
- `README.md`：若命令表列出 `tasks` 的 action，补 `tasks card --task <id>`。
- `docs/designs/2026-10-15-zcode-workflow-orchestration.md`：决策日志已登记本设计的指针；实现后把"不引入任务级并行"标注为被本设计取代。
- `docs/README.md`：Active designs 登记本文件。
- `tests/`：`tasks card` 的单元测试。
- `docs/contracts/`：无变更（不改门禁、Schema、发布契约）；实现时按 `code-review-invariants.md` 复核 `advance` 幂等与 run 隔离。

## Decision log

- 2026-10-18：用户在首跑后反馈"workflow 模式端到端时间特别长"；核实主因为提供方故障、结构性原因为串行任务循环，决定把任务级并行作为独立设计推进，**先出设计稿评审，再实现**（用户指示）。
- 2026-10-18：并行范围定为"同一 PENDING 队列前 K 个任务成波、一波一次 `advance`"，不改任务创建顺序与阶段门禁（依据：`list` 与 `next` 同序、同时 PENDING 的任务由创建时机保证独立、`advance` 对多输出幂等）。
- 2026-10-18：取卡途径倾向新增只读 `tasks card --task <id>`，理由是执行卡文本应单源于 `execution_envelope.py`（首跑已因脚本侧格式耦合发生过漂移）。待用户确认。
- 2026-10-18：看板粒度按波而非按任务，受 ZCode 单次运行 256 条 `report` 上限约束。
