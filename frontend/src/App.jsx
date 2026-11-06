import React, { useEffect, useState } from 'react'
import { Toast } from './components.jsx'
import { onToast, toast } from './toast.js'
import { api } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import Tasks from './pages/Tasks.jsx'
import Algorithms from './pages/Algorithms.jsx'
import Bagu from './pages/Bagu.jsx'
import Courses from './pages/Courses.jsx'
import Projects from './pages/Projects.jsx'
import Checkin from './pages/Checkin.jsx'
import Search from './pages/Search.jsx'
import Reports from './pages/Reports.jsx'
import Summaries from './pages/Summaries.jsx'
import Chat from './pages/Chat.jsx'
import Agent from './pages/Agent.jsx'
import Dialog from './pages/Dialog.jsx'
import Eval from './pages/Eval.jsx'
import Trace from './pages/Trace.jsx'
import Settings from './pages/Settings.jsx'

const NAV = [
  { key: 'dashboard', label: '总览', icon: '📊' },
  { key: 'checkin', label: '每日打卡', icon: '✅' },
  { key: 'tasks', label: '学习路线', icon: '🗺️' },
  { key: 'algorithms', label: '算法', icon: '🧮' },
  { key: 'bagu', label: '八股', icon: '📚' },
  { key: 'courses', label: '课程', icon: '🎬' },
  { key: 'projects', label: '项目', icon: '🚀' },
  { key: 'summaries', label: '每日总结', icon: '📝' },
  { key: 'reports', label: '报告', icon: '📈' },
  { key: 'agent', label: 'Agent', icon: '🤖' },
  { key: 'dialog', label: '多轮对话', icon: '💭' },
  { key: 'eval', label: '评测 / 成本', icon: '🧪' },
  { key: 'trace', label: 'Trace', icon: '📜' },
  { key: 'chat', label: 'AI 助手', icon: '💬' },
  { key: 'settings', label: '设置', icon: '⚙️' },
]

const PAGE_TITLES = {
  dashboard: '总览',
  tasks: '学习路线',
  algorithms: '算法刷题',
  bagu: '八股面试题',
  courses: '课程与资料',
  projects: '项目追踪',
  checkin: '每日打卡',
  search: '全局搜索',
  summaries: '每日总结',
  reports: '报告',
  agent: 'Agent 自主规划',
  dialog: '多轮对话',
  eval: '评测与成本看板',
  trace: 'Agent 运行回放',
  chat: 'AI 助手',
  settings: '设置',
}

const pageFromHash = () => {
  const h = window.location.hash.replace(/^#\/?/, '')
  return h && h !== 'dashboard' ? h : 'dashboard'
}

export default function App() {
  const [page, setPageState] = useState(pageFromHash)
  const [toastMsg, setToastMsg] = useState('')
  const [readiness, setReadiness] = useState(null)

  // 页面状态与 URL hash 同步：刷新不丢当前页，也方便直达（如 /#/reports）
  const setPage = (p) => {
    window.location.hash = p === 'dashboard' ? '/' : '/' + p
    setPageState(p)
  }

  useEffect(() => {
    const onHash = () => setPageState(pageFromHash)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const off = onToast((m) => {
      setToastMsg(m)
      setTimeout(() => setToastMsg(''), 2600)
    })
    api.get('/dashboard').then((d) => setReadiness(d.progress?.['实习准备度'] ?? null)).catch(() => {})
    return off
  }, [])

  // 「打开即最新」：后端 /api/version 反映前端构建版本；窗口切到前台或每 10s 检查一次，
  // 版本变了（改完代码重新构建+重启后端后）自动刷新成最新版，不用手动 F5。
  useEffect(() => {
    if (import.meta.env.DEV) return // 开发模式 Vite 已热刷新，跳过
    let last = null
    let timer
    const check = async () => {
      try {
        const v = (await api.get('/version'))?.version
        if (!v) return
        if (last && v !== last) {
          toast('🔁 检测到新版本，正在自动刷新…')
          setTimeout(() => location.reload(), 400)
          return
        }
        last = v
      } catch { /* 后端重启瞬间连不上，忽略，下轮再查 */ }
    }
    const onVisible = () => { if (document.visibilityState === 'visible') check() }
    check()
    timer = setInterval(check, 10000)
    window.addEventListener('focus', check)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', check)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  const today = new Date()
  const dateStr = `${today.getMonth() + 1}月${today.getDate()}日 · ${['周日','周一','周二','周三','周四','周五','周六'][today.getDay()]}`

  const goSearch = (q) => { setSearchQ(q); setPage('search') }
  const [searchQ, setSearchQ] = useState('')

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">🎓 <span>Agent 学习 OS</span></div>
        {NAV.map((n) => (
          <button key={n.key} className={`nav-item${page === n.key ? ' active' : ''}`} onClick={() => setPage(n.key)}>
            <span className="icon">{n.icon}</span><span>{n.label}</span>
          </button>
        ))}
        <div className="spacer" />
        <div className="readiness-mini">
          <div className="label">实习准备度</div>
          <div className="num">{readiness ?? '—'} <span style={{ fontSize: 13, fontWeight: 500 }}>/ 100</span></div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <h1>{PAGE_TITLES[page] || '总览'}</h1>
            <div className="date">{dateStr}</div>
          </div>
          <div className="search-box">
            <span>🔍</span>
            <input
              placeholder="全局搜索任务 / 算法 / 八股 / 课程 / 项目"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && goSearch(searchQ)}
            />
          </div>
        </div>

        {page === 'dashboard' && <Dashboard onNavigate={setPage} />}
        {page === 'tasks' && <Tasks />}
        {page === 'algorithms' && <Algorithms />}
        {page === 'bagu' && <Bagu />}
        {page === 'courses' && <Courses />}
        {page === 'projects' && <Projects />}
        {page === 'checkin' && <Checkin onNavigate={setPage} />}
        {page === 'search' && <Search query={searchQ} />}
        {page === 'summaries' && <Summaries />}
        {page === 'reports' && <Reports />}
        {page === 'agent' && <Agent />}
        {page === 'dialog' && <Dialog />}
        {page === 'eval' && <Eval />}
        {page === 'trace' && <Trace />}
        {page === 'chat' && <Chat />}
        {page === 'settings' && <Settings />}
      </main>

      <Toast message={toastMsg} />
    </div>
  )
}
