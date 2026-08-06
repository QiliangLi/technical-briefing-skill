# Technical Briefing Skill 增量改造计划

## 0. Codex 执行说明

本文件将放在现有 `technical-briefing-skill` 本地仓库中。Codex 应直接在当前工作区实施，不要重新克隆、初始化或复制仓库，也不要建立所谓“基线目录”。

开始前只需要：

1. 阅读当前工作区的 `README.md`、`SKILL.md`、`briefing_skill/`、`config/`、`prompts/`、`schemas/`、`templates/` 和 `tests/`。
2. 执行 `git status --short`，识别用户尚未提交的修改，避免覆盖。
3. 使用 `rg` 搜索本文提到的符号和字段，确认本地代码是否比远端版本更新。
4. 所有修改都应沿用当前 Python 包、SQLite、Agent 任务队列和 CLI，不新增固定模型 API。
5. 不要改动现有 `agently-cli` 默认邮件后端、人工审核门禁、新鲜度门槛和跨期去重语义，除非本文明确要求。
6. 不要把 Follow Builders、YeeKal AI Daily、human-writing 或 humanizer 整个 vendor 到当前仓库。

建议 Codex 先执行：

```bash
git status --short
rg -n "judgements|judgement_refs|_rebuild_synthesis|issue_synthesis|item_writing|CollectionService|FulltextService" .
```

---

## 1. 当前实现与本次改造范围

当前仓库已经具备以下主链路：

```text
CollectionService
→ raw_items
→ RuleMatcher
→ relevance_review
→ FulltextService
→ fact_extraction
→ EventClusterer
→ item_writing
→ fact_check
→ issue_synthesis
→ issue.json
→ EmailService / Renderer
→ review
→ agently-cli 或 SMTP
```

现有入口已经是 Python 包：

```text
briefing.py
→ briefing_skill.cli:main
```

现有采集器由 `briefing_skill/collection.py` 固定注册：

- `AIHotCollector`
- `ArxivCollector`
- `RSSCollector`
- `GitHubReleaseCollector`

当前 `CollectedItem` 已包含本次接入所需的大部分字段：

```text
source_id
discovery_source
source_level
discovery_only
title
summary
original_url
published_at
discovered_at
authors
external_id
topic_hint
direction_hint
priority
payload
```

本次只做三类增量修改：

1. 接入 Follow Builders。
2. 接入 YeeKal AI Daily。
3. 使用 `human-writing` 和 `humanizer` 改善单条解读与“本期判断”的自然中文，同时修复当前 `issue_synthesis` 和 `rebuild-existing` 的结构问题。

---

# 第一部分：接入新信源

## 2. 信源定位

### 2.1 Follow Builders

Follow Builders 提供三个公开 JSON Feed：

```text
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json
```

该信源的角色是：

```text
人物观点、工程实践、访谈和产品动向发现源
```

它不应直接替代论文、官方文档和项目仓库。

建议等级：

```yaml
source_level: B
discovery_only: true
```

例外：若 `feed-blogs.json` 中的 URL 本身指向明确的官方技术博客，也暂时仍按 B 级发现项入库。后续若同一 canonical URL 被官方 RSS、Agent Web Search 或 GitHub 等 A 级来源再次发现，现有事件聚类会把它们合并。第一版不要在 Follow Builders 适配器中自行维护复杂的厂商域名白名单。

适配专题优先级：

```text
Agent语义加速       高
AI Infra横向动态    高
状态感知网络/TPN    中
跨域传输            中
DPU/DSA/光交换      低
```

### 2.2 YeeKal AI Daily

YeeKal AI Daily 的角色是：

```text
AI新闻、GitHub开源项目和Hacker News社区讨论的交叉发现源
```

公开入口：

```text
RSS:   https://yeekal.com/rss/daily.xml
索引:  https://yeekal.com/daily/
```

YeeKal 日报页面本身经过二次筛选和 LLM 摘要，不能直接作为技术事实。当前系统应提取日报中的外部原始链接，把原始链接作为候选来源。

建议等级：

```yaml
source_level: B
discovery_only: true
```

适配专题优先级：

```text
Agent语义加速       很高
AI Infra横向动态    很高
状态感知网络/TPN    高
跨域传输            中高
DPU/DSA/光交换      中低
```

