"""Phase 4 记忆工具：结构化长期记忆的读写（Agent 记住 → 用户确认 → 规划遵守）。

- get_memories   只读，列出待确认 + 已确认记忆（无审计）
- remember       记住一条（直接写 agent_memories，但 status=pending **待确认**，不生效）
- forget_memory  软删一条（status=forgotten，列表/注入都过滤）

业务不变量走 app/services/memories.py（与路由共用同一套行为）。
记住/忘记是写操作，走 task_tools._audit 记入 agent_actions。
"""
from ...services import memories as msvc
from .task_tools import _audit


def _compact(m: dict) -> dict:
    """记忆 → 紧凑快照（审计与返回用，含待确认状态）。"""
    return {
        "memory_id": m["id"],
        "mkey": m["mkey"],
        "mtype": m["mtype"],
        "content": m["content"],
        "keywords": m["keywords"] or "",
        "importance": m["importance"],
        "status": m["status"],
    }


# ---------- 读 ----------
def get_memories(args: dict, ctx=None) -> dict:
    """列出记忆（pending + active，pending 在前）。可选 type 过滤。"""
    mtype = (args.get("type") or "").strip()
    mems = msvc.get_memories()
    if mtype:
        mems = [m for m in mems if m["mtype"] == mtype]
    return {"count": len(mems), "memories": [_compact(m) for m in mems]}


# ---------- 写 ----------
def validate_remember(args: dict) -> dict:
    """参数校验 + 清洗：key/content 必填；type ∈ 4 类；importance 转 int 夹 1-5。"""
    args = dict(args or {})
    key = (args.get("key") or "").strip()
    if not key:
        raise ValueError("remember 缺少必填参数 key（短中文标识，如「学习时段」）")
    args["key"] = key
    content = (args.get("content") or "").strip()
    if not content:
        raise ValueError("remember 缺少必填参数 content（完整事实，如「工作日 20:00-23:00 学习效率最高」）")
    args["content"] = content
    mtype = (args.get("type") or args.get("mtype") or "preference").strip()
    if mtype not in msvc.MTYPES:
        raise ValueError(f"remember 的 type 必须是 {'/'.join(sorted(msvc.MTYPES))} 之一")
    args["type"] = mtype
    if args.get("importance") is not None:
        try:
            args["importance"] = int(args["importance"])
        except (TypeError, ValueError):
            raise ValueError("remember 参数 importance 必须是 1~5 的数字")
    if args.get("keywords") is not None:
        args["keywords"] = str(args["keywords"]).strip()
    return args


def remember(args: dict, ctx=None) -> dict:
    """记住一条记忆：**待确认**（status=pending，面板确认后才参与规划）。"""
    try:
        m = msvc.remember(
            args["key"], args["content"],
            mtype=args["type"], importance=args.get("importance") or 3,
            keywords=args.get("keywords") or "",
            run_id=(ctx.run_id if ctx is not None else "") or "",
        )
        after = _compact(m)
        _audit(ctx, "remember", args, {}, after)
        return {**after, "message": "已记住（待确认，确认后生效）"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "remember", args, {}, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise


def validate_forget_memory(args: dict) -> dict:
    args = dict(args or {})
    key = (args.get("key") or "").strip()
    if not key:
        raise ValueError("forget_memory 缺少必填参数 key")
    args["key"] = key
    return args


def forget_memory(args: dict, ctx=None) -> dict:
    """软删一条记忆（status=forgotten，列表/注入都过滤）。按 key 定位。"""
    key = args["key"]
    existing = msvc.get_memory_by_key(key)
    before = _compact(existing) if existing else {}
    try:
        if existing:
            msvc.forget_memory(existing["id"])
        _audit(ctx, "forget_memory", args, before, {})
        return {"key": key, "forgotten": bool(existing), "message": "已忘记（软删留痕）"}
    except Exception as e:  # noqa: BLE001
        _audit(ctx, "forget_memory", args, before, {}, ok=False, error=f"{type(e).__name__}: {e}")
        raise
