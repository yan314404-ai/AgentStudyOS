import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'

// Phase 6 · 多模型设置：选供应商 + 模型 + API key + 测试连接。
// 全站只设一个全局模型：Agent / 聊天 / 周月报共用。key 只存本机 config.json，永不回传。

export default function Settings() {
  const [providers, setProviders] = useState([])   // 供应商元数据
  const [provider, setProvider] = useState('deepseek')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [models, setModels] = useState({})         // 每家各自已选的模型（切回时回填）
  const [hasKeys, setHasKeys] = useState({})       // 每家是否已存 key（tab 徽章）
  const [loaded, setLoaded] = useState(false)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testRes, setTestRes] = useState(null)     // { ok, msg } 或 null

  const load = () => api.get('/settings')
    .then((d) => {
      setProviders(d.providers || [])
      setProvider(d.provider || 'deepseek')
      setModel(d.model || '')
      setModels(d.models || {})
      setHasKeys(d.has_keys || {})
      setLoaded(true)
    })
    .catch(() => {})

  useEffect(() => { load() }, [])

  const cur = providers.find((p) => p.id === provider) || {}

  const switchProvider = (pid) => {
    setProvider(pid)
    setModel(models[pid] || '')   // 切回时保留该家上次选的模型
    setApiKey('')                 // key 永不回传，切换必清空
    setTestRes(null)
  }

  const test = async () => {
    if (!apiKey.trim()) return toast('请先输入该供应商的 API key')
    setTesting(true); setTestRes(null)
    try {
      const d = await api.post('/settings/test', { provider, api_key: apiKey.trim(), model: model.trim() })
      setTestRes(d.ok
        ? { ok: true, msg: `连接成功 · ${d.model || model || cur.default_model}` }
        : { ok: false, msg: d.error || '连接失败' })
    } catch (e) {
      setTestRes({ ok: false, msg: e.message })
    } finally { setTesting(false) }
  }

  const save = async () => {
    if (!apiKey.trim() && !model.trim()) return toast('填点内容再保存：API key 或模型名')
    setSaving(true)
    try {
      const d = await api.put('/settings', { provider, api_key: apiKey.trim(), model: model.trim() })
      toast(d.configured ? '已保存 ✅' : '已保存，但还没配 key，去对应平台拿一个吧')
      setApiKey('')
      setTestRes(null)
      load()
    } catch (e) { toast(e.message) } finally { setSaving(false) }
  }

  return (
    <div className="settings-page">
      <div className="card">
        <h3>🌐 模型供应商</h3>
        <p className="muted">
          所有 AI 功能（Agent 规划/复盘/总结、AI 助手、周月报）共用当前选中的模型；
          API key 只存本机 config.json，不会上传。
        </p>

        {!loaded ? <div className="loading">加载中…</div> : (
          <>
            <div className="tabbar">
              {providers.map((p) => (
                <button
                  key={p.id}
                  className={`tab-btn${provider === p.id ? ' active' : ''}`}
                  onClick={() => switchProvider(p.id)}
                >
                  {p.label}{hasKeys[p.id] ? ' ✅' : ''}
                </button>
              ))}
            </div>

            <div className="form-grid">
              <div className="field full">
                <label>模型</label>
                <input
                  list="model-list"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={cur.default_model || '输入模型名'}
                />
                <datalist id="model-list">
                  {(cur.suggested_models || []).map((m) => <option key={m} value={m} />)}
                </datalist>
                <div className="hint">常用模型已列出，也可以自由输入任何模型名</div>
              </div>

              <div className="field full">
                <label>API key{hasKeys[provider] ? '（当前已配置，留空则不修改）' : ''}</label>
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={hasKeys[provider] ? '已配置，留空则保留原 key' : `输入 ${cur.label || ''} API key`}
                />
                <div className="hint">
                  {cur.console_url
                    ? <a href={cur.console_url} target="_blank" rel="noreferrer">去哪拿 {cur.label} key？</a>
                    : 'key 只存本机 config.json，不会上传'}
                </div>
              </div>
            </div>

            <div className="row-actions">
              <button className="btn primary sm" onClick={save} disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
              <button className="btn ghost sm" onClick={test} disabled={testing}>
                {testing ? '测试中…' : '测试连接'}
              </button>
              <button className="btn ghost sm" onClick={() => setShowKey(!showKey)}>
                {showKey ? '🙈 隐藏 key' : '👁 显示 key'}
              </button>
            </div>

            {testRes && (
              <div className={`report-ai${testRes.ok ? '' : ' err'}`} style={{ marginTop: 14 }}>
                {testRes.ok ? '✅ ' : '⚠️ '}{testRes.msg}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
