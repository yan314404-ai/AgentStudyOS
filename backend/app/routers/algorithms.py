from datetime import datetime
from fastapi import APIRouter, HTTPException
from .. import crud

router = APIRouter(prefix="/api/algorithms", tags=["算法"])

CATEGORIES = ["数组", "哈希", "字符串", "双指针", "滑动窗口", "链表", "栈", "队列", "堆",
              "二叉树", "DFS", "BFS", "回溯", "二分", "排序", "贪心", "动态规划", "图", "并查集"]


@router.get("")
def list_problems(category: str = ""):
    if category:
        return crud.fetch_all("algorithm_problems", where="category=?", params=(category,), order="id DESC")
    return crud.fetch_all("algorithm_problems", order="id DESC")


@router.get("/categories")
def list_categories():
    return CATEGORIES


@router.get("/random")
def random_problem():
    row = crud.fetch_all("algorithm_problems", order="RANDOM()", params=())
    return row[0] if row else None


@router.post("")
def add_problem(body: dict):
    body.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    return crud.create("algorithm_problems", body)


@router.put("/{rid}")
def edit_problem(rid: int, body: dict):
    row = crud.update("algorithm_problems", rid, body)
    if not row:
        raise HTTPException(404, "题目不存在")
    return row


@router.delete("/{rid}")
def del_problem(rid: int):
    if not crud.fetch_one("algorithm_problems", rid):
        raise HTTPException(404, "题目不存在")
    crud.delete("algorithm_problems", rid)
    return {"ok": True}
