# 知识阶段接入每期发送之后（逐期执行，回填降级为恢复路径）

- Status: implemented
- Created: 2026-10-26
- Last updated: 2026-10-26

## Problem and evidence

知识物化与 Candidate 发现有完整协议（`knowledge prepare/next/apply`、Schema、
apply 校验、manifest 门禁），但没有任何调度入口指向它：

- `SKILL.md` 的正常运行四步止于发送归档；
- ZCode workflow `briefing-run` 终止于 `READY_TO_SEND`；
- `scripts/install-cron.example` 只调度 `collect` 与 `prepare`；
- 完成标准只覆盖发送前。

唯一入口是 `docs/operations/knowledge-freshness.md` 的"积压回填"，靠
manifest 水位发现欠账。结果是知识阶段持续滞后、定期批量补：09-20 补 3 期
（6a6832b）、10-15 补 5 期 09-24～10-14（ca04880）、10-21 补 2 期
（51135d9）。批量模式还催生了 workspace/ 下四个未追踪 helper 脚本（同日
已随 0aa8365 移入 `scripts/` 并文档化）。

直接证据：2026-10-23 期归档三天后知识阶段未开始，
`knowledge manifest validate` 报三项错误（graph 过期、snapshot 不匹配、缺
`issue-diffs/2026-10-23.json`）。

## Goals and non-goals

目标：

- 每期发送归档后，同一会话内立即为该期执行知识阶段；正常情况下
  `publication_state` 始终为 `knowledge_complete`，首页不长期显示 pending。
- 积压回填流程保留为恢复路径，不再是常态执行方式。

非目标：

- 不改任何 Python 代码、CLI、Schema、任务边界或 apply 校验。
- 不改 `briefing-run` workflow 编排（终止于 `READY_TO_SEND` 不变）。
- 不把四个批量 helper 提升为正式 CLI；不做 cron 自动化——知识任务是
  Agent 语义任务，无法无人值守完成。

## Constraints and invariants

- 知识阶段只读已发布归档（`archive/index.json` 列出的 `issue.json` 与
  `papers.json`），不读候选池、全文或 reader。
- 任务绑定包含前一期 apply 后的 Roadmap digest：逐期顺序执行，下一期在
  本期全部 apply 之后重新 `prepare`；旧期 diff 已固化，不重建。
- `apply` 是唯一写入门禁；失败修复原任务重试，不跳期、不手改 manifest。
- Pages 门禁语义不变：`archive_only`/`analysis_pending` 允许上线并诚实
  显示 pending。
- 归档推送（第一次部署，pending 状态）与知识完成后的 `knowledge/` 推送
  （第二次部署，complete）是两次独立部署，均由既有 Pages workflow 处理。
- 测试套件把已提交仓库钉在完全物化状态（`test_knowledge_graph` 比对
  graph 水位、`test_knowledge_materialization` 钉住对象计数与 manifest
  完成态、`test_graph_surfaces.LENS_REPRO` 钉住镜头计数）。历次 backfill
  提交都同步更新了后两处计数；归档后未做知识阶段会让 `pytest -q` 变红
  （2026-10-23 当前即如此），只重建 graph/manifest 而不做任务无法恢复。

## Proposed design

`SKILL.md` 新增"第五步：知识物化与 Candidate 发现（发送归档后）"，作为
每期收尾：对刚归档的期次依次执行 `knowledge prepare` → 逐任务
`next`/`apply` → `candidates prepare` → 逐任务 `next`/`apply` →
`validate` → `graph build`/`validate` → `diff build` → `manifest
build`/`validate`，随后按 AGENTS.md 自动提交规则提交 `knowledge/` 并推送。
手动路径与 workflow 路径的第四步都在主会话执行，第五步同样始终在主会话
执行。README、architecture、knowledge-freshness、zcode-workflow-run 与
knowledge-materialization 契约同步更新执行时机。

## Compatibility and migration

- 既有积压（2026-10-23）用同一逐期流程补齐，无数据迁移。
- issue-diffs、manifest 状态机、任务目录结构全部不变。

## Failure, recovery, and rollback

- 单任务 apply 失败：修复输出后对同一任务重试，不产生半更新知识。
- 发送后中断：按 `knowledge-freshness.md` 的积压回填逐期补齐；
  `analysis_failed` 显式标记仍可用于保留现场。
- 回滚：本设计只改文档与运行次序，恢复旧次序即回滚，无状态迁移。

## Verification

- `pytest tests/test_env.py tests/test_external_skill_contract.py`；
  Codex skill-creator `quick_validate.py`；变更文档相对链接检查；
  `git diff --check`。本改动只改文档，全量 `pytest -q` 中
  `test_knowledge_graph::test_committed_repo_builds_in_memory_and_matches_the_published_graph`
  因 2026-10-23 未物化而在改动前后同样失败，与本改动无关。
- 验收：下一次执行（含当前欠账 2026-10-23）按第五步完成后
  `knowledge manifest validate` 通过、manifest 为 `knowledge_complete`，
  且 `pytest -q` 全绿。

## Documentation impact

- `SKILL.md`：新增第五步；workflow 节与完成标准同步。
- `README.md`：发送段落与运行模型。
- `docs/architecture.md`：Pipeline 与 Machine/reader layers 的执行时机。
- `docs/operations/knowledge-freshness.md`：常态路径与回填定位。
- `docs/operations/zcode-workflow-run.md`：编排边界。
- `docs/contracts/knowledge-materialization.md`：增量更新时机一句。
- `docs/README.md`：本文件索引。

## Decision log

- 2026-10-26：用户确认方向——知识阶段接进每期发送之后；四个批量 helper
  保留在 `scripts/` 并文档化适用场景，接受日后闲置。同日完成实现。
