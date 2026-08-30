import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'
import { Empty } from '../components.jsx'

const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export default function Summaries() {
  const [dateStr, setDateStr] = useState(fmt(new Date()))
  const [content, setContent] = useState('')
  const [savedId, setSavedId] = useState(null)
  const [list, setList] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/summaries?date=' + dateStr)
      .then((r) => { setContent(r.content || ''); setSavedId(r.id || null) })
      .catch((e) => toast(e.message))
  }, [dateStr])

  useEffect(() => {
    api.get('/summaries/list').then((r) => setList(r || [])).catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const reloadList = () => api.get('/summaries/list').then((r) => setList(r || [])).catch(() => {})

  const save = async () => {
    if (!content.trim()) return toast('先写点什么再保存吧')
    try {
      const r = await api.post('/summaries', { log_date: dateStr, content })
      setSavedId(r.id)
      toast('已保存 📝')
      reloadList()
    } catch (e) { toast(e.message) }
  }

  const del = async () => {
    if (!savedId) return toast('这天的总结还没保存过')
    if (!confirm('删除这一天的总结？')) return
    try {
      await api.del('/summaries/' + savedId)
      setContent(''); setSavedId(null); toast('已删除'); reloadList()
    } catch (e) { toast(e.message) }
  }

  const today = fmt(new Date())

  return (
    <div className="grid grid-2">
      {/* 左：写总结 */}
      <div className="card summary-editor">
        <h3>📝 每日总结</h3>
        <div className="muted" style={{ marginBottom: 14 }}>
          每天想写就写、不想写就不写，这是你自己的复盘。不打卡也能写。
        </div>
        <div className="field">
          <label>日期</label>
          <input type="date" value={dateStr} max={today} onChange={(e) => setDateStr(e.target.value)} />
        </div>
        <div className="field">
          <label>今日总结</label>
          <textarea rows={9} placeholder={'例如：\n- 完成了什么？\n- 学到了什么？\n- 卡在哪了？\n- 明天打算做什么？'}
            value={content} onChange={(e) => setContent(e.target.value)} />
        </div>
        <div className="row-actions">
          <button className="btn primary" onClick={save}>保存</button>
          {savedId && <button className="btn danger" onClick={del}>删除这天</button>}
        </div>
      </div>

      {/* 右：历史记录 */}
      <div className="card summary-list">
        <h3>🗂️ 历史记录{list ? `（${list.length} 篇）` : ''}</h3>
        {loading ? <div className="loading">加载中…</div> :
          !list || list.length === 0 ? <Empty text="还没有写过总结，从今天开始吧" /> : (
            list.map((s) => (
              <div key={s.id} className={`summary-row${s.log_date === dateStr ? ' active' : ''}`} onClick={() => setDateStr(s.log_date)}>
                <div className="sum-date">{s.log_date}</div>
                <div className="sum-preview">{s.content.length > 60 ? s.content.slice(0, 60) + '…' : s.content}</div>
              </div>
            ))
          )}
      </div>
    </div>
  )
}
