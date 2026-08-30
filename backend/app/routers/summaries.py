"""每日总结：手写、独立功能，可写可不写，按日期查看历史。"""
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from .. import crud

router = APIRouter(prefix="/api/summaries", tags=["每日总结"])


@router.get("")
def get_one(date_str: str = ""):
    """取某天的总结；没写过返回空内容，方便前端回填。"""
    d = date_str or date.today().isoformat()
    rows = crud.fetch_all("daily_summaries", where="log_date=?", params=(d,))
    return rows[0] if rows else {"log_date": d, "content": ""}


@router.get("/list")
def list_all():
    """全部历史，按日期倒序，供「按日期查看记录」。"""
    return crud.fetch_all("daily_summaries", order="log_date DESC")


@router.post("")
def upsert(body: dict):
    """写/改某天总结。存在则更新，不存在则新建。"""
    d = body.get("log_date") or date.today().isoformat()
    content = body.get("content") or ""
    now = datetime.now().isoformat(timespec="seconds")
    existing = crud.fetch_all("daily_summaries", where="log_date=?", params=(d,))
    if existing:
        return crud.update("daily_summaries", existing[0]["id"], {"content": content, "updated_at": now})
    return crud.create(
        "daily_summaries",
        {"log_date": d, "content": content, "created_at": now, "updated_at": ""},
    )


@router.delete("/{rid}")
def delete(rid: int):
    if not crud.fetch_one("daily_summaries", rid):
        raise HTTPException(404, "总结不存在")
    crud.delete("daily_summaries", rid)
    return {"ok": True}
