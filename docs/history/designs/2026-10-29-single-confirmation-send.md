# 单次确认发送：agently 令牌信封自动校验

- Status: implemented
- Created: 2026-10-29
- Last updated: 2026-10-29

> Implemented and archived; durable rules live in `SKILL.md` (第四步),
> `docs/operations/agently-publication-transport.md`, and `config/settings.yaml`
> (`send.auto_confirm_envelope`). Tests: `tests/test_agently_transport.py`.

## Problem and evidence

当前发送需要用户两次人工确认：① 阅读预览页后确认发送内容；② 第一次
`send --confirm-send` 返回 agently-cli 的令牌摘要（收件人/主题/附件数）后，再确认一次信封。
第二次确认保护的信封字段全部可确定性推导，机器校验比人工扫一眼更可靠；
2026-10-29 期实际执行中第二次确认未提供任何人工才能发现的信息。

两次确认的成因是两个独立契约叠加：agently-cli 的两步令牌协议（外部工具，不可去除，
只能自动续接）与 SKILL.md 第四步「将摘要展示给用户，等待用户确认后再次运行」的
宿主 Agent 运行手册要求。

## Goals and non-goals

**Goals**

- 用户在预览页后只确认一次；`--confirm-send` 第一次调用在信封校验全绿时同次调用内
  自动携令牌完成发送。
- 信封校验全部确定性，进入 Python 并配测试：主题 == 本期 issue 生成的主题、
  收件人(cc/bcc) == 解析配置、附件数 == 1、收件人与上一期已发送收件人一致
  （防环境变量漂移发错人）。
- 任一校验失败或 agently 再次要求确认时，回退现行两步人工流程，行为与今天完全一致。

**Non-goals**

- 不移除 `--confirm-send` 门禁；不改变预览页人工阅读确认环节；不改动 agently-cli
  本身；不恢复 SMTP（保持 retired）。

## Constraints and invariants

- 无 `--confirm-send` 时必须拒绝发送（不变）。
- 发送前置检查（approval 状态、validation failures、HTML 公网图片、1MB 限制、
  request_key 令牌绑定、body_fallback 粘性降级）全部保持。
- 自动完成只在「已安装的 transport 路径」生效；安装前的 `emailer._agently_send`
  回退路径保持始终两步，由现有测试钉住。
- 令牌摘要字段缺失时该项不判错（agently 未回显则无从比对），字段存在但与期望不符
  即判错；收件人漂移检查独立于摘要，来自 `send_history` 最近一条 SENT。
- 自动续接失败（网络/安全过滤/再次要求确认）不删除 pending 文件，保留人工重跑路径。

## Proposed design

1. `EmailService` 新增两个纯方法（emailer.py）：
   - `_verify_send_envelope(summary, *, subject, recipients, cc, bcc) -> list[str]`：
     逐项比对，返回人类可读错误列表（缺失字段跳过，存在即比对）。
   - `_previous_sent_recipients() -> list[str]`：查询 `send_history` 最近一条 SENT 的
     recipients（逗号分隔）。
2. `agently_transport.agently_send` 在两条令牌返回路径（exit 8 与
   confirmation_required payload）persist pending 后：
   - `settings.send.auto_confirm_envelope`（默认 true）且信封校验（含收件人漂移）全绿
     → 写 `workspace/runs/<run_id>/agently-send-verified.json` 审计文件（gitignored），
     同次调用内以令牌重试；成功则走既有 sent 路径。
   - 重试再次要求确认或失败 → 抛 `AgentlyConfirmationRequired`（不删 pending），
     回退两步。
   - 校验失败 → `AgentlyConfirmationRequired` 附 `verification_errors`，CLI 输出中
     列出每条判错原因。
3. `AgentlyConfirmationRequired` 增加可选 `verification_errors` 参数，消息含判错列表；
   退出码与 CLI 处理不变。
4. `config/settings.yaml` 新增 `send.auto_confirm_envelope: true` 开关，可一键恢复
   始终两步。

## Compatibility and migration

- 无盘上状态迁移：pending 文件结构不变（新增审计文件只在自动完成成功前写）。
- 旧 run 的半完成 pending（已请求令牌未发送）在新代码下首次重跑会先走信封校验，
   全绿即自动完成，与人工第二次调用等价。
- `send.auto_confirm_envelope: false` 时行为与变更前逐字节一致。

## Failure, recovery, and rollback

- 信封判错 → 停止并列出原因，人工核对后重跑（仍两步）。
- 自动续接网络失败 → pending 保留，重跑 `send --confirm-send` 续用令牌；令牌若被
  agently 端消费则按现行 stale-token 语义重新请求。
- 回滚 = 配置开关置 false，无需代码回退。

## Verification

- `tests/test_agently_transport.py` 新增：自动完成成功路径（两次调用、第二次带令牌、
  审计文件落盘、send_history 记录一次）；收件人漂移停止；attachment_count 不符停止；
  开关关闭停止；exit-8 路径同样自动完成。
- `tests/test_emailer.py` 既有两步测试（未安装 transport 的回退路径）保持不变并通过。
- 全量 `pytest -q` 绿后按 change-governance 提交推送。

## Documentation impact

- `SKILL.md` 第四步：两步确认改为「单次确认 + 信封自动校验，异常回退两步」。
- `docs/operations/agently-publication-transport.md`：更新 two-step 表述。
- `config/settings.yaml`：新增 `send:` 段及注释。
- 本设计实现完成后标记 implemented 并移入 `docs/history/designs/`。

## Decision log

- 2026-10-29：用户提出「每次都要确认两次，能否优化成一次」。机制选项（代码级自动
  校验 / 仅改运行手册 / 维持现状）征询未获回复，按推荐采纳代码级：确定性校验进
  Python 符合本仓库「Python 负责确定性工作」的架构原则，且可用测试钉住。
- 2026-10-29：回退路径（未安装 transport 的 emailer._agently_send）保持始终两步，
  避免在非生产路径复制安全语义。
