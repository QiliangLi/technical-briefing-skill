/* Deterministic DOM/SVG renderer for the read-only Evidence Graph and Archive Atlas. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.EvidenceGraph = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const KIND_GEOMETRY = {
    source: [154, 58], evidence: [118, 58], claim: [142, 72], idea: [146, 72],
    assumption: [146, 84], roadmap: [146, 62], decision: [112, 72], unknown: [124, 58],
    issue: [96, 58], topic: [180, 58], archive_entry: [178, 34], aggregate: [178, 34],
  };
  const KIND_LABELS = {
    source: '来源文档', evidence: '证据记录', claim: 'Claim', idea: 'Idea', assumption: 'Assumption',
    roadmap: 'Roadmap', decision: 'Decision', unknown: '未知', issue: '日报期次', topic: 'Topic',
    archive_entry: '归档条目', aggregate: '聚合条目',
  };
  const ICONS = {
    source: 'evidence', evidence: 'trend', claim: 'claim', idea: 'idea', assumption: 'question',
    roadmap: 'roadmap', decision: 'check', unknown: 'alert', issue: 'calendar', topic: 'tag',
    archive_entry: 'evidence', aggregate: 'archive',
  };
  const RELATION_LABELS = {
    declares: '声明', supports: '支持', challenges: '挑战', qualifies: '限定',
    leads_to: '导向', pending: '待确认', contains: '归档结构',
  };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  }

  function graphIcon(name) {
    return `<svg aria-hidden="true"><use href="./assets/icons.svg#${esc(name)}"></use></svg>`;
  }

  function graphNodeSize(kind) {
    const [width, height] = KIND_GEOMETRY[kind] || KIND_GEOMETRY.unknown;
    return {width, height};
  }

  function layoutEvidenceGraphModel(model = {}) {
    const nodes = (model.nodes || []).slice();
    const byKind = new Map();
    nodes.forEach(node => {
      if (!byKind.has(node.kind)) byKind.set(node.kind, []);
      byKind.get(node.kind).push(node);
    });
    byKind.forEach(rows => rows.sort((a, b) => `${a.title}:${a.id}`.localeCompare(`${b.title}:${b.id}`, 'zh-CN')));
    const columns = {
      source: 20, evidence: 205, claim: 355, idea: 515, assumption: 515,
      roadmap: 690, decision: 850, unknown: 850,
    };
    const placed = [];
    const centerY = 294;
    const placeRows = (kind, center = centerY) => {
      const rows = byKind.get(kind) || [];
      if (!rows.length) return [];
      const heights = rows.map(row => graphNodeSize(row.kind).height);
      const total = heights.reduce((sum, value) => sum + value, 0) + Math.max(0, rows.length - 1) * 18;
      let y = Math.max(30, center - total / 2);
      const result = [];
      rows.forEach(node => {
        const size = graphNodeSize(node.kind);
        const positioned = {...node, x: columns[node.kind] || columns.unknown, y, width: size.width, height: size.height};
        placed.push(positioned);
        result.push(positioned);
        y += size.height + 18;
      });
      return result;
    };

    // Keep the evidence corridor clear. Claim is an explicit placeholder rather
    // than a connected node, while Roadmap and Decision occupy separate bands.
    placeRows('source');
    placeRows('evidence');
    placeRows('claim', centerY + 235);
    const ideas = placeRows('idea');
    const ideaTop = ideas[0]?.y ?? centerY;
    const assumptionRows = byKind.get('assumption') || [];
    if (assumptionRows.length) {
      const total = assumptionRows.reduce((sum, node) => sum + graphNodeSize(node.kind).height, 0) + (assumptionRows.length - 1) * 18;
      let y = Math.max(30, ideaTop - total - 18);
      assumptionRows.forEach(node => {
        const size = graphNodeSize(node.kind);
        placed.push({...node, x: columns.assumption, y, width: size.width, height: size.height});
        y += size.height + 18;
      });
    }
    placeRows('roadmap', centerY + 215);
    placeRows('decision', centerY + 145);
    placeRows('unknown', centerY + 235);
    const width = Math.max(1000, ...placed.map(node => node.x + node.width + 24));
    const height = Math.max(590, ...placed.map(node => node.y + node.height + 42));
    return {nodes: placed, edges: (model.edges || []).slice(), width, height};
  }

  function layoutArchiveAtlasModel(model = {}) {
    const nodeById = new Map((model.nodes || []).map(node => [node.id, node]));
    const children = new Map();
    (model.edges || []).forEach(edge => {
      if (!children.has(edge.source)) children.set(edge.source, []);
      children.get(edge.source).push(edge.target);
    });
    children.forEach(ids => ids.sort((a, b) => `${nodeById.get(a)?.title}:${a}`.localeCompare(`${nodeById.get(b)?.title}:${b}`, 'zh-CN')));
    const issues = (model.nodes || []).filter(node => node.kind === 'issue').sort((a, b) => `${a.title}:${a.id}`.localeCompare(`${b.title}:${b.id}`));
    const placed = [];
    let cursorY = 60;
    issues.forEach(issue => {
      const topics = (children.get(issue.id) || []).map(id => nodeById.get(id)).filter(node => node?.kind === 'topic');
      const topicRows = topics.map(topic => ({topic, entries: (children.get(topic.id) || []).map(id => nodeById.get(id)).filter(Boolean)}));
      const blockHeight = Math.max(174, topicRows.reduce((sum, row) => sum + Math.max(76, row.entries.length * 40 + 10), 0));
      placed.push({...issue, x: 26, y: cursorY + blockHeight / 2 - 29, ...graphNodeSize('issue')});
      let topicY = cursorY;
      topicRows.forEach(row => {
        const rowHeight = Math.max(76, row.entries.length * 40 + 10);
        placed.push({...row.topic, x: 252, y: topicY + rowHeight / 2 - 29, ...graphNodeSize('topic')});
        row.entries.forEach((entry, index) => placed.push({...entry, x: 586, y: topicY + 5 + index * 40, ...graphNodeSize(entry.kind)}));
        topicY += rowHeight;
      });
      cursorY += blockHeight + 18;
    });
    return {nodes: placed, edges: (model.edges || []).slice(), width: 1020, height: Math.max(720, cursorY + 24)};
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function cubicPoint(a, b, c, d, t = .5) {
    const mt = 1 - t;
    return mt ** 3 * a + 3 * mt ** 2 * t * b + 3 * mt * t ** 2 * c + t ** 3 * d;
  }

  function routeEvidenceEdge(source, target, requestedOffset = 0) {
    const sourceCenter = {x: source.x + source.width / 2, y: source.y + source.height / 2};
    const targetCenter = {x: target.x + target.width / 2, y: target.y + target.height / 2};
    const horizontalGap = target.x >= source.x + source.width
      ? target.x - source.x - source.width
      : source.x >= target.x + target.width ? source.x - target.x - target.width : -1;
    const verticalGap = target.y >= source.y + source.height
      ? target.y - source.y - source.height
      : source.y >= target.y + target.height ? source.y - target.y - target.height : -1;
    const horizontal = horizontalGap >= 0 && (verticalGap < 0 || horizontalGap >= verticalGap * .55);

    if (horizontal) {
      const direction = targetCenter.x >= sourceCenter.x ? 1 : -1;
      const offset = clamp(requestedOffset, -Math.min(source.height, target.height) * .28, Math.min(source.height, target.height) * .28);
      const x1 = direction > 0 ? source.x + source.width : source.x;
      const x2 = direction > 0 ? target.x : target.x + target.width;
      const y1 = sourceCenter.y + offset;
      const y2 = targetCenter.y + offset;
      const bend = Math.max(8, Math.abs(x2 - x1) * .42);
      const c1x = x1 + direction * bend;
      const c2x = x2 - direction * bend;
      return {
        axis: 'horizontal',
        d: `M ${x1} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${x2} ${y2}`,
        labelX: cubicPoint(x1, c1x, c2x, x2),
        labelY: cubicPoint(y1, y1, y2, y2) - 6,
        sourceAnchor: {x: x1, y: y1},
        targetAnchor: {x: x2, y: y2},
      };
    }

    const direction = targetCenter.y >= sourceCenter.y ? 1 : -1;
    const offset = clamp(requestedOffset, -Math.min(source.width, target.width) * .28, Math.min(source.width, target.width) * .28);
    const y1 = direction > 0 ? source.y + source.height : source.y;
    const y2 = direction > 0 ? target.y : target.y + target.height;
    const x1 = sourceCenter.x + offset;
    const x2 = targetCenter.x + offset;
    const bend = Math.max(8, Math.abs(y2 - y1) * .42);
    const c1y = y1 + direction * bend;
    const c2y = y2 - direction * bend;
    return {
      axis: 'vertical',
      d: `M ${x1} ${y1} C ${x1} ${c1y}, ${x2} ${c2y}, ${x2} ${y2}`,
      labelX: cubicPoint(x1, x1, x2, x2) + 20,
      labelY: cubicPoint(y1, c1y, c2y, y2) - 3,
      sourceAnchor: {x: x1, y: y1},
      targetAnchor: {x: x2, y: y2},
    };
  }

  function renderEdges(layout, selectedEdgeId) {
    const nodes = new Map(layout.nodes.map(node => [node.id, node]));
    const incomingTotals = new Map();
    layout.edges.forEach(edge => incomingTotals.set(edge.target, (incomingTotals.get(edge.target) || 0) + 1));
    const incomingSeen = new Map();
    return layout.edges.map(edge => {
      const source = nodes.get(edge.source);
      const target = nodes.get(edge.target);
      if (!source || !target) return '';
      const seen = incomingSeen.get(edge.target) || 0;
      incomingSeen.set(edge.target, seen + 1);
      const offset = (seen - ((incomingTotals.get(edge.target) || 1) - 1) / 2) * 8;
      const route = routeEvidenceEdge(source, target, offset);
      const label = RELATION_LABELS[edge.relation] || edge.relation;
      return `<g class="graph-edge relation-${esc(edge.relation)}${edge.id === selectedEdgeId ? ' is-selected' : ''}" data-edge-id="${esc(edge.id)}">
        <path class="graph-edge-line" d="${route.d}" marker-end="url(#arrow-${esc(edge.relation)})"></path>
        <path class="graph-edge-hit" d="${route.d}"></path>
        <text x="${route.labelX}" y="${route.labelY}" text-anchor="middle"><tspan>${esc(label)}</tspan></text>
      </g>`;
    }).join('');
  }

  function markerDefs() {
    return Object.keys(RELATION_LABELS).map(relation => `<marker id="arrow-${relation}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z"></path></marker>`).join('');
  }

  function renderNode(node, model, selectedId) {
    const incoming = (model.edges || []).filter(edge => edge.target === node.id).length;
    const outgoing = (model.edges || []).filter(edge => edge.source === node.id).length;
    const external = /^https?:/i.test(node.href || '');
    const label = `${KIND_LABELS[node.kind] || node.kind}：${node.title}。状态 ${node.status || '未记录'}。入边 ${incoming}，出边 ${outgoing}`;
    return `<button type="button" class="graph-node node-${esc(node.kind)}${node.unresolved ? ' is-unresolved' : ''}${node.id === selectedId ? ' is-selected' : ''}" data-node-id="${esc(node.id)}" style="left:${node.x}px;top:${node.y}px;width:${node.width}px;height:${node.height}px" aria-label="${esc(label)}" title="${esc(node.title)}"${external ? ` data-external-href="${esc(node.href)}"` : ''}>
      <span class="graph-node-icon">${graphIcon(ICONS[node.kind] || 'question')}</span>
      <span class="graph-node-copy"><strong>${esc(node.title)}</strong><small>${esc(node.subtitle || node.status || '')}</small></span>
      ${node.id === selectedId ? '<i class="focus-corners" aria-hidden="true"></i>' : ''}
    </button>`;
  }

  function renderMiniMap(layout, selectedId) {
    const sx = 174 / layout.width;
    const sy = 104 / layout.height;
    return `<svg viewBox="0 0 186 116" aria-hidden="true">${layout.edges.map(edge => {
      const a = layout.nodes.find(node => node.id === edge.source);
      const b = layout.nodes.find(node => node.id === edge.target);
      return a && b ? `<line x1="${12 + (a.x + a.width / 2) * sx}" y1="${6 + (a.y + a.height / 2) * sy}" x2="${12 + (b.x + b.width / 2) * sx}" y2="${6 + (b.y + b.height / 2) * sy}"></line>` : '';
    }).join('')}${layout.nodes.map(node => `<rect class="mini-${esc(node.kind)}${node.id === selectedId ? ' is-selected' : ''}" x="${12 + node.x * sx}" y="${6 + node.y * sy}" width="${Math.max(3, node.width * sx)}" height="${Math.max(3, node.height * sy)}"></rect>`).join('')}</svg>`;
  }

  class EvidenceGraphRenderer {
    constructor(rootElement, model, options = {}) {
      this.root = rootElement;
      this.model = model || {nodes: [], edges: []};
      this.options = options;
      this.mode = options.mode === 'atlas' ? 'atlas' : 'graph';
      this.selectedId = this.model.focusId;
      this.selectedEdgeId = '';
      this.scale = 1;
      this.x = 0;
      this.y = 0;
      this.drag = null;
      this.layout = this.mode === 'atlas' ? layoutArchiveAtlasModel(this.model) : layoutEvidenceGraphModel(this.model);
      this.render();
      this.bind();
      requestAnimationFrame(() => this.fit());
    }

    render() {
      const mini = this.mode === 'graph' ? `<div class="graph-minimap">${renderMiniMap(this.layout, this.selectedId)}</div>` : '';
      this.root.innerHTML = `<div class="graph-transform" style="width:${this.layout.width}px;height:${this.layout.height}px">
        <svg class="graph-edges" width="${this.layout.width}" height="${this.layout.height}" aria-hidden="true"><defs>${markerDefs()}</defs>${renderEdges(this.layout, this.selectedEdgeId)}</svg>
        <div class="graph-nodes">${this.layout.nodes.map(node => renderNode(node, this.model, this.selectedId)).join('')}</div>
      </div>${mini}`;
      this.applyTransform();
    }

    bind() {
      this.root.addEventListener('click', event => {
        const node = event.target.closest('[data-node-id]');
        if (node) {
          this.selectNode(node.dataset.nodeId, true);
          return;
        }
        const edge = event.target.closest('[data-edge-id]');
        if (edge) this.selectEdge(edge.dataset.edgeId, true);
      });
      this.root.addEventListener('dblclick', event => {
        if (event.target.closest('[data-node-id]')) this.options.onExpand?.();
      });
      this.root.addEventListener('keydown', event => this.onKeydown(event));
      this.root.addEventListener('wheel', event => {
        if (!(event.ctrlKey || event.metaKey || document.activeElement === this.root)) return;
        event.preventDefault();
        this.zoom(event.deltaY < 0 ? .1 : -.1);
      }, {passive: false});
      this.root.addEventListener('pointerdown', event => {
        if (event.button !== 0 || event.target.closest('[data-node-id],[data-edge-id]')) return;
        this.drag = {id: event.pointerId, x: event.clientX, y: event.clientY, ox: this.x, oy: this.y, moved: false};
      });
      this.root.addEventListener('pointermove', event => {
        if (!this.drag || this.drag.id !== event.pointerId) return;
        if (!this.drag.moved && Math.hypot(event.clientX - this.drag.x, event.clientY - this.drag.y) <= 4) return;
        this.drag.moved = true;
        this.root.setPointerCapture(event.pointerId);
        this.x = this.drag.ox + event.clientX - this.drag.x;
        this.y = this.drag.oy + event.clientY - this.drag.y;
        this.applyTransform();
      });
      const endDrag = () => { this.drag = null; this.root.classList.remove('is-dragging'); };
      this.root.addEventListener('pointerup', endDrag);
      this.root.addEventListener('pointercancel', endDrag);
      if (typeof ResizeObserver !== 'undefined') {
        let width = this.root.clientWidth;
        this.resizeObserver = new ResizeObserver(entries => {
          const next = entries[0]?.contentRect.width || width;
          if (Math.abs(next - width) > 1) { width = next; this.fit(); }
        });
        this.resizeObserver.observe(this.root);
      }
    }

    applyTransform() {
      const stage = this.root.querySelector('.graph-transform');
      if (stage) stage.style.transform = `translate(${this.x}px, ${this.y}px) scale(${this.scale})`;
      this.options.onZoom?.(Math.round(this.scale * 100));
    }

    fit() {
      const width = this.root.clientWidth || 800;
      const height = this.root.clientHeight || 590;
      this.scale = Math.max(.5, Math.min(1.8, Math.min((width - 36) / this.layout.width, (height - 36) / this.layout.height)));
      this.x = Math.round((width - this.layout.width * this.scale) / 2);
      this.y = Math.round((height - this.layout.height * this.scale) / 2);
      this.applyTransform();
    }

    zoom(delta) {
      const previous = this.scale;
      this.scale = Math.max(.5, Math.min(1.8, Math.round((this.scale + delta) * 10) / 10));
      const cx = this.root.clientWidth / 2;
      const cy = this.root.clientHeight / 2;
      this.x = cx - (cx - this.x) * (this.scale / previous);
      this.y = cy - (cy - this.y) * (this.scale / previous);
      this.applyTransform();
    }

    reset() { this.scale = 1; this.x = 0; this.y = 0; this.applyTransform(); }

    selectNode(id, notify = false) {
      if (!this.layout.nodes.some(node => node.id === id)) return;
      this.selectedId = id;
      this.selectedEdgeId = '';
      this.render();
      if (notify) this.options.onSelectNode?.(id);
    }

    selectEdge(id, notify = false) {
      if (!this.model.edges.some(edge => edge.id === id)) return;
      this.selectedEdgeId = id;
      this.render();
      if (notify) this.options.onSelectEdge?.(id);
    }

    onKeydown(event) {
      const current = event.target.closest('[data-node-id]');
      if (!current || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      const origin = this.layout.nodes.find(node => node.id === current.dataset.nodeId);
      if (!origin) return;
      const connected = new Set(this.model.edges.flatMap(edge => edge.source === origin.id ? [edge.target] : edge.target === origin.id ? [edge.source] : []));
      const candidates = this.layout.nodes.filter(node => connected.has(node.id)).filter(node => {
        const dx = node.x - origin.x;
        const dy = node.y - origin.y;
        if (event.key === 'ArrowLeft') return dx < 0;
        if (event.key === 'ArrowRight') return dx > 0;
        if (event.key === 'ArrowUp') return dy < 0;
        return dy > 0;
      }).sort((a, b) => Math.hypot(a.x - origin.x, a.y - origin.y) - Math.hypot(b.x - origin.x, b.y - origin.y));
      if (!candidates.length) return;
      event.preventDefault();
      const target = this.root.querySelector(`[data-node-id="${CSS.escape(candidates[0].id)}"]`);
      target?.focus();
      this.selectNode(candidates[0].id, true);
    }

    destroy() { this.resizeObserver?.disconnect(); }
  }

  return {
    EvidenceGraphRenderer,
    KIND_LABELS,
    RELATION_LABELS,
    layoutArchiveAtlasModel,
    layoutEvidenceGraphModel,
    routeEvidenceEdge,
  };
});
