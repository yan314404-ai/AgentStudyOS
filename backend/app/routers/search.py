from fastapi import APIRouter
from .. import crud

router = APIRouter(prefix="/api/search", tags=["全局搜索"])


@router.get("")
def search(q: str = ""):
    q = (q or "").strip()
    if not q:
        return {"tasks": [], "algorithms": [], "bago": [], "courses": [], "projects": []}
    like = f"%{q}%"

    tasks = crud.fetch_all(
        "tasks",
        where="title LIKE ? OR description LIKE ? OR note LIKE ?",
        params=(like, like, like),
    )[:20]
    algorithms = crud.fetch_all(
        "algorithm_problems",
        where="title LIKE ? OR note LIKE ? OR mistake_reason LIKE ?",
        params=(like, like, like),
    )[:20]
    bago = crud.fetch_all(
        "bago_questions",
        where="question LIKE ? OR standard_answer LIKE ? OR tags LIKE ?",
        params=(like, like, like),
    )[:20]
    courses = crud.fetch_all(
        "courses",
        where="name LIKE ? OR note LIKE ? OR review LIKE ?",
        params=(like, like, like),
    )[:20]
    projects = crud.fetch_all(
        "projects",
        where="name LIKE ? OR goal LIKE ? OR next_step LIKE ? OR interview_points LIKE ?",
        params=(like, like, like, like),
    )[:20]

    return {
        "tasks": tasks,
        "algorithms": algorithms,
        "bago": bago,
        "courses": courses,
        "projects": projects,
    }