AI HOT 的 Agent、AI、KVCache 类优先级保持最高。新增信源的作用是补充视角，不改变“A 级来源决定最终证据等级”的规则。

---

## 3. 配置文件修改

修改 `config/sources.yaml`，新增两个逻辑信源。

建议结构如下。Codex 可根据当前 YAML 风格调整键名，但不要改变语义。

```yaml
  - id: follow_builders
    name: Follow Builders
    type: follow_builders
    enabled: true
    source_level: B
    discovery_only: true
    feeds:
      x: https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json
      podcasts: https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json
      blogs: https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json
    base_priorities:
      x: 8
      podcasts: 12
      blogs: 14
    topic_boosts:
      agent_acceleration: 1.30
      ai_infra_horizontal: 1.25
      tpn: 1.10
      cross_region: 1.10
      memory_dsa: 0.90
      dpu_inline: 0.90
      optical_network: 0.80
    max_x_items: 40
    max_podcast_items: 8
    max_blog_items: 20
    skip_short_x_chars: 60
    notes: >-
      只作为Builder观点、访谈和官方博客线索源；
      推文和播客观点不得独立支撑重点技术结论。

  - id: yeekal_daily
    name: YeeKal AI Daily
    type: yeekal_daily
    enabled: true
    source_level: B
    discovery_only: true
    rss_url: https://yeekal.com/rss/daily.xml
    index_url: https://yeekal.com/daily/
    max_issue_pages: 3
    max_external_links_per_issue: 40
    base_priority: 14
    topic_boosts:
      agent_acceleration: 1.35
      ai_infra_horizontal: 1.35
      tpn: 1.20
      cross_region: 1.15
      memory_dsa: 1.00
      dpu_inline: 1.00
      optical_network: 0.90
    notes: >-
      只提取日报中的外部原始链接和邻近说明；
      不把YeeKal的摘要、洞察和评分直接作为技术证据。
```

不要在 `config/sources.yaml` 中加入模型配置、推送配置或 YeeKal 项目的 systemd 配置。

---

## 4. Follow Builders 适配器

新增：

```text
briefing_skill/adapters/follow_builders.py
```

类名建议：

```python
class FollowBuildersCollector:
    ...
```

构造函数应接收：

```python
ConfigBundle
Database
HttpClient
run_dir: Path
```

需要 `run_dir` 是因为播客 transcript 不应直接写入 SQLite 的 `payload_json`，而应保存为独立文件。

### 4.1 ETag 与错误隔离

每个 Feed 单独使用 `source_state`：

```text
follow-builders:x:<url>
follow-builders:podcasts:<url>
follow-builders:blogs:<url>
```

请求时沿用 `AIHotCollector` 的 ETag 模式：

```text
If-None-Match
304 → 返回空列表
200 → 更新 source_state
单个Feed失败 → 记录warning，继续其他Feed
```

不要因 podcasts Feed 失败而丢弃 X 或 blogs 的结果。

### 4.2 X Feed 映射

`feed-x.json` 的结构是：

```text
generatedAt
lookbackHours
x[]
  name
  handle
  bio
  tweets[]
    id
    text
    createdAt
    url
    likes
    retweets
    replies
```

每条有效 tweet 生成一个 `CollectedItem`。

字段映射：

```text
source_id        = follow_builders_x
discovery_source = Follow Builders / X / <builder name>
source_level     = B
discovery_only   = true
title            = 从tweet正文提取的首个完整短句或首行
summary          = 完整tweet正文
original_url     = tweet.url
published_at     = tweet.createdAt
discovered_at    = feed.generatedAt
authors          = [builder name]
external_id      = tweet.id
priority         = X基础分 + 互动轻量加分
payload          = handle、bio、likes、retweets、replies、feed_generated_at、source_role
```

`payload.source_role` 设置为：

```text
people_signal
```

过滤规则：

1. 空文本直接跳过。
2. 少于 `skip_short_x_chars` 且只有“yes”“confirmation here”“nice use case”或纯链接性质的低信息内容跳过。
3. 不因为点赞数低而直接丢弃长技术观点。
4. 互动量只用于小幅排序，不能把非技术内容变成高价值候选。
5. 不尝试把 X 推文自动升级为 A 级来源。
6. 不把 `bio` 拼进摘要正文，只保存在 payload。

标题生成必须使用完整短句，不能在字数中间硬截断并添加省略号。可复用现有 `complete_sentence_excerpt()`，或新增专门的短标题清理函数。

