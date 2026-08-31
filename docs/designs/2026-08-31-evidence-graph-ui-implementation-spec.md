# Evidence 图谱 UI 像素级还原实施方案

- Status: accepted
- Created: 2026-08-31
- Last updated: 2026-08-31

## Problem and evidence

当前公开站点已经实现编辑部工作台外壳，以及 Evidence Explorer 的证据路径、Claim 清单和缺口说明，但 `#graph` 与 `#atlas` 仍只会回落到 Evidence 默认页，关系图和 Archive Atlas 没有重新接入。

本方案以 `docs/designs/图谱UI/` 下四张已选定成图为视觉证据，定义可以直接进入开发的像素级还原规则：

| 编号 | 参考图 | 原始尺寸 | 实现角色 |
| --- | --- | --- | --- |
| R1 | `ChatGPT Image 2026年8月31日 13_19_25 (1).png` | 1586×992 | 桌面默认关系图、Claim 聚焦态、详情栏和关系列表 |
| R2 | `ChatGPT Image 2026年8月31日 13_19_26 (2).png` | 1586×992 | Archive Atlas 结构浏览视图 |
| R3 | `ChatGPT Image 2026年8月31日 13_19_26 (3).png` | 1586×992 | Assumption 冲突聚焦态和证据对照详情 |
| R4 | `ChatGPT Image 2026年8月31日 13_19_26 (4).png` | 853×1844 | 约 426×922 CSS px 的 2× 移动端证据路径 |

成图是视觉基准，不是业务数据或 Schema。R1/R3 中的“示例 Claim”、关系数量、知识水位百分比和部分来源标题只用于排版；实现必须使用已发布 Archive 与 materialized knowledge 中真实存在的对象和关系。

## Goals and non-goals

### Goals

- 在 Evidence Explorer 中提供“证据链 / 关系图 / 证据缺口 / Archive Atlas”四个可深链视图。
- 在 1586×992 基准视口高保真还原 R1、R2、R3 的框架、密度、节点语言、连线语言和详情布局。
- 在 375、390、414 和 430px 宽度还原 R4 的移动证据路径，而不是压缩桌面画布。
- 关系图只投影现有显式对象和关系；缺失 Claim 显示“尚未物化”，不补写内容。
- 图谱、详情和关系列表保持同一选择状态，并支持鼠标、触控和键盘操作。
- 复用当前静态站点、设计 token、SVG 图标和已加载数据，不引入运行时生成图片或外部服务。

### Non-goals

- 不新增图数据库、服务端 API、写回能力或编辑工作流。
- 不从文本相似度、标题关键词或浏览器侧模型推断新关系。
- 不把图中示例数字、Claim、Decision 或实验结果写入知识对象。
- 不在本次实现中修改 briefing 任务顺序、知识物化 Schema 或发布流程。
- 不删除旧 Atlas 文件；完成新视图并验证前，它们继续作为可回滚资产保留。

## Constraints and invariants

### 规范优先级

当成图和已有合同不一致时，按以下顺序实施：

1. 数据真实性、来源定位和公开边界。
2. `docs/contracts/editorial-workbench-ui.md` 的共享外壳、断点与无障碍规则。
3. 本方案的尺寸、组件与交互规则。
4. 参考图中的纹理、文字换行和抗锯齿表现。

因此，桌面共享导航保持合同规定的 72px，不照抄成图中约 60px 的生成偏差；图谱页通过 103px 的紧凑页头，使四视图 Tab 仍在基准视口约 y=175 处开始。R4 顶部的系统状态栏属于手机截图外框，不进入网页 DOM。

### 证据边界

