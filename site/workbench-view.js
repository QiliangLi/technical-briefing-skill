/* Display models and shared editorial renderers. Source data never carries style. */
const STATUS_LABELS = {
  seed: "Seed",
  observing: "Evidence Building",
  ready_for_validation: "Ready to Validate",
  promising: "有希望",
  rejected: "已淘汰",
  proposal_candidate: "立项候选",
  emerging: "形成中",
  established: "已建立",
};
const IDEA_TYPE_LABELS = {
  research_hypothesis: "Research Hypothesis",
  solution_concept: "Solution Concept",
};

function statusTone(value = "") {
  const normalized = norm(value);
  if (/reject|fail|conflict|失效|冲突|反对/.test(normalized)) return "negative";
  if (/ready|promising|established|complete|support|materialchange|支持|进入|完成/.test(normalized)) return "positive";
  if (/seed|observe|emerging|unknown|limit|lag|warning|不足|限制|待|落后/.test(normalized)) return "warning";
  return "neutral";
}

function badge(label, tone) {
  return `<span class="status-badge ${esc(tone || statusTone(label))}">${esc(label || "未知")}</span>`;
}

function newestKnowledgeDate() {
  const dates = [
    ...(state.knowledge?.roadmaps || []).map((row) => row.updated_by_issue),
    ...(state.knowledge?.ideas || []).map((row) => row.last_updated_issue),
  ].filter(Boolean);
  return dates.sort().at(-1) || "未物化";
}

function lagCount() {
  if (!state.latest) return 0;
  const materialized = newestKnowledgeDate();
  const latestIndex = state.issues.findIndex((row) => row.date === state.latest.date);
  const materializedIndex = state.issues.findIndex((row) => row.date === materialized);
  if (materializedIndex < 0) return materialized === state.latest.date ? 0 : 1;
  return Math.max(0, latestIndex - materializedIndex);
}

function knowledgeStatusMarkup() {
  const archived = state.latest?.date || "暂无归档";
  const materialized = newestKnowledgeDate();
  const lag = lagCount();
  const lagLabel = state.knowledgeError ? "部分失败" : lag ? `落后 ${lag} 期` : "完整";
  const lagTone = state.knowledgeError ? "negative" : lag ? "warning" : "positive";
  return `<div class="knowledge-status" aria-label="知识状态">
    <div class="status-card">${icon("calendar")}<div><span>归档最新</span><strong>${esc(archived)}</strong></div></div>
    <div class="status-card positive">${icon("book")}<div><span>知识物化</span><strong>${esc(materialized)}</strong></div></div>
    <div class="status-card ${lagTone}">${icon("alert")}<div><span>同步状态</span><strong>${esc(lagLabel)}</strong></div></div>
  </div><div class="status-summary">${icon("status")}<span>归档 ${esc(archived)} · 知识 ${esc(materialized)} · ${esc(lagLabel)}</span></div>`;
}

function pageHeader({ title, description, home = false, breadcrumb = "" }) {
  return `<header class="page-header${home ? " home-header" : ""}">
    <div class="page-heading">${breadcrumb ? `<div class="breadcrumb">${breadcrumb}</div>` : ""}<h1>${esc(title)}</h1>${description ? `<p>${esc(description)}</p>` : ""}</div>
    ${knowledgeStatusMarkup()}
  </header>`;
}

function metricStrip(metrics) {
  return `<div class="metric-strip" style="--metric-count:${metrics.length}">${metrics
    .map(
      (row) => `<div class="metric ${esc(row.tone || "")}">${icon(row.icon || "status")}<span class="metric-label">${esc(row.label)}</span><strong class="metric-value">${esc(row.value)}</strong>${row.note ? `<span class="metric-note">${esc(row.note)}</span>` : ""}</div>`,
    )
    .join("")}</div>`;
}

function section(title, body, options = {}) {
  return `<section class="editorial-section ${esc(options.className || "")}">
    <div class="section-head"><div><h2>${esc(title)}</h2>${options.note ? `<p>${esc(options.note)}</p>` : ""}</div>${options.action || ""}</div>
    <div class="section-body">${body}</div>
  </section>`;
}

function emptyState(title, copy, iconName = "archive") {
  return `<div class="empty-state">${icon(iconName)}<b>${esc(title)}</b><p>${esc(copy)}</p></div>`;
}

function fieldRows(fields) {
  return `<dl class="field-list">${fields
    .filter((row) => text(row.value))
    .map((row) => `<div class="field-row"><dt>${esc(row.label)}</dt><dd>${row.html ? row.value : esc(row.value)}</dd></div>`)
    .join("")}</dl>`;
}

function dossierCard(item, options = {}) {
  const fields = (options.fields || []).filter((row) => text(row.value));
  const labels = (options.badges || []).filter(Boolean);
  return `<article class="dossier-card ${esc(options.className || "")}">
    <div class="dossier-head">${options.index != null ? `<span class="dossier-index">${esc(options.index)}</span>` : ""}<h3 class="dossier-title">${esc(item.title || item.name || "未命名对象")}</h3></div>
    ${labels.length ? `<div class="dossier-badges">${labels.map((row) => badge(row.label || row, row.tone)).join("")}</div>` : ""}
    ${item.summary ? `<p class="dossier-summary">${esc(item.summary)}</p>` : ""}
    ${fields.length ? fieldRows(fields) : ""}
    ${options.footer ? `<footer class="dossier-footer">${options.footer}</footer>` : ""}
  </article>`;
}

function dataTable(columns, rows, options = {}) {
  if (!rows.length) return emptyState(options.emptyTitle || "没有数据", options.emptyCopy || "当前公开数据中没有可展示记录。", options.emptyIcon || "claim");
  const table = `<div class="data-table-wrap"><table class="data-table"><thead><tr>${columns
    .map((column) => `<th${column.width ? ` style="width:${esc(column.width)}"` : ""}>${esc(column.label)}</th>`)
    .join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${columns.map((column) => `<td class="${column.numeric ? "numeric" : ""}">${column.render ? column.render(row) : esc(row[column.key] || "")}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
  const cards = `<div class="table-cards">${rows
    .map((row) => `<article class="definition-card"><h3>${esc(row[options.cardTitleKey || columns[0].key] || "记录")}</h3>${fieldRows(columns.slice(1).map((column) => ({ label: column.label, value: column.render ? column.render(row) : row[column.key], html: Boolean(column.render) })))}</article>`)
    .join("")}</div>`;
  return table + cards;
}

function editorialNote(title, copy, tone = "") {
  return `<div class="editorial-note ${esc(tone)}">${icon(tone === "negative" ? "alert" : tone === "warning" ? "clock" : "status")}<div><b>${esc(title)}</b><p>${esc(copy)}</p></div></div>`;
}

function quickLink(href, iconName, label, external = false) {
  return `<a class="quick-link" href="${esc(href)}" ${external ? 'target="_blank" rel="noreferrer"' : ""}>${icon(iconName)}<span>${esc(label)}</span>${icon("chevron")}</a>`;
}

