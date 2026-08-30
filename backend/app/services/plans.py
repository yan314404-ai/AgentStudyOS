"""计划领域服务：跨天计划（Phase 3 闭环）的唯一来源。

计划 = 一天一份（agent_plans.plan_date UNIQUE），计划项关联任务（agent_plan_items.task_id）。
实际执行分钟**实时**从 task_sessions 聚合（确定性、诚实，不调 LLM）。
复盘调整走 review_status + adjustments_json：待确认（pending）→ 用户确认（confirm_review）后才生效。

写入口：
- create_plan    （Agent「安排」计划，直接生效 + 调用方审计）
- submit_review  （Agent 提交复盘，调整只记录不生效，待确认）
- confirm_review （用户确认，应用调整：adjust/remove/add/next_plan，每步写 agent_actions 审计）
- reject_review  （用户拒绝，清空调整）
"""
import json
from datetime import date, datetime

from .. import crud
from ..db import connect
from . import tasks as svc

# 调整动作白名单
ACTIONS = {"adjust", "remove", "add", "next_plan"}
# 偏差判定阈值：|偏差|<=20% 视为合理；<-20% 计划过量；>+20% 计划不足
VERDICT_THRESHOLD = 20


class BadRequest(ValueError):
    """参数不合法（计划领域）。"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_json(raw) -> list:
    try:
        obj = json.loads(raw or "[]")
        return obj if isinstance(obj, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _audit_row(run_id: str, tool: str, args: dict, before: dict, after: dict, ok=True, error=""):
    """写一条 agent_actions 审计（confirm 应用调整时使用；best-effort）。"""
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO agent_actions(run_id,tool,args_json,before_json,after_json,ok,error,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (run_id, tool,
             json.dumps(args, ensure_ascii=False), json.dumps(before, ensure_ascii=False),
             json.dumps(after, ensure_ascii=False), 1 if ok else 0, error, _now()),
        )
        conn.commit()
    except Exception:  # noqa: BLE001 —— 审计失败不能打断确认流程
        pass
    finally:
        conn.close()


def _plan_before(plan_date: str):
    """plan_date 之前最近的一份计划（供 prev_plan_id 计划链）。"""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, plan_date FROM agent_plans WHERE plan_date < ? ORDER BY plan_date DESC LIMIT 1",
            (plan_date,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def _get_plan_by_id(plan_id: int):
    conn = connect()
    try:
        row = conn.execute("SELECT plan_date FROM agent_plans WHERE id=?", (plan_id,)).fetchone()
    finally:
        conn.close()
    return get_plan(row["plan_date"]) if row else None


# ---------- 读 ----------
def get_plan(plan_date: str) -> dict | None:
    """计划详情：头 + 计划项（每项含该日实时实际分钟）+ 已解析的待确认调整。"""
    conn = connect()
    try:
        p = conn.execute("SELECT * FROM agent_plans WHERE plan_date=?", (plan_date,)).fetchone()
        if not p:
            return None
        rows = conn.execute(
            "SELECT * FROM agent_plan_items WHERE plan_id=? AND status='active' ORDER BY sort_order, id",
            (p["id"],),
        ).fetchall()
        items = []
        for it in rows:
            d = dict(it)
            d["actual_minutes"] = int(conn.execute(
                "SELECT COALESCE(SUM(minutes),0) FROM task_sessions WHERE task_id=? AND log_date=?",
                (d["task_id"], plan_date),
            ).fetchone()[0])
            items.append(d)
        out = dict(p)
        out["adjustments"] = _parse_json(out.get("adjustments_json") or "")
        out["expected_total"] = sum(i["expected_minutes"] for i in items)  # 实时重算为准
        out["actual_total"] = sum(i["actual_minutes"] for i in items)
        out["items"] = items
        return out
    finally:
        conn.close()


def compute_plan_vs_actual(plan_date: str) -> dict | None:
    """计划 vs 实际：确定性对比（任务级 SUM，诚实不编造）。无该日计划返回 None。"""
    plan = get_plan(plan_date)
    if not plan:
        return None
    planned = plan["expected_total"]
    actual = plan["actual_total"]
    dev_min = actual - planned
    dev_pct = round(dev_min / planned * 100) if planned else 0
    if dev_pct <= -VERDICT_THRESHOLD:
        verdict = "over"      # 计划过量（实际显著少于计划）
    elif dev_pct >= VERDICT_THRESHOLD:
        verdict = "under"     # 计划不足（实际显著多于计划）
    else:
        verdict = "ok"
    items = [{
        "task_id": i["task_id"],
        "title": i["title"],
        "expected": i["expected_minutes"],
        "actual": i["actual_minutes"],
        "diff": i["actual_minutes"] - i["expected_minutes"],
    } for i in plan["items"]]
    return {
        "plan_id": plan["id"],
        "plan_date": plan_date,
        "planned_total": planned,
        "actual_total": actual,
        "deviation_min": dev_min,
        "deviation_pct": dev_pct,
        "verdict": verdict,
        "items": items,
    }


def list_plans(limit: int = 10) -> list:
    """按日期倒序的计划列表（每份含实际分钟）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT plan_date FROM agent_plans ORDER BY plan_date DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [get_plan(r["plan_date"]) for r in rows]


