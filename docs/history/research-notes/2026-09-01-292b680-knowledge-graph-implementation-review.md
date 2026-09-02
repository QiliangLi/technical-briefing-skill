# `292b680` 日报知识图谱与 Idea 证据视图实现评审

- 评审日期：2026-09-01
- 评审模式：task
- 目标提交：`292b6802071489d1316563bf3149dc4b0cb638d7`
- 评审范围：`292b680^..292b680`
- 目标分支：`codex/editorial-workbench-ui`
- 提交标题：`feat: implement daily briefing knowledge graph and Idea evidence views`
- 结论：**FIX**

## 总体判断

该提交完成了 Graph Builder、`knowledge/graph.json` 发布派生物、Cytoscape.js 渲染适配层、日报知识图谱页面、Idea 证据子视图以及 Pages 发布门禁，完整测试、图谱新鲜度校验和 JavaScript 语法检查均通过。

但当前实现仍存在两个核心 UI 回归，以及图模型筛选、权威输入校验、发布触发和测试隔离方面的问题。它们会导致关系图无法从正常界面进入、移动端证据链空白、筛选后画布降级，以及格式错误的长期知识可能通过 Pages 门禁。因此本次评审结论为 `FIX`。

## Findings

### 1. 高：Idea 关系图从正常 UI 无法进入

证据：`site/idea-evidence-view.js:269` 只在当前已经是 `mode=graph` 时渲染“证据链 / 关系图”切换控件。正常进入 `view=evidence&mode=path` 后，页面没有任何指向 `mode=graph` 的链接。

浏览器复现：在 1280×800 访问：

```text
#ideas?idea=idea_08f0269ef7fd181c9968&view=evidence&mode=path
```

页面中“关系图”链接数量为 0。用户只能手写 URL，或依赖旧 `#graph` 书签进入新关系图。

影响：提交声称交付的 Idea Evidence Graph 对普通导航流程不可达，核心验收目标没有完成。

建议：无论当前是 `path` 还是 `graph`，都渲染同一组模式切换控件，并增加从 path 进入 graph 的浏览器或 DOM 合同测试。

### 2. 高：移动端 Idea 证据链为空白

证据：`site/idea-evidence-view.js:266` 仅在 `mode=graph` 时生成 `mobileMarkup()`；与此同时，`site/knowledge-graph.css:270` 在 768px 以下隐藏 `.evidence-path-view`，`site/knowledge-graph.css:279` 还隐藏 `.desktop-evidence-view`。

浏览器复现：在 375×812 访问 Idea 证据链，结果为：

```text
.evidence-path-view display: none
.mobile-evidence-view count: 0
page horizontal overflow: 0
```

可见正文只剩跳转链接和站点标题，没有证据路径、证据记录清单或移动关系列表。

影响：320、375、414px 等合同规定的移动端宽度无法使用默认 Idea 证据视图。

建议：path 模式也生成移动端证据路径和关系列表；增加 375px 下关键内容可见性的真实浏览器断言。

### 3. 中：隐藏节点类型会保留悬空边并导致图形渲染失败

证据：`site/data-contract.js:415` 从 `nodes` 中排除隐藏 kind，但 `site/data-contract.js:416` 仍使用过滤前的 `visible` 集合保留边，没有根据最终节点集合重算边。

使用当前 `knowledge/graph.json` 的模型复现：

```text
hide=topic     -> 31 nodes, 31 edges, 31 dangling edges
hide=direction ->  9 nodes, 31 edges, 31 dangling edges
```

浏览器访问 `#knowledge?lens=structure&hide=topic` 后，Cytoscape 初始化失败，页面显示“图形渲染不可用”，关系列表仍包含缺少端点的 31 条关系。

影响：页面提供的“节点类型”筛选会主动破坏渲染模型，图、详情和关系列表不再表达同一组对象。

建议：在节点 kind 过滤后创建最终节点 ID 集合，只保留 source 和 target 都存在于该集合的边；为每个可隐藏 kind 增加无悬空边断言。

### 4. 中：Topic 筛选没有约束 judgement 节点

证据：`site/data-contract.js:372-376` 按期次加入全局所有 judgement，没有检查 judgement 是否通过 `supports_judgement` 连接到当前 Topic 或 Direction 下的可见 item。

使用当前发布图谱筛选 `topic=agent_acceleration&lens=judgements&range=all` 得到：

