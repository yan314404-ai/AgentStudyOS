"""学习路线任务：增删改查 + 学习计时（sessions）/ 自动进度 + 课程挂靠。

业务不变量（进度重算 / 打卡分类同步 / 记时事务）集中在 app/services/tasks.py，
这里只做 HTTP 校验与响应整形——手动页面与 Agent 工具共享同一套行为。
"""
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from .. import crud
from ..db import connect
from ..services import tasks as svc

router = APIRouter(prefix="/api/tasks", tags=["学习任务"])

# 兼容导出（若页面/脚本引用了这两个常量）
CATEGORY_FIELD_MAP = svc.CATEGORY_FIELD_MAP
DEFAULT_FIELD = svc.DEFAULT_FIELD


@router.get("")
def list_tasks(phase: str = ""):
    if phase:
        rows = crud.fetch_all("tasks", where="phase=?", params=(phase,), order="id")
    else:
        rows = crud.fetch_all("tasks", order="id")
    return svc.attach_courses(rows)


@router.get("/phases")
def list_phases():
    return crud.distinct("tasks", "phase")


@router.get("/sessions/today")
def sessions_today():
    """今天记过时的任务明细（供打卡页「今日任务学习」块）。"""
    today = date.today().isoformat()
    conn = connect()
    rows = conn.execute(
        "SELECT s.id, s.task_id, t.title, s.minutes, s.note, s.source, s.log_date "
        "FROM task_sessions s JOIN tasks t ON t.id=s.task_id "
        "WHERE s.log_date=? ORDER BY s.id DESC",
        (today,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("")
def add_task(body: dict):
    body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    return crud.create("tasks", body)


@router.put("/{rid}")
def edit_task(rid: int, body: dict):
    """支持 manual_progress：>=0 手动锁定；-1 恢复自动并立即重算。"""
    try:
        row = svc.update_task(rid, body)
    except svc.TaskNotFound:
        raise HTTPException(404, "任务不存在")
    return svc.attach_courses([row])[0]


@router.delete("/{rid}")
def del_task(rid: int):
    if not crud.fetch_one("tasks", rid):
        raise HTTPException(404, "任务不存在")
    crud.delete("tasks", rid)
    return {"ok": True}


@router.post("/{rid}/sessions")
def add_session(rid: int, body: dict):
    """记一笔学习时间：minutes 必填(1~999)。自动累加时间、重算进度、同步当天打卡。"""
    try:
        result = svc.add_session(
            rid,
            int(body.get("minutes") or 0),
            note=(body.get("note") or "").strip(),
            log_date=body.get("log_date"),
            source=body.get("source") or "quick",
        )
    except svc.TaskNotFound:
        raise HTTPException(404, "任务不存在")
    except svc.BadRequest as e:
        raise HTTPException(400, str(e))
    updated = svc.attach_courses([result["task"]])[0]
    return {"task": updated, "today_total": result["today_total"]}
