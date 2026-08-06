# Technical Briefing Skill

面向公司内部领导和技术同事的可迁移技术情报Skill。它每天增量采集信息，每2～3天整理4～6条高价值内容，输出可追溯、去重、图文并茂的HTML邮件和Guizang风格视觉卡片。

## 主要能力

- 六个技术专题及窄检索方向，并保留AI Infra横向动态；
- AI HOT、arXiv、RSS、GitHub Release、Follow Builders、YeeKal AI Daily和当前Agent开放搜索；
- AI/Agent/KVCache相关查询提高AI HOT采集优先级；
- 一手来源核验，AI HOT、Follow Builders和YeeKal只作为发现源；
- URL、标题、正文与事件级去重；
- 深度解读与横向Radar双通道，避免所有线索都进入全文分析；
- 模糊相关性候选按专题批量处理；
- 缺口驱动的开放搜索和按专题设置的深读预算；
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

## 低Token双通道

默认执行策略将候选分为两条路径：

```text
A级原始来源、高相关候选
→ 批量相关性判断或规则高置信通过
→ 每期最多10条进入全文事实抽取
→ 写作、事实检查和综合判断

AI Infra、Agent生态、KVCache生态、存储与介质线索
以及B/C级或discovery-only来源
→ 横向Radar
→ 默认不读取全文、不逐条写作和事实检查
```

开放Web搜索只补充固定信源没有覆盖的重点方向，默认最多4次。只有已解析、非discovery-only的A级原始来源才算“已覆盖”；二手线索不会阻止系统继续寻找原始材料。

相关配置位于 `config/settings.yaml` 的 `efficiency` 段。可通过下面的命令估算任务数量变化：

```bash
python scripts/estimate_efficiency.py
```

估算值表示计划生成的Agent任务数量，不等同于实际Codex Token账单。正式启用后仍应比较关键事件召回率、人工修改量、实际耗时和订阅额度变化。

## Agent如何处理任务

该Skill不调用固定模型API。Python脚本会生成任务文件，当前Agent负责：

1. 读取任务指定的Prompt；
2. 读取输入文件及必要的专题上下文；
3. 输出符合JSON Schema的结果；
4. 写到指定输出路径；
5. 运行`python briefing.py advance`。

模糊候选使用 `relevance_batch` 任务，每个任务最多处理12条同专题候选；输出必须对每个输入候选返回且只返回一条结果，缺失、重复或未知ID都会被拒绝。

`item_writing` 和 `issue_synthesis` 任务会要求当前Agent先按结构化事实写初稿，再依次调用本地 `$human-writing` 与 `$humanizer`。这两个Skill只负责自然中文润色和AI句式审查，不是Python运行时依赖，也不会被vendor到本仓库。

未安装时可在本机执行：

```bash
npx skills add https://github.com/KKKKhazix/human-writing --global --agent codex
npx skills add https://github.com/blader/humanizer --global --agent codex
```

Follow Builders只补充Builder观点、工程实践和访谈线索；YeeKal AI Daily只解析日报里的外部原始链接。两者均为B级发现源，不能独立支撑重点技术结论，YeeKal日报日期也不能替代外部原始发布日期。

对旧期次执行 `rebuild-existing --confirm-rebuild` 后，流程会停在 `AWAITING_ISSUE_SYNTHESIS`。必须完成新的结构化综合判断并执行`advance`，才能重新渲染、验证和审核邮件。

## AI HOT优先策略

`config/topics.yaml`为每个专题设置`aihot_priority`。高优先级会增加AI HOT候选排序权重，但不会提高最终证据等级。AI HOT条目必须回到`links.original`指向的一手来源后才能成为重点条目。

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
