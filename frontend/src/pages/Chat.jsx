import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { toast } from '../toast.js'
import { Empty } from '../components.jsx'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [configured, setConfigured] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const bodyRef = useRef(null)

  // 挂载：恢复历史 + 看 key 是否已配置
  useEffect(() => {
    api.get('/chat/history').then((r) => setMessages(r || [])).catch(() => {}).finally(() => setLoaded(true))
    api.get('/config').then((d) => setConfigured(d.configured)).catch(() => {})
  }, [])

  // 新消息自动滚到底
  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, sending])

  const send = async () => {
    const content = input.trim()
    if (!content || sending) return
    setMessages((m) => [...m, { id: 'local-' + Date.now(), role: 'user', content, created_at: new Date().toLocaleString('zh-CN', { hour12: false }) }])
    setInput('')
    setSending(true)
    try {
      const d = await api.post('/chat/message', { content })
      if (d.ok) {
        setMessages((m) => [...m, { role: 'assistant', content: d.reply, created_at: new Date().toLocaleString('zh-CN', { hour12: false }) }])
      } else {
        if (d.reason === 'not_configured') {
          setConfigured(false)
          setMessages((m) => [...m, { err: true, role: 'assistant', content: '还没有配置模型 API key —— 点上方按钮去「设置」页配置后就能聊了。', created_at: '' }])
        } else {
          setMessages((m) => [...m, { err: true, role: 'assistant', content: '⚠️ ' + (d.error || '发送失败'), created_at: '' }])
        }
      }
    } catch (e) {
      setMessages((m) => [...m, { err: true, role: 'assistant', content: '⚠️ ' + e.message, created_at: '' }])
    } finally {
      setSending(false)
    }
  }

  const clear = async () => {
    if (!messages.length) return toast('对话是空的')
    if (!confirm('清空全部聊天记录？')) return
    try {
      await api.del('/chat/clear')
      setMessages([])
      toast('已清空')
    } catch (e) { toast(e.message) }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat-page">
      {!configured && (
        <div className="chat-hint">
          <span>📌 聊天需要模型 API key —— </span>
          <button className="btn primary sm" onClick={() => { window.location.hash = '#/settings' }}>去设置页配置</button>
        </div>
      )}

      <div className="card chat-body" ref={bodyRef}>
        {!loaded ? <div className="loading">加载中…</div> :
          messages.length === 0 ? (
            <Empty text={'我是你的学习助手，已接入你的学习数据。试试问我：\n「我这周学得怎么样？」\n「帮我看看这个月有什么问题」\n「接下来该优先做什么？」'} />
          ) : messages.map((m, i) => (
            <div key={m.id ?? i} className={`chat-msg ${m.role}${m.err ? ' err' : ''}`}>
              <div className="bubble">{m.content}</div>
              {m.created_at && <div className="time">{m.created_at}</div>}
            </div>
          ))}
        {sending && <div className="chat-msg assistant"><div className="bubble typing">AI 思考中…</div></div>}
      </div>

      <div className="chat-input">
        <textarea
          rows={2}
          placeholder="问点什么，Enter 发送 / Shift+Enter 换行"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
        />
        <button className="btn primary" onClick={send} disabled={sending || !input.trim()}>{sending ? '发送中…' : '发送'}</button>
        <button className="btn ghost" onClick={clear} title="清空对话">🗑️</button>
      </div>
    </div>
  )
}
