"""Executor 单测：逐条执行、read 去重、失败如实上报（不静默）、trace 落库。"""
import unittest

from helpers import reset_db

from app.agent.executor import Executor
from app.agent.tools import build_registry
from app.agent.trace import TraceStore


class TestExecutor(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.registry = build_registry()
        self.executor = Executor(self.registry)

    def _trace(self, run_id="exec-test"):
        return TraceStore(run_id)

    def test_runs_all_steps(self):
        plan = {"goal": "g", "steps": [
            {"tool": "get_learning_overview", "arguments": {}},
            {"tool": "get_task_list", "arguments": {}},
        ]}
        results = self.executor.run({}, plan, self._trace())
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["ok"] for r in results))
        self.assertTrue(all("data" in r for r in results))
        self.assertTrue(all("cost_ms" in r for r in results))

    def test_read_tool_dedup_via_cache(self):
        plan = {"goal": "g", "steps": [
            {"tool": "get_learning_overview", "arguments": {}},
            {"tool": "get_learning_overview", "arguments": {}},
        ]}
        results = self.executor.run({}, plan, self._trace())
        self.assertFalse(results[0]["cached"])
        self.assertTrue(results[1]["cached"])

    def test_failed_step_recorded_not_silent(self):
        plan = {"goal": "g", "steps": [
            {"tool": "no_such_tool", "arguments": {}},
        ]}
        results = self.executor.run({}, plan, self._trace())
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["ok"])
        self.assertIn("未知工具", results[0]["error"])

    def test_trace_has_tool_call_result_error(self):
        plan = {"goal": "g", "steps": [
            {"tool": "get_task_list", "arguments": {}},
            {"tool": "bad_tool", "arguments": {}},
        ]}
        self.executor.run({}, plan, self._trace("exec-trace2"))
        events = TraceStore.summary("exec-trace2")
        types = [e["event_type"] for e in events]
        self.assertIn("tool_call", types)
        self.assertIn("tool_result", types)
        self.assertIn("error", types)  # 失败工具要写 error 事件


if __name__ == "__main__":
    unittest.main()
