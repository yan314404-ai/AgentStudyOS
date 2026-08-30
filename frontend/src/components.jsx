import React, { useEffect } from 'react'

// 进度条
export function ProgressBar({ value, max = 100, color, sm }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  return (
    <div className={`progress-track${sm ? ' sm' : ''}`}>
      <div className={`progress-fill${color ? ' ' + color : ''}`} style={{ width: pct + '%' }} />
    </div>
  )
}

// 状态标签
export function Pill({ text }) {
  const cls = ['待开始', '进行中', '已完成', '已延期', '高', '中', '低', '简单', '中等', '困难',
    'm1', 'm2', 'm3', 'm4', 'm5'].includes(text) ? text : ''
  return <span className={`pill ${cls}`}>{text}</span>
}

// 弹窗
export function Modal({ title, children, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}

// 轻提示
export function Toast({ message }) {
  if (!message) return null
  return <div className="toast">{message}</div>
}

// 空状态
export function Empty({ text }) {
  return <div className="empty">🌱 {text || '暂无数据'}</div>
}

// 确认删除（带颜色）
export function DangerBtn({ onClick, label = '删除' }) {
  return (
    <button className="btn danger sm" onClick={onClick}>{label}</button>
  )
}
