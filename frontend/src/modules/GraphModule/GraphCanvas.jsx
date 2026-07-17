import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import cytoscape from 'cytoscape';
import { graphStyles } from './graphStyles';
import { getRole } from '../../roleStore';
import { maskAccount } from '../../utils/maskAccount';

const formatTransactionLabel = (edge) => {
  const amount = Number(edge.amount || 0);
  const time = edge.time || edge.timestamp || '';
  const formattedAmount = new Intl.NumberFormat('en-IN').format(amount);
  return time ? `\u20B9${formattedAmount} \u00B7 ${time}` : `\u20B9${formattedAmount}`;
};

const getGraphBounds = (container) => {
  const width = container?.clientWidth || 800;
  const height = container?.clientHeight || 600;
  const padding = Math.max(36, Math.min(70, Math.floor(Math.min(width, height) * 0.09)));

  return { width, height, padding };
};

const getNodeDepths = (nodes, edges) => {
  const ids = nodes.map((node) => String(node.accountId || node.id));
  const indegree = new Map(ids.map((id) => [id, 0]));
  const children = new Map(ids.map((id) => [id, []]));

  edges.forEach((edge) => {
    const source = String(edge.source);
    const target = String(edge.target);
    if (!indegree.has(source) || !indegree.has(target)) return;
    indegree.set(target, indegree.get(target) + 1);
    children.get(source).push(target);
  });

  const depths = new Map();
  let queue = ids.filter((id) => indegree.get(id) === 0);
  if (queue.length === 0 && ids.length > 0) queue = [ids[0]];

  queue.forEach((id) => depths.set(id, 0));

  while (queue.length > 0) {
    const id = queue.shift();
    const nextDepth = (depths.get(id) || 0) + 1;
    children.get(id)?.forEach((childId) => {
      if (!depths.has(childId) || nextDepth > depths.get(childId)) {
        depths.set(childId, nextDepth);
        queue.push(childId);
      }
    });
  }

  ids.forEach((id) => {
    if (!depths.has(id)) depths.set(id, 0);
  });

  return depths;
};

const positionNode = (cy, id, position, animate) => {
  const node = cy.getElementById(id);
  if (node.length === 0) return;

  if (animate) {
    node.stop();
    node.animate({ position }, { duration: 450 });
  } else {
    node.position(position);
  }
};

const applyDenseGridLayout = (cy, orderedIds, container, animate) => {
  const { width, height, padding } = getGraphBounds(container);
  const usableWidth = Math.max(width - padding * 2, 1);
  const usableHeight = Math.max(height - padding * 2, 1);
  const aspect = usableWidth / usableHeight;
  const columns = Math.max(1, Math.ceil(Math.sqrt(orderedIds.length * aspect)));
  const rows = Math.max(1, Math.ceil(orderedIds.length / columns));

  orderedIds.forEach((id, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    const x = padding + (usableWidth * (column + 1)) / (columns + 1);
    const y = padding + (usableHeight * (row + 1)) / (rows + 1);
    positionNode(cy, id, { x, y }, animate);
  });
};

const shouldUseDenseGrid = (columns, usableWidth, usableHeight) => {
  const minReadableXGap = 96;
  const minReadableYGap = 86;
  const maxRows = Math.max(...Array.from(columns.values(), (ids) => ids.length), 1);
  const xGap = usableWidth / Math.max(columns.size - 1, 1);
  const yGap = usableHeight / Math.max(maxRows + 1, 1);

  return columns.size > 7 || xGap < minReadableXGap || yGap < minReadableYGap;
};

