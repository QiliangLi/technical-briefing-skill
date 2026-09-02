---
name: technical-briefing-skill
description: Collect, verify, deduplicate, analyse, illustrate, format, validate, and email recurring internal technical briefings. Use for 技术情报简报、技术信息收集、论文与博客筛选、Agent/AI/KVCache/DPU/DSA/TPN/AI芯片与加速器/I/O直通与存储数据路径/跨域传输/光交换信息追踪、Guizang图文卡片、定期邮件简报、去重和断点恢复。
---

# Technical Briefing Skill

## 目标

把大量分散、重复、深浅不一的公开技术信息压缩为可信、可读、可追溯并能直接支持项目判断的内部技术简报。

默认受众是公司内部领导和技术同事。代码保留紧凑模式；当前项目启用`expanded_v2`。每个配置的深度专题以4条完整解读为目标，Top4之外已判定相关且具有A级原始来源的内容进入“专题补充”，每条只保留1～2句总结和原文链接。专题不足4条时，先把本期简要内容按价值顺序升级为详细内容；本期简要全部升级后仍不足4条，再从60天窗口内的历史纯简要内容中按价值顺序升级补足。历史简要不要求在本期重新被发现，但必须已有通过事实检查的Machine Item和可验证的简要发布身份；升级改变的是发布角色，旧版Machine Item可沿用配置的历史正文门槛，但仍须五字段完整、事实核验通过并有A级来源。任何身份只要曾经作为详细内容发布过，就不得在没有实质更新时再次补充或重访；当前与历史简要都不足时才允许少于4条，不得用弱信息凑数。每2～3天发送一次，不强制覆盖全部专题。

## 核心架构

- Python负责确定性工作：当前采集、可恢复外部历史回填、过滤、去重、状态、预算、滚动专题池、保守的跨期relevance cache、多样性选择、Evidence Pack、定向Evidence Repair、跨期facts cache、事实任务会话分组、任务成本统计、渲染、邮件和归档。邮件默认通过本机已授权的`agently-cli`发送，SMTP仅作为显式备用后端。
- 当前Agent负责智能工作：未命中relevance cache时的批量相关性与价值判断、未命中facts cache时的事实抽取、必要时一次定向facts修复、批量Machine Item草稿写作、风险触发的事实复核、一期一次的Reader Projection、综合判断和一期一次的`illustrated_publication`。Machine Item保持稳定并服务Fact Check、Roadmap和Idea分析；Reader Projection在确定性Evidence Gate及必要的LLM Fact Check之后生成，只负责当前run的读者表达，不能跨run缓存。Codex宿主直接使用自身生图能力；Claude Code宿主在该任务中通过已安装的`openai/codex-plugin-cc`把整期生图委派给`codex:codex-rescue`子Agent。兼容的事实抽取可以复用同一Agent会话，但每篇来源的任务、Evidence Pack、输出、Schema、cache和repair始终独立。外部历史分页、游标、时间截断和历史去重不属于Agent任务。
- 重点专题走深度通道；Top4之外的相关A级内容走专题补充；AI Infra、Agent生态、KVCache生态、存储与介质等广度信息走Radar通道。
- 同一GitHub项目在专题补充中的多条低价值release可以聚合显示，但不得把不同论文或Top4深度条目强行合并。
- 不得在Python中绑定某家模型API。
- 不得依赖聊天上下文记住历史；常规状态、relevance cache与使用记录写入SQLite，外部历史回填游标写入SQLite `source_state`，回填报告写入被忽略的`workspace/backfill/`，跨期facts写入本地`workspace/cache/facts/`。
- Topic、Direction、判断卡或容量配置变更只从新run边界启用；存在按旧配置创建的非终态run时，必须先用原配置完成或明确终止，不得用新配置继续解释旧任务图，也不得追溯改写已发布Topic身份。
- Skill本身不产生定时触发；由Cron或宿主Agent任务系统调用CLI。

## 首次使用

1. 在Skill根目录运行：

   ```bash
   python briefing.py setup
   python briefing.py setup --vendor --node
   python briefing.py doctor
   ```