### 4.3 Podcasts Feed 映射

`feed-podcasts.json` 的结构包含：

```text
generatedAt
lookbackHours
podcasts[]
  name
  title
  guid
  url
  publishedAt
  transcript
```

每一期播客生成一个 `CollectedItem`：

```text
source_id        = follow_builders_podcast
discovery_source = Follow Builders / Podcast / <podcast name>
source_level     = B
discovery_only   = true
title            = episode.title
summary          = 仅保留简短元数据说明，不复制完整 transcript
original_url     = episode.url
published_at     = episode.publishedAt
discovered_at    = feed.generatedAt
authors          = [podcast name]
external_id      = episode.guid
priority         = podcast基础分
payload          = podcast_name、local_fulltext_path、source_role
```

`payload.source_role`：

```text
builder_interview
```

完整 transcript 写入：

```text
workspace/runs/<run_id>/source-cache/follow-builders/podcasts/<guid>.md
```

文件内容至少包括：

```text
标题
播客名称
原始URL
发布时间
Transcript
```

不要把完整 transcript 放进 `raw_items.payload_json`，否则 SQLite、任务输入和调试输出会明显膨胀。

### 4.4 Blogs Feed 映射

`feed-blogs.json` 当前可能为空，因此解析器必须容忍空数组和字段变化。

支持以下候选字段：

```text
title
url / link
publishedAt / published_at
summary / description
content
author / name
id / guid
```

映射：

```text
source_id        = follow_builders_blog
discovery_source = Follow Builders / Blog
source_level     = B
discovery_only   = true
original_url     = blog.url或blog.link
published_at     = blog发布时间
discovered_at    = feed.generatedAt
payload          = feed原始元数据中除正文外的字段
```

若有长 `content`，同样写入 `source-cache`，只在 payload 中保存相对路径。

### 4.5 FulltextService 支持本地全文

修改：

```text
briefing_skill/fulltext.py
```

在 `fetch_candidate()` 或 `_fetch()` 的最前面检查：

```python
payload.get("local_fulltext_path")
```

若路径存在：

1. 从仓库根目录或 run 目录解析相对路径。
2. 直接读取文件。
3. `media_type` 使用 `text/markdown`。
4. `fetch_status` 使用 `LOCAL_SOURCE`。
5. 之后仍走现有 sanitize、最大字符限制和 chunk 逻辑。

不要把 Follow Builders 的特殊判断散落在 `FulltextService` 中。只识别通用的 `local_fulltext_path`，以后其他适配器也能复用。

---

## 5. YeeKal AI Daily 适配器

新增：

```text
briefing_skill/adapters/yeekal.py
```

类名建议：

```python
class YeeKalDailyCollector:
    ...
```

构造函数接收：

```python
ConfigBundle
Database
HttpClient
```

### 5.1 第一层：获取近期日报页面

优先读取：

```text
https://yeekal.com/rss/daily.xml
```

RSS 条目只用于发现日报页面，不直接生成 `CollectedItem`。

从 RSS 中取最近 `max_issue_pages` 个日报链接。

RSS 失败时才回退到：

```text
https://yeekal.com/daily/
```

从索引页提取最近日报路径。

使用 ETag：

```text
yeekal:rss:<url>
yeekal:index:<url>
yeekal:issue:<issue-url>
```

### 5.2 第二层：解析日报中的外部原始链接

对每个日报页：

1. 解析正文区域。
2. 找出 `href` 指向外部域名的链接。
3. 排除：
   - `yeekal.com` 自身链接；
   - 图片、头像、二维码和静态资源；
   - 分享按钮；
   - 无标题或明显导航链接；
   - 重复 canonical URL。
4. 为每个外部链接提取邻近上下文：
   - 链接文字；
   - 最近的标题；
   - 所在卡片或段落的简短说明；
   - 日报页面 URL；
   - 日报日期；
   - 所属板块，如 RSS、GitHub Trending、Hacker News。

不要把整篇 YeeKal 日报作为一条候选。

### 5.3 原始发布日期解析

当前系统的新鲜度门槛使用 `published_at`，并且未知日期会被排除。因此 YeeKal 适配器不能直接把“日报日期”冒充为外部文章的原始发布日期。

为每个通过初步技术关键词过滤的外部链接执行轻量日期解析。

