import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Empty } from '../components.jsx'

// Phase 5 · Agent Trace 回放：把一次 Agent 运行回放成一屏可截图、可对面试讲清楚的时间轴。

const STATUS_LABEL = { running: '运行中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
const STATUS_STYLE = {
  running: { background: '#1e88e5' },
  succeeded: { background: '#2e9e5b' },
  failed: { background: '#e5484d' },
  cancelled: { background: '#8b8b96' },
}

const LABELS = {
  observe: '观察', plan: '规划', tool: '工具',
  plan_compare: '计划对比', user_memories: '记忆',
  reflect: '复盘', replan: '重规划', error: '错误', finish: 'Finish',
}
const ICONS = {
  observe: '🔭', plan: '💭', tool: '🛠️',
  plan_compare: '📊', user_memories: '🧠',
  reflect: '🔄', replan: '🔁', error: '⚠️', finish: '🏁',
}
const TONE = {
  observe: 't-observe', plan: 't-plan', tool: 't-tool',
  plan_compare: 't-feedback', user_memories: 't-memory',
  reflect: 't-reflect', replan: 't-replan', error: 't-error', finish: 't-finish',
}

const json = (o) => {
  try { return JSON.stringify(o ?? {}, null, 2) } catch { return String(o) }
}
const short = (o, n = 70) => {
  const s = json(o).replace(/\s+/g, ' ').trim()
  return s.length > n ? s.slice(0, n) + '…' : s
}
const fmtDur = (ms) => {
  if (!isFinite(ms) || ms < 0) return '—'
  const s = Math.round(ms / 1000)
  if (s < 1) return '1s'
  if (s < 60) return s + 's'
  return Math.floor(s / 60) + 'm ' + (s % 60) + 's'
}
const timeOf = (t) => (t || '').slice(11, 16)

// ---------- 时间轴行构建 ----------

function eventRow(e) {
  const c = e.content || {}
  const base = {
    key: e.seq, time: timeOf(e.created_at),
    tone: TONE[e.event_type] || '', icon: ICONS[e.event_type] || '📄',
    typeLabel: LABELS[e.event_type] || e.event_type,
  }
  switch (e.event_type) {
    case 'observe':
      return { ...base, title: <>观察 · <b>{c.tool}()</b></>, detail: <pre>{json(c.result)}</pre> }
    case 'plan': {
      const p = c.plan || {}
      const steps = Array.isArray(p.steps) ? p.steps : []
      return {
        ...base,
        title: <>{p.goal || '制定计划'}</>,
        detail: (
          <>
            {p.reasoning_summary && <div className="trace-reasoning">💡 {p.reasoning_summary}</div>}
            {steps.length > 0 && (
              <ol className="trace-steps-list">
                {steps.map((s, i) => (
                  <li key={i}><b>{s.tool}()</b> {short(s.arguments, 140)}</li>
                ))}
              </ol>
            )}
          </>
        ),
      }
    }
    case 'reflect': {
      const r = c.reflection || {}
      const goalTxt = r.goal_completed ? '目标已达成' : '目标未完成'
      const planTxt = r.need_replan ? '需要重规划' : '计划有效'
      return {
        ...base,
        title: <>{goalTxt} · {planTxt}</>,
        detail: (
          <>
            <div className="trace-kv"><span>目标完成</span><b>{r.goal_completed ? '是' : '否'}</b></div>
            <div className="trace-kv"><span>需要重规划</span><b>{r.need_replan ? '是' : '否'}</b></div>
            {r.reason && <div className="trace-kv"><span>原因</span><span>{r.reason}</span></div>}
            {r.next_action && <div className="trace-kv"><span>下一步</span><span>{r.next_action}</span></div>}
          </>
        ),
      }
    }
    case 'plan_compare':
      return {
        ...base,
        title: <>对比 {c.plan_date}：计划 {c.planned_total} / 实际 {c.actual_total} 分钟（{c.deviation_pct}%）</>,
        detail: (
          <>
            <div className="trace-kv"><span>计划分钟</span><b>{c.planned_total}</b></div>
            <div className="trace-kv"><span>实际分钟</span><b>{c.actual_total}</b></div>
            <div className="trace-kv"><span>偏差</span><b>{c.deviation_pct}</b></div>
            {c.verdict && <div className="trace-kv"><span>结论</span><b>{c.verdict}</b></div>}
          </>
        ),
      }
    case 'user_memories': {
      const keys = c.mkeys || []
      return {
        ...base,
        title: <>注入 {c.count} 条用户记忆{keys.length ? `（${keys.join('、')}）` : ''}</>,
        detail: keys.length ? <ul className="trace-keys">{keys.map((k) => <li key={k}>{k}</li>)}</ul> : null,
      }
    }
    case 'replan':
      return { ...base, title: c.reason || '重新规划' }
    case 'error':
      return { ...base, title: c.message || '错误' }
    default:
      return { ...base, title: short(c) }
  }
}

// tool_call + tool_result 合并为一行（executor 总是成对写，合并后「工具数 = 行数」，截图清爽）
function toolRow(call, res) {
  const callC = (call && call.content) || {}
  const resC = (res && res.content) || {}
  const ok = res ? !!resC.ok : null
  const tool = callC.tool || resC.tool || ''
  const statusTxt = ok === null ? '无结果' : ok ? '✅' : '⚠️ 失败'
  const preview = ok === false ? (resC.result?.error || '') : resC.result !== undefined ? short(resC.result) : short(callC.args)
  return {
    key: call ? call.seq : res.seq,
    time: timeOf(call ? call.created_at : res.created_at),
    tone: ok === false ? 't-error' : 't-tool',
    icon: ok === false ? '⚠️' : '🛠️',
    typeLabel: '工具',
    title: (
      <>
        <b>{tool}()</b>
        <span className="trace-result">{statusTxt}</span>
        {resC.cached && <span className="muted">(缓存)</span>}
        {preview && <span className="muted trace-preview">{preview}</span>}
      </>
    ),
    detail: (
      <>
        {callC.args !== undefined && (
          <div><div className="trace-label">参数</div><pre>{json(callC.args)}</pre></div>
        )}
        {resC.result !== undefined && (
          <div><div className="trace-label">结果</div><pre>{json(resC.result)}</pre></div>
        )}
      </>
    ),
  }
}

function finishRow(run, n) {
  return {
    key: 900000 + n,
    time: timeOf(run.finished_at),
    tone: 't-finish',
    icon: '🏁',
    typeLabel: 'Finish',
    title: `完成 · ${STATUS_LABEL[run.status] || run.status} · 共 ${n} 步`,
    detail: null,
  }
}

function buildRows(events, run) {
  const rows = []
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.event_type === 'tool_call') {
      const next = events[i + 1]
      if (next && next.event_type === 'tool_result' && next.content.tool === e.content.tool) {
        rows.push(toolRow(e, next)); i++
      } else {
        rows.push(toolRow(e, null))
      }
      continue
    }
    if (e.event_type === 'tool_result') { rows.push(toolRow(null, e)); continue }
    rows.push(eventRow(e))
  }
  // 合成 Finish 行（trace 里没有 finish 事件，由运行状态 + finished_at 得出）
  if (run.finished_at && STATUS_LABEL[run.status]) rows.push(finishRow(run, rows.length))
  return rows
}