- `source → evidence` 只来自归档条目的来源 URL 或 Reader 定位。
- `evidence → idea` 只来自 `evidence_for` 与 `evidence_against`。
- `evidence → roadmap` 只来自 Roadmap 分支中显式的 `evidence_item_ids` 或证据时间线引用。
- Assumption 可以从 Idea 的 `unknowns` 或 `hypothesis` 生成只读投影节点，节点必须标注“来自 Idea 字段”，不能获得独立持久化身份。
- Claim 仅在来源对象已经提供可定位的 Claim 时成为普通节点；否则使用虚线占位节点“Claim 尚未物化”，且不绘制它到下游对象的已确认实线。
- 候选关系默认关闭；没有带规则名、规则版本和 provenance 的候选关系时，开关禁用并说明原因。
- 任一关系必须有来源对象 ID、目标对象 ID、关系类型和 provenance；缺一项则留在未解析清单，不进入图谱。

### 产品与发布边界

- GitHub Pages 页面保持只读，不出现“确认关系”“创建笔记”等不可执行按钮。
- 外部链接仅在真实 URL 存在时显示，并使用 `target="_blank" rel="noreferrer"`。
- 默认仅显示当前对象的一跳关系；第二跳最多 40 个节点、80 条边，超限时停止展开并给出说明。
- 关系图永远配套关系列表；Archive Atlas 永远显示“结构连接不表示支持或因果”的说明。
- 页面不加载 CDN 脚本，不新增遥测、Cookie 或网络请求。

## Proposed design

### 1. 路由与视图状态

Evidence 路由增加稳定的 `view` 参数：

```text
#evidence?idea=<idea_id>&view=path
#evidence?idea=<idea_id>&view=graph&node=<node_id>&depth=1&candidates=0
#evidence?idea=<idea_id>&view=gaps
#evidence?view=atlas&scope=all&mode=topic&issue=<date>&topic=<topic_id>
```

- 没有 `view` 时默认 `path`，保持现有入口行为。
- `#graph` 解析为 `#evidence?view=graph`，`#atlas` 解析为 `#evidence?view=atlas`，并保留已有 `idea` 等查询参数。
- Tab 使用普通锚点以支持复制链接、前进后退和无 JavaScript 降级；选中节点、深度、候选关系开关和 Atlas 筛选同步到 URL。
- 临时平移与缩放不写入 URL；切换 Tab 后重新执行“适应画布”。

### 2. 前端数据投影合同

新增依赖无关的 `buildEvidenceGraphModel()` 与 `buildArchiveAtlasModel()`。两个函数只接收 `app.js` 已加载的数据，返回显示模型，不读取 DOM。

```js
{
  nodes: [{ id, kind, title, subtitle, status, provenance, href, unresolved }],
  edges: [{ id, source, target, relation, confirmation, provenance }],
  focusId,
  unresolved: [{ reason, sourceRef, targetRef }],
  limits: { depth, nodeCount, edgeCount, truncated }
}
```

关系枚举固定为：

| relation | 中文标签 | 线型 | 颜色 |
| --- | --- | --- | --- |
| `declares` | 声明 | 实线 | 深蓝 |
| `supports` | 支持 | 实线 | 橄榄绿 |
| `challenges` | 挑战 | 实线 | 砖红 |
| `qualifies` | 限定 | 6/4 短虚线 | 琥珀 |
| `leads_to` | 导致 / 导向 | 实线 | 深蓝 |
| `pending` | 待确认 | 6/5 虚线 | 中性灰 |
| `contains` | 归档结构 | 实线 | 蓝灰，仅限 Atlas |

`data-contract.js` 负责参数归一化、稳定 ID 和丢弃悬空边；`workbench-view.js` 只编排视图。相同输入必须产生稳定排序与相同坐标，保证截图和重载不抖动。

### 3. 渲染架构

不增加 Cytoscape、G6、Sigma 或 D3 依赖。采用轻量混合 DOM/SVG：

- 一个绝对定位的 HTML 节点层，节点本身使用原生 `<button>` 或 `<a>`，便于换行、聚焦和读屏。
- 一个 SVG 边层，负责箭头、线型、文字标签、选中高亮和小地图。
- 两层放入同一个变换容器，共享 `translate(x, y) scale(z)`。
- `ResizeObserver` 只在容器宽度变化后重新计算锚点；平移和缩放只更新 transform，不重排节点。
- 桌面关系图使用确定性分层布局，按 `source → evidence → claim/assumption → idea/roadmap → decision` 分列；同列按对象类型、期次、稳定 ID 排序。
- 同一列使用 18px 最小垂直间距；交叉边优先通过同列排序消解，禁止随机力导向布局。
- Archive Atlas 复用旧 Atlas 的纯数据聚合思路，但重写为“期次 → Topic → 条目”的确定性泳道，不直接挂载旧 CSS 或旧全局状态。

