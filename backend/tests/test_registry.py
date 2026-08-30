"""ToolRegistry 单测：注册 / 未知工具 / 去重缓存 / 参数校验失败。"""
import unittest

from helpers import reset_db

from app.agent.tools import build_registry


class TestRegistry(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.reg = build_registry()

    def test_all_tools_registered(self):
        names = self.reg.names()
        expected = ("get_learning_overview", "get_recent_learning_sessions",
                    "get_weak_points", "get_task_list", "get_courses", "get_reports",
                    "create_task", "add_session", "update_task", "complete_task",
                    "create_review_task",
                    "get_plan", "get_plan_vs_actual", "create_plan", "submit_review",
                    "get_memories", "remember", "forget_memory")
        for n in expected:
            self.assertIn(n, names)
        self.assertEqual(len(names), len(expected))

    def test_unknown_tool_returns_clean_error(self):
        res = self.reg.execute("no_such_tool", {})
        self.assertFalse(res["ok"])
        self.assertIn("未知工具", res["error"])

    def test_read_tool_same_args_cached(self):
        r1 = self.reg.execute("get_learning_overview", {})
        r2 = self.reg.execute("get_learning_overview", {})
        self.assertTrue(r1["ok"])
        self.assertTrue(r2["ok"])
        self.assertTrue(r2.get("cached"))
        self.assertEqual(r1["data"], r2["data"])

    def test_read_tool_diff_args_not_cached(self):
        r1 = self.reg.execute("get_recent_learning_sessions", {"days": 7})
        r2 = self.reg.execute("get_recent_learning_sessions", {"days": 14})
        self.assertFalse(r1.get("cached"))
        self.assertFalse(r2.get("cached"))

    def test_write_tool_not_cached(self):
        r1 = self.reg.execute("create_task", {"title": "重复写"})
        r2 = self.reg.execute("create_task", {"title": "重复写"})
        self.assertTrue(r1["ok"])
        self.assertTrue(r2["ok"])
        self.assertFalse(r2.get("cached"))

    def test_args_validation_failure_reported(self):
        res = self.reg.execute("create_task", {})  # 缺 title
        self.assertFalse(res["ok"])
        self.assertIn("title", res["error"])


if __name__ == "__main__":
    unittest.main()