function renderHome() {
  const latest = state.latest;
  const roadmaps = [...(state.knowledge?.roadmaps || [])].sort((a, b) => text(b.updated_by_issue).localeCompare(text(a.updated_by_issue)));
  const ideas = [...(state.knowledge?.ideas || [])].sort((a, b) => text(b.last_updated_issue).localeCompare(text(a.last_updated_issue)));
  const latestItems = latest?.papers || [];
  const missingSources = latestItems.filter((row) => !row.url).length;
  const changedTopics = roadmaps.filter((row) => row.updated_by_issue === latest?.date && row.change_type !== "no_material_change").length;
  const ideaChanges = ideas.filter((row) => row.last_updated_issue === latest?.date).length;
  const metrics = [
    { label: "本期期次", value: latest?.date || "暂无", note: latest ? `${latestItems.length} 条公开记录` : "等待归档", icon: "calendar" },
    { label: "发生实质变化的 Topic", value: changedTopics, note: "以长期知识更新时间为准", icon: "claim", tone: "positive" },
    { label: "新 Idea Candidate", value: 0, note: "公开数据未提供 Candidate 集合", icon: "idea", tone: "negative" },
    { label: "Idea 状态变化", value: ideaChanges, note: "较上一期的已记录变化", icon: "status" },
    { label: "异常与知识落后", value: `${missingSources} / ${lagCount()}`, note: "缺来源 / 落后期数", icon: "alert", tone: missingSources || lagCount() ? "negative" : "positive" },
  ];
  const changeRows = roadmaps.slice(0, 4).map((row) => ({
    topic: row.topic_name,
    judgment: row.summary || "暂无长期判断摘要",
    trigger: row.updated_by_issue || "未记录",
    evidence: row.change_type === "no_material_change" ? "无实质变化" : "长期知识已更新",
    roadmap: row.change_type === "no_material_change" ? "未进入" : "已进入",
    topic_id: row.topic_id,
  }));
  const changes = dataTable(
    [
      { key: "topic", label: "Topic", width: "18%", render: (row) => `<a href="#roadmaps?topic=${encodeURIComponent(row.topic_id)}"><strong>${esc(row.topic)}</strong></a>` },
      { key: "judgment", label: "当前一句话判断", width: "45%" },
      { key: "trigger", label: "更新期次", width: "13%" },
      { key: "evidence", label: "当前证据状态", width: "15%", render: (row) => badge(row.evidence, statusTone(row.evidence)) },
      { key: "roadmap", label: "Roadmap", width: "12%", render: (row) => badge(row.roadmap, statusTone(row.roadmap)) },
    ],
    changeRows,
    { emptyTitle: "本期没有实质变化", emptyCopy: "新增论文未改变已有长期判断。", cardTitleKey: "topic" },
  );
  const riskBody = `<div class="risk-list">
    <div class="risk-record ${lagCount() ? "warning" : ""}">${icon("clock")}<div><b>${lagCount() ? "知识物化落后" : "知识物化已同步"}</b><span>${lagCount() ? `长期知识落后最新归档 ${lagCount()} 期` : "归档与长期知识处于同一期"}</span></div></div>
    <div class="risk-record warning">${icon("source")}<div><b>来源记录检查</b><span>${missingSources ? `${missingSources} 条公开记录未解析到原始来源` : "本期公开记录均保留来源入口"}</span></div></div>
    <div class="risk-record">${icon("status")}<div><b>阶段判断克制</b><span>${roadmaps.length} 个 Topic 中，证据不足时继续显示 Signal Timeline</span></div></div>
  </div>`;
  const ideaBody = ideas.length
    ? `<div class="dossier-grid idea-cards" style="--card-count:${Math.min(3, ideas.length)}">${ideas.slice(0, 3).map((row, index) => {
        const object = state.ideaObjects.get(row.idea_id) || {};
        return dossierCard(
          { title: row.title, summary: object.hypothesis || object.expected_effect || "" },
          {
            index: index + 1,
            badges: [IDEA_TYPE_LABELS[row.idea_type] || row.idea_type, { label: STATUS_LABELS[row.status] || row.status, tone: statusTone(row.status) }],
            footer: `<a href="#ideas?idea=${encodeURIComponent(row.idea_id)}">查看 Idea 证据与决策 →</a>`,
          },
        );
      }).join("")}</div>`
    : emptyState("还没有正式 Idea", "长期知识物化后，正式 Idea 会在这里出现。", "idea");
  const quick = `<div class="link-matrix">${quickLink("#roadmaps", "roadmap", "查看 Roadmap")}${quickLink("#ideas", "idea", "进入 Idea Hub")}${quickLink("#evidence", "evidence", "沿证据路径阅读")}${quickLink("#archive", "archive", "浏览日报归档")}</div>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "首页", description: "把分散的证据转化为清晰的判断，驱动更好的技术决策。", home: true })}${metricStrip(metrics)}<div class="home-grid">${section("本期最重要变化", changes)}${section("风险与异常", riskBody)}${section("本期新产生或更新的 Idea", ideaBody)}${section("快速入口", quick)}</div></div>`;
}

function renderRoadmap(row, roadmap) {
  if (!row || !roadmap) {
    $("#appMain").innerHTML = `${pageHeader({ title: "Roadmap 详情", description: "阅读技术路线、判断变化与证据边界。" })}${emptyState("Roadmap 尚未物化", "系统不会用日期列表或 next_action 临时拼装替代品。", "roadmap")}`;
    return;
  }
  const branches = Array.isArray(roadmap.branches) ? roadmap.branches : [];
  const branch = branches.find((candidate) => candidate.branch_id === state.route.params.branch) || branches[0] || null;
  const viewMode = { evidence_timeline: "Signal Timeline", landscape: "Landscape", trajectory: "Trajectory" }[roadmap.view_mode] || roadmap.view_mode || "未知";
  const selector = `<select class="object-select" aria-label="选择 Roadmap" onchange="go('roadmaps',{topic:this.value})">${state.knowledge.roadmaps.map((entry) => `<option value="${esc(entry.topic_id)}" ${entry.topic_id === row.topic_id ? "selected" : ""}>${esc(entry.topic_name)}</option>`).join("")}</select>`;
  const summary = `<div class="object-summary"><div class="summary-cell"><span>Topic 名称</span>${selector}</div><div class="summary-cell"><span>当前一句话判断</span><p>${esc(roadmap.summary || row.summary || "暂无判断摘要")}</p></div><div class="summary-cell"><span>当前模式</span><strong>${esc(viewMode)}</strong></div></div>`;
  const trackCards = branches.slice(0, 6).map((track, index) => dossierCard(
    { title: track.name, summary: track.summary || "" },
    { index: index + 1, fields: [
      { label: "成熟度", value: STATUS_LABELS[track.status] || track.status || "未知" },
      { label: "证据状态", value: `${(track.evidence_item_ids || []).length} 条已发布证据` },
      { label: "主要瓶颈", value: (track.open_questions || [])[0] || "尚未记录" },
      { label: "最新出现", value: track.evidence_timeline?.at(-1)?.issue_date || roadmap.updated_by_issue },
    ], footer: `<a href="#roadmaps?topic=${encodeURIComponent(row.topic_id)}&branch=${encodeURIComponent(track.branch_id)}">查看该路线 →</a>` },
  )).join("");
  const timelineRows = branch?.stages?.length ? branch.stages : branch?.evidence_timeline || roadmap.evidence_timeline || [];
  const milestones = timelineRows.slice(-4).map((event, index, rows) => `<div class="milestone ${index === rows.length - 1 ? "current" : ""}"><b>${esc(event.name || event.title || evidenceItem(event)?.title || "证据记录")}</b><span>${esc(event.issue_date || event.first_seen_issue || roadmap.updated_by_issue || "未记录")}</span></div>`).join("");
  const refs = branch?.evidence_item_ids || branch?.evidence_timeline || [];
  const claims = refs.slice(-8).map((reference, index) => {
    const item = evidenceItem(reference);
    return { id: `Claim ${String.fromCharCode(65 + index)}`, claim: item?.title || reference.reason || "未解析的证据记录", relation: "支持或限制当前路线", strength: item ? "已发布" : "待解析", source: item?.url || reference.source_urls?.[0] || "", issue: item?.issue_date || reference.issue_date || "" };
  });
  const claimTable = dataTable([
    { key: "id", label: "Claim", width: "11%" },
    { key: "claim", label: "证据摘要", width: "44%" },
    { key: "relation", label: "判断关系", width: "18%" },
    { key: "strength", label: "状态", width: "12%", render: (claim) => badge(claim.strength, statusTone(claim.strength)) },
    { key: "source", label: "来源", width: "15%", render: (claim) => claim.source ? `<a href="${esc(claim.source)}" target="_blank" rel="noreferrer">原文 ↗</a>` : "未解析" },
  ], claims, { emptyTitle: "尚无 Claim 摘要", emptyCopy: "该路线目前只有概览，没有可映射的 Claim。", cardTitleKey: "id" });
  const main = `<div class="page-stack">${section("当前主要技术路线", `<div class="dossier-grid track-grid">${trackCards || emptyState("尚未形成稳定路线", "当前只保留可追溯的证据时间线。", "roadmap")}</div>`, { note: `${branches.length} 条路线` })}${section("真正改变判断的 Milestones", milestones ? `<div class="milestone-track" style="--milestone-count:${Math.min(4, timelineRows.length)}">${milestones}</div>` : emptyState("没有可靠 Milestone", "普通新增论文不会被包装成 Milestone。", "clock"))}${section("证据与判断（支持 / 反对 / 限制）", `${claimTable}${editorialNote("证据边界", roadmap.view_mode === "evidence_timeline" ? "当前证据不足以可靠划分技术阶段，因此只展示 Signal Timeline。" : "判断仅使用已发布日报中的公开证据。", "warning")}`)}</div>`;
  const relatedIdeas = (state.knowledge.ideas || []).filter((idea) => idea.topic_ids?.includes(row.topic_id));
  const questions = (branch?.open_questions || []).length ? `<ul>${branch.open_questions.map((question) => `<li>${esc(question)}</li>`).join("")}</ul>` : `<p>当前物化对象未记录 Open Questions。</p>`;
  const side = `<aside class="side-rail">${section("当前状态", editorialNote(viewMode, roadmap.view_mode === "evidence_timeline" ? "部分证据不足，当前只能形成可追溯的信号时间线。" : "当前模式来自长期知识对象。"))}${section("入口与来源", `<div class="side-list">${quickLink(issueHref(roadmap.updated_by_issue), "book", "进入更新期日报", true)}${(branch?.source_urls || []).slice(0, 2).map((url, index) => quickLink(url, "source", `原始来源 ${index + 1}`, true)).join("")}</div>`)}${section("相关 Idea", relatedIdeas.length ? `<div class="side-list">${relatedIdeas.map((idea) => quickLink(`#ideas?idea=${encodeURIComponent(idea.idea_id)}`, "idea", idea.title)).join("")}</div>` : emptyState("没有关联 Idea", "当前 Topic 尚未关联正式 Idea。", "idea"))}${section("Open Questions", questions)}${section("Roadmap 基本信息", fieldRows([{ label: "版本", value: `v${roadmap.version}` }, { label: "更新期次", value: roadmap.updated_by_issue }, { label: "证据范围", value: roadmap.evidence_scope }]))}</aside>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "Roadmap 详情", description: "沿主要路线、关键证据与未决问题阅读一个技术方向。" })}${summary}<div class="two-column roadmap-layout">${main}${side}</div></div>`;
}

