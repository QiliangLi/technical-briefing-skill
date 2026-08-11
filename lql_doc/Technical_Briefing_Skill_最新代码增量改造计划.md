# Technical Briefing Skill 增量改造计划（已归档）

这份文件曾记录早期的增量改造方案，相关实现已经经过后续多轮架构调整，不能再作为当前运行契约或依赖安装说明使用。

当前实现请以以下文件为准：

- `SKILL.md`：主流程、Agent/Skill 边界、成本与质量规则；
- `README.md`：当前架构与使用方式；
- `docs/illustrated-publication.md`：整期生图与双 HTML 发布契约；
- `config/settings.yaml`：运行时预算和策略；
- `briefing_skill/bootstrap.py`：当前 active runtime 的安装顺序与 Stage owner。

当前文字处理只在 `item_style_polish` 阶段对整期调用一次 `human-writing`；草稿写作和 `issue_synthesis` 不加载额外写作 Skill。

当前 AI 插图只使用 `ian-xiaohei-illustrations` 与项目内 Qiliang overlay/reference manifest；Guizang Social Card 仅保留为卡片/HTML 排版依赖。