// ---------- 子组件 ----------

function TraceHeader({ run }) {
  return (
    <div className="trace-header">
      <div className="trace-title-row">
        <h3>Agent Run <span className="trace-id">#{run.id ?? run.run_id.slice(0, 6)}</span></h3>
        <span className="badge" style={STATUS_STYLE[run.status] || {}}>{STATUS_LABEL[run.status] || run.status}</span>
      </div>
      <div className="trace-goal">🎯 {run.goal}</div>
      {run.error && <div className="run-error">⚠️ {run.error}</div>}
    </div>
  )
}

function TraceStats({ run, events }) {
  const dur = run.finished_at
    ? fmtDur(new Date(run.finished_at) - new Date(run.started_at))
    : '运行中'
  const tools = events.filter((e) => e.event_type === 'tool_call').length
  const u = run.token_usage || {}
  const tokens = u.total_tokens ?? '—'
  const cost = u.cost_cny
  return (
    <div className="stat-grid">
      <div className="stat-chip"><span>⏱ 耗时</span><b>{dur}</b></div>
      <div className="stat-chip">
        <span>🔢 Token</span>
        <b>{tokens}</b>
        {u.input_tokens !== undefined && (
          <span style={{ fontSize: 11 }}>入 {u.input_tokens} / 出 {u.output_tokens}</span>
        )}
      </div>
      <div className="stat-chip">
        <span>💰 成本（估算）</span>
        <b>{cost === undefined ? '—' : '¥' + Number(cost).toFixed(4)}</b>
        {u.price_known === false && <span style={{ fontSize: 11 }}>单价未收录</span>}
      </div>
      <div className="stat-chip"><span>🔄 迭代</span><b>{run.iteration}</b></div>
      <div className="stat-chip"><span>🛠️ 工具调用</span><b>{tools}</b></div>
      <div className="stat-chip">
        <span>📡 LLM 调用</span>
        <b>{u.llm_calls ?? '—'}</b>
        {u.latency_ms > 0 && <span style={{ fontSize: 11 }}>{(u.latency_ms / 1000).toFixed(1)} 秒</span>}
      </div>
    </div>
  )
}

