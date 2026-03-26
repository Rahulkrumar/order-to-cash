import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const SUGGESTED = [
  'Which products have the most billing documents?',
  'Trace billing document 91150187',
  'Find sales orders delivered but not billed',
  'Show all payments cleared in 2025',
  'Which customer has the highest order value?',
]

function Avatar({ initials, dark }) {
  return (
    <div style={{
      width: 32, height: 32, borderRadius: '50%',
      background: dark ? '#111' : '#f1f5f9',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 12, fontWeight: 600,
      color: dark ? 'white' : '#475569',
      flexShrink: 0,
    }}>
      {initials}
    </div>
  )
}

function SQLBlock({ sql }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          background: 'none', border: '1px solid #e2e8f0', borderRadius: 6,
          fontSize: 11, color: '#64748b', cursor: 'pointer', padding: '3px 8px',
        }}
      >
        {open ? '▾' : '▸'} {open ? 'Hide' : 'Show'} SQL
      </button>
      {open && <div className="msg-sql">{sql}</div>}
    </div>
  )
}

export default function ChatPanel({ onHighlight, apiUrl }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hi! I can help you analyze the **Order to Cash** process.',
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text) => {
    const q = text || input.trim()
    if (!q || loading) return
    setInput('')

    const userMsg = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await axios.post(`${apiUrl}/chat`, {
        message: q,
        history: history.slice(-6),
      })
      const { answer, sql, data, highlighted_nodes } = res.data

      const botMsg = { role: 'assistant', content: answer, sql, data }
      setMessages(prev => [...prev, botMsg])

      if (highlighted_nodes?.length) {
        onHighlight(highlighted_nodes)
      }

      setHistory(prev => [
        ...prev,
        { role: 'user', content: q },
        { role: 'assistant', content: answer },
      ])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: err.response?.data?.detail || 'Connection error. Is the backend running?',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="chat-panel" style={{ height: '100%' }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px 10px',
        borderBottom: '1px solid #f1f5f9',
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 2 }}>Chat with Graph</div>
        <div style={{ fontSize: 13, color: '#475569' }}>Order to Cash</div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex',
            gap: 10,
            marginBottom: 16,
            flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
          }}>
            {msg.role === 'assistant' && <Avatar initials="D" dark />}
            {msg.role === 'user' && <Avatar initials="You" dark={false} />}

            <div style={{ flex: 1 }}>
              {msg.role === 'assistant' && (
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
                  Dodge AI
                  <span style={{ color: '#94a3b8', fontWeight: 400, marginLeft: 4 }}>
                    Graph Agent
                  </span>
                </div>
              )}

              {msg.role === 'user' ? (
                <div className="msg-user">{msg.content}</div>
              ) : (
                <div className="msg-bot">
                  <span dangerouslySetInnerHTML={{
                    __html: msg.content
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\n/g, '<br/>')
                  }} />
                  {msg.sql && <SQLBlock sql={msg.sql} />}
                  {msg.data?.length > 0 && (
                    <div className="msg-results-count">
                      {msg.data.length} row{msg.data.length !== 1 ? 's' : ''} returned
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 16 }}>
            <Avatar initials="D" dark />
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>Dodge AI <span style={{ color: '#94a3b8', fontWeight: 400 }}>Graph Agent</span></div>
              <div className="msg-bot" style={{ color: '#94a3b8' }}>
                <span style={{ animation: 'pulse 1s infinite' }}>Analyzing…</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested queries */}
      {messages.length <= 1 && (
        <div style={{ padding: '0 12px 8px', flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>Try asking:</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {SUGGESTED.map(s => (
              <button
                key={s}
                onClick={() => send(s)}
                style={{
                  background: '#f8fafc', border: '1px solid #e2e8f0',
                  borderRadius: 8, padding: '6px 10px', fontSize: 12,
                  textAlign: 'left', cursor: 'pointer', color: '#475569',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.target.style.background = '#f1f5f9'}
                onMouseLeave={e => e.target.style.background = '#f8fafc'}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid #f1f5f9',
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          background: '#f8fafc', border: '1px solid #e2e8f0',
          borderRadius: 10, padding: '8px 12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span className="status-dot" />
            <span style={{ fontSize: 11, color: '#64748b' }}>Dodge AI is awaiting instructions</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Analyze anything"
            rows={1}
            style={{
              flex: 1, resize: 'none', border: '1px solid #e2e8f0',
              borderRadius: 8, padding: '8px 12px', fontSize: 13,
              fontFamily: 'inherit', outline: 'none', lineHeight: 1.5,
              background: 'white',
            }}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            style={{
              background: input.trim() && !loading ? '#111' : '#e2e8f0',
              color: input.trim() && !loading ? 'white' : '#94a3b8',
              border: 'none', borderRadius: 8, padding: '8px 16px',
              fontSize: 13, fontWeight: 500, cursor: input.trim() && !loading ? 'pointer' : 'default',
              transition: 'background 0.15s',
              alignSelf: 'flex-end',
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
