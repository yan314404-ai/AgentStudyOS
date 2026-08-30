import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { ProgressBar } from '../components.jsx'

const PROVIDER_LABEL = { deepseek: 'DeepSeek', openai: 'GPT', anthropic: 'Claude' }

const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const todayISO = () => fmt(new Date())
const fmtHours = (m) => { m = m || 0; return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m` }

const lvl = (m) => (m <= 0 ? 0 : m <= 30 ? 1 : m <= 60 ? 2 : m <= 120 ? 3 : 4)
const LVL_CLASS = ['lvl0', 'lvl1', 'lvl2', 'lvl3', 'lvl4']

function Heatmap({ data }) {
  const cells = useMemo(() => {
    const map = {}
    for (const d of data || []) map[d.date] = d.minutes || 0
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const start = new Date(today)
    start.setDate(start.getDate() - 363)
    start.setDate(start.getDate() - start.getDay()) // 回退到最近的周日，保证每列从周日开始
    const arr = []
    const cur = new Date(start)
    const tISO = todayISO()
    while (cur <= today) {
      const iso = fmt(cur)
      arr.push({ date: iso, minutes: map[iso] || 0, isToday: iso === tISO })
      cur.setDate(cur.getDate() + 1)
    }
    return arr
  }, [data])

  const activeDays = (data || []).filter((d) => d.minutes > 0).length
  const total = (data || []).reduce((s, d) => s + d.minutes, 0)

  return (
    <div className="hm-wrap">
      <div className="hm-grid">
        {cells.map((c) => (
          <div key={c.date} className={`hm-cell ${LVL_CLASS[lvl(c.minutes)]}${c.isToday ? ' today' : ''}`}
            title={`${c.date} · ${c.minutes} 分钟`} />
        ))}
      </div>
      <div className="hm-meta">
        <span>近一年学习 <b>{activeDays}</b> 天，共 <b>{fmtHours(total)}</b>（悬停格子看每天）</span>
        <span className="hm-legend">少
          <i className="hm-cell lvl0" /><i className="hm-cell lvl1" /><i className="hm-cell lvl2" />
          <i className="hm-cell lvl3" /><i className="hm-cell lvl4" />多
        </span>
      </div>
    </div>
  )
}

function ModuleBar({ modules }) {
  const entries = Object.entries(modules || {})
  const total = entries.reduce((s, [, v]) => s + v, 0)
  if (!total) return <div className="muted">本期还没有学习记录，先去打卡吧</div>
  return (
    <div className="mod-list">
      {entries.map(([name, v]) => (
        <div className="mod-row" key={name}>
          <span className="mod-name">{name}</span>
          <ProgressBar value={total ? (v / total) * 100 : 0} />
          <span className="mod-min">{v} 分</span>
        </div>
      ))}
    </div>
  )
}

const diffText = (s) => {
  if (!s || s.prev_total_minutes <= 0) return '上期无记录'
  if (s.diff_pct == null) return '上期无记录'
  if (s.diff_minutes > 0) return `+${fmtHours(s.diff_minutes)}（+${s.diff_pct}%）`
  if (s.diff_minutes < 0) return `${fmtHours(s.diff_minutes)}（${s.diff_pct}%）`
  return '持平'
}

export default function Reports() {
  const [cfg, setCfg] = useState({ configured: false })
  const [tab, setTab] = useState('week')
  const [heat, setHeat] = useState(null)
  const [rep, setRep] = useState(null)
  const [loading, setLoading] = useState(false)
  const [aiErr, setAiErr] = useState('')

  useEffect(() => {
    api.get('/config').then((d) => setCfg(d)).catch(() => {})
    api.get('/reports/heatmap').then((d) => setHeat(d.data)).catch(() => {})
  }, [])

  const load = async (refresh) => {
    setLoading(true); setAiErr('')
    try {
      const d = await api.get(`/reports/${tab === 'week' ? 'weekly' : 'monthly'}${refresh ? '?refresh=1' : ''}`)
      setRep(d)
      if (d.ai_error) setAiErr(d.ai_error)
      if (d.ok === false) {
        if (d.reason === 'not_configured') setCfg((c) => ({ ...c, configured: false }))
        else setAiErr(d.reason)
      }
    } catch (e) {
      setAiErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(false) }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps

  const stats = rep?.stats

  return (
    <div className="reports-page">
      {/* AI 配置条：key 配置收敛到「设置」页 */}
      <div className={`config-bar${cfg.configured ? ' ok' : ''}`}>
        {cfg.configured ? (
          <>
            <span>✅ {PROVIDER_LABEL[cfg.provider] || cfg.provider} 已配置 · {cfg.model}，周报/月报由 AI 生成</span>
            <button className="btn ghost sm" onClick={() => { window.location.hash = '#/settings' }}>⚙️ 去设置</button>
          </>
        ) : (
          <>
            <span className="muted">📌 配置模型 API key 后，周报/月报由 AI 撰写（key 只存本机，在「设置」页配置）</span>
            <button className="btn primary sm" onClick={() => { window.location.hash = '#/settings' }}>⚙️ 去设置</button>
          </>
        )}
      </div>

      {/* 热力图 */}
      <div className="card">
        <h3>🔥 学习热力图</h3>
        <Heatmap data={heat} />
      </div>

      {/* 周报 / 月报 */}
      <div className="card">
        <div className="tabbar">
          <button className={`tab-btn${tab === 'week' ? ' active' : ''}`} onClick={() => setTab('week')}>📅 周报</button>
          <button className={`tab-btn${tab === 'month' ? ' active' : ''}`} onClick={() => setTab('month')}>🗓️ 月报</button>
          {rep?.cached && <span className="tag">已缓存</span>}
          <button className="btn ghost sm" onClick={() => load(true)} disabled={loading}>🔄 重新生成</button>
        </div>

        {stats ? (
          <>
            <div className="grid grid-3 report-stats">
              <div className="stat-chip"><span>总时长</span><b>{fmtHours(stats.total_minutes)}</b></div>
              <div className="stat-chip"><span>打卡 {stats.checkin_days}/{stats.day_count} 天 · 日均</span><b>{stats.avg_per_day} 分</b></div>
              <div className="stat-chip"><span>对比上期</span>
                <b className={stats.diff_minutes > 0 ? 'up' : stats.diff_minutes < 0 ? 'down' : ''}>{diffText(stats)}</b></div>
              {tab === 'month' && <div className="stat-chip"><span>已完成任务</span><b>{stats.completed_tasks ?? 0}</b></div>}
            </div>

            <h4 className="block-title">模块分布（分钟）</h4>
            <ModuleBar modules={stats.modules} />

            <h4 className="block-title">AI 复盘{stats.total_minutes > 0 ? '' : '（本期暂无打卡数据，仅供演示）'}</h4>
            {loading ? (
              <div className="loading">AI 撰写中，请稍候…</div>
            ) : rep?.content ? (
              <div className="report-ai">{rep.content}</div>
            ) : (
              <div className="report-ai err">
                {rep?.ok === false && rep.reason === 'not_configured'
                  ? '尚未配置模型 API key —— 去「设置」页配置后即可生成 AI 复盘；统计数据已在上方正常展示。'
                  : aiErr ? `生成失败：${aiErr}` : '暂无内容'}
              </div>
            )}
          </>
        ) : loading ? (
          <div className="loading">统计计算中…</div>
        ) : (
          <div className="loading">加载中…</div>
        )}
      </div>
    </div>
  )
}
