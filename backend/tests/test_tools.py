"""学习工具单测：读工具返回结构 + create_task 直接生效 + 写工具审计。"""
import unittest

from helpers import reset_db

from app import crud
from app.agent.tools import build_registry


class TestLearningTools(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.reg = build_registry()

    def _ok(self, tool, args=None):
        res = self.reg.execute(tool, args or {})
        self.assertTrue(res["ok"], res.get("error"))
        return res["data"]

    def test_learning_overview_structure(self):
        data = self._ok("get_learning_overview")
        for k in ("readiness", "algo_mastery", "bago_mastery", "project_progress",
                  "task_progress", "category_progress", "streak_days",
                  "week_total_minutes", "week_checkin_days"):
            self.assertIn(k, data)
        self.assertIsInstance(data["category_progress"], dict)
        self.assertIsInstance(data["readiness"], int)

    def test_recent_sessions_structure(self):
        data = self._ok("get_recent_learning_sessions", {"days": 7})
        self.assertIn("days", data)
        self.assertIn("sessions", data)
        self.assertIn("week_total_minutes", data)
        self.assertIn("month_total_minutes", data)
        self.assertIsInstance(data["sessions"], list)

    def test_weak_points_structure(self):
        data = self._ok("get_weak_points")
        for k in ("weak_categories", "lowest_category", "algorithm_mastery_pct",
                  "bago_mastery_pct", "rule"):
            self.assertIn(k, data)
        self.assertIsInstance(data["weak_categories"], list)

    def test_task_list_structure(self):
        data = self._ok("get_task_list")
        self.assertGreater(data["count"], 0)
        t = data["tasks"][0]
        for k in ("id", "phase", "category", "title", "progress", "status", "mode"):
            self.assertIn(k, t)

    def test_task_list_phase_filter(self):
        all_data = self._ok("get_task_list")
        agent = self._ok("get_task_list", {"phase": "4 · Agent"})
        self.assertGreater(all_data["count"], agent["count"])
        self.assertTrue(all(t["phase"].startswith("4 · Agent") for t in agent["tasks"]))

    def test_create_task_direct_effect(self):
        # 全直接：create_task 直接生效，status 默认「待开始」，进度 0，note 打标 🤖 Agent 创建
        data = self._ok("create_task", {"title": "复习 Attention", "hours": 2})
        self.assertEqual(data["status"], "待开始")
        self.assertEqual(data["title"], "复习 Attention")
        self.assertEqual(data["progress"], 0)
        tasks = self._ok("get_task_list")
        created = [t for t in tasks["tasks"] if t["title"] == "复习 Attention"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["status"], "待开始")
        self.assertEqual(created[0]["progress"], 0)
        row = crud.fetch_all("tasks", where="title=?", params=("复习 Attention",))[0]
        self.assertIn("🤖 Agent 创建", row["note"])

    def test_create_task_honors_status_whitelist(self):
        # 直接生效：传入的 status 生效（不再强制待确认）；白名单外字段丢弃；进度始终 0
        data = self._ok("create_task", {"title": "x", "status": "进行中", "progress": 99, "hack": 1})
        self.assertEqual(data["status"], "进行中")
        self.assertEqual(data["progress"], 0)
        created = [t for t in self._ok("get_task_list")["tasks"] if t["title"] == "x"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["status"], "进行中")
        self.assertEqual(created[0]["progress"], 0)

    def test_create_task_missing_title(self):
        res = self.reg.execute("create_task", {})
        self.assertFalse(res["ok"])
        self.assertIn("title", res["error"])

    def test_create_task_bad_hours(self):
        res = self.reg.execute("create_task", {"title": "x", "hours": "abc"})
        self.assertFalse(res["ok"])
        self.assertIn("hours", res["error"])


if __name__ == "__main__":
    unittest.main()
