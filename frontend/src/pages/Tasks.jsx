import React, { useEffect, useRef, useState } from 'react'
import { useLoad, saveResource, deleteResource } from '../useLoad.js'
import { ProgressBar, Pill, Modal, Empty, DangerBtn } from '../components.jsx'
import { api } from '../api.js'
import { toast } from '../toast.js'

const EMPTY = {
  phase: '1 · 基础', category: '', title: '', description: '', resource: '',
  start_date: '', due_date: '', priority: '高', status: '待开始', progress: 0, hours: 0, note: '',
}
const PHASES = ['1 · 基础', '2 · LLM', '3 · RAG', '4 · Agent', '5 · 工程化', '6 · 实习准备']
const COURSE_PLATFORMS = ['B站', 'YouTube', 'LeetCode', 'MOOC', '文档/博客', '其他']

// 分钟 → "1.5h" / "30m"
const fmtH = (mins) => {
  if (!mins) return '0'
  if (mins < 60) return mins + 'm'
  const h = mins / 60
  return (Number.isInteger(h) ? h : h.toFixed(1)).toString().replace(/\.0$/, '') + 'h'
}
// 秒 → "mm:ss"
const fmtClock = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
// 讲解文案里的 **加粗** → <strong>
const renderGuide = (text) => text.split('**').map((s, i) => (i % 2 ? <strong key={i}>{s}</strong> : s))

