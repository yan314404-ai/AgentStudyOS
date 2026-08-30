from datetime import datetime
from fastapi import APIRouter, HTTPException
from .. import crud

router = APIRouter(prefix="/api/courses", tags=["课程"])


@router.get("")
def list_courses():
    return crud.fetch_all("courses", order="id")


@router.post("")
def add_course(body: dict):
    body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    return crud.create("courses", body)


@router.put("/{rid}")
def edit_course(rid: int, body: dict):
    row = crud.update("courses", rid, body)
    if not row:
        raise HTTPException(404, "课程不存在")
    return row


@router.delete("/{rid}")
def del_course(rid: int):
    if not crud.fetch_one("courses", rid):
        raise HTTPException(404, "课程不存在")
    crud.delete("courses", rid)
    return {"ok": True}
