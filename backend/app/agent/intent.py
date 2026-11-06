"""意图识别 + 多轮对话管理（Phase 5）。

为什么用规则而不是让 LLM 分类：
- 意图路由每轮都要跑，走 LLM 就多一次请求、多一份钱和延迟；本项目 5 类意图边界清晰，
  正则 + 关键词的准确率在自建评测集上可验证（见 backend/app/agent/eval_cases.py），
  规则还完全可解释、可单测。
- 槽位缺失时才追问（一次只问一个），用户答完继续；这是最经典的对话管理写法，
  比「把全部槽位一次问完」更不容易让用户迷惑。

数据流：
    classify(text)                → {"intent":..., "confidence":..., "slots":{...}, "missing":[...]}
    merge_pending(pending, text)  → 把用户对追问的回答并进上一轮的槽位，再判一次
    next_question(intent, missing)→ 中文追问话术
"""
import re
from datetime import date, datetime, timedelta

# ---------- 意图定义 ----------
INTENT_PLAN = "plan"          # 安排某天学习
INTENT_REVIEW = "review"      # 复盘某天计划
INTENT_RECORD = "record"      # 记录已学时间
INTENT_REMEMBER = "remember"  # 记住偏好/事实
INTENT_FORGET = "forget"      # 忘掉某条记忆
INTENT_QUERY = "query"        # 查状态/要建议
INTENT_CHAT = "chat"          # 其他/闲聊

INTENTS = [INTENT_PLAN, INTENT_REVIEW, INTENT_RECORD, INTENT_REMEMBER,
           INTENT_FORGET, INTENT_QUERY, INTENT_CHAT]

INTENT_LABEL = {
    INTENT_PLAN: "安排计划",
    INTENT_REVIEW: "复盘计划",
    INTENT_RECORD: "记录学习",
    INTENT_REMEMBER: "记住偏好",
    INTENT_FORGET: "忘掉记忆",
    INTENT_QUERY: "查询状态",
    INTENT_CHAT: "一般对话",
}

# 每个意图必需（required）和可选（optional）的槽位
SLOT_SCHEMA = {
    INTENT_PLAN: {"required": ["date"], "optional": ["minutes"]},
    INTENT_REVIEW: {"required": ["plan_date"], "optional": []},
    INTENT_RECORD: {"required": ["minutes"], "optional": ["task_id", "log_date"]},
    INTENT_REMEMBER: {"required": ["content"], "optional": []},
    INTENT_FORGET: {"required": ["key"], "optional": []},
    INTENT_QUERY: {"required": [], "optional": []},
    INTENT_CHAT: {"required": [], "optional": []},
}

SLOT_LABEL = {
    "date": "哪一天的计划",
    "plan_date": "复盘哪一天的",
    "minutes": "多少分钟",
    "task_id": "哪个任务",
    "log_date": "记到哪一天",
    "content": "要记住什么",
    "key": "要忘掉哪条记忆",
}

# ---------- 关键词规则（顺序 = 优先级，先命中先返回） ----------
# 每条：(意图, 正则, 基础置信度)
_RULES = [
    (INTENT_FORGET, re.compile(r"(忘掉|忘记|别记了|不用记|删掉.*记忆|删除.*记忆)"), 0.95),
    (INTENT_REMEMBER, re.compile(r"(记住|请记住|记下来|以后都按|以后注意|帮我记一下.*偏好)"), 0.95),
    (INTENT_REVIEW, re.compile(r"(复盘|回顾.*计划|计划.*执行情况|昨天.*完成得|计划.*vs.*实际|对比.*计划)"), 0.9),
    # 注意：不能写「学习.*分钟」——「帮我安排 2026-12-01 的学习，共 180 分钟」会被误判成记录。
    # 记录意图必须出现「记录/学了/打卡」这类动词。
    (INTENT_RECORD, re.compile(r"(记一笔|记录|学了|已经学|打卡.*(?:分钟|小时))"), 0.85),
    (INTENT_PLAN, re.compile(r"(安排|计划.*(明天|今天|后天|下周)|排.*计划|规划.*学习|制定.*计划)"), 0.85),
    (INTENT_QUERY, re.compile(r"(分析.*状态|我的.*进度|学得怎么样|弱项|薄弱|建议|准备度|还剩)"), 0.8),
]

# ---------- 槽位抽取 ----------
_RE_MINUTES = re.compile(r"(\d{1,4})\s*(?:分钟|分|min)")
_RE_HOURS = re.compile(r"(\d{1,2}(?:\.\d)?)\s*(?:个?小时|h\b)")
_RE_TASK_ID = re.compile(r"任务\s*#?\s*(\d{1,6})")
# 任务标题里的引号包裹（「…」 / "…" / '…'）
_RE_QUOTED = re.compile(r"[「“\"']([^」”\"']{2,40})[」”\"']")

