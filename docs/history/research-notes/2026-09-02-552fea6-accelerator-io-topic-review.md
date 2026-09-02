# `552fea6` 加速器直连 I/O 与存储数据路径专题实现评审

- 评审日期：2026-09-02
- 评审模式：task
- 目标提交：`552fea655b0b510d029e6166d5614fdaab13f028`
- 评审范围：`552fea6^..552fea6`
- 目标分支：`main`
- 提交标题：`feat: add accelerator I/O datapath topic`
- 结论：**PASS**（附 2 项低严重度跟进项，不构成阻塞）

## 总体判断

该提交按已归档设计（`docs/history/designs/2026-09-02-accelerator-io-datapath-topic.md`，状态 `implemented`）完整落地了第九个深度专题 `accelerator_io_datapath`：

- **专题接入完整**：`config/topics-io.yaml` 新增专题与四个 Direction；`briefing_skill/config.py` 加载扩展文件、判断卡路由并更新横向 Radar 描述兼容改写；`briefing_skill/deep_eligibility.py` 新增带 boundary 的 Deep 准入契约；`briefing_skill/discovery_stage.py` 新增厂商与学术 preferred domains；`config/sources.yaml` 逐源加入 boost/allowlist（`simon_willison` 有意不加，测试固化）；`config/project-context/accelerator-io-datapath.md` 判断卡与 `current_questions`、`valuable_evidence` 对齐。
- **容量同步一致**：`settings.yaml` 的 `max_fact_candidates_total`/`hard_cap` 与 `scoring.yaml` 的 `expanded_v2.core_max`/`observation_max`/`total_max` 五处全部从 32 改为 36，每专题 Top4 与 `topic_target=4` 保持不变；新增回归测试覆盖 9 专题 × 4 = 36 恰好达上限的场景。
- **领域逻辑去重**：`pipeline.py` 与 `quality_guard.py` 中三份按 Topic 硬编码的 preferred domains 收敛为 `discovery_stage._preferred_domains()` 单一来源；`quality_guard.py` 中被删除的硬编码列表与新函数逐项一致，重构行为保持。
- **不变量未回归**：未改动邮件确认/发送/归档/发布行为；`emailer.py` 仅在旧 run 无 item ID 的遗留回退启发式中增加新 Topic 的 token 线索；配置变更只对新 run 生效的边界规则已写入 `SKILL.md`；无状态迁移需求，运行隔离与幂等路径不受影响。
- **文档同步**：`SKILL.md`（专题清单、扩展文件位置、36 条安全上限、配置变更边界规则）、`docs/contracts/project-insight-layer.md`（专题覆盖数与 Deep budget）均已更新；当前文档无残留"八个深度专题"或 32 上限表述（`config.py:67-70` 的三处 replace 是有意保留的旧文案兼容改写）。

完整测试套件 554 项全部通过，与设计文档记录一致。

## Findings

### 1. 低：Deep 选择器兜底上限 32 未随九专题兜底集同步改为 36

证据：`briefing_skill/topic_local_deep.py:64` 与 `briefing_skill/topic_local_deep.py:109` 的兜底默认仍为 `max_fact_candidates_hard_cap`/`max_fact_candidates_total` 缺省 32。同一提交已把另外两处兜底升级为九专题：`briefing_skill/efficiency.py:12-16`（`DEFAULT_DEEP_TOPICS`，经 `deep_selection_guard.py:19` 生效）和 `briefing_skill/quality_guard.py:135-148` 的内联九专题元组。

触发条件：仅当 `efficiency` 配置同时缺失 `deep_topics`、`max_fact_candidates_hard_cap`、`max_fact_candidates_total` 三组键（例如 settings.yaml 被裁剪或测试注入不完整 settings）时触发。随仓库发布的 `config/settings.yaml` 三组键齐全，默认路径不经过该兜底。

影响：兜底路径内部自相矛盾——九专题 × 每专题 4 = 36 超过兜底 cap 32，`select_topic_local_deep_budget` 在 `topic_local_deep.py:88-92` 抛出 `RuntimeError`。失败方式是响亮的 fail closed（符合设计的"不得静默饿死专题"不变量），不会静默截断或跨 run 泄漏，因此仅为潜在配置下的不一致，非当前缺陷。