建议新增通用模块：

```text
briefing_skill/source_metadata.py
```

提供：

```python
def extract_published_at(html: str, url: str) -> str | None:
    ...
```

按以下顺序解析：

1. JSON-LD 中的 `datePublished`。
2. `meta[property="article:published_time"]`。
3. `meta[name="date"]`、`datePublished` 等常见字段。
4. `<time datetime="...">`。
5. GitHub Release URL 中可通过页面元数据获得的发布日期。
6. arXiv URL 中已有明确标识时，可留给 arXiv 采集器或页面元数据解析。

字段含义：

```text
published_at  = 外部原始来源的发布日期
discovered_at = YeeKal日报日期或抓取时间
```

无法解析原始发布日期时：

```text
published_at = None
```

不要使用日报日期替代。当前新鲜度逻辑会安全地排除这类记录。

### 5.4 CollectedItem 映射

每个外部链接生成一条：

```text
source_id        = yeekal_daily
discovery_source = YeeKal AI Daily
source_level     = B
discovery_only   = true
title            = 外部链接标题或日报中的条目标题
summary          = 日报中的邻近短说明，仅作发现摘要
original_url     = 外部链接
published_at     = 从外部页面解析出的日期
discovered_at    = 日报日期
external_id      = stable hash(issue_url + original_url)
priority         = base_priority × 主题相关boost
payload          = issue_url、section、link_text、source_role
```

`payload.source_role`：

```text
aggregated_discovery
```

### 5.5 技术预过滤

为了避免对日报中的所有外链发起请求，可在解析原始日期前做一次便宜的文本预过滤。

预过滤文本：

```text
条目标题 + 邻近说明 + 板块名称
```

关键词来源应从当前 `config/topics.yaml` 动态汇总：

- `include_terms`
- `aihot_boost_terms`
- 查询中的稳定技术词

不要在 `yeekal.py` 中重新维护一套固定专题列表。

预过滤只用于减少外部请求，不能代替后续 `RuleMatcher` 和 `relevance_review`。

### 5.6 不复用 YeeKal 的 LLM 与推送系统

本次不做：

- 不导入 YeeKal 的 OpenAI 兼容 LLM 客户端。
- 不导入它的飞书、Discord 和 systemd 代码。
- 不直接复制它的日报摘要。
- 不把它的评分作为当前项目的最终评分。
- 不导入 420 个 RSS 源。
- 不复用其 `news-data` 目录。

后续确有需要时，再单独评估 OPML、GitHub Trending 和 HN 模块。

---

## 6. 注册采集器

修改：

```text
briefing_skill/collection.py
```

新增 import：

```python
from .adapters.follow_builders import FollowBuildersCollector
from .adapters.yeekal import YeeKalDailyCollector
```

在 collectors 中注册，保留现有失败隔离：

```python
collectors = [
    AIHotCollector(...),
    ArxivCollector(...),
    RSSCollector(...),
    GitHubReleaseCollector(...),
    FollowBuildersCollector(self.config, self.db, self.http, self.run_dir),
    YeeKalDailyCollector(self.config, self.db, self.http),
]
```

不要为两个新信源新增 CLI 命令。它们应跟随现有：

```bash
python briefing.py collect
python briefing.py run
```

统一运行。

---

# 第二部分：自然中文与“本期判断”结构修复

## 7. 当前问题

当前普通流程中：

```text
prompts/issue-synthesis.md
→ schemas/issue-synthesis.schema.json
→ Pipeline._apply_task(issue_synthesis)
→ EmailService._judgement_refs()
→ templates/email.html
```

当前 `judgements` 是字符串数组，无法明确表示：

- 判断标题；
- 判断正文；
- 支撑条目；
- 后续关注点。

邮件端只能从文字中模糊猜测条目引用，因此会产生：

```text
判断正文
对应：条目标题
```

同时，`briefing_skill/expanded.py` 的 `_rebuild_synthesis()` 会直接生成：

```text
条目标题：核心结论
```

这是当前重建后“本期判断”像条目摘要拼接的直接原因。

本次必须同时修复正常流程和 `rebuild-existing`，不能只改 Prompt。

---

## 8. 安装和调用润色 Skills

### 8.1 安装到本地 Codex

使用 Skills CLI 安装：

