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
  const quick = `<div class="link-matrix">${quickLink("#roadmaps", "roadmap", "查看 Roadmap")}${quickLink("#ideas", "idea", "进入 Idea Hub")}${quickLink("#knowledge", "trend", "查看知识图谱")}${quickLink("#archive", "archive", "浏览日报归档")}</div>`;
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
  const evidence = IdeaEvidenceView.evidenceEntries(idea);
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
  const path = IdeaEvidenceView.evidencePathMarkup(row, idea, evidence[0]);
  const main = `<div class="page-stack">${overview}<div class="definition-grid">${definition}${assumptions}</div>${section("证据摘要（按 Claim）", claimTable)}${section("最小验证建议", suggestion)}${section("证据路径（阅读路径）", path)}</div>`;
  const timeline = idea.decision_log?.length ? `<ol class="timeline">${idea.decision_log.slice(-5).map((event, index, rows) => `<li ${index === rows.length - 1 ? 'aria-current="step"' : ""}><time>${esc(event.issue_date || "")}</time><span>${esc(event.reason || event.decision || "状态更新")}</span></li>`).join("")}</ol>` : emptyState("没有决策时间线", "当前对象未记录状态事件。", "clock");
  const roadmapLinks = (idea.topic_ids || []).map((topicId) => quickLink(`#roadmaps?topic=${encodeURIComponent(topicId)}`, "roadmap", topicLabel(topicId))).join("");
  const side = `<aside class="side-rail">${section("Decision Timeline", timeline)}${section("关联 Roadmap", roadmapLinks ? `<div class="side-list">${roadmapLinks}</div>` : emptyState("没有关联 Roadmap", "当前 Idea 尚未绑定 Topic。", "roadmap"))}${section("相关 Open Questions", (idea.unknowns || []).length ? `<ul>${idea.unknowns.map((unknown) => `<li>${esc(unknown)}</li>`).join("")}</ul>` : "<p>暂无。</p>")}${section("操作入口", `<div class="side-list">${quickLink(`#ideas?idea=${encodeURIComponent(row.idea_id)}&view=evidence&mode=path`, "evidence", "查看证据链与关系图")}${quickLink(`#ideas?idea=${encodeURIComponent(row.idea_id)}&view=gaps`, "claim", "查看证据缺口")}${evidence[0]?.source_urls?.[0] ? quickLink(evidence[0].source_urls[0], "source", "查看原始来源", true) : ""}${quickLink("#ideas", "idea", "返回 Idea Hub")}</div>`)}</aside>`;
  $("#appMain").innerHTML = `<div class="page-stack">${pageHeader({ title: "Idea 详情", description: "查看一个 Idea 的来龙去脉、证据成熟度与下一步验证建议。", breadcrumb: '<a href="#ideas">Idea Hub</a><span>/</span><span>详情</span>' })}<div class="desktop-evidence-tabs">${IdeaEvidenceView.tabsMarkup(row, "overview")}</div><div class="two-column idea-detail-layout">${main}${side}</div></div>`;
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
  else if (route.name === "ideas" && route.params.idea && route.params.view === "evidence") {
    IdeaEvidenceView.renderEvidence(context.row, context.object, context);
  } else if (route.name === "ideas" && route.params.idea && route.params.view === "gaps") {
    IdeaEvidenceView.renderGaps(context.row, context.object, context);
  } else if (route.name === "ideas" && route.params.idea) renderIdeaDetail(context.row, context.object);
  else if (route.name === "ideas") renderIdeaHub();
  else if (route.name === "knowledge") KnowledgeGraphView.render(context);
  else if (route.name === "archive") renderArchive();
  else if (route.name === "features") renderFeatures();
  else renderHome();
}
