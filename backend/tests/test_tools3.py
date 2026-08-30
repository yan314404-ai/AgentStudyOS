"""Phase 3 计划工具单测：get_plan / get_plan_vs_actual / create_plan / submit_review（审计捕获）。

create_plan 直接生效 + 审计；submit_review 只记待确认调整（不建任务不改计划项）；
偏差走 task_sessions 真实 SUM，诚实不编造。
"""
import unittest
from datetime import date, timedelta

from helpers import reset_db

from app import crud
from app.agent.tools import build_registry
from app.services import tasks as tsvc

# 固定「昨天」做计划日，方便与 task_sessions 关联
Y = (date.today() - timedelta(days=1)).isoformat()


class FakeContext:
    """确定性审计捕获器：不写库，只记录工具提交的 before/after。"""

    def __init__(self):
        self.run_id = "test-run"
        self.actions = []

    def audit(self, tool, args, before, after, ok=True, error=""):
        self.actions.append({"tool": tool, "args": args, "before": before,
                             "after": after, "ok": ok, "error": error})


def _new_task(title: str, category: str = "算法"):
    return crud.create("tasks", {
        "title": title, "phase": "未分组", "category": category,
        "status": "待开始", "progress": 0, "created_at": "2026-08-24T00:00:00",
    })


class TestPlanTools(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.reg = build_registry()
        self.ctx = FakeContext()

    def _ok(self, tool, args=None, ctx=None):
        res = self.reg.execute(tool, args or {}, ctx)
        self.assertTrue(res["ok"], res.get("error"))
        return res["data"]

    # ---------- 读工具 ----------
    def test_get_plan_empty(self):
        data = self._ok("get_plan")
        self.assertFalse(data["found"])

    def test_get_plan_after_create(self):
        t = _new_task("算法一")
        self._ok("create_plan", {"plan_date": Y, "items": [{"task_id": t["id"], "expected_minutes": 120}]}, self.ctx)
        data = self._ok("get_plan")
        self.assertTrue(data["found"])
        plan = data["plan"]
        self.assertEqual(plan["plan_date"], Y)
        self.assertEqual(plan["expected_total"], 120)
        self.assertEqual(plan["actual_total"], 0)  # 还没学
        self.assertEqual(plan["items"][0]["title"], "算法一")
        self.assertEqual(plan["review_status"], "none")

    def test_get_plan_by_date_and_missing(self):
        t = _new_task("算法一")
        self._ok("create_plan", {"plan_date": Y, "items": [{"task_id": t["id"], "expected_minutes": 60}]}, self.ctx)
        data = self._ok("get_plan", {"plan_date": Y})
        self.assertEqual(data["plan"]["expected_total"], 60)
        miss = self._ok("get_plan", {"plan_date": "2099-01-01"})
        self.assertFalse(miss["found"])

    def test_get_plan_vs_actual_honest(self):
        t = _new_task("算法一")
        self._ok("create_plan", {"plan_date": Y, "items": [{"task_id": t["id"], "expected_minutes": 120}]}, self.ctx)
        tsvc.add_session(t["id"], 90, log_date=Y, source="agent")  # 真实执行 90/120
        data = self._ok("get_plan_vs_actual")
        self.assertTrue(data["found"])
        self.assertEqual(data["planned_total"], 120)
        self.assertEqual(data["actual_total"], 90)
        self.assertEqual(data["deviation_pct"], -25)
        self.assertEqual(data["verdict"], "over")  # -25% ≤ -20 → 计划过量
        self.assertEqual(data["items"][0]["diff"], 90 - 120)
        miss = self._ok("get_plan_vs_actual", {"plan_date": "2099-01-01"})
        self.assertFalse(miss["found"])

    # ---------- 写工具 ----------
    def test_create_plan_direct_and_audited(self):
        t = _new_task("算法一")
        data = self._ok("create_plan", {
            "plan_date": Y,
            "items": [{"task_id": t["id"], "expected_minutes": 120}],
            "goal": "刷题",
        }, self.ctx)
        self.assertEqual(data["plan_date"], Y)
        self.assertEqual(data["review_status"], "none")
        self.assertIn("message", data)
        self.assertEqual(len(self.ctx.actions), 1)
        act = self.ctx.actions[0]
        self.assertEqual(act["tool"], "create_plan")
        self.assertEqual(act["before"], {})
        self.assertEqual(act["after"]["plan_id"], data["plan_id"])
        self.assertEqual(act["after"]["expected_total"], 120)

    def test_create_plan_requires_existing_task(self):
        res = self.reg.execute(
            "create_plan", {"plan_date": Y, "items": [{"task_id": 999999, "expected_minutes": 60}]}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("任务不存在", res["error"])
        self.assertEqual(len(self.ctx.actions), 1)  # 失败也审计 ok=0
        self.assertEqual(self.ctx.actions[0]["ok"], 0)

    def test_submit_review_pending_not_effective(self):
        t = _new_task("算法一")
        self._ok("create_plan", {"plan_date": Y, "items": [{"task_id": t["id"], "expected_minutes": 120}]}, self.ctx)
        n_tasks = len(crud.fetch_all("tasks"))
        data = self._ok("submit_review", {
            "plan_date": Y,
            "verdict": "计划过量",
            "reasoning": "实际只有 90 分钟",
            "adjustments": [{"action": "add", "title": "LeetCode 第1题", "category": "算法", "expected_minutes": 30}],
        }, self.ctx)
        self.assertEqual(data["review_status"], "pending")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["adjustments"]), 1)
        # 待确认不直接建任务 / 不改计划项
        self.assertEqual(len(crud.fetch_all("tasks")), n_tasks)
        # 审计：before=原计划，after=pending
        act = self.ctx.actions[-1]
        self.assertEqual(act["tool"], "submit_review")
        self.assertEqual(act["before"]["review_status"], "none")
        self.assertEqual(act["after"]["review_status"], "pending")

    def test_submit_review_no_plan_fails(self):
        res = self.reg.execute("submit_review", {"plan_date": Y, "verdict": "计划过量"}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("没有计划", res["error"])

    def test_submit_review_missing_verdict(self):
        res = self.reg.execute("submit_review", {"plan_date": Y}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("verdict", res["error"])


if __name__ == "__main__":
    unittest.main()