```bash
npx skills add https://github.com/KKKKhazix/human-writing --global --agent codex
npx skills add https://github.com/blader/humanizer --global --agent codex
```

若当前 Skills CLI 不支持 `--agent codex`，按其提示安装到全局 Skills 目录，并重新启动 Codex 会话。

本项目不 vendor 这两个仓库，也不在 Python 中调用它们。

### 8.2 调用顺序

只在 Agent 处理以下任务时调用：

```text
item_writing
issue_synthesis
```

执行顺序：

```text
根据结构化事实完成初稿
→ 调用 $human-writing 调整中文表达
→ 调用 $humanizer 做AI写作痕迹审查
→ 恢复并校验JSON结构
→ 写入任务输出文件
```

职责：

`$human-writing`

- 调整中文语序、句子推进、主语和动作；
- 删除报告腔、名词堆叠和不自然的压缩表达；
- 让技术负责人能够直接读懂；
- 不添加任何事实、数字或因果关系。

`$humanizer`

- 只做最后审查；
- 清理模板化AI句式、重复强调、虚假升华和机械并列；
- 不把技术文档改成个人散文；
- 不替换准确的技术名词、项目名、缩写和数值；
- 不改变 JSON 字段含义。

不要求 Python 自动探测 Skills 是否安装。Skill 是当前 Agent 的能力，不是运行时依赖。

---

## 9. 让任务指令明确列出所需 Skills

修改：

```text
briefing_skill/tasks.py
briefing_skill/pipeline.py
```

`TaskService.create()` 已经支持 `metadata_json`，但 `instructions()` 尚未使用。

修改 `TaskService.instructions()`：

1. 读取 `metadata_json`。
2. 若存在 `required_skills`，在任务说明中列出。
3. 指示 Agent 在生成初稿后调用对应 Skills。
4. 不要把 Skills 的完整 Prompt 嵌入任务输入。

示意语义：

```text
Required skills: $human-writing, $humanizer
Use them after the factual draft and before writing the final JSON.
```

在创建 `item_writing` 任务时增加：

```python
metadata={
    "required_skills": ["human-writing", "humanizer"],
    "skill_mode": "chinese_technical_rewrite_then_ai_pattern_audit",
}
```

在创建 `issue_synthesis` 任务时同样增加。

不要给 `fact_extraction`、`relevance_review` 和 `fact_check` 添加润色 Skills。

---

## 10. 修改 item-writing Prompt

修改：

```text
prompts/item-writing.md
```

保留现有事实、长度、字段完整性和来源要求。

新增原则：

1. 先根据 facts 写出事实正确的初稿。
2. 初稿完成后调用 `$human-writing`，只润色标题和五个自然语言字段。
3. 再调用 `$humanizer` 做审查，不允许增加材料中没有的事实。
4. 技术名词、项目名、缩写、数字、基线和条件必须原样保留或准确转述。
5. 一个句子只承担一个主要判断。
6. 优先写清楚“谁做了什么、为什么有用”，再写缩写和机制。
7. 不用字段名、冒号和括号堆叠代替正常中文句子。
8. 最终仍返回现有 `brief-item.schema.json` 要求的 JSON。

不增加单独的 `item_polish` 任务。现有 `fact_check` 位于 `item_writing` 之后，可以继续校验润色后的事实一致性。

---

## 11. 重构 issue-synthesis Schema

修改：

```text
schemas/issue-synthesis.schema.json
```

将：

```json
"judgements": ["string"]
```

改为结构化对象数组。

目标结构：

```json
{
  "headline": "string",
  "judgements": [
    {
      "title": "string",
      "body": "string",
      "evidence_item_ids": ["brief_item_id"]
    }
  ],
  "topic_names": ["string"],
  "watch_next": ["string"]
}
```

建议约束：

```text
judgements: 1～3条
title: 非空短标题
body: 至少一个完整句子
evidence_item_ids: 1～4个，uniqueItems=true
watch_next: 0～3条
```

不要把某个具体技术案例写死在 Schema 或 Prompt 中。

允许一期只有一个核心条目时生成一条判断。不要保持当前 `minItems: 2` 的硬限制。

---

## 12. issue_synthesis 任务输入带上条目 ID

修改：

```text
briefing_skill/pipeline.py
```

当前 `_maybe_prepare_issue()` 传给 synthesis 的 `items` 只是条目 JSON，缺少用于精确引用的 `brief_item_id`。

