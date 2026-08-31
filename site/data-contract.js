/* Stable, dependency-free data contracts shared by the static workbench and tests. */
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
    const aliases = {roadmap: 'roadmaps', 'idea-bank': 'ideas', graph: 'evidence', atlas: 'evidence', dashboard: 'home', plan: 'features'};
    const requested = aliases[rawName] || rawName || 'home';
    const allowed = new Set(['home', 'roadmaps', 'ideas', 'evidence', 'archive', 'features']);
    const name = allowed.has(requested) ? requested : 'home';
    const params = Object.fromEntries(new URLSearchParams(query));
    if (name === 'evidence') {
      const aliasView = rawName === 'graph' ? 'graph' : rawName === 'atlas' ? 'atlas' : '';
      Object.assign(params, normalizeEvidenceParams({...params, view: aliasView || params.view}));
    }
    return {name, params};
  }

  function normalizeEvidenceParams(params = {}) {
    const views = new Set(['path', 'graph', 'gaps', 'atlas']);
    const view = views.has(text(params.view)) ? text(params.view) : 'path';
    const rawDepth = Number.parseInt(params.depth, 10);
    const depth = rawDepth === 2 ? '2' : '1';
    const candidates = String(params.candidates) === '1' ? '1' : '0';
    const scope = text(params.scope) === 'latest' ? 'latest' : 'all';
    const mode = text(params.mode) === 'keyword' ? 'keyword' : 'topic';
    return {
      ...params,
      view,
      ...(view === 'graph' ? {depth, candidates} : {}),
      ...(view === 'atlas' ? {scope, mode} : {}),
    };
  }

  function stableGraphId(kind, value) {
    return `${text(kind).toLowerCase()}:${text(value).replace(/\s+/g, '-').replace(/[^\p{L}\p{N}:._-]+/gu, '') || 'unknown'}`;
  }

  function buildEvidenceGraphModel(input = {}) {
    const params = normalizeEvidenceParams(input.params || {});
    const idea = input.idea || {};
    const ideaRow = input.ideaRow || {};
    const itemRows = Array.isArray(input.items) ? input.items : [];
    const itemMap = new Map();
    itemRows.forEach(item => {
      [itemId(item), text(item?.id), text(item?.brief_item_id)].filter(Boolean).forEach(id => itemMap.set(id, item));
    });
    const roadmapRows = Array.isArray(input.roadmaps) ? input.roadmaps : [];
    const roadmapObjects = input.roadmapObjects instanceof Map
      ? input.roadmapObjects
      : new Map(Object.entries(input.roadmapObjects || {}));
    const nodes = new Map();
    const edges = [];
    const unresolved = [];

    function addNode(node) {
      if (!node?.id || nodes.has(node.id)) return nodes.get(node?.id);
      const value = {
        subtitle: '', status: '', provenance: {}, href: '', unresolved: false,
        ...node,
      };
      nodes.set(value.id, value);
      return value;
    }
    function addEdge(source, target, relation, provenance, confirmation = 'confirmed') {
      if (!nodes.has(source) || !nodes.has(target)) {
        unresolved.push({reason: 'dangling_edge', sourceRef: source, targetRef: target});
        return;
      }
      if (!source || !target || !relation || !provenance || !Object.keys(provenance).length) {
        unresolved.push({reason: 'incomplete_provenance', sourceRef: source, targetRef: target});
        return;
      }
      const id = stableGraphId('edge', `${source}:${relation}:${target}:${edges.length}`);
      edges.push({id, source, target, relation, confirmation, provenance});
    }

    const ideaId = stableGraphId('idea', idea.idea_id || ideaRow.idea_id);
    addNode({
      id: ideaId,
      kind: 'idea',
      title: text(idea.title || ideaRow.title) || '未命名 Idea',
      subtitle: text(idea.hypothesis || idea.idea_type || ideaRow.idea_type),
      status: text(idea.status || ideaRow.status),
      provenance: {object_id: text(idea.idea_id || ideaRow.idea_id), field: 'idea'},
      href: idea.idea_id || ideaRow.idea_id ? `#ideas?idea=${encodeURIComponent(idea.idea_id || ideaRow.idea_id)}` : '',
    });

    const evidenceEntries = [
      ...(Array.isArray(idea.evidence_for) ? idea.evidence_for.map(row => ({...row, relation: 'supports'})) : []),
      ...(Array.isArray(idea.evidence_against) ? idea.evidence_against.map(row => ({...row, relation: 'challenges'})) : []),
    ];
    const evidenceIds = new Map();
    evidenceEntries.forEach((entry, index) => {
      const ref = text(entry.item_id || entry.brief_item_id || entry.evidence_item_id);
      const item = itemMap.get(ref);
      const evidenceId = stableGraphId('evidence', ref || `${ideaId}:${index}`);
      evidenceIds.set(ref, evidenceId);
      addNode({
        id: evidenceId,
        kind: 'evidence',
        title: '证据记录',
        subtitle: text(item?.issue_date || entry.issue_date) || '期次未记录',
        status: item ? '已发布' : '未解析',
        provenance: {object_id: text(idea.idea_id || ideaRow.idea_id), field: entry.relation === 'supports' ? 'evidence_for' : 'evidence_against', item_id: ref},
        href: item?.issue_date ? `#archive?date=${encodeURIComponent(item.issue_date)}` : '',
        unresolved: !item,
        description: text(entry.reason),
      });
      if (item) {
        const sourceId = stableGraphId('source', ref || canonicalIdentity(item));
        addNode({
          id: sourceId,
          kind: 'source',
          title: text(item.title) || '归档条目',
          subtitle: [text(item.topic_name), text(item.issue_date)].filter(Boolean).join(' · '),
          status: '已发布',
          provenance: {object_id: ref, field: item.url ? 'url' : 'archive'},
          href: text(item.url),
          issueDate: text(item.issue_date),
        });
        addEdge(sourceId, evidenceId, 'declares', {object_id: ref, field: item.url ? 'url' : 'archive'});
      } else {
        unresolved.push({reason: 'missing_archive_item', sourceRef: ref, targetRef: evidenceId});
      }
      if (item) {
        addEdge(evidenceId, ideaId, entry.relation, {
          object_id: text(idea.idea_id || ideaRow.idea_id),
          field: entry.relation === 'supports' ? 'evidence_for' : 'evidence_against',
          item_id: ref,
        });
      }
    });

    if (evidenceEntries.length) {
      addNode({
        id: stableGraphId('claim', `${ideaId}:unmaterialized`),
        kind: 'claim',
        title: 'Claim 尚未物化',
        subtitle: '当前来源对象没有可定位 Claim',
        status: '尚未物化',
        provenance: {object_id: text(idea.idea_id || ideaRow.idea_id), field: 'evidence_for/evidence_against'},
        unresolved: true,
      });
    }

    const assumptions = Array.isArray(idea.unknowns) && idea.unknowns.length
      ? idea.unknowns.map((title, index) => ({title, field: `unknowns[${index}]`}))
      : text(idea.hypothesis) ? [{title: idea.hypothesis, field: 'hypothesis'}] : [];
    assumptions.forEach((assumption, index) => {
      const id = stableGraphId('assumption', `${idea.idea_id || ideaRow.idea_id}:${index + 1}`);
      addNode({
        id,
        kind: 'assumption',
        title: text(assumption.title),
        subtitle: '来自 Idea 字段',
        status: '待验证',
        provenance: {object_id: text(idea.idea_id || ideaRow.idea_id), field: assumption.field},
      });
      addEdge(ideaId, id, 'qualifies', {object_id: text(idea.idea_id || ideaRow.idea_id), field: assumption.field});
    });

    roadmapRows
      .filter(row => (idea.topic_ids || ideaRow.topic_ids || []).includes(row.topic_id))
      .forEach(row => {
        const roadmap = roadmapObjects.get(row.topic_id) || {};
        const relevantRefs = new Set();
        (roadmap.branches || []).forEach(branch => {
          (branch.evidence_item_ids || []).forEach(ref => relevantRefs.add(text(ref)));
          (branch.evidence_timeline || []).forEach(event => relevantRefs.add(text(event.item_id || event.evidence_item_id)));
        });
        const linkedEvidence = [...relevantRefs].filter(ref => evidenceIds.has(ref) && itemMap.has(ref));
        if (!linkedEvidence.length) return;
        const roadmapId = stableGraphId('roadmap', row.topic_id);
        addNode({
          id: roadmapId,
          kind: 'roadmap',
          title: text(row.topic_name || roadmap.topic_name),
          subtitle: text(roadmap.view_mode || row.change_type),
          status: text(row.change_type),
          provenance: {object_id: text(roadmap.roadmap_id || row.topic_id), field: 'branches.evidence_item_ids'},
          href: `#roadmaps?topic=${encodeURIComponent(row.topic_id)}`,
        });
        linkedEvidence.forEach(ref => addEdge(evidenceIds.get(ref), roadmapId, 'leads_to', {
          object_id: text(roadmap.roadmap_id || row.topic_id), field: 'branches.evidence_item_ids', item_id: ref,
        }));
        if (params.depth === '2') {
          [...relevantRefs].filter(ref => !evidenceIds.has(ref)).forEach(ref => {
            const item = itemMap.get(ref);
            if (!item) {
              unresolved.push({reason: 'missing_roadmap_evidence', sourceRef: ref, targetRef: roadmapId});
              return;
            }
            const evidenceId = stableGraphId('evidence', ref);
            const sourceId = stableGraphId('source', ref || canonicalIdentity(item));
            evidenceIds.set(ref, evidenceId);
            addNode({
              id: evidenceId,
              kind: 'evidence',
              title: '证据记录',
              subtitle: text(item.issue_date) || '期次未记录',
              status: '已发布',
              provenance: {object_id: text(roadmap.roadmap_id || row.topic_id), field: 'branches.evidence_item_ids', item_id: ref},
              href: item.issue_date ? `#archive?date=${encodeURIComponent(item.issue_date)}` : '',
            });
            addNode({
              id: sourceId,
              kind: 'source',
              title: text(item.title) || '归档条目',
              subtitle: [text(item.topic_name), text(item.issue_date)].filter(Boolean).join(' · '),
              status: '已发布',
              provenance: {object_id: ref, field: item.url ? 'url' : 'archive'},
              href: text(item.url),
              issueDate: text(item.issue_date),
            });
            addEdge(sourceId, evidenceId, 'declares', {object_id: ref, field: item.url ? 'url' : 'archive'});
            addEdge(evidenceId, roadmapId, 'leads_to', {object_id: text(roadmap.roadmap_id || row.topic_id), field: 'branches.evidence_item_ids', item_id: ref});
          });
        }
      });

    (Array.isArray(idea.decision_log) ? idea.decision_log : []).forEach((event, index) => {
      const rawId = text(event.event_id) || `${idea.idea_id || ideaRow.idea_id}:${index + 1}`;
      const id = stableGraphId('decision', rawId);
      addNode({
        id,
        kind: 'decision',
        title: text(event.decision) || 'Decision',
        subtitle: text(event.issue_date),
        status: text(event.to_status),
        description: text(event.reason),
        provenance: {object_id: rawId, field: 'decision_log'},
      });
      addEdge(ideaId, id, 'leads_to', {object_id: rawId, field: 'decision_log'});
    });

    if (params.candidates === '1') {
      (Array.isArray(input.candidateRelations) ? input.candidateRelations : []).forEach(candidate => {
        if (!candidate.rule_name || !candidate.rule_version || !candidate.provenance) {
          unresolved.push({reason: 'invalid_candidate_relation', sourceRef: candidate.source, targetRef: candidate.target});
          return;
        }
        addEdge(candidate.source, candidate.target, candidate.relation || 'pending', {
          ...candidate.provenance, rule_name: candidate.rule_name, rule_version: candidate.rule_version,
        }, 'candidate');
      });
    }

    let nodeRows = [...nodes.values()].sort((a, b) => `${a.kind}:${a.id}`.localeCompare(`${b.kind}:${b.id}`, 'zh-CN'));
    let edgeRows = edges.sort((a, b) => `${a.source}:${a.target}:${a.relation}`.localeCompare(`${b.source}:${b.target}:${b.relation}`, 'zh-CN'));
    let truncated = false;
    if (nodeRows.length > 40) {
      const directRefs = new Set(evidenceEntries.map(entry => text(entry.item_id || entry.brief_item_id || entry.evidence_item_id)));
      const priority = node => {
        if (node.id === ideaId) return 0;
        if (['assumption', 'roadmap', 'decision', 'claim'].includes(node.kind)) return 1;
        const ref = text(node.provenance?.item_id || node.provenance?.object_id);
        if (directRefs.has(ref)) return 2;
        return 3;
      };
      const keep = new Set(nodeRows.slice().sort((a, b) => {
        const priorityDelta = priority(a) - priority(b);
        if (priorityDelta) return priorityDelta;
        const dateDelta = text(b.issueDate || b.subtitle).localeCompare(text(a.issueDate || a.subtitle));
        return dateDelta || a.id.localeCompare(b.id);
      }).slice(0, 40).map(node => node.id));
      nodeRows = nodeRows.filter(node => keep.has(node.id));
      edgeRows = edgeRows.filter(edge => keep.has(edge.source) && keep.has(edge.target));
      truncated = true;
    }
    if (edgeRows.length > 80) {
      edgeRows = edgeRows.slice(0, 80);
      truncated = true;
    }
    const requestedFocus = text(params.node);
    const renderedIds = new Set(nodeRows.map(node => node.id));
    const focusId = renderedIds.has(requestedFocus) ? requestedFocus : ideaId;
    const confirmedRelations = edgeRows.filter(edge => edge.confirmation === 'confirmed' && edge.target === focusId).map(edge => edge.relation);
    return {
      nodes: nodeRows,
      edges: edgeRows,
      focusId,
      requestedFocusMissing: Boolean(requestedFocus && !renderedIds.has(requestedFocus)),
      unresolved: unresolved.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
      limits: {depth: Number(params.depth || 1), nodeCount: nodeRows.length, edgeCount: edgeRows.length, truncated},
      conflict: confirmedRelations.includes('supports') && confirmedRelations.includes('challenges'),
      candidatesAvailable: Array.isArray(input.candidateRelations) && input.candidateRelations.some(row => row.rule_name && row.rule_version && row.provenance),
      candidatesEnabled: params.candidates === '1',
    };
  }

  function buildArchiveAtlasModel(input = {}) {
    const params = normalizeEvidenceParams({...input.params, view: 'atlas'});
    const allIssues = [...(Array.isArray(input.issues) ? input.issues : [])].sort((a, b) => text(a.date).localeCompare(text(b.date)));
    const latest = allIssues.at(-1);
    const issueFilter = text(params.issue);
    const issues = issueFilter
      ? allIssues.filter(issue => text(issue.date) === issueFilter)
      : params.scope === 'latest' ? (latest ? [latest] : []) : allIssues;
    const nodes = [];
    const edges = [];
    const topicFilter = text(params.topic);
    issues.forEach(issue => {
      const issueId = stableGraphId('issue', issue.date);
      nodes.push({id: issueId, kind: 'issue', title: text(issue.date), subtitle: `${(issue.papers || []).length} 条内容`, status: '', provenance: {object_id: text(issue.date), field: 'archive.index'}, href: `#archive?date=${encodeURIComponent(issue.date)}`, unresolved: false});
      const groups = new Map();
      (issue.papers || []).forEach(item => {
        const key = params.mode === 'keyword' ? text(item.keywords?.[0]) || '未分类' : text(item.topic_name) || '未分类';
        const topicId = params.mode === 'topic' ? text(item.topic_id) || norm(key) : norm(key);
        if (topicFilter && topicId !== topicFilter && key !== topicFilter) return;
        if (!groups.has(key)) groups.set(key, {id: topicId, items: []});
        groups.get(key).items.push(item);
      });
      [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, 'zh-CN')).forEach(([label, group]) => {
        const topicId = stableGraphId('topic', `${issue.date}:${group.id || label}`);
        nodes.push({id: topicId, kind: 'topic', title: label, subtitle: `${group.items.length} 条聚合`, status: '', provenance: {object_id: text(issue.date), field: params.mode === 'topic' ? 'topic_name' : 'keywords'}, href: '', unresolved: false, issueDate: text(issue.date)});
        edges.push({id: stableGraphId('edge', `${issueId}:contains:${topicId}`), source: issueId, target: topicId, relation: 'contains', confirmation: 'confirmed', provenance: {object_id: text(issue.date), field: 'papers'}});
        const sortedItems = group.items
          .slice()
          .sort((a, b) => `${text(a.title)}:${itemId(a)}`.localeCompare(`${text(b.title)}:${itemId(b)}`, 'zh-CN'));
        sortedItems.slice(0, 4).forEach(item => {
            const archiveId = stableGraphId('archive_entry', `${issue.date}:${itemId(item) || canonicalIdentity(item)}`);
            nodes.push({id: archiveId, kind: 'archive_entry', title: text(item.title) || '未命名条目', subtitle: text(item.role || item.direction_name), status: text(item.role), provenance: {object_id: itemId(item), field: 'archive.papers'}, href: text(item.url), unresolved: false, issueDate: text(issue.date), topicId});
            edges.push({id: stableGraphId('edge', `${topicId}:contains:${archiveId}`), source: topicId, target: archiveId, relation: 'contains', confirmation: 'confirmed', provenance: {object_id: itemId(item), field: 'topic_name'}});
          });
        if (sortedItems.length > 4) {
          const aggregateId = stableGraphId('aggregate', `${issue.date}:${group.id || label}`);
          nodes.push({id: aggregateId, kind: 'aggregate', title: `+ ${sortedItems.length - 4} 条摘要`, subtitle: `共 ${sortedItems.length} 条`, status: '', provenance: {object_id: text(issue.date), field: 'archive.papers'}, href: '', unresolved: false, issueDate: text(issue.date), topicId, count: sortedItems.length - 4});
          edges.push({id: stableGraphId('edge', `${topicId}:contains:${aggregateId}`), source: topicId, target: aggregateId, relation: 'contains', confirmation: 'confirmed', provenance: {object_id: text(issue.date), field: 'topic_name'}});
        }
      });
    });
    nodes.sort((a, b) => `${a.issueDate || a.title}:${a.kind}:${a.title}:${a.id}`.localeCompare(`${b.issueDate || b.title}:${b.kind}:${b.title}:${b.id}`, 'zh-CN'));
    edges.sort((a, b) => `${a.source}:${a.target}`.localeCompare(`${b.source}:${b.target}`));
    const focusId = nodes.some(node => node.id === params.node) ? params.node : nodes.find(node => node.kind === 'archive_entry')?.id || nodes[0]?.id || '';
    return {nodes, edges, focusId, unresolved: [], limits: {depth: 1, nodeCount: nodes.length, edgeCount: edges.length, truncated: false}, scope: params.scope, mode: params.mode};
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
    buildArchiveAtlasModel,
    buildEvidenceGraphModel,
    knowledgePath,
    mergeRadarWithoutDuplicates,
    mergeReaderItem,
    norm,
    originalEmailPath,
    parseRoute,
    normalizeEvidenceParams,
    radarFromIssue,
    readerHeadline,
    readerSummary,
    stableGraphId,
    validateKnowledgeIndex,
  };
});
