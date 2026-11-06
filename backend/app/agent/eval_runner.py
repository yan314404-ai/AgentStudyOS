"""评测执行器：把内置用例集跑成一份可对比的评测报告。

三种用例成本差很大，所以分开跑（API 用 kinds 参数控制）：
- intent / dialog：纯规则，零 token、毫秒级、不写业务表 → 默认全跑
- run：真实跑一次 Agent，会花 token、**会写业务表（建计划/任务）** → 必须显式指定 kinds=["run"]

为什么自己写评测而不是只靠单测：
单测验证「代码按预期工作」，评测验证「Agent 在真实输入上的行为对不对」。
两者失败原因完全不同——提示词改动、模型换代、工具描述微调，单测全绿但评测会掉。
"""
import json
import uuid
from datetime import datetime

from ..db import connect
from . import eval_cases, intent as intent_mod

KINDS_CHEAP = ("intent", "dialog")
KINDS_ALL = ("intent", "dialog", "run")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_eval_id() -> str:
    return "ev" + uuid.uuid4().hex[:14]


# ---------- 用例入库（幂等） ----------
def seed_cases() -> int:
    """把内置用例写进 agent_eval_cases（按 name 幂等 upsert），返回用例总数。"""
    rows = eval_cases.case_rows()
    now = _now()
    conn = connect()
    try:
        for r in rows:
            exists = conn.execute(
                "SELECT id FROM agent_eval_cases WHERE name=?", (r["name"],)
            ).fetchone()
            payload = json.dumps(r["expect"], ensure_ascii=False)
            if exists:
                conn.execute(
                    "UPDATE agent_eval_cases SET kind=?, goal=?, available_time=?, expect_json=?, "
                    "note=?, updated_at=? WHERE id=?",
                    (r["kind"], r["goal"], r["available_time"], payload, r["note"], now,
                     exists["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO agent_eval_cases(name,kind,goal,available_time,expect_json,note,"
                    "enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?)",
                    (r["name"], r["kind"], r["goal"], r["available_time"], payload, r["note"],
                     now, now),
                )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) AS c FROM agent_eval_cases").fetchone()["c"]
    finally:
        conn.close()
    return total


def list_cases() -> list:
    """用例列表（含内置但未入库的提示）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_eval_cases ORDER BY kind, id"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "name": r["name"],
            "kind": r["kind"],
            "goal": r["goal"],
            "available_time": r["available_time"],
            "expect": _loads(r["expect_json"]),
            "note": r["note"] or "",
            "enabled": bool(r["enabled"]),
        })
    return out


def _loads(raw: str) -> dict:
    try:
        obj = json.loads(raw or "")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------- 判分 ----------
def _grade_intent(expect: dict, actual: dict) -> tuple:
    """返回 (passed, reasons)。expect 里出现哪些键就比哪些键。"""
    reasons = []
    exp = eval_cases.resolve_expected(expect)
    if "intent" in exp and actual.get("intent") != exp["intent"]:
        reasons.append(f"意图期望 {exp['intent']}，实际 {actual.get('intent')}")
    if "missing" in exp:
        if sorted(actual.get("missing") or []) != sorted(exp["missing"]):
            reasons.append(f"缺槽位期望 {exp['missing']}，实际 {actual.get('missing')}")
    if "confidence_min" in exp and actual.get("confidence", 0) < exp["confidence_min"]:
        reasons.append(f"置信度 {actual.get('confidence')} < 下限 {exp['confidence_min']}")
    if "confidence_max" in exp and actual.get("confidence", 0) > exp["confidence_max"]:
        reasons.append(f"置信度 {actual.get('confidence')} > 上限 {exp['confidence_max']}")
    slots = actual.get("slots") or {}
    for k, v in (exp.get("slots") or {}).items():
        if slots.get(k) != v:
            reasons.append(f"槽位 {k} 期望 {v!r}，实际 {slots.get(k)!r}")
    for k, needles in (exp.get("slots_contains") or {}).items():
        hay = str(slots.get(k) or "")
        for needle in needles:
            if needle not in hay:
                reasons.append(f"槽位 {k} 应包含 {needle!r}，实际 {hay!r}")
    return (not reasons, reasons)


def _grade_dialog(expect: dict, actual: dict) -> tuple:
    """多轮：expect.pending + expect.text → merge_pending → 与 want 比。"""
    reasons = []
    exp = eval_cases.resolve_expected(expect)
    want = exp.get("want") or {}
    if "intent" in want and actual.get("intent") != want["intent"]:
        reasons.append(f"意图期望 {want['intent']}，实际 {actual.get('intent')}")
    if "missing" in want:
        if sorted(actual.get("missing") or []) != sorted(want["missing"]):
            reasons.append(f"缺槽位期望 {want['missing']}，实际 {actual.get('missing')}")
    slots = actual.get("slots") or {}
    for k, v in (want.get("slots") or {}).items():
        if slots.get(k) != v:
            reasons.append(f"槽位 {k} 期望 {v!r}，实际 {slots.get(k)!r}")
    return (not reasons, reasons)


def _grade_run(expect: dict, run_row: dict, trace_events: list) -> tuple:
    """真实 run：看最终状态 + 调用过的工具 + token 数。"""
    reasons = []
    if expect.get("status") and run_row.get("status") != expect["status"]:
        reasons.append(f"状态期望 {expect['status']}，实际 {run_row.get('status')}")
    tools = [e.get("content", {}).get("tool") for e in trace_events
             if e.get("event_type") in ("tool_call", "observe")]
    for t in expect.get("tools_include") or []:
        if t not in tools:
            reasons.append(f"未调用期望工具 {t}（实际调用 {sorted(set(x for x in tools if x))}）")
    usage = _loads(run_row.get("token_usage_json") or "{}")
    if expect.get("min_tokens") and (usage.get("total_tokens") or 0) < expect["min_tokens"]:
        reasons.append(f"token {usage.get('total_tokens')} < 下限 {expect['min_tokens']}")
    return (not reasons, reasons)


# ---------- 执行 ----------
def _run_one(case: dict, kinds: tuple) -> dict:
    """跑一个用例，返回 {passed, detail, tokens, cost, latency}。"""
    kind = case["kind"]
    expect = _loads(case["expect_json"])
    started = datetime.now()
    detail = {}
    passed = False
    reasons = []

    if kind == "intent":
        actual = intent_mod.classify(case["goal"])
        passed, reasons = _grade_intent(expect, actual)
        detail = {"actual": actual}
    elif kind == "dialog":
        exp = eval_cases.resolve_expected(expect)
        actual = intent_mod.merge_pending(exp.get("pending") or {}, exp.get("text") or "")
        passed, reasons = _grade_dialog(expect, actual)
        detail = {"actual": actual}
    elif kind == "run":
        # 延迟 import：run 类会拉起真实 LLM，纯规则用例不该付这个代价
        from .repo import RunRepo
        from .runtime import AgentRuntime
        from .trace import TraceStore
        rt = AgentRuntime()
        run_id = rt.run(case["goal"], case["available_time"] or 0)
        row = RunRepo.get(run_id) or {}
        events = TraceStore.summary(run_id)
        passed, reasons = _grade_run(expect, row, events)
        usage = rt.llm.usage_snapshot()
        detail = {"run_id": run_id, "usage": usage, "status": row.get("status")}
    else:
        reasons = [f"未知用例类型 {kind}"]

    elapsed = int((datetime.now() - started).total_seconds() * 1000)
    detail["reasons"] = reasons
    detail["latency_ms"] = elapsed
    tokens = (detail.get("usage") or {}).get("total_tokens") or 0
    cost = (detail.get("usage") or {}).get("cost_cny") or 0.0
    return {"passed": passed, "detail": detail, "tokens": tokens, "cost": cost}


def run_eval(kinds=KINDS_CHEAP, limit: int = 0) -> dict:
    """跑一轮评测并落库，返回汇总。

    kinds 默认只跑零成本的 intent/dialog；传 ("intent","dialog","run") 才跑真实 Agent。
    run 类会写业务表，建议在临时库上跑（AGENT_STUDY_DB 指临时文件）。

    未知 kind 直接报错而不是静默过滤：调用方把 ("run",) 敲成 ("runs",) 时，
    静默兜底会跑一轮零成本用例并返回 100% —— 看起来「真实运行也过了」，实际根本没跑。
    """
    kinds = tuple(kinds or KINDS_CHEAP)
    bad = [k for k in kinds if k not in KINDS_ALL]
    if bad:
        raise ValueError(f"未知用例类型：{'/'.join(bad)}（可选 {'/'.join(KINDS_ALL)}）")
    seed_cases()
    conn = connect()
    try:
        placeholders = ",".join("?" for _ in kinds)
        rows = conn.execute(
            f"SELECT * FROM agent_eval_cases WHERE enabled=1 AND kind IN ({placeholders}) "
            "ORDER BY id",
            kinds,
        ).fetchall()
    finally:
        conn.close()
    cases = [dict(r) for r in rows]
    if limit and limit > 0:
        cases = cases[:limit]

    eval_id = new_eval_id()
    started_at = _now()
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO agent_eval_runs(eval_id,status,total,passed,failed,error,total_tokens,"
            "cost_cny,started_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eval_id, "running", len(cases), 0, 0, "", 0, 0.0, started_at, ""),
        )
        conn.commit()
    finally:
        conn.close()

    total_passed = 0
    total_tokens = 0
    total_cost = 0.0
    error = ""
    try:
        for case in cases:
            try:
                res = _run_one(case, kinds)
            except Exception as e:  # noqa: BLE001 —— 单个用例炸了不能毁整轮评测
                res = {"passed": False, "tokens": 0, "cost": 0.0,
                       "detail": {"reasons": [f"{type(e).__name__}: {e}"]}}
            total_passed += 1 if res["passed"] else 0
            total_tokens += res["tokens"]
            total_cost += res["cost"]
            conn = connect()
            try:
                conn.execute(
                    "INSERT INTO agent_eval_results(eval_id,case_id,case_name,kind,passed,"
                    "detail_json,created_at) VALUES(?,?,?,?,?,?,?)",
                    (eval_id, case["id"], case["name"], case["kind"],
                     1 if res["passed"] else 0,
                     json.dumps(res["detail"], ensure_ascii=False), _now()),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"

    failed = len(cases) - total_passed
    conn = connect()
    try:
        conn.execute(
            "UPDATE agent_eval_runs SET status=?, passed=?, failed=?, error=?, total_tokens=?, "
            "cost_cny=?, finished_at=? WHERE eval_id=?",
            ("failed" if error else "succeeded", total_passed, failed, error[:1000],
             total_tokens, round(total_cost, 6), _now(), eval_id),
        )
        conn.commit()
    finally:
        conn.close()

    return get_eval(eval_id)


def get_eval(eval_id: str) -> dict | None:
    """单份评测报告（含每条用例结果）。"""
    conn = connect()
    try:
        run = conn.execute("SELECT * FROM agent_eval_runs WHERE eval_id=?", (eval_id,)).fetchone()
        if not run:
            return None
        results = conn.execute(
            "SELECT * FROM agent_eval_results WHERE eval_id=? ORDER BY id", (eval_id,)
        ).fetchall()
    finally:
        conn.close()
    return {
        "eval_id": run["eval_id"],
        "status": run["status"],
        "total": run["total"],
        "passed": run["passed"],
        "failed": run["failed"],
        "pass_rate": round(run["passed"] / run["total"] * 100, 1) if run["total"] else 0.0,
        "error": run["error"] or "",
        "total_tokens": run["total_tokens"],
        "cost_cny": run["cost_cny"],
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "results": [
            {
                "case_id": r["case_id"],
                "case_name": r["case_name"],
                "kind": r["kind"],
                "passed": bool(r["passed"]),
                "detail": _loads(r["detail_json"]),
            }
            for r in results
        ],
    }


def list_evals(limit: int = 10) -> list:
    """历史评测列表（不含逐条结果，列表页用）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_eval_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "eval_id": r["eval_id"],
            "status": r["status"],
            "total": r["total"],
            "passed": r["passed"],
            "failed": r["failed"],
            "pass_rate": round(r["passed"] / r["total"] * 100, 1) if r["total"] else 0.0,
            "total_tokens": r["total_tokens"],
            "cost_cny": r["cost_cny"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
        }
        for r in rows
    ]
