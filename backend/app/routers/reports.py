"""报告：热力图 + 周报/月报（统计 + DeepSeek AI 总结，带缓存避免重复花钱）。"""
import json
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from .. import llm, stats
from ..db import connect

router = APIRouter(prefix="/api/reports", tags=["报告"])

WEEK_SYSTEM = (
    "你是一位严谨又亲切的学习复盘教练。你用数据说话，指出亮点和不足，"
    "给出可执行的下一步建议。语言用中文，简洁有重点。"
)
MONTH_SYSTEM = (
    "你是一位严谨又亲切的学习复盘教练。你站在月度视角评估整体节奏和成长，"
    "给出下个月的结构性建议。语言用中文，简洁有重点。"
)

_MODULE_FIELDS = stats.MODULE_FIELDS


def _parse_date(s: str) -> date:
    if s:
        try:
            return date.fromisoformat(s)
        except ValueError:
            raise HTTPException(400, "日期格式错误，应为 YYYY-MM-DD")
    return date.today()


def _fmt_hours(minutes: int) -> str:
    minutes = int(minutes or 0)
    if minutes >= 60:
        return f"{minutes // 60} 小时 {minutes % 60} 分"
    return f"{minutes} 分钟"


def _diff_text(s: dict) -> str:
    if s["prev_total_minutes"] <= 0:
        return "上期无学习记录"
    if s["diff_pct"] is None:
        return "上期无学习记录"
    d = s["diff_minutes"]
    if d > 0:
        return f"较上期增加 {_fmt_hours(d)}（+{s['diff_pct']}%）"
    if d < 0:
        return f"较上期减少 {_fmt_hours(-d)}（{s['diff_pct']}%）"
    return "与上期持平"


def _build_user_message(period_type: str, s: dict) -> str:
    label = "本周" if period_type == "week" else "本月"
    lines = [
        f"请为我生成一份{label}学习复盘报告。",
        f"周期：{s['start']} 至 {s['end']}",
        f"总学习时长：{_fmt_hours(s['total_minutes'])}（{s['total_minutes']} 分钟）",
        f"打卡天数：{s['checkin_days']}/{s['day_count']} 天，日均 {s['avg_per_day']} 分钟",
        f"与上期对比：{_diff_text(s)}",
        "各模块投入（分钟）：" + "、".join(f"{k} {v}" for k, v in s["modules"].items()),
    ]
    if period_type == "month":
        lines.append(f"已完成任务数（累计 progress≥100）：{s.get('completed_tasks', 0)}")
    lines.append("\n每天的具体记录（你写下的完成项、学到的东西、遇到的问题）：")
    for r in s["logs"]:
        line = f"- {r['log_date']}: 总 {r['total_minutes'] or 0} 分钟"
        if r.get("completed"):
            line += f"；完成：{r['completed'][:120]}"
        if r.get("learned"):
            line += f"；学到：{r['learned'][:120]}"
        if r.get("problems"):
            line += f"；问题：{r['problems'][:120]}"
        lines.append(line)
    lines.append(
        "\n请用中文输出一份有结构、有温度、可执行的复盘，分三部分："
        "① 本期亮点 ② 不足与风险 ③ 下期建议。整体 400 字以内，"
        "不要出现『根据提供的数据』这类客套话。"
    )
    return "\n".join(lines)


def _load_cached(period_type: str, start: str):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM reports WHERE period_type=? AND period_start=?", (period_type, start)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _save_report(period_type: str, s: dict, content: str) -> None:
    conn = connect()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR REPLACE INTO reports(period_type, period_start, period_end, stats_json, content, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (period_type, s["start"], s["end"], json.dumps(s, ensure_ascii=False), content, now),
    )
    conn.commit()
    conn.close()


def _ai_text(period_type: str, s: dict):
    """调 DeepSeek 生成总结。返回 (text, err)；err 为 None 表示成功。"""
    if not llm.is_configured():
        return None, "not_configured"
    system = WEEK_SYSTEM if period_type == "week" else MONTH_SYSTEM
    user = _build_user_message(period_type, s)
    try:
        return llm.generate(system, user), None
    except RuntimeError as e:
        return None, str(e)


def _report(period_type: str, anchor: date, refresh: bool):
    s = stats.weekly_stats(anchor) if period_type == "week" else stats.monthly_stats(anchor)
    if not refresh:
        cached = _load_cached(period_type, s["start"])
        if cached and cached["content"]:
            return {"ok": True, "stats": s, "content": cached["content"], "cached": True}
    text, err = _ai_text(period_type, s)
    if text:
        _save_report(period_type, s, text)
        return {"ok": True, "stats": s, "content": text, "cached": False}
    # AI 失败：有旧缓存就回退展示，否则报错（统计永远返回）
    cached = _load_cached(period_type, s["start"])
    if cached and cached["content"]:
        return {"ok": True, "stats": s, "content": cached["content"], "cached": True, "ai_error": err}
    return {"ok": False, "reason": err or "unknown", "stats": s, "content": ""}


@router.get("/heatmap")
def heatmap():
    return {"data": stats.heatmap_data()}


@router.get("/weekly")
def weekly(date: str = "", refresh: int = 0):
    return _report("week", _parse_date(date), bool(refresh))


@router.get("/monthly")
def monthly(date: str = "", refresh: int = 0):
    return _report("month", _parse_date(date), bool(refresh))
