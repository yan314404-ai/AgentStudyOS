import React, { useState } from 'react'
import { useLoad, saveResource, deleteResource } from '../useLoad.js'
import { ProgressBar, Pill, Modal, Empty, DangerBtn } from '../components.jsx'
import { toast } from '../toast.js'

const EMPTY_PROJECT = {
  name: '', goal: '', background: '', core_features: '', tech_stack: '', github: '', demo: '',
  version: 'V1', progress: 0, current_phase: '', next_step: '', risks: '', interview_points: '',
}
const EMPTY_MILESTONE = { name: '', status: '待开始', progress: 0, planned_time: '', actual_time: '', start_date: '', end_date: '', note: '' }

export default function Projects() {
  const { data: list, loading, reload } = useLoad('/projects')
  const [editing, setEditing] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [msForm, setMsForm] = useState(null) // 正在添加里程碑的项目 id

  if (loading) return <div className="loading">加载中…</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <button className="btn primary" onClick={() => setEditing({ ...EMPTY_PROJECT })}>+ 新项目</button>
      </div>

      <div className="grid grid-2">
        {(!list || list.length === 0) && <div className="card"><Empty text="还没有项目" /></div>}
        {list.map((p) => (
          <div key={p.id} className="card">
            <div className="project-header">
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <Pill text={p.status || '待开始'} />
                <button className="btn sm" onClick={() => setEditing({ ...p })}>编辑</button>
                <DangerBtn onClick={() => { if (confirm('删除项目会同时删除它的里程碑，确定？')) deleteResource('/projects', p.id, reload) }} />
              </div>
            </div>
            {p.goal && <div className="muted" style={{ marginTop: 4 }}>🎯 {p.goal}</div>}
            <div className="progress-label" style={{ marginTop: 12 }}><span>整体进度</span><span>{p.progress}%</span></div>
            <ProgressBar value={p.progress} />
            <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {p.tech_stack && <span className="tag">{p.tech_stack}</span>}
              {p.github && <a href={p.github} target="_blank" rel="noreferrer">GitHub</a>}
              {p.demo && <a href={p.demo} target="_blank" rel="noreferrer">Demo</a>}
            </div>
            {p.next_step && <div style={{ marginTop: 8, fontSize: 13 }}>▶️ 下一步：{p.next_step}</div>}
            {p.interview_points && <div style={{ marginTop: 4, fontSize: 12, color: 'var(--purple)' }}>💡 面试可讲：{p.interview_points}</div>}

            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <strong style={{ fontSize: 13 }}>里程碑</strong>
                <button className="btn sm" onClick={() => setMsForm(p.id)}>+ 里程碑</button>
              </div>
              {p.milestones?.length === 0 && <div className="muted" style={{ fontSize: 12 }}>暂无里程碑</div>}
              {p.milestones?.map((m) => (
                <div key={m.id} className="milestone">
                  <Pill text={m.status} />
                  <div className="ms-name">{m.name}</div>
                  <div style={{ width: 60 }}><ProgressBar value={m.progress} sm /></div>
                  <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{m.progress}%</span>
                  <button className="btn ghost sm" onClick={() => {
                    const prog = Math.min(100, (m.progress || 0) + 25)
                    saveResource('/projects/milestones', { ...m, progress: prog, status: prog >= 100 ? '已完成' : '进行中' }, m.id, reload)
                  }}>推进</button>
                  <DangerBtn onClick={() => { if (confirm('删除里程碑？')) deleteResource('/projects/milestones', m.id, reload) }} />
                </div>
              ))}
            </div>

            <button className="btn sm" style={{ marginTop: 10 }} onClick={() => setExpanded((e) => ({ ...e, [p.id]: !e[p.id] }))}>
              {expanded[p.id] ? '收起详细资料 ▴' : '展开详细资料 ▾'}
            </button>
            {expanded[p.id] && (
              <div style={{ marginTop: 10, fontSize: 13, color: 'var(--text-2)', display: 'grid', gap: 6 }}>
                {p.background && <div><strong>背景：</strong>{p.background}</div>}
                {p.core_features && <div><strong>核心功能：</strong>{p.core_features}</div>}
                {p.current_phase && <div><strong>当前阶段：</strong>{p.current_phase}</div>}
                {p.risks && <div><strong>风险：</strong>{p.risks}</div>}
                {p.problems && <div><strong>遇到的问题：</strong>{p.problems}</div>}
                {p.solutions && <div><strong>解决方案：</strong>{p.solutions}</div>}
                {p.metrics && <div><strong>指标：</strong>{p.metrics}</div>}
              </div>
            )}
          </div>
        ))}
      </div>

      {editing !== null && (
        <ProjectModal initial={editing} onClose={() => setEditing(null)}
          onSave={(p) => saveResource('/projects', p, editing.id, () => { reload(); setEditing(null) })} />
      )}
      {msForm !== null && (
        <Modal title="添加里程碑" onClose={() => setMsForm(null)}>
          <MilestoneForm pid={msForm} onClose={() => setMsForm(null)} onDone={() => { reload(); setMsForm(null) }} />
        </Modal>
      )}
    </div>
  )
}