_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _today() -> date:
    return datetime.now().date()


def extract_date(text: str) -> str:
    """从中文里抽日期，返回 YYYY-MM-DD；抽不到返回空串。

    支持：今天/昨天/前天/明天/后天/大后天、本周X/周X/星期X、下周X、M月D日、YYYY-MM-DD。
    只认这些明确写法，模糊说法（如「过几天」）不猜。
    """
    t = text or ""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return ""
    today = _today()
    relative = {
        "大后天": 3, "后天": 2, "明天": 1, "今天": 0, "今日": 0, "昨天": -1, "昨日": -1, "前天": -2,
    }
    # 长词优先，避免「大后天」被「后天」先吃掉
    for word in sorted(relative, key=len, reverse=True):
        if word in t:
            return (today + timedelta(days=relative[word])).isoformat()
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", t)
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
            # 已过去的月日按明年算（用户说「12月19日」在 11 月时指未来）
            if d < today - timedelta(days=180):
                d = date(today.year + 1, d.month, d.day)
            return d.isoformat()
        except ValueError:
            return ""
    m = re.search(r"(下周|这周|本周|周|星期)([一二三四五六日天])", t)
    if m:
        target = _WEEKDAY[m.group(2)]
        weekday = today.weekday()
        if m.group(1) == "下周":
            delta = (7 - weekday) + target
        else:
            delta = target - weekday
        return (today + timedelta(days=delta)).isoformat()
    return ""


def extract_minutes(text: str) -> int:
    """抽分钟数：优先「N 分钟」，其次「N 小时」换算；抽不到返回 0。"""
    t = text or ""
    m = _RE_MINUTES.search(t)
    if m:
        return max(0, min(1440, int(m.group(1))))
    m = _RE_HOURS.search(t)
    if m:
        return max(0, min(1440, int(round(float(m.group(1)) * 60))))
    return 0


def extract_task_ref(text: str) -> dict:
    """抽任务引用：id 或标题片段。返回 {"task_id": int|None, "task_hint": str}。"""
    t = text or ""
    m = _RE_TASK_ID.search(t)
    if m:
        return {"task_id": int(m.group(1)), "task_hint": ""}
    m = _RE_QUOTED.search(t)
    if m:
        return {"task_id": None, "task_hint": m.group(1).strip()}
    return {"task_id": None, "task_hint": ""}


def extract_slots(intent: str, text: str) -> dict:
    """按意图抽该意图需要的槽位，抽不到的键不出现（便于 missing 计算）。"""
    slots = {}
    t = text or ""
    if intent == INTENT_PLAN:
        d = extract_date(t)
        if d:
            slots["date"] = d
        mins = extract_minutes(t)
        if mins:
            slots["minutes"] = mins
    elif intent == INTENT_REVIEW:
        d = extract_date(t)
        if d:
            slots["plan_date"] = d
    elif intent == INTENT_RECORD:
        mins = extract_minutes(t)
        if mins:
            slots["minutes"] = mins
        ref = extract_task_ref(t)
        if ref["task_id"] is not None:
            slots["task_id"] = ref["task_id"]
        elif ref["task_hint"]:
            slots["task_hint"] = ref["task_hint"]
        d = extract_date(t)
        if d:
            slots["log_date"] = d
    elif intent == INTENT_REMEMBER:
        content = _remember_content(t)
        if content:
            slots["content"] = content
    elif intent == INTENT_FORGET:
        key = _forget_key(t)
        if key:
            slots["key"] = key
    return slots


def _remember_content(text: str) -> str:
    """记住类：把「记住：xxx」「记住 xxx」「以后都按 xxx」后面的内容当槽位值。"""
    t = (text or "").strip()
    m = re.search(r"(?:记住|请记住|记下来|记一下|以后都按|以后注意|以后都|以后)[：:，, ]*(.+)", t)
    if m:
        content = m.group(1).strip(" 。，,、")
        return content if len(content) >= 2 else ""
    return ""


def _forget_key(text: str) -> str:
    """忘掉类：优先引号里的标识，其次「忘掉 xxx」后面的短语。"""
    t = (text or "").strip()
    m = _RE_QUOTED.search(t)
    if m:
        return m.group(1).strip()
    # 「忘掉记忆：学习时段」里「记忆」只是名词，不能当 key 的一部分
    m = re.search(r"(?:忘掉|忘记|别记了|不用记)(?:这条|那条|该条)?记忆?[：:，, ]*(.+)", t)
    if m:
        key = m.group(1).strip(" 。，,、")
        return key if 2 <= len(key) <= 30 else ""
    return ""


