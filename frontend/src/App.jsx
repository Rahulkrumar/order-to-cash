import { useState, useEffect } from 'react'
import GraphView from './components/GraphView.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || '/api'

export default function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [highlightedNodes, setHighlightedNodes] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showOverlay, setShowOverlay] = useState(true)

  useEffect(() => {
    axios.get(`${API}/graph`)
      .then(res => {
        setGraphData(res.data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Top nav */}
      <nav style={{
        height: 52,
        borderBottom: '1px solid #e2e8f0',
        background: 'white',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 8,
        flexShrink: 0,
        zIndex: 10,
      }}>
        <button
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '4px 6px', borderRadius: 4, color: '#64748b',
            fontSize: 18, lineHeight: 1,
          }}
          title="Toggle sidebar"
        >⊞</button>
        <span style={{ color: '#94a3b8', fontSize: 14 }}>Mapping</span>
        <span style={{ color: '#94a3b8', fontSize: 14 }}>/</span>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Order to Cash</span>
        {loading && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#94a3b8' }}>
            Loading graph…
          </span>
        )}
        {!loading && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#94a3b8' }}>
            {graphData.nodes.length} nodes · {graphData.edges.length} edges
          </span>
        )}
      </nav>

      {/* Main split layout */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Graph area */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {/* Toolbar */}
          <div style={{
            position: 'absolute', top: 12, left: 12, zIndex: 20,
            display: 'flex', gap: 8,
          }}>
            <button
              style={{
                background: 'white', border: '1px solid #e2e8f0',
                borderRadius: 8, padding: '6px 12px', fontSize: 13,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              }}
              onClick={() => setSelectedNode(null)}
            >
              ⤢ Minimize
            </button>
            <button
              style={{
                background: showOverlay ? '#111' : 'white',
                color: showOverlay ? 'white' : '#111',
                border: '1px solid #e2e8f0',
                borderRadius: 8, padding: '6px 12px', fontSize: 13,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              }}
              onClick={() => setShowOverlay(v => !v)}
            >
              <span style={{ fontSize: 15 }}>⊞</span>
              {showOverlay ? 'Hide' : 'Show'} Granular Overlay
            </button>
          </div>

          <GraphView
            graphData={graphData}
            highlightedNodes={highlightedNodes}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
            showOverlay={showOverlay}
          />
        </div>

        {/* Chat panel — fixed right */}
        <div style={{ width: 360, flexShrink: 0 }}>
          <ChatPanel
            onHighlight={setHighlightedNodes}
            apiUrl={API}
          />
        </div>
      </div>
    </div>
  )
}
