/* Deterministic local layout for the filtered knowledge-graph display model.
 *
 * knowledge/graph.json positions are whole-graph coordinates; after a Topic/
 * range filter they leave thousands of units of empty rows between visible
 * nodes, so edges cross huge voids. This module regenerates coordinates for
 * the CURRENT model only, per lens:
 *
 *   buildKnowledgeGraphModel()  → visible nodes/edges (data-contract.js)
 *   → KnowledgeLayout.build()   → lens coordinates + initial viewport (here)
 *   → GraphRenderer             → mount, select, zoom, draw
 *
 * The layout reads only node kind, relation, issue_date, and stable IDs from
 * the model. It never adds, drops, or rewrites nodes or edges, and identical
 * input always produces identical coordinates. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.KnowledgeLayout = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const LENSES = ['structure', 'evolution', 'judgements'];

  function text(value) { return value == null ? '' : String(value).trim(); }

  function byId(a, b) { return text(a).localeCompare(text(b)); }

  function nodeMap(model) {
    const map = new Map();
    (model.nodes || []).forEach((node) => map.set(node.data.id, node));
    return map;
  }

  /* ---------------------------------------------------------------- *
   * Lens-specific object counts and empty-state detection
   * ---------------------------------------------------------------- */

  function lensSpecificCounts(model) {
    const counts = { topics: 0, directions: 0, items: 0, issues: 0, judgements: 0, supportEdges: 0, overlays: 0 };
    (model.nodes || []).forEach((node) => {
      const kind = node.data.kind;
      if (kind === 'topic') counts.topics += 1;
      else if (kind === 'direction') counts.directions += 1;
      else if (kind === 'item') counts.items += 1;
      else if (kind === 'issue') counts.issues += 1;
      else if (kind === 'judgement') counts.judgements += 1;
      else counts.overlays += 1;
    });
    (model.edges || []).forEach((edge) => {
      if (edge.data.relation === 'supports_judgement') counts.supportEdges += 1;
    });
    return counts;
  }

  /* The object a lens exists to show. When it is zero, the page must show an
   * explicit empty state instead of the shared Topic/Direction skeleton. */
  function lensEmptyState(lens, counts, params) {
    const range = text(params && params.range) || 'recent3';
    const scope = range === 'all' ? '全部期次' : range === 'latest' ? '最近一期' : '最近三期';
    if (lens === 'structure' && counts.directions === 0) {
      return { empty: true, reason: '当前范围内没有 Direction 节点。', scope };
    }
    if (lens === 'evolution' && counts.items === 0) {
      return {
        empty: true,
        reason: `${scope}没有进入长期知识的日报条目，演化透镜没有可展示的时间片。`,
        scope,
      };
    }
    if (lens === 'judgements' && counts.judgements === 0) {
      return {
        empty: true,
        reason: `${scope}没有带显式证据引用的编辑判断。`,
        scope,
      };
    }
    return { empty: false, scope };
  }

  /* ---------------------------------------------------------------- *
   * Per-lens layouts
   * ---------------------------------------------------------------- */

  function layoutStructure(model, positions) {
    const topics = [];
    const directions = [];
    const overlays = { roadmap: [], roadmap_branch: [], idea: [], other: [] };
    (model.nodes || []).forEach((node) => {
      const kind = node.data.kind;
      if (kind === 'topic') topics.push(node);
      else if (kind === 'direction') directions.push(node);
      else if (kind in overlays) overlays[kind].push(node);
      else overlays.other.push(node);
    });
    topics.sort((a, b) => byId(a.data.id, b.data.id));
    directions.sort((a, b) => byId(a.data.id, b.data.id));

    let y = 0;
    topics.forEach((node) => {
      positions[node.data.id] = { x: 0, y };
      y += 170;
    });
    const contextEnd = Math.max(y, 170);
    directions.forEach((node, index) => {
      positions[node.data.id] = { x: 360, y: index * 150 };
    });
    const directionEnd = directions.length * 150;
    let overlayY = 0;
    ['roadmap', 'roadmap_branch', 'idea', 'other'].forEach((bucket) => {
      overlays[bucket]
        .sort((a, b) => byId(a.data.id, b.data.id))
        .forEach((node) => {
          positions[node.data.id] = { x: bucket === 'roadmap' ? 720 : 760, y: overlayY };
          overlayY += 150;
        });
    });
    const height = Math.max(contextEnd, directionEnd, overlayY, 200);
    return { width: 920, height };
  }

  /* Evolution: Issue columns as time, Direction lanes as rows. Items sit in
   * their Direction × Issue cell; dense cells wrap into sub-columns so one
   * busy cell cannot stretch a lane thousands of units tall. Issue anchors
   * sit at the vertical center of their column so published_in edges stay
   * short verticals inside the column. */
  function layoutEvolution(model, positions) {
    const CELL = 92;
    const CELL_ROWS = 6;
    const SUB_COLUMN = 190;

    const lanes = [];
    const laneByDirection = new Map();
    (model.nodes || []).forEach((node) => {
      if (node.data.kind === 'direction') lanes.push(node);
    });
    lanes.sort((a, b) => byId(a.data.id, b.data.id));
    lanes.forEach((node, index) => laneByDirection.set(node.data.id, index));

    const topics = (model.nodes || []).filter((node) => node.data.kind === 'topic')
      .sort((a, b) => byId(a.data.id, b.data.id));
    const issues = (model.nodes || []).filter((node) => node.data.kind === 'issue')
      .sort((a, b) => byId(text(a.data.issue_date) || a.data.id, text(b.data.issue_date) || b.data.id));
    const items = (model.nodes || []).filter((node) => node.data.kind === 'item')
      .sort((a, b) => byId(a.data.id, b.data.id));

    // Which lane does each item belong to? Follow the explicit has_item edge
    // direction → item; items without a visible direction go to a trailing lane.
    const laneOfItem = new Map();
    (model.edges || []).forEach((edge) => {
      if (edge.data.relation === 'has_item' && laneByDirection.has(edge.data.source)) {
        laneOfItem.set(edge.data.target, laneByDirection.get(edge.data.source));
      }
    });
    const fallbackLane = lanes.length;
    items.forEach((item) => {
      if (!laneOfItem.has(item.data.id)) laneOfItem.set(item.data.id, fallbackLane);
    });
    const totalLanes = lanes.length + (items.some((item) => laneOfItem.get(item.data.id) === fallbackLane) ? 1 : 0);

    const issueOf = new Map();
    issues.forEach((node, index) => issueOf.set(node.data.id, index));
    const columnOfItem = new Map();
    const stackByLane = new Map();
    const stackByColumn = new Map();
    items.forEach((item) => {
      const lane = laneOfItem.get(item.data.id);
      const col = issueOf.get(issueOfItem(model, item.data.id)) ?? -1;
      columnOfItem.set(item.data.id, col);
      if (!stackByLane.has(lane)) stackByLane.set(lane, new Map());
      const stacks = stackByLane.get(lane);
      stacks.set(col, (stacks.get(col) || 0) + 1);
      stackByColumn.set(col, Math.max(stackByColumn.get(col) || 0, stacks.get(col)));
    });

    // Lane heights wrap dense cells at CELL_ROWS rows; column widths grow with
    // their densest cell's sub-column count.
    const laneTop = new Map();
    let y = 0;
    for (let lane = 0; lane < totalLanes; lane += 1) {
      let maxStack = 1;
      const stacks = stackByLane.get(lane);
      if (stacks) stacks.forEach((count) => { maxStack = Math.max(maxStack, count); });
      laneTop.set(lane, y);
      y += Math.min(maxStack, CELL_ROWS) * CELL + 74;
    }
    const lanesHeight = Math.max(y, 220);

    const columnX = new Map();
    let x = 640;
    for (let col = 0; col < issues.length; col += 1) {
      columnX.set(col, x);
      const subs = Math.ceil((stackByColumn.get(col) || 1) / CELL_ROWS);
      x += subs * SUB_COLUMN + 130;
    }
    const gridWidth = issues.length ? columnX.get(issues.length - 1) + (Math.ceil((stackByColumn.get(issues.length - 1) || 1) / CELL_ROWS)) * SUB_COLUMN + 200 : 640;

    topics.forEach((node, index) => {
      positions[node.data.id] = { x: 0, y: index * 150 };
    });
    lanes.forEach((node) => {
      positions[node.data.id] = { x: 300, y: laneTop.get(laneByDirection.get(node.data.id)) + 30 };
    });

    // Items: column by issue, lane row; stacked deterministically by item id.
    const stackCursor = new Map();
    const itemY = new Map();
    items.forEach((item) => {
      const lane = laneOfItem.get(item.data.id);
      const col = columnOfItem.get(item.data.id) ?? -1;
      const key = `${lane}:${col}`;
      const used = stackCursor.get(key) || 0;
      stackCursor.set(key, used + 1);
      const sub = Math.floor(used / CELL_ROWS);
      const row = used % CELL_ROWS;
      const itemPosition = {
        x: (col >= 0 ? columnX.get(col) : 640) + sub * SUB_COLUMN,
        y: laneTop.get(lane) + 30 + row * CELL,
      };
      positions[item.data.id] = itemPosition;
      itemY.set(item.data.id, itemPosition.y);
    });

    // Issue anchors at the vertical center of their column's items.
    issues.forEach((node, index) => {
      const ys = items
        .filter((item) => columnOfItem.get(item.data.id) === index)
        .map((item) => itemY.get(item.data.id));
      const center = ys.length ? (Math.min(...ys) + Math.max(...ys)) / 2 : lanesHeight / 2;
      positions[node.data.id] = { x: columnX.get(index), y: center };
    });

    // Overlay kinds, if enabled, form a trailing context column. Only nodes
    // without a lane position land here.
    let overlayY = 0;
    (model.nodes || [])
      .filter((node) => !positions[node.data.id])
      .sort((a, b) => byId(a.data.id, b.data.id))
      .forEach((node) => {
        positions[node.data.id] = { x: 0, y: lanesHeight + 120 + overlayY };
        overlayY += 130;
      });

    return { width: Math.max(gridWidth, 640), height: lanesHeight + (overlayY ? overlayY + 120 : 0) };
  }


  function issueOfItem(model, itemId) {
    // published_in edge item → issue; fall back to the item's own issue_date.
    for (const edge of model.edges || []) {
      if (edge.data.relation === 'published_in' && edge.data.source === itemId) return edge.data.target;
    }
    const node = nodeMap(model).get(itemId);
    return node && node.data.issue_date ? `issue:${node.data.issue_date}` : '';
  }

  /* Judgements: judgement-centered evidence clusters. Evidence items sit in a
   * column left of their judgement; clusters are packed into columns so tall
   * ranges grow sideways instead of leaving one 15k-unit vertical spread.
   * Topic/Direction remain as a weakened context column. */
  function layoutJudgements(model, positions) {
    const judgements = (model.nodes || []).filter((node) => node.data.kind === 'judgement')
      .sort((a, b) => byId(a.data.id, b.data.id));
    const items = (model.nodes || []).filter((node) => node.data.kind === 'item')
      .sort((a, b) => byId(a.data.id, b.data.id));

    const itemsOfJudgement = new Map();
    (model.edges || []).forEach((edge) => {
      if (edge.data.relation === 'supports_judgement') {
        if (!itemsOfJudgement.has(edge.data.target)) itemsOfJudgement.set(edge.data.target, []);
        itemsOfJudgement.get(edge.data.target).push(edge.data.source);
      }
    });

    // Assign each item to the first (sorted) judgement citing it; later
    // judgements reusing the item get a bounded cross-cluster edge.
    const clusterOfItem = new Map();
    const clusters = judgements.map((judgement) => ({
      judgement,
      items: (itemsOfJudgement.get(judgement.data.id) || []).filter((itemId) => {
        if (clusterOfItem.has(itemId)) return false;
        clusterOfItem.set(itemId, judgement.data.id);
        return true;
      }).sort(byId),
    }));

    const ROW = 92;
    const PAD = 84;
    const COLUMN_MAX_HEIGHT = 3200;
    const COLUMN_WIDTH = 1140;
    const ITEM_COLUMN = 360;
    const JUDGEMENT_COLUMN = 780;

    // Greedy column packing: deterministic, keeps each column's height bounded
    // so context anchors never sit thousands of units away from their content.
    let packY = 0;
    let packCol = 0;
    clusters.forEach((cluster) => {
      const height = Math.max(1, cluster.items.length) * ROW + PAD;
      if (packY > 0 && packY + height > COLUMN_MAX_HEIGHT) {
        packCol += 1;
        packY = 0;
      }
      cluster.col = packCol;
      cluster.y = packY;
      packY += height;
    });
    const columns = packCol + 1;
    const columnHeight = Math.max(packY, 200);
    const columnX = (col) => col * COLUMN_WIDTH;

    const directionY = new Map();
    const itemDirections = new Map();
    (model.edges || []).forEach((edge) => {
      if (edge.data.relation === 'has_item' && !itemDirections.has(edge.data.target)) {
        itemDirections.set(edge.data.target, edge.data.source);
      }
    });
    clusters.forEach((cluster) => {
      const offsetX = columnX(cluster.col);
      const rows = Math.max(1, cluster.items.length);
      cluster.items.forEach((itemId, index) => {
        const itemY = cluster.y + index * ROW;
        positions[itemId] = { x: offsetX + ITEM_COLUMN, y: itemY };
        const directionId = itemDirections.get(itemId);
        if (directionId) {
          if (!directionY.has(directionId)) directionY.set(directionId, []);
          directionY.get(directionId).push(itemY);
        }
      });
      const centerY = cluster.y + ((rows - 1) * ROW) / 2;
      positions[cluster.judgement.data.id] = { x: offsetX + JUDGEMENT_COLUMN, y: centerY };
    });

    // Context column: topics first, then directions beside the median y of
    // their own evidence items so has_item/has_direction edges stay local.
    const topics = (model.nodes || []).filter((node) => node.data.kind === 'topic')
      .sort((a, b) => byId(a.data.id, b.data.id));
    let contextY = 0;
    topics.forEach((node) => {
      positions[node.data.id] = { x: -320, y: contextY };
      contextY += 150;
    });
    const anchored = new Set();
    const directions = (model.nodes || []).filter((node) => node.data.kind === 'direction')
      .sort((a, b) => byId(a.data.id, b.data.id));
    // Anchor each direction beside the median y of its own evidence items,
    // inside the column those items live in, so has_item edges stay short.
    const itemsByDirection = new Map();
    clusters.forEach((cluster) => {
      cluster.items.forEach((itemId) => {
        const directionId = itemDirections.get(itemId);
        if (!directionId) return;
        if (!itemsByDirection.has(directionId)) itemsByDirection.set(directionId, []);
        itemsByDirection.get(directionId).push({ y: positions[itemId].y, col: cluster.col });
      });
    });
    directions.forEach((node) => {
      const rows = itemsByDirection.get(node.data.id);
      if (rows && rows.length) {
        const sorted = rows.slice().sort((a, b) => a.y - b.y);
        const mid = Math.floor((sorted.length - 1) / 2);
        const medianY = sorted.length % 2
          ? sorted[mid].y
          : (sorted[mid].y + sorted[mid + 1].y) / 2;
        const median = sorted.length % 2 ? sorted[mid] : { y: medianY, col: sorted[mid].col };
        positions[node.data.id] = { x: columnX(median.col) + 60, y: median.y };
        anchored.add(node.data.id);
      }
    });
    directions.forEach((node) => {
      if (!anchored.has(node.data.id)) {
        positions[node.data.id] = { x: -160, y: contextY };
        contextY += 130;
      }
    });
    if (topics.length && anchored.size) {
      const dirYs = directions.filter((node) => anchored.has(node.data.id)).map((node) => positions[node.data.id].y);
      const meanY = Math.round(dirYs.reduce((sum, value) => sum + value, 0) / dirYs.length);
      positions[topics[0].data.id] = { x: -320, y: meanY };
    }
    let extraY = columnHeight + 80;
    // Skeleton items that no judgement cites form a compact context grid
    // instead of a single long column.
    let gridIndex = 0;
    (model.nodes || [])
      .filter((node) => !positions[node.data.id] && node.data.kind === 'item')
      .sort((a, b) => byId(a.data.id, b.data.id))
      .forEach((node) => {
        positions[node.data.id] = {
          x: 60 + (gridIndex % 6) * 210,
          y: extraY + Math.floor(gridIndex / 6) * 130,
        };
        gridIndex += 1;
      });
    extraY += Math.ceil(gridIndex / 6) * 130 + 40;
    (model.nodes || [])
      .filter((node) => !positions[node.data.id])
      .sort((a, b) => byId(a.data.id, b.data.id))
      .forEach((node) => {
        positions[node.data.id] = { x: 0, y: extraY };
        extraY += 130;
      });

    return { width: columnX(columns - 1) + JUDGEMENT_COLUMN + 200, height: Math.max(columnHeight, extraY, 220) };
  }

  /* ---------------------------------------------------------------- *
   * Viewport: lens-specific default focus and first-screen set
   * ---------------------------------------------------------------- */

  function oneHopIds(model, nodeId) {
    const ids = new Set([nodeId]);
    (model.edges || []).forEach((edge) => {
      if (edge.data.source === nodeId) ids.add(edge.data.target);
      if (edge.data.target === nodeId) ids.add(edge.data.source);
    });
    return [...ids];
  }

  function latestItemIssue(model, nodeId) {
    let latest = '';
    (model.edges || []).forEach((edge) => {
      if (edge.data.relation === 'has_item' && edge.data.source === nodeId) {
        const node = nodeMap(model).get(edge.data.target);
        const date = text(node && node.data.issue_date);
        if (date > latest) latest = date;
      }
    });
    return latest;
  }

  /* Explicit node wins; otherwise each lens picks its own focus and first
   * screen so switching lenses visibly changes the canvas. */
  function buildViewport(model, lens, positions, params) {
    const requested = text(params && params.node);
    const known = nodeMap(model);
    if (requested && known.has(requested)) {      return { focusId: requested, fitIds: oneHopIds(model, requested), highlightIds: null, automatic: false };
    }
    if (lens === 'structure') {
      const topic = (model.nodes || []).find((node) => node.data.kind === 'topic');
      const focusId = topic ? topic.data.id : (model.nodes || [])[0]?.data.id || '';
      return { focusId, fitIds: (model.nodes || []).map((node) => node.data.id), highlightIds: null, automatic: Boolean(focusId) };
    }
    if (lens === 'evolution') {
      const directions = (model.nodes || []).filter((node) => node.data.kind === 'direction');
      if (!directions.length) return null;
      const requestedDirection = text(params && params.direction);
      let lane = directions.find((node) => node.data.id === `direction:${requestedDirection}`)
        || directions.find((node) => nodeShortDirection(node.data.id) === requestedDirection);
      if (!lane) {
        lane = directions.slice().sort((a, b) => byId(latestItemIssue(model, b.data.id), latestItemIssue(model, a.data.id)) || byId(a.data.id, b.data.id))[0];
      }
      const itemsInLane = (model.edges || [])
        .filter((edge) => edge.data.relation === 'has_item' && edge.data.source === lane.data.id)
        .map((edge) => edge.data.target);
      const issueIds = new Set();
      itemsInLane.forEach((itemId) => {
        (model.edges || []).forEach((edge) => {
          if (edge.data.relation === 'published_in' && edge.data.source === itemId) issueIds.add(edge.data.target);
        });
      });
      if (!issueIds.size) {
        const latest = (model.nodes || []).filter((node) => node.data.kind === 'issue')
          .sort((a, b) => byId(text(b.data.issue_date) || b.data.id, text(a.data.issue_date) || a.data.id))[0];
        if (latest) issueIds.add(latest.data.id);
      }
      const fitIds = [lane.data.id, ...itemsInLane, ...issueIds];
      return { focusId: lane.data.id, fitIds, highlightIds: fitIds, automatic: true };
    }
    if (lens === 'judgements') {
      const judgements = (model.nodes || []).filter((node) => node.data.kind === 'judgement')
        .sort((a, b) => byId(text(b.data.issue_date) || b.data.id, text(a.data.issue_date) || a.data.id) || byId(a.data.id, b.data.id));
      if (!judgements.length) return null;
      const focus = judgements[0];
      const evidenceIds = (model.edges || [])
        .filter((edge) => edge.data.relation === 'supports_judgement' && edge.data.target === focus.data.id)
        .map((edge) => edge.data.source);
      const fitIds = [focus.data.id, ...evidenceIds];
      return { focusId: focus.data.id, fitIds, highlightIds: fitIds, automatic: true };
    }
    return null;
  }

  function nodeShortDirection(id) {
    return String(id || '').replace(/^direction:/, '');
  }

  /* ---------------------------------------------------------------- *
   * Edge statistics used by tests and the truncation-free guarantee
   * ---------------------------------------------------------------- */

  function edgeStats(model, positions) {
    const stats = new Map();
    (model.edges || []).forEach((edge) => {
      const from = positions[edge.data.source];
      const to = positions[edge.data.target];
      if (!from || !to) return;
      const relation = edge.data.relation;
      const length = Math.round(Math.hypot(to.x - from.x, to.y - from.y));
      if (!stats.has(relation)) stats.set(relation, []);
      stats.get(relation).push(length);
    });
    const result = {};
    stats.forEach((lengths, relation) => {
      const sorted = lengths.slice().sort((a, b) => a - b);
      const median = sorted[Math.floor((sorted.length - 1) / 2)];
      result[relation] = {
        count: sorted.length,
        min: sorted[0],
        median,
        p95: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))],
        max: sorted[sorted.length - 1],
      };
    });
    return result;
  }

  /* Entry point: coordinates + initial viewport for the current model. */
  function build(model, options = {}) {
    const lens = LENSES.indexOf(options.lens) >= 0 ? options.lens : 'structure';
    const positions = {};
    if (!model || !Array.isArray(model.nodes) || !model.nodes.length) {
      return { available: false, positions, viewport: null, summary: null, empty: { empty: true, reason: '当前筛选下没有可绘制节点。' } };
    }
    let bounds;
    if (lens === 'evolution') bounds = layoutEvolution(model, positions);
    else if (lens === 'judgements') bounds = layoutJudgements(model, positions);
    else bounds = layoutStructure(model, positions);

    const counts = lensSpecificCounts(model);
    const empty = lensEmptyState(lens, counts, options.params);
    const viewport = empty.empty ? null : buildViewport(model, lens, positions, options.params);
    return {
      available: true,
      lens,
      positions,
      viewport,
      empty: empty.empty ? empty : null,
      counts,
      bounds,
      stats: edgeStats(model, positions),
    };
  }

  return {
    LENSES,
    build,
    lensSpecificCounts,
    lensEmptyState,
    edgeStats,
  };
});
