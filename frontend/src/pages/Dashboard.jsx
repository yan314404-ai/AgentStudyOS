import React from 'react'
import { useLoad } from '../useLoad.js'
import { ProgressBar, Pill, Empty } from '../components.jsx'

function Ring({ value }) {
  const r = 52
  const c = 2 * Math.PI * r
  const filled = c * (Math.min(100, Math.max(0, value)) / 100)
  return (
    <div className="ring">
      <svg viewBox="0 0 130 130">
        <circle cx="65" cy="65" r={r} fill="none" stroke="#d1fae5" strokeWidth="12" />
        <circle cx="65" cy="65" r={r} fill="none" stroke="#10b981" strokeWidth="12"
          strokeLinecap="round" strokeDasharray={`${filled} ${c}`} transform="rotate(-90 65 65)" />
        <text x="65" y="62" textAnchor="middle" className="ring-num">{value}</text>
        <text x="65" y="80" textAnchor="middle" className="ring-label">/ 100</text>
      </svg>
    </div>
  )
}

const CAT_EMOJI = {
  基础: '🧱', LLM: '🤖', RAG: '📂', Agent: '🕸️', 'Agent 工程': '🛠️', 实习准备: '🧭',
  算法: '🧮', 八股: '📚', 项目: '🚀',
}

export default function Dashboard({ onNavigate }) {
  const { data, loading } = useLoad('/dashboard')

  if (loading || !data) return <div className="loading">加载中…</div>

  const p = data.progress
  const today = data.today
  const todayMin = today?.total_minutes ?? 0

  const cats = []
  if (p['任务分类']) {
    for (const [k, v] of Object.entries(p['任务分类'])) cats.push({ name: k, value: v, emoji: CAT_EMOJI[k] || '📌' })
  }
  if (p['算法掌握'] !== undefined) cats.push({ name: '算法', value: p['算法掌握'], emoji: CAT_EMOJI['算法'] })
  if (p['八股掌握'] !== undefined) cats.push({ name: '八股', value: p['八股掌握'], emoji: CAT_EMOJI['八股'] })
  if (p['项目进度'] !== undefined) cats.push({ name: '项目', value: p['项目进度'], emoji: CAT_EMOJI['项目'] })

  return (
    <div>
      <div className="hero">
        <Ring value={p['实习准备度'] ?? 0} />
        <div className="hero-info">
          <div className="title">Agent 实习准备度：{p['实习准备度'] ?? 0} / 100</div>
          <div className="desc">基于你的路线任务、算法 / 八股掌握度、项目进度实时计算（参考指标，不代表预测）</div>
          <div className="hero-stats">
            <div><div className="hs-num">🔥 {data.streak} 天</div><div className="hs-label">连续打卡</div></div>
            <div><div className="hs-num">⏱️ {todayMin} 分钟</div><div className="hs-label">今日学习</div></div>
            <div><div className="hs-num">{p['任务进度'] ?? 0}%</div><div className="hs-label">路线总进度</div></div>
          </div>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginTop: 16 }}>
        {cats.map((c) => (
          <div key={c.name} className="card cat-card">
            <div className="cat-emoji">{c.emoji}</div>
            <div className="cat-body">
              <div className="cat-name"><span>{c.name}</span><span className="cat-pct">{c.value}%</span></div>
              <ProgressBar value={c.value} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>今日打卡</h3>
          {today ? (
            <>
              <div className="progress-label"><span>学习时长</span><span>{todayMin} / 150 分钟</span></div>
              <ProgressBar value={todayMin} max={150} />
              <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13 }}>
                <span>🧮 算法 {today.algorithm_count} 题</span>
                <span>📚 八股 {today.bago_minutes}m</span>
                <span>🎬 课程 {today.course_minutes}m</span>
                <span>🚀 项目 {today.project_minutes}m</span>
              </div>
              {today.completed && <div style={{ marginTop: 10, fontSize: 13, color: 'var(--text-2)' }}>✅ {today.completed}</div>}
              <button className="btn primary sm" style={{ marginTop: 14 }} onClick={() => onNavigate('checkin')}>去打卡</button>
            </>
          ) : <Empty text="今天还没打卡" />}
        </div>

        <div className="card">
          <h3>最近待办 · 路线任务</h3>
          {data.upcoming?.length ? (
            data.upcoming.map((t) => (
              <div key={t.id} className="task-item">
                <Pill text={t.status} />
                <div className="ti-title">
                  <div>{t.title}</div>
                  <div className="sub">{t.phase} · {t.due_date || '无截止'} · {t.progress}%</div>
                </div>
                <ProgressBar value={t.progress} sm color={t.status === '进行中' ? 'blue' : ''} />
              </div>
            ))
          ) : <Empty text="暂无待办" />}
          <button className="btn sm" style={{ marginTop: 10 }} onClick={() => onNavigate('tasks')}>查看全部 →</button>
        </div>
      </div>
    </div>
  )
}