2. AI解释图使用唯一的 Ian/Qiliang 人物契约：

   ```text
   assets/persona/ian-qiliang/overlay.md
   assets/persona/ian-qiliang/reference-manifest.yaml
   ```

   `reference-manifest.yaml`中的`identity_anchor`、`action_anchor`和`wide_scene_anchor`都必须指向仓库内真实图片。运行时会在创建`illustrated_publication`前校验这些文件；缺失时只能让图片路径失败并保留正文，不得换成通用人物或其他生图风格。

### Ian 风格的项目级人物覆盖

在本项目中调用 `ian-xiaohei-illustrations` 生成正文插画时，必须先读取
`assets/persona/ian-qiliang/overlay.md`。Ian Skill 的风格 DNA、构图模式、原创隐喻、
提示词结构和 QA 规则保持原样，只把默认“小黑”角色替换为该覆盖文件定义的
Qiliang 手绘形象。不得修改用户级或插件目录中的 Ian Skill，也不得把人物当头像、
水印或角落装饰；人物必须承担解释本期技术判断的核心动作。

3. 先运行离线样例：

   ```bash
   python briefing.py demo
   ```

4. 新安装或历史断档时可检查并主动推进历史覆盖：

   ```bash
   python briefing.py backfill-status
   python briefing.py backfill
   ```

   正常`collect`会用很小的请求预算自动继续同一批历史游标，不要求一次性把60天全部抓完。

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

`run`内部调用`collect`。当历史回填尚未完成时，每次正常`collect`只允许使用`historical_backfill.auto_requests_per_collect`规定的小预算推进游标；回填记录先进入独立历史池，不直接创建Agent任务。

### 第二步：处理Agent任务

运行：

```bash
python briefing.py tasks next --run latest
```

严格按命令返回的执行说明处理，不得自行扩大读取范围。普通任务仍是单任务执行；当下一个任务属于`fact_extraction`且存在同专题、同项目判断卡、同Prompt/Schema的兼容任务时，命令可以返回一个**事实抽取会话组**。当前配置最多4个独立任务；各任务仍保留自己的direction上下文。

单任务执行规则：

1. 读取指定Prompt；
2. 读取指定输入JSON；
3. 只读取输入中明确引用的专题判断卡和文档。对于`relevance_batch`，只读取紧凑topic卡、批次级direction卡、候选元数据/摘要和项目判断卡，不主动打开全文；对于`fact_extraction`，正常路径只能读取任务引用的Evidence Pack；对于`fact_evidence_repair`，只能读取结构化旧facts和任务引用的targeted supplement。不得为了“更完整”主动打开未引用的原始全文；
4. 输出符合指定Schema的JSON；
5. 写入指定输出路径，然后执行`python briefing.py advance --run latest`。

事实抽取会话组必须遵守更严格的隔离规则：共享Prompt、Facts Schema和项目判断卡只读取一次；之后严格按命令列出的顺序逐任务处理。每个任务必须单独读取自己的输入JSON、direction上下文和完整Evidence Pack，前一个任务的证据对后一个任务不可采信，不得跨来源比较、归纳、补事实或移动数字；每个任务复制自己的`_task`绑定并写入自己的输出JSON，禁止产生合并数组或batch输出。全部组内输出写完后只执行一次`advance`。会话分组只减少Agent启动和重复上下文加载，不允许减少候选数、Evidence字符、facts字段、Schema校验、语义校验、facts cache、Evidence Repair或后续fact check。

需要调试、恢复旧宿主行为，或对会话隔离有任何不确定时，使用：

```bash
python briefing.py tasks next-single --run latest
```

它强制只返回一个任务；宁可退化为更多Agent启动，也不得为了分组而截断Evidence或放宽质量门禁。

relevance cache命中时，Python会在任务创建前直接恢复`relevant / score / reason / fulltext_required`，因此该候选不再出现在Agent relevance任务中。facts cache命中时，Python会直接复用已验证facts并把候选推进到`FACTS_READY`，不得再启动无意义的事实抽取Agent任务。

重复直到运行阶段为`READY_FOR_RENDER`。

### 第三步：渲染与校验

```bash
python briefing.py render --execute
python briefing.py validate
```

`validate`就是发布门：渲染完成后由最终校验把issue提升到`READY_TO_SEND`，存在FAIL时必须修复后重跑。没有独立的review/approve命令；人工检查直接阅读`workspace/runs/<run_id>/email.html`与`validation.json`完成。

