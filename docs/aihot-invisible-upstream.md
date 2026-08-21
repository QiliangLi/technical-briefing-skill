# AI Hot 隐形上游接入（运维说明）

对应设计：`lql_doc/热点雷达_AIHot隐形上游接入设计_20260821.md`。

## 契约摘要

AI Hot 是不可见的上游编辑与发现服务：

- 内部机器层保留真实 provider（`aihot`）、item/story ID、AI Hot URL、原始响应和内容 hash；
- 公开阅读层（邮件、归档公开 JSON、GitHub Pages）不出现任何 AI Hot 品牌、域名、栏目或 attribution；
- 每条公开 Radar 卡片只展示：公开标题、一段现成中文摘要、本系统分类、原始发布日期、原始网页站点名和 `links.original` 绝对 URL。

## 栏目与采集

连接器版本：`briefing_skill/adapters/aihot.py::AIHOT_CONNECTOR_VERSION`（当前 3）。

| Lane | 接口 | 用途 |
|---|---|---|
| selected | `GET /api/v1/items?mode=selected&window=24h&limit=50` | 主候选池 |
| all / paper | `GET /api/v1/items?mode=all&q=...`（`category=paper` 子通道） | Direction 补漏 |
| daily | `GET /api/v1/dailies/latest` | 补充遗漏条目（需 title+summary+original 三要素） |
| hot | `GET /api/v1/hot-topics` | 热点权重与 story 身份；无单条摘要不产出卡片 |

配置见 `config/sources.yaml`（`hot_topics_enabled` / `daily_enabled` 可独立关闭）。

## 冻结、缓存与幂等

- 每个 run 的全部 lane 响应与 lane 计划 hash 一起冻结在 `workspace/runs/<run_id>/source-cache/aihot/freeze.json`；重复 collect 同一 run 时直接回放冻结数据，不再请求上游；
- 冻结 run 不可变：lane 计划（配置查询变化）在冻结后发生变化的就地重采会直接报 stale-run 错误并要求新建 run——避免"新 freeze + 旧 raw_items"的 run 内状态分裂；
- 单个 lane 失败只记录错误并继续（结果与错误状态一并冻结），已成功 lane 的结果不受影响；全部 lane 失败才视为 provider 级失败；内部台账写入失败同样不清空已采集结果，错误记入 freeze 的 `ledger_error` 字段；
- 台账唯一身份为 `record_id`（绑定完整 lane key），同类型多条 query lane 命中同一 item 会各自留下审计行（存量库在 `Database.init()` 自动重建旧四列唯一约束）；
- 跨运行响应体缓存在 SQLite `source_state.payload.body`；304 时回放缓存体，新 run 不会拿到空 Radar；旧缓存无响应体时强制重新拉取；
- `radar_upstream_records` 台账按完整 lane key 记录每条观察（query/topic/direction、ETag、首次抓取时间、是否被采用、radar_id、决策原因），按 run 隔离、upsert 幂等，resume 不覆盖原始抓取身份。

## 日期与文案纪律

- Radar 新鲜度以 active run 的报告日期（issue `date_to`，按配置时区解释日末，默认 Asia/Shanghai）为唯一基准，同一冻结 run 任何时候 resume/render 结果一致；缺失或非法报告日期、非法时区配置都直接报错，绝不回退墙上时钟或 UTC；
- AI 日报日期只是内部召回边界：日报条目缺少自己的原始发布日期时，公开卡片不显示日期，绝不把日报日期伪装成原始发布日期；
- 上游 `reason`（编辑推荐理由）永不进入公开文案，只保留在内部台账；公开摘要只接受 `summary`/`description` 字段；
- 公开标题不截断：超出上限（160 字符）的标题整条淘汰；
- 同一 item 的多 lane 文案变体全部保留，直出时按 selected > daily > all > paper 顺序回退到第一个可用的中文完整句版本。

## 确定性直出

