import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'

const HIDDEN_FIELDS = new Set(['type', 'label', 'color', 'size'])

function NodePopup({ node, onClose, position }) {
  if (!node) return null
  const data = node.data || {}
  const entries = Object.entries(data).filter(([k]) => !HIDDEN_FIELDS.has(k) && data[k] !== '')
  const visible = entries.slice(0, 12)
  const hidden = entries.length - visible.length

  return (
    <div
      className="node-popup"
      style={{
        position: 'absolute',
        left: Math.min(position.x + 12, window.innerWidth - 360),
        top: Math.max(position.y - 20, 60),
        pointerEvents: 'auto',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div className="popup-title">{node.type}</div>
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
          Additional fields hidden for readability
        </div>
      )}
      <div className="connections">
        Connections: {node.connections || 0}
      </div>
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

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', W)
      .attr('height', H)
      .style('background', '#f8f9fa')

    // Zoom behaviour
    const g = svg.append('g')
    svg.call(
      d3.zoom()
        .scaleExtent([0.05, 4])
        .on('zoom', e => g.attr('transform', e.transform))
    )

    // Deep-copy nodes/links (d3 mutates them)
    const nodes = graphData.nodes.map(n => ({ ...n, connections: 0 }))
    const links = graphData.edges.map(e => ({ ...e }))

    // Count connections per node
    const connMap = {}
    links.forEach(l => {
      connMap[l.source] = (connMap[l.source] || 0) + 1
      connMap[l.target] = (connMap[l.target] || 0) + 1
    })
    nodes.forEach(n => { n.connections = connMap[n.id] || 0 })

    // Force simulation
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(80).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(d => (d.size || 8) + 4))
    simRef.current = sim

    // Edges
    const link = g.append('g').selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#bfdbfe')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.7)

    // Nodes
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

    // Outer ring (highlighted)
    nodeG.append('circle')
      .attr('r', d => (d.size || 8) + 5)
      .attr('fill', 'none')
      .attr('stroke', '#fbbf24')
      .attr('stroke-width', 2)
      .attr('opacity', d => highlightedNodes.includes(d.id) ? 1 : 0)
      .attr('class', 'highlight-ring')

    // Main circle
    nodeG.append('circle')
      .attr('r', d => d.size || 8)
      .attr('fill', 'white')
      .attr('stroke', d => d.color || '#60a5fa')
      .attr('stroke-width', 1.5)

    // Tick
    sim.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      nodeG.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Click outside to deselect
    svg.on('click', () => {
      setPopup(null)
      onSelectNode(null)
    })
  }, [graphData, onSelectNode])

  useEffect(() => { buildGraph() }, [buildGraph])

  // Update highlighted rings when highlightedNodes changes
  useEffect(() => {
    if (!svgRef.current) return
    d3.select(svgRef.current)
      .selectAll('.highlight-ring')
      .attr('opacity', d => highlightedNodes.includes(d?.id) ? 1 : 0)
  }, [highlightedNodes])

  // Handle resize
  useEffect(() => {
    const ro = new ResizeObserver(() => buildGraph())
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [buildGraph])

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <svg ref={svgRef} style={{ display: 'block', width: '100%', height: '100%' }} />
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
