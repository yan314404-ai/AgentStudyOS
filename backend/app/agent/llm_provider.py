"""Agent 用的 LLM 封装：全部委托给 app/llm.py 的多模型统一入口。

- chat()            委托 llm.chat_with_usage（多轮自由文本），累计 token
- structured_json() 委托 llm.structured_json（三家统一，Claude 走抽取兜底），累计 token
- model              初始化即读当前活动模型（修复 agent_runs.model 存空串的问题）

公开接口（chat / structured_json / total_tokens / model）与旧版一致，
runtime / planner / reflector 零改动。
"""
from .. import llm


class AgentLLM:
    def __init__(self, timeout: int = 90):
        self.timeout = timeout
        self.total_tokens = 0
        self.model = llm.active_model()  # run 建行时 model 就是活动模型

    def is_configured(self) -> bool:
        return llm.is_configured()

    # ---------- 自由文本 ----------
    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        self.model = llm.active_model()
        text, tokens = llm.chat_with_usage(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            timeout=self.timeout,
        )
        self.total_tokens += tokens
        return text

    # ---------- 结构化 JSON ----------
    def structured_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        self.model = llm.active_model()
        obj, tokens = llm.structured_json(
            system, user,
            temperature=temperature,
            timeout=self.timeout,
        )
        self.total_tokens += tokens
        return obj