def find_unreviewed(today: str = None) -> dict | None:
    """最久未复盘的过去计划（计划日早于今天、review_status=none、仍 active）。无则 None。"""
    today = today or date.today().isoformat()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT plan_date FROM agent_plans "
            "WHERE plan_date < ? AND review_status='none' AND status='active' "
            "ORDER BY plan_date ASC LIMIT 1",
            (today,),
        ).fetchone()
    finally:
        conn.close()
    return get_plan(row["plan_date"]) if row else None


# ---------- 写：计划（直接生效，调用方审计） ----------
def create_plan(plan_date: str, items: list, goal: str = "", reasoning_summary: str = "",
                run_id: str = "", prev_plan_id: int = None) -> dict:
    """按计划日 upsert 一份计划（直接生效）：头 + 重建计划项。

    items 每项必须含整数 task_id（Agent 先 create_task 拿 id 再建计划，链条自然）。
    用 UPDATE 而非 INSERT OR REPLACE，保住 plan_id 以维护 prev_plan_id 计划链。
    """
    plan_date = str(plan_date or "").strip()
    try:
        date.fromisoformat(plan_date)
    except ValueError:
        raise BadRequest("plan_date 必须是 YYYY-MM-DD")
    if not isinstance(items, list) or not items:
        raise BadRequest("items 不能为空")
    clean = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise BadRequest(f"items[{i}] 必须是对象")
        tid = it.get("task_id")
        if tid is None:
            raise BadRequest(f"items[{i}] 缺少 task_id（先 create_task 拿 id）")
        try:
            tid = int(tid)
        except (TypeError, ValueError):
            raise BadRequest(f"items[{i}] 的 task_id 必须是数字")
        task = crud.fetch_one("tasks", tid)
        if not task:
            raise BadRequest(f"items[{i}] 的 task_id={tid} 任务不存在")
        exp = it.get("expected_minutes") or 0
        try:
            exp = int(exp)
        except (TypeError, ValueError):
            raise BadRequest(f"items[{i}] 的 expected_minutes 必须是数字")
        if not (0 <= exp <= 1440):
            raise BadRequest(f"items[{i}] 的 expected_minutes 需在 0~1440 之间")
        clean.append({
            "task_id": tid,
            "title": (it.get("title") or task.get("title") or "").strip(),
            "category": (it.get("category") or task.get("category") or "").strip(),
            "kind": (it.get("kind") or "task").strip(),
            "expected_minutes": exp,
            "suggested_time": (it.get("suggested_time") or "").strip()[:50],
        })
    if prev_plan_id is None:
        prev = _plan_before(plan_date)
        prev_plan_id = prev["id"] if prev else None
    goal = str(goal or "")
    reasoning_summary = str(reasoning_summary or "")
    total = sum(i["expected_minutes"] for i in clean)
    conn = connect()
    try:
        existing = conn.execute("SELECT id FROM agent_plans WHERE plan_date=?", (plan_date,)).fetchone()
        now = _now()
        if existing:
            pid = existing["id"]
            # 重建计划 = 新的复盘周期：清掉旧的复盘状态
            conn.execute(
                "UPDATE agent_plans SET status='active', goal=?, reasoning_summary=?, run_id=?, "
                "prev_plan_id=?, expected_total=?, review_status='none', review_verdict='', "
                "review_reasoning='', review_run_id='', adjustments_json='[]', updated_at=? WHERE id=?",
                (goal, reasoning_summary, run_id, prev_plan_id, total, now, pid),
            )
            conn.execute("DELETE FROM agent_plan_items WHERE plan_id=?", (pid,))
        else:
            cur = conn.execute(
                "INSERT INTO agent_plans(plan_date,status,goal,reasoning_summary,run_id,prev_plan_id,"
                "expected_total,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (plan_date, "active", goal, reasoning_summary, run_id, prev_plan_id, total, now, now),
            )
            pid = cur.lastrowid
        for i, it in enumerate(clean):
            conn.execute(
                "INSERT INTO agent_plan_items(plan_id,task_id,title,category,kind,expected_minutes,suggested_time,status,sort_order) "
                "VALUES(?,?,?,?,?,?,?,'active',?)",
                (pid, it["task_id"], it["title"], it["category"], it["kind"],
                 it["expected_minutes"], it["suggested_time"], i),
            )
        conn.commit()
    finally:
        conn.close()
    return get_plan(plan_date)


