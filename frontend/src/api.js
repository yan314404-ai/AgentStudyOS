// 统一的 API 请求封装。开发模式走 vite 代理，生产模式同源 /api
async function request(method, path, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch('/api' + path, opts)
  } catch (e) {
    throw new Error('无法连接后端服务，请确认 启动.bat 已运行')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `${method} ${path} 失败(${res.status})`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b ?? {}),
  put: (p, b) => request('PUT', p, b ?? {}),
  del: (p) => request('DELETE', p),
}
