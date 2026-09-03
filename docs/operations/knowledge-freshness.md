# 知识新鲜度与发布门禁运维

本文描述长期知识与已发布归档之间的新鲜度诊断与恢复:`knowledge/manifest.json`
的四种发布状态、积压回填的逐期流程、`analysis_failed` 的恢复路径,以及
Pages 新鲜度门禁失败的排查。字段与命令的权威定义见
`docs/contracts/knowledge-materialization.md`。

## 状态与第一眼诊断

```bash
python3 briefing.py knowledge manifest validate   # 不一致会列出全部差异
cat knowledge/manifest.json
```

| 现象 | 含义 | 动作 |
| --- | --- | --- |
| `materialized_through_issue` 落后 `archive_head_issue` | 存在待分析期次 | 按"积压回填"流程逐期补齐 |
| `publication_state: archive_only` 且有 `pending_issues` | 归档已发布但任务未准备 | 对最旧待分析期次执行 `knowledge prepare` |
| `publication_state: analysis_pending` | 任务已准备/执行中 | 用 `knowledge status --issue <date>` 查看进度 |
| `publication_state: analysis_failed` | 运维显式标记的失败 | 按"analysis_failed 恢复"处理 |
| `candidate_analysis_state: archive_only` | 有期次尚未做 Candidate 发现 | 对最旧 `candidate_pending_issues` 执行 `knowledge candidates prepare` |
| `candidate_analysis_state: analysis_pending` | Candidate Direct/Synthesis 任务未全部 apply | 用 `knowledge candidates status --issue <date>` 查看进度 |

首页与图谱页面读取同一 manifest:状态未追平时首页展示“本期已归档,长期判断
正在分析”等诚实提示,不会用旧 Roadmap 摘要冒充本期变化。

## 积压回填(逐期)

任务绑定包含前一期次 apply 后的 Roadmap digest,因此回填必须按期次顺序执行,
且下一期必须在本期全部 apply 之后重新 `prepare`:

```bash
python3 briefing.py knowledge prepare --issue <oldest-pending>
python3 briefing.py knowledge next --issue <issue>        # 逐任务执行
python3 briefing.py knowledge apply --task <task_id>
python3 briefing.py knowledge status --issue <issue>      # 全部 applied 后继续
python3 briefing.py knowledge candidates prepare --issue <issue>
python3 briefing.py knowledge candidates next --issue <issue> # 每个 Direct/Synthesis 任务
python3 briefing.py knowledge candidates apply --task <task_id>
python3 briefing.py knowledge candidates status --issue <issue>
python3 briefing.py knowledge validate
python3 briefing.py knowledge graph build && python3 briefing.py knowledge graph validate
python3 briefing.py knowledge diff build --issue <issue>
python3 briefing.py knowledge manifest build && python3 briefing.py knowledge manifest validate
```

注意:

- 每期 diff 必须在该期 apply 完成后立即构建;旧期 diff 已按当时状态固化,
  不要在后续期次 apply 后重建(判断字段以构建当时的 Roadmap 状态为准)。
- 单个 Topic 失败不会发布半更新知识:apply 校验失败时不产生 application,
  修复输出后对同一任务重试即可。
- Candidate 失败同样修复原任务重试；不要跳过最旧 Candidate pending 期次。
  apply 使用 `knowledge/.candidate-transaction.json` 恢复未提交的多文件更新，
  journal 不应手工删除。
- 全部待分析期次完成后,manifest 才会变为 `knowledge_complete`;
  Pages 门禁允许中间状态上线,但首页只显示 pending 进度。

## analysis_failed 恢复

`analysis_failed` 由运维显式写入,用于保留现场(上一份 `knowledge_complete`
snapshot 继续可读,Archive 不受影响):

```bash
python3 briefing.py knowledge manifest build --state analysis_failed \
  --note "2026-08-29 tpn 任务语义校验失败,等待修复"

# 正式知识可继续完整发布，但 Candidate 发现失败时单独标记
python3 briefing.py knowledge manifest build --candidate-state analysis_failed \
  --note "Candidate 任务失败，保留上一份 Candidate/Idea 快照"
```

恢复步骤:修复任务输出 → 对同一任务重新 `apply` → 按“积压回填”完成
graph/diff/manifest 链 → 状态自然回到 `knowledge_complete`。不要直接把
manifest 改回 `knowledge_complete`;`manifest validate` 会重算图谱 digest
并交叉核对水位与 diff,任何不一致都会失败。

## 归档之后的调度缺口

manifest 的 `pending_issues` 只说明“已发布归档尚未被知识分析”。如果问题
是**最新归档本身落后**(例如期望某天应产生新日报但没有),这是生产调度/日报
生成缺口,不是 Pages 同步问题:

1. 检查运行主机: `workspace/runs/` 下最新的 run 目录时间;
2. 检查 crontab 是否安装(`crontab -l`;仓库只有
   `scripts/install-cron.example`,不会自动安装);
3. 检查采集与发送日志(`workspace/logs/`)确认失败阶段。

## Pages 新鲜度门禁失败排查

Pages 工作流在 graph 门禁之后执行
`knowledge manifest build → knowledge manifest validate → knowledge diff validate`。
常见失败与处理:

- `snapshot_id must match the current graph build` / `graph.json is stale`:
  graph 与知识输入不同步,重跑 `knowledge graph build` 后重新构建 manifest;
- `knowledge_complete is not allowed while pending issues remain` /
  `materialized_through_issue` 不符:分析未完成,先完成回填,或让 manifest
  如实输出 pending 状态;
- `knowledge_complete requires knowledge/issue-diffs/<head>.json` 或
  `status must be complete`:head 期次投影缺失或为 partial,补跑该期
  `diff build`;
- 判断字段模板句报错(`must not reuse seed template copy`):某期 Roadmap
  summary 仍是 seed 模板,按 prompt 要求改写为可行动判断后重新 apply/构建。

回滚:manifest 与 issue diff 都是附加的可重建投影,回滚前端或知识代码不需要
回滚 Archive;删除这两类文件后按上文命令重建即可。

## 线上/仓库联合发布检查

发布完成不等于线上生效。部署后必须访问页面本身(而不是只看构建状态):

1. 三个图谱透镜路由(结构/演化/编辑判断,带 `topic` 与 `range=recent3`)的
   状态条摘要与本地 `knowledge/graph.json` 构建结果一致;
2. 首页水位显示 `knowledge_complete`,且 `archive_head_issue` 与
   `materialized_through_issue` 相同;
3. 页面首屏不再出现旧的“构建输入摘要”卡片(应为折叠的“技术信息”);
4. 页面静态资源版本参数包含当前布局模块(`knowledge-layout.js`);
5. 线上知识水位落后仓库时,按“积压回填”流程补齐后再部署,不要用旧站点
   状态反推本地实现是否正确。