### 4. 共享视觉 token

继续使用当前编辑部 token；图谱只新增关系线与画布 token：

```css
--graph-canvas: #fffefb;
--graph-grid: rgba(25, 51, 74, .055);
--graph-navy: #0b3f7d;
--graph-blue-muted: #6f88a5;
--graph-support: #4f8629;
--graph-challenge: #cf2d2d;
--graph-qualify: #c47a08;
--graph-pending: #858b91;
--graph-focus-ring: 0 0 0 3px rgba(11, 63, 125, .18);
```

- 页面与面板仍使用 `--page`、`--surface`、`--surface-raised`，不把生成图接近纯白的背景当作新主题。
- 所有边框为 1px；面板圆角 6px，节点圆角 5px，状态标签圆角 3px。
- 阴影只使用现有 `--shadow`；图谱节点默认无投影。
- 画布网格为两个 24px 周期的 1px 线性网格，透明度不超过 5.5%。
- 节点、关系和状态不能只靠颜色区分，必须同时使用图标、文字、边框或线型。

### 5. 桌面页面几何

基准为 1586×992，沿用 1540px 最大内容宽度和 24px 页面边距。允许截图抗锯齿导致的 1px 偏差；布局框偏差不得超过 2px。

#### 共享头部

| 区域 | 尺寸与规则 |
| --- | --- |
| 顶部导航 | 72px，高度遵守现有合同 |
| 图谱页头 | 103px；标题 42/46px；副标题 14/22px |
| 三张状态卡 | 176×64px，间距 12px；不足 1280px 时收窄而不换行 |
| 四视图 Tab | 42px；单项最小宽度 108px；选中项 3px 深蓝底线 |
| 上下文条 | 48px；内容按 24px 内距分组，组间 1px 分隔线 |

#### R1 / R3 关系图工作区

工作区使用共享边框，内部不留卡片间缝：

```text
252px 筛选栏 | minmax(0, 1fr) 画布 | 358px 详情栏
```

- 三列主体高 608px；画布最小宽 720px。
- 筛选栏内距 12px，组间 10px，分组底边线；搜索框高 34px。
- 画布工具栏位于右上角，距上/右 12px；按钮高 32px，图标按钮宽 32px，组合控件间距 6px。
- 小地图固定在右下角，尺寸 198×132px，距右/下 12px；在宽度低于 1280px 时隐藏。
- 底部关系列表与主体间距 8px，高 102px；表头 40px，首行 52px，更多行在页面向下滚动后出现。
- R3 的冲突提示放在 Tab 右上方的上下文区，最大宽 590px，高 56px；不挤压标题区。
- 详情栏标题区 48px；分组标题 14/22px；正文 12/19px；底部操作区固定在栏底，按钮高 40px。

#### R2 Archive Atlas

```text
272px 控制栏 | minmax(0, 1fr) Atlas 画布 | 344px 条目详情
```

- 列间距 12px，主体高 790px。
- 画布顶部泳道表头 42px；期次列宽 210px，Topic 列宽 330px，条目列占剩余空间。
- 每个期次组最小高 174px，组间以 1px 虚线分隔。
- 期次节点 96×58px，Topic 节点 180×58px，条目节点 178×28px，聚合节点使用相同宽度和虚线边框。
- 结构边统一蓝灰色，1px；数量必须同时显示文字，不用线宽作为唯一编码。
- 缩放与适应画布控件固定在左下角；Atlas 不显示关系类型图例。

### 6. 节点与关系组件

#### 节点

