"""Agent Run 持久化：agent_runs 表 + stale 恢复 + 单运行锁。

run_id 由 gen_run_id() 生成；路由层负责建行 + 单锁，运行时只更新。
"""
import json
import uuid
from datetime import datetime

from ..db import connect

STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# RunRepo.update 允许更新的列（白名单，防 SQL 注入）
_FINISH_FIELDS = {
    "status", "model", "iteration", "finished_at", "state_json", "planner_output_json",
    "final_reply", "reflection_json", "error", "token_usage_json", "intent",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def gen_run_id() -> str:
    return uuid.uuid4().hex[:16]


class RunRepo:
    @staticmethod
    def create(run_id: str, goal: str, available_time: int, model: str = "",
               intent: str = "") -> None:
        conn = connect()
        conn.execute(
            "INSERT INTO agent_runs(run_id,goal,available_time,status,model,intent,started_at,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (run_id, goal, available_time, STATUS_RUNNING, model, intent or "", now(), now()),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get(run_id: str):
        conn = connect()
        row = conn.execute("SELECT * FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list(limit: int = 20) -> list:
        conn = connect()
        rows = conn.execute(
            "SELECT id, run_id, goal, status, iteration, started_at, finished_at, error "
            "FROM agent_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update(run_id: str, **fields) -> None:
        data = {k: v for k, v in fields.items() if k in _FINISH_FIELDS}
        if not data:
            return
        sets = ",".join(f"{k}=?" for k in data)
        conn = connect()
        conn.execute(f"UPDATE agent_runs SET {sets} WHERE run_id=?", list(data.values()) + [run_id])
        conn.commit()
        conn.close()

    @staticmethod
    def has_running() -> bool:
        conn = connect()
        row = conn.execute("SELECT 1 AS x FROM agent_runs WHERE status=? LIMIT 1", (STATUS_RUNNING,)).fetchone()
        conn.close()
        return bool(row)

    @staticmethod
    def recover_stale_runs() -> int:
        """把遗留 running 置为 failed（进程崩溃/重启后的残留），返回处理条数。"""
        conn = connect()
        cur = conn.execute(
            "UPDATE agent_runs SET status=?, finished_at=?, error=? WHERE status=?",
            (STATUS_FAILED, now(), "进程中断，run 未完成", STATUS_RUNNING),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return n
