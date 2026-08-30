"""AgentContext 审计单测：agent_actions 落库 + run_id 关联 + 失败记录（全直接模式的兜底）。"""
import json
import unittest

from helpers import reset_db

from app import crud
from app.agent.context import AgentContext


class TestAudit(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_audit_writes_row(self):
        ctx = AgentContext("run-abc")
        ctx.audit("create_task", {"title": "x"}, {}, {"task_id": 1, "title": "x"}, ok=True)
        rows = crud.fetch_all("agent_actions", where="run_id=?", params=("run-abc",))
        self.assertEqual(len(rows), 1)
        a = rows[0]
        self.assertEqual(a["tool"], "create_task")
        self.assertEqual(a["ok"], 1)
        self.assertEqual(json.loads(a["args_json"])["title"], "x")
        self.assertEqual(json.loads(a["after_json"])["task_id"], 1)
        self.assertEqual(json.loads(a["before_json"]), {})

    def test_audit_failure_recorded(self):
        ctx = AgentContext("run-abc")
        ctx.audit("update_task", {"task_id": 3}, {"progress": 10}, {},
                  ok=False, error="BadRequest: 任务不存在")
        rows = crud.fetch_all("agent_actions", where="run_id=?", params=("run-abc",))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ok"], 0)
        self.assertIn("BadRequest", rows[0]["error"])

    def test_audit_isolated_by_run(self):
        AgentContext("run-a").audit("create_task", {}, {}, {"task_id": 1})
        AgentContext("run-b").audit("create_task", {}, {}, {"task_id": 2})
        rows = crud.fetch_all("agent_actions")
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["run_id"] for r in rows}, {"run-a", "run-b"})


if __name__ == "__main__":
    unittest.main()