| 类型 | 默认尺寸 | 图标 | 边框与辅助规则 |
| --- | --- | --- | --- |
| 来源 / 归档条目 | 154×58px | 文档 | 深蓝实线；标题最多两行 |
| 证据记录 | 118×58px | 统计记录 | 深蓝；日期使用等宽数字 |
| Claim | 142×72px | Claim / 天平 | 深蓝；未物化时虚线并明确写出 |
| Idea | 146×72px | 灯泡 | 琥珀；当前对象加 2px 选中边框 |
| Assumption | 146×84px | 问号 | 琥珀；冲突态保持浅底，不使用整块红底 |
| Roadmap | 146×62px | 旗帜 | 橄榄绿 |
| Decision | 112×72px | 决策记录 | 紫灰，只在真实对象存在时显示 |
| Unknown / missing | 124×58px | 问号 / 警告 | 砖红虚线 |

- 节点内距 10px；图标 22px；标题 12/18px；辅助文字 11/16px。
- 节点标题超过两行时截断并提供 `title` 与详情栏完整文本。
- 当前节点使用四角 10px 取景标记；键盘焦点使用统一 focus ring。
- 非当前一跳节点降至 `opacity: .28`，文字仍保持至少 4.5:1 对比时才可显示；否则整节点隐藏。

#### 关系

- 关系线 1.5px，选中 2px；箭头 7×7px。
- 标签使用 11/16px、600 字重，位于路径中点并带 2px 画布色衬底，避免压线。
- 同一源目标的平行关系偏移 8px；反向关系使用另一侧曲线。
- 标签不得隐藏；空间不足时先隐藏非聚焦二跳关系，再截断节点，不能只留下无标签线。
- 点击边会选中对应关系列表行；键盘从节点按方向键移动到几何方向最近的相邻节点，Enter 打开详情或链接。

### 7. 交互与状态同步

- 首次进入图谱后自动聚焦 URL 中的 `node`，否则聚焦当前 Idea；画布执行一次“适应画布”。
- 单击节点更新选中态、详情栏和 URL，不触发整页重载。
- 双击节点或“展开一跳”增加到二跳；到达上限后按钮禁用并说明“已达到 40 个节点上限”。
- 鼠标滚轮仅在按住 Ctrl/⌘ 或画布已获焦时缩放，避免劫持页面滚动；缩放范围 50%–180%，步进 10%。
- 拖动画布需要从空白处开始；拖动超过 4px 后不触发背景点击。
- `适应画布`、缩小、百分比、放大、重置和展开按钮均有可见中文 `aria-label`。
- 图谱选择与列表选择双向同步，选中行使用 `aria-selected="true"`。
- R3 冲突态由同一聚焦节点同时存在 confirmed `supports` 与 `challenges` 关系触发，不由标题关键词推断。

### 8. 移动端还原

`max-width: 767px` 完全切换为 R4 的纵向路径模式，不挂载桌面图谱的平移缩放交互。

- 网页标题栏高 56px；系统时间、电量和信号不属于页面。
- 页面水平内距 15px；卡片间距 7px；面板圆角 6px。
- 知识水位摘要高 58px，第一行是图标、标题、进度条与定性/真实比例，第二行是范围和截止期次。
- 四视图 Tab 高 42px，横向滚动但隐藏滚动条；当前项始终滚入可见区域。
- 当前 Idea 卡最小高 50px，标题最多两行，整卡可进入详情。
- “证据路径”面板在 390–430px 宽时高约 335px，使用两列交错节点和可读关系标签；所有尺寸按 R4 的 2× 导出稿折半。
- 证据路径只显示当前对象最相关的前 5 条来源路径；其余进入“查看全部”关系列表。
- “筛选关系”高 44px，打开底部 sheet；sheet 使用原生 dialog，顶部有标题、关闭按钮、节点类型、关系类型、期次与候选关系开关。
- 当前节点详情与关系列表改为定义卡片；不显示桌面右侧栏和横向表格。
- 底部“在桌面查看关系图”是说明型次要入口，不伪装成能够切换设备的动作；点击后显示桌面视图使用说明。
- 360–767px 保持 R4 双列路径；320–359px 降级为单列节点和垂直关系轨，避免横向溢出。
- 所有交互目标至少 44×44px，正文不小于 14px，关系标签不小于 12px。