# ---------- 写：复盘（待确认，不生效） ----------
def _validate_adjustments(adjustments) -> list:
    """校验调整列表：action ∈ ACTIONS + 必填字段。返回干净列表。"""
    if adjustments is None:
        return []
    if not isinstance(adjustments, list):
        raise BadRequest("adjustments 必须是数组")
    out = []
    for i, a in enumerate(adjustments):
        if not isinstance(a, dict):
            raise BadRequest(f"adjustments[{i}] 必须是对象")
        action = (a.get("action") or "").strip()
        if action not in ACTIONS:
            raise BadRequest(f"adjustments[{i}] 的 action 必须是 {'/'.join(sorted(ACTIONS))} 之一")
        item = {"action": action}
        if action == "adjust":
            if a.get("item_id") is None:
                raise BadRequest("adjust 缺少 item_id")
            if a.get("expected_minutes") is None:
                raise BadRequest("adjust 缺少 expected_minutes")
            item["item_id"] = int(a["item_id"])
            item["expected_minutes"] = int(a["expected_minutes"])
        elif action == "remove":
            if a.get("item_id") is None:
                raise BadRequest("remove 缺少 item_id")
            item["item_id"] = int(a["item_id"])
        elif action == "add":
            title = (a.get("title") or "").strip()
            if not title:
                raise BadRequest("add 缺少 title")
            item["title"] = title
            item["category"] = (a.get("category") or "").strip()
            item["kind"] = (a.get("kind") or "task").strip()
            item["expected_minutes"] = int(a.get("expected_minutes") or 0)
        elif action == "next_plan":
            pd = (a.get("plan_date") or "").strip()
            if not pd:
                raise BadRequest("next_plan 缺少 plan_date")
            try:
                date.fromisoformat(pd)
            except ValueError:
                raise BadRequest("next_plan 的 plan_date 必须是 YYYY-MM-DD")
            items = a.get("items")
            if not isinstance(items, list) or not items:
                raise BadRequest("next_plan 缺少 items")
            clean_items = []
            for j, it in enumerate(items):
                if not isinstance(it, dict) or not (it.get("title") or "").strip():
                    raise BadRequest(f"next_plan.items[{j}] 需要 title")
                clean_items.append({
                    "title": (it["title"] or "").strip(),
                    "category": (it.get("category") or "").strip(),
                    "expected_minutes": int(it.get("expected_minutes") or 0),
                })
            item["plan_date"] = pd
            item["items"] = clean_items
        out.append(item)
    return out


