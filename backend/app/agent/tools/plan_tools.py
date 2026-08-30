"""Phase 3 计划工具：跨天计划的读写（创建计划 / 计划对比 / 提交复盘）。

- create_plan    直接生效 + 审计（Agent「安排」计划；item 必须已建 task）
- submit_review  复盘调整**待确认**（不生效，用户确认后 PlanService.confirm_review 应用）
- get_plan / get_plan_vs_actual  只读，无审计

业务不变量走 app/services/plans.py（与路由共用同一套行为）。
"""
from ...services import plans as psvc
from .task_tools import _audit, _compact_task


def _compact_plan(plan: dict) -> dict:
    """计划 → 紧凑快照（审计与返回用，含复盘待确认状态）。"""
    return {
        "plan_id": plan["id"],
        "plan_date": plan["plan_date"],
        "status": plan["status"],
        "goal": plan.get("goal") or "",
        "reasoning_summary": plan.get("reasoning_summary") or "",
        "expected_total": plan["expected_total"],
        "actual_total": plan["actual_total"],
        "items": [{
            "item_id": i["id"],
            "task_id": i["task_id"],
            "title": i["title"],
            "category": i["category"],
            "kind": i["kind"],
            "expected_minutes": i["expected_minutes"],
            "actual_minutes": i["actual_minutes"],
            "suggested_time": i.get("suggested_time") or "",
        } for i in plan["items"]],
        "review_status": plan.get("review_status") or "none",
        "review_verdict": plan.get("review_verdict") or "",
        "review_reasoning": plan.get("review_reasoning") or "",
        "adjustments": plan.get("adjustments") or [],
    }


# ---------- 读 ----------
def get_plan(args: dict, ctx=None) -> dict:
    """查看某天计划（默认最新一份）。返回 plan + items + 该日实时实际分钟。"""
    plan_date = (args.get("plan_date") or "").strip()
    if plan_date:
        plan = psvc.get_plan(plan_date)
        if not plan:
            return {"found": False, "message": f"{plan_date} 没有计划"}
        return {"found": True, "plan": _compact_plan(plan)}
    plans = psvc.list_plans(1)
    if not plans:
        return {"found": False, "message": "还没有任何学习计划"}
    return {"found": True, "plan": _compact_plan(plans[0])}


def get_plan_vs_actual(args: dict, ctx=None) -> dict:
    """某天计划 vs 实际执行对比（默认最新一份）：确定性偏差，不编造。"""
    plan_date = (args.get("plan_date") or "").strip()
    if not plan_date:
        plans = psvc.list_plans(1)
        if not plans:
            return {"found": False, "message": "还没有任何学习计划"}
        plan_date = plans[0]["plan_date"]
    diff = psvc.compute_plan_vs_actual(plan_date)
    if not diff:
        return {"found": False, "message": f"{plan_date} 没有计划"}
    return {"found": True, **diff}


# ---------- 写 ----------
def validate_create_plan(args: dict) -> dict:
    """参数校验 + 清洗：plan_date / items 必填；每项 task_id 必填（先 create_task 拿 id）。"""
    args = dict(args or {})
    plan_date = (args.get("plan_date") or "").strip()
    if not plan_date:
        raise ValueError("create_plan 缺少必填参数 plan_date")
    args["plan_date"] = plan_date
    items = args.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("create_plan 缺少 items 数组（每项含 task_id）")
    clean_items = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"create_plan items[{i}] 必须是对象")
        tid = it.get("task_id")
        if tid is None:
            raise ValueError(f"create_plan items[{i}] 缺少 task_id（先 create_task 拿 id 再建计划）")
        try:
            tid = int(tid)
        except (TypeError, ValueError):
            raise ValueError(f"create_plan items[{i}] 的 task_id 必须是数字")
        item = dict(it)
        item["task_id"] = tid
        if item.get("suggested_time") is not None:
            item["suggested_time"] = str(item["suggested_time"]).strip()[:50]
        clean_items.append(item)
    args["items"] = clean_items
    return args


def create_plan(args: dict, ctx=None) -> dict:
    """创建/重建某天计划（直接生效）。计划项必须已存在任务（Agent 先 create_task）。"""
    try:
        plan = psvc.create_plan(
            args["plan_date"], args["items"],
            goal=args.get("goal") or "",
            reasoning_summary=args.get("reasoning_summary") or "",
            run_id=(ctx.run_id if ctx is not None else "") or "",
        )
        after = _compact_plan(plan)
        _audit(ctx, "create_plan", args, {}, after)
        return {**after, "message": "计划已创建（直接生效）"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "create_plan", args, {}, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_submit_review(args: dict) -> dict:
    """参数校验 + 清洗：plan_date / verdict 必填；adjustments 必须是数组。"""
    args = dict(args or {})
    plan_date = (args.get("plan_date") or "").strip()
    if not plan_date:
        raise ValueError("submit_review 缺少必填参数 plan_date")
    args["plan_date"] = plan_date
    verdict = (args.get("verdict") or "").strip()
    if not verdict:
        raise ValueError("submit_review 缺少必填参数 verdict")
    args["verdict"] = verdict
    if args.get("reasoning") is not None:
        args["reasoning"] = str(args["reasoning"]).strip()
    if args.get("adjustments") is not None and not isinstance(args["adjustments"], list):
        raise ValueError("submit_review 的 adjustments 必须是数组")
    return args


def submit_review(args: dict, ctx=None) -> dict:
    """提交某天计划的复盘：记录判定 + 待确认调整。**调整不生效**，用户确认后才应用。"""
    plan_date = args["plan_date"]
    before = _compact_plan(psvc.get_plan(plan_date)) if psvc.get_plan(plan_date) else {}
    try:
        plan = psvc.submit_review(
            plan_date, args["verdict"],
            reasoning=args.get("reasoning") or "",
            adjustments=args.get("adjustments") or [],
            run_id=(ctx.run_id if ctx is not None else "") or "",
        )
        after = _compact_plan(plan)
        _audit(ctx, "submit_review", args, before, after)
        return {**after, "message": "复盘已提交（调整待确认，确认后才生效）"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "submit_review", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise
