"""阶段 2 新工具单测：读工具 get_courses/get_reports + 写工具（直接生效 + 审计捕获）。"""
import unittest
from datetime import datetime

from helpers import reset_db

from app import crud, stats
from app.agent.tools import build_registry
from app.db import connect


class FakeContext:
    """确定性审计捕获器：不写库，只记录工具提交的 before/after。"""

    def __init__(self):
        self.run_id = "test-run"
        self.actions = []

    def audit(self, tool, args, before, after, ok=True, error=""):
        self.actions.append({"tool": tool, "args": args, "before": before,
                             "after": after, "ok": ok, "error": error})


class TestTools2(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.reg = build_registry()
        self.ctx = FakeContext()

    def _ok(self, tool, args=None, ctx=None):
        res = self.reg.execute(tool, args or {}, ctx)
        self.assertTrue(res["ok"], res.get("error"))
        return res["data"]

    def _db_task(self, title: str):
        return [t for t in crud.fetch_all("tasks") if t["title"] == title][0]

    # ---------- 读工具 ----------
    def test_get_courses_all(self):
        data = self._ok("get_courses")
        self.assertGreater(data["count"], 0)
        for k in ("id", "name", "platform", "url", "teacher", "progress", "status", "task_id"):
            self.assertIn(k, data["courses"][0])

    def test_get_courses_by_task(self):
        leet = [t for t in crud.fetch_all("tasks") if "LeetCode" in t["title"]][0]
        data = self._ok("get_courses", {"task_id": leet["id"]})
        self.assertGreater(data["count"], 0)
        for c in data["courses"]:
            self.assertEqual(c["task_id"], leet["id"])

    def test_get_reports_week_no_cache(self):
        data = self._ok("get_reports", {"period_type": "week"})
        self.assertEqual(data["period_type"], "week")
        self.assertEqual(data["ai_content"], "")
        self.assertIn("total_minutes", data["stats"])
        self.assertNotIn("logs", data["stats"])  # 原始打卡明细被压缩掉

    def test_get_reports_month(self):
        data = self._ok("get_reports", {"period_type": "month"})
        self.assertEqual(data["period_type"], "month")

    def test_get_reports_cache_hit(self):
        s = stats.weekly_stats()
        conn = connect()
        conn.execute(
            "INSERT OR REPLACE INTO reports(period_type,period_start,period_end,stats_json,content,created_at) VALUES(?,?,?,?,?,?)",
            ("week", s["start"], s["end"], "{}", "【测试周报正文】",
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        conn.close()
        data = self._ok("get_reports", {"period_type": "week"})
        self.assertEqual(data["ai_content"], "【测试周报正文】")

    # ---------- 写工具（直接生效 + 审计） ----------
    def test_create_task_direct_and_audited(self):
        data = self._ok("create_task", {"title": "工具测试任务", "hours": 3}, self.ctx)
        self.assertEqual(data["status"], "待开始")
        self.assertEqual(len(self.ctx.actions), 1)
        act = self.ctx.actions[0]
        self.assertEqual(act["tool"], "create_task")
        self.assertEqual(act["before"], {})
        self.assertEqual(act["after"]["task_id"], data["task_id"])

    def test_add_session_audited(self):
        t = self._db_task("Git + Linux + HTTP/JSON/API")
        data = self._ok("add_session", {"task_id": t["id"], "minutes": 60}, self.ctx)
        self.assertEqual(data["task"]["spent_minutes"], (t["spent_minutes"] or 0) + 60)
        self.assertEqual(len(self.ctx.actions), 1)
        act = self.ctx.actions[0]
        self.assertEqual(act["tool"], "add_session")
        self.assertEqual(act["after"]["task"]["task_id"], t["id"])

    def test_update_task_progress_locks_manual(self):
        t = self._db_task("Git + Linux + HTTP/JSON/API")
        data = self._ok("update_task", {"task_id": t["id"], "progress": 50}, self.ctx)
        self.assertEqual(data["progress"], 50)
        row = crud.fetch_one("tasks", t["id"])
        self.assertEqual(row["manual_progress"], 50)  # progress → manual 锁定语义
        self.assertEqual(len(self.ctx.actions), 1)
        self.assertEqual(self.ctx.actions[0]["before"]["task_id"], t["id"])

    def test_update_task_restore_auto(self):
        t = self._db_task("Git + Linux + HTTP/JSON/API")
        data = self._ok("update_task", {"task_id": t["id"], "manual_progress": -1}, self.ctx)
        self.assertEqual(data["manual_progress"], -1)

    def test_complete_task(self):
        t = self._db_task("Git + Linux + HTTP/JSON/API")
        data = self._ok("complete_task", {"task_id": t["id"]}, self.ctx)
        self.assertEqual(data["status"], "已完成")
        self.assertEqual(data["progress"], 100)

    def test_create_review_task(self):
        t = self._db_task("Git + Linux + HTTP/JSON/API")
        data = self._ok("create_review_task", {"task_id": t["id"], "reason": "记不清"}, self.ctx)
        self.assertEqual(data["title"], "复习：" + t["title"])
        self.assertEqual(len(self.ctx.actions), 1)
        self.assertEqual(self.ctx.actions[0]["tool"], "create_review_task")

    def test_write_failure_audited_ok0(self):
        res = self.reg.execute("update_task", {"task_id": 999999, "status": "已完成"}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("任务不存在", res["error"])
        self.assertEqual(len(self.ctx.actions), 1)
        self.assertEqual(self.ctx.actions[0]["ok"], 0)
        self.assertIn("TaskNotFound", self.ctx.actions[0]["error"])

    def test_write_tool_not_cached(self):
        r1 = self.reg.execute("add_session", {"task_id": self._db_task("Git + Linux + HTTP/JSON/API")["id"], "minutes": 5}, self.ctx)
        r2 = self.reg.execute("add_session", {"task_id": self._db_task("Git + Linux + HTTP/JSON/API")["id"], "minutes": 5}, self.ctx)
        self.assertFalse(r1.get("cached"))
        self.assertFalse(r2.get("cached"))


if __name__ == "__main__":
    unittest.main()