def submit_review(plan_date: str, verdict: str, reasoning: str = "",
                  adjustments: list = None, run_id: str = "") -> dict:
    """提交复盘：记录 verdict + 待确认调整（不生效）。"""
    plan_date = str(plan_date or "").strip()
    if not plan_date:
        raise BadRequest("缺少必填参数 plan_date")
    plan = get_plan(plan_date)
    if not plan:
        raise BadRequest("该日期没有计划，无法复盘")
    verdict = (verdict or "").strip()
    if not verdict:
        raise BadRequest("缺少必填参数 verdict")
    reasoning = (reasoning or "").strip()
    adj = _validate_adjustments(adjustments)
    conn = connect()
    try:
        conn.execute(
            "UPDATE agent_plans SET status='pending', review_status='pending', review_verdict=?, "
            "review_reasoning=?, review_run_id=?, adjustments_json=?, updated_at=? WHERE id=?",
            (verdict, reasoning, run_id, json.dumps(adj, ensure_ascii=False), _now(), plan["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return get_plan(plan_date)


# ---------- 写：确认 / 拒绝（用户手动） ----------
def _apply_adjustment(plan: dict, adj: dict, run_marker: str) -> None:
    action = adj["action"]
    if action == "adjust":
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_plan_items WHERE id=? AND plan_id=?", (adj["item_id"], plan["id"])
            ).fetchone()
            if not row:
                raise BadRequest(f"调整项 {adj['item_id']} 不存在")
            before = {"item_id": row["id"], "expected_minutes": row["expected_minutes"]}
            conn.execute("UPDATE agent_plan_items SET expected_minutes=? WHERE id=?",
                         (adj["expected_minutes"], row["id"]))
            after = {"item_id": row["id"], "expected_minutes": adj["expected_minutes"]}
            conn.commit()
        finally:
            conn.close()
        _audit_row(run_marker, "confirm:adjust", adj, before, after)
    elif action == "remove":
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_plan_items WHERE id=? AND plan_id=?", (adj["item_id"], plan["id"])
            ).fetchone()
            if not row:
                raise BadRequest(f"调整项 {adj['item_id']} 不存在")
            before = {"item_id": row["id"], "title": row["title"]}
            conn.execute("UPDATE agent_plan_items SET status='removed' WHERE id=?", (row["id"],))
            after = {"item_id": row["id"], "status": "removed"}
            conn.commit()
        finally:
            conn.close()
        _audit_row(run_marker, "confirm:remove", adj, before, after)
    elif action == "add":
        task = svc.create_task({
            "title": adj["title"],
            "category": adj.get("category") or "",
            "note": "🤖 复盘调整（已确认）",
        })
        conn = connect()
        try:
            cur = conn.execute(
                "INSERT INTO agent_plan_items(plan_id,task_id,title,category,kind,expected_minutes,status,sort_order) "
                "VALUES(?,?,?,?,?,?,'active',(SELECT COALESCE(MAX(sort_order),0)+1 FROM agent_plan_items WHERE plan_id=?))",
                (plan["id"], task["id"], task["title"], adj.get("category") or "",
                 adj.get("kind") or "task", adj["expected_minutes"], plan["id"]),
            )
            item_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        _audit_row(run_marker, "confirm:add", adj, {},
                   {"task_id": task["id"], "item_id": item_id, "title": task["title"]})
    elif action == "next_plan":
        items = []
        for it in adj.get("items") or []:
            task = svc.create_task({
                "title": it["title"],
                "category": it.get("category") or "",
                "note": "🤖 复盘调整（已确认）",
            })
            items.append({
                "task_id": task["id"], "title": task["title"],
                "category": it.get("category") or "", "expected_minutes": it["expected_minutes"],
                "kind": it.get("kind") or "task",
            })
        new_plan = create_plan(
            adj["plan_date"], items,
            goal=plan.get("goal") or "",
            reasoning_summary=f"由复盘调整生成（源计划 {plan['plan_date']}）",
            run_id=run_marker, prev_plan_id=plan["id"],
        )
        _audit_row(run_marker, "confirm:next_plan", adj,
                   {"plan_date": plan["plan_date"]},
                   {"plan_date": adj["plan_date"], "plan_id": new_plan["id"]})


def confirm_review(plan_id: int, audit_run_id: str = "") -> dict:
    """应用待确认调整（用户确认）：每步审计，最后计划 reviewed + review_status=applied。"""
    plan = _get_plan_by_id(plan_id)
    if not plan:
        raise BadRequest("计划不存在")
    if plan["review_status"] != "pending":
        raise BadRequest("该计划没有待确认的复盘调整")
    run_marker = audit_run_id or (plan.get("review_run_id") or f"confirm:{plan_id}")
    for a in plan.get("adjustments") or []:
        _apply_adjustment(plan, a, run_marker)
    conn = connect()
    try:
        conn.execute(
            "UPDATE agent_plans SET review_status='applied', status='reviewed', updated_at=? WHERE id=?",
            (_now(), plan_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_plan(plan["plan_date"])


def reject_review(plan_id: int) -> dict:
    """拒绝待确认调整：清空调整，review_status=rejected。"""
    plan = _get_plan_by_id(plan_id)
    if not plan:
        raise BadRequest("计划不存在")
    if plan["review_status"] != "pending":
        raise BadRequest("该计划没有待确认的复盘调整")
    conn = connect()
    try:
        conn.execute(
            "UPDATE agent_plans SET review_status='rejected', adjustments_json='[]', updated_at=? WHERE id=?",
            (_now(), plan_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_plan(plan["plan_date"])