const applyDashboardLayout = (cy, nodes, edges, container, animate) => {
  const { width, height, padding } = getGraphBounds(container);
  const usableWidth = Math.max(width - padding * 2, 1);
  const usableHeight = Math.max(height - padding * 2, 1);
  const depths = getNodeDepths(nodes, edges);
  const columns = new Map();

  nodes.forEach((node) => {
    const id = String(node.accountId || node.id);
    const depth = depths.get(id) || 0;
    if (!columns.has(depth)) columns.set(depth, []);
    columns.get(depth).push(id);
  });

  const sortedDepths = Array.from(columns.keys()).sort((a, b) => a - b);
  const orderedIds = sortedDepths.flatMap((depth) => columns.get(depth).sort());

  if (shouldUseDenseGrid(columns, usableWidth, usableHeight)) {
    applyDenseGridLayout(cy, orderedIds, container, animate);
    return;
  }

  const lastColumnIndex = Math.max(sortedDepths.length - 1, 1);

  sortedDepths.forEach((depth, columnIndex) => {
    const ids = columns.get(depth).sort();
    ids.forEach((id, rowIndex) => {
      const x = padding + (usableWidth * columnIndex) / lastColumnIndex;
      const y = padding + (usableHeight * (rowIndex + 1)) / (ids.length + 1);
      positionNode(cy, id, { x, y }, animate);
    });
  });
};

/**
 * GraphCanvas (Phase 5 - Live)
 *
 * Dynamically adds new nodes and edges as they arrive from the backend.
 * Synchronizes status changes for existing nodes.
 */
const DEFAULT_LAYOUT = {
  name: 'breadthfirst',
  directed: true,
  spacingFactor: 1.8,
  padding: 50,
  avoidOverlap: true
};

