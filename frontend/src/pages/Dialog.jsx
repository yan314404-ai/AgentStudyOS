import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'
import { Empty } from '../components.jsx'

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

const EXAMPLES = [
  '安排明天的学习',
  '帮我安排 2026-12-01 的学习，共 180 分钟',
  '记录今天在任务 1 上学习了 40 分钟',
  '记住：我工作日 20:00-23:00 效率最高',
  '复盘昨天的计划',
  '分析我现在的学习状态',
]

const STORAGE_KEY = 'agentos.conv_id'

export default function Dialog() {
  const [convId, setConvId] = useState(() => localStorage.getItem(STORAGE_KEY) || '')
  const [turns, setTurns] = useState([])
  const [pending, setPending] = useState({})
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [availableTime, setAvailableTime] = useState(3)
  const [run, setRun] = useState(null)
  const [hint, setHint] = useState(null)
  const [configured, setConfigured] = useState(true)
  const bodyRef = useRef(null)
  const pollRef = useRef(null)
  const hintTimer = useRef(null)

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  const applyConv = (conv) => {
    if (!conv) return
    setConvId(conv.conv_id)
    localStorage.setItem(STORAGE_KEY, conv.conv_id)
    setTurns(conv.turns || [])
    setPending(conv.pending || {})
  }

  const loadConv = async (id) => {
    if (!id) return
    try {
      const d = await api.get('/agent/conversations/' + id)
      applyConv(d.conversation)
    } catch {
      localStorage.removeItem(STORAGE_KEY)
      setConvId('')
      setTurns([])
    }
  }

  useEffect(() => {
    api.get('/config').then((d) => setConfigured(d.configured)).catch(() => {})
    api.get('/agent/profile').then((p) => setAvailableTime(p.available_time ?? 3)).catch(() => {})
    const id = localStorage.getItem(STORAGE_KEY)
    if (id) loadConv(id).finally(() => setLoaded(true))
    else setLoaded(true)
    return () => { stopPoll(); if (hintTimer.current) clearTimeout(hintTimer.current) }
  }, [])

  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns, sending, run])

  // 边打字边识别意图（防抖 350ms，纯规则零成本，不写库不花钱）
  const onInputChange = (v) => {
    setInput(v)
    if (hintTimer.current) clearTimeout(hintTimer.current)
    const text = v.trim()
    if (!text) { setHint(null); return }
    hintTimer.current = setTimeout(() => {
      api.post('/agent/intent', { text }).then(setHint).catch(() => setHint(null))
    }, 350)
  }

  const pollRun = (runId) => {
    stopPoll()
    pollRef.current = setInterval(async () => {
      try {
        const d = await api.get('/agent/run/' + runId)
        setRun(d)
        if (d.status !== 'running') { stopPoll(); loadConv(convId) }
      } catch { stopPoll() }
    }, 1500)
    api.get('/agent/run/' + runId).then(setRun).catch(() => {})
  }

  const send = async (text0) => {
    const text = (text0 ?? input).trim()
    if (!text || sending) return
    setInput('')
    setHint(null)
    setSending(true)
    setRun(null)
    try {
      const d = await api.post('/agent/chat', {
        conv_id: convId, text, available_time: Number(availableTime) || 0,
      })
      applyConv({ conv_id: d.conv_id, turns: [], pending: {} })
      setConvId(d.conv_id)
      localStorage.setItem(STORAGE_KEY, d.conv_id)
      // 后端已把 user turn 与 assistant turn 落库，重新拉一次拿到完整列表
      await loadConv(d.conv_id)
      if (d.action === 'run' && d.run_id) pollRun(d.run_id)
    } catch (e) {
      toast(e.message)
    } finally {
      setSending(false)
    }
  }

  const resetConv = async () => {
    stopPoll()
    setRun(null)
    localStorage.removeItem(STORAGE_KEY)
    setConvId('')
    setTurns([])
    setPending({})
    setHint(null)
    toast('已开新会话')
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  const pendingSlots = Object.entries(pending.slots || {})
    .filter(([, v]) => v !== '' && v !== null && v !== undefined)

  return (
    <div className="chat-page">
      {!configured && (
        <div className="chat-hint">
          <span>📌 多轮对话会真正调用模型 —— </span>
          <button className="btn primary sm" onClick={() => { window.location.hash = '#/settings' }}>去设置页配置</button>
        </div>
      )}

      <div className="dialog-toolbar">
        <span className="muted">
          多轮对话：先说一半，Agent 会追问缺的信息，补齐后再发起运行。
        </span>
        <span className="muted dialog-conv-id">{convId ? '会话 ' + convId : '新会话（首次发送时创建）'}</span>
        <button className="btn ghost sm" onClick={resetConv}>🆕 新会话</button>
      </div>

      <div className="card chat-body" ref={bodyRef}>
        {!loaded ? <div className="loading">加载中…</div> :
          turns.length === 0 && !sending ? (
            <div className="dialog-empty">
              <Empty text={'试一句，Agent 会先识别意图再决定怎么做：'} />
              <div className="dialog-examples">
                {EXAMPLES.map((s) => (
                  <button key={s} className="dialog-example" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : turns.map((t) => {
            const meta = t.intent || {}
            const isUser = t.role === 'user'
            const isRun = meta.kind === 'run'
            return (
              <div key={t.id} className={`chat-msg ${t.role}`}>
                <div className="bubble">{t.content}</div>
                <div className="dialog-meta">
                  {isUser && meta.intent && (
                    <span className="intent-badge" style={{ background: INTENT_COLOR[meta.intent] || '#94a3b8' }}>
                      {INTENT_LABEL[meta.intent] || meta.intent}
                      {meta.confidence !== undefined && (
                        <span style={{ opacity: .75, fontWeight: 500 }}>{Math.round(meta.confidence * 100)}%</span>
                      )}
                    </span>
                  )}
                  {isUser && meta.slots && Object.keys(meta.slots).length > 0 && (
                    <span className="muted dialog-slots">
                      {Object.entries(meta.slots)
                        .filter(([, v]) => v !== '' && v !== null && v !== undefined)
                        .map(([k, v]) => `${SLOT_LABEL[k] || k}=${v}`).join(' · ')}
                    </span>
                  )}
                  {isUser && (meta.missing || []).length > 0 && (
                    <span className="dialog-missing">缺 {meta.missing.map((k) => SLOT_LABEL[k] || k).join('、')}</span>
                  )}
                  {isRun && <span className="dialog-run-tag">🚀 已发起运行</span>}
                  {!isUser && meta.kind === 'ask' && <span className="dialog-ask-tag">❓ 追问</span>}
                  <span className="time">{(t.created_at || '').slice(11, 19)}</span>
                </div>
              </div>
            )
          })}
        {sending && <div className="chat-msg assistant"><div className="bubble typing">识别意图中…</div></div>}

        {run && (
          <div className="dialog-run">
            <div className="dialog-run-head">
              <span className={`status-dot`} style={{ background: run.status === 'running' ? '#1e88e5' : run.status === 'succeeded' ? '#2e9e5b' : '#e5484d' }} />
              <b>
                {run.status === 'running' ? 'Agent 正在规划并执行…'
                  : run.status === 'succeeded' ? '运行完成'
                    : run.status === 'cancelled' ? '已取消' : '运行失败'}
              </b>
              {run.iteration > 0 && <span className="muted">迭代 {run.iteration}</span>}
              <button className="btn ghost sm" onClick={() => { window.location.hash = '#/trace' }}>看回放 →</button>
            </div>
            {run.error && <div className="run-error">⚠️ {run.error}</div>}
            {run.final_reply && <pre className="dialog-final">{run.final_reply}</pre>}
          </div>
        )}
      </div>

      {/* 实时意图提示 */}
      {hint && input.trim() && (
        <div className="intent-bar">
          <span className="intent-badge" style={{ background: INTENT_COLOR[hint.intent] || '#94a3b8' }}>
            {hint.label}
          </span>
          <span>{hint.describe}</span>
          {hint.missing?.length > 0 && (
            <span className="muted">还缺：{hint.missing.map((k) => SLOT_LABEL[k] || k).join('、')}</span>
          )}
          {hint.question && <span className="muted">发送后会追问「{hint.question}」</span>}
          <span className="intent-conf">置信度 {Math.round((hint.confidence || 0) * 100)}%</span>
        </div>
      )}

      {pendingSlots.length > 0 && (
        <div className="intent-bar" style={{ background: 'var(--amber-bg)', color: '#b45309', borderColor: 'rgba(245,158,11,.28)' }}>
          <span>⏳ 有一轮追问在等你补齐：</span>
          <span>{pendingSlots.map(([k, v]) => `${SLOT_LABEL[k] || k}=${v}`).join(' · ')}</span>
          <span className="intent-conf">意图 {INTENT_LABEL[pending.intent] || pending.intent}</span>
        </div>
      )}

      <div className="chat-input">
        <textarea
          rows={2}
          placeholder="说一句话，例如「帮我安排学习」—— 缺信息时 Agent 会追问。Enter 发送 / Shift+Enter 换行"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={onKey}
        />
        <input
          className="dialog-time"
          type="number" min="0" max="12" value={availableTime}
          title="每天可用学习时间（小时）"
          onChange={(e) => setAvailableTime(e.target.value)}
        />
        <button className="btn primary" onClick={() => send()} disabled={sending || !input.trim()}>
          {sending ? '发送中…' : '发送'}
        </button>
      </div>
    </div>
  )
}
