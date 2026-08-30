from datetime import date, datetime
from fastapi import APIRouter, HTTPException
from .. import crud, stats

router = APIRouter(prefix="/api/checkins", tags=["每日打卡"])

MINUTE_FIELDS = ["algorithm_minutes", "bago_minutes", "course_minutes", "project_minutes", "reading_minutes"]


def _fill_total(data: dict) -> dict:
    total = sum(int(data.get(f) or 0) for f in MINUTE_FIELDS)
    data["total_minutes"] = total
    return data


@router.get("/today")
def today():
    return stats.today_summary()


@router.get("/recent")
def recent(days: int = 7):
    return stats.recent_logs(days=days)


@router.get("/streak")
def streak():
    return {"streak": stats.daily_streak()}


@router.post("")
def upsert_today(body: dict):
    """按 log_date 更新，没有则创建；total_minutes 由后端自动算。"""
    log_date = body.get("log_date") or date.today().isoformat()
    body = _fill_total(body)
    existing = crud.fetch_all("daily_logs", where="log_date=?", params=(log_date,))
    if existing:
        row = crud.update("daily_logs", existing[0]["id"], body)
    else:
        body.setdefault("log_date", log_date)
        body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        row = crud.create("daily_logs", body)
    return row


@router.put("/{rid}")
def update_log(rid: int, body: dict):
    row = crud.update("daily_logs", rid, _fill_total(body))
    if not row:
        raise HTTPException(404, "记录不存在")
    return row
