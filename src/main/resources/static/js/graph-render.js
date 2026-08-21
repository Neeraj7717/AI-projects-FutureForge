// Renders a { nodes, edges } graph (from GraphNodeDto/GraphEdgeDto) using vis-network, styled
// after a graph-database browser (dark canvas, flat colored nodes, force-directed layout,
// a label/relationship legend) so the graph reads as "this is a real graph query result",
// not a product-card wall. The seed/root product (type "SEED_PRODUCT", or matching rootId)
// is colored distinctly from the rest.

const GRAPH_MIN_SCALE = 0.12;
const GRAPH_MAX_SCALE = 3;

const GRAPH_COLORS = {
  root: { bg: "#f43f5e", border: "#fda4af" },
  node: { bg: "#4361ee", border: "#93a5f7" },
  edge: "#475569",
  edgeHighlight: "#818cf8",
  label: "#e5e7eb",
};

function renderDependencyGraph(container, nodes, edges, rootId) {
  const isRootNode = (n) => n.type === "SEED_PRODUCT" || n.id === rootId;

  const visNodes = new vis.DataSet(nodes.map((n) => {
    const root = isRootNode(n);
    const palette = root ? GRAPH_COLORS.root : GRAPH_COLORS.node;
    return {
      id: n.id,
      label: `${n.label}\n${n.sublabel || ""}`,
      shape: "dot",
      size: root ? 22 : 16,
      color: {
        background: palette.bg,
        border: palette.border,
        highlight: { background: palette.bg, border: "#ffffff" },
      },
      borderWidth: root ? 3 : 2,
      font: { color: GRAPH_COLORS.label, size: 11.5, face: "-apple-system, BlinkMacSystemFont, sans-serif", vadjust: 14, multi: false, bold: root ? "650" : false },
    };
  }));

  const visEdges = new vis.DataSet(edges.map((e) => ({
    from: e.from,
    to: e.to,
    arrows: "to",
    label: e.label || "",
    color: { color: GRAPH_COLORS.edge, highlight: GRAPH_COLORS.edgeHighlight },
    font: { color: "#94a3b8", size: 9, strokeWidth: 0, background: "rgba(13,18,32,0.9)", align: "middle" },
    smooth: { type: "dynamic" },
  })));

  const network = new vis.Network(container, { nodes: visNodes, edges: visEdges }, {
    layout: { improvedLayout: true },
    physics: {
      enabled: true,
      solver: "barnesHut",
      barnesHut: { gravitationalConstant: -3200, springLength: 130, springConstant: 0.045, damping: 0.5, avoidOverlap: 0.4 },
      stabilization: { iterations: 150, fit: false },
    },
    interaction: {
      hover: true,
      dragNodes: true,
      // Mouse wheel zoom is intentionally off: it hijacks the page's scroll the moment the
      // cursor crosses the canvas, which is a bad surprise on a page you're otherwise just
      // reading. Dragging still pans; the +/- buttons below are the only way to zoom.
      zoomView: false,
      dragView: true,
      tooltipDelay: 150,
    },
    edges: { width: 1.3 },
  });

  // Physics settles the layout once, then we freeze it - keeps the organic force-directed
  // spread from the screenshot without letting the simulation run (and jitter/eat CPU) forever.
  // network.fit() alone can zoom out arbitrarily far for a large graph, shrinking labels past
  // legibility while node borders (vector strokes) stay visible - so floor the resulting scale.
  const MIN_FIT_SCALE = 0.55;
  network.once("stabilizationIterationsDone", () => {
    network.setOptions({ physics: false });
    network.fit({ animation: false });
    if (network.getScale() < MIN_FIT_SCALE) {
      network.moveTo({ scale: MIN_FIT_SCALE, animation: false });
    }
  });

  attachZoomControls(container, network);
  attachGraphLegend(container, nodes, edges, isRootNode);
  return network;
}

// +/- (and fit-to-view) buttons, overlaid top-right on the graph's wrapping container.
// Re-renders (e.g. changing the hops dropdown) call renderDependencyGraph again on the same
// wrapper, so this reuses the existing control strip instead of stacking a duplicate one, and
// rebinds its click handlers to whichever `network` instance is current.
function attachZoomControls(container, network) {
  const wrap = container.parentElement;
  if (!wrap) return;

  let controls = wrap.querySelector(".graph-zoom-controls");
  if (!controls) {
    controls = document.createElement("div");
    controls.className = "graph-zoom-controls";
    controls.innerHTML = `
      <button type="button" class="graph-zoom-btn" data-action="in" aria-label="Zoom in" title="Zoom in">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
      <button type="button" class="graph-zoom-btn" data-action="out" aria-label="Zoom out" title="Zoom out">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
      <button type="button" class="graph-zoom-btn" data-action="fit" aria-label="Fit to view" title="Fit to view">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
      </button>
    `;
    wrap.appendChild(controls);
  }

  const zoomBy = (factor) => {
    const target = Math.min(GRAPH_MAX_SCALE, Math.max(GRAPH_MIN_SCALE, network.getScale() * factor));
    network.moveTo({ scale: target, animation: { duration: 180, easingFunction: "easeInOutQuad" } });
  };

  controls.querySelectorAll(".graph-zoom-btn").forEach((btn) => {
    btn.onclick = () => {
      if (btn.dataset.action === "in") zoomBy(1.3);
      else if (btn.dataset.action === "out") zoomBy(1 / 1.3);
      else network.fit({ animation: { duration: 220, easingFunction: "easeInOutQuad" } });
    };
  });
}

// Top-left "NODE LABELS" / "RELATIONSHIPS" panel, counted from the actual graph payload so it
// never drifts out of sync with what's drawn - same reuse-on-re-render pattern as the zoom controls.
function attachGraphLegend(container, nodes, edges, isRootNode) {
  const wrap = container.parentElement;
  if (!wrap) return;

  const rootCount = nodes.filter(isRootNode).length;
  const otherCount = nodes.length - rootCount;
  const edgeCounts = {};
  edges.forEach((e) => { const k = e.label || "RELATED_TO"; edgeCounts[k] = (edgeCounts[k] || 0) + 1; });

  let legend = wrap.querySelector(".graph-legend");
  if (!legend) {
    legend = document.createElement("div");
    legend.className = "graph-legend";
    wrap.appendChild(legend);
  }

  const nodeRows = [
    rootCount ? `<div class="legend-row"><span class="legend-dot" style="background:${GRAPH_COLORS.root.bg}"></span>this product<span class="legend-count">${rootCount}</span></div>` : "",
    otherCount ? `<div class="legend-row"><span class="legend-dot" style="background:${GRAPH_COLORS.node.bg}"></span>recommended<span class="legend-count">${otherCount}</span></div>` : "",
  ].join("");

  const edgeRows = Object.entries(edgeCounts)
    .map(([type, count]) => `<div class="legend-row"><span class="legend-dash"></span>${escapeHtml(type)}<span class="legend-count">${count}</span></div>`)
    .join("");

  legend.innerHTML = `
    <div class="legend-block">
      <div class="legend-heading">Node labels</div>
      ${nodeRows}
    </div>
    <div class="legend-block">
      <div class="legend-heading">Relationships</div>
      ${edgeRows}
    </div>
  `;
}
