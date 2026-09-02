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
    const digest = graph?.input_digest || "";
    const manifest = state.manifest;
    const publication = publicationLabel();
    const pendingCount = manifest?.pending_issues?.length || 0;
    const analysisValue = manifest
      ? `${publication.label}${pendingCount ? ` · 待 ${pendingCount} 期` : ""}`
      : "清单缺失";
    const generated = graph?.generated_at ? String(graph.generated_at).replace("T", " ").slice(0, 16) : "未记录";
    return `<div class="knowledge-status" aria-label="图谱新鲜度">
      <div class="status-card">${icon("calendar")}<div><span>日报结构更新至</span><strong>${esc(archive)}</strong></div></div>
      <div class="status-card positive">${icon("book")}<div><span>长期知识更新至</span><strong>${esc(knowledge)}</strong></div></div>
      <div class="status-card ${publication.tone}">${icon("status")}<div><span>分析状态</span><strong>${esc(analysisValue)}</strong></div></div>
    </div><div class="status-summary">${icon("status")}<span>两个水位独立计算：归档 ${esc(archive)} · 长期知识 ${esc(knowledge)} · ${esc(analysisValue)}</span></div>
    <details class="kg-tech-info">
      <summary>技术信息</summary>
      <dl class="field-list">
        <div class="field-row"><dt>构建时间</dt><dd>${esc(generated)} UTC</dd></div>
        <div class="field-row"><dt>输入校验码</dt><dd><code class="kg-digest">${esc(digest || "—")}</code><button type="button" class="graph-control kg-copy-digest" data-copy-digest${digest ? "" : " disabled"}>复制</button></dd></div>
      </dl>
      <p class="filter-note">输入校验码（input digest）是构建输入的完整性校验值，不是内容摘要；用于诊断当前发布由哪些输入构建。</p>
    </details>`;
  }

  /* Global overview: topic cluster cards instead of fitting 40 nodes into a
   * narrow canvas. Clicking a topic opens its readable local graph. */
  function overviewMarkup(graph) {
    const topics = (graph?.nodes || []).filter((node) => node.data.kind === "topic");
    const directionsByTopic = new Map();
    const itemDirections = new Map();
    (graph?.edges || []).forEach((edge) => {
      const data = edge.data;
      if (data.relation === "has_direction") {
        const list = directionsByTopic.get(data.source) || [];
        list.push(data.target);
        directionsByTopic.set(data.source, list);
      }
      // has_item edges run direction → item; the source is the direction.
      if (data.relation === "has_item") itemDirections.set(data.source, (itemDirections.get(data.source) || 0) + 1);
    });
    const cards = topics.map((node) => {
      const topicId = node.data.topic_id || nodeShortId(node.data.id);
      const indexRow = (state.knowledge?.roadmaps || []).find((row) => row.topic_id === topicId);
      const directions = directionsByTopic.get(node.data.id) || [];
      const items = directions.reduce((sum, directionId) => sum + (itemDirections.get(directionId) || 0), 0);
      const lag = issueLag(indexRow?.updated_by_issue);
      const lagBadge = !indexRow?.updated_by_issue
        ? badge("未物化", "warning")
        : badge(lag ? `落后 ${lag} 期` : "同期", lag >= 3 ? "negative" : lag ? "warning" : "positive");
      return `<a class="kg-overview-card" href="${esc(knowledgeHref({ lens: "structure", topic: topicId, range: "recent3" }))}">
        <b>${esc(node.data.label)}</b>
        <span>${directions.length} 条路线 · ${items} 条已发布条目</span>
        <small>最近知识更新 ${esc(indexRow?.updated_by_issue || "未物化")}</small>
        ${lagBadge}
        <em>进入局部图 →</em>
      </a>`;
    }).join("");
    return `<section class="editorial-section kg-overview" aria-label="全局概览">
      <div class="section-head"><div><h2>全局概览</h2><p>${topics.length} 个 Topic 聚类。点击进入单个 Topic 的可读局部图；完整节点与关系列表在局部图和关系列表中提供，不做静默缺失。</p></div></div>
      <div class="kg-overview-grid">${cards}</div>
    </section>`;
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
      ? `当前范围 ${model.limits.nodeCount} / 全图 ${model.limits.totalNodeCount} 节点 · ${model.limits.edgeCount} / ${model.limits.totalEdgeCount} 边（已达上限，按聚焦一跳、判断关联与期次裁剪）`
      : `当前范围 ${model.limits.nodeCount} / 全图 ${model.limits.totalNodeCount} 节点 · ${model.limits.edgeCount} 边`;
    return `<section class="graph-canvas-panel kg-canvas-panel" aria-label="知识图画布">
      <div class="graph-toolbar">
        <div class="graph-control-group"><button class="graph-control" type="button" data-kg-toggle-filters aria-label="收起或展开筛选栏">筛选</button></div>
        <div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="focus" aria-label="聚焦当前对象">聚焦当前对象</button>${state.route.params.topic ? `<a class="graph-control" href="${esc(knowledgeHref({ lens: "structure" }))}">全局概览</a>` : ""}</div>
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
    if (data.kind === "item") sections.push(feedbackButtons("brief_item", nodeShortId(data.id)));
    return `<div class="graph-detail-body">${sections.join("")}</div>`;
  }

  /* Full relationship list with 20-row pages. Every row stays in the DOM
   * (hidden pages included) so the table remains the complete, accessible
   * source of truth; pagination only toggles visibility. */
  const RELATION_PAGE_SIZE = 20;
  function relationshipTableMarkup(model, selectedEdgeId = "") {
    if (!model.edges.length) return `<div id="relationshipList" class="relationship-table">${emptyState("没有已确认关系", "当前筛选下没有可绘制关系；未解析引用不会进入图谱。", "evidence")}</div>`;
    const nodeMap = new Map(model.nodes.map((node) => [node.data.id, node]));
    const totalPages = Math.ceil(model.edges.length / RELATION_PAGE_SIZE);
    return `<div id="relationshipList" class="relationship-table"><table><thead><tr><th style="width:26%">来源对象</th><th style="width:13%">关系</th><th style="width:26%">目标对象</th><th style="width:10%">确认状态</th><th style="width:15%">Provenance</th><th style="width:10%">期次</th></tr></thead><tbody>${model.edges.map((edge, index) => {
      const source = nodeMap.get(edge.data.source);
      const target = nodeMap.get(edge.data.target);
      const provenance = (edge.provenance || [])[0] || {};
      return `<tr tabindex="0" data-relationship-id="${esc(edge.data.id)}" data-relationship-page="${Math.floor(index / RELATION_PAGE_SIZE)}" ${index >= RELATION_PAGE_SIZE ? "hidden" : ""} aria-selected="${edge.data.id === selectedEdgeId}"><td>${esc(source?.data.label || edge.data.source)}</td><td><span class="relationship-symbol ${esc(edge.data.relation)}"><i class="relation-swatch ${esc(edge.data.relation)}"></i>${esc(relationLabel(edge.data.relation))}</span></td><td>${esc(target?.data.label || edge.data.target)}</td><td>已确认</td><td>${esc(provenance.path || "已记录")}</td><td>${esc(source?.data.issue_date || target?.data.issue_date || "—")}</td></tr>`;
    }).join("")}</tbody></table>${totalPages > 1 ? `<div class="rel-pager"><button type="button" class="graph-control" data-rel-page="prev" disabled>上一页</button><span data-rel-page-label>第 1 / ${totalPages} 页 · 共 ${model.edges.length} 条</span><button type="button" class="graph-control" data-rel-page="next">下一页</button></div>` : ""}</div>`;
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
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>当前对象的关系</h2><span>${neighbors.length} 条</span></div><ul class="kg-mobile-list">${neighbors.length ? neighbors.slice(0, 12).map((edge) => listItem(neighborNode(edge), edge)).join("") : "<li><span class='kg-mobile-empty'>当前焦点没有可见关系，先在筛选中放宽期次或类型。</span></li>"}${neighbors.length > 12 ? `<li><a href="#relationshipList"><span class='kg-mobile-empty'>在下方关系列表中查看全部 ${neighbors.length} 条（每页 ${RELATION_PAGE_SIZE} 条）。</span></a></li>` : ""}</ul></section>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>最近条目</h2><span>按期次倒序</span></div><ul class="kg-mobile-list">${recentItems.length ? recentItems.map((node) => `<li><a href="${esc(node.data.href || `#archive?date=${encodeURIComponent(node.data.issue_date)}`)}">${icon("claim")}<span><b>${esc(node.data.label)}</b><small>${esc(node.data.issue_date || "")}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>当前透镜不展示条目，切到“演化”透镜。</span></li>"}</ul></section>
      <section class="mobile-path-card"><div class="mobile-card-head"><h2>编辑判断</h2><span>${recentJudgements.length} 条</span></div><ul class="kg-mobile-list">${recentJudgements.length ? recentJudgements.map((node) => `<li><a href="${esc(node.data.href)}">${icon("status")}<span><b>${esc(node.data.label)}</b><small>${esc(node.data.issue_date)}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>当前透镜不展示判断，切到“编辑判断”透镜。</span></li>"}</ul></section>
      <details class="mobile-path-card kg-mobile-overlays"><summary class="mobile-card-head"><h2>Roadmap / Idea 影响</h2><span>叠层</span></summary><ul class="kg-mobile-list">${overlayNodes.length ? overlayNodes.map((node) => `<li><a href="${esc(node.data.href || "#knowledge")}">${icon(GraphStyles.KIND_META[node.data.kind]?.icon || "roadmap")}<span><b>${esc(node.data.label)}</b><small>${esc(kindLabel(node.data.kind))}</small></span>${icon("chevron")}</a></li>`).join("") : "<li><span class='kg-mobile-empty'>叠层默认关闭，在筛选中打开 Roadmap 或 Idea 叠层。</span></li>"}</ul></details>
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
      if (panel) {
        panel.innerHTML = nodeDetailMarkup(model, graph, selectedNodeId, selectedEdgeId);
        bindFeedbackEvents(panel);
      }
      $$("[data-relationship-id]").forEach((row) => row.setAttribute("aria-selected", String(row.dataset.relationshipId === selectedEdgeId)));
    };

    if (canvas && desktop && model.nodes.length && GraphRenderer.available()) {
      // A topic-scoped local graph uses the deterministic breadthfirst layout
      // so a handful of nodes fill the canvas at readable zoom instead of
      // preserving the whole-graph preset coordinate spread.
      const compactLocal = Boolean(params.topic) && model.nodes.length <= 12;
      handle = GraphRenderer.mountGraph(canvas, {
        nodes: model.nodes.map((node) => ({
          data: { ...node.data, label: GraphStyles.displayLabel(node.data) },
          position: node.position,
        })),
        edges: model.edges,
        layout: compactLocal ? "breadthfirst" : "preset",
        spacingFactor: compactLocal ? 0.7 : undefined,
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
      if (handle) {
        handle.selectNode(model.focusId, false);
        // A topic-scoped local graph fits its one-hop neighborhood so node
        // text stays readable; wider lenses keep the classic whole-model fit.
        if (params.topic) handle.fitFocus();
        else handle.fit();
      } else {
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
      if (button.dataset.graphAction === "focus") handle.fitFocus();
      if (button.dataset.graphAction === "in") handle.zoomBy(0.15);
      if (button.dataset.graphAction === "out") handle.zoomBy(-0.15);
      if (button.dataset.graphAction === "reset") handle.reset();
    }));

    // Desktop filter rail can be collapsed to give the canvas more width.
    $("[data-kg-toggle-filters]")?.addEventListener("click", () => {
      $(".kg-workspace")?.classList.toggle("filters-collapsed");
    });

    // Copy the raw input digest from the tech-info disclosure.
    $("[data-copy-digest]")?.addEventListener("click", async (event) => {
      const digest = state.knowledgeGraph?.input_digest || "";
      if (!digest) return;
      const button = event.currentTarget;
      try {
        await navigator.clipboard.writeText(digest);
        button.textContent = "已复制";
      } catch (_) {
        button.textContent = "复制失败";
      }
      setTimeout(() => { button.textContent = "复制"; }, 1600);
    });

    // Relationship list pagination: rows stay in the DOM; pages toggle visibility.
    const relationshipRows = () => $$("#relationshipList [data-relationship-page]");
    let relationshipPage = 0;
    const applyRelationshipPage = () => {
      const totalPages = Math.max(1, Math.ceil(relationshipRows().length / RELATION_PAGE_SIZE));
      relationshipPage = Math.min(Math.max(0, relationshipPage), totalPages - 1);
      relationshipRows().forEach((row) => { row.hidden = Number(row.dataset.relationshipPage) !== relationshipPage; });
      const label = $("[data-rel-page-label]");
      if (label) label.textContent = `第 ${relationshipPage + 1} / ${totalPages} 页`;
      const prev = $('[data-rel-page="prev"]');
      const next = $('[data-rel-page="next"]');
      if (prev) prev.disabled = relationshipPage === 0;
      if (next) next.disabled = relationshipPage >= totalPages - 1;
    };
    $('[data-rel-page="prev"]')?.addEventListener("click", () => { relationshipPage -= 1; applyRelationshipPage(); });
    $('[data-rel-page="next"]')?.addEventListener("click", () => { relationshipPage += 1; applyRelationshipPage(); });
    if (relationshipRows().length) applyRelationshipPage();

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
    if (!graph) {
      $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "知识图谱", description: "把历期日报沉淀的 Topic、Direction、条目与编辑判断连成可追溯的一张图。" })}
        ${editorialNote("图谱数据暂不可用", "knowledge/graph.json 缺失或不符合发布合同，页面不会用推测关系补图。可先浏览 Roadmap、Idea Hub 与归档。", "negative")}</div>`;
      return;
    }
    const model = BriefingData.buildKnowledgeGraphModel({ graph, params });
    // Bare #knowledge?lens=structure shows the topic-cluster overview instead
    // of fitting every Topic+Direction node into a narrow canvas. A topic
    // param (or another lens) opens the full workspace with its local graph.
    const overviewMode = params.lens === "structure" && !params.topic && !params.node;
    if (overviewMode) {
      $("#appMain").innerHTML = `<div class="page-stack kg-page">
        ${pageHeader({ title: "知识图谱", description: "先在全局概览中选择 Topic，再进入可读的局部图；连接表示分类、时间定位与显式引用，不表示支持或因果结论。" })}
        ${watermarkMarkup(graph)}${metricsMarkup(model)}
        ${lensTabsMarkup(params)}
        ${overviewMarkup(graph)}
        ${section(`未解析引用（${model.unresolved.length}）`, unresolvedMarkup(model), { note: "缺少目标、关系类型或 provenance 的引用不会绘制成已确认边。" })}
      </div>`;
      document.querySelector(".kg-lens-tabs a[aria-current='page']")?.scrollIntoView({ block: "nearest", inline: "center" });
      return;
    }
    const detailAside = `<aside class="graph-detail-panel kg-detail-panel" aria-label="节点详情"><h2 class="graph-panel-title">当前详情</h2><div data-kg-detail></div></aside>`;
    const desktopWorkspace = `<div class="kg-workspace">${filterPanelMarkup(model, graph, params)}${canvasPanelMarkup(model)}${detailAside}</div>`;
    const relationshipSection = section(`关系列表（${model.limits.edgeCount} 条）`, relationshipTableMarkup(model), {
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