构造 `synthesis_items` 时加入：

```text
brief_item_id
topic_id
direction_id
score
item_role
```

只传入 `core` 条目，保持当前“不读取 observation 和热点雷达”的规则。

任务输入应至少包含：

```text
issue_id
items[]
  brief_item_id
  title
  topic_id
  topic_name
  core_conclusion
  mechanism
  result
  boundary
  project_relevance
  score
max_judgements
audience
```

---

## 13. 修改 issue-synthesis Prompt

修改：

```text
prompts/issue-synthesis.md
```

要求：

1. 判断必须来自多个最终入选条目的共同趋势、机制、工程后果或不确定性。
2. 不得把项目名加冒号后复制单条摘要。
3. 不得把条目标题作为判断正文的开头。
4. 先给出读者能理解的判断，再说明依据。
5. 使用自然中文，不使用数据库字段拼接式表达。
6. 每条判断返回准确的 `evidence_item_ids`。
7. 只能引用任务输入中存在的 `brief_item_id`。
8. 完成事实初稿后调用 `$human-writing`。
9. 再调用 `$humanizer` 做AI痕迹审查。
10. 不新增事实、数字、技术因果或来源中没有的判断依据。
11. 返回 JSON only。

Prompt 中不要固定 LMCache、Ray Serve 或阿里云等具体示例。

---

## 14. 增加 issue_synthesis 语义校验

修改：

```text
briefing_skill/tasks.py
```

新增：

```python
def issue_synthesis_validation_errors(
    output: dict[str, Any],
    input_data: dict[str, Any],
) -> list[str]:
    ...
```

至少检查：

1. `evidence_item_ids` 全部存在于任务输入。
2. ID 不重复。
3. 判断正文不包含 `对应：`。
4. 判断正文不能等于某条标题或核心结论。
5. `title` 和 `body` 不能以省略号、逗号、冒号或分号结尾。
6. `body` 至少包含一个完整句号。
7. 当输入有两个以上核心条目时，优先要求每条综合判断引用两个以上条目；若判断确实只针对单条重大变化，可允许一个，但不应所有判断都只引用一条。
8. `headline` 不得只是“本期筛选出N条信息”之类流程状态描述。

在 `TaskService.sync()` 中为 `issue_synthesis` 调用该校验器。

校验失败时沿用当前行为：

```text
task status → INVALID
用户修正输出或重新运行 Agent
```

---

## 15. EmailService 使用精确 ID，不再猜引用

修改：

```text
briefing_skill/emailer.py
```

重写 `_judgement_refs()` 的新格式处理：

```text
judgement.title
judgement.body
judgement.evidence_item_ids
```

建立：

```python
items_by_id = {
    item["brief_item_id"]: item
}
```

根据 `evidence_item_ids` 直接映射链接。

返回给模板的对象：

```text
title
text
refs[]
```

保留对旧字符串版 `judgements` 的兼容分支即可，但新运行不再使用模糊别名、英文 token 和 topic cue 猜测。

旧兼容代码可以单独放到：

```python
_legacy_judgement_refs()
```

避免新旧逻辑混在一起。

---

## 16. 修改邮件模板

修改：

```text
templates/email.html
```

本期判断区域改成：

```text
序号
判断标题
判断正文
相关解读链接
```

不要再显示：

```text
对应：
```

可改为更自然且弱化的：

```text
相关解读：
```

也可以只显示条目链接，不显示标签。

模板应读取：

```text
judgement.title
judgement.text
judgement.refs
```

不要从判断正文中重复显示项目名称。

---

## 17. 修复 expanded_v2 的 rebuild-existing

这是本次必须修改的重点。

当前：

```text
briefing_skill/expanded.py::_rebuild_synthesis()
```

会把前三条内容拼成：

```text
标题：核心结论
```

必须删除这一自动拼接逻辑。

### 17.1 rebuild 后重新创建 issue_synthesis 任务

修改：

```text
briefing_skill/expanded.py
briefing_skill/cli.py
briefing_skill/tasks.py
```

`rebuild_expanded_issue()` 完成条目重新选择后：

1. 更新 `issue_items`。
2. 清除旧 `synthesis_path`。
3. 重新准备 `issue_synthesis` 输入。
4. 将现有同 ID 的 `issue_synthesis` 任务重置为 `PENDING`，并覆盖其 input。
5. 删除旧 output 文件。
6. 将 run stage 设置为：

