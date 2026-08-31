/* #knowledge route: the daily-briefing knowledge graph. Three lenses
 * (structure / evolution / judgements), deterministic preset coordinates from
 * knowledge/graph.json, Roadmap and Idea influence overlays, a synchronized
 * relationship list, and a layered-path fallback below 768px. The canvas is a
 * viewport onto the same display model as the list; the list is never optional. */

const KnowledgeGraphView = (() => {
  const LENS_META = [
    { id: "structure", label: "结构", note: "默认透镜：Topic 与 Direction 骨架" },
    { id: "evolution", label: "演化", note: "按期次展开 Direction 下的日报条目" },
    { id: "judgements", label: "编辑判断", note: "编辑判断与其显式证据条目" },
  ];
  const RANGE_META = [
    { id: "latest", label: "仅最近一期" },
    { id: "recent3", label: "最近三期" },
    { id: "all", label: "全部期次" },
  ];
  const UNRESOLVED_LABELS = {
    dangling_judgement_evidence: "判断引用了未发布条目",
    dangling_roadmap_evidence: "Roadmap 引用了未发布条目",
    dangling_idea_evidence: "Idea 引用了未发布条目",
    missing_item_direction: "条目缺少 Topic 或 Direction",
    missing_branch_id: "Roadmap 分支缺少稳定 branch_id",
  };
  const LENS_KINDS = {
    structure: ["topic", "direction"],
    evolution: ["topic", "direction", "item", "issue"],
    judgements: ["topic", "direction", "item", "judgement"],
  };
  const SEARCHABLE_KINDS = ["topic", "direction", "item", "judgement", "roadmap", "roadmap_branch", "idea"];

  const kindLabel = (kind) => GraphStyles.KIND_META[kind]?.label || kind;
  const relationLabel = (relation) => GraphStyles.RELATION_META[relation]?.label || relation;
  const nodeShortId = (id) => String(id || "").split(":").slice(1).join(":") || id;

  function knowledgeHref(params) {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")).toString();
    return `#knowledge${query ? `?${query}` : ""}`;
  }

  function replaceKnowledgeUrl(params) {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")).toString();
    history.replaceState(null, "", `#knowledge${query ? `?${query}` : ""}`);
    state.route = BriefingData.parseRoute(location.hash);
  }

  function watermarkMarkup(graph) {
    const archive = graph?.archive_through_issue || "暂无归档";
    const knowledge = graph?.knowledge_through_issue || "未物化";
    const digest = graph?.input_digest ? graph.input_digest.slice(7, 17) : "—";
    return `<div class="knowledge-status" aria-label="图谱新鲜度">
      <div class="status-card">${icon("calendar")}<div><span>日报结构更新至</span><strong>${esc(archive)}</strong></div></div>
      <div class="status-card positive">${icon("book")}<div><span>长期知识更新至</span><strong>${esc(knowledge)}</strong></div></div>
      <div class="status-card">${icon("source")}<div><span>构建输入摘要</span><strong>sha256:${esc(digest)}</strong></div></div>
    </div><div class="status-summary">${icon("status")}<span>两个水位独立计算：归档 ${esc(archive)} · 长期知识 ${esc(knowledge)} · 输入摘要 sha256:${esc(digest)}</span></div>`;
  }

  function metricsMarkup(model) {
    const byKind = model.stats.byKind || {};
    const metrics = [
      { label: "Topic", value: byKind.topic || 0, icon: "tag" },
      { label: "Direction", value: byKind.direction || 0, icon: "arrow" },
      { label: "日报条目", value: byKind.item || 0, icon: "claim" },
      { label: "编辑判断", value: byKind.judgement || 0, icon: "status" },
      { label: "未解析引用", value: model.stats.unresolvedCount || 0, icon: "alert", tone: (model.stats.unresolvedCount || 0) ? "negative" : "positive" },
    ];
    return `<div class="metric-strip" style="--metric-count:${metrics.length}">${metrics
      .map((row) => `<div class="metric ${esc(row.tone || "")}">${icon(row.icon)}<span class="metric-label">${esc(row.label)}</span><strong class="metric-value">${esc(row.value)}</strong></div>`)
      .join("")}</div>`;
  }

  function lensTabsMarkup(params) {
    return `<nav class="kg-lens-tabs" aria-label="知识图谱透镜">${LENS_META.map((lens) => {
      const active = lens.id === params.lens;
      const next = { ...params, lens: lens.id };
      if (lens.id === "structure") { delete next.direction; }
      return `<a href="${knowledgeHref(next)}" ${active ? 'aria-current="page"' : ""} data-lens="${lens.id}"><b>${esc(lens.label)}</b><span>${esc(lens.note)}</span></a>`;
    }).join("")}</nav>`;
  }

  function filterRow(href, label, count, active) {
    return `<a class="graph-filter-row" href="${esc(href)}" aria-current="${active}"><span>${esc(label)}</span><b>${count}</b></a>`;
  }

  function filterPanelMarkup(model, graph, params) {
    const topicNodes = (graph?.nodes || []).filter((node) => node.data.kind === "topic");
    const directionNodes = (graph?.nodes || []).filter((node) => node.data.kind === "direction");
    const overlays = new Set(text(params.overlay).split(",").filter(Boolean));
    const hidden = new Set(text(params.hide).split(",").filter(Boolean));
    const rangeLinks = RANGE_META.map((range) => filterRow(
      knowledgeHref({ ...params, range: range.id, from: "", to: "" }),
      range.label, "", params.range === range.id,
    )).join("");
    const customRange = `<div class="kg-custom-range">
      <label><span>自</span><input type="date" data-range-from value="${esc(params.from || "")}"></label>
      <label><span>至</span><input type="date" data-range-to value="${esc(params.to || "")}"></label>
      <button type="button" class="graph-control" data-apply-range>按范围筛选</button>
    </div>`;
    const topicLinks = [`<option value="">全部 Topic</option>`]
      .concat(topicNodes.map((node) => `<option value="${esc(node.data.topic_id)}" ${params.topic === node.data.topic_id ? "selected" : ""}>${esc(node.data.label)}</option>`))
      .join("");
    const directionLinks = [`<option value="">全部 Direction</option>`]
      .concat(directionNodes.map((node) => `<option value="${esc(node.data.direction_id)}" ${params.direction === node.data.direction_id ? "selected" : ""}>${esc(node.data.label)}</option>`))
      .join("");
    const lensKinds = LENS_KINDS[params.lens] || LENS_KINDS.structure;
    const kindOptions = [...lensKinds, ...(["roadmap", "roadmap_branch", "idea"].filter((kind) => overlays.has(kind === "idea" ? "idea" : "roadmap")))];
    const kindLinks = kindOptions.map((kind) => filterRow(
      knowledgeHref({ ...params, hide: hidden.has(kind) ? [...hidden].filter((value) => value !== kind).join(",") : [...hidden, kind].sort().join(",") }),
      kindLabel(kind), (model.stats.byKind[kind] || 0), !hidden.has(kind),
    )).join("");
    return `<aside class="graph-filter-panel kg-filter-panel" aria-label="知识图谱筛选">
      <div class="graph-panel-section">
        <h3>搜索</h3>
        <input class="graph-search" type="search" data-kg-search placeholder="搜索 Topic、Direction 或条目" aria-label="搜索图谱对象" autocomplete="off">
        <div class="kg-search-results" data-kg-search-results aria-live="polite"></div>
      </div>
      <div class="graph-panel-section"><h3>透镜</h3><div class="graph-filter-list">${LENS_META.map((lens) => filterRow(knowledgeHref({ ...params, lens: lens.id }), lens.label, "", params.lens === lens.id)).join("")}</div></div>
      <div class="graph-panel-section"><h3>期次</h3><div class="graph-filter-list">${rangeLinks}</div>${customRange}</div>
      <div class="graph-panel-section"><h3>Topic</h3><select class="object-select" data-kg-topic aria-label="筛选 Topic">${topicLinks}</select></div>
      <div class="graph-panel-section"><h3>Direction</h3><select class="object-select" data-kg-direction aria-label="筛选 Direction">${directionLinks}</select></div>
      <div class="graph-panel-section"><h3>节点类型</h3><div class="graph-filter-list">${kindLinks}</div></div>
      <div class="graph-panel-section"><h3>影响叠层</h3>
        <div class="graph-filter-list">
          ${filterRow(knowledgeHref({ ...params, overlay: overlays.has("roadmap") ? [...overlays].filter((v) => v !== "roadmap").sort().join(",") : [...overlays, "roadmap"].sort().join(",") }), "Roadmap 叠层", "", overlays.has("roadmap"))}
          ${filterRow(knowledgeHref({ ...params, overlay: overlays.has("idea") ? [...overlays].filter((v) => v !== "idea").sort().join(",") : [...overlays, "idea"].sort().join(",") }), "Idea 叠层", "", overlays.has("idea"))}
        </div>
        <p class="filter-note">叠层默认关闭，避免与日报结构混成全量图。</p>
      </div>
      <div class="graph-panel-section"><h3>数据口径</h3>
        ${filterRow(knowledgeHref({ ...params, unresolved: params.unresolved === "1" ? "" : "1" }), "只看存在未解析引用", (graph?.unresolved || []).length, params.unresolved === "1")}
        <p class="filter-note">${model.limits.truncated ? `已达 ${model.limits.nodeLimit} 节点 / ${model.limits.edgeLimit} 边上限，裁剪保留聚焦一跳、显式判断与较近期次。` : "未解析引用不会绘制成已确认边。"}</p>
      </div>
    </aside>`;
  }

  function canvasPanelMarkup(model) {
    const status = model.limits.truncated
      ? `显示 ${model.limits.nodeCount}/${model.limits.totalNodeCount} 节点 · ${model.limits.edgeCount}/${model.limits.totalEdgeCount} 边（已达上限，按聚焦一跳、判断关联与期次裁剪）`
      : `${model.limits.nodeCount} 节点 · ${model.limits.edgeCount} 边`;
    return `<section class="graph-canvas-panel kg-canvas-panel" aria-label="知识图画布">
      <div class="graph-toolbar">
        <div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="fit" aria-label="适应画布">适应画布</button></div>
        <div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="out" aria-label="缩小">−</button><span class="graph-control zoom-value" data-zoom-value>100%</span><button class="graph-control" type="button" data-graph-action="in" aria-label="放大">＋</button></div>
        <div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="reset" aria-label="重置画布">↻</button></div>
      </div>
      <div class="kg-canvas-frame">
        <div class="kg-canvas" tabindex="0" data-kg-canvas role="application" aria-label="知识图谱画布，可用方向键沿关系移动，回车展开"></div>
        <div class="kg-canvas-grid" aria-hidden="true"></div>
        <span class="kg-canvas-status" data-kg-status>${esc(status)}</span>
        <div class="kg-canvas-fallback" data-kg-fallback hidden>图形渲染不可用；下方关系列表展示同一份显示模型。</div>
      </div>
    </section>`;
  }

  function nodeCounts(model, nodeId) {
    const incoming = model.edges.filter((edge) => edge.data.target === nodeId);
    const outgoing = model.edges.filter((edge) => edge.data.source === nodeId);
    return { incoming, outgoing };
  }

  function nodeDetailMarkup(model, graph, nodeId, selectedEdgeId) {
    if (selectedEdgeId) {
      const edge = model.edges.find((candidate) => candidate.data.id === selectedEdgeId);
      if (edge) {
        const nodeById = new Map(model.nodes.map((node) => [node.data.id, node]));
        const provenance = (edge.provenance || []).map((entry) => `${entry.path}${entry.field ? ` · ${entry.field}` : ""}`).join("；");
        return `<div class="graph-detail-body">
          <div class="graph-detail-section"><h3>${esc(relationLabel(edge.data.relation))}</h3>${badge("已确认关系", "positive")}</div>
          <div class="graph-detail-section">${fieldRows([
            { label: "起点", value: nodeById.get(edge.data.source)?.data.label || edge.data.source },
            { label: "终点", value: nodeById.get(edge.data.target)?.data.label || edge.data.target },
            { label: "关系", value: relationLabel(edge.data.relation) },
            { label: "Provenance", value: provenance || "已记录" },
          ])}</div>
          <div class="graph-detail-section"><p>箭头方向由关系枚举决定；本页不交换 source 与 target。</p></div>
        </div>`;
      }
    }
    const node = model.nodes.find((candidate) => candidate.data.id === nodeId) || model.nodes.find((candidate) => candidate.data.id === model.focusId);
    if (!node) return emptyState("没有节点详情", "当前筛选下没有可查看对象。", "question");
    const data = node.data;
    const { incoming, outgoing } = nodeCounts(model, data.id);
    const enriched = data.kind === "item" ? state.itemById.get(nodeShortId(data.id)) : null;
    const detail = enriched?.detail || enriched || {};
    const sections = [];
    sections.push(`<div class="graph-detail-section"><h3>${esc(data.label)}</h3>${badge(kindLabel(data.kind), data.kind === "judgement" ? "warning" : "neutral")}${model.requestedFocusMissing && data.id === model.focusId ? "<p>请求的节点不在当前筛选内，已回退到默认焦点。</p>" : ""}</div>`);
    const identityFields = [
      { label: "类型", value: kindLabel(data.kind) },
      { label: "稳定 ID", value: data.id },
      data.status ? { label: "状态", value: data.status } : null,
      data.role ? { label: "角色", value: data.role } : null,
      data.source_level ? { label: "来源等级", value: `Level ${data.source_level}` } : null,
      data.issue_date ? { label: "期次", value: data.issue_date } : null,
      data.first_issue_date && data.first_issue_date !== data.last_issue_date ? { label: "覆盖期次", value: `${data.first_issue_date} → ${data.last_issue_date}` } : null,
    ].filter(Boolean);
    sections.push(`<div class="graph-detail-section"><h3>身份</h3>${fieldRows(identityFields)}</div>`);
    if (data.body || data.summary) sections.push(`<div class="graph-detail-section"><h3>${data.kind === "judgement" ? "判断正文" : "摘要"}</h3><p>${esc(data.body || data.summary)}</p></div>`);
    if (data.kind === "item") {
      const itemFields = [
        detail.core_conclusion ? { label: "核心结论", value: detail.core_conclusion } : null,
        detail.mechanism ? { label: "机制", value: detail.mechanism } : null,
        detail.result ? { label: "结果", value: detail.result } : null,
        detail.boundary ? { label: "边界", value: detail.boundary } : null,
        detail.project_relevance ? { label: "项目相关性", value: detail.project_relevance } : null,
      ].filter(Boolean);
      if (itemFields.length) sections.push(`<div class="graph-detail-section"><h3>条目要点</h3>${fieldRows(itemFields)}</div>`);
      if (enriched?.url) sections.push(`<div class="graph-detail-actions"><a href="${esc(enriched.url)}" target="_blank" rel="noreferrer">打开原文 ↗</a></div>`);
    }
    if (Array.isArray(data.evidence_item_ids) && data.evidence_item_ids.length) {
      sections.push(`<div class="graph-detail-section"><h3>显式证据条目</h3><ul class="kg-evidence-list">${data.evidence_item_ids.map((ref) => {
        const item = state.itemById.get(ref);
        return `<li><a href="#archive?date=${encodeURIComponent(item?.issue_date || data.issue_date)}&item=${encodeURIComponent(ref)}">${esc(item?.title || ref)}</a></li>`;
      }).join("")}</ul></div>`);
    }
    const relationFields = [
      { label: "入边", value: `${incoming.length} 条（${[...new Set(incoming.map((edge) => relationLabel(edge.data.relation)))].join("、") || "无"}）` },
      { label: "出边", value: `${outgoing.length} 条（${[...new Set(outgoing.map((edge) => relationLabel(edge.data.relation)))].join("、") || "无"}）` },
      { label: "Provenance", value: (node.provenance || []).map((entry) => entry.path).join("；") || "已记录" },
    ];
    sections.push(`<div class="graph-detail-section"><h3>来源与影响</h3>${fieldRows(relationFields)}</div>`);
    const actions = [];
    if (data.href) actions.push(`<a href="${esc(data.href)}" ${/^https?:/i.test(data.href) ? 'target="_blank" rel="noreferrer"' : ""}>打开对象</a>`);
    if (data.kind === "topic") {
      actions.push(`<a href="${knowledgeHref({ ...state.route.params, lens: "evolution", topic: nodeShortId(data.id), node: data.id })}">查看演化</a>`);
      actions.push(`<a href="${knowledgeHref({ ...state.route.params, lens: "judgements", topic: nodeShortId(data.id), node: data.id })}">查看编辑判断</a>`);
    }
    if (data.kind === "direction") {
      actions.push(`<a href="${knowledgeHref({ ...state.route.params, lens: "evolution", direction: data.direction_id, node: data.id })}">展开该方向条目</a>`);
    }
    if (data.kind === "item") actions.push(`<a href="${knowledgeHref({ ...state.route.params, lens: "judgements", node: data.id })}">查看相关判断</a>`);
    if (data.kind === "roadmap" || data.kind === "topic") actions.push(`<a href="#roadmaps?topic=${encodeURIComponent(data.topic_id || nodeShortId(data.id))}">进入 Roadmap</a>`);
    if (data.kind === "roadmap_branch") actions.push(`<a href="#roadmaps?topic=${encodeURIComponent(data.topic_id)}&branch=${encodeURIComponent(data.branch_id)}">进入 Roadmap 分支</a>`);
    if (data.kind === "idea") actions.push(`<a href="#ideas?idea=${encodeURIComponent(nodeShortId(data.id))}&view=overview">进入 Idea</a>`);
    if (actions.length) sections.push(`<div class="graph-detail-actions">${actions.join("")}</div>`);
    return `<div class="graph-detail-body">${sections.join("")}</div>`;
  }

  function relationshipTableMarkup(model, selectedEdgeId = "") {
    if (!model.edges.length) return `<div id="relationshipList" class="relationship-table">${emptyState("没有已确认关系", "当前筛选下没有可绘制关系；未解析引用不会进入图谱。", "evidence")}</div>`;
    const nodeMap = new Map(model.nodes.map((node) => [node.data.id, node]));
    return `<div id="relationshipList" class="relationship-table"><table><thead><tr><th style="width:26%">来源对象</th><th style="width:13%">关系</th><th style="width:26%">目标对象</th><th style="width:10%">确认状态</th><th style="width:15%">Provenance</th><th style="width:10%">期次</th></tr></thead><tbody>${model.edges.map((edge) => {
      const source = nodeMap.get(edge.data.source);
      const target = nodeMap.get(edge.data.target);
      const provenance = (edge.provenance || [])[0] || {};
      return `<tr tabindex="0" data-relationship-id="${esc(edge.data.id)}" aria-selected="${edge.data.id === selectedEdgeId}"><td>${esc(source?.data.label || edge.data.source)}</td><td><span class="relationship-symbol ${esc(edge.data.relation)}"><i class="relation-swatch ${esc(edge.data.relation)}"></i>${esc(relationLabel(edge.data.relation))}</span></td><td>${esc(target?.data.label || edge.data.target)}</td><td>已确认</td><td>${esc(provenance.path || "已记录")}</td><td>${esc(source?.data.issue_date || target?.data.issue_date || "—")}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  }

  function unresolvedMarkup(model) {
    if (!model.unresolved.length) {
      return editorialNote("未解析引用为零", "当前发布输入中的显式引用都能定位到对象。", "");
    }
    const rows = model.unresolved.map((entry, index) => `<div class="gap-card"><b>未解析 ${index + 1}</b><span>${esc(UNRESOLVED_LABELS[entry.reason] || entry.reason)}</span><small>${esc([entry.source_ref, entry.target_ref, entry.detail].filter(Boolean).join(" · "))}</small></div>`).join("");
    return `<div class="gaps-grid">${rows}</div>`;
  }

  function mobileMarkup(model, graph) {
    const focusNode = model.nodes.find((node) => node.data.id === model.focusId) || model.nodes[0];
    const adjacency = (id) => model.edges.filter((edge) => edge.data.source === id || edge.data.target === id);
    const neighbors = focusNode ? adjacency(focusNode.data.id) : [];
    const neighborNode = (edge) => model.nodes.find((node) => node.data.id === (edge.data.source === focusNode?.data.id ? edge.data.target : edge.data.source));
    const listItem = (node, edge) => node
      ? `<li><button type="button" data-mobile-node="${esc(node.data.id)}">${icon(GraphStyles.KIND_META[node.data.kind]?.icon || "question")}<span><b>${esc(node.data.label)}</b><small>${esc(relationLabel(edge.data.relation))} · ${esc(kindLabel(node.data.kind))}</small></span>${icon("chevron")}</button></li>`
      : "";
    const recentItems = model.nodes
      .filter((node) => node.data.kind === "item")
      .sort((a, b) => text(b.data.issue_date).localeCompare(text(a.data.issue_date)))
      .slice(0, 8);
    const recentJudgements = model.nodes
      .filter((node) => node.data.kind === "judgement")
      .sort((a, b) => text(b.data.issue_date).localeCompare(text(a.data.issue_date)))
      .slice(0, 5);
    const overlayNodes = model.nodes.filter((node) => ["roadmap", "roadmap_branch", "idea"].includes(node.data.kind)).slice(0, 8);
    return `<div class="kg-mobile">
      <div class="mobile-knowledge-card"><div class="mobile-knowledge-main">${icon("status")}<b>当前焦点</b><strong>${esc(focusNode?.data.label || "未选择")}</strong></div><div class="mobile-knowledge-meta"><span>归档 ${esc(graph?.archive_through_issue || "—")}</span><span>长期知识 ${esc(graph?.knowledge_through_issue || "—")}</span></div></div>
      <button class="mobile-filter-button" type="button" data-open-mobile-filter>${icon("sliders")}<span>筛选与透镜（${model.limits.nodeCount} 节点 · ${model.limits.edgeCount} 边）</span>${icon("chevron")}</button>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>当前对象的关系</h2><span>${neighbors.length} 条</span></div><ul class="kg-mobile-list">${neighbors.length ? neighbors.slice(0, 12).map((edge) => listItem(neighborNode(edge), edge)).join("") : "<li><span class='kg-mobile-empty'>当前焦点没有可见关系，先在筛选中放宽期次或类型。</span></li>"}</ul></section>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>最近条目</h2><span>按期次倒序</span></div><ul class="kg-mobile-list">${recentItems.length ? recentItems.map((node) => `<li><a href="${esc(node.data.href || `#archive?date=${encodeURIComponent(node.data.issue_date)}`)}">${icon("claim")}<span><b>${esc(node.data.label)}</b><small>${esc(node.data.issue_date || "")}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>当前透镜不展示条目，切到“演化”透镜。</span></li>"}</ul></section>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>编辑判断</h2><span>${recentJudgements.length} 条</span></div><ul class="kg-mobile-list">${recentJudgements.length ? recentJudgements.map((node) => `<li><a href="${esc(node.data.href)}">${icon("status")}<span><b>${esc(node.data.label)}</b><small>${esc(node.data.issue_date)}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>当前透镜不展示判断，切到“编辑判断”透镜。</span></li>"}</ul></section>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>Roadmap / Idea 影响</h2><span>叠层</span></div><ul class="kg-mobile-list">${overlayNodes.length ? overlayNodes.map((node) => `<li><a href="${esc(node.data.href || "#knowledge")}">${icon(GraphStyles.KIND_META[node.data.kind]?.icon || "roadmap")}<span><b>${esc(node.data.label)}</b><small>${esc(kindLabel(node.data.kind))}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>叠层默认关闭，在筛选中打开 Roadmap 或 Idea 叠层。</span></li>"}</ul></section>
      <dialog class="mobile-filter-dialog" data-mobile-filter><div class="mobile-dialog-head"><h2>筛选与透镜</h2><button type="button" data-close-mobile-filter aria-label="关闭筛选">×</button></div><div class="mobile-dialog-body" data-mobile-filter-body></div></dialog>
    </div>`;
  }

  let activeMedia = null;

  function bindBreakpoint() {
    if (activeMedia) activeMedia.removeEventListener("change", activeMediaListener);
    if (typeof matchMedia !== "function") return;
    activeMedia = matchMedia("(min-width: 768px)");
    activeMedia.addEventListener("change", activeMediaListener);
  }

  function activeMediaListener(event) {
    // Crossing the 768px band swaps canvas vs layered-path surfaces; re-render
    // the route so the renderer mounts or unmounts cleanly.
    if (typeof renderRoute === "function") renderRoute();
  }

  function bind(model, graph, params) {
    bindBreakpoint();
    const canvas = $("[data-kg-canvas]");
    const desktop = typeof matchMedia === "function" ? matchMedia("(min-width: 768px)").matches : true;
    let handle = null;
    let selectedNodeId = model.focusId;
    let selectedEdgeId = "";

    const updateDetail = () => {
      const panel = $("[data-kg-detail]");
      if (panel) panel.innerHTML = nodeDetailMarkup(model, graph, selectedNodeId, selectedEdgeId);
      $$("[data-relationship-id]").forEach((row) => row.setAttribute("aria-selected", String(row.dataset.relationshipId === selectedEdgeId)));
    };

    if (canvas && desktop && model.nodes.length && GraphRenderer.available()) {
      handle = GraphRenderer.mountGraph(canvas, {
        nodes: model.nodes.map((node) => ({
          data: { ...node.data, label: GraphStyles.displayLabel(node.data) },
          position: node.position,
        })),
        edges: model.edges,
        layout: "preset",
        focusId: model.focusId,
        onSelectNode: (data) => {
          selectedNodeId = data.id;
          selectedEdgeId = "";
          updateDetail();
          replaceKnowledgeUrl({ ...params, node: data.id });
        },
        onSelectEdge: (data) => {
          selectedEdgeId = data.id;
          selectedNodeId = "";
          updateDetail();
        },
        onExpand: (data) => {
          const node = model.nodes.find((candidate) => candidate.data.id === data.id);
          if (!node) return;
          if (node.data.kind === "direction") go("knowledge", { ...params, lens: "evolution", direction: node.data.direction_id, node: node.data.id });
          else if (node.data.kind === "topic") go("knowledge", { ...params, lens: "evolution", topic: nodeShortId(node.data.id), node: node.data.id });
          else if (node.data.href && /^#/.test(node.data.href)) window.location.hash = node.data.href.slice(1);
        },
        onZoom: (value) => {
          const label = $("[data-zoom-value]");
          if (label) label.textContent = `${value}%`;
        },
        onFailure: () => {
          const fallback = $("[data-kg-fallback]");
          if (fallback) fallback.hidden = false;
        },
      });
      if (handle) handle.selectNode(model.focusId, false);
      else {
        const fallback = $("[data-kg-fallback]");
        if (fallback) fallback.hidden = false;
      }
    } else if (canvas) {
      const fallback = $("[data-kg-fallback]");
      if (fallback) fallback.hidden = false;
    }

    $$('[data-graph-action]').forEach((button) => button.addEventListener("click", () => {
      if (!handle) return;
      if (button.dataset.graphAction === "fit") handle.fit();
      if (button.dataset.graphAction === "in") handle.zoomBy(0.15);
      if (button.dataset.graphAction === "out") handle.zoomBy(-0.15);
      if (button.dataset.graphAction === "reset") handle.reset();
    }));

    $$("[data-relationship-id]").forEach((row) => {
      const choose = () => {
        selectedEdgeId = row.dataset.relationshipId;
        selectedNodeId = "";
        const edge = model.edges.find((candidate) => candidate.data.id === selectedEdgeId);
        if (handle && edge) handle.selectEdge(selectedEdgeId, false);
        updateDetail();
        row.scrollIntoView({ block: "nearest", behavior: "auto" });
      };
      row.addEventListener("click", choose);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          choose();
        }
      });
    });

    const searchInput = $("[data-kg-search]");
    const searchResults = $("[data-kg-search-results]");
    if (searchInput && searchResults) {
      const renderMatches = () => {
        const needle = norm(searchInput.value);
        if (!needle) {
          searchResults.innerHTML = "";
          return;
        }
        const matches = (graph?.nodes || [])
          .filter((node) => SEARCHABLE_KINDS.includes(node.data.kind) && norm(`${node.data.label} ${node.data.id}`).includes(needle))
          .slice(0, 8);
        searchResults.innerHTML = matches.length
          ? matches.map((node) => `<button type="button" class="kg-search-result" data-kg-jump="${esc(node.data.id)}">${icon(GraphStyles.KIND_META[node.data.kind]?.icon || "question")}<span><b>${esc(node.data.label)}</b><small>${esc(kindLabel(node.data.kind))}${node.data.issue_date ? ` · ${esc(node.data.issue_date)}` : ""}</small></span>${icon("chevron")}</button>`).join("")
          : "<p class='filter-note'>没有匹配对象。</p>";
        searchResults.querySelectorAll("[data-kg-jump]").forEach((button) => button.addEventListener("click", () => {
          const targetId = button.dataset.kgJump;
          searchResults.innerHTML = "";
          const lensNeedsItems = ["item", "judgement", "issue"].includes(targetId.split(":")[0]);
          const nextLens = lensNeedsItems && params.lens === "structure" ? (targetId.split(":")[0] === "judgement" ? "judgements" : "evolution") : params.lens;
          go("knowledge", { ...params, lens: nextLens, node: targetId, range: params.range === "latest" ? "recent3" : params.range });
        }));
      };
      searchInput.addEventListener("input", renderMatches);
    }

    const topicSelect = $("[data-kg-topic]");
    topicSelect?.addEventListener("change", (event) => go("knowledge", { ...params, topic: event.target.value, direction: "", node: "" }));
    const directionSelect = $("[data-kg-direction]");
    directionSelect?.addEventListener("change", (event) => go("knowledge", { ...params, direction: event.target.value, node: "" }));
    const applyRange = $("[data-apply-range]");
    applyRange?.addEventListener("click", () => {
      const from = $("[data-range-from]")?.value || "";
      const to = $("[data-range-to]")?.value || "";
      go("knowledge", { ...params, from, to, node: "" });
    });

    const mobileDialog = $("[data-mobile-filter]");
    const filterBody = $("[data-mobile-filter-body]");
    const openMobileFilter = $("[data-open-mobile-filter]");
    if (filterBody && !filterBody.childElementCount) filterBody.innerHTML = filterPanelMarkup(model, graph, params);
    openMobileFilter?.addEventListener("click", () => {
      if (filterBody) filterBody.innerHTML = filterPanelMarkup(model, graph, params);
      mobileDialog?.showModal();
    });
    $("[data-close-mobile-filter]")?.addEventListener("click", () => mobileDialog?.close());
    mobileDialog?.addEventListener("click", (event) => {
      if (event.target === mobileDialog) mobileDialog.close();
    });
    const mobileSelects = () => {
      const dialogTopic = mobileDialog?.querySelector("[data-kg-topic]");
      dialogTopic?.addEventListener("change", (event) => go("knowledge", { ...params, topic: event.target.value, direction: "", node: "" }));
      const dialogDirection = mobileDialog?.querySelector("[data-kg-direction]");
      dialogDirection?.addEventListener("change", (event) => go("knowledge", { ...params, direction: event.target.value, node: "" }));
    };
    mobileSelects();
    $$("[data-mobile-node]").forEach((button) => button.addEventListener("click", () => {
      selectedNodeId = button.dataset.mobileNode;
      selectedEdgeId = "";
      updateDetail();
      replaceKnowledgeUrl({ ...params, node: selectedNodeId });
      $$(".kg-mobile")[0]?.scrollIntoView({ block: "start", behavior: "auto" });
    }));

    updateDetail();
  }

  function render(context = {}) {
    const params = BriefingData.normalizeKnowledgeParams(state.route.params);
    const graph = context.graph || null;
    const model = BriefingData.buildKnowledgeGraphModel({ graph, params });
    if (!graph) {
      $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "知识图谱", description: "把历期日报沉淀的 Topic、Direction、条目与编辑判断连成可追溯的一张图。" })}
        ${editorialNote("图谱数据暂不可用", "knowledge/graph.json 缺失或不符合发布合同，页面不会用推测关系补图。可先浏览 Roadmap、Idea Hub 与归档。", "negative")}</div>`;
      return;
    }
    const detailAside = `<aside class="graph-detail-panel kg-detail-panel" aria-label="节点详情"><h2 class="graph-panel-title">当前详情</h2><div data-kg-detail></div></aside>`;
    const desktopWorkspace = `<div class="kg-workspace">${filterPanelMarkup(model, graph, params)}${canvasPanelMarkup(model)}${detailAside}</div>`;
    const relationshipSection = section("关系列表", relationshipTableMarkup(model), {
      note: "与画布同一份显示模型；箭头方向由关系枚举决定。",
      action: `<a class="section-action" href="#relationshipList">查看全部</a>`,
    });
    const unresolvedSection = section(`未解析引用（${model.unresolved.length}）`, unresolvedMarkup(model), { note: "缺少目标、关系类型或 provenance 的引用不会绘制成已确认边。" });
    $("#appMain").innerHTML = `<div class="page-stack kg-page">
      ${pageHeader({ title: "知识图谱", description: "把历期日报沉淀的 Topic、Direction、条目与编辑判断连成可追溯的一张图；连接表示分类、时间定位与显式引用，不表示支持或因果结论。" })}
      ${watermarkMarkup(graph)}${metricsMarkup(model)}
      ${lensTabsMarkup(params)}
      ${mobileMarkup(model, graph)}
      ${desktopWorkspace}
      ${relationshipSection}
      ${unresolvedSection}
    </div>`;
    bind(model, graph, params);
    document.querySelector(".kg-lens-tabs a[aria-current='page']")?.scrollIntoView({ block: "nearest", inline: "center" });
  }

  return { render, knowledgeHref };
})();
