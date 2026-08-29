# Technical Briefing Skill

这是一个面向公司内部技术判断的情报简报系统。它从公开来源持续采集材料，回到论文、官方文档和项目仓库核验事实，再生成可追溯的中文 HTML 简报。系统会保留跨期状态，避免重复推送，也能在中断后继续执行。

## 能做什么

- 按配置追踪 AI 基础设施、Agent、缓存、网络、芯片、存储等技术方向。
- 先做低成本召回和价值判断，再把有限的全文预算留给高价值一手来源。
- 为每条深度内容保存结构化事实、证据位置、适用边界和项目判断。
- 生成正文版与插画版邮件，校验后再发送并归档。
- 用 SQLite、运行目录和跨期缓存保证去重、恢复与审计。

详细运行约束以 [SKILL.md](SKILL.md) 为准。代码结构和状态边界见 [架构说明](docs/architecture.md)。

## 快速开始

需要 Python 3.10 及以上版本。Node.js 只在安装可选的页面与卡片依赖时使用。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

python briefing.py setup
python briefing.py setup --vendor --node
python briefing.py doctor
```

先跑离线样例，确认本地环境和渲染流程。

```bash
python briefing.py demo
```

## 运行一期简报

启动新一期。

```bash
python briefing.py run
```

恢复最近一期。

```bash
python briefing.py resume --run latest
```

随后按队列逐个处理 Agent 任务。

```bash
python briefing.py tasks next --run latest
# 按返回说明读取指定输入，写入指定 JSON 输出
python briefing.py advance --run latest
```

重复上面的任务循环，直到阶段变为 `READY_FOR_RENDER`。`tasks next` 有时会返回一组彼此隔离的事实抽取任务；如果执行环境无法可靠保持隔离，改用 `tasks next-single`。

完成后渲染并校验。

```bash
python briefing.py render --execute --run latest
python briefing.py validate --run latest
```

`validate` 是发布门。通过后状态进入 `READY_TO_SEND`。发送仍需人工确认。

```bash
python briefing.py send --confirm-send --run latest
```

默认邮件后端是本机已授权的 `agently-cli`。第一次调用只生成确认摘要和令牌，用户确认后再次运行同一命令才会真正发送。发送成功后，系统自动归档并尝试发布。发布失败时可以单独重试。

```bash
python briefing.py publish-archive --run <run_id>
```

## 运行模型

```text
公开来源与历史回填
→ 候选召回、去重和价值判断
→ 一手来源与 Evidence Pack
→ 结构化 facts 与必要的一次定向补证据
→ Machine Item 与 Evidence Gate
→ 高风险条目的 Fact Check
→ 当前 run 的 Reader Projection
→ 综合判断与整期插画
→ 两份 HTML、校验、发送和归档
```

Python 负责采集、状态、预算、缓存、校验、渲染和发送。Agent 只处理命令明确创建的语义任务。任何 Agent 任务都不能自行扩大输入范围。

## 常用检查

```bash
python briefing.py stats --run latest
python briefing.py backfill-status
python scripts/run_golden_eval.py
pytest -q
```

成本、数量和时间窗口都由 [config/settings.yaml](config/settings.yaml) 控制。README 不复制这些易变默认值，避免配置修改后出现两套说法。

## 仓库导航

| 路径 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent 执行入口与强约束 |
| [AGENTS.md](AGENTS.md) | 仓库维护、评审和兼容规则 |
| [docs/](docs/) | 当前架构、运行说明、契约与历史资料 |
| [config/](config/) | 专题、来源、评分、邮件与成本配置 |
| [prompts/](prompts/) | 运行时 Agent Prompt，含旧 run 的兼容文件 |
| [schemas/](schemas/) | Agent 输出和归档数据的 JSON Schema |
| [briefing_skill/](briefing_skill/) | Python 实现 |
| [tests/](tests/) 与 [eval/](eval/) | 自动化测试和质量回归集 |
| [archive/](archive/) | 已发布简报的公开归档 |
| [published-assets/](published-assets/) | 邮件可访问的已发布图片 |
| `workspace/` | 被忽略的本地运行状态、缓存和任务文件 |

文档索引见 [docs/README.md](docs/README.md)。历史评审和旧实施记录只用于追溯，不能当作当前运行说明。

## 许可

仓库代码使用 MIT License。可选的 `vendor/` 上游组件保留各自许可，安装、修改或分发前请同时查看 [NOTICE.md](NOTICE.md) 与上游条款。
