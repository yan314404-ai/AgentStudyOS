"""Planner：把目标 + 观察摘要交给 LLM，产出结构化行动计划（只输出，不落库、不执行）。

返回结构固定为：
  {"goal": str, "reasoning_summary": str, "steps": [{"tool": str, "arguments": dict}]}

steps 的工具名必须在本 run 的注册表内，planner 做校验：结构损坏或引用未知工具 → ValueError(中文)。
"""
import json

from .prompts import load
from .registry import ToolRegistry


class Planner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, goal: str, state, registry: ToolRegistry) -> dict:
        system = load("planner")
        user = self._build_user(goal, state, registry)
        obj = self.llm.structured_json(system, user)
        return self._validate(obj, registry, goal)

    # ---------- 组装 ----------
    def _build_user(self, goal: str, state, registry: ToolRegistry) -> str:
        today = state.current_date or ""
        # 按 category 分组列出，方便 LLM 理解工具用途
        groups: dict = {}
        for s in registry.specs():
            groups.setdefault(s.category, []).append(s)
        lines = []
        for cat in sorted(groups):
            lines.append(f"[{cat}]")
            for s in groups[cat]:
                lines.append(
                    f"- {s.name}: {s.description} | 参数: {json.dumps(s.input_schema, ensure_ascii=False)}"
                )
        tools = "\n".join(lines)
        obs = {
            name: (res.get("data") if res.get("ok") else {"error": res.get("error")})
            for name, res in (state.observations or {}).items()
        }
        return (
            f"今天的日期：{today}\n"
            f"用户目标：{goal}\n"
            f"每天可用学习时间（小时）：{state.available_time}\n\n"
            f"【已观察到的学习数据】\n{json.dumps(obs, ensure_ascii=False)}\n\n"
            f"【可用工具】\n{tools}\n\n"
            "请输出 JSON。"
        )

    # ---------- 校验 ----------
    def _validate(self, obj: dict, registry: ToolRegistry, goal: str) -> dict:
        if not isinstance(obj, dict):
            raise ValueError("Planner 输出不是 JSON 对象")
        steps = obj.get("steps")
        if not isinstance(steps, list):
            raise ValueError("Planner 输出缺少 steps 数组")
        cleaned = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Planner 输出 steps[{i}] 不是对象")
            tool = step.get("tool")
            if not isinstance(tool, str) or not tool:
                raise ValueError(f"Planner 输出 steps[{i}] 缺少 tool")
            if not registry.has(tool):
                raise ValueError(f"Planner 引用了未知工具：{tool}")
            arguments = step.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ValueError(f"Planner 输出 steps[{i}] 的 arguments 必须是对象")
            cleaned.append({"tool": tool, "arguments": arguments})
        return {
            "goal": (obj.get("goal") or goal),
            "reasoning_summary": str(obj.get("reasoning_summary") or "")[:200],
            "steps": cleaned,
        }
