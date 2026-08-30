from datetime import datetime
from fastapi import APIRouter, HTTPException
from .. import crud

router = APIRouter(prefix="/api/projects", tags=["项目"])


def _with_milestones(proj: dict) -> dict:
    proj["milestones"] = crud.fetch_all("milestones", where="project_id=?", params=(proj["id"],), order="id")
    return proj


@router.get("")
def list_projects():
    rows = crud.fetch_all("projects", order="id")
    return [_with_milestones(p) for p in rows]


@router.get("/{rid}")
def get_project(rid: int):
    row = crud.fetch_one("projects", rid)
    if not row:
        raise HTTPException(404, "项目不存在")
    return _with_milestones(row)


@router.post("")
def add_project(body: dict):
    body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    return _with_milestones(crud.create("projects", body))


@router.put("/{rid}")
def edit_project(rid: int, body: dict):
    row = crud.update("projects", rid, body)
    if not row:
        raise HTTPException(404, "项目不存在")
    return _with_milestones(row)


@router.delete("/{rid}")
def del_project(rid: int):
    if not crud.fetch_one("projects", rid):
        raise HTTPException(404, "项目不存在")
    conn = crud.connect()
    conn.execute("DELETE FROM milestones WHERE project_id=?", (rid,))
    conn.commit()
    conn.close()
    crud.delete("projects", rid)
    return {"ok": True}


# ---------- 里程碑 ----------
@router.post("/{rid}/milestones")
def add_milestone(rid: int, body: dict):
    if not crud.fetch_one("projects", rid):
        raise HTTPException(404, "项目不存在")
    body["project_id"] = rid
    return crud.create("milestones", body)


@router.put("/milestones/{mid}")
def edit_milestone(mid: int, body: dict):
    row = crud.update("milestones", mid, body)
    if not row:
        raise HTTPException(404, "里程碑不存在")
    return row


@router.delete("/milestones/{mid}")
def del_milestone(mid: int):
    if not crud.fetch_one("milestones", mid):
        raise HTTPException(404, "里程碑不存在")
    crud.delete("milestones", mid)
    return {"ok": True}