function ideaCard(row, mode, index) {
  const object = state.ideaObjects.get(row.idea_id) || {};
  const support = object.evidence_for?.length || 0;
  const against = object.evidence_against?.length || 0;
  return dossierCard(
    { title: row.title, summary: object.hypothesis || object.problem || "" },
    {
      index,
      className: `${mode === "portfolio" ? "portfolio-card" : ""} ${mode === "validation" ? "validation-card" : ""} compact-dossier`,
      badges: [IDEA_TYPE_LABELS[row.idea_type] || row.idea_type, { label: STATUS_LABELS[row.status] || row.status, tone: statusTone(row.status) }],
      fields: [
        { label: "产生方式", value: object.decision_log?.[0]?.decision === "created" ? "已记录的系统综合" : "历史对象" },
        { label: "证据摘要", value: `支持 ${support} · 反对 ${against} · 未知 ${(object.unknowns || []).length}` },
        { label: "最大未知", value: object.unknowns?.[0] || "未记录" },
        { label: "关联 Topic", value: (row.topic_ids || []).map(topicLabel).join("、") },
      ],
      footer: `<a href="#ideas?idea=${encodeURIComponent(row.idea_id)}">查看详情与下一步 →</a>`,
    },
  );
}

function topicLabel(topicId) {
  return state.knowledge?.roadmaps?.find((row) => row.topic_id === topicId)?.topic_name || topicId;
}

function renderIdeaHub() {
  const all = state.knowledge?.ideas || [];
  const validationStatuses = new Set(["ready_for_validation", "promising", "proposal_candidate"]);
  const validation = all.filter((row) => validationStatuses.has(row.status));
  const portfolio = all.filter((row) => !validationStatuses.has(row.status));
  const candidates = [];
  const latestChanges = all.filter((row) => row.last_updated_issue === state.latest?.date).length;
  const metrics = [
    { label: "Candidate Inbox", value: candidates.length, note: "公开候选集合", icon: "idea", tone: "negative" },
    { label: "Idea Portfolio", value: portfolio.length, note: "已入库的正式 Idea", icon: "claim", tone: "positive" },
    { label: "Validation", value: validation.length, note: "已进入验证", icon: "status" },
    { label: "本期状态变化", value: latestChanges, note: "较上一期的净变化", icon: "trend", tone: "warning" },
  ];
  const column = (key, title, note, rows, emptyCopy) => `<section class="editorial-section hub-column ${key === "candidate" ? "active" : ""}" data-hub-panel="${key}"><div class="hub-column-head"><div><h2>${title}</h2><p>${note}</p></div><span class="hub-count">${rows.length}</span></div><div class="hub-stack">${rows.length ? rows.map((row, index) => ideaCard(row, key, index + 1)).join("") : emptyState(`没有${title}记录`, emptyCopy, "idea")}</div></section>`;
  const tabs = `<div class="segmented-tabs hub-tabs" role="tablist" aria-label="Idea 集合"><button role="tab" aria-selected="true" data-hub-tab="candidate">Candidate ${candidates.length}</button><button role="tab" aria-selected="false" data-hub-tab="portfolio">Portfolio ${portfolio.length}</button><button role="tab" aria-selected="false" data-hub-tab="validation">Validation ${validation.length}</button></div>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "Idea Hub", description: "查看哪些在排队、哪些已入库、哪些在验证中。" })}${metricStrip(metrics)}${tabs}<div class="idea-hub-grid">${column("candidate", "Candidate Inbox", "系统提出，尚未确认", candidates, "当前公开数据不包含 Candidate 集合；不会把正式 Idea 倒推成候选。")}${column("portfolio", "Idea Portfolio", "已接受并持续维护", portfolio, "还没有正式 Idea。")}${column("validation", "Validation", "已经进入验证", validation, "当前没有 Idea 进入验证；建议不会冒充已执行实验。")}</div>${editorialNote("状态说明", "Candidate 与正式 Idea 使用独立集合；证据不足、来源不独立或与已有 Idea 相似时会明确说明。")}</div>`;
  $$("[data-hub-tab]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-hub-tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab === button)));
    $$("[data-hub-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.hubPanel === button.dataset.hubTab));
  }));
}

function renderIdeaDetail(row, idea) {
  if (!row || !idea) {
    renderIdeaHub();
    return;
  }
  const evidence = [...(idea.evidence_for || []).map((entry) => ({ ...entry, relation: "支持" })), ...(idea.evidence_against || []).map((entry) => ({ ...entry, relation: "反对" }))];
  const sources = new Set(evidence.flatMap((entry) => entry.source_urls || []));
  const origin = idea.decision_log?.[0];
  const latestDecision = idea.decision_log?.at(-1);
  const overview = `<section class="editorial-section idea-overview"><h2>${esc(idea.title)}</h2><div class="idea-meta-grid">${fieldRows([
    { label: "Idea 类型", value: IDEA_TYPE_LABELS[idea.idea_type] || idea.idea_type },
    { label: "当前状态", value: badge(STATUS_LABELS[idea.status] || idea.status, statusTone(idea.status)), html: true },
    { label: "产生方式", value: origin?.decision === "created" ? "已记录的系统综合" : "历史 Seed，产生方式未记录" },
    { label: "Origin Event", value: origin?.reason || "未记录" },
    { label: "证据成熟度", value: `${evidence.length} 条 Claim · ${sources.size} 个独立来源` },
    { label: "当前决策摘要", value: latestDecision?.reason || "尚无决策摘要" },
  ])}</div></section>`;
  const definition = section("Idea 内容", fieldRows([
    { label: "问题", value: idea.problem },
    { label: "机制", value: idea.mechanism },
    { label: "目标", value: idea.hypothesis },
    { label: "预期效果", value: idea.expected_effect },
  ]));
  const assumptions = section("关键 Assumptions", (idea.unknowns || []).length ? `<div class="assumption-list">${idea.unknowns.map((unknown, index) => `<div class="assumption-row"><span class="assumption-id">A${index + 1}</span><div class="assumption-copy">${esc(unknown)}</div><span class="assumption-state">未知 / 待验证</span></div>`).join("")}</div>` : emptyState("未记录 Assumption", "当前对象没有独立 Assumption 记录。", "question"), { note: "由现有 unknowns 映射，不补写新证据" });
  const claimRows = evidence.map((entry, index) => {
    const item = evidenceItem(entry);
    return { id: `Claim ${String.fromCharCode(65 + index)}`, claim: item?.title || entry.reason || "证据记录", type: "来源事实", relation: entry.relation, summary: entry.reason, source: item?.url || entry.source_urls?.[0] || "" };
  });
  const claimTable = dataTable([
    { key: "id", label: "Claim", width: "10%" },
    { key: "claim", label: "Claim 内容", width: "28%" },
    { key: "type", label: "类型", width: "12%", render: (claim) => badge(claim.type, "positive") },
    { key: "relation", label: "关系", width: "12%", render: (claim) => badge(claim.relation, statusTone(claim.relation)) },
    { key: "summary", label: "证据概括", width: "28%" },
    { key: "source", label: "来源", width: "10%", render: (claim) => claim.source ? `<a href="${esc(claim.source)}" target="_blank" rel="noreferrer">原文 ↗</a>` : "未解析" },
  ], claimRows, { emptyTitle: "尚无证据 Claim", emptyCopy: "Idea 仍可保留，但必须明确证据不足。", cardTitleKey: "id" });
  const suggestion = idea.validation_plan ? editorialNote("验证建议 · 尚未执行", `${idea.validation_plan.minimal_model || idea.validation_plan.mode || "当前只保存验证建议"}。这不是仿真或实验结果。`, "warning") : editorialNote("尚无验证建议", "当前状态未进入 Validation，不展示完整 Plan、Run 或 Result。", "warning");
  const path = renderEvidencePathForIdea(row, idea, evidence[0]);
  const main = `<div class="page-stack">${overview}<div class="definition-grid">${definition}${assumptions}</div>${section("证据摘要（按 Claim）", claimTable)}${section("最小验证建议", suggestion)}${section("证据路径（阅读路径）", path)}</div>`;
  const timeline = idea.decision_log?.length ? `<ol class="timeline">${idea.decision_log.slice(-5).map((event, index, rows) => `<li ${index === rows.length - 1 ? 'aria-current="step"' : ""}><time>${esc(event.issue_date || "")}</time><span>${esc(event.reason || event.decision || "状态更新")}</span></li>`).join("")}</ol>` : emptyState("没有决策时间线", "当前对象未记录状态事件。", "clock");
  const roadmapLinks = (idea.topic_ids || []).map((topicId) => quickLink(`#roadmaps?topic=${encodeURIComponent(topicId)}`, "roadmap", topicLabel(topicId))).join("");
  const side = `<aside class="side-rail">${section("Decision Timeline", timeline)}${section("关联 Roadmap", roadmapLinks ? `<div class="side-list">${roadmapLinks}</div>` : emptyState("没有关联 Roadmap", "当前 Idea 尚未绑定 Topic。", "roadmap"))}${section("相关 Open Questions", (idea.unknowns || []).length ? `<ul>${idea.unknowns.map((unknown) => `<li>${esc(unknown)}</li>`).join("")}</ul>` : "<p>暂无。</p>")}${section("操作入口", `<div class="side-list">${quickLink(`#evidence?idea=${encodeURIComponent(row.idea_id)}`, "evidence", "查看 Evidence Path")}${evidence[0]?.source_urls?.[0] ? quickLink(evidence[0].source_urls[0], "source", "查看原始来源", true) : ""}${quickLink("#ideas", "idea", "返回 Idea Hub")}</div>`)}</aside>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "Idea 详情", description: "查看一个 Idea 的来龙去脉、证据成熟度与下一步验证建议。", breadcrumb: '<a href="#ideas">Idea Hub</a><span>/</span><span>详情</span>' })}<div class="two-column idea-detail-layout">${main}${side}</div></div>`;
}

