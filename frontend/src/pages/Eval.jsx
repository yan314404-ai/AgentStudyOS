import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'
import { Empty } from '../components.jsx'

const INTENT_LABEL = {
  plan: '安排计划', review: '复盘计划', record: '记录学习',
  remember: '记住偏好', forget: '忘掉记忆', query: '查询状态', chat: '一般对话',
}
const KIND_LABEL = { intent: '意图识别', dialog: '多轮对话', run: '真实运行' }
const KIND_STYLE = {
  intent: { background: '#3b82f6' },
  dialog: { background: '#8b5cf6' },
  run: { background: '#f59e0b' },
}

// 一次 run 的成本常常只有几厘钱，直接 toFixed(2) 全是 0.00，按量级切换精度
const money = (v) => {
  const n = Number(v) || 0
  if (n === 0) return '¥0'
  if (n < 0.0001) return '¥' + n.toFixed(6)
  if (n < 0.01) return '¥' + n.toFixed(4)
  return '¥' + n.toFixed(2)
}
const num = (v) => (Number(v) || 0).toLocaleString('en-US')
const ms = (v) => {
  const n = Number(v) || 0
  return n >= 1000 ? (n / 1000).toFixed(1) + ' 秒' : n + ' 毫秒'
}

// 横向条形：一组数字比大小够用，不为了这个引图表库
function Bars({ rows, valueKey, labelKey, format, emptyText }) {
  const max = Math.max(1, ...rows.map((r) => Number(r[valueKey]) || 0))
  if (!rows.length) return <Empty text={emptyText || '暂无数据'} />
  return (
    <div className="bar-list">
      {rows.map((r, i) => {
        const v = Number(r[valueKey]) || 0
        return (
          <div className="bar-row" key={i}>
            <div className="bar-label" title={String(r[labelKey])}>{r[labelKey]}</div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: Math.max(2, (v / max) * 100) + '%' }} />
            </div>
            <div className="bar-value">{format ? format(v) : v}</div>
          </div>
        )
      })}
    </div>
  )
}

