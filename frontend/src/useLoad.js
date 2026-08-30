import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { toast } from './toast.js'

// 加载数据的小 hook：data / loading / reload
export function useLoad(path, initial = null) {
  const [data, setData] = useState(initial)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const reload = useCallback(() => {
    setLoading(true)
    api.get(path)
      .then((d) => { setData(d); setError('') })
      .catch((e) => { setError(e.message); toast(e.message) })
      .finally(() => setLoading(false))
  }, [path])

  useEffect(() => { reload() }, [reload])
  return { data, loading, error, reload }
}

// 向某资源提交：save(path, payload, id?) —— 有 id 走 PUT，否则 POST
export async function saveResource(route, payload, id, reload) {
  try {
    const saved = id ? await api.put(`${route}/${id}`, payload) : await api.post(route, payload)
    toast(id ? '已保存' : '已添加')
    if (reload) reload()
    return saved
  } catch (e) {
    toast(e.message)
    return null
  }
}

export async function deleteResource(route, id, reload) {
  try {
    await api.del(`${route}/${id}`)
    toast('已删除')
    if (reload) reload()
    return true
  } catch (e) {
    toast(e.message)
    return false
  }
}