export default function Tasks() {
  const { data: tasks, loading, reload } = useLoad('/tasks')
  const { data: guides } = useLoad('/phases', [])
  const [editing, setEditing] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [guideOpen, setGuideOpen] = useState({})
  const [quick, setQuick] = useState(null)     // 记一笔：{id,title}
  const [courseModal, setCourseModal] = useState(null) // 添加/编辑课程：{task, course?}
  const [seconds, setSeconds] = useState(0)    // 计时器已过秒数（驱动显示）
  const timer = useRef(null)                   // {taskId, startTs}
  const timerIv = useRef(null)

  useEffect(() => () => { if (timerIv.current) clearInterval(timerIv.current) }, [])

  if (loading) return <div className="loading">加载中…</div>
  const groups = {}
  for (const t of tasks || []) (groups[t.phase] = groups[t.phase] || []).push(t)

  const running = timer.current ? tasks?.find((t) => t.id === timer.current.taskId) : null

  // ---------- 计时器 ----------
  const startTimer = (t) => {
    if (timer.current) finishTimer()
    timer.current = { taskId: t.id, startTs: Date.now() }
    setSeconds(0)
    timerIv.current = setInterval(() => {
      if (timer.current) setSeconds(Math.floor((Date.now() - timer.current.startTs) / 1000))
    }, 1000)
    toast(`▶ 开始学习「${t.title}」`)
  }
  const finishTimer = async () => {
    if (!timer.current) return
    clearInterval(timerIv.current)
    timerIv.current = null
    const secs = Math.floor((Date.now() - timer.current.startTs) / 1000)
    const taskId = timer.current.taskId
    timer.current = null
    setSeconds(0)
    if (secs >= 30) await submitSession(taskId, Math.max(1, Math.ceil(secs / 60)), 'timer')
    else toast('学习时间太短，未记录（<30 秒）')
  }

  // ---------- 记时间 / 记一笔 ----------
  const submitSession = async (taskId, minutes, source, note = '') => {
    try {
      await api.post(`/tasks/${taskId}/sessions`, { minutes, source, note })
      reload()
      toast(`已记录 ${minutes} 分钟 ⏱`)
    } catch (e) { toast(e.message) }
  }

  // ---------- 进度：手动锁定 / 恢复自动 ----------
  const manualProgress = (t, val) => saveResource('/tasks', { manual_progress: Number(val) }, t.id, reload)
  const restoreAuto = (t) => saveResource('/tasks', { manual_progress: -1 }, t.id, reload)

  // ---------- 课程 ----------
  const coursePlus = (c) => {
    const lm = (c.learned_minutes || 0) + 30
    const prog = Math.min(100, Math.round((lm / Math.max(c.total_minutes, 1)) * 100))
    saveResource('/courses', { ...c, learned_minutes: lm, progress: prog, status: '进行中' }, c.id, reload)
  }

  return (
    <div>
      {running && (
        <div className="timer-banner" onClick={finishTimer}>
          ⏱ 正在学习「{running.title}」 <strong>{fmtClock(seconds)}</strong> · 点击结束并记录
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <button className="btn primary" onClick={() => setEditing({ ...EMPTY })}>+ 添加任务</button>
      </div>

      {Object.keys(groups).length === 0 && <Empty text="还没有任务，点击右上角添加" />}

      {Object.entries(groups).map(([phase, list]) => {
        const guide = (guides || []).find((g) => g.phase === phase)
        return (
          <div key={phase} className="phase-section">
            <div className="phase-header">
              <h2>{phase} <span className="phase-count">({list.length})</span></h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="phase-count">平均 {Math.round(list.reduce((s, t) => s + t.progress, 0) / list.length)}%</span>
                {guide && (
                  <button className="btn ghost sm" onClick={() => setGuideOpen((g) => ({ ...g, [phase]: !g[phase] }))}>
                    {guideOpen[phase] ? '收起讲解 ▲' : '阶段讲解 ▼'}
                  </button>
                )}
              </div>
            </div>

            {guide && guideOpen[phase] && (
              <div className="card guide-card">
                <div className="guide-title">📖 {guide.title}</div>
                <div className="guide-text">{renderGuide(guide.guide)}</div>
                <div className="guide-label">🎯 目标岗位（AI Agent / LLM 应用开发 实习）对此的要求</div>
                <ul className="guide-reqs">
                  {guide.job_reqs.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                <div className="guide-sources">
                  来源：
                  {guide.sources.map((s) => (
                    <a key={s.url} href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                  ))}
                </div>
              </div>
            )}

            <div className="card">
              {list.map((t) => {
                const isRunning = timer.current && timer.current.taskId === t.id
                return (
                  <div key={t.id}>
                    <div className="route-row">
                      <button className="btn ghost sm" onClick={() => setExpanded((e) => ({ ...e, [t.id]: !e[t.id] }))}>
                        {expanded[t.id] ? '▾' : '▸'}
                      </button>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13.5 }}>{t.title}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                          <Pill text={t.status} /> <Pill text={t.priority} />
                          {t.category && <span className="tag">{t.category}</span>}
                          {t.start_date && <span style={{ marginLeft: 6 }}>📅 {t.start_date} → {t.due_date}</span>}
                        </div>
                      </div>
                      <div style={{ width: 150 }}>
                        <div className="progress-label">
                          <span>进度 {t.progress}%</span>
                          <span className={`mode-tag ${t.mode}`}>{t.mode === 'manual' ? '✋ 手动' : '🔄 自动'}</span>
                        </div>
                        <input
                          type="range" min="0" max="100" step="5" value={t.progress}
                          onChange={(e) => manualProgress(t, e.target.value)}
                          style={{ width: '100%' }}
                          title="拖动会切换为手动模式（可点「恢复自动」）"
                        />
                        <div className="task-time">⏱ 已学 {fmtH(t.spent_minutes)} / 目标 {fmtH((t.hours || 0) * 60)}</div>
                      </div>
                      <div className="row-actions">
                        {isRunning ? (
                          <button className="btn primary sm" onClick={finishTimer}>⏱ {fmtClock(seconds)} 结束</button>
                        ) : (
                          <button className="btn sm" onClick={() => startTimer(t)} title="计时学习，结束后自动记时">▶ 开始</button>
                        )}
                        <button className="btn sm" onClick={() => setQuick({ id: t.id, title: t.title })}>＋记一笔</button>
                        <button className="btn sm" onClick={() => setEditing({ ...t })}>编辑</button>
                        <DangerBtn onClick={() => { if (confirm('确定删除该任务？')) deleteResource('/tasks', t.id, reload) }} />
                      </div>
                    </div>

                    {expanded[t.id] && (
                      <div className="task-detail">
                        {t.description && <div>🎯 {t.description}</div>}
                        {t.note && <div>📝 {t.note}</div>}
                        <div className="task-courses">
                          <div className="task-courses-title">📚 配套课程</div>
                          {t.courses && t.courses.length > 0 ? (
                            t.courses.map((c) => (
                              <div key={c.id} className="task-course-row">
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div className="course-name">
                                    {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.name}</a> : c.name}
                                  </div>
                                  <div className="course-meta">
                                    {[c.platform, c.teacher].filter(Boolean).join(' · ') || '—'}
                                    {c.total_minutes > 0 && ` · 共 ${c.total_minutes} 分钟`}
                                  </div>
                                </div>
                                <div style={{ width: 90 }}><ProgressBar value={c.progress} sm /></div>
                                <button className="btn sm" onClick={() => coursePlus(c)}>＋30分</button>
                                <button className="btn sm" onClick={() => setCourseModal({ task: t, course: c })}>编辑</button>
                              </div>
                            ))
                          ) : (
                            <div className="task-no-course">
                              ⚠️ 暂无配套课程，加一个就能在路线里直接学
                              <button className="btn primary sm" onClick={() => setCourseModal({ task: t, course: null })}>＋ 添加课程</button>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {editing !== null && (
        <TaskModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(payload) => saveResource('/tasks', payload, editing.id, () => { reload(); setEditing(null) })}
        />
      )}

      {quick && (
        <QuickModal
          title={quick.title}
          onClose={() => setQuick(null)}
          onSave={async (minutes, note) => { await submitSession(quick.id, minutes, 'quick', note); setQuick(null) }}
        />
      )}

      {courseModal && (
        <CourseMiniModal
          task={courseModal.task}
          course={courseModal.course}
          onClose={() => setCourseModal(null)}
          onSaved={() => { reload(); setCourseModal(null) }}
        />
      )}
    </div>
  )
}

// ---------- 任务编辑弹窗（沿用原逻辑） ----------
function TaskModal({ initial, onClose, onSave }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.title.trim()) return toast('任务名不能为空')
    onSave({ ...f, title: f.title.trim(), progress: Number(f.progress) || 0, hours: Number(f.hours) || 0 })
  }
  return (
    <Modal title={initial.id ? '编辑任务' : '添加任务'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full">
            <label>任务名 *</label>
            <input value={f.title} onChange={set('title')} placeholder="例如：文档解析 / Chunk / Embedding" />
          </div>
          <div className="field">
            <label>阶段</label>
            <select value={f.phase} onChange={set('phase')}>
              {PHASES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label>分类</label>
            <input value={f.category} onChange={set('category')} placeholder="编程 / 工程 / 后端 / RAG…" />
          </div>
          <div className="field">
            <label>优先级</label>
            <select value={f.priority} onChange={set('priority')}>
              <option>高</option><option>中</option><option>低</option>
            </select>
          </div>
          <div className="field">
            <label>状态</label>
            <select value={f.status} onChange={set('status')}>
              <option>待开始</option><option>进行中</option><option>已完成</option><option>已延期</option>
            </select>
          </div>
          <div className="field">
            <label>开始日期</label>
            <input type="date" value={f.start_date} onChange={set('start_date')} />
          </div>
          <div className="field">
            <label>截止日期</label>
            <input type="date" value={f.due_date} onChange={set('due_date')} />
          </div>
          <div className="field">
            <label>目标小时数</label>
            <input type="number" min="0" value={f.hours} onChange={set('hours')} placeholder="自动进度按此计算" />
          </div>
          <div className="field">
            <label>进度（0~100）</label>
            <input type="number" min="0" max="100" value={f.progress} onChange={set('progress')} />
          </div>
          <div className="field full">
            <label>目标产出 / 说明</label>
            <textarea value={f.description} onChange={set('description')} />
          </div>
          <div className="field full">
            <label>参考资源 / 备注</label>
            <input value={f.resource} onChange={set('resource')} placeholder="链接或资料" />
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

// ---------- 记一笔弹窗 ----------
function QuickModal({ title, onClose, onSave }) {
  const [minutes, setMinutes] = useState(30)
  const [note, setNote] = useState('')
  return (
    <Modal title={`记一笔 · ${title}`} onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); if (!(minutes >= 1)) return toast('分钟数至少 1'); onSave(minutes, note.trim()) }}>
        <div className="form-grid">
          <div className="field">
            <label>学习分钟数 *</label>
            <input type="number" min="1" max="999" value={minutes} onChange={(e) => setMinutes(Number(e.target.value) || 0)} />
          </div>
          <div className="field">
            <label>备注（可选）</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="学到哪了 / 看了什么" />
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>取消</button>
          <button type="submit" className="btn primary">记录</button>
        </div>
      </form>
    </Modal>
  )
}

// ---------- 添加/编辑课程弹窗（挂在任务下） ----------
function CourseMiniModal({ task, course, onClose, onSaved }) {
  const [f, setF] = useState(course ? { ...course } : { name: '', platform: 'B站', url: '', status: '待开始' })
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault()
    if (!f.name.trim()) return toast('课程名不能为空')
    try {
      const payload = { ...f, name: f.name.trim(), task_id: task.id }
      if (course) await api.put(`/courses/${course.id}`, payload)
      else await api.post('/courses', payload)
      toast('已保存')
      onSaved()
    } catch (err) { toast(err.message) }
  }
  return (
    <Modal title={course ? '编辑课程' : `添加课程 · ${task.title}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full">
            <label>课程名称 *</label>
            <input value={f.name} onChange={set('name')} placeholder="课程 / 视频 / 文档标题" />
          </div>
          <div className="field">
            <label>平台</label>
            <select value={f.platform} onChange={set('platform')}>
              {COURSE_PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label>状态</label>
            <select value={f.status} onChange={set('status')}>
              <option>待开始</option><option>进行中</option><option>已完成</option>
            </select>
          </div>
          <div className="field full">
            <label>链接</label>
            <input value={f.url} onChange={set('url')} placeholder="https://…" />
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
