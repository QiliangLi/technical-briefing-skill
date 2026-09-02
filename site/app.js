/* Static data orchestration for the public editorial workbench. */
const state = {
  issues: [],
  items: [],
  latest: null,
  itemById: new Map(),
  knowledge: null,
  knowledgeError: null,
  knowledgeGraph: null,
  knowledgeGraphError: null,
  knowledgeGraphPromise: null,
  manifest: null,
  issueDiff: null,
  ideaObjects: new Map(),
  roadmapObjects: new Map(),
  featurePlan: null,
  feedback: null,
  roots: { archive: "./archive", knowledge: "./knowledge" },
  route: { name: "home", params: {} },
  renderToken: 0,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value = "") =>
  String(value).replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );
const text = (value) => (value == null ? "" : String(value).trim());
const norm = BriefingData.norm;
const icon = (name, className = "") =>
  `<svg class="${esc(className)}" aria-hidden="true"><use href="./assets/icons.svg#${esc(name)}"></use></svg>`;

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

async function optionalJson(url) {
  try {
    return await getJson(url);
  } catch (_) {
    return null;
  }
}

async function resolveRoot(directory) {
  const candidates = [`./${directory}`, `../${directory}`];
  let lastError;
  for (const root of candidates) {
    try {
      return { root, index: await getJson(`${root}/index.json`) };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error(`无法读取 ${directory}/index.json`);
}

function inferKeywords(item) {
  const result = new Set((item.keywords || []).filter(Boolean));
  if (item.topic_name) result.add(item.topic_name);
  if (item.direction_name) result.add(item.direction_name);
  const haystack = [item.title, item.summary, item.topic_name, item.direction_name]
    .filter(Boolean)
    .join(" ");
  ["KVCache", "KV Cache", "Agent", "RDMA", "DPU", "CXL", "MoE", "GPU", "NPU", "TPN", "Prefill", "Decode", "推理", "存储", "网络", "内存", "跨域", "调度", "缓存"]
    .filter((keyword) => norm(haystack).includes(norm(keyword)))
    .forEach((keyword) => result.add(keyword));
  return [...result].slice(0, 20);
}

function itemSourceUrl(detail, paper) {
  return (
    paper.url ||
    detail.url ||
    detail.sources?.find((source) => source.primary)?.url ||
    detail.sources?.[0]?.url ||
    ""
  );
}

async function loadArchiveIssue(meta) {
  const root = state.roots.archive;
  const base = `${root}/issues/${meta.date}`;
  const [papers, issueDoc, reader, manifest] = await Promise.all([
    getJson(`${root}/${meta.papers_file}`),
    optionalJson(`${base}/issue.json`).then((value) => value || {}),
    optionalJson(`${base}/reader.json`),
    optionalJson(`${base}/publication-manifest.json`),
  ]);
  const machineMap = BriefingData.collectItemMap(issueDoc);
  const readerMap = BriefingData.collectItemMap(reader);
  const paperRows = papers.map((paper, index) => {
    const id = BriefingData.itemId(paper) || `${meta.date}:${index}`;
    const detail = machineMap.get(id) || {};
    const machine = {
      ...paper,
      id: paper.paper_key || id,
      item_id: id,
      issue_date: meta.date,
      url: itemSourceUrl(detail, paper),
      summary: detail.core_conclusion || detail.summary || detail.project_relevance || "",
      direction_name: detail.direction_name || paper.direction_name || paper.direction_id || "",
      keywords: detail.keywords || paper.keywords || [],
      detail,
    };
    const merged = BriefingData.mergeReaderItem(machine, readerMap.get(id));
    merged.keywords = inferKeywords(merged);
    return merged;
  });
  const derivedRadar = BriefingData.radarFromIssue(issueDoc, meta.date).map((row) => {
    const identity = BriefingData.canonicalIdentity(row, location.href);
    const readerRow = (reader?.radar || []).find(
      (candidate) => BriefingData.canonicalIdentity(candidate, location.href) === identity,
    );
    const merged = BriefingData.mergeReaderItem(row, readerRow);
    merged.keywords = inferKeywords(merged);
    return merged;
  });
  const allItems = BriefingData.mergeRadarWithoutDuplicates(paperRows, derivedRadar, location.href);
  return {
    ...meta,
    headline: BriefingData.readerHeadline(reader, meta.headline),
    papers: allItems,
    radar: allItems.filter((row) => row.role === "radar"),
    issueDoc,
    reader,
    manifest,
    public_href: `${base}/email.html`,
    illustrated_href: `${base}/email-illustrated.html`,
    original_href: BriefingData.originalEmailPath(manifest, meta.date).replace(/^\.\/archive/, root),
  };
}

async function loadKnowledgeObject(path) {
  const normalized = text(path).replace(/^\.\//, "").replace(/^knowledge\//, "");
  if (!normalized) throw new Error("知识对象缺少 path");
  return getJson(`${state.roots.knowledge}/${normalized}`);
}

/* knowledge/graph.json is a derived publication. It is loaded lazily by the
 * routes that need it (#knowledge and Idea evidence/graph views), never by the
 * Idea Hub list, and a failure here degrades those pages instead of the site. */
async function loadKnowledgeGraph() {
  if (state.knowledgeGraphPromise) return state.knowledgeGraphPromise;
  state.knowledgeGraphPromise = (async () => {
    try {
      const raw = await getJson(`${state.roots.knowledge}/graph.json`);
      state.knowledgeGraph = BriefingData.validateKnowledgeGraph(raw);
    } catch (error) {
      state.knowledgeGraph = null;
      state.knowledgeGraphError = error;
    }
    return state.knowledgeGraph;
  })();
  return state.knowledgeGraphPromise;
}

async function loadData() {
  const [archiveResult, knowledgeResult, featurePlan] = await Promise.all([
    resolveRoot("archive"),
    resolveRoot("knowledge").catch((error) => ({ error })),
    optionalJson("./feature-plan.json"),
  ]);
  state.roots.archive = archiveResult.root;
  state.featurePlan = featurePlan;
  state.issues = await Promise.all((archiveResult.index.issues || []).map(loadArchiveIssue));
  state.issues.sort((a, b) => a.date.localeCompare(b.date));
  state.latest = state.issues.at(-1) || null;
  state.items = state.issues.flatMap((issue) => issue.papers);
  state.items.forEach((item) => {
    [item.item_id, item.brief_item_id, item.detail?.brief_item_id, item.id]
      .filter(Boolean)
      .forEach((id) => state.itemById.set(String(id), item));
  });

  if (knowledgeResult.error) {
    state.knowledgeError = knowledgeResult.error;
    return;
  }
  state.roots.knowledge = knowledgeResult.root;
  /* knowledge/manifest.json is a derived freshness projection; its absence
   * degrades to "publication manifest missing" instead of stale summaries
   * being shown as this issue's change. */
  state.manifest = await optionalJson(`${state.roots.knowledge}/manifest.json`);
  if (state.manifest?.publication_state === "knowledge_complete" && state.manifest.archive_head_issue) {
    state.issueDiff = await optionalJson(
      `${state.roots.knowledge}/issue-diffs/${state.manifest.archive_head_issue}.json`,
    );
  }
  try {
    state.knowledge = BriefingData.validateKnowledgeIndex(knowledgeResult.index);
    const [ideaPairs, roadmapPairs] = await Promise.all([
      Promise.all(
        state.knowledge.ideas.map(async (row) => [row.idea_id, await loadKnowledgeObject(row.path)]),
      ),
      Promise.all(
        state.knowledge.roadmaps.map(async (row) => [row.topic_id, await loadKnowledgeObject(row.path)]),
      ),
    ]);
    state.ideaObjects = new Map(ideaPairs);
    state.roadmapObjects = new Map(roadmapPairs);
  } catch (error) {
    state.knowledge = null;
    state.knowledgeError = error;
  }
}

function issueHref(date) {
  return `${state.roots.archive}/issues/${date}/email.html`;
}

function itemKey(item) {
  return String(item?.item_id || item?.brief_item_id || item?.detail?.brief_item_id || item?.id || "");
}

function evidenceItem(reference) {
  const id =
    typeof reference === "string"
      ? reference
      : reference?.item_id || reference?.brief_item_id || reference?.evidence_item_id;
  return id ? state.itemById.get(String(id)) : null;
}

function go(route, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value != null && value !== ""),
  ).toString();
  location.hash = `${route}${query ? `?${query}` : ""}`;
}

async function selectedRoadmap(route) {
  const entries = state.knowledge?.roadmaps || [];
  // A bare #roadmaps renders the browsable overview; only an explicit topic
  // param selects a detail page, and unknown topics 404 honestly instead of
  // silently falling back to the first entry.
  if (!route.params.topic) return { overview: true, row: null, object: null };
  const row = entries.find((candidate) => candidate.topic_id === route.params.topic) || null;
  if (!row) return { row: null, object: null };
  if (!state.roadmapObjects.has(row.topic_id)) {
    state.roadmapObjects.set(row.topic_id, await loadKnowledgeObject(row.path));
  }
  return { row, object: state.roadmapObjects.get(row.topic_id) };
}

function selectedIdea(route) {
  const rows = state.knowledge?.ideas || [];
  const row = rows.find((candidate) => candidate.idea_id === route.params.idea) || rows[0];
  return { row, object: row ? state.ideaObjects.get(row.idea_id) : null };
}

async function renderRoute() {
  const token = ++state.renderToken;
  // A route switch must never leak the previous canvas, listeners, or zoom.
  if (typeof GraphRenderer !== "undefined") GraphRenderer.destroyActive();
  state.route = BriefingData.parseRoute(location.hash);
  if (state.route.legacy) {
    // Old bookmarks render the new surface immediately and the address bar is
    // normalized once, without adding a history entry.
    const params = new URLSearchParams(
      Object.entries(state.route.params).filter(([, value]) => value != null && value !== ""),
    ).toString();
    history.replaceState(null, "", `#${state.route.name}${params ? `?${params}` : ""}`);
    state.route = BriefingData.parseRoute(location.hash);
  }
  document.body.dataset.route = state.route.name;
  document.body.dataset.view = state.route.params.view || "";
  const navRoute = state.route.name === "features" ? "home" : state.route.name;
  $$(".primary-nav a").forEach((link) =>
    link.classList.toggle("active", link.dataset.route === navRoute),
  );
  $("#primaryNav").classList.remove("open");
  $("#menuToggle").setAttribute("aria-expanded", "false");
  $("#appMain").innerHTML =
    '<div class="route-loading" aria-label="页面加载中"><span></span><span></span><span></span></div>';
  try {
    let context = {};
    if (state.route.name === "roadmaps") context = await selectedRoadmap(state.route);
    if (state.route.name === "ideas" && state.route.params.idea) {
      context = selectedIdea(state.route);
      if (state.route.params.view === "evidence" || state.route.params.view === "gaps") {
        context.graph = await loadKnowledgeGraph();
        context.graphError = state.knowledgeGraphError;
      }
    }
    if (state.route.name === "knowledge") {
      context.graph = await loadKnowledgeGraph();
      context.graphError = state.knowledgeGraphError;
    }
    if (token !== state.renderToken) return;
    renderWorkbenchView(state.route, context);
    document.title = `${$("#appMain h1")?.textContent || "技术情报"} · 技术情报工作台`;
    window.scrollTo({ top: 0, behavior: "auto" });
  } catch (error) {
    if (token !== state.renderToken) return;
    $("#appMain").innerHTML = `<div class="editorial-note negative">${icon("alert")}<div><b>页面加载失败</b><p>${esc(error.message)}</p></div></div>`;
  }
}

function buildSearchIndex() {
  const rows = [];
  (state.knowledge?.roadmaps || []).forEach((row) =>
    rows.push({ kind: "Roadmap", title: row.topic_name, note: row.summary, href: `#roadmaps?topic=${encodeURIComponent(row.topic_id)}` }),
  );
  (state.knowledge?.ideas || []).forEach((row) =>
    rows.push({ kind: "Idea", title: row.title, note: row.status, href: `#ideas?idea=${encodeURIComponent(row.idea_id)}` }),
  );
  state.items.forEach((row) =>
    rows.push({ kind: "日报条目", title: row.title, note: `${row.issue_date} · ${row.topic_name || "未分类"}`, href: row.url || issueHref(row.issue_date) }),
  );
  return rows;
}

function renderSearchResults(query = "") {
  const needle = norm(query);
  const matches = buildSearchIndex()
    .filter((row) => !needle || norm(`${row.title} ${row.note}`).includes(needle))
    .slice(0, 18);
  $("#searchResults").innerHTML = matches.length
    ? matches
        .map(
          (row) => `<a class="search-result" href="${esc(row.href)}" ${/^https?:/i.test(row.href) ? 'target="_blank" rel="noreferrer"' : ""}><span>${esc(row.kind)}</span><div><b>${esc(row.title)}</b><small>${esc(row.note || "")}</small></div></a>`,
        )
        .join("")
    : '<div class="empty-state"><b>没有匹配结果</b><p>换一个 Topic、Idea 名称或来源关键词试试。</p></div>';
  $$("#searchResults a").forEach((link) => link.addEventListener("click", () => $("#searchDialog").close()));
}

function bindShell() {
  $("#menuToggle").addEventListener("click", () => {
    const open = $("#primaryNav").classList.toggle("open");
    $("#menuToggle").setAttribute("aria-expanded", String(open));
  });
  const dialog = $("#searchDialog");
  const openSearch = () => {
    renderSearchResults();
    dialog.showModal();
    $("#searchInput").focus();
  };
  $("#searchTrigger").addEventListener("click", openSearch);
  $("[data-close-search]").addEventListener("click", () => dialog.close());
  $("#searchInput").addEventListener("input", (event) => renderSearchResults(event.target.value));
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearch();
    }
  });
  window.addEventListener("hashchange", renderRoute);
}

async function bootWorkbench() {
  bindShell();
  // Browser-local demo feedback on brief items; storage failures disable the
  // toggles instead of breaking the read-only site.
  try {
    state.feedback = new BriefingFeedback.LocalFeedbackStore(window.localStorage);
  } catch (_) {
    state.feedback = null;
  }
  try {
    await loadData();
  } catch (error) {
    $("#loadBanner").hidden = false;
    $("#loadBanner").textContent = `站点数据加载失败：${error.message}`;
  }
  if (state.knowledgeError) {
    $("#loadBanner").hidden = false;
    $("#loadBanner").textContent = "长期知识暂不可用；日报归档仍可独立查看。";
  }
  renderRoute();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootWorkbench);
} else {
  bootWorkbench();
}
