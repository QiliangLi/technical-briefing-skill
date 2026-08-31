/* Idea Hub 证据子视图：承接原 Evidence Path / Evidence Graph / Evidence Gaps。
 * path 是可读证据链，graph 用发布图谱投影单个 Idea 的证据审计子图，
 * gaps 只陈述 Idea 字段里的真实缺口。三个视图参数与 Idea Overview 互不丢失状态。 */

const IdeaEvidenceView = (() => {
  const kindLabel = (kind) => GraphStyles.KIND_META[kind]?.label || kind;
  const relationLabel = (relation) => GraphStyles.RELATION_META[relation]?.label || relation;
  const nodeShortId = (id) => String(id || "").split(":").slice(1).join(":") || id;

  function evidenceHref(row, params = {}) {
    const query = new URLSearchParams(Object.entries({ idea: row?.idea_id, ...params }).filter(([, value]) => value != null && value !== "")).toString();
    return `#ideas?${query}`;
  }

  function tabsMarkup(row, view, mode) {
    const tabs = [
      { href: evidenceHref(row, { view: "overview" }), label: "Overview", active: view === "overview" },
      { href: evidenceHref(row, { view: "evidence", mode: "path" }), label: "证据链", active: view === "evidence" },
      { href: evidenceHref(row, { view: "gaps" }), label: "证据缺口", active: view === "gaps" },
    ];
    return `<nav class="evidence-view-tabs" aria-label="Idea 视图">${tabs.map((tab) => `<a href="${esc(tab.href)}" ${tab.active ? 'aria-current="page"' : ""}>${esc(tab.label)}</a>`).join("")}</nav>`;
  }

  function replaceIdeaUrl(row, params) {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")).toString();
    history.replaceState(null, "", `#ideas?${query}`);
    state.route = BriefingData.parseRoute(location.hash);
  }

  function evidenceEntries(idea) {
    return [
      ...(Array.isArray(idea.evidence_for) ? idea.evidence_for.map((entry) => ({ ...entry, relation: "支持" })) : []),
      ...(Array.isArray(idea.evidence_against) ? idea.evidence_against.map((entry) => ({ ...entry, relation: "反对" })) : []),
    ];
  }

  function evidencePathMarkup(row, idea, reference) {
    const item = evidenceItem(reference);
    const source = item?.url || reference?.source_urls?.[0] || "";
    const steps = [
      { icon: "source", title: "原始来源", note: item?.title || "公开论文或工程资料", href: source },
      { icon: "trend", title: "证据记录", note: reference?.reason || "结构化提炼与归因", href: item ? issueHref(item.issue_date) : "" },
      { icon: "idea", title: "Idea Assumption", note: idea.unknowns?.[0] || idea.hypothesis || "关键假设", href: `#ideas?idea=${encodeURIComponent(row.idea_id)}&view=gaps` },
      { icon: "status", title: "系统综合判断", note: STATUS_LABELS[idea.status] || idea.status || "未知" },
      { icon: "check", title: "Decision", note: idea.decision_log?.at(-1)?.decision || "持续构建证据" },
    ];
    return `<div class="evidence-path">${steps.map((step) => `<div class="path-step">${icon(step.icon)}${step.href ? `<a href="${esc(step.href)}" ${/^https?:/i.test(step.href) ? 'target="_blank" rel="noreferrer"' : ""}><b>${esc(step.title)}</b><span>${esc(step.note)}</span></a>` : `<b>${esc(step.title)}</b><span>${esc(step.note)}</span>`}</div>`).join("")}</div>`;
  }

  function contextBar(row, idea, model, mode) {
    const percent = model.nodes.length
      ? Math.round(model.nodes.filter((node) => !node.unresolved).length / model.nodes.length * 100)
      : 0;
    return `<div class="evidence-context-bar desktop-evidence-view">
      <div class="evidence-context-item"><span>当前 Idea</span><strong>${esc(row?.title || "未选择")}</strong></div>
      <div class="evidence-context-item"><span>状态</span>${badge(STATUS_LABELS[idea?.status] || idea?.status || "未知", statusTone(idea?.status))}</div>
      <div class="evidence-context-item"><span>范围</span><strong>${mode === "graph" ? `上下游 ${model.limits.depth} 跳` : "完整证据链"}</strong></div>
      <div class="evidence-context-item"><span>证据水位</span><div class="knowledge-meter"><i style="--meter:${percent}%"></i><strong>${percent}%</strong></div></div>
      ${mode === "graph" && model.conflict ? '<div class="conflict-banner"><b>证据存在冲突</b><span>同一 Idea 同时存在已确认的支持与反对条目。</span></div>' : ""}
    </div>`;
  }

  function pathView(row, idea) {
    const entries = evidenceEntries(idea);
    const claims = entries.map((entry) => {
      const item = evidenceItem(entry);
      return { source: item?.title || entry.source_urls?.[0] || "未解析", relation: entry.relation, date: item?.issue_date || entry.issue_date || "", boundary: entry.reason || "未记录", href: item?.url || entry.source_urls?.[0] || "" };
    });
    const table = dataTable([
      { key: "source", label: "原始来源", width: "32%" },
      { key: "relation", label: "关系", width: "12%", render: (claim) => badge(claim.relation, statusTone(claim.relation)) },
      { key: "date", label: "首次进入日报", width: "15%" },
      { key: "boundary", label: "证据边界", width: "33%" },
      { key: "href", label: "入口", width: "8%", render: (claim) => claim.href ? `<a href="${esc(claim.href)}" target="_blank" rel="noreferrer">原文</a>` : "缺失" },
    ], claims, { emptyTitle: "没有可解析证据", emptyCopy: "当前 Idea 可以保留，但证据路径仍不完整。", cardTitleKey: "source" });
    return `<div class="desktop-evidence-view evidence-path-view"><div class="page-stack">
      <section class="path-surface"><h2>证据路径</h2>${evidencePathMarkup(row, idea, entries[0])}</section>
      ${section("证据记录清单", table)}
      ${editorialNote("Claim 尚未物化", "当前知识对象没有可定位的 first-class Claim；证据 reason 只作为关系说明，不冒充 Claim。", "warning")}
    </div></div>`;
  }

  function gapsView(row, idea, model) {
    const gaps = (idea.unknowns || []).length ? idea.unknowns : ["持续跟踪新的独立公开来源"];
    return `<div class="desktop-evidence-view evidence-path-view"><section class="gaps-surface"><h2>当前证据缺口</h2>
      <p>这些缺口直接来自 Idea 的 unknowns；页面不补写实验结果或推断关系。</p>
      <div class="gaps-grid">${gaps.map((gap, index) => `<article class="gap-card"><b>缺口 ${index + 1}</b><span>${esc(gap)}</span></article>`).join("")}</div>
      ${model.unresolved.length ? editorialNote("未解析关系", `${model.unresolved.length} 条引用因缺少目标对象或 provenance 未进入图谱。`, "negative") : editorialNote("关系引用完整", "当前投影中的已确认边都能定位来源和目标。")}
    </section></div>`;
  }

  function graphDetailMarkup(model, selectedId, selectedEdgeId) {
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
        </div>`;
      }
    }
    const node = model.nodes.find((candidate) => candidate.data.id === selectedId) || model.nodes.find((candidate) => candidate.data.id === model.focusId);
    if (!node) return emptyState("没有节点详情", "当前投影没有可查看对象。", "question");
    const incoming = model.edges.filter((edge) => edge.data.target === node.data.id);
    const outgoing = model.edges.filter((edge) => edge.data.source === node.data.id);
    const provenance = (node.provenance || []).map((entry) => `${entry.path}${entry.field ? ` · ${entry.field}` : ""}`).join("；");
    return `<div class="graph-detail-body">
      ${model.requestedFocusMissing && node.data.id === model.focusId ? '<div class="graph-detail-section"><p>请求的节点不存在，已回退到当前 Idea。</p></div>' : ""}
      <div class="graph-detail-section"><h3>${esc(node.data.label)}</h3>${badge(kindLabel(node.data.kind), "neutral")}</div>
      <div class="graph-detail-section"><h3>身份</h3>${fieldRows([
        { label: "类型", value: kindLabel(node.data.kind) },
        { label: "状态", value: node.data.status || "未记录" },
        ...(node.data.issue_date ? [{ label: "期次", value: node.data.issue_date }] : []),
      ])}</div>
      ${node.data.description || node.data.summary || node.data.body ? `<div class="graph-detail-section"><h3>陈述</h3><p>${esc(node.data.description || node.data.summary || node.data.body)}</p></div>` : ""}
      <div class="graph-detail-section"><h3>来源与影响</h3>${fieldRows([
        { label: "Provenance", value: provenance || "未记录" },
        { label: "入边", value: `${incoming.length} 条` },
        { label: "出边", value: `${outgoing.length} 条` },
      ])}</div>
      ${node.data.href ? `<div class="graph-detail-actions"><a href="${esc(node.data.href)}" ${/^https?:/i.test(node.data.href) ? 'target="_blank" rel="noreferrer"' : ""}>打开对象</a></div>` : ""}
    </div>`;
  }

  function relationshipTableMarkup(model, selectedEdgeId = "") {
    if (!model.edges.length) return `<div id="relationshipList" class="relationship-table">${emptyState("没有已解析关系", "未解析引用不会绘制到图谱中。", "evidence")}</div>`;
    const nodeMap = new Map(model.nodes.map((node) => [node.data.id, node]));
    return `<div id="relationshipList" class="relationship-table"><table><thead><tr><th style="width:26%">来源对象</th><th style="width:14%">关系</th><th style="width:26%">目标对象</th><th style="width:10%">确认状态</th><th style="width:14%">Provenance</th><th style="width:10%">期次</th></tr></thead><tbody>${model.edges.map((edge) => {
      const source = nodeMap.get(edge.data.source);
      const target = nodeMap.get(edge.data.target);
      const provenance = (edge.provenance || [])[0] || {};
      return `<tr tabindex="0" data-relationship-id="${esc(edge.data.id)}" aria-selected="${edge.data.id === selectedEdgeId}"><td>${esc(source?.data.label || edge.data.source)}</td><td><span class="relationship-symbol ${esc(edge.data.relation)}"><i class="relation-swatch ${esc(edge.data.relation)}"></i>${esc(relationLabel(edge.data.relation))}</span></td><td>${esc(target?.data.label || edge.data.target)}</td><td>已确认</td><td>${esc(provenance.path || provenance.field || "已记录")}</td><td>${esc(source?.data.issue_date || target?.data.issue_date || "—")}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  }

  function graphView(row, idea, model, params) {
    const depthOptions = `<div class="graph-depth-options" role="radiogroup" aria-label="展开深度">
      <label><input type="radio" name="graph-depth" value="1" ${model.limits.depth === 1 ? "checked" : ""}>1 跳</label>
      <label><input type="radio" name="graph-depth" value="2" ${model.limits.depth === 2 ? "checked" : ""}>2 跳</label>
    </div>`;
    return `<div class="desktop-evidence-view"><div class="graph-workspace">
      <aside class="graph-filter-panel" aria-label="图谱筛选">
        <div class="graph-panel-section"><h3>当前对象</h3><div class="graph-filter-row">${icon("idea")}<span>Idea：${esc(row?.title || "未选择")}</span></div>${depthOptions}</div>
        <div class="graph-panel-section"><h3>节点类型</h3><div class="graph-filter-list">${[...new Set(model.nodes.map((node) => node.data.kind))].map((kind) => `<div class="graph-filter-row">${icon(GraphStyles.KIND_META[kind]?.icon || "question")}<span>${esc(kindLabel(kind))}</span><b>${model.nodes.filter((node) => node.data.kind === kind).length}</b></div>`).join("")}</div></div>
        <div class="graph-panel-section"><h3>关系类型</h3><div class="graph-filter-list">${[...new Set(model.edges.map((edge) => edge.data.relation))].map((relation) => `<div class="graph-filter-row"><i class="relation-swatch ${esc(relation)}"></i><span>${esc(relationLabel(relation))}</span><b>${model.edges.filter((edge) => edge.data.relation === relation).length}</b></div>`).join("")}</div></div>
        <div class="graph-panel-section"><h3>数据口径</h3><p class="filter-note">${model.usesPublishedGraph ? "子图投影自发布图谱 knowledge/graph.json。" : "发布图谱不可用，子图直接由 Idea 显式字段构建。"}${model.limits.truncated ? ` 已按 ${model.limits.nodeCount} 节点上限裁剪。` : ""}</p></div>
      </aside>
      <section class="graph-canvas-panel" aria-label="关系图画布"><div class="graph-toolbar"><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="fit" aria-label="适应画布">适应画布</button></div><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="out" aria-label="缩小">−</button><span class="graph-control zoom-value" data-zoom-value>100%</span><button class="graph-control" type="button" data-graph-action="in" aria-label="放大">＋</button></div><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="reset" aria-label="重置画布">↻</button></div></div>
        <div class="graph-canvas" tabindex="0" data-graph-canvas aria-label="Idea 证据关系图，可用方向键沿关系移动"></div>
        <div class="kg-canvas-fallback" data-graph-fallback hidden>图形渲染不可用；下方关系列表展示同一份显示模型。</div>
      </section>
      <aside class="graph-detail-panel" aria-label="节点详情"><h2 class="graph-panel-title">当前节点详情</h2><div data-graph-detail>${graphDetailMarkup(model, model.focusId, "")}</div></aside>
    </div>${relationshipTableMarkup(model)}</div>`;
  }

  function mobileMarkup(row, idea, model, view, mode) {
    const entries = evidenceEntries(idea);
    return `<div class="mobile-evidence-view">
      <a class="mobile-focus-card" href="#ideas?idea=${encodeURIComponent(row.idea_id)}&view=overview">${icon("idea")}<div><b>当前 Idea：${esc(row.title)}</b><span>${view === "evidence" ? `证据视图 · ${mode === "graph" ? `上下游 ${model.limits.depth} 跳` : "完整证据链"}` : "证据缺口"} · 状态：${esc(STATUS_LABELS[idea.status] || idea.status)}</span></div>${icon("chevron")}</a>
      ${view === "gaps" ? "" : `<section class="mobile-path-card"><div class="mobile-card-head"><h2>证据路径</h2><span>${entries.length} 条证据</span></div>${evidencePathMarkup(row, idea, entries[0])}</section>`}
      <section class="mobile-relation-card"><div class="mobile-card-head"><h2>关系列表 <small>（展示前 8 条）</small></h2><a href="#relationshipList">查看全部</a></div>${model.edges.length ? `<ul class="kg-mobile-list">${model.edges.slice(0, 8).map((edge) => {
        const source = model.nodes.find((node) => node.data.id === edge.data.source);
        const target = model.nodes.find((node) => node.data.id === edge.data.target);
        return `<li><span class="mobile-relation-row"><i class="relation-swatch ${esc(edge.data.relation)}"></i><span>${esc(source?.data.label || edge.data.source)}　→ ${esc(relationLabel(edge.data.relation))} →　${esc(target?.data.label || edge.data.target)}</span></span></li>`;
      }).join("")}</ul>` : '<p class="filter-note">当前没有已解析关系。</p>'}</section>
      ${view === "graph" ? `<button class="desktop-help-button" type="button" data-desktop-help>${icon("monitor")}<span>在桌面查看交互关系图</span></button>` : ""}
    </div>`;
  }

  function bindGraph(row, idea, model, params) {
    const canvas = $("[data-graph-canvas]");
    if (!canvas) return;
    let handle = null;
    let selectedNodeId = model.focusId;
    let selectedEdgeId = "";
    const updateDetail = () => {
      const panel = $("[data-graph-detail]");
      if (panel) panel.innerHTML = graphDetailMarkup(model, selectedNodeId, selectedEdgeId);
      $$("[data-relationship-id]").forEach((entry) => entry.setAttribute("aria-selected", String(entry.dataset.relationshipId === selectedEdgeId)));
    };
    if (GraphRenderer.available() && model.nodes.length) {
      handle = GraphRenderer.mountGraph(canvas, {
        nodes: model.nodes,
        edges: model.edges,
        layout: model.nodes.every((node) => node.position) ? "preset" : "breadthfirst",
        focusId: model.focusId,
        onSelectNode: (data) => {
          selectedNodeId = data.id;
          selectedEdgeId = "";
          updateDetail();
          replaceIdeaUrl(row, { idea: row.idea_id, view: "evidence", mode: "graph", depth: params.depth, node: data.id });
        },
        onSelectEdge: (data) => {
          selectedEdgeId = data.id;
          selectedNodeId = "";
          updateDetail();
        },
        onZoom: (value) => {
          const label = $("[data-zoom-value]");
          if (label) label.textContent = `${value}%`;
        },
        onFailure: () => {
          const fallback = $("[data-graph-fallback]");
          if (fallback) fallback.hidden = false;
        },
      });
      if (handle) handle.selectNode(model.focusId, false);
      else $("[data-graph-fallback]") && ($("[data-graph-fallback]").hidden = false);
    } else {
      const fallback = $("[data-graph-fallback]");
      if (fallback) fallback.hidden = false;
    }
    $$('[data-graph-action]').forEach((button) => button.addEventListener("click", () => {
      if (!handle) return;
      if (button.dataset.graphAction === "fit") handle.fit();
      if (button.dataset.graphAction === "in") handle.zoomBy(0.15);
      if (button.dataset.graphAction === "out") handle.zoomBy(-0.15);
      if (button.dataset.graphAction === "reset") handle.reset();
    }));
    $$('[name="graph-depth"]').forEach((input) => input.addEventListener("change", () =>
      go("ideas", { idea: row.idea_id, view: "evidence", mode: "graph", depth: input.value })));
    $$("[data-relationship-id]").forEach((entry) => {
      const choose = () => {
        selectedEdgeId = entry.dataset.relationshipId;
        selectedNodeId = "";
        if (handle) handle.selectEdge(selectedEdgeId, false);
        updateDetail();
      };
      entry.addEventListener("click", choose);
      entry.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          choose();
        }
      });
    });
    $("[data-desktop-help]")?.addEventListener("click", () =>
      window.alert("证据关系图的平移、缩放和完整关系列表适合在宽度至少 768px 的桌面浏览器中查看。"));
    updateDetail();
  }

  function renderEvidence(row, idea, context = {}) {
    if (!row || !idea) {
      $("#appMain").innerHTML = `${pageHeader({ title: "Idea 证据视图", description: "用显式证据回答一个 Idea 为什么存在、由什么支持或反对。" })}${tabsMarkup(row, "evidence")}${emptyState("没有可聚焦的 Idea", "长期知识中尚无正式 Idea。", "idea")}`;
      return;
    }
    const params = BriefingData.normalizeIdeaViewParams({ ...state.route.params, idea: row.idea_id });
    const model = BriefingData.buildIdeaEvidenceGraphModel({
      ideaRow: row,
      idea,
      graph: context.graph || null,
      items: state.items,
      params,
    });
    const mode = params.mode || "path";
    const body = mode === "graph"
      ? graphView(row, idea, model, params)
      : pathView(row, idea);
    const mobile = mode === "graph" ? mobileMarkup(row, idea, model, "evidence", "graph") : "";
    $("#appMain").innerHTML = `<div class="page-stack evidence-explorer">
      ${pageHeader({ title: "Idea 证据视图", description: "追踪判断从来源、证据到 Roadmap 与 Idea 决策的完整路径。", breadcrumb: `<a href="#ideas">Idea Hub</a><span>/</span><span>${esc(row.title)}</span>` })}
      <div class="desktop-evidence-tabs">${tabsMarkup(row, "evidence", mode)}${mode === "graph" ? `<div class="segmented-tabs"><a href="${evidenceHref(row, { view: "evidence", mode: "path" })}" ${mode !== "graph" ? 'aria-current="page"' : ""}>证据链</a><a href="${evidenceHref(row, { view: "evidence", mode: "graph" })}" ${mode === "graph" ? 'aria-current="page"' : ""}>关系图</a></div>` : ""}</div>
      ${contextBar(row, idea, model, mode)}
      ${mobile}
      ${body}
    </div>`;
    if (mode === "graph") bindGraph(row, idea, model, params);
    document.querySelector(".evidence-view-tabs a[aria-current='page']")?.scrollIntoView({ block: "nearest", inline: "center" });
  }

  function renderGaps(row, idea, context = {}) {
    if (!row || !idea) {
      $("#appMain").innerHTML = `${pageHeader({ title: "Idea 证据缺口", description: "缺口只陈述 Idea 字段里的真实未知。" })}${tabsMarkup(row, "gaps")}${emptyState("没有可聚焦的 Idea", "长期知识中尚无正式 Idea。", "idea")}`;
      return;
    }
    const model = BriefingData.buildIdeaEvidenceGraphModel({
      ideaRow: row,
      idea,
      graph: context.graph || null,
      items: state.items,
      params: { idea: row.idea_id, view: "evidence", mode: "path" },
    });
    $("#appMain").innerHTML = `<div class="page-stack evidence-explorer">
      ${pageHeader({ title: "Idea 证据缺口", description: "一个 Idea 还缺什么证据、哪些假设没有被验证。", breadcrumb: `<a href="#ideas">Idea Hub</a><span>/</span><span>${esc(row.title)}</span>` })}
      <div class="desktop-evidence-tabs">${tabsMarkup(row, "gaps")}</div>
      ${mobileMarkup(row, idea, model, "gaps", "path")}
      ${gapsView(row, idea, model)}
    </div>`;
  }

  return { renderEvidence, renderGaps, tabsMarkup, evidencePathMarkup, evidenceEntries };
})();