export default function Eval() {
  const [evals, setEvals] = useState([])
  const [cases, setCases] = useState([])
  const [report, setReport] = useState(null)
  const [running, setRunning] = useState(false)
  const [withRun, setWithRun] = useState(false)
  const [cost, setCost] = useState(null)
  const [prices, setPrices] = useState(null)
  const [days, setDays] = useState(30)
  const [loaded, setLoaded] = useState(false)

  const loadEvals = () => api.get('/agent/evals')
    .then((d) => { setEvals(d.evals || []); setCases(d.cases || []) })
    .catch(() => {})

  const loadCost = (d = days) => api.get('/agent/cost?days=' + d).then(setCost).catch(() => {})

  useEffect(() => {
    Promise.all([
      loadEvals(),
      loadCost(),
      api.get('/agent/cost/prices').then(setPrices).catch(() => {}),
    ]).finally(() => setLoaded(true))
  }, [])

  useEffect(() => { if (loaded) loadCost(days) }, [days]) // eslint-disable-line react-hooks/exhaustive-deps

  const runEval = async () => {
    if (withRun && !confirm('「真实运行」类用例会调用模型（花 token）并写入计划/任务表。\n建议只在临时库上跑。继续吗？')) return
    setRunning(true)
    try {
      const kinds = withRun ? ['intent', 'dialog', 'run'] : ['intent', 'dialog']
      const d = await api.post('/agent/evals', { kinds })
      setReport(d.eval)
      toast(`✅ 评测完成：${d.eval.passed}/${d.eval.total} 通过（${d.eval.pass_rate}%）`)
      loadEvals()
      loadCost()
    } catch (e) { toast(e.message) }
    finally { setRunning(false) }
  }

  const openEval = async (evalId) => {
    try {
      const d = await api.get('/agent/evals/' + evalId)
      setReport(d.eval)
    } catch (e) { toast(e.message) }
  }

  const casesByKind = useMemo(() => {
    const g = { intent: 0, dialog: 0, run: 0 }
    for (const c of cases) if (g[c.kind] !== undefined) g[c.kind] += 1
    return g
  }, [cases])

  if (!loaded) return <div className="loading">加载中…</div>

  const t = cost?.totals || {}

  return (
    <div className="eval-page">
      {/* ---------- 评测 ---------- */}
      <div className="card">
        <div className="eval-head">
          <h3>🧪 Agent 评测</h3>
          <div className="eval-actions">
            <label className="eval-check" title="真实运行会调模型、花 token，并写入计划/任务表">
              <input type="checkbox" checked={withRun} onChange={(e) => setWithRun(e.target.checked)} />
              含真实运行
            </label>
            <button className="btn primary" onClick={runEval} disabled={running}>
              {running ? '评测中…' : '▶ 跑一轮评测'}
            </button>
          </div>
        </div>
        <p className="muted eval-hint">
          用例集 {cases.length} 条（意图 {casesByKind.intent} · 多轮 {casesByKind.dialog} · 真实运行 {casesByKind.run}）。
          意图与多轮是纯规则用例，零 token 零写库；真实运行会调模型，请只在临时库上勾选。
        </p>

        {report && (
          <div className="eval-report">
            <div className="stat-grid">
              <div className="stat-chip"><span>通过率</span><b className={report.failed ? 'down' : 'up'}>{report.pass_rate}%</b></div>
              <div className="stat-chip"><span>通过 / 总数</span><b>{report.passed} / {report.total}</b></div>
              <div className="stat-chip"><span>Token</span><b>{num(report.total_tokens)}</b></div>
              <div className="stat-chip"><span>成本</span><b>{money(report.cost_cny)}</b></div>
            </div>
            {report.error && <div className="run-error">⚠️ {report.error}</div>}
            <div className="eval-cases">
              {report.results.map((r, i) => (
                <div key={i} className={`eval-case${r.passed ? '' : ' fail'}`}>
                  <div className="eval-case-top">
                    <span className="eval-case-icon">{r.passed ? '✅' : '❌'}</span>
                    <b>{r.case_name}</b>
                    <span className="badge" style={KIND_STYLE[r.kind] || {}}>{KIND_LABEL[r.kind] || r.kind}</span>
                    <span className="muted eval-latency">{r.detail?.latency_ms ?? 0} ms</span>
                  </div>
                  {!r.passed && (r.detail?.reasons || []).length > 0 && (
                    <ul className="eval-reasons">
                      {r.detail.reasons.map((s, j) => <li key={j}>{s}</li>)}
                    </ul>
                  )}
                  {r.passed && r.detail?.actual && (
                    <div className="muted eval-actual">
                      识别为 {INTENT_LABEL[r.detail.actual.intent] || r.detail.actual.intent}
                      {r.detail.actual.slots && Object.keys(r.detail.actual.slots).length > 0 &&
                        ' · ' + Object.entries(r.detail.actual.slots).map(([k, v]) => `${k}=${v}`).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="block-title">历史评测</div>
        {evals.length === 0 ? (
          <Empty text={'还没有跑过评测。\n点「跑一轮评测」即可（零成本，不花 token）'} />
        ) : (
          <div className="eval-history">
            {evals.map((e) => (
              <button
                key={e.eval_id}
                className={`eval-history-row${report?.eval_id === e.eval_id ? ' active' : ''}`}
                onClick={() => openEval(e.eval_id)}
              >
                <span className="status-dot" style={{ background: e.failed ? '#e5484d' : '#2e9e5b' }} />
                <span className="eval-history-rate">{e.pass_rate}%</span>
                <span className="muted">{e.passed}/{e.total}</span>
                <span className="muted">{num(e.total_tokens)} token</span>
                <span className="muted">{money(e.cost_cny)}</span>
                <span className="muted eval-history-time">{(e.started_at || '').slice(0, 16).replace('T', ' ')}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ---------- 成本看板 ---------- */}
      <div className="card">
        <div className="eval-head">
          <h3>💰 用量与成本</h3>
          <div className="tabbar" style={{ margin: 0 }}>
            {[7, 30, 90, 365].map((d) => (
              <button key={d} className={`tab-btn${days === d ? ' active' : ''}`} onClick={() => setDays(d)}>
                {d === 365 ? '一年' : d + ' 天'}
              </button>
            ))}
          </div>
        </div>
        <p className="muted eval-hint">📌 {cost?.price_note || ''}</p>

        {!cost || cost.totals.runs === 0 ? (
          <Empty text={'这段时间还没有 Agent 运行记录。\n去「Agent」页跑一次就会产生用量'} />
        ) : (
          <>
            <div className="stat-grid">
              <div className="stat-chip"><span>运行次数</span><b>{num(t.runs)}</b></div>
              <div className="stat-chip"><span>总 Token</span><b>{num(t.total_tokens)}</b></div>
              <div className="stat-chip"><span>总成本（估算）</span><b>{money(t.cost_cny)}</b></div>
              <div className="stat-chip"><span>平均每次 Token</span><b>{num(Math.round(t.avg_tokens))}</b></div>
              <div className="stat-chip"><span>输入 / 输出</span><b style={{ fontSize: 15 }}>{num(t.input_tokens)} / {num(t.output_tokens)}</b></div>
              <div className="stat-chip"><span>LLM 调用次数</span><b>{num(t.llm_calls)}</b></div>
              <div className="stat-chip"><span>平均延迟</span><b style={{ fontSize: 15 }}>{ms(Math.round(t.avg_latency_ms))}</b></div>
              <div className="stat-chip"><span>平均成本</span><b>{money(t.avg_cost_cny)}</b></div>
            </div>

            {cost.legacy_runs > 0 && (
              <div className="legacy-note">
                ℹ️ 有 {cost.legacy_runs} 次早期运行只记录了总 token，没有输入/输出分项，也没算成本 ——
                这些按 0 计入，不做推算。
              </div>
            )}

            <div className="grid grid-2" style={{ marginTop: 16 }}>
              <div>
                <div className="block-title">按天 Token</div>
                <Bars rows={cost.by_day.slice(-14)} valueKey="total_tokens" labelKey="date" format={num} emptyText="暂无数据" />
              </div>
              <div>
                <div className="block-title">按模型 Token</div>
                <Bars rows={cost.by_model} valueKey="total_tokens" labelKey="model" format={num} emptyText="暂无数据" />
              </div>
            </div>

            <div className="grid grid-2" style={{ marginTop: 16 }}>
              <div>
                <div className="block-title">按意图 Token</div>
                <Bars
                  rows={cost.by_intent.map((x) => ({ ...x, label: INTENT_LABEL[x.intent] || x.intent }))}
                  valueKey="total_tokens" labelKey="label" format={num} emptyText="暂无数据"
                />
              </div>
              <div>
                <div className="block-title">按模型成本</div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>模型</th><th>次数</th><th>Token</th><th>成本</th></tr>
                    </thead>
                    <tbody>
                      {cost.by_model.map((m) => (
                        <tr key={m.model}>
                          <td>{m.model}{!m.price_known && <span className="muted">（未收录单价）</span>}</td>
                          <td>{m.runs}</td>
                          <td>{num(m.total_tokens)}</td>
                          <td>{money(m.cost_cny)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="block-title">最近运行明细</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>开始时间</th><th>意图</th><th>模型</th><th>输入</th><th>输出</th>
                    <th>合计</th><th>调用</th><th>延迟</th><th>成本</th>
                  </tr>
                </thead>
                <tbody>
                  {cost.recent.map((r) => (
                    <tr key={r.run_id}>
                      <td className="muted">{(r.started_at || '').slice(5, 16).replace('T', ' ')}</td>
                      <td>{INTENT_LABEL[r.intent] || r.intent || '—'}</td>
                      <td>{r.model || '—'}</td>
                      <td>{r.detail_available ? num(r.input_tokens) : <span className="muted" title="早期运行没有分项数据">—</span>}</td>
                      <td>{r.detail_available ? num(r.output_tokens) : <span className="muted">—</span>}</td>
                      <td>{num(r.total_tokens)}</td>
                      <td>{r.llm_calls || '—'}</td>
                      <td>{r.latency_ms ? ms(r.latency_ms) : '—'}</td>
                      <td>{r.detail_available ? money(r.cost_cny) : <span className="muted">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {prices && (
          <>
            <div className="block-title">价目表（{prices.unit}）</div>
            <div className="price-table">
              {prices.items.map((p) => (
                <div key={p.model} className="price-row">
                  <span>{p.model}</span>
                  <span className="muted">输入 {p.input} · 输出 {p.output}</span>
                </div>
              ))}
              <div className="price-row">
                <span className="muted">未收录模型按默认价</span>
                <span className="muted">输入 {prices.default.input} · 输出 {prices.default.output}</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
