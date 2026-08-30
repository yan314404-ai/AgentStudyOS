"""Executor：逐条执行 plan.steps，是确定性核心（不碰 LLM）。

- 每个 step 校验并执行，写 tool_call / tool_result trace；失败记 error 事件，不静默
- read 工具的同参数去重由 registry 缓存兜底（返回 cached=True）
- 结果统一截断（trace.shorten ≤800 字），防 trace / 上下文膨胀
"""
import time


class Executor:
    def __init__(self, registry):
        self.registry = registry

    def run(self, state, plan: dict, trace, ctx=None) -> list:
        steps = (plan or {}).get("steps") or []
        results = []
        for step in steps:
            tool = step.get("tool")
            args = step.get("arguments") or {}
            trace.tool_call(tool, args)

            t0 = time.time()
            res = self.registry.execute(tool, args, ctx)
            cost_ms = int((time.time() - t0) * 1000)

            ok = res.get("ok", False)
            if ok:
                trace.tool_result(tool, res.get("data"), ok=True, cached=res.get("cached", False))
            else:
                err = res.get("error")
                trace.tool_result(tool, {"error": err}, ok=False)
                trace.error(f"{tool} 执行失败：{err}")

            results.append({
                "tool": tool,
                "args": args,
                "ok": ok,
                "data": res.get("data") if ok else None,
                "error": None if ok else res.get("error"),
                "cached": bool(res.get("cached", False)),
                "cost_ms": cost_ms,
            })
        return results
