---
name: technical-briefing-skill
description: Collect, verify, deduplicate, analyse, illustrate, format, review, and email recurring internal technical briefings. Use for 技术情报简报、技术信息收集、论文与博客筛选、Agent/AI/KVCache/DPU/DSA/TPN/跨域传输/光交换信息追踪、Guizang图文卡片、定期邮件简报、去重和断点恢复。
---

# Technical Briefing Skill

## 目标

把大量分散、重复、深浅不一的公开技术信息压缩为少量可信、可读、图文并茂，并能直接支持项目判断的内部技术简报。

默认受众是公司内部领导和技术同事。代码保留4～6条的紧凑模式；当前项目启用`expanded_v2`，每期最多展示14条核心解读，并可附最多4条明确标注的邻近动态，总量不超过18条。数量不足时必须少发，不得用旧消息或弱信息凑数。每2～3天发送一次，不强制覆盖全部专题。

## 核心架构

- Python负责确定性工作：采集、过滤、去重、状态、预算、渲染、邮件和归档。邮件默认通过本机已授权的`agently-cli`发送，SMTP仅作为显式备用后端。
- 当前Agent负责智能工作：批量相关性、事实抽取、单条写作、事实校验、综合判断和视觉路由。
- 重点专题走深度通道；AI Infra、Agent生态、KVCache生态、存储与介质等广度信息走Radar通道，默认不读取全文。
- 不得在Python中绑定某家模型API。
- 不得依赖聊天上下文记住历史；所有状态写入SQLite和`workspace/runs/`。
- Skill本身不产生定时触发；由Cron或宿主Agent任务系统调用CLI。

## 首次使用

1. 在Skill根目录运行：

   ```bash
   python briefing.py setup
   python briefing.py setup --vendor --node
   python briefing.py doctor
   ```

2. 用户需要个人形象时，请其提供或放置经过确认的参考照片：

   ```text
   assets/persona/reference.jpg
   ```

   没有参考照片时，不得声称还原本人面部，只能使用通用低细节技术侦察员。

3. 先运行离线样例：

   ```bash
   python briefing.py demo
   ```

## 正常运行

### 第一步：启动或继续

新一轮：

```bash
python briefing.py run
```

继续上一轮：

```bash
python briefing.py resume --run latest
```

### 第二步：处理Agent任务

运行：

```bash
python briefing.py tasks next --run latest
```

严格按命令输出的五步执行：

1. 读取指定Prompt；
2. 读取指定输入JSON；
3. 只读取输入中引用的专题判断卡和单篇文档/分块；
4. 输出符合指定Schema的JSON；
5. 写入指定输出路径，然后执行`python briefing.py advance --run latest`。

重复直到运行阶段为`READY_FOR_RENDER`。

### 第三步：渲染与审核

```bash
python briefing.py render --execute
python briefing.py validate
python briefing.py review --serve
```

必须先审核再发送。第一版不得自动发送。

### 第四步：发送

完成审核、修复所有FAIL后：

```bash
python briefing.py approve --all   # 仅在已人工确认全部条目时使用
python briefing.py send --confirm-send
```

没有`--confirm-send`时必须拒绝发送。使用默认`agently-cli`时，第一次带`--confirm-send`的调用只请求发送确认令牌并停止；将摘要展示给用户，等待用户确认后，再次运行同一命令完成发送。令牌保存在当前运行目录的被忽略文件中，不能提交到仓库。

如果需要使用SMTP备用后端，先设置`EMAIL_BACKEND=smtp`，再按同一人工审核和`--confirm-send`门禁发送。

## 上下文与成本硬规则

