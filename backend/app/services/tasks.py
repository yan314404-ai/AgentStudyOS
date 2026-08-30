"""任务领域服务：进度重算 / 打卡同步 / 学习时间事务的唯一来源。

任何写入口（手动页面 routers.tasks / Agent 写工具 agent.tools.task_tools）都委托到这里，
保证「记一笔 → 累加时间 → 重算进度 → 同步当天打卡」在任何入口行为一致。

领域异常：
  TaskNotFound → router 翻译成 404；BadRequest → router 翻译成 400。
"""
from datetime import date, datetime

from .. import crud
from ..db import connect

# 任务分类 → 当天打卡字段；其余分类统一计入课程时长
CATEGORY_FIELD_MAP = {
    "算法": "algorithm_minutes",
    "八股": "bago_minutes",
    "项目": "project_minutes",
    "阅读": "reading_minutes",
}
DEFAULT_FIELD = "course_minutes"


class TaskNotFound(ValueError):
    """任务不存在。"""


class BadRequest(ValueError):
    """参数不合法。"""


def recalc_progress(conn, task_id: int) -> int:
    """按规则重算进度：手动锁定优先，否则 累计时间/目标小时。返回新进度。"""
    t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if t is None:
        return 0
    mp = t["manual_progress"]
    if mp is not None and mp >= 0:
        prog = mp
    elif (t["hours"] or 0) > 0:
        prog = min(100, round((t["spent_minutes"] or 0) / (t["hours"] * 60) * 100))
    else:
        prog = t["progress"] or 0
    conn.execute("UPDATE tasks SET progress=? WHERE id=?", (prog, task_id))
    return prog


def add_to_daily_log(conn, log_date: str, field: str, minutes: int) -> None:
    """把任务学习时间累加到当天打卡对应分类（存在则累加，没有则新建）。"""
    row = conn.execute("SELECT id FROM daily_logs WHERE log_date=?", (log_date,)).fetchone()
    if row:
        conn.execute(
            f"UPDATE daily_logs SET {field}=COALESCE({field},0)+?, total_minutes=COALESCE(total_minutes,0)+? WHERE id=?",
            (minutes, minutes, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO daily_logs(log_date," + field + ",total_minutes,created_at) VALUES(?,?,?,?)",
            (log_date, minutes, minutes, datetime.now().isoformat(timespec="seconds")),
        )


def attach_courses(rows: list) -> list:
    """给任务列表附加关联课程 + 模式标签。"""
    conn = connect()
    out = []
    for t in rows:
        t = dict(t)
        mp = t.get("manual_progress")
        t["mode"] = "manual" if (mp is not None and mp >= 0) else "auto"
        t["courses"] = [
            dict(r)
            for r in conn.execute("SELECT * FROM courses WHERE task_id=? ORDER BY id", (t["id"],))
        ]
        out.append(t)
    conn.close()
    return out


def stats_today_total(log_date: str) -> int:
    conn = connect()
    row = conn.execute("SELECT total_minutes FROM daily_logs WHERE log_date=?", (log_date,)).fetchone()
    conn.close()
    return row["total_minutes"] if row else 0


def create_task(data: dict) -> dict:
    """新建任务（直接生效）。title 必填；默认 phase=未分组 / status=待开始 / progress=0。"""
    data = dict(data or {})
    title = (data.get("title") or "").strip()
    if not title:
        raise BadRequest("缺少必填参数 title")
    data["title"] = title
    data.setdefault("phase", "未分组")
    data.setdefault("status", "待开始")
    data.setdefault("progress", 0)
    data["created_at"] = data.get("created_at") or datetime.now().isoformat(timespec="seconds")
    return crud.create("tasks", data)


def add_session(
    task_id: int,
    minutes: int,
    note: str = "",
    log_date: str = None,
    source: str = "quick",
) -> dict:
    """记一笔学习时间：INSERT session → 累加 spent_minutes → 条件重算进度 → 同步当天打卡。

    返回 {"session_id", "task"(原始行), "today_total"}。
    """
    task = crud.fetch_one("tasks", task_id)
    if not task:
        raise TaskNotFound("任务不存在")
    minutes = int(minutes or 0)
    if not (1 <= minutes <= 999):
        raise BadRequest("minutes 需在 1~999 之间")
    log_date = log_date or date.today().isoformat()
    field = CATEGORY_FIELD_MAP.get(task["category"], DEFAULT_FIELD)

    conn = connect()
    cur = conn.execute(
        "INSERT INTO task_sessions(task_id,minutes,log_date,note,source,created_at) VALUES(?,?,?,?,?,?)",
        (task_id, minutes, log_date, note, source, datetime.now().isoformat(timespec="seconds")),
    )
    session_id = cur.lastrowid
    conn.execute("UPDATE tasks SET spent_minutes=COALESCE(spent_minutes,0)+? WHERE id=?", (minutes, task_id))
    # 手动锁定的任务不再自动改进度
    mp = task.get("manual_progress")
    if mp is None or mp < 0:
        recalc_progress(conn, task_id)
    add_to_daily_log(conn, log_date, field, minutes)
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "task": crud.fetch_one("tasks", task_id),
        "today_total": stats_today_total(log_date),
    }


def update_task(task_id: int, body: dict) -> dict:
    """更新任务字段。manual_progress>=0 手动锁定；-1 恢复自动并立即重算。"""
    row = crud.update("tasks", task_id, body)
    if not row:
        raise TaskNotFound("任务不存在")
    if "manual_progress" in body or "spent_minutes" in body:
        conn = connect()
        recalc_progress(conn, task_id)
        conn.commit()
        conn.close()
        row = crud.fetch_one("tasks", task_id)
    return row


def complete_task(task_id: int) -> dict:
    """标记任务完成：status=已完成 + 手动锁定 100 → 进度 100。"""
    if not crud.fetch_one("tasks", task_id):
        raise TaskNotFound("任务不存在")
    crud.update("tasks", task_id, {"status": "已完成", "manual_progress": 100})
    conn = connect()
    recalc_progress(conn, task_id)
    conn.commit()
    conn.close()
    return crud.fetch_one("tasks", task_id)


def create_review_task(task_id: int, reason: str = "") -> dict:
    """给既有任务生成「复习：<title>」复习任务，继承 phase/category/priority。"""
    src = crud.fetch_one("tasks", task_id)
    if not src:
        raise TaskNotFound("任务不存在")
    note = "🤖 Agent 复习任务"
    reason = (reason or "").strip()
    if reason:
        note += "：" + reason
    data = {
        "title": "复习：" + (src["title"] or ""),
        "phase": src.get("phase") or "未分组",
        "category": src.get("category") or "",
        "priority": src.get("priority") or "中",
        "status": "待开始",
        "progress": 0,
        "note": note,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return crud.create("tasks", data)
