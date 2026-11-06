"""Agent Runtime API：发起 run（单运行锁 + 后台线程）、轮询、历史、画像、取消。

- POST /run       发起一次 Agent 运行；已有 running 的 run 则 409
- GET  /run/{id}  轮询进度（状态 / 计划 / 逐步 trace / 最终回复 / token 用量）
- GET  /runs      历史列表
- GET/PUT /profile 读写 Agent 画像（存 settings 表）
- POST /run/{id}/cancel  取消运行（后台循环每轮检查 cancelled）

Phase 5 新增：
- POST /intent            只识别意图不发起 run（前端边打字边提示）
- POST /chat              多轮对话：识别意图 → 缺槽位追问 / 齐了就发起 run
- GET/POST /conversations 会话列表 / 新建
- GET  /conversations/{id} 会话详情（含 turn）
- POST /conversations/{id}/close 结束会话
- GET  /cost              成本看板（按天/按模型聚合 token 与花费）
- GET/POST /evals         评测历史 / 跑一轮评测
- GET  /evals/{eval_id}   单份评测报告
"""
import json
import threading

from fastapi import APIRouter, HTTPException

from ..agent import eval_runner
from ..agent import intent as intent_mod
from ..agent.repo import RunRepo, now
from ..agent.runtime import AgentRuntime
from ..agent.trace import TraceStore
from ..db import connect
from ..services import conversations as cvs
from ..services import memories as msvc
from ..services import plans as psvc
from ..services import usage as usage_svc

router = APIRouter(prefix="/api/agent", tags=["Agent"])

# 进程内启动锁：校验「无 running」+ 建行 两步原子化，防并发 POST 双跑
_LAUNCH_LOCK = threading.Lock()


def recover_stale_runs() -> int:
    """把遗留 running 置为 failed（启动时调用）。"""
    return RunRepo.recover_stale_runs()


def has_running_run() -> bool:
    """当前是否有 run 正在跑（给「关闭服务」判断能不能关）。"""
    return RunRepo.has_running()


def maybe_auto_review() -> str | None:
    """半自动提醒：有未复盘的过去计划且无 run 在跑 → 后台自动触发一次复盘 run。

    启动/打开 App 时由 lifespan 调用；best-effort，异常不打断启动。
    """
    try:
        target = psvc.find_unreviewed()
        if not target or RunRepo.has_running():
            return None
        goal = (
            f"复盘 {target['plan_date']} 的学习计划执行情况：用 get_plan_vs_actual 对比实际学习分钟与计划，"
            "判定是否计划过量/合理/不足，用 submit_review 提交 verdict 与待确认调整建议。"
        )
        run_id = AgentRuntime().run_async(goal, available_time=0)
        return run_id
    except Exception:  # noqa: BLE001 —— 自动复盘失败不应让后端启动崩掉
        return None


def _json_or_empty(raw: str) -> dict:
    try:
        obj = json.loads(raw or "")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------- settings 画像（复用现有 settings 表，不新增表） ----------
def _get_setting(key: str, default: str = "") -> str:
    conn = connect()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def _set_setting(key: str, value) -> None:
    conn = connect()
    conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit()
    conn.close()


# ---------- 运行 ----------
@router.post("/run")
def start_run(body: dict):
    goal = (body.get("goal") or "").strip()
    if not goal:
        raise HTTPException(400, "goal 不能为空")
    try:
        available_time = max(0, int(body.get("available_time") or 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "available_time 必须是数字")
    intent = (body.get("intent") or "").strip()

    with _LAUNCH_LOCK:
        if RunRepo.has_running():
            raise HTTPException(409, "Agent 正在执行中，请等待完成后再发起新的运行")
        run_id = AgentRuntime().run_async(goal, available_time, intent=intent)
    return {"run_id": run_id}


@router.get("/run/{run_id}")
def get_run(run_id: str):
    row = RunRepo.get(run_id)
    if not row:
        raise HTTPException(404, "run 不存在")
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "goal": row["goal"],
        "status": row["status"],
        "iteration": row["iteration"],
        "intent": row["intent"] or "",
        "error": row["error"] or "",
        "final_reply": row["final_reply"] or "",
        "planner_output": _json_or_empty(row["planner_output_json"]),
        "reflection": _json_or_empty(row["reflection_json"]),
        "token_usage": _json_or_empty(row["token_usage_json"]),
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "trace_events": TraceStore.summary(run_id),
    }


@router.get("/run/{run_id}/actions")
def run_actions(run_id: str):
    """该 run 的全部 Agent 写操作审计（agent_actions：参数 + before/after 快照）。"""
    row = RunRepo.get(run_id)
    if not row:
        raise HTTPException(404, "run 不存在")
    conn = connect()
    rows = conn.execute(
        "SELECT id, tool, args_json, before_json, after_json, ok, error, created_at "
        "FROM agent_actions WHERE run_id=? ORDER BY id",
        (run_id,),
    ).fetchall()
    conn.close()
    actions = []
    for r in rows:
        actions.append({
            "id": r["id"],
            "tool": r["tool"],
            "args": _json_or_empty(r["args_json"]),
            "before": _json_or_empty(r["before_json"]),
            "after": _json_or_empty(r["after_json"]),
            "ok": bool(r["ok"]),
            "error": r["error"] or "",
            "created_at": r["created_at"],
        })
    return {"run_id": run_id, "actions": actions}


@router.post("/run/{run_id}/cancel")
def cancel_run(run_id: str):
    row = RunRepo.get(run_id)
    if not row:
        raise HTTPException(404, "run 不存在")
    if row["status"] == "running":
        RunRepo.update(run_id, status="cancelled", finished_at=now())
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/runs")
def list_runs(limit: int = 20):
    return {"runs": RunRepo.list(limit=min(max(limit, 1), 100))}


# ---------- Agent 画像 ----------
@router.get("/profile")
def get_profile():
    return {
        "goal": _get_setting("agent_goal", ""),
        "available_time": int(_get_setting("agent_available_time", "3")),
        "target_date": _get_setting("agent_target_date", ""),
    }