- 开关：`config/scoring.yaml` → `radar.direct_copy`（默认 true）；
- 候选合并身份顺序：story ID → item ID → 规范化原始 URL → 稳定身份（arXiv/DOI/GitHub）→ 规范化标题；
- 技术范围过滤、跨期去重（`radar_history` 的 URL、统一规范化标题、upstream item ID 与 story ID——同一事件换报道/URL/标题也无法重复发布）、深度/附录 URL 冲突排除后按确定性权重排序（hot +40 / selected +30 / daily +20 / Direction 0-20 / A 级 URL +10 / 多栏目 +5 / 24 小时内 +5）；
- 数量约束：最多 8 条、每类最多 2 条、同一 story/GitHub 项目最多 1 条；合法候选不足时允许少于 5 条并记录 underfill 原因；
- 公开文案 = 冻结上游标题 + 完整摘要（或 1-2 个连续完整句子）；run 目录 `issue/radar-direct.json` 保存每条标题与摘要的 source_field/source_text_hash/span/public_text_hash，`selection_hash` 绑定冻结输入 hash、规则版本和全部公开字段 hash；
- 发布门从冻结输入向外单向重算整条链，并以 active run 为外部锚点：freeze、radar-direct、manifest 的 `run_id` 必填且等于当前 run，active issue 的 `date_to` 必填并与数据库 `issues` 表、radar-direct 的 `reference_date` 三方一致，配置时区不可读即为失败（整套旧 run 产物复制到别的 run 目录、删除锚点字段均无法通过）；真实 freeze 文件 hash 必须与记录的 `frozen_input_sha256` 一致（含 AI Hot 条目时该 hash 必填），每条 AI Hot 卡片必须能按 item ID/URL 在 freeze 中定位到其声称的原始字段文本（支持 daily 的 `report.sections[].items` 嵌套结构和跨 lane 文案回退：定位会扫描全部同身份观察直到文本精确匹配，copy variant 记录精确 lane key），`selection_hash`（绑定 run/报告日/时区/冻结输入/持久化规则版本/含来源名在内的全部公开字段）必须存在并按记录重算一致——规则版本持久化在文档中并校验必须在显式支持集合内（顶层 `version` 即 direct-copy schema 版本），公开来源名由原始 URL 确定性重算，manifest 必须携带同一 `selection_hash` 且来源名必填（缺失即失败）；direct、manifest、DOM 三层的记录数（含空集）、radar_id 与 URL 唯一性、分类、标题、来源名、发布日期无条件逐项交叉一致，任何一层缺失/多余/重复、hash 缺失或联合篡改都使发布失败；
- 发送历史由 canonical `record_delivery` 写入跨期 story/item 身份（只投影最终邮件中以 Radar 卡片出现的 URL——`published_sources.section='radar-item'`，正文 Deep 来源和未发送的数据库残留都不会附着 Radar 身份）；内部台账状态记录在独立的 `ledger-status.json` sidecar（原子写入；每次 collect 重写：resume 成功清除错误、失败记录错误，冻结响应本身不可变）；发布门不信任 sidecar 自述——sidecar 严格校验 schema 与 `run_id`（缺失/损坏/属于其他 run 即失败），并用冻结输入推导期望记录集合与 `radar_upstream_records` 数据库实际集合精确比对，只有数据库完整时健康 sidecar 才能覆盖历史 freeze 错误；
- `issue_synthesis` 不再读取 radar_candidates，也不再生成 radar_signals；确定性 finalize 负责写入兼容的 `synthesis.radar_signals`（archive/Pages 继续可用）。

## 公开痕迹负向扫描

`briefing_skill/public_trace_scan.py` 对以下最终产物扫描 `AI HOT` / `AIHOT` / `aihot.virxact.com` / `links.aihot` / `upstream_provider` / `discovery_source`：

- 发布验证（`Renderer.validate`）：run 目录两份邮件 HTML、`issue/issue.json`、`publication-manifest.json`；
- 归档（`scripts/archive_sent_issue.py archive`）：归档公开目录六个公开文件（不含 `original/` 快照与内部 run 诊断）。

出现任何命中即发布/归档失败。源码、配置、测试 fixture 与内部台账不在扫描范围。

## 失败与降级

- AI Hot API 失败：保留其他来源，Radar 允许减量，不得复制上一期内容填充，不得在渲染阶段联网补救；
- 热点榜无法解析到单条摘要：只记录内部命中，不发布空摘要卡片，不使用 story digest 冒充单一来源摘要；
- 上游摘要非中文或不完整：尝试其他栏目同一 item 的中文摘要，仍不可用则淘汰；
- 上游更正/撤回：未发布的 run 重新 collect 产生新冻结版本；已发布归档不静默改写；
- 归档与历史重写全部走临时目录原子替换：组装、校验、痕迹扫描全部通过后才一次性换入正式目录，失败时已发布目录字节不变；交换使用每次唯一的备份名，入口先恢复上一次被中断的 stale 备份，进程崩溃后不会丢失唯一可恢复副本；
- 公开 URL 必须是具体的原始页面（绝对 http(s)、非上游域名、非站点根地址）。

## 灰度与回滚

- 回滚到旧的 Agent 写作路径：`config/scoring.yaml` 设 `radar.direct_copy: false`（`issue_synthesis` 会自动恢复注入 radar_candidates，并切换到 `prompts/issue-synthesis-legacy-radar.md`——与输入契约一致的 legacy 版本化 Prompt）；
- 建议先跑一期 shadow run：collect 后用冻结输入分别对比新旧 Radar 的信息量、重复率、类别覆盖与公开文案，再默认启用。

## 使用范围边界

AI Hot 公开规则允许个人非商业、公益非商业和组织内部使用，且不强制界面署名，但机器响应中的来源与 canonical 信息应保留。本项目：内部保留完整溯源、公开层零痕迹、不做镜像/批量导出/代理接口。若 GitHub Pages 用途转为商业、客户交付、广告赞助或持续大规模公开再分发，上线前需重新确认授权。上游规则 URL 与规则版本应记录在本文件并在变更时复查（2026-08-21 口径）。