1. 禁止一次加载全部搜索结果。
2. 规则过滤前，Agent不读取全文。
3. 模糊相关性候选按专题批量处理，每批最多12条；输出必须对每个输入候选返回且只返回一条结果。
4. 只有已解析、非`discovery_only`的A级原始来源才能进入深度通道；B/C级和聚合线索进入Radar并继续用于发现原始来源。
5. 开放Web搜索只补充没有A级原始来源覆盖的重点方向，默认每期最多4次。
6. 全文事实抽取默认每期最多10条、单专题最多3条；超出预算的候选保留为`DEFERRED_BUDGET`，不得删除。
7. 全文分析每次只处理一篇来源，长论文按章节或输入中已生成的chunk处理。
8. 完成事实抽取后，后续任务只读取结构化facts，不再读取全文。
9. 最终综合判断只读取核心解读，不读取观察池和热点Radar。
10. 不要为了“记住上次推送”使用对话记忆；查询SQLite和事件历史。

成本配置位于`config/settings.yaml`的`efficiency`段。可执行：

```bash
python scripts/estimate_efficiency.py
```

查看代表性Agent任务数量估算。该结果不等同于实际Token账单，正式运行仍需检查关键事件召回率、人工修改量、端到端耗时和订阅额度。

## 新鲜度硬门槛

- 核心解读默认只接受原始发布时间在本期日期前3天内的信息；
- 邻近AI Infra动态默认只接受7天内的信息；
- 超过14天或无法确认原始发布日期的内容不得进入日常选刊；
- 搜索发现时间和抓取时间不得代替原始发布日期；
- 旧事件只有存在明确`incremental_update`及新增内容时才允许重新推送；
- 新鲜度门槛必须在评分和条数目标之前执行。

## 信息源规则

### AI HOT

AI HOT对以下方向提高优先级：

- Agent语义加速；
- Coding Agent、CodeGraph、仓库索引和工具链；
- KVCache、Prefill/Decode、LLM Serving和Token性能网络；
- 跨域KVCache和Agent Cache。

但AI HOT永远是发现源：

```text
AI HOT候选
→ links.original
→ 原始论文/官方博客/仓库
→ 事实抽取
```

不得把AI HOT的AI摘要直接当作技术证据。

### Follow Builders与YeeKal AI Daily

Follow Builders用于发现Builder观点、工程实践、访谈和官方博客线索；YeeKal AI Daily用于发现日报中的外部技术文章、项目和社区讨论。两者均保持B级、`discovery_only`，必须回到A级原始论文、官方文档、官方博客或项目仓库后才能进入重点信息。YeeKal日报日期只表示发现时间，不得冒充外部原始发布日期。

处理`item_writing`和`issue_synthesis`任务时，先根据结构化事实写初稿，再调用`$human-writing`调整自然中文，最后调用`$humanizer`审查机械AI句式。两个Skill都不得增加事实、数字、因果关系或来源。`rebuild-existing`重选条目后必须重新完成`issue_synthesis`，不得自动拼接条目摘要。

本地未安装润色Skills时执行：

```bash
npx skills add https://github.com/KKKKhazix/human-writing --global --agent codex
npx skills add https://github.com/blader/humanizer --global --agent codex
```

### 来源等级

- A：原始论文、官方文档、官方博客、原项目仓库、正式会议页。
- B：高质量聚合、专家分析、作者访谈、独立实践博客。
- C：媒体、自媒体、社区和社交平台线索。

重点信息至少需要一个已解析A级来源。

## 专题与横向Radar

深度专题包括：

1. 状态感知网络、阿里云Token Performance Network；
2. 内存语义、CXL、Intel DSA/IAA卸载；
3. DPU/SmartNIC/IPU随路卸载；
4. Agent语义加速，包括CodeGraph、Read/Grep/Glob、上下文构建和工具执行链；
5. KVCache、Agent Cache和记忆的跨域传输；
6. AI/GPU集群光交换网络。

横向Radar保持以下四类召回：

- AI Infra：LLM Serving、推理引擎、GPU集群、集合通信、编译器、Kernel、分布式训练、可观测性和故障恢复；
- Agent生态：MCP、Computer Use、Browser Agent、Agent Memory、多Agent和开发工具；
- KVCache生态：Prefix Cache、量化、分层、路由、持久化以及LMCache、vLLM、SGLang等项目动态；
- 存储与介质：HBM、CXL内存、Persistent Memory、NVMe SSD、NAND、QLC/TLC、ZNS、HDD和Computational Storage。

