"""统一工具注册表：注册 / 校验 / 执行。

- execute 永不抛异常：返回 {"ok": True, "data": ...} 或 {"ok": False, "error": "中文原因"}
- 参数失败（args_handler 抛 ValueError）与执行异常都如实上报，不静默吞掉
- read 工具带「同参数去重缓存」：一次 run 内重复调用同工具同参数 → 返回缓存，避免重复执行
"""
import json
from typing import Optional

from .schemas import Permission, ToolSpec


class ToolRegistry:
    def __init__(self):
        self._specs: dict[str, ToolSpec] = {}
        self._cache: dict[tuple, dict] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"工具 {spec.name} 已注册")
        self._specs[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._specs.get(name)

    def has(self, name: str) -> bool:
        return name in self._specs

    def names(self) -> list:
        return sorted(self._specs)

    def specs(self) -> list:
        return list(self._specs.values())

    def execute(self, tool: str, args: dict, ctx=None) -> dict:
        """执行工具。永不抛异常；返回 {ok, data} 或 {ok, error}（read 工具带去重缓存）。
        ctx 为 AgentContext（写工具用它记录审计快照），无则传 None。"""
        spec = self._specs.get(tool)
        if not spec:
            return {"ok": False, "error": f"未知工具：{tool}"}

        key = None
        if spec.permission == Permission.READ:
            key = (tool, json.dumps(args or {}, sort_keys=True, ensure_ascii=False))
            if key in self._cache:
                return {**self._cache[key], "cached": True}

        try:
            cleaned = spec.args_handler(args or {})
        except ValueError as e:
            # 参数校验失败也留一条 ok=0 审计（写工具），让「Agent 试过但被拒」可见；
            # 读工具无审计语义（不产生副作用）。
            if ctx is not None and spec.permission != Permission.READ:
                ctx.audit(spec.name, args or {}, {}, {}, ok=False, error=str(e))
            return {"ok": False, "error": str(e), "cached": False}
        try:
            data = spec.handler(cleaned, ctx)
            result = {"ok": True, "data": data, "cached": False}
        except ValueError as e:
            result = {"ok": False, "error": str(e), "cached": False}
        except Exception as e:  # noqa: BLE001 —— 工具执行异常必须如实上报，不能静默
            result = {"ok": False, "error": f"{tool} 执行异常：{e}", "cached": False}

        if key:
            self._cache[key] = result
        return result
