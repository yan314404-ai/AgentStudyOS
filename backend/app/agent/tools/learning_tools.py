"""只读学习状态工具：Observe 层。复用 stats/crud 聚合，输出紧凑结构。

统一签名 handler(args, ctx=None)：ctx 供写工具用，读工具忽略。
"""
from datetime import date

from ... import crud, stats


def get_learning_overview(args: dict, ctx=None) -> dict:
    """学习总览：实习准备度、各分类进度、连续打卡、本周统计。"""
    p = stats.overall_progress()
    w = stats.weekly_stats()
    return {
        "readiness": p["实习准备度"],
        "algo_mastery": p["算法掌握"],
        "bago_mastery": p["八股掌握"],
        "project_progress": p["项目进度"],
        "task_progress": p["任务进度"],
        "category_progress": p["任务分类"],
        "streak_days": stats.daily_streak(),
        "week_total_minutes": w["total_minutes"],
        "week_checkin_days": w["checkin_days"],
        "week_modules_minutes": w["modules"],
        "week_diff_vs_prev": w["diff_minutes"],
    }


def get_recent_learning_sessions(args: dict, ctx=None) -> dict:
    """最近 N 天打卡明细 + 周/月汇总（摘要字段）。"""
    days = max(7, min(int(args.get("days") or 14), 90))
    sessions = []
    for r in stats.recent_logs(days):
        mods = {stats.MODULE_NAMES[f]: (r[f] or 0) for f in stats.MODULE_FIELDS if (r[f] or 0) > 0}
        sessions.append({
            "date": r["log_date"],
            "total_minutes": r["total_minutes"] or 0,
            "modules": mods,
            "completed": (r.get("completed") or "")[:80],
            "learned": (r.get("learned") or "")[:80],
            "problems": (r.get("problems") or "")[:80],
        })
    m = stats.monthly_stats()
    return {
        "days": days,
        "sessions": sessions,
        "week_total_minutes": stats.weekly_stats()["total_minutes"],
        "month_total_minutes": m["total_minutes"],
    }


def get_weak_points(args: dict, ctx=None) -> dict:
    """识别弱项：任务分类进度低于 50% 的分类 + 算法/八股掌握度。"""
    cats = stats.task_progress_by_category()
    sorted_cats = sorted(cats.items(), key=lambda kv: kv[1])
    below = [{"category": k, "progress": v} for k, v in sorted_cats if v < 50]
    lowest = {"category": sorted_cats[0][0], "progress": sorted_cats[0][1]} if sorted_cats else None
    p = stats.overall_progress()
    return {
        "weak_categories": below,
        "lowest_category": lowest,
        "algorithm_mastery_pct": p["算法掌握"],
        "bago_mastery_pct": p["八股掌握"],
        "rule": "任务分类平均进度 < 50% 视为弱项；掌握度越低越优先补",
    }


def get_courses(args: dict, ctx=None) -> dict:
    """课程/资料清单（可指定 task_id 只看某任务的配套课程）。"""
    task_id = args.get("task_id")
    if task_id:
        rows = crud.fetch_all("courses", where="task_id=?", params=(int(task_id),), order="id")
    else:
        rows = crud.fetch_all("courses", order="id")
    courses = [{
        "id": c["id"],
        "name": c["name"],
        "platform": c.get("platform") or "",
        "url": c.get("url") or "",
        "teacher": c.get("teacher") or "",
        "progress": c["progress"] or 0,
        "status": c.get("status") or "",
        "task_id": c.get("task_id"),
    } for c in rows]
    return {"count": len(courses), "courses": courses}


def get_reports(args: dict, ctx=None) -> dict:
    """周/月报：复用统计 + 读 reports 缓存。不触发 AI 生成（避免花钱）。"""
    period_type = (args.get("period_type") or "week").strip().lower()
    if period_type not in ("week", "month"):
        raise ValueError("period_type 只能是 week 或 month")
    anchor_raw = args.get("anchor")
    if anchor_raw:
        try:
            anchor = date.fromisoformat(str(anchor_raw))
        except ValueError:
            raise ValueError("anchor 必须是 YYYY-MM-DD 格式日期")
    else:
        anchor = date.today()
    s = stats.weekly_stats(anchor) if period_type == "week" else stats.monthly_stats(anchor)
    # reports 表 UNIQUE(period_type, period_start)：命中缓存则附 AI 正文，未命中只给统计
    cached = crud.fetch_all(
        "reports",
        where="period_type=? AND period_start=?",
        params=(period_type, s["start"]),
    )
    content = cached[0]["content"] if cached and (cached[0].get("content") or "") else ""
    return {
        "period_type": s["period_type"],
        "start": s["start"],
        "end": s["end"],
        "stats": {k: v for k, v in s.items() if k != "logs"},  # 去掉原始打卡明细，保持紧凑
        "ai_content": content,  # 为空说明该期还没生成过报告（去「报告」页可生成）
    }
