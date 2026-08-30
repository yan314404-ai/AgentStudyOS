from fastapi import APIRouter
from .. import stats, crud

router = APIRouter(prefix="/api/dashboard", tags=["总览"])


@router.get("")
def dashboard():
    today = stats.today_summary()
    upcoming = crud.fetch_all(
        "tasks",
        where="status != '已完成' AND due_date != ''",
        order="due_date ASC",
    )[:6]
    return {
        "progress": stats.overall_progress(),
        "streak": stats.daily_streak(),
        "today": today,
        "recent": stats.recent_logs(days=7),
        "upcoming": upcoming,
        "task_categories": stats.task_progress_by_category(),
    }