function TraceTimeline({ run, events }) {
  const rows = buildRows(events, run)
  if (rows.length === 0) return <Empty text="该运行没有留下时间轴事件" />
  return (
    <div className="trace-steps">
      {rows.map((row) => (
        <details key={row.key} className={`trace-step ${row.tone}`}>
          <summary>
            <span className="trace-dot" />
            <span className="trace-time">{row.time}</span>
            <span className="trace-icon">{row.icon}</span>
            <span className="trace-type">{row.typeLabel}</span>
            <span className="trace-title">{row.title}</span>
          </summary>
          {row.detail && <div className="trace-detail">{row.detail}</div>}
        </details>
      ))}
    </div>
  )
}

// ---------- 主组件 ----------

export default function Trace() {
  const [runs, setRuns] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const refreshRuns = () => api.get('/agent/runs').then((d) => setRuns(d.runs || [])).catch(() => {})

  // 挂载：拉运行历史，默认选中最新一条
  useEffect(() => {
    let alive = true
    api.get('/agent/runs').then((d) => {
      if (!alive) return
      const list = d.runs || []
      setRuns(list)
      if (list.length) setSelectedId((prev) => prev || list[0].run_id)
    }).catch(() => {})
    return () => { alive = false }
  }, [])

  // 选中变化：拉详情；运行中每 2s 轮询，完成后停轮询并刷新列表状态
  useEffect(() => {
    if (!selectedId) return
    let alive = true
    setLoading(true)
    const fetchOnce = async () => {
      try {
        const d = await api.get('/agent/run/' + selectedId)
        if (!alive) return
        setRun(d); setErr(''); setLoading(false)
        if (d.status !== 'running') refreshRuns()
      } catch (e) {
        if (!alive) return
        setErr(e.message || '加载失败'); setLoading(false)
      }
    }
    fetchOnce()
    const timer = setInterval(() => {
      if (!alive) return
      api.get('/agent/run/' + selectedId).then((d) => {
        if (!alive) return
        setRun(d); setErr('')
        if (d.status !== 'running') { clearInterval(timer); refreshRuns() }
      }).catch(() => {})
    }, 2000)
    return () => { alive = false; clearInterval(timer) }
  }, [selectedId])

  return (
    <div className="trace-page">
      <div className="trace-layout">
        <aside className="card trace-sidebar">
          <h3 className="trace-sidebar-title">🗂 运行历史</h3>
          {runs.length === 0 ? (
            <Empty text="还没有 Agent 运行记录，先去「🤖 Agent」页跑一次" />
          ) : (
            <div className="run-list">
              {runs.map((r) => (
                <button
                  key={r.run_id}
                  className={`run-item${r.run_id === selectedId ? ' active' : ''}`}
                  onClick={() => setSelectedId(r.run_id)}
                >
                  <span className="status-dot" style={STATUS_STYLE[r.status] || {}} />
                  <span className="run-id">#{r.id ?? r.run_id.slice(0, 6)}</span>
                  <span className="run-goal">{r.goal}</span>
                  <span className="muted run-time">{r.started_at ? r.started_at.slice(5, 16).replace('T', ' ') : ''}</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="card trace-detail-card">
          {!run && !err && !loading && <Empty text="从左侧选择一次运行，开始回放" />}
          {err && <div className="run-error">⚠️ 加载失败：{err}</div>}
          {loading && <div className="loading">正在加载运行轨迹…</div>}
          {run && (
            <>
              <TraceHeader run={run} />
              <TraceStats run={run} events={run.trace_events || []} />
              <TraceTimeline run={run} events={run.trace_events || []} />
              {run.final_reply && (
                <div className="final-reply"><span className="final-icon">🎯</span><pre>{run.final_reply}</pre></div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  )
}