function renderEvidencePathForIdea(row, idea, reference) {
  const item = evidenceItem(reference);
  const source = item?.url || reference?.source_urls?.[0] || "";
  const steps = [
    { icon: "source", title: "原始来源", note: item?.title || "公开论文或工程资料", href: source },
    { icon: "trend", title: "证据记录", note: reference?.reason || "结构化提炼与归因", href: item ? issueHref(item.issue_date) : "" },
    { icon: "idea", title: "Idea Assumption", note: idea.unknowns?.[0] || idea.hypothesis || "关键假设", href: `#ideas?idea=${encodeURIComponent(row.idea_id)}` },
    { icon: "status", title: "系统综合判断", note: STATUS_LABELS[idea.status] || idea.status || "未知" },
    { icon: "check", title: "Decision", note: idea.decision_log?.at(-1)?.decision || "持续构建证据" },
  ];
  return `<div class="evidence-path">${steps.map((step) => `<div class="path-step">${icon(step.icon)}${step.href ? `<a href="${esc(step.href)}" ${/^https?:/i.test(step.href) ? 'target="_blank" rel="noreferrer"' : ""}><b>${esc(step.title)}</b><span>${esc(step.note)}</span></a>` : `<b>${esc(step.title)}</b><span>${esc(step.note)}</span>`}</div>`).join("")}</div>`;
}

function evidenceViewHref(view, row, params = {}) {
  const query = new URLSearchParams(Object.entries({ idea: row?.idea_id, view, ...params }).filter(([, value]) => value != null && value !== "")).toString();
  return `#evidence?${query}`;
}

function evidenceViewTabs(view, row) {
  return `<nav class="evidence-view-tabs" aria-label="Evidence 视图">
    <a href="${evidenceViewHref("path", row)}" ${view === "path" ? 'aria-current="page"' : ""}>证据链</a>
    <a href="${evidenceViewHref("graph", row, { depth: 1, candidates: 0 })}" ${view === "graph" ? 'aria-current="page"' : ""}>关系图</a>
    <a href="${evidenceViewHref("gaps", row)}" ${view === "gaps" ? 'aria-current="page"' : ""}>证据缺口</a>
    <a href="${evidenceViewHref("atlas", row, { scope: "all", mode: "topic" })}" ${view === "atlas" ? 'aria-current="page"' : ""}>Archive Atlas</a>
  </nav>`;
}

function graphKnowledgePercent(model) {
  return model.nodes.length ? Math.round(model.nodes.filter((node) => !node.unresolved).length / model.nodes.length * 100) : 0;
}

function evidenceContextBar(row, idea, model, view) {
  const percent = graphKnowledgePercent(model);
  const current = model.nodes.find((node) => node.id === model.focusId);
  const relations = model.edges.filter((edge) => edge.target === current?.id && edge.confirmation === "confirmed").map((edge) => edge.relation);
  const conflict = relations.includes("supports") && relations.includes("challenges");
  return `<div class="evidence-context-bar desktop-evidence-view">
    <div class="evidence-context-item"><span>当前 Idea</span><strong>${esc(row?.title || "未选择")}</strong></div>
    <div class="evidence-context-item"><span>状态</span>${badge(STATUS_LABELS[idea?.status] || idea?.status || "未知", statusTone(idea?.status))}</div>
    <div class="evidence-context-item"><span>范围</span><strong>上游与下游 ${esc(model.limits.depth || 1)} 跳</strong></div>
    <div class="evidence-context-item"><span>知识水位</span><div class="knowledge-meter"><i style="--meter:${percent}%"></i><strong>${percent}%</strong></div></div>
    ${view === "graph" && conflict ? '<div class="conflict-banner"><b>证据存在冲突</b><span>同一节点同时存在已确认的支持与挑战关系。</span></div>' : ""}
  </div>`;
}

function graphDetailMarkup(model, selectedId) {
  const node = model.nodes.find((candidate) => candidate.id === selectedId) || model.nodes.find((candidate) => candidate.id === model.focusId);
  if (!node) return emptyState("没有节点详情", "当前投影没有可查看对象。", "question");
  const incoming = model.edges.filter((edge) => edge.target === node.id);
  const outgoing = model.edges.filter((edge) => edge.source === node.id);
  const provenance = Object.entries(node.provenance || {}).map(([key, value]) => `${key}: ${value}`).join(" · ");
  return `<div class="graph-detail-body">
    ${model.requestedFocusMissing && selectedId === model.focusId ? '<div class="graph-detail-section"><p>请求的节点不存在，已回退到当前 Idea。</p></div>' : ""}
    <div class="graph-detail-section"><h3>${esc(node.title)}</h3>${badge(EvidenceGraph.KIND_LABELS[node.kind] || node.kind, node.unresolved ? "negative" : "neutral")}</div>
    <div class="graph-detail-section"><h3>身份</h3>${fieldRows([{ label: "类型", value: EvidenceGraph.KIND_LABELS[node.kind] || node.kind }, { label: "状态", value: node.status || "未记录" }, { label: "名称", value: node.title }])}</div>
    ${node.description || node.subtitle ? `<div class="graph-detail-section"><h3>陈述</h3><p>${esc(node.description || node.subtitle)}</p></div>` : ""}
    <div class="graph-detail-section"><h3>来源与影响</h3>${fieldRows([{ label: "Provenance", value: provenance || "未记录" }, { label: "入边", value: `${incoming.length} 条` }, { label: "出边", value: `${outgoing.length} 条` }])}</div>
    ${node.unresolved ? '<div class="graph-detail-section"><p>该对象尚未物化或引用未解析，不参与已确认下游关系。</p></div>' : ""}
  </div><div class="graph-detail-actions">${node.href ? `<a href="${esc(node.href)}" ${/^https?:/i.test(node.href) ? 'target="_blank" rel="noreferrer"' : ""}>打开对象</a>` : ""}<a href="#relationshipList">查看证据链</a></div>`;
}

function relationshipTableMarkup(model, selectedEdgeId = "") {
  if (!model.edges.length) return `<div id="relationshipList" class="relationship-table">${emptyState("没有已解析关系", "未解析引用不会绘制到图谱中。", "evidence")}</div>`;
  const nodeMap = new Map(model.nodes.map((node) => [node.id, node]));
  return `<div id="relationshipList" class="relationship-table"><table><thead><tr><th style="width:18%">来源对象</th><th style="width:12%">关系</th><th style="width:26%">目标对象</th><th style="width:13%">确认状态</th><th style="width:20%">来源</th><th style="width:11%">更新时间</th></tr></thead><tbody>${model.edges.map((edge) => {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    const provenance = edge.provenance || {};
    return `<tr tabindex="0" data-relationship-id="${esc(edge.id)}" aria-selected="${edge.id === selectedEdgeId}"><td>${esc(source?.title || edge.source)}</td><td><span class="relationship-symbol ${esc(edge.relation)}"><i class="relation-swatch ${esc(edge.relation)}"></i>${esc(EvidenceGraph.RELATION_LABELS[edge.relation] || edge.relation)}</span></td><td>${esc(target?.title || edge.target)}</td><td>${esc(edge.confirmation === "candidate" ? "候选" : "已确认")}</td><td>${esc(provenance.object_id || provenance.item_id || "已记录")}</td><td>${esc(source?.issueDate || target?.subtitle || "—")}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}

