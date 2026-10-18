# ZCode workflow 运行（briefing-run）

本文描述如何在 ZCode 宿主中以动态 workflow `briefing-run` 编排一期 briefing，如何观察进度、从中断中恢复、处置故障，以及如何回退到手动循环。设计与决策依据见 `../designs/2026-10-15-zcode-workflow-orchestration.md`。

## 边界

- 编排覆盖 SKILL.md 的第一～三步（初始化、Agent 任务循环、渲染与校验），**终止于 `READY_TO_SEND`**。
- 发送（第四步）不在编排内：人工阅读 `workspace/runs/<run_id>/email.html` 与 `validation.json` 后，在主会话执行 `send --confirm-send` 两步令牌确认；发送后的自动归档与推送流程不变。
- Python 侧与手动路径零差别：任务图、调度、Schema/语义校验、Evidence Gate、`validate` 发布门、cache 语义全部不变。

## 发起

workflow 只能由用户显式请求启动；在会话中说"用 workflow 跑一期 briefing"或直接要求运行 `briefing-run` 即可，宿主会以 `CreateWorkflow saved: briefing-run` 发起并展示脚本与 `world.run` 命令集供确认。

| 场景 | 参数 |
| --- | --- |
| 新一期（采集 + 全流程） | `mode: "run"` |
| 续跑最近一期（默认） | `mode: "resume"` |

确认后在后台运行；主会话可继续其他工作，完成通知携带最终报告。

## 进度观察

- 阶段图：`初始化 briefing 运行 → 编辑部逐个处理任务卡 → 排版与发布前校验`。线上的节点是**阶段**（phase），整个任务循环是其中一个节点，几十张执行卡不在线上拆成独立的点。
- 子代理按**编辑部角色**命名：`角色·对象·第N轮`。角色由任务类型映射（选题编辑/资料编辑/查证员/撰稿人/核查员/主编/润稿编辑/美术编辑/情报记者），对象从任务 input.json 的人读字段提取（专题名、方向名、候选数、条目数等，截断 24 字）；INVALID 修复为 `校对员·第N轮`，发布校验修复为 `终审校对·第N次`。运行流据此可读出"编辑部里谁在处理什么"；轮次号保证同一运行内唯一。命名也是 `AmendWorkflow` 按名导入缓存的前提——匿名子代理的已完成 ask 永不复用。
- 任务看板（artifact board）：每张执行卡一张卡片，实时在 执行中 → 完成（或 修复中 → 修复后完成）列间移动；这是任务级"一个任务一个点"的可视形态，resume 后看板原样重建。
- 每张执行卡的状态变化同步进入实时结果流；INVALID 修复与校验修复在 `log` 叙事线中可见。
- 成功结束时发布两个产物卡片：`email.html`（待人工确认发送）与 `validation.json`。
- 需要快照时用 `GetWorkflowRun`（其他会话的运行也可看）；本项目历史运行用 `ListWorkflowRuns`。不要轮询。

## 中断恢复与修订

| 情况 | 处置 |
| --- | --- |
| 进程退出/宿主重启/用户停止 | `ResumeWorkflowRun` journal 重放；或直接新起 `mode: "resume"` 的 workflow——盘上流水线状态幂等，已完成任务不会重做 |
| 编排脚本缺陷 | 编辑 `.zcode/workflows/briefing-run.dwf.ts` 后 `AmendWorkflow` 热缓存续跑，已完成的 ask 与 `world.run` 零成本重放（ask 缓存按子代理名 + 逐字相同指令匹配；2026-10-18 前的运行子代理匿名，对那些运行只能新起 `mode: "resume"`） |
| `world.run` 超时 errored | 任务循环里的 `advance` 已带 300s → 900s 的捕获重试；若仍超时，先在主会话手动 `advance` 解阻塞（通常是阶段切换重负载或 DB 锁竞争），再新起 `mode: "resume"` |
| provider 限流/网络抖动 | 运行时自动重试，无需干预；持续 20 分钟无进展会有一次提示通知，运行仍在等待 |

## 故障处置

| 现象 | 含义 | 下一步 |
| --- | --- | --- |
| 报告结论为"修复预算耗尽" | 某任务连续 INVALID 超过2次修复上限 | 主会话读该任务输入/输出手动修复，或 `tasks next-single` 接手 |
| 报告结论为"校验未通过（3轮）" | `validation.json` 存在未消除的 FAIL | 按 `validation.json` 手动修复后重跑 `render --execute` + `validate` |
| 报告结论为"队列已空但阶段为 …" | run 处于 `NO_EDITORIAL_ELIGIBLE` 等终态 | 按该阶段的人工流程处置 |
| 子代理升级提问（`dwfq-…`） | 任务执行中被证据/指令矛盾卡住 | 主会话回答（必要时先用 `AskUserQuestion` 征询用户），不要让子代理自行猜测 |

## 回退演练

任意时刻停止 workflow，按 SKILL.md「正常运行」手动循环接手（`tasks next` → 执行 → `advance`）；单任务调试用 `tasks next-single`。状态只在 SQLite 与 `workspace/runs/` 中，无任何迁移。

## 维护注意

- 脚本中的解析函数与 `execution_envelope.py` 的 canonical 执行卡格式（单卡首行 `Task <id> (<type>) — canonical execution contract vN`；组卡为编号 `Process only envelope .../tasks/<type>/<id>.execution.json` 行）、`cli.py` 的 advance/tasks-list 输出、`render --execute` 的 JSON（`"email"` 键为绝对路径）耦合；改动这些输出时同步更新脚本，并用 `EvalWorkflowSnippet` 以真实样本重跑解析函数。
- 有界上限（任务轮次 80、INVALID 修复 2 次/任务、校验修复 3 轮）是编排自身的保险丝，与流水线配置无关。
