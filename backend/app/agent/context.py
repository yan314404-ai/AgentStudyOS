"""AgentContext：给写工具注入 run 上下文（run_id + 审计）。

全直接模式：所有写操作直接生效，由 agent_actions 记录「参数 + before/after 快照」兜底，
before 快照即人工回滚的依据。审计是尽力而为（best-effort）：写失败不打断 run。
"""
import json
from datetime import datetime

from ..db import connect


class AgentContext:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def audit(self, tool: str, args: dict, before: dict, after: dict,
              ok: bool = True, error: str = "") -> None:
        """记录一次写操作。参数 / before / after 均序列化为 JSON 快照。"""
        try:
            conn = connect()
            conn.execute(
                "INSERT INTO agent_actions(run_id,tool,args_json,before_json,after_json,ok,error,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    self.run_id,
                    tool,
                    json.dumps(args or {}, ensure_ascii=False),
                    json.dumps(before or {}, ensure_ascii=False),
                    json.dumps(after or {}, ensure_ascii=False),
                    1 if ok else 0,
                    (error or "")[:2000],
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
        except Exception:  # noqa: BLE001 —— 审计失败不能打断 run
            pass
        finally:
            conn.close()
