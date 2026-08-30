import React, { useState } from 'react'
import { useLoad, saveResource } from '../useLoad.js'
import { toast } from '../toast.js'
import { api } from '../api.js'

const FIELDS = [
  ['algorithm_minutes', '🧮 算法(分)', '算法分钟'],
  ['bago_minutes', '📚 八股(分)', '八股分钟'],
  ['course_minutes', '🎬 课程(分)', '课程分钟'],
  ['project_minutes', '🚀 项目(分)', '项目分钟'],
  ['reading_minutes', '📖 阅读(分)', '论文/阅读分钟'],
]

export default function Checkin({ onNavigate }) {
  const [today, setToday] = useState(null)
  const [form, setForm] = useState({ algorithm_count: 0, algorithm_minutes: 0, bago_minutes: 0, course_minutes: 0, project_minutes: 0, reading_minutes: 0, mood: 3, completed: '', problems: '', learned: '', tomorrow_plan: '' })
  const { data: recent, reload: reloadRecent } = useLoad('/checkins/recent?days=14', [])
  const { data: todaySessions, reload: reloadSessions } = useLoad('/tasks/sessions/today', [])

  React.useEffect(() => {
    api.get('/checkins/today').then((d) => {
      if (d) {
        setToday(d)
        setForm((f) => ({ ...f,
          algorithm_count: d.algorithm_count || 0, algorithm_minutes: d.algorithm_minutes || 0,
          bago_minutes: d.bago_minutes || 0, course_minutes: d.course_minutes || 0,
          project_minutes: d.project_minutes || 0, reading_minutes: d.reading_minutes || 0,
          mood: d.mood || 3, completed: d.completed || '', problems: d.problems || '',
          learned: d.learned || '', tomorrow_plan: d.tomorrow_plan || '' }))
      }
    }).catch(() => {})
  }, [])

  const setNum = (k) => (e) => setForm((s) => ({ ...s, [k]: Number(e.target.value) || 0 }))
  const setTxt = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const save = async () => {
    const saved = await saveResource('/checkins', { ...form, log_date: new Date().toISOString().slice(0, 10) }, null, () => { reloadRecent(); reloadSessions(); })
    if (saved) { setToday(saved); toast('打卡已保存 💪') }
  }

  const total = FIELDS.reduce((s, [k]) => s + (form[k] || 0), 0)

  return (
    <div>
      <div className="streak-banner">🔥 每天花 2 分钟打卡，一年后你会感谢现在的自己。坚持比完美更重要。</div>

      <div className="grid grid-2">
        <div className="card">
          <h3>今日快速打卡 <span style={{ fontWeight: 400, color: 'var(--text-3)', fontSize: 12 }}>只填数字，其余可留空</span></h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
            <div className="field">
              <label>算法题数</label>
              <input type="number" min="0" value={form.algorithm_count} onChange={setNum('algorithm_count')} />
            </div>
            <div className="field">
              <label>今日状态（1~5）</label>
              <select value={form.mood} onChange={setNum('mood')}>
                {[5, 4, 3, 2, 1].map((v) => <option key={v} value={v}>{'😄🙂😐😕😫'[5 - v]} {v} 分</option>)}
              </select>
            </div>
            {FIELDS.map(([k, label]) => (
              <div className="field" key={k}>
                <label>{label}</label>
                <input type="number" min="0" value={form[k]} onChange={setNum(k)} />
              </div>
            ))}
          </div>

          <div className="field" style={{ marginBottom: 10 }}>
            <label>今天完成了什么</label>
            <textarea value={form.completed} onChange={setTxt('completed')} placeholder="Research Agent 完成了 Tool Calling；LeetCode 2 题" />
          </div>
          <div className="field" style={{ marginBottom: 10 }}>
            <label>遇到的问题 / 学到什么</label>
            <textarea value={form.problems} onChange={setTxt('problems')} placeholder="遇到 X 问题，卡在 Y，明天再查" />
          </div>
          <div className="field" style={{ marginBottom: 10 }}>
            <label>明天准备做什么</label>
            <input value={form.tomorrow_plan} onChange={setTxt('tomorrow_plan')} placeholder="做 Retry / 继续 DFS 3 题" />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 6 }}>
            <button className="btn primary" onClick={save}>保存打卡</button>
            <span style={{ fontSize: 13, color: 'var(--text-2)' }}>今日合计 <strong style={{ color: 'var(--green-dark)', fontSize: 16 }}>{total}</strong> 分钟</span>
            {today?.total_minutes > 0 && <span className="pill 已完成">已打卡 {today.total_minutes} 分钟</span>}
          </div>
        </div>

        <div className="card">
          <h3>最近 14 天</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>日期</th><th>算法</th><th>八股</th><th>课程</th><th>项目</th><th>总时长</th><th>状态</th></tr>
              </thead>
              <tbody>
                {(recent || []).map((r) => (
                  <tr key={r.id}>
                    <td>{r.log_date}</td>
                    <td>{r.algorithm_count} 题 / {r.algorithm_minutes}m</td>
                    <td>{r.bago_minutes}m</td>
                    <td>{r.course_minutes}m</td>
                    <td>{r.project_minutes}m</td>
                    <td><strong>{r.total_minutes}m</strong></td>
                    <td>{r.total_minutes > 0 ? '✅' : '⬜'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {todaySessions && todaySessions.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px dashed rgba(15,23,42,.12)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>📌 今日任务学习（路线计时自动归入上方分类）</div>
              {(todaySessions || []).map((s) => (
                <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</span>
                  <strong style={{ color: 'var(--green-dark)', flexShrink: 0, marginLeft: 8 }}>{s.minutes} 分</strong>
                </div>
              ))}
            </div>
          )}
          <button className="btn sm" style={{ marginTop: 12 }} onClick={() => onNavigate('dashboard')}>回总览看连续天数 →</button>
        </div>
      </div>
    </div>
  )
}
