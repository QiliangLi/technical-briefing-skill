/* Stable, dependency-free data contracts shared by the static workbench and tests.
 * Route parsing, legacy-URL normalization, published-JSON validation, and the
 * two graph projections (knowledge graph, Idea evidence subgraph) live here.
 * This file never computes layout coordinates; positions come from the build-time
 * graph document or from the renderer's deterministic layout. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.BriefingData = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const TRACKING_PARAM = /^(?:utm_.+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid)$/i;

  function text(value) { return value == null ? '' : String(value).trim(); }
  function norm(value) {
    return text(value).toLowerCase().replace(/[\s_\-\/、，。:：()（）]+/g, '');
  }

  function itemId(item) {
    return text(item?.brief_item_id || item?.item_id || item?.source_item_id || item?.paper_key || item?.id);
  }

  function canonicalIdentity(item, baseUrl = 'https://example.invalid/') {
    const arxiv = text(item?.arxiv_id).replace(/v\d+$/i, '');
    if (arxiv) return `arxiv:${arxiv.toLowerCase()}`;
    const rawUrl = text(item?.url || item?.source_url || item?.source_urls?.[0]);
    if (rawUrl) {
      try {
        const url = new URL(rawUrl, baseUrl);
        url.hash = '';
        [...url.searchParams.keys()].forEach(key => {
          if (TRACKING_PARAM.test(key)) url.searchParams.delete(key);
        });
        url.searchParams.sort();
        let path = url.pathname.replace(/\/$/, '');
        if (/arxiv\.org$/i.test(url.hostname)) {
          path = path.replace(/v\d+$/i, '');
          const match = path.match(/^\/(?:abs|pdf)\/([^/]+?)(?:\.pdf)?$/i);
          if (match) return `arxiv:${match[1].toLowerCase()}`;
        }
        return `url:${url.hostname.toLowerCase()}${path.toLowerCase()}${url.search}`;
      } catch (_) {
        return `url:${rawUrl.replace(/#.*$/, '').replace(/\/$/, '').toLowerCase()}`;
      }
    }
    const id = itemId(item);
    return id ? `id:${id}` : `title:${norm(item?.title || item?.signal || item?.summary)}`;
  }

  function collectItemMap(doc) {
    const map = new Map();
    const seen = new Set();
    function walk(value, keyHint = '') {
      if (!value || typeof value !== 'object' || seen.has(value)) return;
      seen.add(value);
      if (Array.isArray(value)) {
        value.forEach(row => walk(row));
        return;
      }
      const explicitId = itemId(value);
      const hintedId = /^[a-z0-9:_-]{8,}$/i.test(keyHint) ? keyHint : '';
      const id = explicitId || hintedId;
      if (id) {
        const previous = map.get(id) || {};
        map.set(id, {...previous, ...value});
      }
      Object.entries(value).forEach(([key, row]) => walk(row, key));
    }
    walk(doc);
    return map;
  }

  function readerSummary(readerItem) {
    if (!readerItem || typeof readerItem !== 'object') return '';
    const paragraphs = Array.isArray(readerItem.paragraphs) ? readerItem.paragraphs.filter(Boolean) : [];
    const body = Array.isArray(readerItem.body) ? readerItem.body.filter(Boolean).join('\n\n') : readerItem.body;
    return text(
      readerItem.summary || readerItem.lead || readerItem.core_conclusion || readerItem.signal_summary ||
      body || paragraphs.join('\n\n') || readerItem.takeaway
    );
  }

  function mergeReaderItem(machineItem, readerItem) {
    const reader = readerItem && typeof readerItem === 'object' ? readerItem : {};
    const displayTitle = text(reader.title || reader.signal || machineItem.title || machineItem.signal);
    const displaySummary = readerSummary(reader) || text(machineItem.summary || machineItem.core_conclusion || machineItem.project_relevance);
    return {
      ...machineItem,
      machine_title: machineItem.title || machineItem.signal || '',
      title: displayTitle,
      summary: displaySummary,
      reader,
    };
  }

  function readerHeadline(reader, fallback = '') {
    return text(reader?.headline || reader?.synthesis?.headline || reader?.issue?.headline || fallback);
  }

  function radarFromIssue(issueDoc, issueDate) {
    const rows = issueDoc?.synthesis?.radar_signals || [];
    return rows.map((row, index) => ({
      id: `radar:${issueDate}:${index}`,
      item_id: text(row.brief_item_id || row.item_id) || `radar:${issueDate}:${index}`,
      paper_key: `radar:${issueDate}:${index}`,
      title: row.signal || row.summary || 'Radar signal',
      summary: row.summary || '',
      url: row.source_urls?.[0] || row.source_url || '',
      source_urls: row.source_urls || [],
      topic_name: row.category || '今日雷达',
      topic_id: `radar-${row.category || 'other'}`,
      direction_name: '今日雷达',
      role: 'radar',
      score: null,
      issue_date: issueDate,
      detail: row,
    }));
  }

  function mergeRadarWithoutDuplicates(papers, derivedRadar, baseUrl) {
    const result = [...(papers || [])];
    function radarKeys(row) {
      const keys = new Set([canonicalIdentity(row, baseUrl)]);
      const rawUrl = text(row?.url || row?.source_url || row?.source_urls?.[0]);
      if (rawUrl) keys.add(canonicalIdentity({...row, arxiv_id: '', url: rawUrl}, baseUrl));
      const title = norm(row?.title || row?.signal || row?.summary);
      if (title) keys.add(`title:${title}`);
      return [...keys].filter(Boolean);
    }
    const seen = new Set(result.filter(row => row.role === 'radar').flatMap(radarKeys));
    (derivedRadar || []).forEach(row => {
      const keys = radarKeys(row);
      if (!keys.length || keys.some(key => seen.has(key))) return;
      keys.forEach(key => seen.add(key));
      result.push(row);
    });
    return result;
  }

  function parseRoute(hash) {
    const raw = text(hash).replace(/^#/, '');
    const [rawName, query = ''] = raw.split('?');
    let params = Object.fromEntries(new URLSearchParams(query));
    let name = rawName || 'home';
    let legacy = false;
    // Legacy bookmark normalization. Old routes never render a second page;
    // they map onto the current Knowledge / Idea surfaces once, here.
    if (name === 'evidence' || name === 'graph' || name === 'atlas') {
      legacy = true;
      const legacyView = text(params.view) || (name === 'graph' ? 'graph' : name === 'atlas' ? 'atlas' : 'path');
      if (params.idea && legacyView !== 'atlas') {
        name = 'ideas';
        params = legacyView === 'gaps'
          ? { idea: params.idea, view: 'gaps' }
          : normalizeIdeaViewParams({
              idea: params.idea,
              view: 'evidence',
              mode: legacyView === 'graph' ? 'graph' : 'path',
              depth: params.depth,
              node: params.node,
            });
      } else {
        name = "knowledge";
        if (legacyView === "atlas") {
          // #atlas carries issue/topic scoping that translates into the
          // evolution lens; #graph without an idea simply lands on #knowledge.
          const evolutionParams = { lens: "evolution" };
          if (params.issue) {
            evolutionParams.from = params.issue;
            evolutionParams.to = params.issue;
          }
          if (params.topic) evolutionParams.topic = params.topic;
          params = evolutionParams;
        } else {
          params = {};
        }
      }
    } else {
      const aliases = { roadmap: 'roadmaps', 'idea-bank': 'ideas', dashboard: 'home', plan: 'features' };
      name = aliases[name] || name || 'home';
    }
    const allowed = new Set(['home', 'roadmaps', 'ideas', 'knowledge', 'archive', 'features']);
    if (!allowed.has(name)) {
      name = 'home';
      params = {};
    }
    if (name === 'knowledge') params = normalizeKnowledgeParams(params);
    if (name === 'ideas' && params.idea) params = normalizeIdeaViewParams(params);
    return { name, params, legacy };
  }

  const KNOWLEDGE_LENSES = new Set(['structure', 'evolution', 'judgements']);
  const KNOWLEDGE_RANGES = new Set(['latest', 'recent3', 'all', 'custom']);
  const KNOWLEDGE_OVERLAYS = new Set(['roadmap', 'idea']);
  const KNOWLEDGE_HIDEABLE_KINDS = new Set(['topic', 'direction', 'item', 'judgement', 'issue', 'roadmap', 'roadmap_branch', 'idea']);

  function normalizeKnowledgeParams(params = {}) {
    const lens = KNOWLEDGE_LENSES.has(text(params.lens)) ? text(params.lens) : 'structure';
    const from = text(params.from);
    const to = text(params.to);
    let range = KNOWLEDGE_RANGES.has(text(params.range)) ? text(params.range) : 'recent3';
    if (from && to) range = 'custom';
    const overlays = [...new Set(text(params.overlay).split(',').map((value) => value.trim()).filter((value) => KNOWLEDGE_OVERLAYS.has(value)))].sort();
    const hidden = [...new Set(text(params.hide).split(',').map((value) => value.trim()).filter((value) => KNOWLEDGE_HIDEABLE_KINDS.has(value)))].sort();
    const result = {
      lens,
      range,
      overlay: overlays.join(','),
      hide: hidden.join(','),
    };
    ['topic', 'direction', 'node'].forEach((key) => {
      if (text(params[key])) result[key] = text(params[key]);
    });
    if (from) result.from = from;
    if (to) result.to = to;
    if (String(params.unresolved) === '1') result.unresolved = '1';
    return result;
  }

  const IDEA_VIEWS = new Set(['overview', 'evidence', 'gaps']);

  function normalizeIdeaViewParams(params = {}) {
    const view = IDEA_VIEWS.has(text(params.view)) ? text(params.view) : 'overview';
    const result = { view };
    if (text(params.idea)) result.idea = text(params.idea);
    if (view === 'evidence') {
      const mode = text(params.mode) === 'graph' ? 'graph' : 'path';
      result.mode = mode;
      if (mode === 'graph') {
        result.depth = Number.parseInt(params.depth, 10) === 2 ? '2' : '1';
        if (text(params.node)) result.node = text(params.node);
      }
    }
    return result;
  }

  function stableGraphId(kind, value) {
    return `${text(kind).toLowerCase()}:${text(value).replace(/\s+/g, '-').replace(/[^\p{L}\p{N}:._-]+/gu, '') || 'unknown'}`;
  }

  /* ---------------------------------------------------------------- *
   * Knowledge graph projection (#knowledge)
   * ---------------------------------------------------------------- */

  const KNOWLEDGE_LENS_KINDS = {
    structure: ['topic', 'direction'],
    evolution: ['topic', 'direction', 'item', 'issue'],
    judgements: ['topic', 'direction', 'item', 'judgement'],
  };
  const SOFT_NODE_LIMIT = 60;
  const SOFT_EDGE_LIMIT = 120;
  const HARD_NODE_LIMIT = 250;
  const HARD_EDGE_LIMIT = 500;
  const KIND_ORDER = { roadmap: 0, topic: 1, roadmap_branch: 2, direction: 3, item: 4, judgement: 5, issue: 5, idea: 6 };

  function validateKnowledgeGraph(value) {
    if (
      !value || typeof value !== 'object' ||
      value.schema_version !== 1 ||
      !Array.isArray(value.nodes) || !Array.isArray(value.edges) || !Array.isArray(value.unresolved) ||
      typeof value.archive_through_issue !== 'string' ||
      typeof value.knowledge_through_issue !== 'string' ||
      typeof value.input_digest !== 'string' ||
      !value.input_digest.startsWith('sha256:') ||
      !value.stats || typeof value.stats.node_count !== 'number'
    ) {
      throw new Error('knowledge/graph.json 不符合 schema_version=1 发布合同');
    }
    return value;
  }

  function buildKnowledgeGraphModel(input = {}) {
    const params = normalizeKnowledgeParams(input.params || {});
    const emptyLimits = { nodeLimit: 0, edgeLimit: 0, nodeCount: 0, edgeCount: 0, totalNodeCount: 0, totalEdgeCount: 0, truncated: false };
    const emptyStats = { nodeCount: 0, edgeCount: 0, unresolvedCount: 0, byKind: {}, byRelation: {} };
    const graph = input.graph;
    if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) {
      return {
        unavailable: true,
        params,
        nodes: [],
        edges: [],
        unresolved: [],
        issueDates: [],
        focusId: '',
        requestedFocusMissing: false,
        limits: emptyLimits,
        stats: emptyStats,
      };
    }

    const issueDates = graph.nodes
      .filter((node) => node.data.kind === 'issue')
      .map((node) => text(node.data.issue_date) || text(node.data.label))
      .filter(Boolean)
      .sort();
    const latest = issueDates.at(-1) || '';
    const recentDates = new Set(issueDates.slice(-3));
    const overlays = new Set(text(params.overlay).split(',').filter(Boolean));
    const kinds = new Set(KNOWLEDGE_LENS_KINDS[params.lens] || KNOWLEDGE_LENS_KINDS.structure);
    if (overlays.has('roadmap')) {
      kinds.add('roadmap');
      kinds.add('roadmap_branch');
    }
    if (overlays.has('idea')) kinds.add('idea');

    const outgoing = new Map();
    const incoming = new Map();
    graph.edges.forEach((edge) => {
      const data = edge.data;
      if (!outgoing.has(data.source)) outgoing.set(data.source, []);
      outgoing.get(data.source).push(data);
      if (!incoming.has(data.target)) incoming.set(data.target, []);
      incoming.get(data.target).push(data);
    });

    function itemInRange(node) {
      if (params.range === 'all') return true;
      const date = text(node.data.issue_date) || text(node.data.first_issue_date);
      if (params.range === 'latest') return Boolean(latest) && date === latest;
      if (params.range === 'recent3') return recentDates.has(date);
      if (params.range === 'custom') {
        if (params.from && date && date < params.from) return false;
        if (params.to && date && date > params.to) return false;
        return true;
      }
      return true;
    }

    const topicFilter = text(params.topic);
    const directionFilter = text(params.direction);
    const visible = new Set();
    const topics = graph.nodes.filter((node) => node.data.kind === 'topic' && (!topicFilter || node.data.id === `topic:${topicFilter}`));
    topics.forEach((node) => visible.add(node.data.id));

    const directions = [];
    topics.forEach((topic) => {
      (outgoing.get(topic.data.id) || []).forEach((edge) => {
        if (edge.relation !== 'has_direction') return;
        if (directionFilter && edge.target !== `direction:${directionFilter}`) return;
        if (!visible.has(edge.target)) {
          visible.add(edge.target);
          const node = graph.nodes.find((candidate) => candidate.data.id === edge.target);
          if (node) directions.push(node);
        }
      });
    });

    const visibleItemIds = new Set();
    if (kinds.has('item')) {
      directions.forEach((direction) => {
        (outgoing.get(direction.data.id) || []).forEach((edge) => {
          if (edge.relation !== 'has_item' || visible.has(edge.target)) return;
          const node = graph.nodes.find((candidate) => candidate.data.id === edge.target);
          if (node && itemInRange(node)) {
            visible.add(node.data.id);
            visibleItemIds.add(node.data.id);
          }
        });
      });
    }
    if (kinds.has('issue')) {
      if (kinds.has('item')) {
        // Issues enter only through the items actually shown, so range and
        // Topic/Direction filters never leak unrelated issue nodes.
        graph.edges.forEach((edge) => {
          if (edge.data.relation === 'published_in' && visibleItemIds.has(edge.data.source)) {
            visible.add(edge.data.target);
          }
        });
      } else {
        graph.nodes.forEach((node) => {
          if (node.data.kind !== 'issue' || visible.has(node.data.id)) return;
          if (params.range === 'latest') {
            if (text(node.data.issue_date) === latest) visible.add(node.data.id);
          } else if (params.range === 'recent3') {
            if (recentDates.has(text(node.data.issue_date))) visible.add(node.data.id);
          } else if (params.range === 'custom') {
            const date = text(node.data.issue_date);
            if ((!params.from || date >= params.from) && (!params.to || date <= params.to)) visible.add(node.data.id);
          } else {
            visible.add(node.data.id);
          }
        });
      }
    }
    if (kinds.has('judgement')) {
      // A judgement is visible exactly when it explicitly cites a visible
      // item, so judgements from other Topics never leak into a filtered view.
      graph.edges.forEach((edge) => {
        if (edge.data.relation === 'supports_judgement' && visibleItemIds.has(edge.data.source)) {
          visible.add(edge.data.target);
        }
      });
    }
    if (overlays.has('roadmap')) {
      graph.nodes.forEach((node) => {
        if (visible.has(node.data.id)) return;
        if (node.data.kind === 'roadmap') {
          const tracksTopic = (outgoing.get(node.data.id) || []).some((edge) => edge.relation === 'tracks' && visible.has(edge.target));
          if (tracksTopic || !topics.length) visible.add(node.data.id);
        }
      });
      graph.nodes.forEach((node) => {
        if (node.data.kind !== 'roadmap_branch' || visible.has(node.data.id)) return;
        const organizesVisible = (outgoing.get(node.data.id) || []).some((edge) => edge.relation === 'organizes' && visible.has(edge.target));
        if (organizesVisible) visible.add(node.data.id);
      });
    }
    if (overlays.has('idea')) {
      graph.nodes.forEach((node) => {
        if (node.data.kind !== 'idea' || visible.has(node.data.id)) return;
        const relatesToVisible = (outgoing.get(node.data.id) || []).some((edge) => edge.relation === 'relates_to' && visible.has(edge.target));
        if (relatesToVisible) visible.add(node.data.id);
      });
    }

    if (String(params.unresolved) === '1') {
      const unresolvedIds = new Set();
      (graph.unresolved || []).forEach((entry) => {
        [entry.source_ref, entry.target_ref].forEach((ref) => {
          if (ref && visible.has(ref)) unresolvedIds.add(ref);
        });
      });
      visible.forEach((id) => {
        if (!unresolvedIds.has(id)) visible.delete(id);
      });
    }

    // Node-type filtering applies after structural reachability so hiding a
    // bridge kind never rewrites how the remaining graph was derived. Edges
    // are then re-derived from the FINAL node set so a hidden kind can never
    // leave a dangling edge behind.
    const hiddenKinds = new Set(text(params.hide).split(',').filter(Boolean));
    let nodes = graph.nodes.filter((node) => visible.has(node.data.id) && !hiddenKinds.has(node.data.kind));
    const filteredIds = new Set(nodes.map((node) => node.data.id));
    let edges = graph.edges.filter((edge) => filteredIds.has(edge.data.source) && filteredIds.has(edge.data.target));

    const requestedFocus = text(params.node);
    let focusId = requestedFocus && filteredIds.has(requestedFocus)
      ? requestedFocus
      : topics.find((topic) => filteredIds.has(topic.data.id))?.data.id || nodes[0]?.data.id || '';
    const oneHop = new Set();
    if (focusId) {
      (outgoing.get(focusId) || []).forEach((edge) => oneHop.add(edge.target));
      (incoming.get(focusId) || []).forEach((edge) => oneHop.add(edge.source));
    }

    const nodeLimit = params.range === 'all' ? HARD_NODE_LIMIT : SOFT_NODE_LIMIT;
    const edgeLimit = params.range === 'all' ? HARD_EDGE_LIMIT : SOFT_EDGE_LIMIT;
    let truncated = false;
    if (nodes.length > nodeLimit) {
      const priority = (node) => {
        if (node.data.id === focusId) return 0;
        if (oneHop.has(node.data.id)) return 1;
        if (node.data.kind === 'judgement') return 2;
        return 3;
      };
      const keep = new Set(nodes.slice().sort((a, b) => {
        const priorityDelta = priority(a) - priority(b);
        if (priorityDelta) return priorityDelta;
        const dateDelta = text(b.data.issue_date).localeCompare(text(a.data.issue_date));
        return dateDelta || a.data.id.localeCompare(b.data.id);
      }).slice(0, nodeLimit).map((node) => node.data.id));
      nodes = nodes.filter((node) => keep.has(node.data.id));
      edges = edges.filter((edge) => keep.has(edge.data.source) && keep.has(edge.data.target));
      truncated = true;
    }
    if (edges.length > edgeLimit) {
      const focusFirst = (edge) => (edge.data.source === focusId || edge.data.target === focusId ? 0 : 1);
      const keepEdges = edges.slice().sort((a, b) => {
        const focusDelta = focusFirst(a) - focusFirst(b);
        return focusDelta || a.data.id.localeCompare(b.data.id);
      }).slice(0, edgeLimit);
      const keptEdgeIds = new Set(keepEdges.map((edge) => edge.data.id));
      edges = edges.filter((edge) => keptEdgeIds.has(edge.data.id));
      const stillVisible = new Set(edges.flatMap((edge) => [edge.data.source, edge.data.target]));
      nodes = nodes.filter((node) => stillVisible.has(node.data.id) || node.data.id === focusId);
      truncated = true;
    }
    if (!nodes.some((node) => node.data.id === focusId)) focusId = nodes[0]?.data.id || '';

    const byKind = {};
    const byRelation = {};
    graph.nodes.forEach((node) => { byKind[node.data.kind] = (byKind[node.data.kind] || 0) + 1; });
    graph.edges.forEach((edge) => { byRelation[edge.data.relation] = (byRelation[edge.data.relation] || 0) + 1; });

    return {
      unavailable: false,
      params,
      nodes,
      edges,
      unresolved: graph.unresolved || [],
      issueDates,
      focusId,
      requestedFocusMissing: Boolean(requestedFocus && requestedFocus !== focusId),
      limits: {
        nodeLimit,
        edgeLimit,
        nodeCount: nodes.length,
        edgeCount: edges.length,
        totalNodeCount: graph.nodes.length,
        totalEdgeCount: graph.edges.length,
        truncated,
      },
      stats: {
        nodeCount: graph.nodes.length,
        edgeCount: graph.edges.length,
        unresolvedCount: (graph.unresolved || []).length,
        byKind,
        byRelation,
      },
    };
  }

  /* ---------------------------------------------------------------- *
   * Idea evidence subgraph projection (#ideas?...&view=evidence)
   * ---------------------------------------------------------------- */

  const IDEA_GRAPH_NODE_LIMIT = 60;
  const IDEA_GRAPH_EDGE_LIMIT = 100;
  const IDEA_SUBGRAPH_RELATION_LABELS = {
    relates_to: '关联专题',
    supports_idea: '支持',
    challenges_idea: '反对',
    published_in: '发布于',
    supports_judgement: '支持判断',
    uses_evidence: '引用证据',
    tracks: '跟踪',
    qualifies: '限定',
    leads_to: '导向',
  };

  function buildIdeaEvidenceGraphModel(input = {}) {
    const params = normalizeIdeaViewParams({ ...(input.params || {}), view: 'evidence' });
    const depth = params.mode === 'graph' ? (params.depth === '2' ? 2 : 1) : 1;
    const idea = input.idea || {};
    const ideaRow = input.ideaRow || {};
    const ideaId = text(idea.idea_id || ideaRow.idea_id);
    const ideaNodeId = `idea:${ideaId}`;
    const graph = input.graph && Array.isArray(input.graph.nodes) && Array.isArray(input.graph.edges) ? input.graph : null;
    const itemMap = new Map();
    (Array.isArray(input.items) ? input.items : []).forEach((item) => {
      [itemId(item), text(item?.id), text(item?.brief_item_id)].filter(Boolean).forEach((id) => itemMap.set(id, item));
    });

    const nodes = new Map();
    const edges = new Map();
    const unresolved = [];

    function addNode(raw) {
      if (!raw?.id || nodes.has(raw.id)) return;
      const { position, provenance, ...data } = raw;
      nodes.set(raw.id, { data, position, provenance: provenance || [] });
    }
    function addEdge(source, target, relation, provenance = {}) {
      if (!nodes.has(source) || !nodes.has(target)) return;
      const id = `edge:${relation}:${source}->${target}`;
      if (edges.has(id)) return;
      edges.set(id, {
        data: {
          id,
          source,
          target,
          relation,
          label: IDEA_SUBGRAPH_RELATION_LABELS[relation] || relation,
          confirmation: 'explicit',
        },
        provenance: [provenance],
      });
    }
    function addGraphObject(node) {
      if (!node) return;
      addNode({ ...node.data, position: node.position, provenance: node.provenance });
    }

    addNode({
      id: ideaNodeId,
      kind: 'idea',
      label: text(idea.title || ideaRow.title) || '未命名 Idea',
      status: text(idea.status || ideaRow.status),
      summary: text(idea.hypothesis || idea.problem),
      href: ideaId ? `#ideas?idea=${encodeURIComponent(ideaId)}&view=overview` : '',
      provenance: [{ path: 'idea', object_id: ideaId, field: 'idea' }],
    });

    const evidenceItemIds = new Set();
    if (graph) {
      const nodeById = new Map(graph.nodes.map((node) => [node.data.id, node]));
      const publishedEdges = graph.edges.filter((edge) =>
        edge.data.target === ideaNodeId && ['supports_idea', 'challenges_idea'].includes(edge.data.relation));
      publishedEdges.forEach((edge) => {
        addGraphObject(nodeById.get(edge.data.source));
        evidenceItemIds.add(edge.data.source);
        edges.set(edge.data.id, edge);
      });
      graph.edges
        .filter((edge) => edge.data.source === ideaNodeId && edge.data.relation === 'relates_to')
        .forEach((edge) => {
          addGraphObject(nodeById.get(edge.data.target));
          edges.set(edge.data.id, edge);
        });
      if (depth >= 2) {
        graph.edges.forEach((edge) => {
          const data = edge.data;
          const connectsEvidence = evidenceItemIds.has(data.source) || evidenceItemIds.has(data.target);
          if (!connectsEvidence) return;
          if (data.relation === 'published_in' || data.relation === 'supports_judgement') {
            addGraphObject(nodeById.get(data.source));
            addGraphObject(nodeById.get(data.target));
            edges.set(data.id, edge);
          } else if (data.relation === 'uses_evidence' && evidenceItemIds.has(data.target)) {
            addGraphObject(nodeById.get(data.source));
            edges.set(data.id, edge);
          }
        });
      }
    } else {
      // Fallback projection from the Idea object itself when the published
      // graph document is unavailable. Still explicit fields only.
      const entries = [
        ...(Array.isArray(idea.evidence_for) ? idea.evidence_for.map((row) => ({ ...row, relation: 'supports_idea' })) : []),
        ...(Array.isArray(idea.evidence_against) ? idea.evidence_against.map((row) => ({ ...row, relation: 'challenges_idea' })) : []),
      ];
      entries.forEach((entry) => {
        const ref = text(entry.item_id || entry.brief_item_id || entry.evidence_item_id);
        const item = itemMap.get(ref);
        if (!ref || !item) {
          unresolved.push({ reason: 'missing_archive_item', source_ref: ref || 'unknown', target_ref: ideaNodeId });
          return;
        }
        const itemNodeId = `item:${ref}`;
        addNode({
          id: itemNodeId,
          kind: 'item',
          label: text(item.title) || '归档条目',
          topic_id: text(item.topic_id),
          direction_id: text(item.direction_id),
          issue_date: text(item.issue_date),
          href: text(item.issue_date) ? `#archive?date=${encodeURIComponent(item.issue_date)}&item=${encodeURIComponent(ref)}` : '',
          provenance: [{ path: 'archive', object_id: ref, field: 'brief_item_id' }],
        });
        evidenceItemIds.add(itemNodeId);
        addEdge(itemNodeId, ideaNodeId, entry.relation, { path: 'idea', object_id: ideaId, field: entry.relation === 'supports_idea' ? 'evidence_for' : 'evidence_against' });
      });
      (Array.isArray(idea.topic_ids) ? idea.topic_ids : []).forEach((topicId) => {
        const topicNodeId = `topic:${topicId}`;
        addNode({
          id: topicNodeId,
          kind: 'topic',
          label: text(topicId),
          topic_id: text(topicId),
          provenance: [{ path: 'idea', object_id: ideaId, field: 'topic_ids' }],
        });
        addEdge(ideaNodeId, topicNodeId, 'relates_to', { path: 'idea', object_id: ideaId, field: 'topic_ids' });
      });
    }

    // Idea-field projections: assumptions and decisions are read-only views of
    // Idea fields and never receive persistent identities.
    const assumptions = Array.isArray(idea.unknowns) && idea.unknowns.length
      ? idea.unknowns.map((title, index) => ({ title, field: `unknowns[${index}]` }))
      : text(idea.hypothesis) ? [{ title: idea.hypothesis, field: 'hypothesis' }] : [];
    assumptions.forEach((assumption, index) => {
      const id = `assumption:${ideaId}:${index + 1}`;
      addNode({
        id,
        kind: 'assumption',
        label: text(assumption.title) || '关键假设',
        status: '待验证',
        href: `#ideas?idea=${encodeURIComponent(ideaId)}&view=gaps`,
        provenance: [{ path: 'idea', object_id: ideaId, field: assumption.field }],
      });
      addEdge(ideaNodeId, id, 'qualifies', { path: 'idea', object_id: ideaId, field: assumption.field });
    });
    (Array.isArray(idea.decision_log) ? idea.decision_log : []).forEach((event, index) => {
      const rawId = text(event.event_id) || `${ideaId}:${index + 1}`;
      const id = `decision:${rawId}`;
      addNode({
        id,
        kind: 'decision',
        label: text(event.decision) || 'Decision',
        status: text(event.to_status),
        issue_date: text(event.issue_date),
        description: text(event.reason),
        provenance: [{ path: 'idea', object_id: rawId, field: 'decision_log' }],
      });
      addEdge(ideaNodeId, id, 'leads_to', { path: 'idea', object_id: rawId, field: 'decision_log' });
    });

    const IDEA_SUBGRAPH_KIND_ORDER = { idea: 0, item: 1, topic: 2, judgement: 3, issue: 3, roadmap_branch: 4, roadmap: 4, assumption: 5, decision: 5 };
    let nodeRows = [...nodes.values()].sort((a, b) => (IDEA_SUBGRAPH_KIND_ORDER[a.data.kind] ?? 9) - (IDEA_SUBGRAPH_KIND_ORDER[b.data.kind] ?? 9) || a.data.id.localeCompare(b.data.id));
    let edgeRows = [...edges.values()].sort((a, b) => a.data.id.localeCompare(b.data.id));
    let truncated = false;
    if (nodeRows.length > IDEA_GRAPH_NODE_LIMIT) {
      const priority = (node) => {
        if (node.data.id === ideaNodeId) return 0;
        if (['assumption', 'decision'].includes(node.data.kind)) return 1;
        if (evidenceItemIds.has(node.data.id) || node.data.kind === 'topic') return 2;
        return 3;
      };
      const keep = new Set(nodeRows.slice().sort((a, b) => {
        const priorityDelta = priority(a) - priority(b);
        if (priorityDelta) return priorityDelta;
        return text(b.data.issue_date).localeCompare(text(a.data.issue_date)) || a.data.id.localeCompare(b.data.id);
      }).slice(0, IDEA_GRAPH_NODE_LIMIT).map((node) => node.data.id));
      nodeRows = nodeRows.filter((node) => keep.has(node.data.id));
      edgeRows = edgeRows.filter((edge) => keep.has(edge.data.source) && keep.has(edge.data.target));
      truncated = true;
    }
    if (edgeRows.length > IDEA_GRAPH_EDGE_LIMIT) {
      edgeRows = edgeRows.slice(0, IDEA_GRAPH_EDGE_LIMIT);
      const stillVisible = new Set(edgeRows.flatMap((edge) => [edge.data.source, edge.data.target]));
      nodeRows = nodeRows.filter((node) => stillVisible.has(node.data.id) || node.data.id === ideaNodeId);
      truncated = true;
    }

    const requestedFocus = text(params.node);
    const renderedIds = new Set(nodeRows.map((node) => node.data.id));
    const focusId = renderedIds.has(requestedFocus) ? requestedFocus : ideaNodeId;
    const ideaIncoming = edgeRows.filter((edge) => edge.data.target === ideaNodeId).map((edge) => edge.data.relation);

    return {
      nodes: nodeRows,
      edges: edgeRows,
      focusId,
      requestedFocusMissing: Boolean(requestedFocus && !renderedIds.has(requestedFocus)),
      unresolved: unresolved.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      conflict: ideaIncoming.includes('supports_idea') && ideaIncoming.includes('challenges_idea'),
      evidenceItemIds: [...evidenceItemIds],
      usesPublishedGraph: Boolean(graph),
      limits: { depth, nodeCount: nodeRows.length, edgeCount: edgeRows.length, truncated },
    };
  }

  function knowledgePath(path) {
    const value = text(path).replace(/^\.\//, '');
    if (!value) return '';
    if (/^https?:\/\//i.test(value)) return value;
    return value.startsWith('knowledge/') ? `./${value}` : `./knowledge/${value}`;
  }

  function validateKnowledgeIndex(value) {
    if (!value || value.schema_version !== 1 || !Array.isArray(value.roadmaps) || !Array.isArray(value.ideas)) {
      throw new Error('knowledge/index.json 不符合 schema_version=1 合同');
    }
    return value;
  }

  function originalEmailPath(manifest, date) {
    if (!manifest || typeof manifest !== 'object') return '';
    const flatFileKeys = manifest.files && !Array.isArray(manifest.files) && typeof manifest.files === 'object'
      ? Object.keys(manifest.files)
      : [];
    const candidates = [
      ...(Array.isArray(manifest.original_variants) ? manifest.original_variants.map(name => `original/${name}`) : []),
      ...(Array.isArray(manifest.original_files) ? manifest.original_files : []),
      ...(Array.isArray(manifest.files?.original) ? manifest.files.original : []),
      ...flatFileKeys.filter(path => /^original\/email(?:-illustrated)?\.html$/i.test(path)),
      manifest.original_email,
      manifest.artifacts?.original_email,
    ].filter(Boolean).map(value => typeof value === 'string' ? value : value.path).filter(Boolean);
    const match = candidates.find(path => /(?:^|\/)email\.html$/i.test(path)) || candidates.find(path => /(?:^|\/)email-illustrated\.html$/i.test(path));
    if (!match) return '';
    if (/^https?:\/\//i.test(match)) return match;
    if (match.startsWith('archive/')) return `./${match}`;
    if (match.startsWith('issues/')) return `./archive/${match}`;
    if (match.startsWith('original/')) return `./archive/issues/${date}/${match}`;
    return `./archive/issues/${date}/original/${match.replace(/^.*\//, '')}`;
  }

  return {
    canonicalIdentity,
    collectItemMap,
    itemId,
    buildIdeaEvidenceGraphModel,
    buildKnowledgeGraphModel,
    knowledgePath,
    mergeRadarWithoutDuplicates,
    mergeReaderItem,
    norm,
    normalizeIdeaViewParams,
    normalizeKnowledgeParams,
    originalEmailPath,
    parseRoute,
    radarFromIssue,
    readerHeadline,
    readerSummary,
    stableGraphId,
    validateKnowledgeGraph,
    validateKnowledgeIndex,
  };
});