### 第四步：发送

校验通过、并经人工确认邮件内容后：

```bash
python briefing.py send --confirm-send
```

发送成功后，CLI会自动把该run归档到`archive/issues/<date>/`，只提交归档产物并推送`main`，由GitHub Pages workflow完成部署。若传输成功但发布因网络或工作树状态失败，可在修复后运行`python briefing.py publish-archive --run <run_id>`重试；自动流程不会把邮件发送结果伪装成已发布。

没有`--confirm-send`时必须拒绝发送。使用默认`agently-cli`时，第一次带`--confirm-send`的调用只请求发送确认令牌并停止；将摘要展示给用户，等待用户确认后，再次运行同一命令完成发送。令牌保存在当前运行目录的被忽略文件中，不能提交到仓库。

如果需要使用SMTP备用后端，先设置`EMAIL_BACKEND=smtp`，再按同一人工确认和`--confirm-send`门禁发送。

## 上下文与成本硬规则

1. 禁止一次加载全部搜索结果。
2. 规则匹配只负责“找得到”，不能直接代表“值得深读”；Agent在规则过滤前不读取全文。
3. A级深度候选按专题批量做价值判断；`max_relevance_batch`默认最多24条，同时受`relevance_batch_max_input_chars`默认48k字符预算约束。topic信息只在批次级出现一次，direction配置必须去重后由候选通过`direction_id`引用；超长摘要默认最多暴露5k字符的完整句摘录。输出仍必须逐候选返回且不得缺失、重复或出现未知ID。只有明确版本arXiv、GitHub Release/Tag、DOI等强版本来源才允许跨期复用relevance；缓存键必须同时匹配来源指纹、topic、direction、Prompt/Schema/项目判断卡形成的evaluator版本和新鲜度区间。普通可变网页不得零评审复用；跨越配置的2/7/30/60天新鲜度边界必须重新评审。不得仅因关键词、topic hint或direction hint自动进入全文分析。
4. 只有已解析、非`discovery_only`的A级原始来源才能竞争深度Top4；B/C级和聚合线索进入Radar并继续用于发现原始来源。
5. 开放Web搜索只补充A级覆盖缺口，默认每期最多4次。TPN同一方向只有一个项目时仍视为覆盖不足，避免单一项目阻止多样化搜索。
6. 深度事实抽取按专题本地选择，单专题最多4条、同专题同项目最多1条、同方向优先最多2条；整期安全上限由`config/settings.yaml`配置。其余相关A级候选进入专题补充，不做全文写作和事实检查。
7. 原始全文可以在本地保留到`max_fulltext_chars`用于审计，但正常`fact_extraction`默认只读取`evidence_pack_max_chars`控制的Evidence Pack。Evidence Pack必须优先覆盖架构/方法/实验/结果/边界和专题相关段落，并保留章节或页码定位。
8. Evidence Pack信息不足时，宁可少写结论并在`limitations`记录缺失验证，也不得自行读取未引用全文或猜测数字。只有当缺失baseline、工作负载/硬件条件、部署边界或明确limitation会实质改变结论解释时，才允许在`evidence_gaps`中提出最多3个具体缺口，并给出可在原文中直接检索的source-native术语。
9. 每篇来源最多只允许一轮`fact_evidence_repair`。Python只能在首轮Evidence Pack未曝光的章节中按明确gap terms生成`evidence_repair_max_chars`限制的targeted supplement；repair Agent只读取结构化旧facts和这份supplement。没有明确术语命中时保持保守结论，不得退化为全文搜索；repair后仍缺失的信息保留在`limitations/evidence_gaps`，不得发起第二轮。
10. facts cache只能复用稳定来源指纹与运行时抽取版本完全匹配的结果。零抓取复用仅用于明确版本arXiv、GitHub Release/Tag和DOI类强版本身份；普通可变网页必须重新验证。事实Prompt、Facts Schema和Evidence Repair Prompt变化会自动影响运行时版本；Evidence Pack算法发生实质改变时仍应更新`fact_extractor_version`。
11. facts cache命中必须走同步fast path，不能再次生成需要Agent处理的事实抽取任务；存在未解决`evidence_gaps`的facts不得写入跨期cache。未命中cache的独立`fact_extraction`任务允许在**不修改任务图和证据量**的前提下复用执行会话：仅同topic+项目判断卡+Prompt/Schema可分组，当前配置最多4篇且组内Evidence合计不超过72k字符；每篇direction上下文仍单独读取。Evidence长度未知、超过预算、不兼容或任何隔离条件无法证明时必须单独运行。分组不得改变任何单篇输出、校验、cache、repair或fact check语义。
12. 新运行的深度条目先使用最多4条的`item_writing_batch`独立形成事实受约束的Machine Item。Python对每条执行确定性Evidence Gate；只有命中语义风险的条目才创建LLM `fact_check_batch`，低风险条目由Gate记录后通过。`fact_check_batch_size`默认24只是安全上限。每个event/item仍保持独立ID、来源、Schema/语义校验、provenance和PASS/FAIL，禁止跨条目移动事实。旧run已经存在`item_style_polish`、单条`item_writing`或已有fact-check任务时按旧任务继续恢复。
13. 所有Machine Item通过Gate或必要的Fact Check后，只创建一个当前run的`reader_projection`任务，并对整期条目调用一次`$human-writing`。Reader Projection可以选择性改写标题、导语、正文和可选takeaway，但不得改变事实、数字、条件、因果强度、ID、角色、score、日期或来源；每个sidecar必须绑定准确的Machine Item hash。`issue_synthesis`、Roadmap和Idea分析继续读取Machine数据，不能把有损的reader文案当作事实源。
14. 专题补充默认每专题最多8条、同项目最多2条；每条仅1～2句总结和原文链接，不参与本期综合判断。同一GitHub项目多条低优先级release可聚合为Release Family，必须保留每个原始链接。
15. 完成facts抽取/必要的repair后，后续任务只读取结构化facts，不再读取全文。
16. 最终综合判断只读取通过事实检查的核心深度解读，不读取专题补充和热点Radar。
17. 不要为了“记住上次推送”使用对话记忆；查询SQLite、事件历史、缓存和推送历史。
18. 外部历史回填必须是确定性、可分页、可时间截断的Python工作，禁止为“补60天历史”批量创建Agent搜索任务。当前可验证回填只包括arXiv专题方向和配置的GitHub Releases仓库；其他A级源必须显示为`unsupported_sources`，RSS不得假装是完整历史档案。
19. 历史回填本身必须产生0个Agent任务。抓取结果写入不属于正常`runs`表的独立历史批次；后续正常run通过`backlog_materialize_per_run`逐步搬入，默认每次最多120条，然后才进入批量价值判断。因此一次回填发现1000条，也不得直接制造1000条Agent任务。
20. 每次正常`collect`最多消耗`historical_backfill.auto_requests_per_collect`个历史外部请求，默认4个；不同GitHub/arXiv lane必须公平轮转并持久化游标。手工`backfill --max-requests N`只允许加速同一游标状态，不得绕过去重和下游120条入口预算。