function graphFilterMarkup(model, row) {
  const counts = model.nodes.reduce((map, node) => map.set(node.kind, (map.get(node.kind) || 0) + 1), new Map());
  return `<aside class="graph-filter-panel" aria-label="图谱筛选">
    <input class="graph-search" type="search" data-graph-search placeholder="搜索 Claim、Idea、Roadmap 或来源" aria-label="搜索图谱节点" />
    <div class="graph-panel-section"><h3>当前对象</h3><div class="graph-filter-row">${icon("idea")}<span>Idea：${esc(row?.title || "未选择")}</span></div></div>
    <div class="graph-panel-section"><h3>节点类型</h3><div class="graph-filter-list">${["source", "evidence", "claim", "idea", "roadmap", "assumption", "decision", "unknown"].map((kind) => `<label class="graph-filter-row"><input type="checkbox" checked data-node-kind="${kind}"><span>${esc(EvidenceGraph.KIND_LABELS[kind])}</span><b>${counts.get(kind) || 0}</b></label>`).join("")}</div></div>
    <div class="graph-panel-section"><h3>关系类型</h3><div class="graph-filter-list">${["declares", "supports", "challenges", "qualifies", "leads_to", "pending"].map((relation) => `<div class="graph-filter-row"><i class="relation-swatch ${relation}"></i><span>${esc(EvidenceGraph.RELATION_LABELS[relation])}</span><b>${model.edges.filter((edge) => edge.relation === relation).length}</b></div>`).join("")}</div></div>
    <div class="graph-panel-section"><h3>深度</h3><div class="graph-depth-options"><label><input type="radio" name="graph-depth" value="1" ${model.limits.depth === 1 ? "checked" : ""}>1 跳</label><label><input type="radio" name="graph-depth" value="2" ${model.limits.depth === 2 ? "checked" : ""}>2 跳</label></div></div>
    <div class="graph-panel-section"><label class="candidate-toggle"><span>显示候选关系</span><input type="checkbox" data-candidates ${model.candidatesEnabled ? "checked" : ""} ${model.candidatesAvailable ? "" : "disabled"}></label><p class="filter-note">${model.candidatesAvailable ? "候选边包含规则版本与 provenance。" : "没有带规则名、版本和 provenance 的候选关系。"}</p></div>
    <div class="graph-panel-section"><h3>未解析关系</h3><p class="filter-note">${model.unresolved.length ? `${model.unresolved.length} 条引用未进入图谱；可在“证据缺口”查看原因。` : "当前没有悬空引用。"}</p></div>
  </aside>`;
}

function mobileEvidencePath(model) {
  const nodeMap = new Map(model.nodes.map((node) => [node.id, node]));
  const focus = nodeMap.get(model.focusId) || model.nodes.find((node) => node.kind === "idea");
  const evidenceEdges = model.edges
    .filter((edge) => edge.target === focus?.id && ["supports", "challenges"].includes(edge.relation) && nodeMap.get(edge.source)?.kind === "evidence")
    .slice(0, 3);
  const evidenceNodes = evidenceEdges.map((edge) => nodeMap.get(edge.source)).filter(Boolean);
  const nodes = [];
  const placement = new Map();
  const add = (node, column, row) => {
    if (!node || placement.has(node.id)) return;
    placement.set(node.id, { column, row });
    nodes.push(node);
  };

  evidenceNodes.forEach((evidence, index) => {
    const sourceEdge = model.edges.find((edge) => edge.target === evidence.id && edge.relation === "declares" && nodeMap.get(edge.source)?.kind === "source");
    add(nodeMap.get(sourceEdge?.source), 1, index + 1);
    add(evidence, 2, index + 1);
  });

  const finalRow = Math.max(1, evidenceNodes.length + 1);
  add(focus, 1, finalRow);
  const roadmap = model.edges
    .filter((edge) => edge.relation === "leads_to" && evidenceNodes.some((node) => node.id === edge.source))
    .map((edge) => nodeMap.get(edge.target))
    .find((node) => node?.kind === "roadmap");
  add(roadmap, 2, finalRow);

  const ids = new Set(nodes.map((node) => node.id));
  const edges = model.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target) && ["declares", "supports", "challenges", "leads_to"].includes(edge.relation));
  return { nodes, edges, placement };
}

function mobileEvidenceMarkup(row, idea, model, view) {
  const percent = graphKnowledgePercent(model);
  const path = mobileEvidencePath(model);
  const relation = model.edges.find((edge) => ["supports", "challenges"].includes(edge.relation));
  const iconByKind = { source: "evidence", evidence: "trend", idea: "idea", roadmap: "roadmap" };
  return `<div class="mobile-evidence-view">
    <div class="mobile-knowledge-card"><div class="mobile-knowledge-main">${icon("trend")}<b>紧凑知识水位</b><div class="knowledge-meter"><i style="--meter:${percent}%"></i></div><strong>${percent}%</strong></div><div class="mobile-knowledge-meta"><span>范围：上游与下游 ${model.limits.depth} 路</span><span>截至：${esc(state.latest?.date || "未记录")}</span></div></div>
    ${evidenceViewTabs(view, row)}
    <a class="mobile-focus-card" href="#ideas?idea=${encodeURIComponent(row.idea_id)}">${icon("idea")}<div><b>当前 Idea：${esc(row.title)}</b><span>上游与下游 ${model.limits.depth} 路 · 状态：${esc(STATUS_LABELS[idea.status] || idea.status)}</span></div>${icon("chevron", "chevron")}</a>
    <section class="mobile-path-card"><div class="mobile-card-head"><h2>证据路径</h2><span>收起⌃</span></div><div class="mobile-path-canvas" data-mobile-path-canvas><svg class="mobile-path-connectors" data-mobile-path-connectors aria-hidden="true"></svg><div class="mobile-path-grid">${path.nodes.map((node) => { const position = path.placement.get(node.id); return `<div class="mobile-path-node ${esc(node.kind)}" data-mobile-node-id="${esc(node.id)}" style="--mobile-col:${position.column};--mobile-row:${position.row}">${icon(iconByKind[node.kind] || "question")}<div><b>${esc(EvidenceGraph.KIND_LABELS[node.kind])}</b><span>${esc(node.title)}</span></div></div>`; }).join("")}</div></div></section>
    <button class="mobile-filter-button" type="button" data-open-mobile-filter>${icon("sliders")}<span>筛选关系（${new Set(model.edges.map((edge) => edge.relation)).size} 个类型 · 全显示）</span>${icon("chevron")}</button>
    <section class="mobile-detail-card"><h2>当前节点详情</h2>${fieldRows([{ label: "类型", value: "Idea" }, { label: "名称", value: row.title }, { label: "状态", value: STATUS_LABELS[idea.status] || idea.status }, { label: "范围", value: `上游与下游 ${model.limits.depth} 路` }, { label: "更新时间", value: idea.last_updated_issue || row.last_updated_issue }])}</section>
    <section class="mobile-relation-card"><div class="mobile-card-head"><h2>关系列表 <small>（展示前 5 条）</small></h2><a href="#relationshipList">查看全部</a></div>${relation ? `<div class="mobile-relation-row"><i></i><span>${esc(model.nodes.find((node) => node.id === relation.source)?.title || "证据记录")}　→ ${esc(EvidenceGraph.RELATION_LABELS[relation.relation])} →　当前 Idea</span>${icon("chevron")}</div>` : `<div class="mobile-relation-row"><i></i><span>当前没有已解析关系</span></div>`}</section>
    <button class="desktop-help-button" type="button" data-desktop-help>${icon("monitor")}<span>在桌面查看关系图</span></button>
    <dialog class="mobile-filter-dialog" data-mobile-filter><div class="mobile-dialog-head"><h2>筛选关系</h2><button type="button" data-close-mobile-filter aria-label="关闭筛选">×</button></div><div class="mobile-dialog-body">${graphFilterMarkup(model, row)}</div></dialog>
  </div>`;
}

function renderEvidenceGraphView(row, model) {
  const atLimit = model.limits.nodeCount >= 40;
  return `<div class="desktop-evidence-view"><div class="graph-workspace">
    ${graphFilterMarkup(model, row)}
    <section class="graph-canvas-panel" aria-label="关系图画布"><div class="graph-toolbar"><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="fit" aria-label="适应画布">适应画布</button></div><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="out" aria-label="缩小">−</button><span class="graph-control zoom-value" data-zoom-value>100%</span><button class="graph-control" type="button" data-graph-action="in" aria-label="放大">＋</button></div><div class="graph-control-group"><button class="graph-control" type="button" data-graph-action="reset" aria-label="重置画布">↻</button><button class="graph-control" type="button" data-graph-action="expand" aria-label="展开一跳" ${atLimit ? 'disabled title="已达到 40 个节点上限"' : ""}>展开一跳</button></div></div><div class="graph-canvas" tabindex="0" data-graph-canvas aria-label="证据关系图，可用方向键沿关系移动"></div></section>
    <aside class="graph-detail-panel" aria-label="节点详情"><h2 class="graph-panel-title">当前节点详情</h2><div data-graph-detail>${graphDetailMarkup(model, model.focusId)}</div></aside>
  </div>${relationshipTableMarkup(model)}</div>`;
}

