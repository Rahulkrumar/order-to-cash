import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'

const HIDDEN_FIELDS = new Set(['type', 'label', 'color', 'size'])

// Cluster colors per node type
const CLUSTER_COLORS = {
  Customer:        { fill: '#dbeafe', stroke: '#3b82f6' },
  SalesOrder:      { fill: '#dcfce7', stroke: '#22c55e' },
  OrderItem:       { fill: '#d1fae5', stroke: '#10b981' },
  Product:         { fill: '#fef9c3', stroke: '#eab308' },
  Delivery:        { fill: '#ffe4e6', stroke: '#f43f5e' },
  BillingDocument: { fill: '#f3e8ff', stroke: '#a855f7' },
  JournalEntry:    { fill: '#ffedd5', stroke: '#f97316' },
  Payment:         { fill: '#cffafe', stroke: '#06b6d4' },
  Plant:           { fill: '#f1f5f9', stroke: '#64748b' },
}

function NodePopup({ node, onClose, position }) {
  if (!node) return null
  const data = node.data || {}
  const entries = Object.entries(data).filter(([k]) => !HIDDEN_FIELDS.has(k) && data[k] !== '')
  const visible = entries.slice(0, 12)
  const hidden = entries.length - visible.length
  const colors = CLUSTER_COLORS[node.type] || { fill: '#f1f5f9', stroke: '#64748b' }

  return (
    <div
      className="node-popup"
      style={{
        position: 'absolute',
        left: Math.min(position.x + 12, window.innerWidth - 360),
        top: Math.max(position.y - 20, 60),
        pointerEvents: 'auto',
        borderTop: `3px solid ${colors.stroke}`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div className="popup-title" style={{ color: colors.stroke }}>{node.type}</div>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 16, padding: 0 }}
        >×</button>
      </div>
      <div className="field-row">
        <span className="field-key">Entity:</span>
        <span className="field-val">{node.type}</span>
      </div>
      {visible.map(([k, v]) => (
        <div className="field-row" key={k}>
          <span className="field-key">{k}:</span>
          <span className="field-val">{String(v)}</span>
        </div>
      ))}
      {hidden > 0 && (
        <div style={{ color: '#94a3b8', fontStyle: 'italic', marginTop: 4, fontSize: 12 }}>
          +{hidden} more fields
        </div>
      )}
      <div className="connections">
        Connections: {node.connections || 0}
      </div>
    </div>
  )
}

// Legend component
function Legend() {
  return (
    <div style={{
      position: 'absolute', bottom: 16, left: 16,
      background: 'rgba(255,255,255,0.95)', borderRadius: 10,
      padding: '10px 14px', boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      fontSize: 11, zIndex: 10, border: '1px solid #e2e8f0',
    }}>
      <div style={{ fontWeight: 600, color: '#475569', marginBottom: 6 }}>Node Types</div>
      {Object.entries(CLUSTER_COLORS).map(([type, colors]) => (
        <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: colors.fill, border: `2px solid ${colors.stroke}`,
            flexShrink: 0,
          }} />
          <span style={{ color: '#64748b' }}>{type}</span>
        </div>
      ))}
    </div>
  )
}

export default function GraphView({
  graphData, highlightedNodes, selectedNode, onSelectNode, showOverlay
}) {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const simRef = useRef(null)
  const [popupPos, setPopupPos] = useState({ x: 0, y: 0 })
  const [popup, setPopup] = useState(null)

  const buildGraph = useCallback(() => {
    if (!svgRef.current || !graphData.nodes.length) return

    const container = containerRef.current
    const W = container.clientWidth
    const H = container.clientHeight

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', W)
      .attr('height', H)
      .style('background', '#f8f9fa')

    const g = svg.append('g')
    svg.call(
      d3.zoom()
        .scaleExtent([0.05, 4])
        .on('zoom', e => g.attr('transform', e.transform))
    )

    const nodes = graphData.nodes.map(n => ({ ...n, connections: 0 }))
    const links = graphData.edges.map(e => ({ ...e }))

    const connMap = {}
    links.forEach(l => {
      connMap[l.source] = (connMap[l.source] || 0) + 1
      connMap[l.target] = (connMap[l.target] || 0) + 1
    })
    nodes.forEach(n => { n.connections = connMap[n.id] || 0 })

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(90).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(d => (d.size || 8) + 6))
    simRef.current = sim

    // Edges
    const link = g.append('g').selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#cbd5e1')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.5)

    // Node groups
    const nodeG = g.append('g').selectAll('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation()
        const rect = svgRef.current.getBoundingClientRect()
        const transform = d3.zoomTransform(svgRef.current)
        setPopupPos({
          x: transform.applyX(d.x) + rect.left,
          y: transform.applyY(d.y) + rect.top,
        })
        setPopup(d)
        onSelectNode(d)
      })
      .call(
        d3.drag()
          .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
          .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )

    // Highlight pulse ring (outer)
    nodeG.append('circle')
      .attr('r', d => (d.size || 8) + 8)
      .attr('fill', '#fbbf24')
      .attr('fill-opacity', 0.25)
      .attr('stroke', '#f59e0b')
      .attr('stroke-width', 2)
      .attr('opacity', d => highlightedNodes.includes(d.id) ? 1 : 0)
      .attr('class', 'highlight-ring')

    // Main circle with cluster color
    nodeG.append('circle')
      .attr('r', d => d.size || 8)
      .attr('fill', d => {
        const c = CLUSTER_COLORS[d.type]
        return c ? c.fill : 'white'
      })
      .attr('stroke', d => {
        const c = CLUSTER_COLORS[d.type]
        return c ? c.stroke : '#60a5fa'
      })
      .attr('stroke-width', 2)

    sim.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      nodeG.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    svg.on('click', () => {
      setPopup(null)
      onSelectNode(null)
    })
  }, [graphData, onSelectNode])

  useEffect(() => { buildGraph() }, [buildGraph])

  // Update highlighted rings dynamically
  useEffect(() => {
    if (!svgRef.current) return
    d3.select(svgRef.current)
      .selectAll('.highlight-ring')
      .transition().duration(300)
      .attr('opacity', d => highlightedNodes.includes(d?.id) ? 1 : 0)
  }, [highlightedNodes])

  useEffect(() => {
    const ro = new ResizeObserver(() => buildGraph())
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [buildGraph])

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <svg ref={svgRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      <Legend />
      {popup && (
        <NodePopup
          node={popup}
          onClose={() => { setPopup(null); onSelectNode(null) }}
          position={popupPos}
        />
      )}
    </div>
  )
}

          



     
    

