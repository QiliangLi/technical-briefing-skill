# Technical Briefing Skill

面向公司内部领导和技术同事的可迁移技术情报Skill。它每天增量采集信息，每2～3天整理一组高价值内容，输出可追溯、去重、图文并茂的HTML邮件和Guizang风格视觉卡片。

## 主要能力

- 七个深度技术专题及窄检索方向，并保留AI Infra横向动态；
- AI芯片与加速器专题覆盖GPU/NPU/TPU/ASIC、Chiplet、先进封装、内存接口与软硬件协同；
- AI HOT、arXiv、RSS、GitHub Release、Follow Builders、YeeKal AI Daily和当前Agent开放搜索；
- 一手来源核验，AI HOT、Follow Builders和YeeKal只作为发现源；
- 60天滚动深度专题池，已推送内容跨期去重，未覆盖内容后续继续参与排序；
- 每专题最多4条完整深度解读，Top4之外的相关A级内容进入1～2句“专题补充”；
- 同项目、同方向多样性约束，避免单一项目的连续release占满专题；
- 相关性候选按专题批量做价值判断，关键词规则仅用于召回和路由；
- 缺口驱动的开放搜索；TPN单一项目不视为充分覆盖；
- 180～260字的紧凑深度条目；
- 横向Radar继续覆盖AI Infra、Agent、KVCache、存储与介质等近7天信号；
- 独立事实校验和人工审核；
- Guizang Material Illustration中心配图；
- Guizang Social Card卡片排版；
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
python briefing.py approve --all
python briefing.py send --confirm-send
```

默认使用本机已授权的 `agently-cli` 发送 HTML 邮件。第一次执行会请求发送确认令牌并停止；用户确认后，再次执行同一命令才会真正发送。若需要使用SMTP后端，设置 `EMAIL_BACKEND=smtp`。

## 三层输出与成本控制

```text
最近60天未推送A级候选
→ 批量价值判断
→ 多样性选择
   ├─ 每专题Top4：全文事实抽取 → 写作 → fact check → 深度解读
   └─ 其余相关A级：1～2句专题补充 + 原文链接

B/C级、discovery-only与横向信号
→ 近7天热点Radar
```

规则匹配分只负责“找得到”，不直接代表“值得深读”。A级候选由批量任务按项目相关性、技术实质、证据、可行动性和新鲜度评分；例行兼容、依赖升级、普通bug fix、文档/CI/build更新通常只进入专题补充。

全文事实抽取仍默认最多16条、单专题最多4条、同专题同项目最多1条；Top4之外的专题补充不再触发全文、单条写作和事实检查，因此能够扩充信息量而不线性放大Token消耗。

开放Web搜索只补充固定信源没有覆盖的重点方向，默认最多4次。TPN同一方向只有一个项目时仍视为覆盖不足，以主动寻找不同项目或不同机制的原始来源。

相关配置位于 `config/settings.yaml` 的 `efficiency` 段。可通过：

```bash
python scripts/estimate_efficiency.py
```

查看代表性Agent任务数量估算。估算值不等同于实际Codex Token账单，正式运行仍应比较关键事件召回率、人工修改量、实际耗时和订阅额度变化。

## 时间窗口

- 深度专题：最近60天滚动窗口；
- 横向热点Radar：最近7天；
- SQLite中60天内尚未推送的A级来源会在后续运行中继续参与候选排序；
- 已作为深度解读、专题补充或Radar发送的内容不会无变化重复出现；
- 新鲜度只占价值分的小部分，因此高价值的30～60天内容可以高于当天的低价值release。

## Agent如何处理任务

该Skill不调用固定模型API。Python脚本会生成任务文件，当前Agent负责：

1. 读取任务指定的Prompt；
2. 读取输入文件及必要的专题上下文；
3. 输出符合JSON Schema的结果；
4. 写到指定输出路径；
5. 运行`python briefing.py advance`。

相关候选使用 `relevance_batch` 任务，每个任务最多处理12条同专题候选；输出必须对每个输入候选返回且只返回一条结果，缺失、重复或未知ID都会被拒绝。

`item_writing` 和 `issue_synthesis` 会要求当前Agent先按结构化事实写初稿，再依次调用本地 `$human-writing` 与 `$humanizer`。这两个Skill只负责自然中文润色和AI句式审查，不得增加事实。

未安装时可在本机执行：

```bash
npx skills add https://github.com/KKKKhazix/human-writing --global --agent codex
npx skills add https://github.com/blader/humanizer --global --agent codex
```

## 专题配置

基础专题保存在 `config/topics.yaml`，AI芯片与加速器专题保存在 `config/topics-chip.yaml`，加载时合并成七个深度专题和一个AI Infra横向专题。每个专题的项目判断卡位于 `config/project-context/`。

`aihot_priority`只控制发现和候选排序，不改变最终证据等级。AI HOT条目必须回到`links.original`的一手来源后才能成为重点条目。

## 配图策略

```text
论文/官方原图
→ 官方产品图
→ GitHub或产品截图
→ 精确程序化图表
→ Guizang材质机制图
→ 个人IP判断图
→ 纯文字卡
```

精确数字不得交给图像模型绘制。

## 定时运行

```cron
30 7 * * * cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py collect
30 15 * * * cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py collect
0 9 * * 1,3,5 cd /path/to/technical-briefing-skill && .venv/bin/python briefing.py prepare
```

定时任务只能触发确定性脚本。需要Agent推理的任务应由支持Skills/Automations的宿主继续执行，或在人工进入Agent后运行`resume`。

## 许可

本仓库自身代码采用MIT License。`vendor/`中的上游项目不会打包进仓库，需要安装时克隆。Guizang Social Card当前采用AGPL-3.0，修改、再分发或网络服务化前应单独审查其许可义务。
