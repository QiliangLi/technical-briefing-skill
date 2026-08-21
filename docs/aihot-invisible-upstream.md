# AI Hot 隐形上游接入（运维说明）

对应设计：`lql_doc/热点雷达_AIHot隐形上游接入设计_20260821.md`。

## 契约摘要

AI Hot 是不可见的上游编辑与发现服务：

- 内部机器层保留真实 provider（`aihot`）、item/story ID、AI Hot URL、原始响应和内容 hash；
- 公开阅读层（邮件、归档公开 JSON、GitHub Pages）不出现任何 AI Hot 品牌、域名、栏目或 attribution；
- 每条公开 Radar 卡片只展示：公开标题、一段现成中文摘要、本系统分类、原始发布日期、原始网页站点名和 `links.original` 绝对 URL。

## 栏目与采集

连接器版本：`briefing_skill/adapters/aihot.py::AIHOT_CONNECTOR_VERSION`（当前 2）。

| Lane | 接口 | 用途 |
|---|---|---|
| selected | `GET /api/v1/items?mode=selected&window=24h&limit=50` | 主候选池 |
| all / paper | `GET /api/v1/items?mode=all&q=...`（`category=paper` 子通道） | Direction 补漏 |
| daily | `GET /api/v1/dailies/latest` | 补充遗漏条目（需 title+summary+original 三要素） |
| hot | `GET /api/v1/hot-topics` | 热点权重与 story 身份；无单条摘要不产出卡片 |

配置见 `config/sources.yaml`（`hot_topics_enabled` / `daily_enabled` 可独立关闭）。

## 冻结、缓存与幂等

- 每个 run 的全部 lane 响应冻结在 `workspace/runs/<run_id>/source-cache/aihot/freeze.json`；重复 collect 同一 run 时直接回放冻结数据，不再请求上游；
- 跨运行响应体缓存在 SQLite `source_state.payload.body`；304 时回放缓存体，新 run 不会拿到空 Radar；旧缓存无响应体时强制重新拉取；
- `radar_upstream_records` 台账记录每条 lane 观察（含是否被采用、radar_id、决策原因），按 run 隔离、upsert 幂等。

## 确定性直出

- 开关：`config/scoring.yaml` → `radar.direct_copy`（默认 true）；
- 候选合并身份顺序：story ID → item ID → 规范化原始 URL → 稳定身份（arXiv/DOI/GitHub）→ 规范化标题；
- 技术范围过滤、跨期去重（`radar_history`）、深度/附录 URL 冲突排除后按确定性权重排序（hot +40 / selected +30 / daily +20 / Direction 0-20 / A 级 URL +10 / 多栏目 +5 / 24 小时内 +5）；
- 数量约束：最多 8 条、每类最多 2 条、同一 story/GitHub 项目最多 1 条；合法候选不足时允许少于 5 条并记录 underfill 原因；
- 公开文案 = 冻结上游标题 + 完整摘要（或 1-2 个连续完整句子）；run 目录 `issue/radar-direct.json` 保存每条的 source_field/source_text_hash/span/public_text_hash，可机器验证发布字符全部来自冻结字段；
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
- 上游更正/撤回：未发布的 run 重新 collect 产生新冻结版本；已发布归档不静默改写。

## 灰度与回滚

- 回滚到旧的 Agent 写作路径：`config/scoring.yaml` 设 `radar.direct_copy: false`（`issue_synthesis` 会自动恢复注入 radar_candidates）；
- 建议先跑一期 shadow run：collect 后用冻结输入分别对比新旧 Radar 的信息量、重复率、类别覆盖与公开文案，再默认启用。

## 使用范围边界

AI Hot 公开规则允许个人非商业、公益非商业和组织内部使用，且不强制界面署名，但机器响应中的来源与 canonical 信息应保留。本项目：内部保留完整溯源、公开层零痕迹、不做镜像/批量导出/代理接口。若 GitHub Pages 用途转为商业、客户交付、广告赞助或持续大规模公开再分发，上线前需重新确认授权。上游规则 URL 与规则版本应记录在本文件并在变更时复查（2026-08-21 口径）。
