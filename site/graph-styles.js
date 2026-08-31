/* Graph surface style tokens shared by the knowledge graph and the Idea
 * evidence subgraph. Canvas rendering cannot read CSS variables, so the
 * palette mirrors editorial-tokens.css / knowledge-graph.css explicitly.
 * Shape, border style, icon and text label all differentiate kinds; color is
 * never the only signal. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.GraphStyles = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const PALETTE = {
    canvas: '#fffefb',
    ink1: '#151b20',
    ink2: '#343b40',
    ink3: '#666b69',
    hairline: '#e4e0d6',
    navy: '#19334a',
    navyDeep: '#0b3f7d',
    navyMuted: '#61778a',
    blueMuted: '#6f88a5',
    blueSoft: '#e8edf1',
    positive: '#536a3d',
    positiveLine: '#4f8629',
    negative: '#b84f3b',
    negativeLine: '#cf2d2d',
    warning: '#9b631f',
    warningLine: '#c47a08',
    neutral: '#858b91',
  };

  // Published graph kinds plus the two Idea-field-only projection kinds
  // (assumption, decision) that never enter knowledge/graph.json.
  const KIND_META = {
    topic: { label: 'Topic', icon: 'tag', shape: 'round-rectangle', width: 188, height: 56, borderColor: PALETTE.navy, bgColor: '#fffefb', borderWidth: 2 },
    direction: { label: 'Direction', icon: 'arrow', shape: 'tag', width: 168, height: 48, borderColor: PALETTE.navyMuted, bgColor: '#f6f9fb', borderWidth: 1.5 },
    item: { label: '日报条目', icon: 'claim', shape: 'rectangle', width: 188, height: 52, borderColor: PALETTE.ink2, bgColor: '#fbfaf7', borderWidth: 1.5 },
    judgement: { label: '编辑判断', icon: 'status', shape: 'barrel', width: 196, height: 64, borderColor: PALETTE.warning, bgColor: '#fdf7ec', borderWidth: 1.5 },
    issue: { label: '日报期次', icon: 'calendar', shape: 'ellipse', width: 118, height: 44, borderColor: PALETTE.neutral, bgColor: '#f4f4f2', borderWidth: 1.5 },
    roadmap: { label: 'Roadmap', icon: 'roadmap', shape: 'round-rectangle', width: 168, height: 52, borderColor: PALETTE.navyDeep, bgColor: PALETTE.blueSoft, borderWidth: 2.5 },
    roadmap_branch: { label: 'Roadmap 分支', icon: 'roadmap', shape: 'tag', width: 168, height: 46, borderColor: PALETTE.blueMuted, bgColor: '#eef2f6', borderWidth: 1.5, borderStyle: 'dashed' },
    idea: { label: 'Idea', icon: 'idea', shape: 'ellipse', width: 176, height: 54, borderColor: PALETTE.negative, bgColor: '#fdf0ed', borderWidth: 2 },
    assumption: { label: 'Assumption', icon: 'question', shape: 'rectangle', width: 168, height: 48, borderColor: PALETTE.neutral, bgColor: '#fbfaf7', borderWidth: 1.5, borderStyle: 'dashed' },
    decision: { label: 'Decision', icon: 'check', shape: 'round-rectangle', width: 148, height: 44, borderColor: PALETTE.positive, bgColor: '#f3f6ef', borderWidth: 1.5 },
  };

  // Relation labels are part of the data contract (knowledge/graph.json ships
  // them); this table adds visual routing only and must never flip direction.
  const RELATION_META = {
    has_direction: { label: '包含方向', color: PALETTE.navyMuted, taxi: true },
    has_item: { label: '收录条目', color: PALETTE.navyMuted, taxi: true },
    published_in: { label: '发布于', color: PALETTE.neutral, taxi: true },
    supports_judgement: { label: '支持判断', color: PALETTE.warningLine, taxi: false },
    tracks: { label: '跟踪', color: PALETTE.navyDeep, taxi: true },
    organizes: { label: '组织方向', color: PALETTE.blueMuted, taxi: true },
    uses_evidence: { label: '引用证据', color: PALETTE.blueMuted, taxi: false },
    relates_to: { label: '关联专题', color: PALETTE.negativeLine, taxi: false },
    supports_idea: { label: '支持', color: PALETTE.positiveLine, taxi: false },
    challenges_idea: { label: '反对', color: PALETTE.negativeLine, taxi: false },
    // Idea-subgraph-only relations projected from Idea fields.
    qualifies: { label: '限定', color: PALETTE.warningLine, taxi: false },
    leads_to: { label: '导向', color: PALETTE.positive, taxi: false },
  };

  const FONT_STACK = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif';

  function nodeStyle(kind) {
    const meta = KIND_META[kind] || KIND_META.item;
    const style = {
      'background-color': meta.bgColor,
      'border-color': meta.borderColor,
      'border-width': meta.borderWidth,
      'border-style': meta.borderStyle || 'solid',
      shape: meta.shape,
      width: meta.width,
      height: meta.height,
      label: 'data(label)',
      'font-family': FONT_STACK,
      'font-size': kind === 'topic' || kind === 'roadmap' || kind === 'idea' ? 12 : 10.5,
      'font-weight': kind === 'topic' || kind === 'roadmap' || kind === 'idea' ? 600 : 400,
      color: PALETTE.ink1,
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'wrap',
      'text-max-width': 'node',
      'text-outline-color': meta.bgColor,
      'text-outline-width': 3,
      'z-index': kind === 'topic' || kind === 'roadmap' || kind === 'idea' ? 20 : 10,
    };
    return style;
  }

  function edgeStyle(relation) {
    const meta = RELATION_META[relation] || RELATION_META.published_in;
    const structural = Boolean(meta.taxi);
    const style = {
      width: structural ? 1.4 : 2,
      'line-color': meta.color,
      'line-style': structural ? 'solid' : 'solid',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': meta.color,
      'arrow-scale': 0.85,
      'curve-style': structural ? 'taxi' : 'bezier',
      'taxi-direction': 'rightward',
      'taxi-turn': 36,
      'taxi-radius': 6,
      'control-point-step-size': 60,
      'loop-orientation': 'vertical',
      label: 'data(label)',
      'font-family': FONT_STACK,
      'font-size': 9.5,
      color: PALETTE.ink2,
      'text-background-color': PALETTE.canvas,
      'text-background-opacity': 1,
      'text-background-padding': '2px',
      'text-border-opacity': 0,
      'text-rotation': 'autorotate',
      'text-opacity': 0,
      'z-index': 5,
    };
    return style;
  }

  function cytoscapeStylesheet() {
    const styles = [];
    Object.keys(KIND_META).forEach((kind) => {
      styles.push({ selector: `node[kind = "${kind}"]`, style: nodeStyle(kind) });
    });
    Object.keys(RELATION_META).forEach((relation) => {
      styles.push({ selector: `edge[relation = "${relation}"]`, style: edgeStyle(relation) });
    });
    styles.push(
      {
        selector: 'node',
        style: {
          'min-width': 24,
          'min-height': 24,
          'transition-property': 'border-width opacity',
          'transition-duration': 120,
        },
      },
      {
        selector: 'edge',
        style: {
          'transition-property': 'line-color opacity text-opacity width',
          'transition-duration': 120,
        },
      },
      {
        selector: 'node.dim',
        style: { opacity: 0.32 },
      },
      {
        selector: 'edge.dim',
        style: { opacity: 0.1, 'text-opacity': 0 },
      },
      {
        selector: 'node.neighbor',
        style: { 'border-width': 2.5 },
      },
      {
        selector: 'node.focused',
        style: {
          'border-width': 3.5,
          'border-color': PALETTE.navyDeep,
          'overlay-color': 'rgba(11, 63, 125, 0.12)',
          'overlay-padding': 6,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 3.5,
          'border-color': PALETTE.navyDeep,
          'overlay-color': 'rgba(11, 63, 125, 0.18)',
          'overlay-padding': 6,
        },
      },
      {
        selector: 'edge.edge-focus',
        style: { width: 2.4, 'text-opacity': 1, 'z-index': 30 },
      },
      {
        selector: 'edge:selected',
        style: { width: 3, 'text-opacity': 1, 'z-index': 31, 'line-color': PALETTE.navyDeep, 'target-arrow-color': PALETTE.navyDeep },
      },
    );
    return styles;
  }

  return { PALETTE, KIND_META, RELATION_META, cytoscapeStylesheet, FONT_STACK };
});
