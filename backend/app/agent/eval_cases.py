"""内置评测用例集（Agent 行为回归）。

三类用例，成本差别很大，所以分开跑：
- kind="intent"  纯规则意图识别，零 token、零写库、毫秒级 → 默认跑
- kind="dialog"  多轮对话槽位补全（merge_pending），同样零成本 → 默认跑
- kind="run"     真实跑一次 Agent（会花 token、会写真实库数据）→ 必须显式勾选才跑

为什么要有评测：Gartner 的数据是「缺可观测与评估的 88% Agent 试点跨不过生产鸿沟」，
这也是 AI Agent 岗位 JD 里「评测/可观测」这一条的具体落法。没有评测集的 Agent 项目
只能靠肉眼判断「改完提示词好像变好了」，那是不可维护的。

expect_json 约定（相对日期用 $today/$tomorrow/$yesterday/$next_monday 占位，跑的时候解析）：
- intent: {"intent": "plan", "missing": [], "slots": {"date": "$tomorrow"}, "confidence_min": 0.8}
- dialog: {"pending": {"intent": "plan", "slots": {}}, "text": "明天",
           "want": {"intent": "plan", "slots": {"date": "$tomorrow"}, "missing": []}}
- run:    {"status": "succeeded", "tools_include": ["create_plan"], "min_tokens": 1}
"""
from datetime import date, timedelta

# ---------- 用例定义 ----------
# (name, kind, goal, available_time, expect, note)
INTENT_CASES = [
    ("安排明天的学习", "intent", "安排明天的学习", 0,
     {"intent": "plan", "missing": [], "slots": {"date": "$tomorrow"}, "confidence_min": 0.8},
     "最基础的规划意图 + 相对日期"),
    ("安排指定日期与时长", "intent", "帮我安排 2026-12-01 的学习，共 180 分钟", 0,
     {"intent": "plan", "missing": [], "slots": {"date": "2026-12-01", "minutes": 180},
      "confidence_min": 0.8},
     "绝对日期 + 分钟数"),
    ("下周一的计划", "intent", "帮我排一下下周一的计划", 0,
     {"intent": "plan", "missing": [], "slots": {"date": "$next_monday"}, "confidence_min": 0.8},
     "周几相对日期"),
    ("复盘昨天计划", "intent", "复盘昨天的计划", 0,
     {"intent": "review", "missing": [], "slots": {"plan_date": "$yesterday"},
      "confidence_min": 0.8},
     "复盘意图 + 相对日期"),
    ("口语化复盘", "intent", "对比一下昨天计划的执行情况", 0,
     {"intent": "review", "missing": [], "slots": {"plan_date": "$yesterday"},
      "confidence_min": 0.8},
     "同一意图的不同说法（鲁棒性）"),
    ("记录学习-任务号+分钟", "intent", "记录今天在任务 12 上学习了 40 分钟", 0,
     {"intent": "record", "missing": [], "slots": {"minutes": 40, "task_id": 12},
      "confidence_min": 0.8},
     "记录意图 + 任务号 + 分钟"),
    ("记录学习-小时换算", "intent", "我学了 1.5 小时", 0,
     {"intent": "record", "missing": [], "slots": {"minutes": 90}, "confidence_min": 0.8},
     "小时换算成分钟"),
    ("记录学习-缺分钟要追问", "intent", "帮我记录在任务 5 上学习", 0,
     {"intent": "record", "missing": ["minutes"], "slots": {"task_id": 5},
      "confidence_min": 0.8},
     "槽位缺失时应该追问而不是瞎猜"),
    ("记住偏好", "intent", "记住：我晚上效率最高", 0,
     {"intent": "remember", "missing": [], "slots_contains": {"content": ["晚上"]},
      "confidence_min": 0.8},
     "记忆意图 + 内容抽取"),
    ("记住口语说法", "intent", "以后都按 20:00-23:00 安排学习", 0,
     {"intent": "remember", "missing": [], "slots_contains": {"content": ["20:00"]},
      "confidence_min": 0.8},
     "「以后都按…」也是记住偏好"),
    ("忘掉记忆", "intent", "忘掉记忆：学习时段", 0,
     {"intent": "forget", "missing": [], "slots_contains": {"key": ["学习时段"]},
      "confidence_min": 0.8},
     "遗忘意图 + 键名抽取"),
    ("查询状态", "intent", "分析我当前的学习状态", 0,
     {"intent": "query", "missing": [], "confidence_min": 0.8},
     "查询类无必需槽位"),
    ("闲聊不误判", "intent", "今天天气怎么样", 0,
     {"intent": "chat", "confidence_max": 0.5},
     "非学习话题不能误判成学习意图"),
    ("空输入", "intent", "", 0,
     {"intent": "chat", "confidence_max": 0.1},
     "空串要安全兜底"),
]

