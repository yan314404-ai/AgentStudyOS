"""LLM 成本估算：把 API 返回的真实 token 数折算成人民币。

⚠️ 诚实标注（页面上也要写）：
- **token 数是真实的**，来自各家 API 响应的 usage 字段，不是猜的；
- **单价是常量**，按官网公开报价整理（人民币，2026-11 口径），只用于「量级参考」；
  各家随时调价，本机也没有账单对账能力，所以一律叫「估算」。

设计：单价按模型名前缀匹配（如 deepseek-reasoner 优先于 deepseek），
未收录的模型回退 DEFAULT_PRICE 并标 estimated=True，不静默编一个精确数字。
"""

# 模型名前缀 → (输入 元/百万 token, 输出 元/百万 token)
# 顺序有意义：更长的前缀放前面（deepseek-reasoner 要先于 deepseek 命中）
PRICING = [
    ("deepseek-reasoner", 4.0, 16.0),
    ("deepseek", 2.0, 8.0),
    ("gpt-4o-mini", 1.08, 4.32),
    ("gpt-4.1-nano", 0.72, 2.88),
    ("gpt-4.1-mini", 2.88, 11.52),
    ("gpt-4o", 18.0, 72.0),
    ("gpt-4.1", 14.4, 57.6),
    ("gpt-5", 9.0, 72.0),
    ("o3", 14.4, 57.6),
    ("o4-mini", 7.92, 31.68),
    ("claude-haiku", 5.76, 28.8),
    ("claude-opus", 108.0, 540.0),
    ("claude", 21.6, 108.0),
]

# 未收录模型按 DeepSeek 档位估，避免虚高；estimated=True 让前端标「估」
DEFAULT_PRICE = (2.0, 8.0)

NOTE = "token 为 API 返回的真实值，单价为公开报价整理值，成本仅供量级参考"


def price_for(model: str) -> tuple:
    """返回 (输入单价, 输出单价, 是否命中已知价目)。"""
    m = (model or "").strip().lower()
    if m:
        for prefix, pin, pout in PRICING:
            if m.startswith(prefix):
                return pin, pout, True
    return DEFAULT_PRICE[0], DEFAULT_PRICE[1], False


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """按输入/输出 token 分别计价，返回人民币元（保留 6 位，避免小额被抹成 0）。"""
    pin, pout, _ = price_for(model)
    cost = (max(0, int(input_tokens or 0)) / 1_000_000.0) * pin
    cost += (max(0, int(output_tokens or 0)) / 1_000_000.0) * pout
    return round(cost, 6)


def usage_summary(model: str, input_tokens: int, output_tokens: int,
                  total_tokens: int = 0, latency_ms: int = 0) -> dict:
    """统一的 usage 结构，写进 agent_runs.token_usage_json / 评测结果。"""
    it = max(0, int(input_tokens or 0))
    ot = max(0, int(output_tokens or 0))
    tt = max(0, int(total_tokens or 0)) or (it + ot)
    _, _, known = price_for(model)
    return {
        "model": (model or "").strip(),
        "input_tokens": it,
        "output_tokens": ot,
        "total_tokens": tt,
        "cost_cny": estimate_cost(model, it, ot),
        "price_known": known,
        "latency_ms": max(0, int(latency_ms or 0)),
    }
