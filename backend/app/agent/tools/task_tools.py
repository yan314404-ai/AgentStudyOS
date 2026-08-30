"""任务写工具：全部直接生效 + AgentContext 审计（before/after 快照兜底）。

全直接模式：create_task / add_session / update_task / complete_task / create_review_task
都立即写入数据库；每次写操作由 ctx.audit 记录到 agent_actions，before 快照即可回滚依据。
业务不变量走 app/services/tasks.py（与手动页面同一套行为）。
"""
from ... import crud
from ...services import tasks as svc

# create_task 允许写入的字段白名单（crud 还有一层表级白名单兜底）
CREATE_TASK_ALLOWED = {
    "phase", "category", "title", "description", "resource",
    "start_date", "due_date", "priority", "status", "hours", "note",
}


def _compact_task(row: dict) -> dict:
    """任务行 → 紧凑快照（审计与返回用；含回滚所需字段）。"""
    return {
        "task_id": row["id"],
        "title": row["title"],
        "phase": row.get("phase") or "",
        "category": row.get("category") or "",
        "status": row.get("status") or "",
        "progress": row.get("progress") or 0,
        "spent_minutes": row.get("spent_minutes") or 0,
        "manual_progress": row.get("manual_progress"),
    }


def _audit(ctx, tool: str, args: dict, before: dict, after: dict, ok=True, error=""):
    if ctx is not None:
        ctx.audit(tool, args, before, after, ok=ok, error=error)


# ---------- 读 ----------
def get_task_list(args: dict, ctx=None) -> dict:
    """学习路线任务列表（可指定 phase 过滤）。只返回规划需要的字段。"""
    phase = (args.get("phase") or "").strip()
    if phase:
        rows = crud.fetch_all("tasks", where="phase=?", params=(phase,), order="id")
    else:
        rows = crud.fetch_all("tasks", order="id")
    tasks = []
    for t in rows:
        tasks.append({
            "id": t["id"],
            "phase": t["phase"],
            "category": t["category"],
            "title": t["title"],
            "progress": t["progress"],
            "status": t["status"],
            "hours": t["hours"],
            "start_date": t["start_date"],
            "due_date": t["due_date"],
            "mode": "manual" if (t.get("manual_progress") is not None and t["manual_progress"] >= 0) else "auto",
        })
    return {"count": len(tasks), "tasks": tasks}


# ---------- 写（直接生效 + 审计） ----------
def validate_create_task(args: dict) -> dict:
    """参数校验 + 清洗：title 必填；hours 必须数字。失败抛 ValueError(中文)。"""
    args = dict(args or {})
    title = (args.get("title") or "").strip()
    if not title:
        raise ValueError("create_task 缺少必填参数 title")
    args["title"] = title
    if "hours" in args and args.get("hours") is not None:
        try:
            args["hours"] = float(args["hours"])
        except (TypeError, ValueError):
            raise ValueError("create_task 参数 hours 必须是数字")
    return args


