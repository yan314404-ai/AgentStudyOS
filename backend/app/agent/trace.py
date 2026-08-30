"""Agent 执行轨迹：逐步写 agent_trace_events，供前端时间线轮询展示。

事件类型：observe / plan / tool_call / tool_result / reflect / replan / error
内容都做深截断（≤800 字），防止 trace 膨胀。
"""
import json
from datetime import datetime

from ..db import connect

TRACE_LIMIT = 800


class TraceStore:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.seq = 0

    def write(self, event_type: str, content: dict) -> None:
        self.seq += 1
        conn = connect()
        conn.execute(
            "INSERT INTO agent_trace_events(run_id,seq,event_type,content_json,created_at) VALUES(?,?,?,?,?)",
            (self.run_id, self.seq, event_type, json.dumps(content, ensure_ascii=False),
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        conn.close()

    # ---------- 语义化写入 ----------
    def observe(self, tool: str, result: dict) -> None:
        self.write("observe", {"tool": tool, "result": shorten(result)})

    def plan(self, plan: dict) -> None:
        self.write("plan", {"plan": plan})

    def tool_call(self, tool: str, args: dict) -> None:
        self.write("tool_call", {"tool": tool, "args": args})

    def tool_result(self, tool: str, result: dict, ok: bool, cached: bool = False) -> None:
        self.write("tool_result", {"tool": tool, "ok": ok, "cached": cached, "result": shorten(result)})

    def reflect(self, reflection: dict) -> None:
        self.write("reflect", {"reflection": reflection})

    def replan(self, reason: str) -> None:
        self.write("replan", {"reason": reason})

    def error(self, message: str) -> None:
        self.write("error", {"message": message})

    # ---------- 读取 ----------
    @staticmethod
    def summary(run_id: str) -> list:
        conn = connect()
        rows = conn.execute(
            "SELECT seq, event_type, content_json, created_at FROM agent_trace_events WHERE run_id=? ORDER BY seq",
            (run_id,),
        ).fetchall()
        conn.close()
        return [
            {
                "seq": r["seq"],
                "event_type": r["event_type"],
                "content": json.loads(r["content_json"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def shorten(obj, limit: int = TRACE_LIMIT):
    """深截断：对象转 JSON 后超长则只留预览，避免 trace / 上下文膨胀。"""
    try:
        text = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"_error": "不可序列化的结果"}
    if len(text) <= limit:
        return obj
    return {"_truncated": True, "preview": text[:limit] + "…"}