function renderEvidencePathView(row, idea, model) {
  const evidence = [...(idea.evidence_for || []).map((entry) => ({ ...entry, relation: "支持" })), ...(idea.evidence_against || []).map((entry) => ({ ...entry, relation: "反对" }))];
  const claims = evidence.map((entry) => {
    const item = evidenceItem(entry);
    return { source: item?.title || entry.source_urls?.[0] || "未解析", relation: entry.relation, date: item?.issue_date || entry.issue_date || "", boundary: entry.reason || "未记录", href: item?.url || entry.source_urls?.[0] || "" };
  });
  const table = dataTable([{ key: "source", label: "原始来源", width: "34%" }, { key: "relation", label: "关系", width: "12%", render: (claim) => badge(claim.relation, statusTone(claim.relation)) }, { key: "date", label: "首次进入日报", width: "16%" }, { key: "boundary", label: "证据边界", width: "30%" }, { key: "href", label: "入口", width: "8%", render: (claim) => claim.href ? `<a href="${esc(claim.href)}" target="_blank" rel="noreferrer">原文</a>` : "缺失" }], claims, { emptyTitle: "没有可解析证据", emptyCopy: "当前 Idea 可以保留，但证据路径仍不完整。", cardTitleKey: "source" });
  return `<div class="desktop-evidence-view evidence-path-view"><div class="page-stack"><section class="path-surface"><h2>证据路径</h2>${renderEvidencePathForIdea(row, idea, evidence[0])}</section>${section("证据记录清单", table)}${editorialNote("Claim 尚未物化", "当前知识对象没有可定位的 first-class Claim；证据 reason 只作为关系说明，不冒充 Claim。", "warning")}</div><aside class="graph-detail-panel">${graphDetailMarkup(model, model.focusId)}</aside></div>`;
}

function renderEvidenceGapsView(row, idea, model) {
  const gaps = (idea.unknowns || []).length ? idea.unknowns : ["持续跟踪新的独立公开来源"];
  return `<div class="desktop-evidence-view evidence-path-view"><section class="gaps-surface"><h2>当前证据缺口</h2><p>这些缺口直接来自 Idea 的 unknowns；页面不补写实验结果或推断关系。</p><div class="gaps-grid">${gaps.map((gap, index) => `<article class="gap-card"><b>缺口 ${index + 1}</b><span>${esc(gap)}</span></article>`).join("")}</div>${model.unresolved.length ? editorialNote("未解析关系", `${model.unresolved.length} 条引用因缺少目标对象或 provenance 未进入图谱。`, "negative") : editorialNote("关系引用完整", "当前投影中的已确认边都能定位来源和目标。")}</section><aside class="graph-detail-panel">${graphDetailMarkup(model, model.focusId)}</aside></div>`;
}

function atlasControlsMarkup(model, row) {
  const issueDates = state.issues.map((issue) => issue.date).sort().reverse();
  const topics = model.mode === "keyword"
    ? [...new Set(state.items.flatMap((item) => item.keywords || []).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN")).slice(0, 10).map((keyword) => ({ id: keyword, title: keyword }))
    : [...new Map(state.items.filter((item) => item.topic_name).map((item) => [item.topic_id || item.topic_name, { id: item.topic_id || item.topic_name, title: item.topic_name }])).values()].sort((a, b) => a.title.localeCompare(b.title, "zh-CN")).slice(0, 10);
  const routeParams = state.route.params;
  return `<aside class="atlas-controls"><div class="atlas-control-group"><div class="atlas-segmented"><a href="${evidenceViewHref("atlas", row, { scope: "latest", mode: model.mode })}" aria-current="${model.scope === "latest"}">最新一期</a><a href="${evidenceViewHref("atlas", row, { scope: "all", mode: model.mode })}" aria-current="${model.scope === "all" && !routeParams.issue}">全部归档</a></div></div><div class="atlas-control-group"><h3>浏览方式</h3><div class="atlas-segmented"><a href="${evidenceViewHref("atlas", row, { scope: model.scope, mode: "topic" })}" aria-current="${model.mode === "topic"}">按 Topic</a><a href="${evidenceViewHref("atlas", row, { scope: model.scope, mode: "keyword" })}" aria-current="${model.mode === "keyword"}">按关键词</a></div></div><div class="atlas-control-group"><h3>期次筛选</h3><div class="graph-filter-list">${issueDates.map((date) => `<a class="graph-filter-row" href="${evidenceViewHref("atlas", row, { scope: "all", mode: model.mode, issue: date, topic: routeParams.topic })}" aria-current="${routeParams.issue === date}"><span>□</span><span>${esc(date)}</span><b>${state.items.filter((item) => item.issue_date === date).length}</b></a>`).join("")}</div></div><div class="atlas-control-group"><h3>Topic 筛选</h3><div class="graph-filter-list"><a class="graph-filter-row" href="${evidenceViewHref("atlas", row, { scope: model.scope, mode: model.mode, issue: routeParams.issue })}" aria-current="${!routeParams.topic}"><span>□</span><span>全部 Topic</span></a>${topics.map((topic) => `<a class="graph-filter-row" href="${evidenceViewHref("atlas", row, { scope: model.scope, mode: model.mode, issue: routeParams.issue, topic: topic.id })}" aria-current="${routeParams.topic === topic.id}"><span>□</span><span>${esc(topic.title)}</span></a>`).join("")}</div></div></aside>`;
}

function renderArchiveAtlasView(row, model) {
  return `<div class="desktop-evidence-view"><div class="atlas-disclaimer">这里的连接表示归档结构和关键词聚合，不表示支持、挑战或因果关系。</div><div class="atlas-workspace">${atlasControlsMarkup(model, row)}<section class="atlas-canvas-shell"><div class="atlas-lane-head"><span>日报期次</span><span>Topic</span><span>归档条目</span></div><div class="atlas-canvas" tabindex="0" data-atlas-canvas aria-label="Archive Atlas 结构图"></div><div class="atlas-toolbar"><div class="graph-control-group"><button class="graph-control" type="button" data-atlas-action="out" aria-label="缩小">−</button><span class="graph-control zoom-value" data-atlas-zoom>100%</span><button class="graph-control" type="button" data-atlas-action="in" aria-label="放大">＋</button></div><button class="graph-control-group graph-control" type="button" data-atlas-action="fit" aria-label="适应画布">适应画布</button></div></section><aside class="atlas-detail"><h2 class="graph-panel-title">条目信息</h2><div data-atlas-detail>${graphDetailMarkup(model, model.focusId)}</div></aside></div></div>`;
}

function replaceEvidenceUrl(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "")).toString();
  history.replaceState(null, "", `#evidence?${query}`);
  state.route = BriefingData.parseRoute(location.hash);
}