```text
60 nodes
55 edges
24 judgement nodes
15 isolated judgement nodes
```

这 15 个孤立 judgement 来自其他 Topic，还会挤占 60 节点软上限。

影响：Topic/Direction 筛选结果混入无关编辑判断，可能进一步裁掉真正相关的节点。

建议：只加入由当前可见 item 显式连接的 judgement；演化透镜中的 issue 也应只保留与可见 item 存在 `published_in` 关系的期次。

### 5. 中：Pages 门禁没有验证权威 Knowledge 输入 Schema

证据：`briefing_skill/knowledge_graph.py:355-359` 只确认 `knowledge/index.json` 是对象；Roadmap 和 Idea 收集器也只检查加载结果是否为对象，没有执行 `knowledge-index.schema.json`、`roadmap.schema.json`、`idea.schema.json` 或对应语义校验。

`.github/workflows/pages.yml:29-38` 只运行：

```bash
python3 briefing.py knowledge graph build
python3 briefing.py knowledge graph validate
```

没有运行已有的 `python3 briefing.py knowledge validate`。

触发：Roadmap 或 Idea 文件仍是合法 JSON 对象，但缺少必填字段、身份不匹配或语义无效。

影响：Graph Builder 可能把它当作部分对象继续构图，最终生成一份符合 graph Schema、但来源数据已经无效或内容残缺的图并成功发布。

建议：Graph Builder 在构建前调用长期知识仓库验证，或在读取每个索引、Roadmap、Idea 时执行相同的 Schema 与语义校验；Pages 门禁同时显式运行 `knowledge validate`。

### 6. 中：Graph Builder 及其 Schema 变化不会触发 Pages 部署

证据：`.github/workflows/pages.yml:5-10` 的 `push.paths` 仅包含：

```text
site/**
archive/**
knowledge/**
pics/**
.github/workflows/pages.yml
```

未包含 `briefing_skill/knowledge_graph.py`、`schemas/**`、`briefing.py`、`pyproject.toml` 或依赖清单。

触发：后续提交只修复 Graph Builder 关系语义、校验器或 Schema，而没有同时改动 `site/` 或 `knowledge/`。

影响：Pages workflow 不会运行，`gh-pages` 会继续保留旧的构建结果，发布面与主分支代码合同不一致。

建议：把 Graph Builder、入口、Schema 和依赖文件加入路径过滤，或移除过窄的路径过滤。

### 7. 低：完整测试会修改跟踪中的 `knowledge/graph.json`

证据：`tests/test_knowledge_graph.py:522-527` 在仓库根目录构建图，并通过 `write_json()` 直接覆盖跟踪文件。测试过程中另一个用例删除了外部 `SOURCE_DATE_EPOCH`，因此该测试会写入当前时间。

本次完整测试结束后，工作树出现：

```text
M knowledge/graph.json
```

差异仅为 `generated_at`。评审过程中已经恢复，最终工作树保持干净。

影响：本地执行测试会制造非预期修改，容易误提交生成时间，也违反测试隔离和评审交接要求。

建议：在 `tmp_path` 中复制最小仓库 fixture 后写文件；或只在内存中构建并比较除 `generated_at` 外的稳定字段，不写回仓库。

## Verification

- `python3 -m pytest -q`：**531 passed in 147.16s**。
- 聚焦测试：`tests/test_public_intelligence_lab.py`、`tests/test_graph_surfaces.py`、`tests/test_knowledge_graph.py`、`tests/test_pages_workflow.py`，**45 passed**。
- `python3 briefing.py knowledge graph validate`：`valid: true`。
- 所有 `site/*.js` 均通过 `node --check`。
- `git diff --check 292b680^ 292b680`：通过。
- 本地浏览器验证覆盖 1280×800 和 375×812。
- 图模型复现覆盖隐藏 Topic/Direction 后的悬空边，以及 Topic judgement 过滤后的孤立节点。
- 测试造成的 `knowledge/graph.json` 时间戳改动已恢复；保存评审前工作树干净。

## Decision

```json
{
  "mode": "task",
  "target": "292b680 feat: implement daily briefing knowledge graph and Idea evidence views",
  "verdict": "FIX",
  "assessment": {
    "reason": "核心构建与测试通过，但 Idea 图入口、移动端证据链、筛选模型和发布门禁仍有可复现的实质缺陷。",
    "findings": {
      "high": 2,
      "medium": 4,
      "low": 1
    }
  }
}
```
