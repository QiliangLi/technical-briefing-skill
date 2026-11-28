# 飞书群助手运维

本文描述群助手怎么启用、怎么启停、会话循环怎么跑、它怎么参与群里的讨论、
缺口怎么上报，以及出问题时怎么处置。字段与规则的权威定义见
`docs/contracts/group-assistant.md`，取舍的来龙去脉见
`docs/history/designs/2026-11-28-group-assistant-as-group-member.md`。

## 三个部分

- **常驻进程** `python briefing.py assistant serve`：以机器人身份经 lark-cli 收发
  消息，是唯一碰飞书的东西。有人点名且词法检索有把握时，它两秒内直接回复。
  群里每开始一段讨论，它十秒后看一眼，需要判断的排成任务文件。
- **宿主会话**：一个 ZCode 会话，靠 `assistant tasks wait` 被叫醒，按执行卡做
  判断：接话、审核想法、上报缺口，或者不说。
- **每周卡片** `feedback`：从 Idea 库挑至多三条发成带按钮的卡片，收集同事的判断。

进程只读已发布的记录（归档、读者卡片、Idea、Roadmap），不碰候选池、运行目录
和缓存。全部状态在被忽略的 `workspace/assistant/` 下，群聊原文不进仓库。

## 首次启用

```bash
python briefing.py assistant index build             # 已发布内容建索引
python briefing.py assistant chat add oc_xxx         # 群白名单，写在本地配置里
python briefing.py assistant report to ou_xxx        # 你的 open_id：缺口和异常私聊发给你
python briefing.py assistant status                  # self_check.ok 应为 true
```

前提是 lark-cli 1.0.100 或更新，并且已经以机器人身份登录。助手默认回答点名，
也默认参与讨论；已经在用的状态目录沿用它原来的模式，要手动打开：
`python briefing.py assistant mode proactive auto`。

把机器人拉进部门群之前，先在群里说明两件事：它会读取群里的全部消息；这些
内容会去掉名字后交给模型判断，讨论到而日报没覆盖的方向会私聊报给你。

## 启停

```bash
python briefing.py assistant serve --detach   # 独立进程，立刻返回；不依附任何会话
python briefing.py assistant stop
python briefing.py assistant status
```

- 进程独立于会话，日志在 `workspace/assistant/serve.log`。会话可以随时重开，
  监听不断。
- 同一台机器上第二个进程会拒绝启动，提示已在运行的 PID。
- 停止的顺序是先关每个消费子进程的 stdin，过 10 秒还没退再发 SIGTERM，最后
  `lark-cli event stop` 关事件总线。不要 `kill -9`：总线会留在后台，要手动关。
- 进程启动时读一次白名单，改了白名单要重启才生效。

## 会话循环

用一个专门的 ZCode 会话，不能是跑简报定时任务的那个。在这个仓库里新开会话，
说「运行群助手」即可：`AGENTS.md` 把这句话路由到 `SKILL.md` 的「飞书群助手
会话」。下面是它执行的内容。

1. 启动进程：`python briefing.py assistant serve --detach`，再运行
   `assistant status`，确认在跑、四个消费者都是 ready、自检通过。
2. 等待：把 `assistant tasks wait` 作为后台任务运行。它只在有语义任务时才返回，
   退出时会话被叫醒。要在后台跑，前台命令最多十分钟就会超时；不要加
   `--timeout` 轮询，那样空闲时也会消耗 token。
3. 执行：每张卡派一个子代理去做，主会话只记下结果。子代理读卡上列的提示词、
   Schema 和输入文件，按提示词写一个 JSON 对象到卡上的输出路径，再运行
   `assistant tasks apply --task <task_id>`。提示词允许时，子代理可以运行
   `assistant search --task <task_id> "<检索式>"` 自己再查，每个任务至多四次。
4. 全部 apply 后回到第 2 步。