DIALOG_CASES = [
    ("追问日期后补全", "dialog", "（多轮：安排计划 → 用户答「明天」）", 0,
     {"pending": {"intent": "plan", "slots": {}}, "text": "明天",
      "want": {"intent": "plan", "slots": {"date": "$tomorrow"}, "missing": []}},
     "缺 date 时追问，用户答相对日期"),
    ("追问任务后补全", "dialog", "（多轮：记录学习 → 用户答「任务 12」）", 0,
     {"pending": {"intent": "record", "slots": {"minutes": 40}}, "text": "任务 12",
      "want": {"intent": "record", "slots": {"minutes": 40, "task_id": 12}, "missing": []}},
     "缺 task_id 时追问，用户答任务号"),
    ("中途换意图不硬拉回", "dialog", "（多轮：挂起安排计划 → 用户改成复盘）", 0,
     {"pending": {"intent": "plan", "slots": {}}, "text": "算了，先复盘昨天的",
      "want": {"intent": "review", "slots": {"plan_date": "$yesterday"}, "missing": []}},
     "用户明确换意图时以新意图为准"),
]

# run 类会花 token、写真实库，默认不跑
RUN_CASES = [
    ("真实跑-安排计划", "run", "帮我安排明天的学习计划，共 120 分钟", 120,
     {"status": "succeeded", "tools_include": ["create_plan"], "min_tokens": 1},
     "端到端：必须真的调 create_plan 落库"),
    ("真实跑-分析状态", "run", "分析我当前的学习状态，指出弱项", 0,
     {"status": "succeeded", "tools_include": ["get_weak_points"], "min_tokens": 1},
     "只读路径：必须用到弱项分析工具"),
]

ALL_CASES = INTENT_CASES + DIALOG_CASES + RUN_CASES


def case_rows() -> list:
    """转成 agent_eval_cases 表的行（供 seed_cases 幂等写入）。"""
    rows = []
    for name, kind, goal, avail, expect, note in ALL_CASES:
        rows.append({
            "name": name,
            "kind": kind,
            "goal": goal,
            "available_time": avail,
            "expect": expect,
            "note": note,
        })
    return rows


# ---------- 相对日期解析 ----------
def resolve_expected(expect: dict) -> dict:
    """把 expect 里的 $today/$tomorrow/$yesterday/$next_monday 换成真实日期。

    评测必须在「任何一天跑都成立」，所以期望值不能写死日期。
    """
    today = date.today()

    def _resolve(value):
        if not isinstance(value, str):
            return value
        if value == "$today":
            return today.isoformat()
        if value == "$tomorrow":
            return (today + timedelta(days=1)).isoformat()
        if value == "$yesterday":
            return (today - timedelta(days=1)).isoformat()
        if value == "$next_monday":
            # 下一个周一（今天是周一则指下周一，与 intent.extract_date 的「下周一」口径一致）
            delta = (7 - today.weekday()) % 7 or 7
            return (today + timedelta(days=delta)).isoformat()
        return value

    def _walk(obj):
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(v) for v in obj]
        return _resolve(obj)

    return _walk(expect)