成本配置位于`config/settings.yaml`的`efficiency`段。正式运行后优先执行：

```bash
python briefing.py stats --run latest
python briefing.py backfill-status
```

`stats`检查每种Agent任务的任务数、尝试次数、INVALID次数、facts cache命中、relevance cache条目/本期命中、输入/输出字符量、原始document字符量、Evidence字符量和压缩比例，并额外给出`fact_session_plan`，区分“独立事实任务数”和“预计需要启动的Agent会话数”。`fact_session_plan`只描述调度层复用，不得被解释成少处理了事实任务或少读了证据。`backfill-status`检查历史lane的游标、请求次数、已抓取数量、最老已看到时间、错误、支持/不支持来源。`agent_read_chars_proxy`只是确定性的字符量代理，不是Codex或API真实Token账单；若宿主以后能提供真实usage，必须把真实Token作为首要指标，同时保留字符量用于可复现实验。

还可执行：

```bash
python scripts/estimate_efficiency.py
```

查看代表性Agent任务数量估算。60天滚动池会增加首次运行的候选数量，但相关性仍按受字符预算约束的批处理；稳定版本来源在评分上下文和新鲜度区间未变化时可跨期复用relevance。专题补充不触发全文、写作和事实检查。任何任务数量或会话数量估算都不等同于实际Token账单，正式运行仍需结合`stats`、人工修改量、端到端耗时和订阅额度。

