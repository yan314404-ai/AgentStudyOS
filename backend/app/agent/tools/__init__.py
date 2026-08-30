"""Agent 工具注册：build_registry() 返回全新 ToolRegistry（每次 run 独立，隔离去重缓存）。

注册 18 个工具（10 读 + 8 写），把数据库变成一个真实的 Agent Environment：
  观察：       get_learning_overview / get_recent_learning_sessions / get_weak_points
  任务：       get_task_list
  课程·报告：  get_courses / get_reports
  计划：       get_plan / get_plan_vs_actual
  记忆：       get_memories
  写操作：     create_task / add_session / update_task / complete_task / create_review_task
               / create_plan（直接生效+审计） / submit_review（复盘调整待确认，确认后生效）
               / remember（记忆待确认，确认后生效） / forget_memory（软删记忆）
普通写工具全部「直接生效」，由 agent_actions 审计表记录 before/after 快照兜底；
submit_review / remember 例外：调整/记忆只记录为待确认，用户确认后才应用。
"""
from ..registry import ToolRegistry
from ..schemas import Permission, ToolSpec
from . import learning_tools, memory_tools, plan_tools, task_tools


def _no_args(args: dict) -> dict:
    if args:
        raise ValueError("该工具不需要参数")
    return {}


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for spec in _specs():
        reg.register(spec)
    return reg