function bindGraphView(row, model) {
  const canvas = $("[data-graph-canvas]");
  if (!canvas) return;
  const renderer = new EvidenceGraph.EvidenceGraphRenderer(canvas, model, {
    onSelectNode: (id) => {
      $("[data-graph-detail]").innerHTML = graphDetailMarkup(model, id);
      replaceEvidenceUrl({ ...state.route.params, idea: row.idea_id, view: "graph", node: id });
    },
    onSelectEdge: (id) => $$('[data-relationship-id]').forEach((entry) => entry.setAttribute("aria-selected", String(entry.dataset.relationshipId === id))),
    onExpand: () => go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", depth: 2 }),
    onZoom: (value) => { const label = $("[data-zoom-value]"); if (label) label.textContent = `${value}%`; },
  });
  $$('[data-graph-action]').forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.graphAction === "fit") renderer.fit();
    if (button.dataset.graphAction === "in") renderer.zoom(.1);
    if (button.dataset.graphAction === "out") renderer.zoom(-.1);
    if (button.dataset.graphAction === "reset") renderer.reset();
    if (button.dataset.graphAction === "expand") go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", depth: 2 });
  }));
  $$('[data-relationship-id]').forEach((entry) => {
    const choose = () => renderer.selectEdge(entry.dataset.relationshipId, true);
    entry.addEventListener("click", choose);
    entry.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } });
  });
  $$('[name="graph-depth"]').forEach((input) => input.addEventListener("change", () => go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", depth: input.value })));
  $("[data-candidates]")?.addEventListener("change", (event) => go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", candidates: event.target.checked ? 1 : 0 }));
  const graphFilterPanel = canvas.closest(".graph-workspace")?.querySelector(".graph-filter-panel");
  const graphSearch = graphFilterPanel?.querySelector("[data-graph-search]");
  const graphKindInputs = graphFilterPanel ? [...graphFilterPanel.querySelectorAll('[data-node-kind]')] : [];
  const applyGraphFilters = () => {
    const needle = norm(graphSearch?.value);
    const enabledKinds = new Set(graphKindInputs.filter((input) => input.checked).map((input) => input.dataset.nodeKind));
    const visibleIds = new Set();
    canvas.querySelectorAll("[data-node-id]").forEach((element) => {
      const node = model.nodes.find((candidate) => candidate.id === element.dataset.nodeId);
      const visible = enabledKinds.has(node?.kind) && !(needle && !norm(`${node?.title} ${node?.subtitle} ${node?.kind}`).includes(needle));
      element.hidden = !visible;
      if (visible) visibleIds.add(element.dataset.nodeId);
    });
    canvas.querySelectorAll("[data-edge-id]").forEach((element) => {
      const edge = model.edges.find((candidate) => candidate.id === element.dataset.edgeId);
      element.toggleAttribute("hidden", !edge || !visibleIds.has(edge.source) || !visibleIds.has(edge.target));
    });
  };
  graphSearch?.addEventListener("input", applyGraphFilters);
  graphKindInputs.forEach((input) => input.addEventListener("change", applyGraphFilters));
}

function bindAtlasView(model) {
  const canvas = $("[data-atlas-canvas]");
  if (!canvas) return;
  const renderer = new EvidenceGraph.EvidenceGraphRenderer(canvas, model, {
    mode: "atlas",
    onSelectNode: (id) => { $("[data-atlas-detail]").innerHTML = graphDetailMarkup(model, id); replaceEvidenceUrl({ ...state.route.params, view: "atlas", node: id }); },
    onZoom: (value) => { const label = $("[data-atlas-zoom]"); if (label) label.textContent = `${value}%`; },
  });
  $$('[data-atlas-action]').forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.atlasAction === "fit") renderer.fit();
    if (button.dataset.atlasAction === "in") renderer.zoom(.1);
    if (button.dataset.atlasAction === "out") renderer.zoom(-.1);
  }));
}