@router.put("/profile")
def put_profile(body: dict):
    if "goal" in body:
        _set_setting("agent_goal", body["goal"])
    if "available_time" in body:
        try:
            _set_setting("agent_available_time", max(0, int(body["available_time"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "available_time 必须是数字")
    if "target_date" in body:
        _set_setting("agent_target_date", body["target_date"])
    return get_profile()


# ---------- Phase 3 闭环：跨天计划 + 复盘确认 ----------
@router.get("/plans")
def list_plans(date: str = ""):
    """计划列表（按日期倒序）或单计划（date=YYYY-MM-DD）。每份含 items + 实际分钟 + 复盘状态。"""
    date = (date or "").strip()
    if date:
        plan = psvc.get_plan(date)
        if not plan:
            raise HTTPException(404, "该日期没有计划")
        return {"plan": plan}
    return {"plans": psvc.list_plans(limit=10)}


@router.post("/plan/{plan_id}/confirm")
def confirm_plan(plan_id: int):
    """用户确认待确认的复盘调整：应用 adjust/remove/add/next_plan，每步写 agent_actions 审计。"""
    try:
        plan = psvc.confirm_review(plan_id)
    except psvc.BadRequest as e:
        raise HTTPException(400, str(e))
    return {"plan": plan}


@router.post("/plan/{plan_id}/reject")
def reject_plan(plan_id: int):
    """用户拒绝待确认的复盘调整：清空调整，review_status=rejected。"""
    try:
        plan = psvc.reject_review(plan_id)
    except psvc.BadRequest as e:
        raise HTTPException(400, str(e))
    return {"plan": plan}


# ---------- Phase 4 长期记忆（Agent 记住 → 用户确认 → 规划遵守） ----------
@router.get("/memories")
def list_memories():
    """记忆列表：pending(待确认) + active(已生效)，pending 在前、importance 降序。"""
    return {"memories": msvc.get_memories()}


@router.post("/memories/{memory_id}/confirm")
def confirm_memory(memory_id: int):
    """用户确认待确认的记忆：pending → active，之后注入规划。"""
    try:
        m = msvc.confirm_memory(memory_id)
    except msvc.BadRequest as e:
        raise HTTPException(400, str(e))
    return {"memory": m}


@router.post("/memories/{memory_id}/reject")
def reject_memory(memory_id: int):
    """用户拒绝待确认的记忆：pending → rejected，不参与规划。"""
    try:
        m = msvc.reject_memory(memory_id)
    except msvc.BadRequest as e:
        raise HTTPException(400, str(e))
    return {"memory": m}


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: int):
    """用户删除记忆（软删 forgotten，列表/注入都过滤）。"""
    msvc.forget_memory(memory_id)
    return {"ok": True}


@router.get("/reminder")
def reminder():
    """顶部横幅：是否有未复盘的过去计划 + 计划/实际分钟 + 偏差。"""
    plan = psvc.find_unreviewed()
    if not plan:
        return {
            "needs_review": False, "plan_date": "", "planned_total": 0,
            "actual_total": 0, "deviation_pct": 0, "verdict": "", "message": "",
        }
    diff = psvc.compute_plan_vs_actual(plan["plan_date"]) or {}
    planned = diff.get("planned_total") or plan["expected_total"]
    actual = diff.get("actual_total") or plan["actual_total"]
    return {
        "needs_review": True,
        "plan_date": plan["plan_date"],
        "planned_total": planned,
        "actual_total": actual,
        "deviation_pct": diff.get("deviation_pct"),
        "verdict": diff.get("verdict", ""),
        "review_status": plan["review_status"],
        "message": f"有未复盘的学习计划：计划 {planned} 分钟 / 实际 {actual} 分钟",
    }


# ---------- Phase 5 意图识别（零成本，供前端边打字边提示） ----------
@router.post("/intent")
def detect_intent(body: dict):
    """只识别意图，不发起 run、不写库、不花钱。前端输入框防抖调它做实时提示。"""
    text = (body.get("text") or "").strip()
    result = intent_mod.classify(text)
    result["describe"] = intent_mod.describe(result["intent"], result["slots"])
    result["question"] = intent_mod.next_question(result["intent"], result["missing"])
    result["goal_preview"] = intent_mod.build_goal(result["intent"], result["slots"])
    return result


# ---------- Phase 5 多轮对话 ----------
@router.get("/conversations")
def list_conversations(limit: int = 20):
    return {"conversations": cvs.list_conversations(limit=limit)}


@router.post("/conversations")
def create_conversation(body: dict = None):
    body = body or {}
    return {"conversation": cvs.create((body.get("conv_id") or "").strip())}


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str):
    conv = cvs.get(conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    return {"conversation": conv}


@router.post("/conversations/{conv_id}/close")
def close_conversation(conv_id: str):
    if not cvs.get(conv_id):
        raise HTTPException(404, "会话不存在")
    return {"conversation": cvs.close(conv_id)}


def _conv_write(conv_id: str, pending: dict | None, reply: str,
                intent: dict, run_id: str = "") -> None:
    """写挂起槽位 + 助手回复气泡。

    会话在用户输入到这一行之间被关掉（前端点「新会话」、多标签页）时，
    服务层会抛 BadRequest —— 这里翻译成 400，而不是让它变成 500。
    """
    try:
        cvs.set_pending(conv_id, pending)
        cvs.add_turn(conv_id, "assistant", reply, intent, run_id)
    except cvs.BadRequest as e:
        raise HTTPException(400, str(e))


@router.post("/chat")
def chat(body: dict):
    """一轮对话：识别意图 → 缺槽位就追问（挂起） / 齐了就发起 run。

    返回 action 三种取值，前端据此决定显示追问气泡还是跳去轮询 run：
    - "ask"     缺槽位，已挂起，question 是要问用户的话
    - "run"     槽位齐了，已发起 run，run_id 给前端轮询
    - "answer"  无需工具的普通对话（chat 意图），直接回一句
    """
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    try:
        conv = cvs.get_or_create((body.get("conv_id") or "").strip())
    except cvs.BadRequest as e:
        raise HTTPException(400, str(e))
    conv_id = conv["conv_id"]

    # 有挂起槽位时优先并入（用户是在回答上一轮追问）
    pending = conv.get("pending") or {}
    result = intent_mod.merge_pending(pending, text) if pending else intent_mod.classify(text)

    try:
        cvs.add_turn(conv_id, "user", text, result)
    except cvs.BadRequest as e:
        raise HTTPException(400, str(e))
    base = {
        "conv_id": conv_id,
        "intent": result["intent"],
        "label": result["label"],
        "confidence": result["confidence"],
        "slots": result["slots"],
        "missing": result["missing"],
        "describe": intent_mod.describe(result["intent"], result["slots"]),
    }

    # 1) 还缺槽位 → 追问并挂起
    if result["missing"]:
        question = intent_mod.next_question(result["intent"], result["missing"])
        _conv_write(conv_id, {"intent": result["intent"], "slots": result["slots"]},
                    question, {"kind": "ask"})
        return {**base, "action": "ask", "question": question, "run_id": ""}

    # 2) 普通对话 → 不花钱，直接回
    if result["intent"] == intent_mod.INTENT_CHAT:
        reply = "我主要负责学习计划：安排计划、复盘执行、记录学习时长、记住你的偏好。你可以直接说「安排明天的学习」。"
        _conv_write(conv_id, None, reply, {"kind": "answer"})
        return {**base, "action": "answer", "question": "", "reply": reply, "run_id": ""}

    # 3) 槽位齐了 → 发起 run
    goal = intent_mod.build_goal(result["intent"], result["slots"])
    try:
        available_time = max(0, int(body.get("available_time") or 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "available_time 必须是数字")
    with _LAUNCH_LOCK:
        if RunRepo.has_running():
            raise HTTPException(409, "Agent 正在执行中，请等待完成后再发起新的运行")
        run_id = AgentRuntime().run_async(goal, available_time, intent=result["intent"])
    _conv_write(conv_id, None, f"收到，开始{result['label']}：{goal}", {"kind": "run"}, run_id)
    return {**base, "action": "run", "question": "", "goal": goal, "run_id": run_id}


# ---------- Phase 5 成本看板 ----------
@router.get("/cost")
def cost_dashboard(days: int = 30):
    """用量与成本看板：总计 / 按天 / 按模型 / 按意图 / 最近 run 明细。"""
    return usage_svc.summary(days=days)


@router.get("/cost/prices")
def cost_prices():
    """当前价目表（标注「单价是常量、成本仅供量级参考」）。"""
    return usage_svc.price_table()


# ---------- Phase 5 评测 ----------
@router.get("/evals")
def list_evals(limit: int = 10):
    return {"evals": eval_runner.list_evals(limit=limit), "cases": eval_runner.list_cases()}


@router.post("/evals")
def run_eval(body: dict = None):
    """跑一轮评测。body.kinds 默认 ["intent","dialog"]（零成本）。

    传 ["intent","dialog","run"] 会真实跑 Agent —— 会花 token 且**会写业务表**，
    只在临时库上做（AGENT_STUDY_DB 指临时文件）。
    """
    body = body or {}
    kinds = body.get("kinds") or list(eval_runner.KINDS_CHEAP)
    if not isinstance(kinds, list):
        raise HTTPException(400, "kinds 必须是数组")
    bad = [k for k in kinds if k not in eval_runner.KINDS_ALL]
    if bad:
        raise HTTPException(400, f"未知用例类型：{'/'.join(bad)}（可选 {'/'.join(eval_runner.KINDS_ALL)}）")
    try:
        limit = max(0, int(body.get("limit") or 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "limit 必须是数字")
    return {"eval": eval_runner.run_eval(kinds=tuple(kinds), limit=limit)}


@router.get("/evals/{eval_id}")
def get_eval(eval_id: str):
    report = eval_runner.get_eval(eval_id)
    if not report:
        raise HTTPException(404, "评测不存在")
    return {"eval": report}
