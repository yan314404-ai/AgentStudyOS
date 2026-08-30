"""Reflector：根据观察 + 计划 + 执行结果，判定目标是否完成、是否重规划。

返回结构固定为：
  {"goal_completed": bool, "need_replan": bool, "reason": str, "next_action": str}
"""
import json

from .prompts import load


class Reflector:
    def __init__(self, llm):
        self.llm = llm

    def reflect(self, goal: str, state) -> dict:
        system = load("reflector")
        user = self._build_user(goal, state)
        obj = self.llm.structured_json(system, user)
        return self._normalize(obj)

    # ---------- 组装 ----------
    def _build_user(self, goal: str, state) -> str:
        obs = {
            name: (res.get("data") if res.get("ok") else {"error": res.get("error")})
            for name, res in (state.observations or {}).items()
        }
        actions = [
            {k: a.get(k) for k in ("tool", "ok", "error", "cached")}
            for a in (state.executed_actions or [])
        ]
        return (
            f"目标：{goal}\n\n"
            f"【观察摘要】\n{json.dumps(obs, ensure_ascii=False)}\n\n"
            f"【本轮计划】\n{json.dumps(state.current_plan or {}, ensure_ascii=False)}\n\n"
            f"【执行结果】\n{json.dumps(actions, ensure_ascii=False)}\n\n"
            "请输出 JSON。"
        )

    # ---------- 规范化 ----------
    @staticmethod
    def _normalize(obj: dict) -> dict:
        if not isinstance(obj, dict):
            raise ValueError("Reflector 输出不是 JSON 对象")
        return {
            "goal_completed": bool(obj.get("goal_completed")),
            "need_replan": bool(obj.get("need_replan")),
            "reason": str(obj.get("reason") or "")[:200],
            "next_action": str(obj.get("next_action") or "")[:200],
        }