## 时间窗与跨期覆盖

- 深度专题使用最近60天的滚动窗口，而不是3天新闻窗口；
- arXiv各深度方向与配置的GitHub Release仓库通过持久化游标主动向过去翻页，直到越过本次60天campaign cutoff或来源耗尽；
- 外部历史记录先进入独立历史池；每次正常运行再把SQLite中最近60天、尚未推送的A级原始来源按预算带入当前候选池；
- `COMPLETE`只表示所有“支持确定性历史分页”的lane已经越过时间边界或耗尽，不得推断`unsupported_sources`也具有完整60天历史；
- 已经作为深度条目、专题补充或Radar发送过的稳定身份不得重复出现；
- relevance cache不得阻止内容变老：跨越新鲜度评分边界后必须重新评审；
- 新鲜度仅占价值判断的小权重，强相关的30～60天内容可以高于当天的弱更新；
- 横向热点Radar仍保持最近7天，维持其“快速发现”的定位；
- 搜索发现时间和抓取时间不得代替原始发布日期；
- 旧事件只有存在明确`incremental_update`及新增内容时才允许重新推送。

## 信息源规则

### AI HOT（不可见上游）

AI HOT是隐形上游编辑与发现服务，接入四条栏目lane：

- `selected`：最近24小时精选，主要Radar直出候选池；
- `all`：按Direction关键词查询最近7天，作为专题补漏和候补池；
- `daily`：AI 日报结构化条目，补充精选与关键词查询的遗漏；
- `hot`：热点榜，只提供热点权重与story身份，本身不产出公开卡片；无法解析到单条摘要的热点仅计入内部覆盖统计。

连接器行为：

- 每个run把全部lane响应冻结在`workspace/runs/<run_id>/source-cache/aihot/freeze.json`，resume/重渲染只读冻结数据，绝不重新请求上游；
- ETag 304从跨运行响应缓存物化内容，新run不会因为上游未变化而拿到空Radar；
- 每条lane观察都写入内部`radar_upstream_records`台账（provider、item/story ID、内容hash、原始payload、是否采用与原因），该台账永不进入归档或Pages；
- AI HOT对Agent语义加速、Coding Agent、KVCache/Prefill-Decode、AI芯片与跨域Cache等方向提高查询优先级。

AI HOT对深度通道永远是发现源：

```text
AI HOT候选
→ links.original
→ 原始论文/官方博客/仓库
→ relevance判断/可验证缓存复用
→ Evidence Pack / facts cache
→ 事实抽取 / 必要时一次Evidence Repair / 缓存复用
```

不得把AI HOT的AI摘要直接当作技术证据；上游`reason`（编辑推荐理由）永不进入公开文案，只保存在内部台账。Radar通道直接采用冻结的上游单条标题与摘要（见"跨期去重与热点Radar"），不调用Agent改写；日报条目缺少原始发布日期时公开卡片不显示日期，日报日期只作内部召回边界，绝不冒充原始发布日期。

### Follow Builders与YeeKal AI Daily

Follow Builders用于发现Builder观点、工程实践、访谈和官方博客线索；YeeKal AI Daily用于发现日报中的外部技术文章、项目和社区讨论。两者均保持B级、`discovery_only`，必须回到A级原始论文、官方文档、官方博客或项目仓库后才能进入重点信息。YeeKal日报日期只表示发现时间，不得冒充外部原始发布日期。

条目写作采用“Machine Item草稿 → 确定性Evidence Gate → 高风险条目Fact Check → 整期Reader Projection”的顺序：`item_writing_batch`只依据各自结构化facts形成机器事实表达；Gate逐条检查证据绑定并只把高风险条目交给LLM复核；随后`reader_projection`把整期条目放在同一个上下文中，只调用一次`$human-writing`生成自然、可选择省略次要字段的读者文案。任何Reader Projection都不得增加事实、数字、因果关系或来源，且不能替代Machine Item。

本地未安装`human-writing`时执行：

