import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Pill } from '../components.jsx'

const GROUPS = [
  ['tasks', '🗺️ 学习任务', (r) => <div key={r.id}><strong>{r.title}</strong> <span className="muted">· {r.phase}</span> <Pill text={r.status} /> <div className="muted">{r.description}</div></div>],
  ['algorithms', '🧮 算法题', (r) => <div key={r.id}><strong>{r.title}</strong> <span className="muted">· {r.category} · {r.difficulty}</span></div>],
  ['bago', '📚 八股题', (r) => <div key={r.id}><strong>{r.question}</strong> <span className="muted">· {r.category}</span></div>],
  ['courses', '🎬 课程', (r) => <div key={r.id}><strong>{r.name}</strong> <span className="muted">· {r.platform}</span></div>],
  ['projects', '🚀 项目', (r) => <div key={r.id}><strong>{r.name}</strong> <span className="muted">· {r.goal}</span></div>],
]

export default function Search({ query }) {
  const [q, setQ] = useState(query || '')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { setQ(query || '') }, [query])

  const run = async (e) => {
    if (e) e.preventDefault()
    if (!q.trim()) return
    setLoading(true)
    try { setData(await api.get('/search?q=' + encodeURIComponent(q.trim()))) }
    catch { /* toast 已在 api 层 */ }
    finally { setLoading(false) }
  }

  const total = data ? GROUPS.reduce((s, [k]) => s + (data[k]?.length || 0), 0) : 0

  return (
    <div>
      <form onSubmit={run} className="card" style={{ display: 'flex', gap: 10, marginBottom: 16, padding: 12 }}>
        <input
          value={q} onChange={(e) => setQ(e.target.value)} autoFocus
          placeholder="输入关键词，回车搜索…（支持任务 / 算法 / 八股 / 课程 / 项目）"
          style={{ flex: 1, border: 'none', outline: 'none', fontSize: 15 }}
        />
        <button className="btn primary" type="submit">搜索</button>
      </form>

      {loading && <div className="loading">搜索中…</div>}

      {data && !loading && (
        <div style={{ marginBottom: 12, color: 'var(--text-2)', fontSize: 13 }}>找到 <strong>{total}</strong> 条结果</div>
      )}

      {data && total === 0 && <div className="card"><div className="empty">没有找到相关结果，换个关键词试试</div></div>}

      {data && GROUPS.map(([key, label, render]) => {
        const items = data[key] || []
        if (!items.length) return null
        return (
          <div key={key} className="card" style={{ marginBottom: 14 }}>
            <h3>{label}（{items.length}）</h3>
            {items.map(render)}
          </div>
        )
      })}
    </div>
  )
}
