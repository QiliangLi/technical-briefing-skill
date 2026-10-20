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
| 每波并行任务数（1–6，默认 6；1 即串行回退） | `concurrency: <N>` |

确认后在后台运行；主会话可继续其他工作，完成通知携带最终报告。

## 进度观察

- 阶段图：`初始化 briefing 运行 → 按波次并行执行任务 → 排版与发布前校验`。线上的节点是**阶段**（phase），整个波次循环是其中一个节点。
- 执行模式为**波次并行**：每波取 PENDING 队列前 `concurrency`（默认 6）个任务（该列表排序与 `tasks next` 一致，前缀即串行队列接下来要派发的任务），用只读 `tasks card --task <id>` 逐任务取 canonical 执行卡，K 个命名子代理并行执行，一波后统一 `advance`。任务输入在创建时冻结、同时 PENDING 的任务由创建时机保证互相独立，因此并行不改变任何任务的读入与质量门（内容影响分析见 `docs/history/designs/2026-10-18-briefing-run-parallel-waves.md`）。
- 子代理按**功能直述**命名：`功能·对象·第N波`。功能标签即该任务在流水线里做的事（见下表）；对象从任务 input.json 的人读字段提取（专题名、方向名、候选数、条目数等，截断 24 字）；INVALID 修复为 `第N波·修复输出·<任务ID前8位>`，发布校验修复为 `终审修复·第N次`。名字在运行内必须唯一（重名会直接终止运行），而波次号只区分波：同一波里同主题、同候选数的两个任务组标签完全相同，因此脚本用 `uniqueName()` 按名去重——首个占用保留原名，后续重复者追加 `·之N`（2026-10-21 新一期第 3 波两个「筛选候选·Agent语义加速·24篇候选」曾因此终止运行）。命名也是 `AmendWorkflow` 按名导入缓存的前提——匿名子代理的已完成 ask 永不复用；去重保留原名正是为了让已完成波次在修订续跑时仍命中缓存。

  | 功能标签 | 任务类型 | 读什么 → 产出什么 |
  | --- | --- | --- |
  | 开放搜索 | agent_web_search | 专题/方向的搜索式 → 开放网络新线索候选（标注来源与日期，出窗拒收） |
  | 筛选候选 | relevance_batch / relevance_review | 候选摘要+专题判断卡 → 逐候选相关性判定（direct/adjacent/tangential/off_topic）与去留 |
  | 提取事实 | fact_extraction | 文献全文/证据包 → 可引用的具体事实（数字、机制、对比），标注证据与缺口 |
  | 补齐证据 | fact_evidence_repair | evidence_gaps + 补充材料 → 清空或收窄缺口，不能解则保留并记录 |
  | 撰写条目 | item_writing_batch / item_writing | 同专题事实 → 情报条目（标题+正文，受字数与数字上限约束） |
  | 核查事实 | fact_check_batch / fact_check | 条目+原始事实 → 字段级纠错补丁（field/before/after/reason） |
  | 汇总判断 | issue_synthesis | 全期条目 → 各专题的本期技术增量判断 |
  | 读者润稿 | reader_projection | 全期条目 → 读者视角文案（human-writing 技能） |
  | 生成插画 | illustrated_publication | 专题条目 → 插画资产 + manifest + 发布提交 |
  | 修复输出 | （INVALID 修复子代理） | 未过校验的任务输出 → 最小定向修复后写回 |
  | 终审修复 | （validate 修复子代理） | validation.json FAIL 项 → 最小修复后重渲染 |
- 任务波次看板（artifact board）：**每波一张卡片**（受单次运行 256 条 report 上限约束，不按任务拆卡），实时在 执行中 → 完成（或 修复中 → 修复后完成）列间移动，卡面列出波内各任务的功能·对象标签；任务级"谁在做什么"由命名子代理在运行流中承担。
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
| 波内若干任务失败（日志"下一波将重发"） | 单任务 ask 失败/升级，未写输出，未拖垮兄弟任务 | 无需干预：任务仍为 PENDING，下一波自动重发；反复失败会在波次上限（40）处停止 |
| 波内全部取卡失败 | `tasks card --task <id>` 全部非零退出 | 主会话手动运行同命令看报错；多为 DB 锁或任务数据异常 |

## 回退演练

任意时刻停止 workflow，按 SKILL.md「正常运行」手动循环接手（`tasks next` → 执行 → `advance`）；单任务调试用 `tasks next-single`，按 ID 取卡用 `tasks card --task <id>`（只读，不改任务状态）。不并行也可用 `concurrency: 1` 以串行波次运行。状态只在 SQLite 与 `workspace/runs/` 中，无任何迁移。

## 维护注意

- 脚本中的解析函数与三处现网格式耦合：`execution_envelope.py` 的 canonical 执行卡（`tasks card` 输出；信封行正则须带 `m` 多行标志）、`tasks list` 的 `{status} {task_type} {id} -> {output_path}` 行、`cli.py` 的 advance JSON 与 `render --execute` 的 JSON（`"email"` 键为绝对路径）。改动这些输出时同步更新脚本，并用 `EvalWorkflowSnippet` 以真实样本重跑解析函数；`tasks card` 的行为有 `tests/test_tasks_card_cli.py` 守护。
- 有界上限（任务波次 40、INVALID 修复 2 次/任务、校验修复 3 轮）是编排自身的保险丝，与流水线配置无关。
- 所有 `agent()` 命名都必须经过 `uniqueName()`：子代理名在运行内重复会立即终止运行（errored），而标签取自任务输入的人读字段，同波内完全可能重复。新增命名子代理时沿用该助手，不要直接拼接字符串。