def _specs() -> list:
    return [
        # ---------- 观察 ----------
        ToolSpec(
            name="get_learning_overview",
            description="获取学习总览：实习准备度、各分类进度、连续打卡天数、本周统计",
            args_handler=_no_args,
            handler=learning_tools.get_learning_overview,
            permission=Permission.READ,
            category="观察",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        ToolSpec(
            name="get_recent_learning_sessions",
            description="获取最近 N 天学习打卡明细（默认 14 天）+ 本周/本月总时长",
            args_handler=lambda args: {"days": int(args.get("days") or 14)},
            handler=learning_tools.get_recent_learning_sessions,
            permission=Permission.READ,
            category="观察",
            input_schema={"type": "object", "properties": {"days": {"type": "integer", "default": 14}}, "required": []},
        ),
        ToolSpec(
            name="get_weak_points",
            description="识别学习弱项：任务分类进度低于 50% 的分类 + 算法/八股掌握度",
            args_handler=_no_args,
            handler=learning_tools.get_weak_points,
            permission=Permission.READ,
            category="观察",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        # ---------- 任务 ----------
        ToolSpec(
            name="get_task_list",
            description="获取学习路线任务列表（可传 phase 过滤，如「4 · Agent」）",
            args_handler=lambda args: {"phase": (args.get("phase") or "").strip()},
            handler=task_tools.get_task_list,
            permission=Permission.READ,
            category="任务",
            input_schema={"type": "object", "properties": {"phase": {"type": "string"}}, "required": []},
        ),
        # ---------- 课程·报告 ----------
        ToolSpec(
            name="get_courses",
            description="获取课程/资料清单（可传 task_id 只看某任务的配套课程）",
            args_handler=lambda args: {"task_id": int(args["task_id"]) if args.get("task_id") is not None else None},
            handler=learning_tools.get_courses,
            permission=Permission.READ,
            category="课程·报告",
            input_schema={"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": []},
        ),
        ToolSpec(
            name="get_reports",
            description="获取周报/月报统计（period_type=week|month，可传 anchor=YYYY-MM-DD）；已生成则附带 AI 正文，未生成只给统计",
            args_handler=lambda args: {
                "period_type": (args.get("period_type") or "week"),
                "anchor": (args.get("anchor") or "").strip() or None,
            },
            handler=learning_tools.get_reports,
            permission=Permission.READ,
            category="课程·报告",
            input_schema={"type": "object", "properties": {
                "period_type": {"type": "string", "enum": ["week", "month"], "default": "week"},
                "anchor": {"type": "string", "description": "YYYY-MM-DD，默认今天"},
            }, "required": []},
        ),
        # ---------- 写操作（全部直接生效 + 审计） ----------
        ToolSpec(
            name="create_task",
            description="创建学习任务（直接生效，不待确认）。title 必填；status 可传（默认「待开始」）",
            args_handler=task_tools.validate_create_task,
            handler=task_tools.create_task,
            permission=Permission.APPEND,
            category="写操作",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "必填，任务标题"},
                    "phase": {"type": "string", "description": "所属阶段，如「4 · Agent」"},
                    "category": {"type": "string", "description": "分类，如 算法/八股/项目/课程"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "hours": {"type": "number", "description": "目标小时数"},
                    "status": {"type": "string", "description": "默认「待开始」"},
                    "note": {"type": "string"},
                },
                "required": ["title"],
            },
        ),
        ToolSpec(
            name="add_session",
            description="给任务记一笔学习时间（直接生效）：累加已学分钟 + 重算进度 + 同步当天打卡",
            args_handler=task_tools.validate_add_session,
            handler=task_tools.add_session,
            permission=Permission.APPEND,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "task_id": {"type": "integer", "description": "必填，任务 id（用 get_task_list 查）"},
                "minutes": {"type": "integer", "description": "必填，本次学习分钟数 1~999"},
                "note": {"type": "string", "description": "学习内容备注"},
                "log_date": {"type": "string", "description": "YYYY-MM-DD，默认今天"},
            }, "required": ["task_id", "minutes"]},
        ),
        ToolSpec(
            name="update_task",
            description="更新任务（直接生效）。progress 会把进度锁定为手动接管；manual_progress=-1 恢复自动；也可改 status/hours/title 等",
            args_handler=task_tools.validate_update_task,
            handler=task_tools.update_task,
            permission=Permission.MUTATE,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "task_id": {"type": "integer", "description": "必填，任务 id"},
                "progress": {"type": "integer", "description": "0~100，锁定进度（手动接管）"},
                "manual_progress": {"type": "integer", "description": "-1 恢复自动"},
                "status": {"type": "string", "description": "如 待开始/进行中/已完成"},
                "hours": {"type": "number"},
                "title": {"type": "string"},
                "phase": {"type": "string"},
                "category": {"type": "string"},
                "priority": {"type": "string"},
                "due_date": {"type": "string"},
                "note": {"type": "string"},
            }, "required": ["task_id"]},
        ),
        ToolSpec(
            name="complete_task",
            description="标记任务完成（直接生效）：status=已完成 + 进度锁定为 100",
            args_handler=task_tools.validate_complete_task,
            handler=task_tools.complete_task,
            permission=Permission.MUTATE,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "task_id": {"type": "integer", "description": "必填，任务 id"},
            }, "required": ["task_id"]},
        ),
        ToolSpec(
            name="create_review_task",
            description="给既有任务生成「复习：<title>」复习任务（直接生效），继承原任务阶段/分类",
            args_handler=task_tools.validate_create_review_task,
            handler=task_tools.create_review_task,
            permission=Permission.APPEND,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "task_id": {"type": "integer", "description": "必填，要复习的任务 id"},
                "reason": {"type": "string", "description": "复习原因，写入 note"},
            }, "required": ["task_id"]},
        ),
        # ---------- 计划（Phase 3 闭环） ----------
        ToolSpec(
            name="get_plan",
            description="查看某天学习计划（默认最新一份）：计划项 + 该日已实际学习分钟",
            args_handler=lambda args: {"plan_date": (args.get("plan_date") or "").strip()},
            handler=plan_tools.get_plan,
            permission=Permission.READ,
            category="计划",
            input_schema={"type": "object", "properties": {
                "plan_date": {"type": "string", "description": "YYYY-MM-DD，默认最新计划"},
            }, "required": []},
        ),
        ToolSpec(
            name="get_plan_vs_actual",
            description="某天计划 vs 实际执行对比（默认最新）：planned/actual/deviation_pct/verdict(over计划过量|under不足|ok)",
            args_handler=lambda args: {"plan_date": (args.get("plan_date") or "").strip()},
            handler=plan_tools.get_plan_vs_actual,
            permission=Permission.READ,
            category="计划",
            input_schema={"type": "object", "properties": {
                "plan_date": {"type": "string", "description": "YYYY-MM-DD，默认最新计划"},
            }, "required": []},
        ),
        ToolSpec(
            name="create_plan",
            description="创建某天学习计划（直接生效）：items 每项必须含 task_id（先用 create_task 建任务）、expected_minutes 预期分钟",
            args_handler=plan_tools.validate_create_plan,
            handler=plan_tools.create_plan,
            permission=Permission.APPEND,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "plan_date": {"type": "string", "description": "必填，计划执行日 YYYY-MM-DD"},
                "items": {"type": "array", "description": "计划项：{task_id, expected_minutes, kind?, suggested_time?}，task_id 必须来自 create_task 的返回值；suggested_time 建议时段（按用户记忆安排，如 20:00-23:00）",
                          "items": {"type": "object", "properties": {
                              "task_id": {"type": "integer"},
                              "expected_minutes": {"type": "integer"},
                              "kind": {"type": "string"},
                              "suggested_time": {"type": "string", "description": "建议时段，如 20:00-23:00（来自用户记忆偏好）"},
                          }, "required": ["task_id", "expected_minutes"]}},
                "goal": {"type": "string"},
                "reasoning_summary": {"type": "string"},
            }, "required": ["plan_date", "items"]},
        ),
        ToolSpec(
            name="submit_review",
            description="提交某天计划的复盘：verdict 判定（计划过量/合理/不足）+ adjustments 待确认调整（不直接生效）",
            args_handler=plan_tools.validate_submit_review,
            handler=plan_tools.submit_review,
            permission=Permission.APPEND,
            category="写操作",
            input_schema={"type": "object", "properties": {
                "plan_date": {"type": "string", "description": "必填，复盘的计划执行日 YYYY-MM-DD"},
                "verdict": {"type": "string", "description": "必填，判定：计划过量/合理/不足"},
                "reasoning": {"type": "string", "description": "偏差分析与调整依据"},
                "adjustments": {"type": "array", "description": "待确认调整，action ∈ adjust(item_id,expected_minutes)/remove(item_id)/add(title,category,expected_minutes)/next_plan(plan_date,items[{title,category,expected_minutes}])"},
            }, "required": ["plan_date", "verdict"]},
        ),
        # ---------- 记忆（Phase 4 长期记忆） ----------
        ToolSpec(
            name="get_memories",
            description="查看已记住的用户记忆（待确认 + 已生效）；可选 type 过滤（preference/fact/goal/rule）",
            args_handler=lambda args: {"type": (args.get("type") or "").strip()},
            handler=memory_tools.get_memories,
            permission=Permission.READ,
            category="记忆",
            input_schema={"type": "object", "properties": {
                "type": {"type": "string", "description": "可选过滤：preference/fact/goal/rule"},
            }, "required": []},
        ),
        ToolSpec(
            name="remember",
            description="记住用户偏好/事实/目标/规则（**待确认**，用户在面板确认后才参与规划）。key=短中文标识，content=完整事实，type=preference/fact/goal/rule",
            args_handler=memory_tools.validate_remember,
            handler=memory_tools.remember,
            permission=Permission.APPEND,
            category="记忆",
            input_schema={"type": "object", "properties": {
                "key": {"type": "string", "description": "必填，短中文标识（改同偏好复用同 key）"},
                "content": {"type": "string", "description": "必填，完整事实，如「工作日 20:00-23:00 学习效率最高」"},
                "type": {"type": "string", "enum": ["preference", "fact", "goal", "rule"], "default": "preference"},
                "importance": {"type": "integer", "description": "1~5，默认 3，注入排序"},
                "keywords": {"type": "string", "description": "逗号分隔，检索用"},
            }, "required": ["key", "content"]},
        ),
        ToolSpec(
            name="forget_memory",
            description="忘掉某条记忆（软删）：key 为用户说过的标识，如「学习时段」",
            args_handler=memory_tools.validate_forget_memory,
            handler=memory_tools.forget_memory,
            permission=Permission.MUTATE,
            category="记忆",
            input_schema={"type": "object", "properties": {
                "key": {"type": "string", "description": "必填，要忘掉的记忆 key"},
            }, "required": ["key"]},
        ),
    ]
