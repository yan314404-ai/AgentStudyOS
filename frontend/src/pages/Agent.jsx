import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'
import { Empty } from '../components.jsx'

const STATUS_LABEL = { running: '运行中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
const STATUS_STYLE = {
  running: { background: '#1e88e5' },
  succeeded: { background: '#2e9e5b' },
  failed: { background: '#e5484d' },
  cancelled: { background: '#8b8b96' },
}

const short = (o, n = 220) => {
  let s
  try { s = JSON.stringify(o) } catch { s = String(o) }
  return s && s.length > n ? s.slice(0, n) + '…' : s
}

const PLAN_BADGE = {
  active: { text: '生效中', cls: 'badge plan-badge-active' },
  pending: { text: '待确认', cls: 'badge plan-badge-pending' },
  reviewed: { text: '已复盘', cls: 'badge plan-badge-reviewed' },
}
const VERDICT_LABEL = { over: '计划过量', under: '计划不足', ok: '执行合理' }
// 把调整项里的 item_id 翻译成任务名。原来直接显示「计划项 #4」，
// 用户看不懂这个内部 id；查不到（比如该项已被移除）才回退到 id。
const itemTitle = (items, itemId) => {
  const hit = (items || []).find((it) => it.id === itemId)
  return hit ? `「${hit.title}」` : ` #${itemId}`
}
const adjustLabel = (a, items) => {
  switch (a.action) {
    case 'adjust': return `调整${itemTitle(items, a.item_id)}预期为 ${a.expected_minutes} 分钟`
    case 'remove': return `移除${itemTitle(items, a.item_id)}`
    case 'add': return `新增任务「${a.title}」${a.expected_minutes} 分钟`
    case 'next_plan': return `生成 ${a.plan_date} 的新计划（${a.items ? a.items.length : 0} 项）`
    default: return short(a)
  }
}

const PlanItem = ({ it }) => {
  const pct = it.expected_minutes > 0
    ? Math.min(100, Math.round((it.actual_minutes / it.expected_minutes) * 100))
    : (it.actual_minutes > 0 ? 100 : 0)
  const over = it.actual_minutes > it.expected_minutes
  return (
    <div className="plan-item">
      <div className="plan-item-top">
        <span className="plan-item-title">{it.title}</span>
        <span className="plan-item-right">
          {it.suggested_time && <span className="plan-slot">⏰ {it.suggested_time}</span>}
          <span className={`plan-item-min${over ? ' over' : ''}`}>{it.actual_minutes} / {it.expected_minutes} 分钟</span>
        </span>
      </div>
      <div className="progress-track sm">
        <div className={`progress-fill ${over ? 'blue' : 'purple'}`} style={{ width: pct + '%' }} />
      </div>
    </div>
  )
}

const MTYPE_LABEL = { preference: '偏好', fact: '事实', goal: '目标', rule: '规则' }
const MEM_STATUS = {
  pending: { text: '待确认', cls: 'memory-badge memory-badge-pending' },
  active: { text: '已生效', cls: 'memory-badge memory-badge-active' },
}

// Phase 5 意图识别（纯规则，零成本）：输入框里实时显示「这句话会被当成什么」，
// 避免用户以为自己在查询、Agent 却按「安排计划」去写库。
const INTENT_LABEL = {
  plan: '安排计划', review: '复盘计划', record: '记录学习',
  remember: '记住偏好', forget: '忘掉记忆', query: '查询状态', chat: '一般对话',
}
const INTENT_COLOR = {
  plan: '#3b82f6', review: '#8b5cf6', record: '#10b981',
  remember: '#f59e0b', forget: '#ef4444', query: '#06b6d4', chat: '#94a3b8',
}
const SLOT_LABEL = {
  date: '日期', minutes: '时长', task_id: '任务', log_date: '记录日期',
  plan_date: '计划日期', content: '内容', key: '关键词',
}

export default function Agent() {
  const [profile, setProfile] = useState({ goal: '', available_time: 3 })
  const [configured, setConfigured] = useState(true)
  const [runs, setRuns] = useState([])
  const [run, setRun] = useState(null)
  const [actions, setActions] = useState([])
  const [plans, setPlans] = useState([])
  const [memories, setMemories] = useState([])
  const [reminder, setReminder] = useState({ needs_review: false, message: '' })
  const [polling, setPolling] = useState(false)
  const [starting, setStarting] = useState(false)
  const [intent, setIntent] = useState(null)
  const pollRef = useRef(null)
  const intentTimer = useRef(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    setPolling(false)
  }

  const loadActions = async (id) => {
    try {
      const d = await api.get('/agent/run/' + id + '/actions')
      setActions(d.actions || [])
    } catch { setActions([]) }
  }

  const loadRun = async (id) => {
    try {
      const d = await api.get('/agent/run/' + id)
      setRun(d)
      if (d.status !== 'running') { stopPolling(); loadRuns(); loadActions(id); loadPlans(); loadReminder(); loadMemories() }
    } catch { stopPolling() }
  }

  const startPolling = (id) => {
    stopPolling()
    setPolling(true)
    loadRun(id)
    pollRef.current = setInterval(() => loadRun(id), 1500)
  }

  const loadRuns = () => api.get('/agent/runs').then((d) => setRuns(d.runs || [])).catch(() => {})
  const loadPlans = () => api.get('/agent/plans').then((d) => setPlans(d.plans || [])).catch(() => {})
  const loadMemories = () => api.get('/agent/memories').then((d) => setMemories(d.memories || [])).catch(() => {})
  const loadReminder = () => api.get('/agent/reminder').then(setReminder).catch(() => {})

  useEffect(() => {
    api.get('/agent/profile').then(setProfile).catch(() => {})
    api.get('/config').then((d) => setConfigured(d.configured)).catch(() => {})
    loadRuns()
    loadPlans()
    loadMemories()
    loadReminder()
    return () => { stopPolling(); if (intentTimer.current) clearTimeout(intentTimer.current) }
  }, [])

  // 边打字边识别意图（防抖 350ms；纯规则零成本，不写库、不花钱）
  const onGoalChange = (v) => {
    setProfile({ ...profile, goal: v })
    if (intentTimer.current) clearTimeout(intentTimer.current)
    const text = v.trim()
    if (!text) { setIntent(null); return }
    intentTimer.current = setTimeout(() => {
      api.post('/agent/intent', { text }).then(setIntent).catch(() => setIntent(null))
    }, 350)
  }

  const confirmPlan = async (id) => {
    try {
      await api.post(`/agent/plan/${id}/confirm`)
      toast('✅ 已确认并应用复盘调整')
      loadPlans(); loadReminder()
    } catch (e) { toast(e.message) }
  }
  const rejectPlan = async (id) => {
    try {
      await api.post(`/agent/plan/${id}/reject`)
      toast('已拒绝复盘调整')
      loadPlans(); loadReminder()
    } catch (e) { toast(e.message) }
  }
  const confirmMemory = async (id) => {
    try {
      await api.post(`/agent/memories/${id}/confirm`)
      toast('✅ 已确认生效，之后规划会遵守这条记忆')
      loadMemories()
    } catch (e) { toast(e.message) }
  }
  const rejectMemory = async (id) => {
    try {
      await api.post(`/agent/memories/${id}/reject`)
      toast('已拒绝这条记忆')
      loadMemories()
    } catch (e) { toast(e.message) }
  }
  const deleteMemory = async (id) => {
    try {
      await api.del(`/agent/memories/${id}`)
      toast('已删除这条记忆')
      loadMemories()
    } catch (e) { toast(e.message) }
  }
  const runReview = async () => {
    if (!configured) return toast('还没配置模型 key，去「设置」页配置后再复盘')
    if (!reminder.plan_date) return
    setStarting(true)
    try {
      const goal = `复盘 ${reminder.plan_date} 的学习计划执行情况：用 get_plan_vs_actual 对比实际学习分钟与计划，判定是否计划过量/合理/不足，用 submit_review 提交 verdict 与待确认调整建议。`
      const d = await api.post('/agent/run', { goal, available_time: 0 })
      setRun(null)
      startPolling(d.run_id)
      loadRuns(); loadReminder()
    } catch (e) { toast(e.message) }
    finally { setStarting(false) }
  }

  const start = async () => {
    const goal = (profile.goal || '').trim()
    if (!goal) return toast('先写下目标再运行 Agent')
    if (!configured) return toast('还没配置模型 key，去「设置」页配置后再运行')
    setStarting(true)
    try {
      const time = Number(profile.available_time) || 0
      api.put('/agent/profile', { goal, available_time: time }).catch(() => {}) // 记住画像
      const d = await api.post('/agent/run', { goal, available_time: time })
      setRun(null)
      startPolling(d.run_id)
      loadRuns()
    } catch (e) { toast(e.message) }
    finally { setStarting(false) }
  }

  const cancel = async () => {
    if (!run?.run_id) return
    try {
      await api.post(`/agent/run/${run.run_id}/cancel`)
      toast('已请求取消')
      stopPolling()
      loadRun(run.run_id)
      loadRuns()
    } catch (e) { toast(e.message) }
  }

  const renderEvent = (e) => {
    const c = e.content || {}
    switch (e.event_type) {
      case 'observe':
        return <div>🔭 观察 <b>{c.tool}</b><div className="muted">{short(c.result)}</div></div>
      case 'tool_call':
        return <div>🛠️ 调用 <b>{c.tool}</b> <span className="muted">{short(c.args)}</span></div>
      case 'tool_result':
        return <div>{c.ok ? '✅' : '❌'} <b>{c.tool}</b>{c.cached && <span className="muted"> (缓存)</span>}<div className="muted">{c.ok ? short(c.result) : (c.result?.error || '')}</div></div>
      case 'plan':
        return <div>💭 规划</div>
      case 'reflect':
        return <div>🔄 复盘</div>
      case 'replan':
        return <div>🔁 重新规划：{c.reason}</div>
      case 'plan_compare':
        return <div>📊 计划对比 <b>{c.plan_date}</b>：计划 {c.planned_total} / 实际 {c.actual_total} 分钟（{c.deviation_pct}%）</div>
      case 'user_memories':
        return <div>🧠 已注入用户记忆 {c.count} 条（{(c.mkeys || []).join('、')}），规划会遵守</div>
      case 'error':
        return <div className="err">⚠️ {c.message}</div>
      default:
        return <div>{e.event_type}</div>
    }
  }

  const plan = run?.planner_output || {}
  const steps = Array.isArray(plan.steps) ? plan.steps : []

  return (
    <div className="agent-page">
      {!configured && (
        <div className="card chat-hint">
          <span>📌 Agent 需要模型 API key —— </span>
          <button className="btn primary sm" onClick={() => { window.location.hash = '#/settings' }}>去设置页配置</button>
        </div>
      )}

      {reminder.needs_review && (
        <div className="card chat-hint reminder-bar">
          <span>📌 {reminder.message}</span>
          <span className="muted">
            {reminder.verdict ? `偏差 ${reminder.deviation_pct}% · ${VERDICT_LABEL[reminder.verdict] || reminder.verdict}` : ''}
          </span>
          <button className="btn primary sm" onClick={runReview} disabled={polling}>🤖 复盘</button>
        </div>
      )}

      <div className="agent-grid">
        {/* 上半：目标 + 运行 */}
        <div className="card">
          <h3>🎯 让 Agent 为你规划</h3>
          <div className="agent-form">
            <textarea
              rows={2}
              placeholder="例如：分析我的学习状态，并提出明天计划"
              value={profile.goal}
              onChange={(e) => onGoalChange(e.target.value)}
            />
            {intent && profile.goal.trim() && (
              <div className="intent-bar">
                <span className="intent-badge" style={{ background: INTENT_COLOR[intent.intent] || '#94a3b8' }}>
                  {intent.label}
                </span>
                <span>{intent.describe}</span>
                {intent.missing?.length > 0 && (
                  <span className="muted">还缺：{intent.missing.map((k) => SLOT_LABEL[k] || k).join('、')}（建议用「多轮对话」页补齐）</span>
                )}
                <span className="intent-conf">置信度 {Math.round((intent.confidence || 0) * 100)}%</span>
              </div>
            )}
            <div className="agent-time-row">
              <label>每天可用时间</label>
              <input
                type="number" min="0" max="12" value={profile.available_time}
                onChange={(e) => setProfile({ ...profile, available_time: e.target.value })}
              />
              <span className="muted">小时</span>
              <button className="btn primary" onClick={start} disabled={starting || polling}>
                {starting ? '启动中…' : polling ? '运行中…' : '🤖 运行 Agent'}
              </button>
            </div>
            {polling && <div className="loading">Agent 正在观察你的学习数据并规划…</div>}
          </div>
        </div>

        {/* 历史运行 */}
        <div className="card">
          <h3>🕘 历史运行</h3>
          {runs.length === 0 ? (
            <Empty text={'还没有运行记录。\n输入目标后点「运行 Agent」'} />
          ) : (
            <div className="run-list">
              {runs.map((r) => (
                <button
                  key={r.run_id}
                  className={`run-item${run?.run_id === r.run_id ? ' active' : ''}`}
                  onClick={() => { stopPolling(); loadRun(r.run_id) }}
                >
                  <span className="status-dot" style={STATUS_STYLE[r.status] || {}} />
                  <span className="run-goal">{r.goal}</span>
                  <span className="muted">{r.finished_at ? (r.finished_at.slice(0, 16).replace('T', ' ')) : ''}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 下半：运行详情 */}
      {run && (
        <div className="card run-detail">
          <div className="run-head">
            <h3>📋 {run.goal}</h3>
            <div className="run-status">
              <span className="badge" style={STATUS_STYLE[run.status] || {}}>{STATUS_LABEL[run.status] || run.status}</span>
              {run.intent && (
                <span className="intent-badge" style={{ background: INTENT_COLOR[run.intent] || '#94a3b8' }}>
                  {INTENT_LABEL[run.intent] || run.intent}
                </span>
              )}
              {run.status === 'running' && <button className="btn ghost sm" onClick={cancel}>取消</button>}
              {run.iteration > 0 && <span className="muted">迭代 {run.iteration}</span>}
            </div>
          </div>

          {run.error && <div className="run-error">⚠️ {run.error}</div>}
          {run.status === 'running' && <div className="loading">Agent 思考中…</div>}

          {steps.length > 0 && (
            <div className="plan-box">
              {plan.reasoning_summary && <div className="plan-goal">💡 {plan.reasoning_summary}</div>}
              {steps.map((s, i) => (
                <div key={i} className="plan-step">{i + 1}. <b>{s.tool}</b> <span className="muted">{short(s.arguments)}</span></div>
              ))}
            </div>
          )}

          {run.trace_events?.length > 0 && (
            <div className="timeline">
              {run.trace_events.map((e) => (
                <div key={e.seq} className="trace-row">{renderEvent(e)}</div>
              ))}
            </div>
          )}

          {run.reflection?.reason && (
            <div className="reflect-box">
              🔄 {run.reflection.goal_completed ? '目标已达成' : '目标未完成'} · {run.reflection.reason}
            </div>
          )}

          {actions.length > 0 && (
            <div className="action-block">
              <h4>🧾 Agent 操作记录（直接生效 + 审计）</h4>
              <div className="action-table">
                {actions.map((a) => (
                  <div key={a.id} className={`action-row${a.ok ? '' : ' err'}`}>
                    <div className="action-tool">
                      {a.ok ? '✅' : '❌'} <b>{a.tool}</b>
                      <span className="muted">{a.created_at ? a.created_at.slice(11, 19) : ''}</span>
                    </div>
                    <div className="muted">参数 {short(a.args)}</div>
                    {a.before && Object.keys(a.before).length > 0 && <div className="muted">之前 {short(a.before)}</div>}
                    {a.after && Object.keys(a.after).length > 0 && <div className="muted">之后 {short(a.after)}</div>}
                    {!a.ok && <div className="err">⚠️ {a.error}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {run.final_reply && (
            <div className="final-reply"><span className="final-icon">🎯</span><pre>{run.final_reply}</pre></div>
          )}

          {/* Phase 5：本次运行的用量明细（token 为 API 真实值，成本按公开单价估算） */}
          {run.token_usage && (run.token_usage.total_tokens > 0) && (
            <div className="run-usage">
              <span>🔢 {run.token_usage.total_tokens} token</span>
              {run.token_usage.input_tokens !== undefined && (
                <span className="muted">入 {run.token_usage.input_tokens} / 出 {run.token_usage.output_tokens}</span>
              )}
              {run.token_usage.llm_calls !== undefined && <span className="muted">{run.token_usage.llm_calls} 次调用</span>}
              {run.token_usage.latency_ms > 0 && <span className="muted">{(run.token_usage.latency_ms / 1000).toFixed(1)} 秒</span>}
              {run.token_usage.cost_cny !== undefined && (
                <span className="run-cost" title="按公开单价估算，仅供量级参考">
                  ≈ ¥{(Number(run.token_usage.cost_cny) || 0).toFixed(4)}
                </span>
              )}
              {run.token_usage.price_known === false && <span className="muted">（该模型单价未收录，按默认价估）</span>}
            </div>
          )}
        </div>
      )}

      {/* 已记住的记忆（Phase 4 长期记忆） */}
      <div className="card plan-section">
        <h3>🧠 已记住的记忆</h3>
        <p className="memory-hint muted">
          Agent 记住的偏好/事实/目标，确认后才参与规划（待确认不生效）。改想法时让 Agent「记住」同一条即可覆盖。
        </p>
        {memories.length === 0 ? (
          <Empty text={'还没有记住的记忆。\n对 Agent 说「记住：平时工作日 20:00-23:00 学习效率最高」即可'} />
        ) : (
          <div className="memory-list">
            {memories.map((m) => (
              <div key={m.id} className="memory-card">
                <div className="memory-top">
                  <span className="memory-type">{MTYPE_LABEL[m.mtype] || m.mtype}</span>
                  <span className={MEM_STATUS[m.status]?.cls || 'memory-badge'}>{MEM_STATUS[m.status]?.text || m.status}</span>
                  <span className="muted memory-imp">{'★'.repeat(Math.max(0, Math.min(5, m.importance)))}</span>
                </div>
                <div className="memory-content">{m.content}</div>
                {m.keywords && <div className="muted memory-keywords">关键词：{m.keywords}</div>}
                <div className="memory-actions">
                  {m.status === 'pending' ? (
                    <>
                      <button className="btn primary sm" onClick={() => confirmMemory(m.id)}>✅ 确认生效</button>
                      <button className="btn ghost sm" onClick={() => rejectMemory(m.id)}>✖ 拒绝</button>
                    </>
                  ) : (
                    <button className="btn ghost sm" onClick={() => deleteMemory(m.id)}>🗑 删除</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 学习计划（Phase 3 闭环） */}
      <div className="card plan-section">
        <h3>📅 学习计划（闭环）</h3>
        {plans.length === 0 ? (
          <Empty text={'还没有跨天学习计划。\n让 Agent 说「安排明天的学习」即可生成'} />
        ) : (
          <div className="plan-list">
            {plans.map((p) => (
              <div key={p.id} className="plan-card">
                <div className="plan-head">
                  <b>{p.plan_date}</b>
                  <span className={PLAN_BADGE[p.status]?.cls || 'badge'}>{PLAN_BADGE[p.status]?.text || p.status}</span>
                </div>
                {p.goal && <div className="plan-goal muted">{p.goal}</div>}
                <div className="plan-items">
                  {p.items.map((it) => <PlanItem key={it.id} it={it} />)}
                </div>
                <div className="plan-total">
                  <span>计划 {p.expected_total} 分钟</span>
                  <span>实际 {p.actual_total} 分钟</span>
                </div>
                {p.review_status === 'pending' && (
                  <div className="review-panel">
                    <div className="review-verdict">
                      🔍 复盘：{p.review_verdict || '—'}
                      {p.review_reasoning && <span className="muted"> · {p.review_reasoning}</span>}
                    </div>
                    <div className="review-adjustments">
                      {p.adjustments.length === 0
                        ? <div className="muted">无调整项</div>
                        : p.adjustments.map((a, i) => <div key={i} className="muted">· {adjustLabel(a, p.items)}</div>)}
                    </div>
                    <div className="review-actions">
                      <button className="btn primary sm" onClick={() => confirmPlan(p.id)}>✅ 确认调整</button>
                      <button className="btn ghost sm" onClick={() => rejectPlan(p.id)}>✖ 拒绝</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