```text
AWAITING_ISSUE_SYNTHESIS
```

7. 不立即生成 `email.html`。
8. 不直接进入 `AWAITING_APPROVAL`。

### 17.2 TaskService 支持重置现有任务

当前任务 ID 由：

```text
run_id + task_type + entity_id
```

稳定生成。`INSERT OR IGNORE` 会导致 rebuild 无法创建新的同 ID 任务。

增加一种显式重置方式，例如：

```python
TaskService.create(..., replace_existing=True)
```

或：

```python
TaskService.requeue(...)
```

语义：

- 覆盖 input、prompt、schema、priority 和 metadata；
- 状态改为 `PENDING`；
- 清空 error；
- 删除旧 output；
- 保留稳定 task ID。

普通流程仍使用当前 `INSERT OR IGNORE`，避免重复创建。

### 17.3 CLI 行为

当前：

```bash
python briefing.py rebuild-existing --run <id> --confirm-rebuild
```

完成后不应直接调用 `EmailService.build()`。

应输出：

```text
条目重选结果
当前stage
下一条Agent任务说明
```

用户或 Codex 随后执行：

```bash
python briefing.py tasks next --run <id>
# 完成 issue_synthesis JSON
python briefing.py advance --run <id>
python briefing.py render --run <id> --execute
python briefing.py validate --run <id>
```

### 17.4 删除或停用 `_rebuild_synthesis`

不要保留任何“标题 + 核心结论”的回退综合判断。

当 Agent 尚未完成 synthesis 时，系统应明确停在 `AWAITING_ISSUE_SYNTHESIS`，而不是生成看似完整但质量差的邮件。

---

# 第三部分：测试

## 18. Follow Builders 测试

新增：

```text
tests/test_follow_builders_adapter.py
```

使用本地 JSON fixture，不访问真实网络。

覆盖：

1. X Feed 正确映射字段。
2. 纯链接、极短确认式 tweet 被过滤。
3. 长技术 tweet 不因互动低而被丢弃。
4. Podcast transcript 写入本地文件。
5. transcript 不进入 `payload_json`。
6. `local_fulltext_path` 可被 `FulltextService` 读取。
7. 空 blogs 数组不报错。
8. 单个 Feed 失败不影响其他 Feed。
9. ETag 304 返回空列表。
10. 所有条目保持 B 级 discovery_only。

---

## 19. YeeKal 测试

新增：

```text
tests/test_yeekal_adapter.py
tests/fixtures/yeekal/
```

覆盖：

1. RSS 能发现近期日报页。
2. RSS 失败时回退索引页。
3. 只提取外部链接。
4. 内部导航、图片和分享链接被排除。
5. 同一 canonical URL 去重。
6. 邻近标题和说明进入 discovery summary。
7. JSON-LD、article:published_time 和 time datetime 能解析发布日期。
8. 无法确认原始发布日期时 `published_at=None`。
9. 日报日期只写 `discovered_at`。
10. 条目保持 B 级 discovery_only。
11. 技术预过滤减少不相关外链请求。
12. 不把整篇日报作为一条 raw item。

---

## 20. Synthesis 与润色测试

新增或修改：

```text
tests/test_issue_synthesis.py
tests/test_tasks.py
tests/test_email_rendering.py
tests/test_expanded.py
```

覆盖：

1. Schema 接受结构化 judgement。
2. 非法 evidence ID 被拒绝。
3. `对应：` 被拒绝。
4. 判断标题和正文不能直接复制条目标题。
5. EmailService 按 ID 建立引用，不使用模糊匹配。
6. 模板显示判断标题和正文。
7. 模板不再输出 `对应：`。
8. `rebuild-existing` 后 stage 为 `AWAITING_ISSUE_SYNTHESIS`。
9. rebuild 会重置 synthesis 任务。
10. rebuild 未完成 synthesis 时不能构建邮件。
11. 完成 synthesis 后 `advance` 能继续生成 `issue.json`。
12. Demo 输出符合新 Schema。
13. `item_writing` 和 `issue_synthesis` 的任务说明列出所需 Skills。
14. Skills metadata 不影响其他任务。

---

## 21. 需要同步更新的文件

Codex 完成实现后检查以下文件是否需要修改：