def missing_slots(intent: str, slots: dict) -> list:
    """缺哪些必需槽位。task_hint 也算「任务已给出」，不要求 task_id。"""
    required = SLOT_SCHEMA.get(intent, {}).get("required", [])
    out = []
    for k in required:
        if k == "task_id":
            if not slots.get("task_id") and not slots.get("task_hint"):
                out.append("task_id")
        elif not slots.get(k):
            out.append(k)
    return out


def classify(text: str) -> dict:
    """识别一句话的意图 + 槽位 + 缺什么。纯规则、零成本、可单测。

    confidence 是「规则命中强度」，不是概率；没命中任何规则 → chat + 0.3。
    """
    t = (text or "").strip()
    if not t:
        return {"intent": INTENT_CHAT, "confidence": 0.0, "slots": {}, "missing": [],
                "label": INTENT_LABEL[INTENT_CHAT]}
    for intent, pattern, conf in _RULES:
        if pattern.search(t):
            slots = extract_slots(intent, t)
            return {
                "intent": intent,
                "confidence": conf,
                "slots": slots,
                "missing": missing_slots(intent, slots),
                "label": INTENT_LABEL[intent],
            }
    return {"intent": INTENT_CHAT, "confidence": 0.3, "slots": {}, "missing": [],
            "label": INTENT_LABEL[INTENT_CHAT]}


def merge_pending(pending: dict, text: str) -> dict:
    """把用户对上一轮追问的回答并进挂起的槽位，再重算 missing。

    pending 结构：{"intent":..., "slots": {...}}（存在 agent_conversations.pending_json）
    只在「用户没给出新意图」时并入，避免用户中途换话题被硬拉回旧意图。
    """
    if not pending:
        return classify(text)
    cur = classify(text)
    base_intent = pending.get("intent") or INTENT_CHAT
    # 用户明确换了个意图（不是 chat）→ 以新意图为准，丢掉挂起
    if cur["intent"] != INTENT_CHAT and cur["intent"] != base_intent:
        return cur
    merged = dict(pending.get("slots") or {})
    merged.update(extract_slots(base_intent, text))
    return {
        "intent": base_intent,
        "confidence": max(cur["confidence"], 0.8),
        "slots": merged,
        "missing": missing_slots(base_intent, merged),
        "label": INTENT_LABEL.get(base_intent, base_intent),
        "resumed": True,
    }


def next_question(intent: str, missing: list) -> str:
    """缺槽位时的中文追问话术（一次只问第一个缺的）。"""
    if not missing:
        return ""
    slot = missing[0]
    label = SLOT_LABEL.get(slot, slot)
    return f"好的，我先确认一下：{label}？"


def build_goal(intent: str, slots: dict) -> str:
    """把意图 + 槽位拼成给 Agent 的自然语言目标（复用现有 planner 提示词规则）。

    刻意拼得像用户自己说的话：planner 的规则是按「用户目标」文本判断走哪条分支的。
    """
    s = slots or {}
    if intent == INTENT_PLAN:
        date_s = s.get("date") or _today().isoformat()
        mins = s.get("minutes")
        tail = f"，共 {mins} 分钟" if mins else ""
        return f"帮我安排 {date_s} 的学习计划{tail}"
    if intent == INTENT_REVIEW:
        date_s = s.get("plan_date") or _today().isoformat()
        return (
            f"复盘 {date_s} 的学习计划执行情况：用 get_plan_vs_actual 对比实际学习分钟与计划，"
            "判定是否计划过量/合理/不足，用 submit_review 提交 verdict 与待确认调整建议。"
        )
    if intent == INTENT_RECORD:
        mins = s.get("minutes") or 0
        ref = s.get("task_id")
        name = f"任务 {ref}" if ref else (s.get("task_hint") or "相关任务")
        day = s.get("log_date")
        tail = f"（记到 {day}）" if day else ""
        return f"帮我记录在{name}上学习了 {mins} 分钟{tail}"
    if intent == INTENT_REMEMBER:
        return f"记住：{s.get('content') or ''}"
    if intent == INTENT_FORGET:
        return f"忘掉记忆：{s.get('key') or ''}"
    if intent == INTENT_QUERY:
        return "分析我当前的学习状态，指出弱项并给出下一步建议"
    return ""


def describe(intent: str, slots: dict) -> str:
    """给前端显示的一行摘要，如「安排计划 · 2026-11-07 · 180 分钟」。"""
    label = INTENT_LABEL.get(intent, intent)
    parts = []
    for k in ("date", "plan_date", "minutes", "task_id", "task_hint", "log_date", "content", "key"):
        v = (slots or {}).get(k)
        if v:
            parts.append(str(v))
    return " · ".join([label] + parts)
