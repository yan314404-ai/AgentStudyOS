from datetime import datetime
from fastapi import APIRouter, HTTPException
from .. import crud

router = APIRouter(prefix="/api/bago", tags=["八股"])

CATEGORIES = ["Python", "MySQL", "Redis", "计算机网络", "操作系统", "LLM", "RAG", "Agent", "工程"]


@router.get("")
def list_questions(category: str = "", keyword: str = ""):
    if category:
        return crud.fetch_all("bago_questions", where="category=?", params=(category,), order="id DESC")
    if keyword:
        like = f"%{keyword}%"
        return crud.fetch_all(
            "bago_questions",
            where="question LIKE ? OR standard_answer LIKE ? OR tags LIKE ?",
            params=(like, like, like),
            order="id DESC",
        )
    return crud.fetch_all("bago_questions", order="id DESC")


@router.get("/categories")
def list_categories():
    return CATEGORIES


@router.get("/random")
def random_question(category: str = ""):
    if category:
        rows = crud.fetch_all("bago_questions", where="category=?", params=(category,), order="RANDOM()")
    else:
        rows = crud.fetch_all("bago_questions", order="RANDOM()")
    return rows[0] if rows else None


@router.post("")
def add_question(body: dict):
    body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    return crud.create("bago_questions", body)


@router.put("/{rid}")
def edit_question(rid: int, body: dict):
    row = crud.update("bago_questions", rid, body)
    if not row:
        raise HTTPException(404, "题目不存在")
    return row


@router.delete("/{rid}")
def del_question(rid: int):
    if not crud.fetch_one("bago_questions", rid):
        raise HTTPException(404, "题目不存在")
    crud.delete("bago_questions", rid)
    return {"ok": True}
