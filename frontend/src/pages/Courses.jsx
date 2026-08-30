import React, { useState } from 'react'
import { useLoad, saveResource, deleteResource } from '../useLoad.js'
import { ProgressBar, Pill, Modal, Empty, DangerBtn } from '../components.jsx'
import { toast } from '../toast.js'

const EMPTY = { name: '', phase: '', platform: 'B站', url: '', teacher: '', total_minutes: 0, learned_minutes: 0, progress: 0, status: '待开始', rating: 0, review: '', note: '', next_to_watch: '' }

export default function Courses() {
  const { data: list, loading, reload } = useLoad('/courses')
  const { data: tasks } = useLoad('/tasks', [])
  const [editing, setEditing] = useState(null)

  const taskName = (tid) => {
    const t = (tasks || []).find((x) => x.id === tid)
    return t ? `${t.phase} · ${t.title}` : ''
  }

  if (loading) return <div className="loading">加载中…</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <button className="btn primary" onClick={() => setEditing({ ...EMPTY })}>+ 添加课程/资料</button>
      </div>
      <div className="grid grid-3">
        {(!list || list.length === 0) && <div className="card"><Empty text="还没有课程" /></div>}
        {list.map((c) => (
          <div key={c.id} className="card course-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <div className="course-name">
                {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.name}</a> : c.name}
              </div>
              <Pill text={c.status} />
            </div>
            <div className="course-meta">
              {[c.platform, c.phase, c.teacher].filter(Boolean).join(' · ') || '—'}
              {c.total_minutes > 0 && ` · 共 ${c.total_minutes} 分钟`}
            </div>
            {c.task_id && taskName(c.task_id) && (
              <div className="course-task-link" onClick={() => { window.location.hash = '#/tasks' }}>
                📍 {taskName(c.task_id)}
              </div>
            )}
            <div className="progress-label"><span>进度 {c.progress}%</span><span>{c.learned_minutes || 0} 分钟</span></div>
            <ProgressBar value={c.progress} color={c.status === '进行中' ? 'blue' : ''} />
            {c.review && <div style={{ fontSize: 12, color: 'var(--text-2)' }}>⭐ {c.review}</div>}
            {c.next_to_watch && <div style={{ fontSize: 12, color: 'var(--text-3)' }}>下一节：{c.next_to_watch}</div>}
            <div className="row-actions" style={{ marginTop: 6 }}>
              <button className="btn sm" onClick={() => setEditing({ ...c })}>编辑</button>
              <button className="btn sm" onClick={() => {
                const lm = (c.learned_minutes || 0) + 30
                const prog = Math.min(100, Math.round((lm / Math.max(c.total_minutes, 1)) * 100))
                saveResource('/courses', { ...c, learned_minutes: lm, progress: prog, status: '进行中' }, c.id, reload)
              }}>＋30 分钟</button>
              <DangerBtn onClick={() => { if (confirm('删除该课程？')) deleteResource('/courses', c.id, reload) }} />
            </div>
          </div>
        ))}
      </div>

      {editing !== null && (
        <CourseModal initial={editing} tasks={tasks || []} onClose={() => setEditing(null)}
          onSave={(p) => saveResource('/courses', p, editing.id, () => { reload(); setEditing(null) })} />
      )}
    </div>
  )
}

function CourseModal({ initial, tasks, onClose, onSave }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: ['total_minutes', 'learned_minutes', 'progress', 'rating'].includes(k) ? Number(e.target.value) : e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.name.trim()) return toast('课程名不能为空')
    onSave({ ...f, name: f.name.trim(), total_minutes: Number(f.total_minutes) || 0, learned_minutes: Number(f.learned_minutes) || 0, progress: Number(f.progress) || 0 })
  }
  return (
    <Modal title={initial.id ? '编辑课程' : '添加课程'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full">
            <label>课程名称 *</label>
            <input value={f.name} onChange={set('name')} placeholder="例如：LangChain + RAG + Agent + LangGraph" />
          </div>
          <div className="field">
            <label>平台</label>
            <input value={f.platform} onChange={set('platform')} placeholder="B站 / LeetCode / YouTube…" />
          </div>
          <div className="field">
            <label>归属任务</label>
            <select
              value={f.task_id || ''}
              onChange={(e) => setF((s) => ({ ...s, task_id: e.target.value ? Number(e.target.value) : '' }))}
            >
              <option value="">不归属（独立课程）</option>
              {(tasks || []).map((t) => (
                <option key={t.id} value={t.id}>{t.phase} · {t.title}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>阶段 / 主题</label>
            <input value={f.phase} onChange={set('phase')} placeholder="Python / RAG / Agent / 面试…" />
          </div>
          <div className="field full">
            <label>链接</label>
            <input value={f.url} onChange={set('url')} placeholder="https://…" />
          </div>
          <div className="field">
            <label>老师 / UP 主</label>
            <input value={f.teacher} onChange={set('teacher')} />
          </div>
          <div className="field">
            <label>状态</label>
            <select value={f.status} onChange={set('status')}>
              <option>待开始</option><option>进行中</option><option>已完成</option>
            </select>
          </div>
          <div className="field">
            <label>总时长（分钟）</label>
            <input type="number" min="0" value={f.total_minutes} onChange={set('total_minutes')} />
          </div>
          <div className="field">
            <label>已学时长（分钟）</label>
            <input type="number" min="0" value={f.learned_minutes} onChange={set('learned_minutes')} />
          </div>
          <div className="field">
            <label>进度（0~100）</label>
            <input type="number" min="0" max="100" value={f.progress} onChange={set('progress')} />
          </div>
          <div className="field">
            <label>推荐度（1~5）</label>
            <select value={f.rating} onChange={set('rating')}>
              <option value={0}>未评</option>{[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v} 星</option>)}
            </select>
          </div>
          <div className="field full">
            <label>用途 / 备注</label>
            <textarea value={f.note} onChange={set('note')} placeholder="这门课要重点学什么" />
          </div>
          <div className="field full">
            <label>下一节准备看什么</label>
            <input value={f.next_to_watch} onChange={set('next_to_watch')} />
          </div>
          <div className="field full">
            <label>我的评价</label>
            <textarea value={f.review} onChange={set('review')} />
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
