# Technical Briefing Skill

面向公司内部领导和技术同事的可迁移技术情报Skill。它每天增量采集信息，每2～3天整理一组高价值内容，输出可追溯、去重、图文并茂的HTML邮件和Guizang风格视觉卡片。

## 主要能力

- 七个深度技术专题及窄检索方向，并保留AI Infra横向动态；
- AI芯片与加速器专题覆盖GPU/NPU/TPU/ASIC、Chiplet、先进封装、内存接口与软硬件协同；
- AI HOT、arXiv、RSS、GitHub Release、Follow Builders、YeeKal AI Daily和当前Agent开放搜索；
- 一手来源核验，AI HOT、Follow Builders和YeeKal只作为发现源；
- 60天滚动深度专题池，已推送内容跨期去重，未覆盖内容后续继续参与排序；
- arXiv与配置的GitHub Release支持可恢复的60天外部历史回填；回填本身不创建Agent任务，并以小请求预算随日常采集逐步完成；
- 每专题最多4条完整深度解读，Top4之外的相关A级内容进入1～2句“专题补充”；
- 同项目、同方向多样性约束，避免单一项目的连续release占满专题；
- 同一GitHub项目在“专题补充”中的多条低优先级release自动聚合为一个Release Family，同时保留每个原文链接；
- 相关性候选按专题批量做价值判断，关键词规则仅用于召回和路由；
- 缺口驱动的开放搜索；TPN单一项目不视为充分覆盖；
- 深度事实抽取默认只向Agent暴露约18k字符的Evidence Pack，而不是完整140k字符全文；
- Evidence Pack缺少会改变结论解释的关键条件时，仅允许一轮最多9k字符的定向补证据，不重新打开完整全文；
- 相同来源指纹与抽取版本可跨期复用facts，缓存命中时不创建需要Agent执行的事实抽取任务；
- 深度条目写作和事实校验默认4条一批，同时保留逐条Schema、事实边界、PASS/FAIL和provenance；
- `stats`命令记录任务数、尝试次数、缓存命中和文本字符量等确定性成本代理；
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

首次安装、历史断档或希望主动补齐历史时，可以查看或加速外部回填：

```bash
python briefing.py backfill-status
python briefing.py backfill
python briefing.py backfill --max-requests 64
```

正常 `collect` 会在普通增量采集前，最多额外消耗4个外部历史请求推进未完成游标；`run` 内部本来就调用 `collect`，因此两种运行方式都只推进一次。回填的完整语义见 `docs/historical-backfill.md`。

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
外部60天历史回填（arXiv / GitHub Release，可恢复、零Agent任务）
→ 独立历史池
→ 每个正常run最多搬入120条未推送A级历史候选

最近60天未推送A级候选
→ 批量价值判断
→ 多样性选择
   ├─ 每专题Top4
   │    → 原始全文本地留存
   │    → Evidence Pack（默认≤18k字符）
   │    → facts cache查询
   │       ├─ 命中：直接生成FACTS_READY，不进入Agent任务队列
   │       └─ 未命中：事实抽取
   │            ├─ 证据足够：写入跨期facts cache
   │            └─ 存在材料性缺口：按明确术语从未曝光章节提取一次补充包（≤9k）
   │                 → facts修复 → 必要时写入跨期facts cache
   │    → 4条一批写作 → 4条一批fact check → 深度解读
   └─ 其余相关A级
        → 1～2句专题补充 + 原文链接
        → 同一GitHub项目多条低优先级更新合并为Release Family

