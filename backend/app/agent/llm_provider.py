"""Agent 用的 LLM 封装：全部委托给 app/llm.py 的多模型统一入口。

- chat()            委托 llm.chat_with_detail（多轮自由文本），累计 token / 成本 / 延迟
- structured_json() 委托 llm.structured_json_detail（三家统一，Claude 走抽取兜底），同样累计
- model              初始化即读当前活动模型（修复 agent_runs.model 存空串的问题）

公开接口（chat / structured_json / total_tokens / model）与旧版一致，
runtime / planner / reflector 零改动；新增 usage_snapshot() 给成本看板用。
"""
from .. import llm
from . import cost


class AgentLLM:
    def __init__(self, timeout: int = 90):
        self.timeout = timeout
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.latency_ms = 0
        self.calls = 0
        self.model = llm.active_model()  # run 建行时 model 就是活动模型

    def is_configured(self) -> bool:
        return llm.is_configured()

    # ---------- 记账 ----------
    def _account(self, usage: dict) -> None:
        self.calls += 1
        self.model = usage.get("model") or llm.active_model()
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        self.latency_ms += int(usage.get("latency_ms") or 0)

    def usage_snapshot(self) -> dict:
        """本次 run 的真实用量汇总（token 真值 + 成本估算），写进 token_usage_json。"""
        return cost.usage_summary(
            self.model, self.input_tokens, self.output_tokens,
            total_tokens=self.total_tokens, latency_ms=self.latency_ms,
        ) | {"llm_calls": self.calls}

    # ---------- 自由文本 ----------
    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        text, usage = llm.chat_with_detail(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            timeout=self.timeout,
        )
        self._account(usage)
        return text

    # ---------- 结构化 JSON ----------
    def structured_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        obj, usage = llm.structured_json_detail(
            system, user,
            temperature=temperature,
            timeout=self.timeout,
        )
        self._account(usage)
        return obj
