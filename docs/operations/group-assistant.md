# 飞书群助手运维

本文描述群助手怎么启用、怎么启停、会话循环怎么跑、每周的 Idea 卡片怎么发，
以及出问题时怎么处置。字段与规则的权威定义见
`docs/contracts/group-assistant.md`，取舍的来龙去脉见
`docs/history/designs/2026-11-27-feishu-group-assistant.md`。

## 三个部分

- **常驻进程** `python briefing.py assistant serve`：以机器人身份经 lark-cli
  收发消息。有人点名且词法检索有把握时，它两秒内直接回复。其余的判断排成
  任务文件，等宿主会话来做。
- **宿主会话**：一个 ZCode 会话，靠 `assistant tasks wait` 被叫醒，按执行卡
  写输出，再 `assistant tasks apply`。它决定细查选哪条、群里的讨论值不值得接话。
- **每周卡片** `feedback`：从 Idea 库挑至多三条发成带按钮的卡片，收集同事的判断。

进程只读已发布的记录（归档、Idea、Roadmap），不碰候选池、运行目录和缓存。
全部状态在被忽略的 `workspace/assistant/` 下，群聊原文不进仓库。

## 首次启用

```bash
python briefing.py assistant index build             # 已发布内容建索引
python briefing.py assistant chat add oc_xxx         # 群白名单，写在本地配置里
python briefing.py assistant mode explicit on        # 回答点名它的消息
python briefing.py assistant status                  # self_check.ok 应为 true
```

前提是 lark-cli 1.0.100 或更新，并且已经以机器人身份登录。主动推荐默认关闭，
试用时先开 `observe`：照样研判、只记不发，用 `assistant review` 看影子决策，
觉得靠谱再切 `auto`。

把机器人拉进部门群之前，先在群里说明它会读取群里的全部消息。

## 启停

```bash
python briefing.py assistant serve     # 前台常驻；在会话里作为后台任务拉起
python briefing.py assistant stop
python briefing.py assistant status
```

- 同一台机器上第二个进程会拒绝启动，提示已在运行的 PID。
- 停止的顺序是先关每个消费子进程的 stdin，过 10 秒还没退再发 SIGTERM，最后
  `lark-cli event stop` 关事件总线。不要 `kill -9`：总线会留在后台，要手动关。
- 进程启动时读一次白名单，改了白名单要重启才生效。

## 会话循环

用一个专门的 ZCode 会话，不能是跑简报定时任务的那个，权限模式要不弹确认。

1. 拉起进程：把 `python briefing.py assistant serve` 作为后台任务运行。
2. 等待：`python briefing.py assistant tasks wait`。有语义任务时它才返回，
   一次带回攒批的全部执行卡，末尾写着下一步。
3. 执行：每张卡只读卡上列的提示词、Schema 和输入文件，把一个 JSON 对象写到
   卡上的输出路径，然后 `python briefing.py assistant tasks apply --task <task_id>`。
4. 全部 apply 后回到第 2 步。

会话不调用 lark-cli，不发送任何消息，不改输入文件。apply 是唯一的写入口，
输出不过校验时任务直接作废。上下文变长后重开会话。

2026-11-28 的实测：`tasks wait` 在三个文案任务攒够 60 秒后立刻返回；读三份
输入、写三份文案、逐个 apply 用了约三分钟；三个任务全部采纳，再 `wait` 在
超时后返回 `no_tasks`。整个过程会话没有调用 lark-cli。

## 每周的 Idea 卡片

知识阶段结束（SKILL.md 第五步）后，先重建索引，再按下面的顺序：

```bash
python briefing.py assistant index build
python briefing.py feedback prepare --issue <date>    # 选卡，给没有通俗文案的 idea 排文案任务
python briefing.py feedback prepare --issue <date>    # 会话执行完文案任务后再跑，看最终文案
python briefing.py feedback push --issue <date>       # 只预览，不发
python briefing.py feedback push --issue <date> --confirm-send
python briefing.py feedback collect                   # 对账：按飞书上的表情补齐台账
python briefing.py feedback status
```

- 每次至多三张：本期状态有变化的排在只新增证据的前面，其次本期新建，最后
  至多一条四周没推过、没人回应的旧 idea。一周内推过的不再推。
- 两次推送至少隔七天，同一期不重发。发送必须有 `--confirm-send`。
- 卡片带四个按钮：值得投入验证、不看好、证据不足、已有人做过。表情只认
  👍 和 👎，飞书没有对应另外两档的表情。
- 卡片发到白名单里的第一个群。话题里的讨论算锚定讨论，一条消息就成形。

## 看状态

`assistant status` 输出五块：

| 字段 | 含义 |
| --- | --- |
| `service` | 是否在跑、PID、心跳距今的秒数、四个消费子进程的状态、补历史的最近结果 |
| `policy` | 是否回答点名、主动推荐模式、规则开关、静音剩余秒数 |
| `today` | 今天各去向的消息数、发出的回复数、决策数 |
| `outbox` / `tasks` | 待发、重试、失败、已发的条数；待执行、已采纳、过期的任务数和今天的叫醒次数 |
| `self_check` | 索引是否与已发布内容一致，固定的问题是否仍能直接答出 |

进程没在跑或自检不过时退出码为 1。`assistant review` 列出影子期的研判决策，
按规则汇总；`assistant stats` 给出去向、决策、发送和反馈的计数。

## 故障处置

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| `consumers` 里某项是 `error`，`error.type` 为 `missing_scope` | 应用缺权限 | 在开发者后台开通，再 `stop` 和 `serve`；这类错误不重试 |
| 某项一直是 `restarting` 或 `starting` | lark-cli 没登录，或总线异常 | `lark-cli event status` 看；`lark-cli event stop` 后重启进程 |
| 进程退出后 `lark-cli event status` 仍显示 running | 进程被强杀 | `lark-cli event stop` |
| `self_check.problems` 提示索引过期 | 归档或知识更新了 | `assistant index build`；运行中的进程每小时自查并重建 |
| `outbox` 里有 `retry` 或 `failed` | 发送失败，`last_error` 有原因 | 网络问题会自己重试五次；权限问题同第一行 |
| `outbox` 里有 `gone` | 要回复的消息已删除 | 不用处理，不会重发 |
| `backfill` 里 `failed: true` | 读群历史失败 | 看 `error`；游标不动，下一轮重读同一段 |
| 点名了但不回答 | 回答没开，群不在白名单，或消息是半小时前的旧消息 | `assistant status` 看 `policy` 和 `chats` |
| 实传脚本以你的身份发送失败 | 用户授权过期（七天） | `lark-cli auth login` 重新授权；只影响实传，不影响机器人 |

## 验证

```bash
python briefing.py assistant e2e                          # 回放：助手的全部测试，不联网
python briefing.py assistant e2e --live                   # 实传：对着测试群真实收发，约 6.5 分钟
python briefing.py assistant e2e --live --soak-minutes 720  # 长稳：常驻并定时发探针
```

实传只认测试群，换一个群就拒绝执行；它以你的身份发消息，都带 `[E2E]` 前缀，
不撤回，需要有效的用户授权。它在独立的状态目录上起进程，不碰真实台账。
回放就是助手的测试套件，改了助手的代码就跑一遍。

2026-11-28 的实传结果：八步全过。点名到回复 0.2 秒，回复落在同一话题，每个
点名一条；进程被杀后重启没有重发；生僻的提问排了细查，采纳后回复；卡片下的
讨论在 observe 下只记不发，在 auto 下出一条推荐，点 👎 之后不再接话；最后的
去向计数与场景一致。

同一天跑过一次 15 分钟的短时长稳：三个探针各回了一条，30 次心跳采样的最大
间隔 5.7 秒，没有重试或失败的发送。过夜的长稳还没有跑。