const GraphCanvas = forwardRef(({ nodes = [], edges = [], onNodeClick }, ref) => {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const isInitializedRef = useRef(false);
  const onNodeClickRef = useRef(onNodeClick);
  const animationRef = useRef(null);
  
  // New features state
  const [layoutName, setLayoutName] = React.useState('breadthfirst');
  const [tooltip, setTooltip] = React.useState(null);

  useEffect(() => {
    onNodeClickRef.current = onNodeClick;
  }, [onNodeClick]);

  useImperativeHandle(ref, () => ({
    highlightNode: (nodeId, duration = 1000) => {
      const cy = cyRef.current;
      if (!cy) return;
      const node = cy.getElementById(nodeId);
      if (node.length > 0) {
        node.animate({
          style: { 'border-width': 10, 'border-color': '#fbbf24' }
        }, {
          duration: 200,
          complete: () => {
            setTimeout(() => {
              node.animate({
                style: {
                  'border-width': 2,
                  'border-color': node.data('status') === 'frozen' ? '#6B7280' : '#1D4ED8'
                }
              }, { duration: 400 });
            }, duration);
          }
        });
      }
    }
  }));

  // 1. Cytoscape setup: create the engine once and keep it alive across data updates.
  useEffect(() => {
    if (!containerRef.current || isInitializedRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: graphStyles,
      layout: DEFAULT_LAYOUT,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false
    });

    cyRef.current = cy;
    isInitializedRef.current = true;
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      onNodeClickRef.current?.({ id: node.id(), status: node.data('status') });
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.edges().removeClass('show-label');
        onNodeClickRef.current?.(null);
      }
    });

    cy.on('mouseover tap', 'edge', (evt) => {
      cy.edges().removeClass('show-label');
      evt.target.addClass('show-label');
      
      const pos = evt.renderedPosition || evt.target.renderedMidpoint();
      const edgeData = evt.target.data();
      setTooltip({
        x: pos.x, y: pos.y,
        title: 'Transaction Flow',
        content: `₹${(edgeData.amount || 0).toLocaleString()} at ${edgeData.time || edgeData.timestamp || 'Unknown'}`
      });
    });

    cy.on('mouseover', 'node', (evt) => {
      const pos = evt.renderedPosition;
      const nodeData = evt.target.data();
      const bal = nodeData.current_balance_sim || nodeData.balance || 0;
      setTooltip({
        x: pos.x, y: pos.y,
        title: `Account: ${nodeData.displayLabel || nodeData.id}`,
        content: `Balance: ₹${Number(bal).toLocaleString()} • Status: ${nodeData.status.toUpperCase()}`
      });
    });

    cy.on('mouseout', 'edge, node', (evt) => {
      if (evt.target.isEdge()) {
        evt.target.removeClass('show-label');
      }
      setTooltip(null);
    });

    // Animate marching ants for money flow
    let offset = 0;
    const animateEdges = () => {
      offset = (offset - 0.5) % 9;
      if (cyRef.current) {
        cyRef.current.edges().style('line-dash-offset', offset);
      }
      animationRef.current = requestAnimationFrame(animateEdges);
    };
    animateEdges();

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      cyRef.current?.destroy();
      cyRef.current = null;
      isInitializedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const cy = cyRef.current;
    if (!container || !cy || !window.ResizeObserver) return undefined;

    const observer = new ResizeObserver(() => {
      cy.resize();
      if (nodes.length > 0) {
        applyDashboardLayout(cy, nodes, edges, container, false);
        cy.fit(cy.elements(), getGraphBounds(container).padding);
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, [nodes, edges]);

  // 2. Data sync: update in place without recreating cy instance.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !isInitializedRef.current) return;

    cy.batch(() => {
      const role = getRole();
      const currentIds = new Set();

      // Update or Add Nodes
      nodes.forEach((item) => {
        const nodeId = String(item.accountId || item.id);
        currentIds.add(nodeId);
        const displayLabel = role === "admin" ? nodeId : maskAccount(nodeId);
        
        const existing = cy.getElementById(nodeId);
        if (existing.length > 0) {
          existing.data({ ...item, displayLabel });
        } else {
          cy.add({ data: { ...item, id: nodeId, displayLabel } });
        }
      });

      // Update or Add Edges
      edges.forEach((edge) => {
        const edgeId = String(edge.id || edge.tx_id || `${edge.source}-${edge.target}`);
        currentIds.add(edgeId);
        
        const existing = cy.getElementById(edgeId);
        if (existing.length > 0) {
          existing.data({ ...edge, label: edge.label || formatTransactionLabel(edge) });
        } else {
          cy.add({ data: {
            ...edge,
            id: edgeId,
            label: edge.label || formatTransactionLabel(edge)
          } });
        }
      });

      // Remove Stale Elements
      cy.elements().forEach((ele) => {
        if (!currentIds.has(ele.id())) {
          ele.remove();
        }
      });
    });

    if (nodes.length > 0) {
      if (layoutName === 'breadthfirst') {
        applyDashboardLayout(cy, nodes, edges, containerRef.current, false);
      }
      cy.layout({ name: layoutName, directed: true, spacingFactor: layoutName === 'breadthfirst' ? 1.8 : 1 }).run();
      cy.fit(cy.elements(), 70);
    }
  }, [nodes, edges, layoutName]);

  return (
    <div className="relative w-full h-full">
      {/* Layout Controls */}
      <div className="absolute top-4 right-4 z-10 flex gap-2 bg-card/80 backdrop-blur-md p-1.5 rounded-lg border border-border shadow-lg">
        {['breadthfirst', 'concentric', 'cose'].map(ly => (
          <button
            key={ly}
            onClick={() => setLayoutName(ly)}
            className={`px-3 py-1 text-[10px] font-bold uppercase rounded transition-colors ${layoutName === ly ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}
          >
            {ly.replace('breadthfirst', 'DAG')}
          </button>
        ))}
      </div>

      {/* Rich Tooltip Overlay */}
      {tooltip && (
        <div 
          className="absolute z-50 pointer-events-none transform -translate-x-1/2 -translate-y-[120%] animate-in fade-in zoom-in-95 duration-200"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="bg-popover text-popover-foreground px-4 py-3 rounded-xl shadow-2xl border border-border flex flex-col gap-1 min-w-[200px]">
            <span className="text-[10px] font-black uppercase text-primary tracking-widest">{tooltip.title}</span>
            <span className="text-xs font-mono font-bold whitespace-nowrap">{tooltip.content}</span>
          </div>
          {/* Tooltip triangle tail */}
          <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 translate-y-full w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-border">
            <div className="absolute left-1/2 bottom-[1px] transform -translate-x-1/2 translate-y-full w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[5px] border-t-popover" />
          </div>
        </div>
      )}

      <div
        ref={containerRef}
        className="graph-canvas"
        style={{
          width: '100%',
          height: '100%',
          background: 'transparent', // Let CSS variables handle it
          textAlign: 'left'
        }}
      />
    </div>
  );
});

export default React.memo(GraphCanvas);
