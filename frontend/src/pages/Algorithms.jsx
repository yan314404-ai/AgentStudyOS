import React, { useState } from 'react'
import { useLoad, saveResource, deleteResource } from '../useLoad.js'
import { Pill, Modal, Empty, DangerBtn } from '../components.jsx'
import { toast } from '../toast.js'
import { api } from '../api.js'

const EMPTY = {
  title: '', source: 'LeetCode', url: '', difficulty: '中等', category: '数组',
  is_first: 1, is_solved: 0, saw_solution: 0, review_count: 0,
  last_review_date: '', next_review_date: '', mastery: 0,
  time_complexity: '', space_complexity: '', note: '', mistake_reason: '',
}

function Mastery({ v }) {
  if (!v) return <span style={{ color: 'var(--text-3)' }}>未做</span>
  const labels = { 1: '看过', 2: '会但不熟', 3: '基本掌握', 4: '较熟练', 5: '精通' }
  return (
    <span>
      <Pill text={`m${v}`} /> <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{labels[v]}</span>
    </span>
  )
}

export default function Algorithms() {
  const { data: list, loading, reload } = useLoad('/algorithms')
  const { data: categories } = useLoad('/algorithms/categories', [])
  const [cat, setCat] = useState('')
  const [editing, setEditing] = useState(null)

  if (loading) return <div className="loading">加载中…</div>
  const rows = (list || []).filter((p) => !cat || p.category === cat)

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <select value={cat} onChange={(e) => setCat(e.target.value)} className="btn">
          <option value="">全部分类</option>
          {(categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn sm" onClick={() => api.get('/algorithms/random').then((r) => { if (r) toast(`🎲 ${r.title}（${r.category}）`); else toast('题库还是空的，先加几题吧') })}>
          🎲 今日随机一题
        </button>
        <div style={{ flex: 1 }} />
        <button className="btn primary" onClick={() => setEditing({ ...EMPTY })}>+ 记录题目</button>
      </div>

      <div className="card table-wrap">
        {rows.length === 0 ? <Empty text="没有记录。刷了题就记录一条吧，坚持一年你会看到质变" /> : (
          <table>
            <thead>
              <tr>
                <th>题目</th><th>分类</th><th>难度</th><th>掌握</th>
                <th>一刷</th><th>做对</th><th>看题解</th><th>复习</th><th>下次复习</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.url ? <a href={p.url} target="_blank" rel="noreferrer">{p.title}</a> : p.title}
                    {p.time_complexity && <div style={{ fontSize: 11, color: 'var(--text-3)' }}>O({p.time_complexity}) / O({p.space_complexity})</div>}
                  </td>
                  <td><span className="tag">{p.category}</span></td>
                  <td><Pill text={p.difficulty} /></td>
                  <td><Mastery v={p.mastery} /></td>
                  <td>{p.is_first ? '✅' : '↩️'}</td>
                  <td>{p.is_solved ? '✅' : '❌'}</td>
                  <td>{p.saw_solution ? '📖' : '💪'}</td>
                  <td>{p.review_count} 刷</td>
                  <td style={{ fontSize: 12, color: p.next_review_date ? 'var(--red)' : 'var(--text-3)' }}>{p.next_review_date || '—'}</td>
                  <td>
                    <div className="row-actions">
                      <button className="btn sm" onClick={() => setEditing({ ...p })}>编辑</button>
                      <button className="btn sm" onClick={() => {
                        const rc = (p.review_count || 0) + 1
                        saveResource('/algorithms', { ...p, review_count: rc, last_review_date: new Date().toISOString().slice(0, 10) }, p.id, reload)
                      }}>＋复习</button>
                      <DangerBtn onClick={() => { if (confirm('删除这条记录？')) deleteResource('/algorithms', p.id, reload) }} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing !== null && (
        <AlgoModal
          categories={categories || []}
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(payload) => saveResource('/algorithms', payload, editing.id, () => { reload(); setEditing(null) })}
        />
      )}
    </div>
  )
}

function AlgoModal({ initial, categories, onClose, onSave }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => {
    const v = e.target.value
    setF((s) => ({ ...s, [k]: ['is_first', 'is_solved', 'saw_solution', 'review_count', 'mastery'].includes(k) ? Number(v) : v }))
  }
  const check = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.checked ? 1 : 0 }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.title.trim()) return toast('题目名不能为空')
    onSave({ ...f, title: f.title.trim() })
  }
  return (
    <Modal title={initial.id ? '编辑题目' : '记录题目'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full">
            <label>题目名称 *</label>
            <input value={f.title} onChange={set('title')} placeholder="例如：两数之和" />
          </div>
          <div className="field">
            <label>分类</label>
            <input list="algo-cats" value={f.category} onChange={set('category')} />
            <datalist id="algo-cats">{(categories || []).map((c) => <option key={c} value={c} />)}</datalist>
          </div>
          <div className="field">
            <label>难度</label>
            <select value={f.difficulty} onChange={set('difficulty')}>
              <option>简单</option><option>中等</option><option>困难</option>
            </select>
          </div>
          <div className="field full">
            <label>题目链接</label>
            <input value={f.url} onChange={set('url')} placeholder="https://leetcode.cn/problems/…" />
          </div>
          <div className="field">
            <label>来源</label>
            <input value={f.source} onChange={set('source')} />
          </div>
          <div className="field">
            <label>掌握程度（1~5）</label>
            <select value={f.mastery} onChange={set('mastery')}>
              <option value={0}>还没掌握</option>
              {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div className="field">
            <label>时间复杂度</label>
            <input value={f.time_complexity} onChange={set('time_complexity')} placeholder="如 n, log n, n²" />
          </div>
          <div className="field">
            <label>空间复杂度</label>
            <input value={f.space_complexity} onChange={set('space_complexity')} placeholder="如 n, 1" />
          </div>
          <div className="field full">
            <label>下次复习日期</label>
            <input type="date" value={f.next_review_date} onChange={set('next_review_date')} />
          </div>
          <label className="field"><input type="checkbox" checked={!!f.is_first} onChange={check('is_first')} /> 第一次做</label>
          <label className="field"><input type="checkbox" checked={!!f.is_solved} onChange={check('is_solved')} /> 做对了</label>
          <label className="field"><input type="checkbox" checked={!!f.saw_solution} onChange={check('saw_solution')} /> 看过题解</label>
          <div className="field">
            <label>当前第几刷</label>
            <select value={f.review_count} onChange={set('review_count')}>
              {[0, 1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v === 0 ? '第 1 刷' : `已复习 ${v} 次`}</option>)}
            </select>
          </div>
          <div className="field full">
            <label>错误原因</label>
            <textarea value={f.mistake_reason} onChange={set('mistake_reason')} placeholder="边界条件 / 思路卡住 / 复杂度没想清…" />
          </div>
          <div className="field full">
            <label>我的笔记</label>
            <textarea value={f.note} onChange={set('note')} placeholder="关键思路、模板、易错点…" />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>取消</button>
          <button type="submit" className="btn primary">保存</button>
        </div>
      </form>
    </Modal>
  )
}
