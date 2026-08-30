"""AI 助手聊天：用户问，AI 基于当前学习数据答。

每次请求把「当前学习状态摘要」注入 system prompt，加上最近对话历史，
一次往返调 DeepSeek。聊天记录持久化到 chat_messages 表（重启不丢）。
"""
from datetime import datetime

from fastapi import APIRouter

from .. import llm, stats
from ..db import connect

router = APIRouter(prefix="/api/chat", tags=["AI 助手"])

HISTORY_LIMIT = 30  # 每次带上最近多少条对话作为上下文
TIME_FORMAT = "%Y-%m-%d %H:%M"


def _now() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _cut(s: str, n: int = 120) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _build_chat_context() -> str:
    """把当前学习数据聚合成本文摘要，作为 system prompt 给 AI。全部复用 stats 现有函数。"""
    p = stats.overall_progress()
    week = stats.weekly_stats()
    month = stats.monthly_stats()
    recent = stats.recent_logs(14)
    today = datetime.now().strftime("%Y-%m-%d")

    lines = []
    lines.append("你是「Agent 学习 OS」的学习助手，用户是准备 AI Agent / LLM 应用开发岗位实习的大三学生。")
    lines.append(f"以下是他的学习数据（数据截至 {today}，均为真实记录），请用中文回答他的问题。")
    lines.append("要求：回答要具体、有数据支撑；给建议要落到他的任务/项目上；数据没有提到的一律不要编造。")
    lines.append("")

    # 准备度
    lines.append("【实习准备度】")
    lines.append(
        f"{p['实习准备度']}/100（算法掌握 {p['算法掌握']}% · 八股掌握 {p['八股掌握']}% · "
        f"项目进度 {p['项目进度']}% · 任务进度 {p['任务进度']}%）"
    )
    cats = p["任务分类"]
    if cats:
        lines.append("任务各阶段平均进度：" + "、".join(f"{k} {v}%" for k, v in cats.items()))
    lines.append("")

    # 本周 / 本月
    for label, s in (("本周", week), ("本月", month)):
        mods = "、".join(f"{k} {v}分" for k, v in s["modules"].items() if v > 0) or "无"
        lines.append(
            f"【{label}统计】{s['start']} ~ {s['end']}：总时长 {s['total_minutes']} 分，"
            f"打卡 {s['checkin_days']}/{s['day_count']} 天，日均 {s['avg_per_day']} 分；各模块 {mods}。"
            f"{'对比上一周期 ' + ('+' if s['diff_minutes'] >= 0 else '') + str(s['diff_minutes']) + ' 分' if s['prev_total_minutes'] > 0 else '上一周期无记录'}。"
        )
    lines.append("")

    # 近 14 天打卡明细
    lines.append("【近 14 天每日打卡】")
    if not recent:
        lines.append("（无记录，他还没打过卡）")
    for r in recent:
        mods = " / ".join(f"{stats.MODULE_NAMES[f]} {r[f]}分" for f in stats.MODULE_FIELDS if (r[f] or 0) > 0)
        detail = []
        if r.get("completed"):
            detail.append("完成:" + _cut(r["completed"], 60))
        if r.get("problems"):
            detail.append("问题:" + _cut(r["problems"], 60))
        if r.get("learned"):
            detail.append("学到:" + _cut(r["learned"], 60))
        tail = "；".join(detail)
        lines.append(f"- {r['log_date']}：{r['total_minutes'] or 0} 分（{mods or '无'}）{('；' + tail) if tail else ''}")
    lines.append("")

    # 最近的每日总结
    conn = connect()
    sums = conn.execute(
        "SELECT log_date, content FROM daily_summaries ORDER BY log_date DESC LIMIT 5"
    ).fetchall()
    tasks_rows = conn.execute(
        "SELECT phase, title, progress, status FROM tasks WHERE progress<100 ORDER BY progress DESC LIMIT 15"
    ).fetchall()
    algo_n = conn.execute("SELECT COUNT(*) AS c FROM algorithm_problems").fetchone()["c"]
    bago_n = conn.execute("SELECT COUNT(*) AS c FROM bago_questions").fetchone()["c"]
    course_n = conn.execute("SELECT COUNT(*) AS c FROM courses").fetchone()["c"]
    proj_n = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
    conn.close()

    lines.append("【最近的每日总结】")
    if sums:
        for r in sums:
            lines.append(f"- {r['log_date']}：{_cut(r['content'])}")
    else:
        lines.append("（无）")
    lines.append("")

    # 未完成任务 → AI 给「下一步建议」的依据
    lines.append("【未完成任务（前 15 条）】")
    if tasks_rows:
        for r in tasks_rows:
            lines.append(f"- [{r['phase']}] {r['title']} · 进度 {r['progress']}% · {r['status']}")
    else:
        lines.append("（所有任务都完成了）")
    lines.append("")

    # 数量简表
    lines.append(
        f"【其他】算法题 {algo_n} 道 · 八股 {bago_n} 题 · 课程 {course_n} 门 · 项目 {proj_n} 个。"
    )
    return "\n".join(lines)


@router.get("/history")
def history():
    conn = connect()
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM chat_messages ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows[-100:]]


@router.post("/message")
def send_message(body: dict):
    content = (body.get("content") or "").strip()
    if not content:
        return {"ok": False, "error": "消息不能为空"}
    if not llm.is_configured():
        return {"ok": False, "reason": "not_configured", "error": "请先在「设置」页配置模型 API key"}

    now = _now()
    conn = connect()
    conn.execute(
        "INSERT INTO chat_messages(role, content, created_at) VALUES(?,?,?)",
        ("user", content, now),
    )
    conn.commit()  # 先落库：即使 AI 调用失败，用户消息也不能丢
    # 最近 HISTORY_LIMIT 条历史（含刚存的这条）作为上下文
    history_rows = conn.execute(
        "SELECT role, content FROM (SELECT role, content, id FROM chat_messages ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        (HISTORY_LIMIT,),
    ).fetchall()
    conn.close()

    messages = [{"role": "system", "content": _build_chat_context()}]
    messages += [{"role": r["role"], "content": r["content"]} for r in history_rows]

    try:
        reply = llm.chat(messages, timeout=60)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    conn = connect()
    conn.execute(
        "INSERT INTO chat_messages(role, content, created_at) VALUES(?,?,?)",
        ("assistant", reply, _now()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "reply": reply}


@router.delete("/clear")
def clear():
    conn = connect()
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    return {"ok": True}