B/C级、discovery-only与横向信号
→ 近7天热点Radar
```

历史回填和正常简报run刻意解耦：一次手工回填即使找到1000条历史记录，也只是先进入独立历史池；后续正常run仍受 `backlog_materialize_per_run: 120` 控制，再经过批量相关性判断和16条深读预算。因此“扩大历史覆盖”不会直接等价为“线性增加Agent任务”。

目前只有能确定性分页并判断时间边界的固定A级源被计入可验证历史覆盖：arXiv按专题方向向后翻页，GitHub Releases按仓库向后翻页。RSS Feed无法通用证明自己保留了完整60天，所以不会被标成“已完整回填”；其他暂不支持确定性历史分页的A级源会在 `backfill-status` 的 `unsupported_sources` 中明确列出。

规则匹配分只负责“找得到”，不直接代表“值得深读”。A级候选由批量任务按项目相关性、技术实质、证据、可行动性和新鲜度评分；例行兼容、依赖升级、普通bug fix、文档/CI/build更新通常只进入专题补充。

深度事实抽取仍默认最多16条、单专题最多4条、同专题同项目最多1条。原始抓取文本仍可保留到最多140k字符用于审计和必要时人工回看，但正常 `fact_extraction` 只读取确定性选择出的Evidence Pack。默认上限是18k字符，优先保留Architecture/Method/Evaluation/Results/Limitations及专题相关段落，并保留章节或页码定位信息。

如果首轮事实抽取明确发现一个会影响正确解释的关键缺口，例如具体baseline、硬件/工作负载条件、部署限制或原文明确的limitation，可以通过 `evidence_gaps` 请求一次定向补证据。Python只在首轮Evidence Pack未包含的章节中检索Agent给出的原文术语，生成默认最多9k字符的supplement；Agent修复facts时只读取结构化旧facts和这份supplement，不重读原18k Evidence Pack，也不打开140k原始全文。找不到明确术语时直接保持保守结论，不退化为通用全文搜索，也不会进行第二轮补读。

事实抽取结果会按稳定来源指纹与运行时抽取版本保存到本地跨期缓存。零抓取复用只面向具有强版本身份的来源，例如明确版本的arXiv、GitHub Release/Tag和DOI类稳定身份；普通可变网页不会为了省Token直接跳过重新验证。Prompt、Schema和Evidence Repair Prompt会参与运行时版本，因此相关规则变化会自动使旧缓存失效；Evidence Pack算法发生实质变化时仍应主动修改 `fact_extractor_version`。

深度条目的写作与事实检查不再默认“一条内容启动一次Agent任务”。新运行按最多4条且总输入字符受限的小批次生成 `item_writing_batch` 与 `fact_check_batch`。每个批次只摊薄Agent启动、Prompt加载以及 `$human-writing` / `$humanizer` 的固定成本；每条内容仍有独立event/item ID、来源、Schema和语义校验，fact check仍逐条给出PASS/FAIL。升级前已经生成旧式单条任务的未完成run继续按旧任务恢复，不会破坏断点状态。

Top4之外的专题补充不触发全文、写作和事实检查，因此能够扩充信息量而不线性放大Token消耗。同一GitHub项目的多个普通release只在专题补充中聚合；Top4深度条目和不同论文不会被强行合并。

开放Web搜索只补充固定信源没有覆盖的重点方向，默认最多4次。TPN同一方向只有一个项目时仍视为覆盖不足，以主动寻找不同项目或不同机制的原始来源。

## 运行成本统计

正式运行或Demo后可执行：

```bash
python briefing.py stats --run latest
```

输出包括：

- 每种Agent任务的任务数和已完成数；
- `tasks next`观察到的尝试次数与INVALID次数；
- fact cache命中次数；
- task input / prompt / output字符量；
- 原始document字符量与Agent实际看到的Evidence字符量；
- Evidence压缩比例；
- `agent_read_chars_proxy`，用于横向比较不同版本的Agent输入规模。

`agent_read_chars_proxy`只是确定性的字符量代理，不是Codex或API实际Token账单。宿主若未来能够暴露真实usage，应优先记录真实输入/输出Token，并把字符量统计保留为可复现的独立指标。

历史覆盖单独查看：

```bash
python briefing.py backfill-status
```

它会按lane显示游标、请求次数、已抓取数量、最老已看到时间、错误和 `NOT_STARTED / IN_PROGRESS / COMPLETE / ERROR / FAILED_PERMANENT` 状态，并列出尚不支持确定性历史分页的A级来源。

还可通过：

```bash
python scripts/estimate_efficiency.py
```

查看代表性Agent任务数量估算。该估算同样不等同于实际Codex Token账单，正式运行应结合 `stats`、人工修改量、端到端耗时和订阅额度变化一起评估。

## 时间窗口

- 深度专题：最近60天滚动窗口；
- 横向热点Radar：最近7天；
- arXiv与已配置GitHub Release会通过可恢复分页主动补齐本安装此前未见的60天历史；
- SQLite中60天内尚未推送的A级来源会在后续运行中继续参与候选排序；
- 其他不具备确定性历史分页能力的来源不会冒充“60天已完整覆盖”，其状态通过 `unsupported_sources` 暴露；
- 已作为深度解读、专题补充或Radar发送的内容不会无变化重复出现；
- 新鲜度只占价值分的小部分，因此高价值的30～60天内容可以高于当天的低价值release。

## Agent如何处理任务

该Skill不调用固定模型API。Python脚本会生成任务文件，当前Agent负责：

1. 读取任务指定的Prompt；
2. 读取指定输入JSON及必要的专题上下文；
3. 对 `fact_extraction` 只读取任务显式引用的Evidence Pack，不主动打开未引用的原始全文；
4. 对 `fact_evidence_repair` 只读取结构化旧facts和任务显式引用的targeted supplement，不重读Evidence Pack或原始全文；
5. 输出符合JSON Schema的结果；
6. 写到指定输出路径；
7. 运行`python briefing.py advance`。

历史回填不属于Agent任务：arXiv/GitHub分页、时间截断、游标、去重和持久化全部由Python确定性完成。

相关候选使用 `relevance_batch` 任务，每个任务最多处理12条同专题候选；输出必须对每个输入候选返回且只返回一条结果，缺失、重复或未知ID都会被拒绝。

新运行的深度条目使用 `item_writing_batch`，默认最多4条一批。Agent先逐条依据各自结构化facts形成初稿，再对整批只调用一次 `$human-writing` 和一次 `$humanizer`；两个Skill只允许调整自然中文，不得跨条目移动或增加事实、数字、因果、来源和ID。`fact_check_batch` 同样按条目独立校验，批处理不改变逐条证据边界。`issue_synthesis` 仍只读取通过事实检查的核心条目，并按原规则进行综合判断和语言审查。

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

`collect` 在历史回填未完成时会顺带消耗一个很小的历史请求预算，因此上面的既有cron无需增加专门的backfill任务。定时任务仍只触发确定性脚本；需要Agent推理的任务应由支持Skills/Automations的宿主继续执行，或在人工进入Agent后运行`resume`。

## 许可

本仓库自身代码采用MIT License。`vendor/`中的上游项目不会打包进仓库，需要安装时克隆。Guizang Social Card当前采用AGPL-3.0，修改、再分发或网络服务化前应单独审查其许可义务。