function bindMobileEvidence(row, model) {
  const dialog = $("[data-mobile-filter]");
  const canvas = $("[data-mobile-path-canvas]");
  const path = mobileEvidencePath(model);
  const drawConnectors = () => {
    const svg = canvas?.querySelector("[data-mobile-path-connectors]");
    if (!svg || !canvas || getComputedStyle(canvas).display === "none") return;
    const canvasRect = canvas.getBoundingClientRect();
    const nodeRects = new Map();
    canvas.querySelectorAll("[data-mobile-node-id]").forEach((element) => {
      if (element.hidden) return;
      const rect = element.getBoundingClientRect();
      nodeRects.set(element.dataset.mobileNodeId, {
        x: rect.left - canvasRect.left,
        y: rect.top - canvasRect.top,
        width: rect.width,
        height: rect.height,
      });
    });
    const incomingTotals = new Map();
    path.edges.forEach((edge) => {
      if (nodeRects.has(edge.source) && nodeRects.has(edge.target)) incomingTotals.set(edge.target, (incomingTotals.get(edge.target) || 0) + 1);
    });
    const incomingSeen = new Map();
    const routedMobileEdge = (edge, source, target, offset) => {
      if (edge.relation === "declares") return EvidenceGraph.routeEvidenceEdge(source, target, offset).d;
      const sourceNode = path.nodes.find((node) => node.id === edge.source);
      const targetNode = path.nodes.find((node) => node.id === edge.target);
      const singleColumn = window.matchMedia("(max-width: 359px)").matches;
      const sourceY = source.y + source.height / 2 + (!singleColumn && edge.relation === "leads_to" ? 10 : !singleColumn ? 5 : 0);
      const targetY = target.y + target.height / 2 + offset;
      let sourceX;
      let targetX;
      let gutterX;
      if (singleColumn || Math.abs(source.x - target.x) < 12) {
        sourceX = source.x;
        targetX = target.x;
        gutterX = Math.max(10, Math.min(source.x, target.x) - 18 + offset);
      } else if (targetNode?.kind === "idea" && sourceNode?.kind === "evidence") {
        sourceX = source.x;
        targetX = target.x + target.width;
        gutterX = (sourceX + targetX) / 2 + offset;
      } else {
        return EvidenceGraph.routeEvidenceEdge(source, target, offset).d;
      }
      const firstDirection = Math.sign(gutterX - sourceX) || 1;
      const verticalDirection = Math.sign(targetY - sourceY) || 1;
      const lastDirection = Math.sign(targetX - gutterX) || 1;
      const radius = Math.max(3, Math.min(9, Math.abs(gutterX - sourceX) / 2, Math.abs(targetY - sourceY) / 2, Math.abs(targetX - gutterX) / 2));
      return `M ${sourceX} ${sourceY} H ${gutterX - firstDirection * radius} Q ${gutterX} ${sourceY} ${gutterX} ${sourceY + verticalDirection * radius} V ${targetY - verticalDirection * radius} Q ${gutterX} ${targetY} ${gutterX + lastDirection * radius} ${targetY} H ${targetX}`;
    };
    const relationNames = [...new Set(path.edges.map((edge) => edge.relation))];
    const markers = relationNames.map((name) => `<marker id="mobile-arrow-${esc(name)}" class="relation-${esc(name)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z"></path></marker>`).join("");
    const lines = path.edges.map((edge) => {
      const source = nodeRects.get(edge.source);
      const target = nodeRects.get(edge.target);
      if (!source || !target) return "";
      const seen = incomingSeen.get(edge.target) || 0;
      incomingSeen.set(edge.target, seen + 1);
      const offset = (seen - ((incomingTotals.get(edge.target) || 1) - 1) / 2) * 8;
      const label = EvidenceGraph.RELATION_LABELS[edge.relation] || edge.relation;
      return `<path class="relation-${esc(edge.relation)}" d="${routedMobileEdge(edge, source, target, offset)}" marker-end="url(#mobile-arrow-${esc(edge.relation)})"><title>${esc(label)}</title></path>`;
    }).join("");
    svg.setAttribute("viewBox", `0 0 ${canvas.clientWidth} ${canvas.clientHeight}`);
    svg.innerHTML = `<defs>${markers}</defs>${lines}`;
  };
  const scheduleDraw = () => requestAnimationFrame(drawConnectors);
  window.mobileEvidenceResizeObserver?.disconnect();
  if (canvas && typeof ResizeObserver !== "undefined") {
    window.mobileEvidenceResizeObserver = new ResizeObserver(scheduleDraw);
    window.mobileEvidenceResizeObserver.observe(canvas);
  }
  scheduleDraw();
  $("[data-open-mobile-filter]")?.addEventListener("click", () => dialog?.showModal());
  $("[data-close-mobile-filter]")?.addEventListener("click", () => dialog?.close());
  $("[data-desktop-help]")?.addEventListener("click", () => window.alert("关系图的平移、缩放和完整关系列表适合在宽度至少 768px 的桌面浏览器中查看。"));
  const mobileKindInputs = dialog ? [...dialog.querySelectorAll('[data-node-kind]')] : [];
  const mobileSearch = dialog?.querySelector('[data-graph-search]');
  const applyMobileFilters = () => {
    const enabledKinds = new Set(mobileKindInputs.filter((input) => input.checked).map((input) => input.dataset.nodeKind));
    const needle = norm(mobileSearch?.value);
    $$('.mobile-path-node').forEach((element) => {
      const node = path.nodes.find((candidate) => candidate.id === element.dataset.mobileNodeId);
      element.hidden = !enabledKinds.has(node?.kind) || Boolean(needle && !norm(element.textContent).includes(needle));
    });
    scheduleDraw();
  };
  mobileKindInputs.forEach((input) => input.addEventListener("change", applyMobileFilters));
  dialog?.querySelectorAll('[name="graph-depth"]').forEach((input) => input.addEventListener("change", () => go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", depth: input.value })));
  dialog?.querySelector('[data-candidates]')?.addEventListener("change", (event) => go("evidence", { ...state.route.params, idea: row.idea_id, view: "graph", candidates: event.target.checked ? 1 : 0 }));
  mobileSearch?.addEventListener("input", applyMobileFilters);
}

function renderEvidence(row, idea, graphContext = {}) {
  const view = state.route.params.view || "path";
  const isAtlas = view === "atlas";
  if ((!row || !idea) && !isAtlas) {
    $("#appMain").innerHTML = `${pageHeader({ title: "Evidence Explorer", description: "用证据回答 Roadmap 为什么变化、Idea 为什么存在，以及当前缺少什么。" })}${emptyState("没有可聚焦的 Idea", "长期知识中尚无正式 Idea。", "evidence")}`;
    return;
  }
  const graphModel = BriefingData.buildEvidenceGraphModel({ ideaRow: row, idea, params: state.route.params, ...graphContext });
  const atlasModel = BriefingData.buildArchiveAtlasModel({ issues: graphContext.issues || state.issues, params: state.route.params });
  const activeModel = isAtlas ? atlasModel : graphModel;
  const title = isAtlas ? "Archive Atlas（结构浏览视图）" : "Evidence Explorer";
  const description = isAtlas ? "这里的连接表示归档结构和关键词聚合，不表示支持或因果关系。" : "追踪判断从来源、证据到 Roadmap 与 Idea 决策的完整路径。";
  const content = view === "graph" ? renderEvidenceGraphView(row, graphModel)
    : view === "atlas" ? renderArchiveAtlasView(row, atlasModel)
      : view === "gaps" ? renderEvidenceGapsView(row, idea, graphModel)
        : state.route.params.task === "missing" ? renderEvidenceGapsView(row, idea, graphModel)
          : renderEvidencePathView(row, idea, graphModel);
  const mobile = row && idea ? mobileEvidenceMarkup(row, idea, graphModel, view) : "";
  $("#appMain").innerHTML = `<div class="page-stack evidence-explorer">${pageHeader({ title, description })}<div class="desktop-evidence-tabs">${evidenceViewTabs(view, row)}</div>${evidenceContextBar(row, idea, activeModel, view)}${mobile}${content}</div>`;
  if (view === "graph") bindGraphView(row, graphModel);
  if (view === "atlas") bindAtlasView(atlasModel);
  if (row && idea) bindMobileEvidence(row, graphModel);
  document.querySelector('.evidence-view-tabs a[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "center" });
}

function impactForItem(item) {
  for (const [ideaId, idea] of state.ideaObjects) {
    const support = (idea.evidence_for || []).some((entry) => itemKey(item) === String(entry.item_id));
    const against = (idea.evidence_against || []).some((entry) => itemKey(item) === String(entry.item_id));
    if (support || against) {
      const row = state.knowledge.ideas.find((entry) => entry.idea_id === ideaId);
      return { label: `${support ? "支持" : "反对"} Idea`, tone: support ? "positive" : "negative", detail: row?.title || "正式 Idea" };
    }
  }
  for (const [topicId, roadmap] of state.roadmapObjects) {
    const found = (roadmap.branches || []).some((branch) => (branch.evidence_item_ids || []).includes(itemKey(item)));
    if (found) return { label: "更新 Roadmap", tone: "positive", detail: topicLabel(topicId) };
  }
  if (item.role === "radar") return { label: "仅发现信号", tone: "neutral", detail: "尚未改变长期判断" };
  return { label: "仅归档", tone: "neutral", detail: "保留为公开参考" };
}

function renderArchive() {
  const issue = state.issues.find((row) => row.date === state.route.params.date) || state.latest;
  if (!issue) {
    $("#appMain").innerHTML = `${pageHeader({ title: "归档", description: "查看每期日报的归档结果与知识沉淀。" })}${emptyState("暂无归档", "发布第一期日报后，这里会出现期次。")}`;
    return;
  }
  const topics = new Set(issue.papers.map((item) => item.topic_name).filter(Boolean));
  const impacts = issue.papers.map((item) => impactForItem(item));
  const materializedCount = impacts.filter((impact) => impact.label !== "仅归档" && impact.label !== "仅发现信号").length;
  const issueNav = `<nav class="issue-nav" aria-label="期次列表">${[...state.issues].reverse().map((row, index) => `<a href="#archive?date=${encodeURIComponent(row.date)}" ${row.date === issue.date ? 'aria-current="page"' : ""}><strong>${esc(row.date)}</strong><small>第 ${state.issues.length - index} 期${row.date === issue.date ? " · 当前" : ""}</small></a>`).join("")}</nav>`;
  const summary = `<div class="issue-summary"><div><span>当前期次</span><strong class="issue-date">${esc(issue.date)}</strong><a class="section-action" href="${esc(issue.public_href)}" target="_blank" rel="noreferrer">查看本期 Reader →</a></div><div><span>Topic 数</span><strong>${topics.size}</strong></div><div><span>条目数量</span><strong>${issue.papers.length}</strong></div><div><span>进入长期知识</span><strong>${materializedCount}</strong></div></div>`;
  const rows = issue.papers.map((item, index) => ({ index: index + 1, title: item.title, topic: item.topic_name || "未分类", summary: item.summary || "暂无读者摘要", source: item.url || "", impact: impacts[index] }));
  const table = dataTable([
    { key: "index", label: "#", width: "6%", numeric: true },
    { key: "title", label: "条目", width: "25%" },
    { key: "topic", label: "Topic", width: "15%" },
    { key: "summary", label: "摘要", width: "34%" },
    { key: "source", label: "来源", width: "10%", render: (row) => row.source ? `<a href="${esc(row.source)}" target="_blank" rel="noreferrer">原文 ↗</a>` : "缺失" },
    { key: "impact", label: "长期影响", width: "14%", render: (row) => badge(row.impact.label, row.impact.tone) },
  ], rows, { emptyTitle: "本期没有公开条目", emptyCopy: "归档元数据存在，但没有可展示记录。", cardTitleKey: "title" });
  const impactTypes = [
    ["更新 Roadmap", "roadmap", "进入长期技术路线并调整判断"],
    ["产生 Idea Candidate", "idea", "当前公开数据没有独立 Candidate 集合"],
    ["支持或反对 Assumption", "evidence", "显式映射到正式 Idea 的证据关系"],
    ["新增证据但未改变判断", "claim", "保留证据，不夸大为 Milestone"],
    ["仅归档 / 仅发现信号", "archive", "作为公开参考，等待后续证据"],
  ];
  const impactList = `<div class="impact-list">${impactTypes.map(([label, iconName, copy]) => `<div class="impact-record">${icon(iconName)}<div><b>${label}</b><p>${copy}</p></div></div>`).join("")}</div>`;
  const currentImpact = rows.filter((row) => row.impact.label !== "仅归档");
  const materialized = currentImpact.filter((row) => row.impact.label !== "仅发现信号");
  const pending = currentImpact.filter((row) => row.impact.label === "仅发现信号");
  const compactList = (list, emptyCopy) => list.length ? `<div class="side-list">${list.slice(0, 5).map((row) => `<div class="side-record">${icon("claim")}<div><b>${esc(row.title)}</b><small>${esc(row.impact.label)}</small></div></div>`).join("")}</div>` : emptyState("没有记录", emptyCopy, "archive");
  const top = `<div class="archive-grid">${section("期次列表", issueNav)}<div class="page-stack">${section("当前期次摘要", summary)}${section(`当前期次的日报条目（${rows.length} 条）`, table)}</div>${section("长期影响状态说明", impactList)}</div>`;
  const bottom = `<div class="archive-bottom">${section("快速入口", `<div class="side-list">${quickLink(issue.public_href, "book", "前往 Reader", true)}${issue.original_href ? quickLink(issue.original_href, "source", "查看实际发送版", true) : ""}${quickLink("#roadmaps", "roadmap", "查看 Roadmap")}${quickLink("#ideas", "idea", "进入 Idea Hub")}</div>`)}${section(`本期进入长期知识的内容（${materialized.length} 条）`, compactList(materialized, "本期没有条目改变长期知识。"))}${section(`尚未物化 / 待补充（${pending.length} 条）`, compactList(pending, "本期没有仅停留在发现层的信号。"))}</div>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "归档", description: "查看每期日报的归档结果与知识沉淀，理解哪些内容被长期化。" })}${lagCount() ? editorialNote("知识 Snapshot 仍落后", `本期已归档，但长期知识落后 ${lagCount()} 期。`, "warning") : ""}${top}${bottom}</div>`;
}

function renderFeatures() {
  const items = state.featurePlan?.items || [];
  const cards = items.map((item, index) => dossierCard(
    { title: item.title, summary: item.summary },
    { index: index + 1, badges: [{ label: item.status === "iterating" ? "正在迭代" : "接下来", tone: item.status === "iterating" ? "positive" : "warning" }], fields: [{ label: "为什么支持", value: item.rationale }, { label: "计划范围", value: (item.scope || []).join("；") }] },
  )).join("");
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "迭代计划", description: "公开产品能力方向；状态不代表固定交付日期。" })}${section("公开能力计划", cards ? `<div class="feature-grid">${cards}</div>` : emptyState("尚无计划条目", "计划数据加入后会在这里显示。"))}</div>`;
}

function renderWorkbenchView(route, context = {}) {
  if (route.name === "home") renderHome();
  else if (route.name === "roadmaps") renderRoadmap(context.row, context.object);
  else if (route.name === "ideas" && route.params.idea) renderIdeaDetail(context.row, context.object);
  else if (route.name === "ideas") renderIdeaHub();
  else if (route.name === "evidence") renderEvidence(context.row, context.object, context.graphContext);
  else if (route.name === "archive") renderArchive();
  else if (route.name === "features") renderFeatures();
  else renderHome();
}
