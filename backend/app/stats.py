"""Dashboard 统计：总进度、分类进度、连续打卡、今日概览。所有数字实时从数据库算。"""
from datetime import date, timedelta
from .db import connect

# 任务阶段 → Dashboard 展示分类
PHASE_MAP = [
    ("1 · 基础", "基础"),
    ("2 · LLM", "LLM"),
    ("3 · RAG", "RAG"),
    ("4 · Agent", "Agent"),
    ("5 · 工程化", "Agent 工程"),
    ("6 · 实习准备", "实习准备"),
]


def _phase_key(phase: str) -> str:
    for prefix, name in PHASE_MAP:
        if phase.startswith(prefix):
            return name
    return phase


def task_progress_by_category() -> dict:
    """按任务阶段聚合平均进度，返回 {分类: 0~100}。"""
    conn = connect()
    rows = conn.execute("SELECT phase, progress FROM tasks").fetchall()
    conn.close()
    acc: dict = {}
    for r in rows:
        key = _phase_key(r["phase"])
        acc.setdefault(key, []).append(r["progress"])
    return {k: round(sum(v) / len(v)) for k, v in acc.items()}


def _avg_mastery(table: str) -> float:
    conn = connect()
    row = conn.execute(f"SELECT AVG(mastery) AS a FROM {table}").fetchone()
    conn.close()
    return (row["a"] or 0) / 5.0  # mastery 0~5


def overall_progress() -> dict:
    """返回 Dashboard 全部指标。全部转成 0~100 百分比后按权重合成准备度（权重合计 1.0）。"""
    cats = task_progress_by_category()
    algo_pct = _avg_mastery("algorithm_problems") * 100
    bago_pct = _avg_mastery("bago_questions") * 100
    proj_pct = _avg_projects() * 100

    weights = {"基础": 0.15, "LLM": 0.15, "RAG": 0.2, "Agent": 0.2, "Agent 工程": 0.1, "实习准备": 0.1}
    weighted = 0.0
    wsum = 0.0
    for k, w in weights.items():
        weighted += cats.get(k, 0) * w
        wsum += w
    task_pct = (weighted / wsum) if wsum else 0

    readiness = (
        algo_pct * 0.25
        + bago_pct * 0.20
        + task_pct * 0.40
        + proj_pct * 0.15
    )

    return {
        "任务分类": cats,
        "算法掌握": round(algo_pct),
        "八股掌握": round(bago_pct),
        "项目进度": round(proj_pct),
        "任务进度": round(task_pct),
        "实习准备度": round(readiness),
    }


def _avg_projects() -> float:
    conn = connect()
    row = conn.execute("SELECT AVG(progress) AS a FROM projects").fetchone()
    conn.close()
    return (row["a"] or 0) / 100.0


def daily_streak() -> int:
    """自今天起往前数，连续 total_minutes>0 的天数。今天没打卡也从今天开始算。"""
    conn = connect()
    rows = conn.execute("SELECT log_date, total_minutes FROM daily_logs ORDER BY log_date DESC").fetchall()
    conn.close()
    has = {r["log_date"]: r["total_minutes"] for r in rows}
    streak = 0
    d = date.today()
    for _ in range(10000):
        key = d.isoformat()
        if key in has and has[key] > 0:
            streak += 1
            d -= timedelta(days=1)
        elif key in has and has[key] == 0 and streak == 0:
            # 今天打卡了但为 0，不算连续，停止
            break
        elif key in has and has[key] == 0:
            break
        else:
            # 没有这条记录：今天没打卡，则从昨天开始算；否则中断
            break
    return streak


def today_summary() -> dict:
    today = date.today().isoformat()
    conn = connect()
    row = conn.execute("SELECT * FROM daily_logs WHERE log_date=?", (today,)).fetchone()
    conn.close()
    return dict(row) if row else None


def recent_logs(days: int = 7) -> list:
    conn = connect()
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT * FROM daily_logs WHERE log_date>=? ORDER BY log_date DESC LIMIT ?", (since, days)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- 第二阶段：热力图 / 周报 / 月报 ----------

MODULE_FIELDS = ["algorithm_minutes", "bago_minutes", "course_minutes", "project_minutes", "reading_minutes"]
MODULE_NAMES = {
    "algorithm_minutes": "算法",
    "bago_minutes": "八股",
    "course_minutes": "课程",
    "project_minutes": "项目",
    "reading_minutes": "阅读",
}


def heatmap_data(days: int = 365) -> list:
    """近 N 天每天学习总分钟，供热力图。返回 [{date, minutes}]。"""
    conn = connect()
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT log_date, total_minutes FROM daily_logs WHERE log_date>=? ORDER BY log_date",
        (since,),
    ).fetchall()
    conn.close()
    return [{"date": r["log_date"], "minutes": r["total_minutes"]} for r in rows]


def _logs_between(start: str, end: str) -> list:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM daily_logs WHERE log_date>=? AND log_date<=? ORDER BY log_date",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _build_report_stats(period_type: str, start_d: date, end_d: date, logs: list, prev_logs: list) -> dict:
    """把一段时间的打卡明细汇总成报告统计。logs 含完整 daily_logs 行，供 AI 当素材。"""
    total = sum(r["total_minutes"] or 0 for r in logs)
    prev_total = sum(r["total_minutes"] or 0 for r in prev_logs)
    modules = {}
    for f in MODULE_FIELDS:
        modules[MODULE_NAMES[f]] = sum(r[f] or 0 for r in logs)
    checkin_days = sum(1 for r in logs if (r["total_minutes"] or 0) > 0)
    day_count = (end_d - start_d).days + 1
    diff = total - prev_total
    diff_pct = (diff / prev_total * 100) if prev_total else None
    return {
        "period_type": period_type,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "total_minutes": total,
        "checkin_days": checkin_days,
        "day_count": day_count,
        "avg_per_day": round(total / max(1, day_count)),
        "modules": modules,
        "logs": logs,
        "prev_total_minutes": prev_total,
        "diff_minutes": diff,
        "diff_pct": round(diff_pct) if diff_pct is not None else None,
    }


def weekly_stats(anchor: date = None) -> dict:
    """本周（周一~周日）聚合统计。anchor 为当天日期，默认今天。"""
    anchor = anchor or date.today()
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    prev_monday = monday - timedelta(days=7)
    prev_sunday = monday - timedelta(days=1)
    logs = _logs_between(monday.isoformat(), sunday.isoformat())
    prev_logs = _logs_between(prev_monday.isoformat(), prev_sunday.isoformat())
    return _build_report_stats("week", monday, sunday, logs, prev_logs)


def monthly_stats(anchor: date = None) -> dict:
    """本月（自然月）聚合统计 + 已完成任务数。"""
    anchor = anchor or date.today()
    start = anchor.replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)
    if start.month == 1:
        prev_start = date(start.year - 1, 12, 1)
    else:
        prev_start = date(start.year, start.month - 1, 1)
    prev_end = start - timedelta(days=1)
    logs = _logs_between(start.isoformat(), end.isoformat())
    prev_logs = _logs_between(prev_start.isoformat(), prev_end.isoformat())
    stats = _build_report_stats("month", start, end, logs, prev_logs)
    conn = connect()
    row = conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE progress>=100").fetchone()
    conn.close()
    stats["completed_tasks"] = row["c"]
    return stats
