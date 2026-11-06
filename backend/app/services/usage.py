"""用量与成本看板（Phase 5）。

数据来源只有一个：`agent_runs.token_usage_json`（Agent 每次 run 结束时由 runtime 写入，
含 model / input_tokens / output_tokens / total_tokens / cost_cny / price_known / latency_ms /
llm_calls）。**不做任何推算**——历史 run 没有明细字段就如实显示 0，并在返回里标注
`detail_available`，前端据此提示「早期 run 没有分项数据」，而不是拿 total 瞎拆。

为什么成本要单独做看板：
1. AI Agent 岗位 JD 里「成本/延迟优化」是明确要求，没有账就没法优化；
2. Agent 一轮 run 会调 3~5 次 LLM，token 涨得比聊天快一个量级，不做看板很容易失控；
3. 单价是公开报价的常量（见 agent/cost.py 的 NOTE），所以看板必须标注「量级参考」。
"""
import json
from datetime import date, datetime, timedelta

from ..agent import cost as cost_mod
from ..db import connect


def _loads(raw: str) -> dict:
    try:
        obj = json.loads(raw or "")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _rows(days: int) -> list:
    """取最近 N 天的 run（按 started_at 前缀匹配 YYYY-MM-DD，SQLite 字符串比较即可）。"""
    days = max(1, min(int(days or 30), 365))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT run_id, goal, status, model, intent, started_at, finished_at, token_usage_json "
            "FROM agent_runs WHERE started_at >= ? ORDER BY id DESC",
            (since,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _run_detail(row: dict) -> dict:
    """单条 run 的用量明细（缺字段如实给 0，不推算）。"""
    usage = _loads(row.get("token_usage_json") or "")
    total = int(usage.get("total_tokens") or 0)
    pin = int(usage.get("input_tokens") or 0)
    pout = int(usage.get("output_tokens") or 0)
    model = row.get("model") or usage.get("model") or ""
    detail_available = bool(usage.get("input_tokens") is not None and usage)
    cost = usage.get("cost_cny")
    if cost is None:
        # 老 run 没有成本字段：只有 total_tokens，不拆不分，直接按 0 记账并标不可用
        cost = 0.0
        detail_available = False
    return {
        "run_id": row["run_id"],
        "goal": row.get("goal") or "",
        "status": row.get("status") or "",
        "intent": row.get("intent") or "",
        "model": model,
        "input_tokens": pin,
        "output_tokens": pout,
        "total_tokens": total,
        "cost_cny": round(float(cost or 0), 6),
        "latency_ms": int(usage.get("latency_ms") or 0),
        "llm_calls": int(usage.get("llm_calls") or 0),
        "price_known": bool(usage.get("price_known", False)),
        "detail_available": detail_available,
        "started_at": row.get("started_at") or "",
        "finished_at": row.get("finished_at") or "",
    }


def summary(days: int = 30) -> dict:
    """成本看板总览：总计 + 按天 + 按模型 + 最近 run 明细。"""
    rows = _rows(days)
    details = [_run_detail(r) for r in rows]

    by_day = {}
    by_model = {}
    by_intent = {}
    totals = {"runs": len(details), "input_tokens": 0, "output_tokens": 0,
              "total_tokens": 0, "cost_cny": 0.0, "latency_ms": 0, "llm_calls": 0}
    for d in details:
        day = (d["started_at"] or "")[:10]
        slot = by_day.setdefault(day, {"date": day, "runs": 0, "total_tokens": 0,
                                       "cost_cny": 0.0, "latency_ms": 0})
        slot["runs"] += 1
        slot["total_tokens"] += d["total_tokens"]
        slot["cost_cny"] = round(slot["cost_cny"] + d["cost_cny"], 6)
        slot["latency_ms"] += d["latency_ms"]

        mkey = d["model"] or "(未记录)"
        mslot = by_model.setdefault(mkey, {"model": mkey, "runs": 0, "input_tokens": 0,
                                           "output_tokens": 0, "total_tokens": 0,
                                           "cost_cny": 0.0, "price_known": d["price_known"]})
        mslot["runs"] += 1
        mslot["input_tokens"] += d["input_tokens"]
        mslot["output_tokens"] += d["output_tokens"]
        mslot["total_tokens"] += d["total_tokens"]
        mslot["cost_cny"] = round(mslot["cost_cny"] + d["cost_cny"], 6)

        ikey = d["intent"] or "(未识别)"
        islot = by_intent.setdefault(ikey, {"intent": ikey, "runs": 0, "total_tokens": 0,
                                            "cost_cny": 0.0})
        islot["runs"] += 1
        islot["total_tokens"] += d["total_tokens"]
        islot["cost_cny"] = round(islot["cost_cny"] + d["cost_cny"], 6)

        for k in ("input_tokens", "output_tokens", "total_tokens", "latency_ms", "llm_calls"):
            totals[k] += d[k]
        totals["cost_cny"] = round(totals["cost_cny"] + d["cost_cny"], 6)

    totals["avg_tokens"] = round(totals["total_tokens"] / totals["runs"], 1) if totals["runs"] else 0
    totals["avg_cost_cny"] = round(totals["cost_cny"] / totals["runs"], 6) if totals["runs"] else 0
    totals["avg_latency_ms"] = round(totals["latency_ms"] / totals["runs"], 1) if totals["runs"] else 0

    return {
        "days": days,
        "totals": totals,
        "by_day": [by_day[k] for k in sorted(by_day)],
        "by_model": sorted(by_model.values(), key=lambda x: -x["total_tokens"]),
        "by_intent": sorted(by_intent.values(), key=lambda x: -x["total_tokens"]),
        "recent": details[:20],
        "price_note": cost_mod.NOTE,
        # 有没有 run 缺少分项数据（老数据），前端据此显示提示条
        "legacy_runs": sum(1 for d in details if not d["detail_available"]),
    }


def price_table() -> dict:
    """当前价目表（前端展示「这个单价怎么来的」）。"""
    return {
        "unit": "元 / 百万 token",
        "items": [
            {"model": model, "input": pin, "output": pout}
            for model, pin, pout in cost_mod.PRICING
        ],
        "default": {"input": cost_mod.DEFAULT_PRICE[0], "output": cost_mod.DEFAULT_PRICE[1]},
        "note": cost_mod.NOTE,
    }