### 9. 文件改动与所有权

实施时按以下边界修改：

| 文件 | 职责 |
| --- | --- |
| `site/data-contract.js` | 解析 `view/node/depth/candidates`，生成稳定 ID，构建纯图谱投影并拒绝悬空边 |
| `site/app.js` | 继续加载 Archive 与 knowledge；向 Evidence 视图传递完整只读上下文 |
| `site/workbench-view.js` | 四 Tab、path/gaps/graph/atlas 视图编排和共享详情/列表渲染 |
| `site/evidence-graph.js` | DOM/SVG 图谱渲染、确定性布局、选择、平移、缩放、键盘与小地图 |
| `site/evidence-graph.css` | 图谱专用布局、节点、边、详情栏和移动路径；不覆盖其他页面 |
| `site/assets/icons.svg` | 仅补充不存在的节点/关系符号，保持单色描边 |
| `tests/test_public_intelligence_lab.py` | 路由、DOM 合同、数据真实性和脚本接入测试 |
| `tests/test_evidence_graph.py` | 投影、稳定布局、悬空边、上限、冲突状态和 Atlas 聚合测试 |
| `docs/contracts/editorial-workbench-ui.md` | 实现完成后写入实际路由、文件和响应式合同 |

不在 `workbench-view.js` 中继续堆积布局算法；旧 `atlas-layout-v2.js` 和 `atlas-interaction-v3.js` 不重新接入入口，只作为行为对照。

### 10. 实施顺序

1. 先实现 route 解析、纯投影模型和 fixture，锁定真实性规则。
2. 实现四 Tab、默认 path 与 gaps 迁移，确认现有 Evidence 行为不回归。
3. 实现桌面节点/边组件和 R1 默认态，再实现选择、详情和关系列表同步。
4. 增加 R3 冲突态、候选关系和未解析关系状态。
5. 实现 R2 Archive Atlas，并与当前 archive 筛选和详情深链对齐。
6. 实现 R4 移动路径、筛选 dialog 与 320px 单列降级。
7. 完成视觉快照、无障碍、性能、全路由回归和当前合同更新。

## Compatibility and migration

- 现有 `#evidence?idea=<id>&task=<task>` 继续有效；没有 `view` 时仍显示证据链，`task` 只影响 path/gaps 内容。
- `#graph` 与 `#atlas` 从兼容别名升级为对应 Evidence 子视图，不破坏旧书签。
- Archive JSON、Reader sidecar、`knowledge/index.json`、Roadmap 与 Idea 文件不迁移。
- 不新增持久化 graph JSON。未来若需要 first-class Claim、Decision 或候选关系生命周期，必须另开 Schema/Graph Builder 设计，不能悄悄扩展本投影。
- 浏览器不支持 `ResizeObserver` 时仍显示适配首屏的静态布局，缩放按钮禁用并给出说明。

## Failure, recovery, and rollback

- 数据加载失败时保留页头和 Tab，在主区显示已有加载错误；不能渲染参考图中的示例节点。
- 聚焦 ID 不存在时回退到当前 Idea，并在详情栏显示“请求的节点不存在”。
- 图谱投影发现悬空边时将其计入未解析清单，不抛弃整张图，也不绘制到错误节点。
- 节点超过上限时按一跳、已确认、来源期次新旧、稳定 ID 的顺序裁剪，并明确显示裁剪状态。
- SVG 或布局初始化异常时自动回退到关系列表，列表仍可访问来源和目标对象。
- 回滚只需从 `site/index.html` 移除 `evidence-graph.css/js`，并让 `view=graph/atlas` 回落到现有 Evidence Path；数据文件无需回滚。

## Verification

### 自动化

