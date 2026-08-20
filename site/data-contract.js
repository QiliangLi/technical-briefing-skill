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
    const aliases = {roadmap: 'roadmaps', 'idea-bank': 'ideas', graph: 'atlas', dashboard: 'home'};
    const requested = aliases[rawName] || rawName || 'home';
    const allowed = new Set(['home', 'roadmaps', 'ideas', 'archive', 'atlas']);
    return {name: allowed.has(requested) ? requested : 'home', params: Object.fromEntries(new URLSearchParams(query))};
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
    knowledgePath,
    mergeRadarWithoutDuplicates,
    mergeReaderItem,
    norm,
    originalEmailPath,
    parseRoute,
    radarFromIssue,
    readerHeadline,
    readerSummary,
    validateKnowledgeIndex,
  };
});
