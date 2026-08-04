# Technical Briefing Skill

面向公司内部领导和技术同事的可迁移技术情报Skill。它每天增量采集信息，每2～3天整理4～6条高价值内容，输出可追溯、去重、图文并茂的HTML邮件和Guizang风格视觉卡片。

## 主要能力

- 六个技术专题及窄检索方向；
- AI HOT、arXiv、RSS、GitHub Release和当前Agent开放搜索；
- AI/Agent/KVCache相关查询提高AI HOT采集优先级；
- 一手来源核验，AI HOT只作为发现源；
- URL、标题、正文与事件级去重；
- 每篇原文独立处理，防止上下文爆炸；
- 300～450字单条技术信息；
- 独立事实校验和人工审核；
- Guizang Material Illustration中心配图；
- Guizang Social Card卡片排版；
- 个人“技术侦察员”视觉IP；
- agently-cli邮件发送、SMTP备用发送、归档和断点恢复。

## 快速开始

```bash
cd technical-briefing-skill
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -e .

python briefing.py setup
python briefing.py setup --vendor --node
python briefing.py doctor
```

运行不联网的完整样例：

```bash
python briefing.py demo
```

样例输出位于：

```text
workspace/runs/demo-*/
```

真实运行：

```bash
python briefing.py run
python briefing.py tasks next
# 当前Agent按提示完成JSON任务
python briefing.py advance
# 重复 tasks next / advance，直到 READY_FOR_RENDER
python briefing.py render --execute
python briefing.py validate
python briefing.py review --serve
# 在审核页保存即完成批准；无浏览器环境可用：
python briefing.py approve --all
python briefing.py send --confirm-send
```

默认使用本机已授权的 `agently-cli` 发送 HTML 邮件。第一次执行会向 Agently Mail 请求发送确认令牌并停止；用户确认后，再次执行同一命令才会真正发送。若需要使用旧的 SMTP 后端，设置 `EMAIL_BACKEND=smtp`。

## Agent如何处理任务

该Skill不调用固定模型API。Python脚本会生成任务文件，当前Agent负责：

1. 读取任务指定的Prompt；
2. 读取单个输入文件及必要的专题上下文；
3. 输出符合JSON Schema的结果；
4. 写到指定输出路径；
5. 运行`python briefing.py advance`。

因此同一仓库可以在Claude Code、Codex、Hermes等不同Agent中运行。

## AI HOT优先策略

`config/topics.yaml`为每个专题设置`aihot_priority`：

- `highest`：Agent语义加速；
- `high`：TPN/KVCache网络、跨域传输；
- `medium`：内存/DSA、DPU；
- `low`：光交换。

高优先级会增加AI HOT关键词查询数量和候选排序权重，但不会提高最终证据等级。AI HOT条目必须回到`links.original`指向的一手来源后才能成为重点条目。

## 配图策略

视觉路由顺序：

```text
论文/官方原图
→ 官方产品图
→ GitHub或产品截图
→ 精确程序化图表
→ Guizang材质机制图
→ 个人IP判断图
→ 纯文字卡
```

精确数字不得交给图像模型绘制。个人角色只用于判断、检查和栏目识别，不遮挡技术证据。

## 定时运行

```cron
30 7 * * * cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py collect
30 15 * * * cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py collect
0 9 * * 1,3,5 cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py prepare
```

定时任务只能触发确定性脚本。需要Agent推理的任务应由支持Skills/Automations的宿主继续执行，或在人工进入Agent后运行`resume`。

## 许可

本仓库自身代码采用MIT License。`vendor/`中的上游项目不会打包进仓库，需要安装时克隆。Guizang Social Card当前采用AGPL-3.0，修改、再分发或网络服务化前应单独审查其许可义务。
