# Archive Reader Contract

归档同时保存两种含义不同的材料。

- `issue.json` 是机器事实和后续 Roadmap、Idea 分析的输入。
- `reader.json` 是当前 Reader Contract 下的公开表达，不能反向覆盖机器事实。
- `original/` 保存当时实际存在的邮件文件，脚本不会覆盖，也不会推断或补造缺失版本。
- 根目录 `email.html` 与 `email-illustrated.html` 是稳定的公开 URL。
- `publication-manifest.json` 记录输入、Reader Contract 和所有产物 hash。

新 run 必须已有 hash 绑定且属于当前 run 的 Reader sidecar，并同时生成两份邮件：

```bash
python3 scripts/archive_sent_issue.py archive --run 2026-08-20-094500
```

历史迁移一次只准备一期，不重跑采集、事实抽取、选择或 Fact Check：

```bash
python3 scripts/archive_sent_issue.py prepare-rewrite \
  --date 2026-08-17 \
  --output workspace/archive-rewrite/2026-08-17-input.json
```

按照输出中指定的 Prompt 和 Schema 完成语义改写后，再显式应用：

```bash
python3 scripts/archive_sent_issue.py apply-rewrite \
  --date 2026-08-17 \
  --input workspace/archive-rewrite/2026-08-17-reader.json
```

`apply-rewrite` 会拒绝条目增删、ID/角色/日期/分数/来源变化、Reader 与 Machine hash 不一致、新增数字、综合判断数量变化以及 Radar 身份变化。仅执行 `prepare-rewrite` 不会修改归档；如果没有完成语义改写，应保留旧公开文件，不能把 Machine Item 自动包装成“已迁移”的 Reader 文案。

旧归档只有一个 `email.html` 时，第一次 apply 只把这个真实文件保存为 `original/email.html`。根目录会生成完整的两份公开 Reader HTML；由于缺少可信的旧 illustrated 版本，增强版安全降级为同一份完整正文，不补造图片，也不会在后续幂等执行时把它误存成历史原件。