function ProjectModal({ initial, onClose, onSave }) {
  const [f, setF] = useState(initial)
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.name.trim()) return toast('项目名不能为空')
    onSave({ ...f, name: f.name.trim(), progress: Number(f.progress) || 0 })
  }
  return (
    <Modal title={initial.id ? '编辑项目' : '新项目'} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="field full"><label>项目名称 *</label><input value={f.name} onChange={set('name')} placeholder="例如：Research Agent" /></div>
          <div className="field full"><label>项目目标</label><input value={f.goal} onChange={set('goal')} placeholder="做成一个能拿出手、能被面试追问的 Demo" /></div>
          <div className="field full"><label>项目背景</label><textarea value={f.background} onChange={set('background')} /></div>
          <div className="field full"><label>核心功能</label><input value={f.core_features} onChange={set('core_features')} /></div>
          <div className="field full"><label>技术栈</label><input value={f.tech_stack} onChange={set('tech_stack')} placeholder="LangGraph / FastAPI / Redis…" /></div>
          <div className="field"><label>GitHub 链接</label><input value={f.github} onChange={set('github')} /></div>
          <div className="field"><label>Demo 链接</label><input value={f.demo} onChange={set('demo')} /></div>
          <div className="field"><label>版本</label><input value={f.version} onChange={set('version')} /></div>
          <div className="field"><label>整体进度（0~100）</label><input type="number" min="0" max="100" value={f.progress} onChange={set('progress')} /></div>
          <div className="field"><label>当前阶段</label><input value={f.current_phase} onChange={set('current_phase')} placeholder="M2 Tool Calling" /></div>
          <div className="field full"><label>下一步</label><input value={f.next_step} onChange={set('next_step')} /></div>
          <div className="field full"><label>风险</label><input value={f.risks} onChange={set('risks')} /></div>
          <div className="field full"><label>面试可讲点</label><textarea value={f.interview_points} onChange={set('interview_points')} placeholder="这个项目能体现你哪些能力" /></div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>取消</button>
          <button type="submit" className="btn primary">保存</button>
        </div>
      </form>
    </Modal>
  )
}

function MilestoneForm({ pid, onClose, onDone }) {
  const [f, setF] = useState({ ...EMPTY_MILESTONE })
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const submit = (e) => {
    e.preventDefault()
    if (!f.name.trim()) return toast('里程碑名不能为空')
    saveResource(`/projects/${pid}/milestones`, { ...f, name: f.name.trim() }, null, onDone)
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <div className="field full"><label>里程碑名称 *</label><input value={f.name} onChange={set('name')} placeholder="V2 · BM25 + Hybrid + Rerank" /></div>
        <div className="field"><label>状态</label><select value={f.status} onChange={set('status')}><option>待开始</option><option>进行中</option><option>已完成</option></select></div>
        <div className="field"><label>进度（0~100）</label><input type="number" min="0" max="100" value={f.progress} onChange={set('progress')} /></div>
        <div className="field"><label>开始日期</label><input type="date" value={f.start_date} onChange={set('start_date')} /></div>
        <div className="field"><label>截止日期</label><input type="date" value={f.end_date} onChange={set('end_date')} /></div>
        <div className="field"><label>预计时间</label><input value={f.planned_time} onChange={set('planned_time')} placeholder="如 2 周" /></div>
        <div className="field"><label>实际时间</label><input value={f.actual_time} onChange={set('actual_time')} /></div>
        <div className="field full"><label>备注</label><input value={f.note} onChange={set('note')} /></div>
      </div>
      <div className="modal-actions">
        <button type="button" className="btn" onClick={onClose}>取消</button>
        <button type="submit" className="btn primary">添加</button>
      </div>
    </form>
  )
}