建议：把两处兜底 32 改为 36；顺带可让 `quality_guard.py:135-148` 直接复用 `DEFAULT_DEEP_TOPICS`，消除下次新增专题需要改两处兜底元组的重复。

### 2. 低：设计验证清单承诺的 hard-cap fail-closed 场景没有测试

证据：设计文档 Verification 一节明确要求"若配置错误导致十个 Topic 都产生 Top4，选择必须因超过 hard cap 而 fail closed，不能静默饿死某个 Topic"。`tests/test_topic_local_deep.py:66` 新增的 `test_nine_topics_can_each_keep_four_candidates_under_the_36_hard_cap` 只覆盖 36 恰好达上限的 happy path；在 `tests/` 全量 grep 中没有任何 `pytest.raises` 断言 `topic_local_deep.py:88-92` 的越界 `RuntimeError`。

触发条件：未来调整 `per_topic_max`、专题数量或 hard cap 时引入容量不一致。

影响：fail-closed 分支当前无回归保护；若后续重构放宽该 `raise`，不会有测试报警。

建议：补一个小型单元测试——10 个 Topic × 4 行、cap 36，断言抛出 `RuntimeError` 且错误信息包含 `max_fact_candidates_hard_cap`。

## 备注（不构成正式 Findings）

- `briefing_skill/pipeline.py:66` 把 `from .discovery_stage import _preferred_domains` 放在 for 循环体内，每次迭代重复执行 import 语句（模块缓存后无实际开销）；移到循环外更清晰。
- `_preferred_domains` 是下划线私有命名，但已被 `pipeline.py`、`quality_guard.py` 和测试跨模块导入；既然它是搜索域路由的单一事实来源，可考虑改为公开命名。
- `briefing_skill/emailer.py:306-322` 遗留 judgement 引用回退的 `topic_cues` 为新 Topic 补了线索，但 `ai_chip_accelerator` 与 `storage_media` 此前就未补——这是遗留启发式本就存在的覆盖不一致，且新 Topic 不会出现在旧 run 数据中，无实际影响。
- `docs/discussions/ChatGPT-完善IO直通专题-20260902-2315.md` 为公开 ChatGPT 对话导出，已扫描确认不含密钥、令牌或私密信息。

## 已执行的验证

```text
.venv/bin/python -m pytest tests/ -q        -> 554 passed in 119.59s
.venv/bin/python -m compileall briefing_skill -> ok
.venv/bin/python briefing.py --help         -> CLI 启动正常
git show --check 552fea6                    -> 无空白错误
```

人工核对：

- `config/settings.yaml` `deep_topics` 共 9 项，含 `accelerator_io_datapath`；`config/scoring.yaml` `expanded_v2` 五个容量值（36/36/36/4/4）与 SKILL.md 声明一致。
- 当前代码与文档（`briefing_skill/`、`config/`、`docs/contracts/`、`docs/operations/`、`SKILL.md`、`prompts/`）中除 Finding 1 的兜底默认值和 `config.py` 有意保留的兼容改写外，无残留 32 上限或八专题硬编码；`docs/architecture.md` 未陈述固定专题数，无需改动（与设计文档声明一致）。
- `_preferred_domains` 重构行为保持：`quality_guard.py` 删除的三组硬编码域列表与新函数逐项一致；`pipeline.py` 初始搜索任务在此前 `agent_acceleration`/`optical_network` 之外，现在也会为 `ai_chip_accelerator` 与 `accelerator_io_datapath` 附加 preferred domains——有意的覆盖扩展，风险低且有测试固定。
- 专题顺序 `storage_media < accelerator_io_datapath < frontier_exploration < ai_infra_horizontal` 与 `_load_topics` 的插入逻辑一致，测试覆盖。
- 评审依据：`docs/contracts/code-review-invariants.md`（运行隔离、简报完整性、邮件资产、外部效果四节逐项核对，无回归）与 `docs/contracts/project-insight-layer.md`（专题覆盖与预算表述已同步）。
