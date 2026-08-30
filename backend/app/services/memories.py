"""记忆领域服务：结构化长期记忆（Phase 4）的唯一来源。

记忆 = 用户偏好/事实/目标/规则，Agent 用 remember 工具记住（**待确认** pending），
用户在 Agent 页确认（confirm_memory）才变 active 参与后续规划注入。
改同一条偏好 = 复用同 mkey 覆盖（status 回到 pending，需重新确认）。

写入口：
- remember       （Agent「记住」，upsert + status='pending'，不生效）
- confirm_memory （用户确认，pending → active，注入才看得到）
- reject_memory  （用户拒绝，pending → rejected）
- forget_memory  （用户删除，→ forgotten，软删留痕）
"""
from datetime import datetime

from ..db import connect

# 记忆类型白名单
MTYPES = {"preference", "fact", "goal", "rule"}
# 生命周期状态
PENDING, ACTIVE, REJECTED, FORGOTTEN = "pending", "active", "rejected", "forgotten"
# 注入上限（importance 降序取前 N，防烧 token）
INJECT_LIMIT = 20


class BadRequest(ValueError):
    """参数不合法（记忆领域）。"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _compact(row) -> dict:
    """记忆行 → 紧凑 dict（返回与注入用）。"""
    return {
        "id": row["id"],
        "mkey": row["mkey"],
        "mtype": row["mtype"],
        "content": row["content"],
        "keywords": row["keywords"] or "",
        "importance": row["importance"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------- 写：记住（待确认，不生效） ----------
def remember(key: str, content: str, mtype: str = "preference",
             importance: int = 3, keywords: str = "", run_id: str = "") -> dict:
    """按 mkey upsert 一条记忆：已存在则覆盖（status 回到 pending），否则新建。待确认。"""
    key = (key or "").strip()
    content = (content or "").strip()
    if not key or not content:
        raise BadRequest("key 和 content 不能为空")
    if mtype not in MTYPES:
        raise BadRequest(f"mtype 必须是 {'/'.join(sorted(MTYPES))} 之一")
    try:
        importance = max(1, min(5, int(importance)))
    except (TypeError, ValueError):
        raise BadRequest("importance 必须是 1~5 的数字")
    keywords = (keywords or "").strip()[:200]
    now = _now()
    conn = connect()
    try:
        exists = conn.execute("SELECT id FROM agent_memories WHERE mkey=?", (key,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE agent_memories SET content=?, mtype=?, importance=?, keywords=?, "
                "status=?, source_run_id=?, updated_at=? WHERE id=?",
                (content, mtype, importance, keywords, PENDING, run_id, now, exists["id"]),
            )
            mid = exists["id"]
        else:
            cur = conn.execute(
                "INSERT INTO agent_memories(mkey,mtype,content,keywords,importance,status,source_run_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (key, mtype, content, keywords, importance, PENDING, run_id, now, now),
            )
            mid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return get_memory(mid)


def get_memory(memory_id: int) -> dict | None:
    """单条记忆详情。"""
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM agent_memories WHERE id=?", (memory_id,)).fetchone()
    finally:
        conn.close()
    return _compact(row) if row else None


def get_memory_by_key(key: str) -> dict | None:
    """按 mkey 取记忆（记住覆盖 / forget_memory 定位用；任何状态都返回）。"""
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM agent_memories WHERE mkey=?", ((key or "").strip(),)).fetchone()
    finally:
        conn.close()
    return _compact(row) if row else None


# ---------- 读 ----------
def get_memories() -> list:
    """面板列表：pending + active（pending 在前、importance 降序、updated 降序）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_memories WHERE status IN (?,?) "
            "ORDER BY CASE status WHEN ? THEN 0 ELSE 1 END, importance DESC, updated_at DESC",
            (PENDING, ACTIVE, PENDING),
        ).fetchall()
    finally:
        conn.close()
    return [_compact(r) for r in rows]


def active_memories(limit: int = INJECT_LIMIT) -> list:
    """注入用：仅已确认（active）记忆，importance 降序，取前 limit 条。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_memories WHERE status=? ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (ACTIVE, limit),
        ).fetchall()
    finally:
        conn.close()
    return [_compact(r) for r in rows]


# ---------- 写：确认 / 拒绝 / 忘记（用户面板操作） ----------
def confirm_memory(memory_id: int) -> dict:
    """用户确认：pending → active，之后参与规划注入。"""
    row = _require_pending(memory_id)
    conn = connect()
    try:
        conn.execute("UPDATE agent_memories SET status=?, updated_at=? WHERE id=?",
                     (ACTIVE, _now(), memory_id))
        conn.commit()
    finally:
        conn.close()
    return get_memory(memory_id) or _compact(row)


def reject_memory(memory_id: int) -> dict:
    """用户拒绝：pending → rejected，不参与规划。"""
    row = _require_pending(memory_id)
    conn = connect()
    try:
        conn.execute("UPDATE agent_memories SET status=?, updated_at=? WHERE id=?",
                     (REJECTED, _now(), memory_id))
        conn.commit()
    finally:
        conn.close()
    return get_memory(memory_id) or _compact(row)


def forget_memory(memory_id: int) -> None:
    """用户删除：→ forgotten（软删留痕，GET/注入都过滤）。"""
    conn = connect()
    try:
        conn.execute("UPDATE agent_memories SET status=?, updated_at=? WHERE id=?",
                     (FORGOTTEN, _now(), memory_id))
        conn.commit()
    finally:
        conn.close()


def _require_pending(memory_id: int):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM agent_memories WHERE id=?", (memory_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise BadRequest("记忆不存在")
    if row["status"] != PENDING:
        raise BadRequest("该记忆不是待确认状态，无法确认/拒绝")
    return row