```bash
npx skills add https://github.com/KKKKhazix/human-writing --global --agent codex
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
4. AI芯片与加速器，包括GPU/NPU/TPU/ASIC、Chiplet、先进封装、内存接口和软硬件协同；
5. Agent语义加速，包括CodeGraph、Read/Grep/Glob、上下文构建和工具执行链；
6. KVCache、Agent Cache和记忆的跨域传输；
7. AI/GPU集群光交换网络；
8. 存储介质与器件，包括NAND/Flash/HBF、新型非易失存储、HDD和介质—控制器协同；
9. 加速器直连I/O与存储数据路径，包括直接数据路径、GPU/NPU主动发起I/O、加速器存储软件快路径和细粒度I/O控制器协同。

基础专题定义在`config/topics.yaml`，芯片、存储介质、加速器存储I/O与边界探索分别定义在`config/topics-chip.yaml`、`config/topics-media.yaml`、`config/topics-io.yaml`和`config/topics-frontier.yaml`。运行时合并全部专题；当前数量和深度/Radar路由以这些文件及`config/settings.yaml`为准。

每个深度专题采用两层输出：

- **深度Top4**：优先覆盖不同项目和不同技术方向，保留完整机制、证据、边界和项目启发；
- **专题补充**：Top4之外仍然相关的A级内容，只给1～2句总结与原文链接。兼容性、例行release等内容更适合放在这里，不应抢占深度Top4。同一GitHub项目的多条普通release可折成一个Release Family，原始链接不能丢。

横向Radar保持以下四类召回：

- AI Infra：LLM Serving、推理引擎、GPU集群、集合通信、编译器、Kernel、分布式训练、可观测性和故障恢复；
- Agent生态：MCP、Computer Use、Browser Agent、Agent Memory、多Agent和开发工具；
- KVCache生态：Prefix Cache、量化、分层、路由、持久化以及LMCache、vLLM、SGLang等项目动态；
- 存储与介质：HBM、HBF、CXL内存、Persistent Memory、NVMe SSD、NAND、QLC/TLC、ZNS、HDD和Computational Storage。

横向强信号只有在拥有A级原始来源、具体机制、量化证据或部署信息并与项目直接相关时，才允许晋升深度通道。具体方向和查询不得在Prompt中重新发明，读取专题配置和对应的`config/project-context/`判断卡。

## 相关性与价值判断

规则匹配分数只由关键词、query overlap、topic/direction hint和来源优先级组成，用于召回和路由，不得直接当成技术价值分。

A级候选进入批量价值判断后，`score`按以下维度形成：

- 项目相关性35分；
- 技术新颖性/实质机制25分；
- 证据具体性20分；
- 可行动性15分；
- 新鲜度5分。

例行兼容、依赖升级、普通bug fix、文档、CI/build和版本号更新可以判为“相关”，但没有实质能力、性能、架构或部署变化时通常不得进入全文Top4，应进入专题补充。最终深读选择还要执行同项目和同方向多样性约束。

relevance复用的目标是避免60天滚动池中同一个不可变版本反复支付Agent判断成本，而不是永久冻结评分。只有强版本来源才能缓存；来源版本/内容指纹、Prompt、Schema、当前专题或方向判断上下文、项目判断卡发生变化都会自动miss。由于价值分包含5分新鲜度，缓存还按`freshness_days`边界分桶，跨桶必须重新判断。

## 单条信息规则

输出应让读者无需打开原文就能理解基本技术方案。内容包括：

- 标题；
- 类型、专题、日期和重要度；
- 一句话核心结论；
- 最小必要机制；
- 1～2个关键结果及条件；
- 最重要的适用边界；
- 一个项目启发或下一步验证动作；
- 3～5个关键词；
- 原始来源。

禁止：营销语言、无条件放大预印本结论、遗漏关键基线、把项目推断写成原文事实、以省略号或悬空标点结束字段。五个正文域合计使用任务输入和`config/settings.yaml`给出的长度预算，当前新条目通常为230～330字；优先删除次要背景，不得依赖冒号串联或括号堆叠强行压缩。渲染器不得截断事实检查后的正文。

## 跨期去重与热点Radar

- 事件身份依次使用arXiv基础ID（忽略`vN`）、DOI、GitHub仓库与Release、规范化原始URL；仅在没有稳定标识时使用语义事件名；
- 外部历史回填与普通采集使用同一稳定来源身份去重，重置游标或与普通采集重叠不得故意产生第二份同源记录；
- 同一稳定身份的历史事件共享`last_pushed_at`，标题语言、版本号或摘要变化不得绕过去重；
- relevance cache和facts cache都比事件去重更严格：外部版本号/内容指纹或对应评审/抽取版本发生变化时不得复用旧结果，即使事件身份仍属于同一论文或项目；
- 专题补充与Radar共享推送URL历史，已经以短摘要展示的内容后续不得无变化重复出现；
- Radar独立按原始URL和规范化标题跨期去重；同一story的多篇报道按story身份合并，每期最多一条；
- Radar最多16条、每类最多5条；当合法候选充足时至少8条链接到公司官方工程博客、产品/研究团队博客或个人Builder原文。AI HOT提供的冻结中文标题与摘要可以直接使用，原始网页是否为中文不影响入选；
- 排除融资财报、股价、高管言论、政治政策、版权诉讼、游戏娱乐和消费应用；
- Radar卡片由确定性代码直接采用冻结上游的单条标题与摘要（整段或连续完整句子），不做生成式改写；每条公开文案保存hash/span溯源，可证明发布字符全部来自冻结上游字段；
- `issue_synthesis`不读写Radar；`radar.direct_copy`（默认开启）控制确定性直出，关闭则回退到综合Agent写作radar_signals的旧路径；
- Radar只链接并展示原始网页来源；发布前对邮件、归档公开JSON和Pages数据做上游痕迹负向扫描（品牌、域名、provider字段），任何AI HOT可见痕迹都会使发布失败；
- Radar在知识层固定为`evidence_kind=discovery_signal`、`claim_strength=unverified`，只能聚类与计数，不得直接支持或否决Roadmap阶段与Idea。

## 视觉规则

生产流程不再运行逐条`visual_routing`。每一期只创建一个`illustrated_publication`任务，在已经事实检查并完成综合判断的最终简报上做整期视觉策划，然后固定生成两份邮件：

```text
email.html
email-illustrated.html
```

`email.html`始终保持纯正文基线；`email-illustrated.html`使用完全相同的正文，只增加解释图。生图任务不得改写、缩写、重排或补充事实。

解释图数量**不设固定上限**。由整期内容决定需要多少张：只要是彼此独立、能实质帮助理解的机制、架构关系、系统路径、取舍或项目判断，都可以生成；不得为了“多图”填充装饰图、重复图或近重复图。信息密集的一期超过3张完全正常，信息较少时也可以少于3张甚至0张。

### 宿主执行规则

- **Codex中运行整个Skill**：直接使用当前Codex宿主的生图能力执行`illustrated_publication`，不增加额外委派。
- **Claude Code中运行整个Skill**：Claude模型本身没有原生生图能力不算失败。必须通过已经安装的`openai/codex-plugin-cc`调用`codex:codex-rescue`子Agent，把整期`illustrated_publication`一次性委派给Codex；使用fresh、foreground执行（`--fresh --wait`），不要按图片拆成多个Codex任务。
- `codex:codex-rescue`是Claude Code的subagent，不是Skill；通过`Agent`工具调用，不得使用`Skill(codex:codex-rescue)`，也不要在另一个Skill里递归调用`/codex:rescue`。
- 委派时必须把当前任务输入、Prompt、Schema/结果绑定、个人IP参考路径、图片输出目录和预期结果路径一起交给Codex。Codex在同一checkout中生成和QA图片，并直接写入最终任务JSON；Claude Code只验证产物后继续`advance`，不得依据stdout重新编造一份manifest。
- 只有插件不可用、Codex未认证、委派任务真实失败或图片QA失败时，Claude Code才允许降级；**“Claude自身不能生图”不是`fallback_to_text`的理由**。

### 个人视觉IP

AI解释图的个人角色只由`assets/persona/ian-qiliang/overlay.md`和`assets/persona/ian-qiliang/reference-manifest.yaml`定义。当前Qiliang形象为短而略蓬松的黑发、细黑框圆形或轻微圆角眼镜、白色衬衫领口外搭黑色针织衫、深色长裤，神情平静、认真、克制；身份、动作和横版场景分别以manifest中的三张批准参考图为准。

- **每一张AI生成的解释图都必须包含个人IP**，不设每期出现次数上限；
- 人物通常占画面15%～25%，必须是技术机制的参与者而不是视觉主体；
- 角色必须通过实际动作参与核心技术隐喻，而不是在角落旁观、摆拍或充当水印；
- 不得卖萌、抢镜、摆主持人姿势、遮挡证据或使用未经批准的通用替代角色；
- 每张图可以变化人物位置和动作，但人物身份和核心视觉特征必须稳定；
- 不直接使用Ian Xiaohei的“小黑”角色，也不得切换到其他人物或插图生成风格。

### 生图约束

- 默认横图比例`1.9:1`；
- 每张图只放少量必要的中文短标签，通常3～5个；
- 图像模型不得虚构百分比、时延、吞吐、P95、坐标或实验柱状图；需要精确数字时应依赖正文和原始证据，而不是让生图模型制造数值图表；
- 每张图生成后检查个人IP一致性、中文文字、箭头/节点关系、裁切、安全边距和事实结构；
- 只有`status=generated`且`persona_used=true`的图片才允许进入`email-illustrated.html`。

详细执行契约见`docs/contracts/illustrated-publication.md`、`prompts/illustrated-publication.md`和`schemas/illustrated-publication.schema.json`。

## 失败降级

- Codex宿主只有在直接生图真实失败时才降级；Claude Code宿主必须先走`openai/codex-plugin-cc`桥接，只有桥接/委派真实失败或图片无法可靠生成时，才把该图标记`fallback_to_text`/`failed`或省略；
- 即使所有图片失败，也必须同时生成`email.html`和`email-illustrated.html`，后者退化为完整正文基线；
- 全文抓取失败：使用摘要做低置信Radar候选，但不得成为无A级来源的重点信息。
- relevance cache来源指纹、版本、评分上下文或新鲜度桶不匹配：按cache miss重新进入批量价值判断，不得为了省Token强行复用；普通可变网页始终按miss处理。
- Evidence Pack缺少材料性条件且明确gap terms在未曝光章节中有命中：最多生成一次targeted supplement；没有命中或repair后仍不足时降低结论强度并写入`limitations`，不得偷偷扩大到未引用全文。
- facts cache文件缺失、版本不匹配、来源版本变化或facts仍有`evidence_gaps`：按cache miss/不缓存处理，不得假装命中。
- 事实抽取会话分组无法证明同topic/项目判断卡/Prompt/Schema，Evidence长度未知，组内Evidence超过配置上限，或宿主无法可靠在同一会话内逐任务写独立输出：自动退化为单任务执行。不得通过截断Evidence、合并输出或跳过Schema/repair来维持分组收益。
- 历史回填单次网络错误：保留lane游标并标为`ERROR`，后续采集再重试，不得从第一页重新扫；明确的GitHub 404等配置/来源问题标为`FAILED_PERMANENT`并在`backfill-status`暴露，修复配置后再reset。
- 邮件失败：不写`last_pushed_at`，下次只重试发送。
- 任何配图失败都不能阻塞简报正文。

## 完成标准

发送前必须满足：

- `expanded_v2`单专题深度解读不超过4条；同专题同项目默认不超过1条深读；
- `expanded_v2`整期详细条目不超过`config/scoring.yaml`配置的36条安全上限；不足时不得用弱信息补齐；
- Top4之外的专题补充只包含已判定相关的A级内容，每条1～2句并链接原文；Release Family必须保留每个原始release链接；
- 每条Machine Item五个事实正文域满足任务输入和当前配置的长度预算；Reader Projection按内容自然展开，不要求机械呈现五个槽位；
- 每条深度解读至少一个A级来源；
- 所有数字可追溯到Evidence Pack或targeted supplement中的定位信息，或其他明确的原始来源；
- 所有详细条目都通过确定性Evidence Gate；命中风险的条目完成LLM Fact Check；当前run的Reader Projection必须绑定通过后的Machine Item hash；
- 无重复事件或重复推送的专题补充；
- 旧事件写明增量；
- 项目判断与来源事实分开；
- `email.html`和`email-illustrated.html`都已生成；
- 归档时两份邮件必须保持原名，原始快照写入不可覆盖的`original/`，根目录公开版必须有hash一致的`reader.json`与`publication-manifest.json`；
- 所有成功生成并进入增强版邮件的解释图都包含批准的个人IP；
- HTML正文可复制、链接可点击；
- 图片无法加载时正文仍完整；
- 已经通过最终`validate`校验，并经人工确认过邮件内容。