```text
SKILL.md
README.md
briefing_skill/collection.py
briefing_skill/fulltext.py
briefing_skill/pipeline.py
briefing_skill/tasks.py
briefing_skill/emailer.py
briefing_skill/expanded.py
briefing_skill/cli.py
briefing_skill/demo.py
briefing_skill/adapters/follow_builders.py
briefing_skill/adapters/yeekal.py
briefing_skill/source_metadata.py
config/sources.yaml
prompts/item-writing.md
prompts/issue-synthesis.md
schemas/issue-synthesis.schema.json
templates/email.html
tests/
```

README 和 SKILL 只需增加：

- 两个新信源的定位；
- 两个润色 Skills 的安装方式；
- Agent 在 `item_writing` 和 `issue_synthesis` 时的调用顺序；
- `rebuild-existing` 需要重新完成 synthesis 任务。

不要重写整个 README 或 SKILL。

---

# 第四部分：验收

## 22. 自动测试

执行：

```bash
python -m pytest
python briefing.py doctor
python briefing.py demo
python briefing.py validate --run latest
```

`demo` 需要更新 `briefing_skill/demo.py`，使其生成新格式的 synthesis JSON。

---

## 23. 新信源网络冒烟测试

在网络可用环境中执行：

```bash
python briefing.py collect --run source-smoke
```

然后检查：

```bash
sqlite3 workspace/briefing.sqlite \
  "select source_id,count(*) from raw_items where run_id='source-smoke' group by source_id;"
```

预期能够看到：

```text
follow_builders_x
follow_builders_podcast
follow_builders_blog（当Feed有内容时）
yeekal_daily
```

检查 Follow Builders podcast：

```bash
find workspace/runs/source-smoke/source-cache/follow-builders -type f
```

检查 YeeKal：

```bash
sqlite3 workspace/briefing.sqlite \
  "select title,original_url,published_at,discovered_at from raw_items where run_id='source-smoke' and source_id='yeekal_daily' limit 20;"
```

要求：

- `original_url` 不能是 YeeKal 日报页；
- `published_at` 不能简单等于日报日期；
- 未确认日期的项目应为 NULL，并在后续新鲜度阶段被排除。

---

## 24. 中文质量验收

完成一轮真实任务后检查：

```bash
python briefing.py tasks list --run latest
python briefing.py render --run latest --execute
```

邮件中的“本期判断”应满足：

1. 每条有独立标题和正文。
2. 不以项目名称加冒号开头。
3. 不出现“对应：”。
4. 能说明跨条目的共同变化或工程后果。
5. 读者不需要先拆解一串英文缩写才能理解。
6. 事实和项目判断分开。
7. 相关条目引用来自 `evidence_item_ids`，不是文本猜测。
8. 重建旧期次后也必须重新经过 Agent synthesis，不再自动拼接条目摘要。

单条技术解读应满足：

1. 五个正文域保持现有 300～450 字总约束。
2. 不改变项目名、数字、基线和适用条件。
3. 句子有明确主语和动作。
4. 不用括号、斜杠和名词串代替正常解释。
5. `fact_check` 仍能通过。

---

# 第五部分：不做的事情

本次明确不做：

- 不重新克隆或初始化当前仓库。
- 不建立代码基线、副本目录或迁移分支。
- 不引入 OpenAI、Anthropic、DeepSeek 等固定模型 API。
- 不修改 agently-cli 默认邮件后端。
- 不取消人工审核。
- 不降低 A 级来源门槛。
- 不把 Follow Builders 推文当作最终技术证据。
- 不把 YeeKal 摘要当作最终技术证据。
- 不直接引入 YeeKal 的 420 个 RSS 源和推送系统。
- 不新增独立 `item_polish` Python 阶段。
- 不把 human-writing 和 humanizer vendor 到仓库。
- 不写死某个项目或某段示例作为润色模板。
- 不让 renderer 截断润色和事实检查后的正文。

---

## 25. Codex 最终交付内容

Codex 完成后应返回：

1. 修改文件列表。
2. 两个新适配器的字段映射说明。
3. synthesis 数据结构变化。
4. `rebuild-existing` 新流程。
5. Skills 调用位置和顺序。
6. 自动测试结果。
7. 网络测试中无法验证的部分。
8. 一份新的 `email.html` 路径，供人工检查中文与排版。