主会话每轮只长几百 token，读输入和写输出的开销都在用完即弃的子代理里；这是
成本不随运行时间平方增长的原因。会话上下文仍然变长后，重开会话即可，进程不用动。

会话和它的子代理不调用 `lark-cli`，不发送任何消息，不改输入文件。apply 是
唯一的写入口，输出不过校验时任务直接作废，不要重试、不要手改输出。

### 它怎么参与讨论

- 一段讨论的第一条消息到达十秒后，进程看一眼并排一个判断任务，不管后面有
  没有人接着说；执行前到的消息并进同一个任务。同一个话题至少隔三十秒才会
  再排一个。
- 会话在四种做法里选一个：不说；接话，引一句讨论原话，带一到两条日报条目；
  某人提出自己的想法时做审核，列出最接近的 idea、支持的证据、边界和库里没有
  的方面；讨论有价值而日报和现有专题都没覆盖时，私聊报给你。
- 标题、日期、数字和链接由程序从日报里拼，会话只写接话。接话里的每个数字
  都必须能在被引的条目或讨论里找到，否则整个输出作废。
- 闲聊和行政事务应该选「不说」。校准提示词时先用 `observe` 模式：照样判断、
  只记不发，过几天用 `assistant review` 看它本来会说什么，再切回 `auto`。

## 缺口上报

- 群里讨论到日报没覆盖的方向时，机器人私聊发给你：讨论要点、参与人的真实
  姓名、最接近的现有专题或方向、建议新增的检索词和建议归入的位置。每条都按
  你在 `config/topics*.yaml` 里能直接改的字段来写。
- 每天至多三条私聊，其余只进台账。它只汇报，不碰日报的任何配置，专题和检索
  词改不改由你决定。
- `python briefing.py assistant report list` 列出，`report show <编号>` 看讨论
  原文，保留三十天。
- 主动发言一小时超过三十条、或进程出错退出，也走这个私聊告诉你一声。

## 新一期的提醒

新一期日报发布后，进程排一个提醒任务：这一期的条目和本期判断，对着群里最近
十四天的讨论。会话挑至多三条和你们的工作直接相关的，每条一句「对你们意味着
什么」，作为一条独立消息发进群里。没有相关的就不发。每期至多一次。

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

- 每次至多三张：本期状态有变化的排在只新增证据的前面，其次本期新建，最后至多
  一条四周没推过、没人回应的旧 idea。一周内推过的不再推。
- 两次推送至少隔七天，同一期不重发。发送必须有 `--confirm-send`。
- 卡片带四个按钮：值得投入验证、不看好、证据不足、已有人做过。表情只认 👍 和
  👎，飞书没有对应另外两档的表情。
- 卡片发到白名单里的第一个群。卡片话题里的讨论算锚定讨论，会带着那条 idea
  一起判断。

## 看状态

`assistant status` 输出六块：

| 字段 | 含义 |
| --- | --- |
| `service` | 是否在跑、PID、心跳距今的秒数、四个消费子进程的状态、补历史的最近结果、上次巡检的错误 |
| `policy` | 是否回答点名、参与模式、静音剩余秒数、私聊收件人 |
| `today` | 今天各去向的消息数、发出的回复数、决策数 |
| `outbox` / `tasks` | 待发、重试、失败、已发的条数；待执行、已采纳、过期的任务数和今天的叫醒次数 |
| `reports` | 各类报告的条数 |
| `self_check` | 索引是否与已发布内容一致，固定的问题是否仍能直接答出 |

进程没在跑或自检不过时退出码为 1。`assistant review` 列出它对每段讨论的判断，
包括选了「不说」的那些，可按做法过滤；`assistant stats` 给出去向、决策、发送、
检索和报告的计数。