横向强信号只有在拥有A级原始来源、具体机制、量化证据或部署信息并与项目直接相关时，才允许晋升深度通道。具体方向和查询不得在Prompt中重新发明，读取`config/topics.yaml`。

## 单条信息规则

输出应让读者无需打开原文就能理解基本技术方案。内容包括：

- 标题；
- 类型、专题、日期和重要度；
- 两句话核心结论；
- 具体机制；
- 1～3个关键结果及条件；
- 适用边界；
- 对当前项目的启发；
- 3～5个关键词；
- 原始来源。

禁止：营销语言、无条件放大预印本结论、遗漏关键基线、把项目推断写成原文事实、以省略号或悬空标点结束字段。五个正文域合计必须为300～450字，渲染器不得截断事实检查后的正文。

## 跨期去重与热点Radar

- 事件身份依次使用arXiv基础ID（忽略`vN`）、DOI、GitHub仓库与Release、规范化原始URL；仅在没有稳定标识时使用语义事件名；
- 同一稳定身份的历史事件共享`last_pushed_at`，标题语言、版本号或摘要变化不得绕过去重；
- Radar独立记录推送历史，按原始URL和规范化标题跨期去重；
- Radar最多8条、每类最多2条，只允许AI系统、Agent、KVCache、芯片、内存、存储介质、网络和开发工具；
- 排除融资财报、股价、高管言论、政治政策、版权诉讼、游戏娱乐和消费应用；
- Radar只链接原始来源，内部发现源不得出现在邮件文字或链接中。

## 视觉规则

先运行视觉路由，不要直接生图。

优先级：原始图 > 官方图 > 真实截图 > 精确程序化图表 > 材质机制图 > 个人IP判断图 > 纯文字卡。

### Guizang Material Illustration

只负责卡片中的中心解释图。适合流程、机制、层级、对比和系统关系。图内只放3～5个短标签。需要时读取：

```text
vendor/guizang-material-illustration/SKILL.md
```

### Guizang Social Card

负责整张卡片和21:9头图。默认Swiss International + IKB Blue。使用上游种子模板，失败时使用本Skill内置fallback模板。发送前强制运行validator。

### 精确图表

任何百分比、时延、吞吐、P95、误差线和坐标必须由程序化图表生成。图像模型不得负责数值准确性。

### 个人视觉IP

个人角色为“技术侦察员”：黑色短发、细框眼镜、白色衬衫、略松的深蓝色条纹领带，平静认真。角色只承担筛选、检查、追踪和连接动作。

- 每期最多出现2次；
- 默认占画面15%，上限25%；
- 不得卖萌、抢镜或遮挡证据；
- 主要用于“本期判断”和最重要条目的项目启发；
- 不直接使用Ian Xiaohei的“小黑”角色。

## 失败降级

- 当前Agent不能生图：输出完整prompt并标记`waiting_for_image_generation`。
- 生图失败：原始图/截图 → 程序化图表 → 纯文字卡。
- 全文抓取失败：使用摘要做低置信Radar候选，但不得成为无A级来源的重点信息。
- 邮件失败：不写`last_pushed_at`，下次只重试发送。
- 任何配图失败都不能阻塞简报正文。

## 完成标准

发送前必须满足：

- 紧凑模式不超过6条；`expanded_v2`核心不超过14条、邻近动态不超过4条、总计不超过18条，单专题合计不超过3条；
- 每条至少一个A级来源；
- 所有数字可追溯；
- 无重复事件；
- 旧事件写明增量；
- 项目判断与来源事实分开；
- Guizang validator无FAIL；
- HTML正文可复制、链接可点击；
- 图片无法加载时正文仍完整；
- 已经经过人工审核。
