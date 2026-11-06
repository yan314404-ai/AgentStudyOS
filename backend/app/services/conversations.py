"""对话领域服务：多轮对话的持久化（Phase 5）。

一个 conversation = 一串 turn（user / assistant / run），加一份「挂起的槽位」。
挂起槽位用于「缺槽位 → 追问 → 用户补一句」这条多轮路径：

    user: "帮我安排学习"        → intent=plan, missing=["date"] → 追问「哪一天的计划？」
    (pending_json = {"intent":"plan","slots":{}})
    user: "明天"                → merge_pending → slots={date:...}, missing=[] → 发起 run

为什么挂起要落库而不是放内存：Web 版会刷新页面、后端会重启，内存里的多轮状态一丢，
用户就得重说一遍；落库后刷新页面还能看到「刚才问了你哪一天」。

不存 token/成本在这里：那是 agent_runs 的事，对话只记录「说了什么、识别成什么、触发了哪个 run」。
"""
import json
import sqlite3
import uuid
from datetime import datetime

from ..db import connect

STATUS_ACTIVE = "active"
STATUS_CLOSED = "closed"

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class BadRequest(ValueError):
    """参数不合法（对话领域）。"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_conv_id() -> str:
    return "cv" + uuid.uuid4().hex[:14]


def _loads(raw: str) -> dict:
    try:
        obj = json.loads(raw or "")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _conv_row(row) -> dict:
    return {
        "conv_id": row["conv_id"],
        "status": row["status"],
        "pending": _loads(row["pending_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _turn_row(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "intent": _loads(row["intent_json"]),
        "run_id": row["run_id"] or "",
        "created_at": row["created_at"],
    }


# ---------- 会话 ----------
def create(conv_id: str = "") -> dict:
    """新建会话（不传 conv_id 则自动生成）。

    幂等：传一个已存在的 conv_id 时返回原会话，而不是抛 UNIQUE 冲突（那会变成 500）。
    前端「新会话」按钮每次都生成新 id，但外部调用/重试/双击都可能撞上同一个 id。
    """
    conv_id = (conv_id or "").strip() or new_conv_id()
    existing = get(conv_id)
    if existing:
        return existing
    now = _now()
    conn = connect()
    try:
        try:
            conn.execute(
                "INSERT INTO agent_conversations(conv_id,status,pending_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?)",
                (conv_id, STATUS_ACTIVE, "", now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # 两个请求同时过了上面的 get 检查 —— 后到的那个改用先到的会话。
            # 这里不抛异常：同一 id 想建两次，语义上「有个能用的会话」就够了。
            conn.rollback()
    finally:
        conn.close()
    return get(conv_id)


def get_or_create(conv_id: str = "") -> dict:
    """有则取，无则建（前端首次进入对话时调用）。

    已结束的会话不复用：status=closed 意味着「这轮对话结束了」，用户再说话应该开新会话，
    而不是把话续接到一个已经关掉的会话里（否则 close 就只是改了个没人看的字段）。
    """
    conv_id = (conv_id or "").strip()
    if conv_id:
        conv = get(conv_id)
        if conv and conv["status"] == STATUS_ACTIVE:
            return conv
        if conv:
            return create()
    return create(conv_id)


def get(conv_id: str) -> dict | None:
    """单个会话详情（含全部 turn）。"""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM agent_conversations WHERE conv_id=?", ((conv_id or "").strip(),)
        ).fetchone()
        if not row:
            return None
        turns = conn.execute(
            "SELECT * FROM agent_conversation_turns WHERE conv_id=? ORDER BY id",
            (row["conv_id"],),
        ).fetchall()
    finally:
        conn.close()
    out = _conv_row(row)
    out["turns"] = [_turn_row(t) for t in turns]
    return out


def list_conversations(limit: int = 20) -> list:
    """会话列表（最近更新在前，不含 turn 明细）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM agent_conversation_turns t WHERE t.conv_id=c.conv_id) AS turns "
            "FROM agent_conversations c ORDER BY c.updated_at DESC, c.id DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        item = _conv_row(r)
        item["turn_count"] = r["turns"]
        # 列表页只给最后一句话做预览，避免拖全量 turn
        item.pop("pending", None)
        out.append(item)
    return out


def set_pending(conv_id: str, pending: dict | None) -> None:
    """写/清挂起槽位（None 或空 dict = 清空）。

    已结束的会话不允许再挂起：close 的语义就是「这轮对话结束了」，
    如果还能往里写 pending，用户下次刷新页面会看到一条「在问你已经关掉的会话」的追问。
    """
    conv_id = (conv_id or "").strip()
    if not conv_id:
        raise BadRequest("conv_id 不能为空")
    conn = connect()
    try:
        row = conn.execute(
            "SELECT status FROM agent_conversations WHERE conv_id=?", (conv_id,)
        ).fetchone()
        if not row:
            raise BadRequest(f"会话 {conv_id} 不存在")
        if row["status"] == STATUS_CLOSED:
            raise BadRequest(f"会话 {conv_id} 已结束，不能继续追加对话")
        payload = json.dumps(pending, ensure_ascii=False) if pending else ""
        conn.execute(
            "UPDATE agent_conversations SET pending_json=?, updated_at=? WHERE conv_id=?",
            (payload, _now(), conv_id),
        )
        conn.commit()
    finally:
        conn.close()


def close(conv_id: str) -> dict:
    """结束会话（不再接受挂起追问）。"""
    conn = connect()
    try:
        conn.execute(
            "UPDATE agent_conversations SET status=?, pending_json='', updated_at=? WHERE conv_id=?",
            (STATUS_CLOSED, _now(), (conv_id or "").strip()),
        )
        conn.commit()
    finally:
        conn.close()
    return get(conv_id) or {}


# ---------- 轮次 ----------
def add_turn(conv_id: str, role: str, content: str, intent: dict | None = None,
             run_id: str = "") -> dict:
    """追加一轮对话（user / assistant）。intent 存该轮的识别结果，便于事后回看。"""
    if role not in (ROLE_USER, ROLE_ASSISTANT):
        raise BadRequest("role 必须是 user 或 assistant")
    conv_id = (conv_id or "").strip()
    if not conv_id:
        raise BadRequest("conv_id 不能为空")
    now = _now()
    conn = connect()
    try:
        owner = conn.execute(
            "SELECT status FROM agent_conversations WHERE conv_id=?", (conv_id,)
        ).fetchone()
        if not owner:
            raise BadRequest(f"会话 {conv_id} 不存在")
        if owner["status"] == STATUS_CLOSED:
            raise BadRequest(f"会话 {conv_id} 已结束，不能继续追加对话")
        cur = conn.execute(
            "INSERT INTO agent_conversation_turns(conv_id,role,content,intent_json,run_id,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (conv_id, role, content or "", json.dumps(intent or {}, ensure_ascii=False),
             run_id or "", now),
        )
        turn_id = cur.lastrowid
        conn.execute("UPDATE agent_conversations SET updated_at=? WHERE conv_id=?", (now, conv_id))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_conversation_turns WHERE id=?", (turn_id,)
        ).fetchone()
    finally:
        conn.close()
    return _turn_row(row)