## 故障处置

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| `consumers` 里某项是 `error`，`error.type` 为 `missing_scope` | 应用缺权限 | 在开发者后台开通，再 `stop` 和 `serve`；这类错误不重试 |
| 某项一直是 `restarting` 或 `starting` | lark-cli 没登录，或总线异常 | `lark-cli event status` 看；`lark-cli event stop` 后重启进程 |
| 进程退出后 `lark-cli event status` 仍显示 running | 进程被强杀 | `lark-cli event stop` |
| `service.tick_error` 有内容 | 一次巡检出错了，通常是读到了日报流程正在改写的文件 | 不用处理，下一次巡检成功会清掉；连续失败一分钟进程才退出 |
| 收到私聊说主动发言超过了三十条 | 熔断 | 多半是提示词出错在循环发言；`assistant mode proactive observe` 切到只记不发，用 `review` 找原因 |
| `self_check.problems` 提示索引过期 | 归档或知识更新了 | `assistant index build`；运行中的进程每小时自查并重建 |
| `outbox` 里有 `retry` 或 `failed` | 发送失败，`last_error` 有原因 | 网络问题会自己重试五次；权限问题同第一行 |
| `outbox` 里有 `gone` | 要回复的消息已删除 | 不用处理，不会重发 |
| `tasks` 里 `contribute` 大量过期 | 没有会话在跑，或会话跟不上 | 看会话是否挂着 `tasks wait`；点名提问不受影响 |
| 点名了但不回答 | 回答被关了，群不在白名单，或消息是半小时前的旧消息 | `assistant status` 看 `policy` 和 `chats` |
| 接话里的事实说得不对 | 会话写的接话失实，程序只校验数字和引用 | 对那条回复点 👎；用 `review` 找到对应的决策，改提示词 |
| 实传脚本以你的身份发送失败 | 用户授权过期（七天） | `lark-cli auth login` 重新授权；只影响实传，不影响机器人 |

## 验证

```bash
python briefing.py assistant e2e                            # 回放：助手的全部测试，不联网
python briefing.py assistant e2e --live                     # 实传：对着测试群真实收发，约 2 分钟
python briefing.py assistant e2e --live --discussions        # 讨论模拟：替身会话，测管道
python briefing.py assistant e2e --live --discussions --session manual --session-wait 600   # 真实会话
python briefing.py assistant e2e --live --soak-minutes 720   # 长稳
```

实传只认测试群，换一个群就拒绝执行；它以你的身份发消息，都带 `[E2E]` 前缀，
不撤回，需要有效的用户授权。它在独立的状态目录上起进程，不碰真实台账。

`eval/assistant-discussions.json` 里是 13 段合成的群聊讨论，每段写明该不该
说话、好的回复必须出现和不能出现哪些词，以及日报库对它有没有相关条目。
讨论模拟跑完生成 `workspace/assistant-e2e/discussion-report.md`，逐个场景列出
讨论、回复和检查结果，留了人工评分的位置。自动检查只查引用和禁忌，接话是否
中肯要人来评。

2026-11-28 的结果：

- 实传八步全过。一段讨论开始后约十四秒被看到；observe 下只记不发；auto 下
  在话题里接话；点 👎 之后不再发言。
- 讨论模拟，替身会话（按规则取第一条候选，不做判断）：13 个过 6 个，每段
  约 20 秒得到回应。过的 6 个是第一条候选恰好相关的；没过的 7 个要么第一条
  候选不相干，要么是闲聊和行政被硬接了话。
- 讨论模拟，真实会话：13 个全过自动检查。六段接话、一个想法审核、两个缺口
  上报、闲聊和行政沉默。「把冷的 KV 换出显存」那段词法检索不到，会话自己改写
  检索式后找到了对的两篇。

需要如实说的两点：

- 自动检查查不出接话的失实。真实会话那一轮里有一条接话说「两篇都有数字」，
  而被引的三星那条明确写着「属于厂商趋势信号而非量化结果」。这种过头话只能
  靠人看 `review` 和点 👎 来纠。
- 从讨论开始到回复发出，替身约 20 秒；真实会话每多一道判断就多一到三分钟，
  取决于会话读输入、写输出的速度。
