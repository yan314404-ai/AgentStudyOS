// 极简全局轻提示，避免多层 prop 透传
const listeners = []
export function toast(msg) {
  listeners.forEach((f) => f(msg))
}
export function onToast(f) {
  listeners.push(f)
  return () => {
    const i = listeners.indexOf(f)
    if (i >= 0) listeners.splice(i, 1)
  }
}
