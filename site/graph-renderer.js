/* Cytoscape.js adapter for both graph surfaces (knowledge graph and Idea
 * evidence subgraph). The renderer receives an already-validated display
 * model only; it never reads Archive/Roadmap/Idea JSON and never infers
 * relationships. When Cytoscape is unavailable or mounting fails, callers fall
 * back to the DOM relationship list built from the same display model. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.GraphRenderer = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  let active = null;

  function available() {
    return typeof root.cytoscape === 'function';
  }

  function destroyActive() {
    if (!active) return;
    try {
      active._destroy();
    } catch (_) {
      /* a destroyed container is already gone */
    }
    active = null;
  }

  function reduceMotion() {
    return typeof root.matchMedia === 'function' && root.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function mountGraph(container, options = {}) {
    destroyActive();
    if (!available() || !container) return null;
    const nodes = (options.nodes || []).map((node) => ({
      data: node.data,
      position: node.position || (options.positions || {})[node.data.id] || undefined,
    }));
    const edges = (options.edges || []).map((edge) => ({ data: edge.data }));
    let cy;
    try {
      cy = root.cytoscape({
        container,
        elements: { nodes, edges },
        style: options.styles || (root.GraphStyles ? root.GraphStyles.cytoscapeStylesheet() : []),
        layout: options.layout === 'breadthfirst'
          ? {
              name: 'breadthfirst',
              roots: options.focusId ? [options.focusId] : undefined,
              directed: true,
              padding: 40,
              spacingFactor: 1.15,
              animate: false,
              maximal: false,
            }
          : { name: 'preset', animate: false },
        wheelSensitivity: 0.18,
        minZoom: 0.2,
        maxZoom: 2.4,
        pixelRatio: 1,
        textureOnViewport: false,
      });
    } catch (error) {
      if (typeof options.onFailure === 'function') options.onFailure(error);
      return null;
    }

    const handle = {
      cy,
      selectedNodeId: options.focusId || null,
      selectedEdgeId: null,
      _destroy() {
        root.removeEventListener('resize', resizeListener);
        if (keydownListener) container.removeEventListener('keydown', keydownListener);
        cy.destroy();
      },
    };

    function applyFocus(nodeId) {
      const focusNode = nodeId ? cy.getElementById(nodeId) : cy.collection();
      if (nodeId && focusNode.empty()) return;
      const all = cy.elements();
      const neighborhood = focusNode.empty() ? cy.collection() : focusNode.closedNeighborhood();
      all.removeClass('dim neighbor focused edge-focus');
      if (focusNode.empty()) {
        cy.edges().addClass('dim');
        return;
      }
      focusNode.addClass('focused');
      focusNode.neighborhood().nodes().addClass('neighbor');
      neighborhood.edges().addClass('edge-focus');
      all.not(neighborhood).addClass('dim');
    }

    handle.selectNode = function selectNode(nodeId, notify = true) {
      const node = cy.getElementById(nodeId);
      if (node.empty()) return false;
      cy.elements().unselect();
      handle.selectedNodeId = nodeId;
      handle.selectedEdgeId = null;
      node.select();
      applyFocus(nodeId);
      if (notify && typeof options.onSelectNode === 'function') options.onSelectNode(node.data());
      return true;
    };

    handle.selectEdge = function selectEdge(edgeId, notify = true) {
      const edge = cy.getElementById(edgeId);
      if (edge.empty()) return false;
      cy.elements().unselect();
      handle.selectedEdgeId = edgeId;
      handle.selectedNodeId = null;
      edge.select();
      applyFocus(null);
      cy.edges().addClass('dim');
      edge.removeClass('dim').addClass('edge-focus');
      if (notify && typeof options.onSelectEdge === 'function') options.onSelectEdge(edge.data());
      return true;
    };

    handle.clearSelection = function clearSelection() {
      cy.elements().unselect();
      handle.selectedNodeId = null;
      handle.selectedEdgeId = null;
      applyFocus(null);
    };

    handle.fit = function fit(padding = 40) {
      cy.fit(undefined, padding);
    };

    handle.zoomBy = function zoomBy(delta) {
      const level = Math.max(0.2, Math.min(2.4, cy.zoom() * (1 + delta)));
      cy.zoom({ level, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
      if (typeof options.onZoom === 'function') options.onZoom(Math.round(cy.zoom() * 100));
    };

    handle.reset = function reset() {
      cy.zoom(1);
      cy.pan({ x: 0, y: 0 });
      handle.fit();
      if (typeof options.onZoom === 'function') options.onZoom(Math.round(cy.zoom() * 100));
    };

    handle.refreshLayout = function refreshLayout() {
      cy.layout({
        name: 'breadthfirst',
        roots: handle.selectedNodeId ? [handle.selectedNodeId] : undefined,
        directed: true,
        padding: 40,
        spacingFactor: 1.15,
        animate: false,
      }).run();
      handle.fit();
    };

    handle.moveSelection = function moveSelection(direction) {
      const currentId = handle.selectedNodeId;
      const current = currentId ? cy.getElementById(currentId) : cy.nodes().first();
      if (current.empty()) return false;
      const candidates = current.openNeighborhood().nodes();
      if (candidates.empty()) return false;
      const origin = current.renderedPosition();
      let best = null;
      let bestScore = -Infinity;
      candidates.forEach((node) => {
        const position = node.renderedPosition();
        const dx = position.x - origin.x;
        const dy = position.y - origin.y;
        const length = Math.hypot(dx, dy) || 1;
        const score = (direction === 'left' ? -dx : direction === 'right' ? dx : direction === 'up' ? -dy : dy) / length;
        if (score > bestScore) {
          bestScore = score;
          best = node;
        }
      });
      if (!best || bestScore < 0.05) return false;
      return handle.selectNode(best.id());
    };

    cy.on('tap', 'node', (event) => {
      handle.selectNode(event.target.id());
    });
    cy.on('tap', 'edge', (event) => {
      handle.selectEdge(event.target.id());
    });
    cy.on('dbltap', 'node', (event) => {
      if (typeof options.onExpand === 'function') options.onExpand(event.target.data());
    });
    cy.on('zoom', () => {
      if (typeof options.onZoom === 'function') options.onZoom(Math.round(cy.zoom() * 100));
    });

    function resizeListener() {
      cy.resize();
    }
    root.addEventListener('resize', resizeListener);

    const keydownListener = (event) => {
      const moves = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
      if (moves[event.key]) {
        event.preventDefault();
        handle.moveSelection(moves[event.key]);
      } else if (event.key === 'Enter' && handle.selectedNodeId && typeof options.onExpand === 'function') {
        event.preventDefault();
        options.onExpand(cy.getElementById(handle.selectedNodeId).data());
      } else if (event.key === 'Escape') {
        handle.clearSelection();
      }
    };
    container.addEventListener('keydown', keydownListener);

    active = handle;
    return handle;
  }

  function getActive() {
    return active;
  }

  return { available, mountGraph, destroyActive, getActive };
});