- `node --check` 覆盖四个活动脚本和新增 `evidence-graph.js`。
- Python/Node fixture 验证同一输入连续构建两次得到完全一致的节点、边、排序和坐标。
- 验证悬空引用不生成边、候选关系默认不可见、缺失 Claim 不生成普通 Claim 节点。
- 验证 `#graph`、`#atlas`、四个 `view` 值、非法深度和无效节点的兼容行为。
- 验证冲突提示只在同一节点同时存在已确认支持与挑战时出现。
- 验证 Atlas 的连接全部为 `contains`，且不会出现支持、挑战或因果标签。
- 运行现有 public site 与 Atlas interaction 测试，确保其他六个页面和旧纯函数不回归。

### 视觉回归

固定浏览器、字体与 DPR 后保存以下基线：

| 基线 | 视口 | 对照 |
| --- | --- | --- |
| `evidence-graph-default` | 1586×992，DPR 1 | R1 |
| `evidence-atlas` | 1586×992，DPR 1 | R2 |
| `evidence-graph-conflict` | 1586×992，DPR 1 | R3 |
| `evidence-graph-mobile` | 430×922，DPR 2 | R4 |
| `evidence-graph-narrow` | 320×780，DPR 2 | 规则验收，无直接成图 |

- 先用结构遮罩比较导航、页头、Tab、三列、列表和面板边界：关键框线坐标误差 ≤2px。
- 再比较颜色与组件：主色 Delta E 2000 ≤3，节点尺寸误差 ≤2px，间距误差 ≤2px，字体字号与行高误差 ≤1px。
- 全页像素差异比例目标 ≤5%；中文字体抗锯齿和真实文案造成的局部差异不作为失败，布局框、颜色块和选中态必须通过。
- R1/R3 节点坐标不要求逐像素复制示例数据的位置；确定性布局、无碰撞、关系可读和聚焦对象占据同一视觉区域是验收标准。

### 手工与无障碍

- 在 1586、1440、1280、1024、768、430、414、390、375、360 和 320px 检查无横向页面溢出。
- 仅使用键盘完成：切换 Tab、选择节点、沿关系移动、打开详情、缩放和回到关系列表。
- VoiceOver 能读出节点类型、标题、状态、入边/出边数量和关系标签；SVG 边本身对读屏隐藏，由关系列表表达。
- 检查 200% 浏览器缩放、`prefers-reduced-motion`、高对比模式和触控目标。
- 真实完成一次“来源 → 证据 → Idea/Roadmap → 来源定位”的追踪，确认图谱和列表结果一致。

### 性能预算

- 不增加第三方运行时依赖。
- 40 节点 / 80 边 fixture 在目标桌面浏览器中首次布局与挂载 ≤100ms，交互更新 ≤16ms 的常见帧预算。
- 新增未压缩 JS ≤35KB，CSS ≤25KB；页面不新增图片请求。
- 画布平移缩放不触发整页 layout，不在 pointermove 中重建 DOM。

## Documentation impact

- 本方案由 `docs/README.md` 索引。
- 实现完成后更新 `docs/contracts/editorial-workbench-ui.md` 的 Evidence 路由、文件边界、移动降级、验证和回滚说明。
- 若实施中需要新增 first-class Claim、graph JSON 或候选关系写入，必须暂停并新建设计，同时更新知识物化合同、Schema 和相应测试。
- 不修改 Prompt、briefing Schema、operations 或邮件发布文档。

## Decision log

- 2026-08-31：用户提供四张生成 UI 并要求据此编写像素级还原实施方案。
- 2026-08-31：四图分别作为默认关系图、Archive Atlas、冲突态和移动端路径的视觉基准。
- 2026-08-31：共享工作台合同优先于图片生成偏差；桌面导航保持 72px，移动系统状态栏不进入页面。
- 2026-08-31：选择原生 HTML 节点加 SVG 边的混合渲染，避免新增图谱库并保留完整键盘和读屏能力。
- 2026-08-31：首版只做浏览器侧确定性投影，不新增持久化 graph JSON，也不制造未物化 Claim。
- 2026-08-31：桌面默认一跳、最多 40 节点 / 80 边；移动端使用纵向证据路径，不加载缩小版桌面画布。