def create_task(args: dict, ctx=None) -> dict:
    """创建学习任务（直接生效，不再待确认）。note 打标 🤖 Agent 创建。"""
    try:
        data = {k: v for k, v in args.items() if k in CREATE_TASK_ALLOWED}
        data["title"] = (args.get("title") or "").strip()
        note = (data.get("note") or "").strip()
        data["note"] = ("🤖 Agent 创建。" + note).strip() if note else "🤖 Agent 创建"
        row = svc.create_task(data)
        after = _compact_task(row)
        _audit(ctx, "create_task", args, {}, after)
        return {**after, "message": "已创建（直接生效）"}
    except Exception as e:  # noqa: BLE001 —— 写失败也要留审计
        _audit(ctx, "create_task", args, {}, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_add_session(args: dict) -> dict:
    """参数校验 + 清洗：task_id / minutes 必填。失败抛 ValueError(中文)。"""
    args = dict(args or {})
    tid = args.get("task_id")
    if tid is None:
        raise ValueError("add_session 缺少必填参数 task_id")
    try:
        args["task_id"] = int(tid)
    except (TypeError, ValueError):
        raise ValueError("add_session 参数 task_id 必须是数字")
    if "minutes" not in args:
        raise ValueError("add_session 缺少必填参数 minutes")
    try:
        args["minutes"] = int(args["minutes"])
    except (TypeError, ValueError):
        raise ValueError("add_session 参数 minutes 必须是数字")
    if args.get("note"):
        args["note"] = str(args["note"]).strip()
    if args.get("log_date"):
        args["log_date"] = str(args["log_date"]).strip()
    return args


def add_session(args: dict, ctx=None) -> dict:
    """给任务记一笔学习时间（直接生效）：累加 spent_minutes + 重算进度 + 同步当天打卡。"""
    tid = args["task_id"]
    existing = crud.fetch_one("tasks", tid)
    before = _compact_task(existing) if existing else {}
    try:
        result = svc.add_session(
            tid,
            args["minutes"],
            note=args.get("note") or "",
            log_date=args.get("log_date") or None,
            source="agent",
        )
        after = {
            "session_id": result["session_id"],
            "task": _compact_task(result["task"]),
            "today_total": result["today_total"],
        }
        _audit(ctx, "add_session", args, before, after)
        return {**after, "message": "已记录学习时间"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "add_session", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_update_task(args: dict) -> dict:
    """参数校验 + 清洗：task_id 必填；progress → manual_progress 锁定语义。"""
    args = dict(args or {})
    tid = args.get("task_id")
    if tid is None:
        raise ValueError("update_task 缺少必填参数 task_id")
    try:
        args["task_id"] = int(tid)
    except (TypeError, ValueError):
        raise ValueError("update_task 参数 task_id 必须是数字")
    # 进度不变量：Agent 改进度 = 手动接管（manual_progress 锁定），传 manual_progress=-1 恢复自动
    if "progress" in args and args.get("progress") is not None:
        p = args.pop("progress")
        try:
            args["manual_progress"] = int(p)
        except (TypeError, ValueError):
            raise ValueError("update_task 参数 progress 必须是数字")
    if "manual_progress" in args and args.get("manual_progress") is not None:
        try:
            args["manual_progress"] = int(args["manual_progress"])
        except (TypeError, ValueError):
            raise ValueError("update_task 参数 manual_progress 必须是数字")
    if "hours" in args and args.get("hours") is not None:
        try:
            args["hours"] = float(args["hours"])
        except (TypeError, ValueError):
            raise ValueError("update_task 参数 hours 必须是数字")
    for k in ("status", "title", "phase", "category", "priority", "due_date", "note"):
        if args.get(k) is not None:
            args[k] = str(args[k]).strip()
    return args


def update_task(args: dict, ctx=None) -> dict:
    """更新任务字段（直接生效）。progress 会锁定进度（手动接管）；manual_progress=-1 恢复自动。"""
    tid = args["task_id"]
    existing = crud.fetch_one("tasks", tid)
    before = _compact_task(existing) if existing else {}
    body = {k: v for k, v in args.items() if k != "task_id" and v is not None}
    try:
        row = svc.update_task(tid, body)
        after = _compact_task(row)
        _audit(ctx, "update_task", args, before, after)
        return {**after, "message": "已更新（直接生效）"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "update_task", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_complete_task(args: dict) -> dict:
    args = dict(args or {})
    tid = args.get("task_id")
    if tid is None:
        raise ValueError("complete_task 缺少必填参数 task_id")
    try:
        args["task_id"] = int(tid)
    except (TypeError, ValueError):
        raise ValueError("complete_task 参数 task_id 必须是数字")
    return args


def complete_task(args: dict, ctx=None) -> dict:
    """标记任务完成（直接生效）：status=已完成 + 进度锁到 100。"""
    tid = args["task_id"]
    existing = crud.fetch_one("tasks", tid)
    before = _compact_task(existing) if existing else {}
    try:
        row = svc.complete_task(tid)
        after = _compact_task(row)
        _audit(ctx, "complete_task", args, before, after)
        return {**after, "message": "已标记完成"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "complete_task", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_create_review_task(args: dict) -> dict:
    args = dict(args or {})
    tid = args.get("task_id")
    if tid is None:
        raise ValueError("create_review_task 缺少必填参数 task_id")
    try:
        args["task_id"] = int(tid)
    except (TypeError, ValueError):
        raise ValueError("create_review_task 参数 task_id 必须是数字")
    if args.get("reason") is not None:
        args["reason"] = str(args["reason"]).strip()
    return args


def create_review_task(args: dict, ctx=None) -> dict:
    """给既有任务生成「复习：<title>」任务（直接生效），继承 phase/category。"""
    tid = args["task_id"]
    src = crud.fetch_one("tasks", tid)
    before = _compact_task(src) if src else {}
    try:
        row = svc.create_review_task(tid, reason=args.get("reason") or "")
        after = _compact_task(row)
        _audit(ctx, "create_review_task", args, before, after)
        return {**after, "message": "已创建复习任务"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "create_review_task", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise
