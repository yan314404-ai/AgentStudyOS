import React, { useState } from 'react'
import { useLoad, saveResource, deleteResource } from '../useLoad.js'
import { Modal, Empty, DangerBtn, Pill } from '../components.jsx'
import { toast } from '../toast.js'
import { api } from '../api.js'

const EMPTY = { category: 'Python', question: '', standard_answer: '', my_answer: '', mastery: 0, is_wrong: 0, mistake_reason: '', next_review_date: '', tags: '' }

export default function Bagu() {
  const { data: list, loading, reload } = useLoad('/bago')
  const { data: categories } = useLoad('/bago/categories', [])
  const [cat, setCat] = useState('')
  const [editing, setEditing] = useState(null)
  const [openId, setOpenId] = useState(null)

  if (loading) return <div className="loading">加载中…</div>
  const rows = (list || []).filter((q) => !cat || q.category === cat)

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <select value={cat} onChange={(e) => setCat(e.target.value)} className="btn">
          <option value="">全部分类</option>
          {(categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn sm" onClick={() => api.get(cat ? `/bago/random?category=${encodeURIComponent(cat)}` : '/bago/random').then((r) => {
          if (r) { setOpenId(r.id); toast(`🎯 ${r.category} · ${r.question.slice(0, 30)}`); document.getElementById('bagu-list')?.scrollIntoView({ behavior: 'smooth' }) }
          else toast('该分类还没有题目')
        })}>🎯 随机抽一题</button>
        <div style={{ flex: 1 }} />
        <button className="btn primary" onClick={() => setEditing({ ...EMPTY })}>+ 添加题目</button>
      </div>

      <div id="bagu-list" className="grid" style={{ gap: 12 }}>
        {rows.length === 0 && <div className="card"><Empty text="这里还没有八股题" /></div>}
        {rows.map((q) => (
          <div key={q.id} className="card bagu-item" onClick={() => setOpenId(openId === q.id ? null : q.id)}>
            <div className="bq-q">
              <span>{q.question}</span>
              <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Pill text={q.category} /> <Pill text={`m${q.mastery}`} />
              </span>
            </div>
            {openId === q.id && (
              <div style={{ marginTop: 10 }}>
                {q.standard_answer && <div className="bq-ans"><strong>标准答案：</strong>{q.standard_answer}</div>}
                {q.my_answer && <div className="bq-mine"><strong>我的回答：</strong>{q.my_answer}</div>}
                {q.is_wrong && q.mistake_reason && <div style={{ color: 'var(--red)', fontSize: 13, marginTop: 8 }}>❌ 错误原因：{q.mistake_reason}</div>}
                {q.next_review_date && <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 8 }}>🔁 下次复习：{q.next_review_date}</div>}
                <div className="row-actions" style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
                  <button className="btn sm" onClick={() => setEditing({ ...q })}>编辑</button>
                  <button className="btn sm" onClick={() => {
                    const m = Math.min(5, (q.mastery || 0) + 1)
                    saveResource('/bago', { ...q, mastery: m, last_review_date: new Date().toISOString().slice(0, 10) }, q.id, reload)
                  }}>复习＋1</button>
                  <button className="btn sm" onClick={() => {
                    saveResource('/bago', { ...q, is_wrong: 1 }, q.id, reload)
                    toast('已标记为答错')
                  }}>答错</button>
                  <DangerBtn onClick={() => { if (confirm('删除这道题？')) deleteResource('/bago', q.id, reload) }} />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {editing !== null && (
        <BaguModal
          categories={categories || []}
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(payload) => saveResource('/bago', payload, editing.id, () => { reload(); setEditing(null) })}
        />
      )}
    </div>
  )
}

function BaguModal({ initial, categories, onClose, onSave }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: ['mastery', 'is_wrong'].includes(k) ? Number(e.target.value) : e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.question.trim()) return toast('问题不能为空')
    onSave({ ...f, question: f.question.trim() })
  }
  return (
    <Modal title={initial.id ? '编辑题目' : '添加八股题'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full">
            <label>问题 *</label>
            <textarea value={f.question} onChange={set('question')} placeholder="例如：解释 Redis 的缓存穿透、击穿、雪崩？" />
          </div>
          <div className="field">
            <label>分类</label>
            <select value={f.category} onChange={set('category')}>
              {(categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label>掌握程度</label>
            <select value={f.mastery} onChange={set('mastery')}>
              <option value={0}>0 · 不会</option>
              {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v} · {['', '答不上来', '会一点', '基本掌握', '较熟练', '可讲清楚'][v]}</option>)}
            </select>
          </div>
          <div className="field full">
            <label>标准答案</label>
            <textarea value={f.standard_answer} onChange={set('standard_answer')} placeholder="写下可讲的答案，面试时能说出口" />
          </div>
          <div className="field full">
            <label>我的答案</label>
            <textarea value={f.my_answer} onChange={set('my_answer')} placeholder="自己复述一遍，对比标准答案" />
          </div>
          <div className="field full">
            <label>标签（逗号分隔）</label>
            <input value={f.tags} onChange={set('tags')} placeholder="GIL, 并发" />
          </div>
          <div className="field">
            <label>是否答错</label>
            <select value={f.is_wrong} onChange={set('is_wrong')}>
              <option value={0}>否</option><option value={1}>是</option>
            </select>
          </div>
          <div className="field">
            <label>下次复习日期</label>
            <input type="date" value={f.next_review_date} onChange={set('next_review_date')} />
          </div>
          <div className="field full">
            <label>错误原因</label>
            <input value={f.mistake_reason} onChange={set('mistake_reason')} placeholder="记错 / 没答全 / 紧张…" />
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
