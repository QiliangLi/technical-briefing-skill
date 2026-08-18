# 已发送日报归档

通过 agently 实际发出的每一期简报归档在此。每期一个目录 `issues/<日期>/`:

```
issues/2026-08-17/
  email.html    当期实发邮件(最终读者见到的版本)
  issue.json    结构化 IssueDocument(核心条目/补充条目/判断/雷达,机器可读)
  papers.json   论文级索引(图谱/论文树的生成底料)
index.json      全部期次索引(按日期排序,含各期条目计数)
```

## papers.json 字段(为图谱/论文树设计)

| 字段 | 含义 |
|---|---|
| `paper_key` | 由 URL 派生的稳定主键,同一论文跨期可 join |
| `arxiv_id` | arXiv 编号(GitHub release 等来源为空) |
| `topic_id` / `topic_name` | 所属专题(雷达条目为空,`topic_name` 存雷达分类) |
| `direction_id` | 专题内方向 |
| `role` | `core`(深度)/ `supplement`(专题补充,含重访)/ `radar`(雷达速览) |
| `revisit` | 是否为重访条目(曾在早期简报出现过) |
| `score` / `published_at` / `source_level` | 评分、论文发表日、来源级别 |
| `item_id` / `issue_date` | 条目 ID 与所属期次 |

生成图谱时:以 `paper_key` 为节点主键,`topic_id` 为专题层,`issue_date` 为时间维,`role` 区分深度/补充/雷达三种边权。

## 追加归档

发送一期后运行:

```bash
python scripts/archive_sent_issue.py --run <run_id>
```

脚本会复制实发邮件与结构化文档、重建 `papers.json`,并刷新 `index.json`。
