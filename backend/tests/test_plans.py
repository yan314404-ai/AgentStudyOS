"""Phase 3 计划领域服务单测：迁移 v7 + 计划/对比/复盘待确认/确认应用/拒绝。"""
import unittest
from datetime import date, timedelta

from helpers import reset_db

from app import crud
from app.db import connect
from app.services import plans as psvc
from app.services import tasks as tsvc

# 固定用「昨天」做计划日，方便 find_unreviewed 判定
Y = (date.today() - timedelta(days=1)).isoformat()
TMR = (date.today() + timedelta(days=1)).isoformat()


def _task(title: str):
    rows = crud.fetch_all("tasks", where="title=?", params=(title,))
    return rows[0] if rows else None


def _new_task(title: str, category: str = "算法"):
    return crud.create("tasks", {
        "title": title, "phase": "未分组", "category": category,
        "status": "待开始", "progress": 0, "created_at": "2026-08-24T00:00:00",
    })


class TestMigrationV7(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_agent_plan_tables_exist(self):
        conn = connect()
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertIn("agent_plans", names)
        self.assertIn("agent_plan_items", names)


class TestCreatePlan(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_create_plan_basic(self):
        t = _new_task("算法一")
        plan = psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 120}], goal="G")
        self.assertEqual(plan["plan_date"], Y)
        self.assertEqual(plan["status"], "active")
        self.assertEqual(plan["expected_total"], 120)
        self.assertEqual(plan["actual_total"], 0)
        self.assertEqual(plan["items"][0]["title"], "算法一")
        self.assertEqual(plan["items"][0]["kind"], "task")
        self.assertIsNone(plan["prev_plan_id"])

    def test_prev_plan_chain(self):
        t1 = _new_task("T1")
        t2 = _new_task("T2")
        p1 = psvc.create_plan(Y, [{"task_id": t1["id"], "expected_minutes": 60}], goal="g1")
        p2 = psvc.create_plan(TMR, [{"task_id": t2["id"], "expected_minutes": 90}], goal="g2")
        self.assertIsNone(p1["prev_plan_id"])
        self.assertEqual(p2["prev_plan_id"], p1["id"])

    def test_upsert_same_date_rebuilds(self):
        t = _new_task("算法一")
        psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 120}])
        p2 = psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 60}])
        self.assertEqual(p2["expected_total"], 60)
        self.assertEqual(len(p2["items"]), 1)
        self.assertEqual(p2["id"], psvc.get_plan(Y)["id"])

    def test_create_plan_validation(self):
        t = _new_task("算法一")
        with self.assertRaises(psvc.BadRequest):
            psvc.create_plan("not-a-date", [{"task_id": t["id"]}])
        with self.assertRaises(psvc.BadRequest):
            psvc.create_plan(Y, [{"title": "缺 task_id"}])
        with self.assertRaises(psvc.BadRequest):
            psvc.create_plan(Y, [])
        with self.assertRaises(psvc.BadRequest):
            psvc.create_plan(Y, [{"task_id": 999999}])

    def test_get_plan_missing(self):
        self.assertIsNone(psvc.get_plan("2099-01-01"))
        self.assertIsNone(psvc.compute_plan_vs_actual(Y))


class TestPlanVsActual(unittest.TestCase):
    def setUp(self):
        reset_db()

    def _plan_with(self, expected, actual):
        t = _new_task("算法一")
        psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": expected}])
        if actual:
            tsvc.add_session(t["id"], actual, log_date=Y, source="agent")
        return t

    def test_over_planning_verdict(self):
        self._plan_with(120, 30)  # -75% → over
        diff = psvc.compute_plan_vs_actual(Y)
        self.assertEqual(diff["planned_total"], 120)
        self.assertEqual(diff["actual_total"], 30)
        self.assertEqual(diff["deviation_pct"], -75)
        self.assertEqual(diff["verdict"], "over")
        self.assertEqual(diff["items"][0]["diff"], 30 - 120)

    def test_under_planning_verdict(self):
        self._plan_with(30, 120)  # +300% → under
        self.assertEqual(psvc.compute_plan_vs_actual(Y)["verdict"], "under")

    def test_ok_verdict(self):
        self._plan_with(60, 50)  # -17% → ok
        self.assertEqual(psvc.compute_plan_vs_actual(Y)["verdict"], "ok")

    def test_actual_is_honest_sum(self):
        t = self._plan_with(120, 40)
        tsvc.add_session(t["id"], 25, log_date=Y, source="timer")
        self.assertEqual(psvc.compute_plan_vs_actual(Y)["actual_total"], 65)


class TestReviewLifecycle(unittest.TestCase):
    def setUp(self):
        reset_db()

    def _plan(self):
        t = _new_task("算法一")
        p = psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 120}])
        return p

    def test_submit_review_pending_not_effective(self):
        p = self._plan()
        n_before = len(crud.fetch_all("tasks"))
        plan = psvc.submit_review(Y, "计划过量", "实际只有计划四分之一",
                                  [{"action": "add", "title": "拆出的子任务", "category": "算法", "expected_minutes": 30}])
        self.assertEqual(plan["review_status"], "pending")
        self.assertEqual(plan["status"], "pending")
        self.assertEqual(len(plan["adjustments"]), 1)
        self.assertEqual(len(crud.fetch_all("tasks")), n_before)  # 待确认不建任务
        # 没有待确认调整的计划提交后进入 pending（空调整也合法）
        self.assertEqual(psvc.submit_review(Y, "计划合理", "OK", [])["review_status"], "pending")

    def test_submit_review_bad_action(self):
        self._plan()
        with self.assertRaises(psvc.BadRequest):
            psvc.submit_review(Y, "x", "r", [{"action": "hack"}])

    def test_submit_review_no_plan(self):
        with self.assertRaises(psvc.BadRequest):
            psvc.submit_review(Y, "x", "r", [])

    def test_confirm_adjust_and_remove(self):
        p = self._plan()
        item_id = p["items"][0]["id"]
        psvc.submit_review(Y, "计划过量", "太多", [
            {"action": "adjust", "item_id": item_id, "expected_minutes": 90},
            {"action": "remove", "item_id": item_id},
        ])
        plan = psvc.confirm_review(p["id"])
        self.assertEqual(plan["review_status"], "applied")
        self.assertEqual(plan["status"], "reviewed")
        self.assertEqual(plan["items"], [])  # 唯一项被移除
        rows = crud.fetch_all("agent_actions", where="run_id=?", params=(f"confirm:{p['id']}",))
        self.assertEqual(len(rows), 2)  # adjust + remove 各一条审计
        self.assertTrue(all(r["ok"] for r in rows))

    def test_confirm_add_creates_task(self):
        p = self._plan()
        psvc.submit_review(Y, "计划过量", "拆任务", [
            {"action": "add", "title": "LeetCode 第1题", "category": "算法", "expected_minutes": 30},
        ])
        n_before = len(crud.fetch_all("tasks"))
        plan = psvc.confirm_review(p["id"])
        self.assertEqual(len(crud.fetch_all("tasks")), n_before + 1)
        self.assertEqual(len(plan["items"]), 2)
        new_item = plan["items"][1]
        self.assertEqual(new_item["title"], "LeetCode 第1题")
        self.assertEqual(new_item["expected_minutes"], 30)
        self.assertEqual(new_item["task_id"] > 0, True)

    def test_confirm_next_plan_chains(self):
        p = self._plan()
        psvc.submit_review(Y, "计划过量", "明天砍半", [
            {"action": "next_plan", "plan_date": TMR, "items": [
                {"title": "复习 LeetCode", "category": "算法", "expected_minutes": 60},
            ]},
        ])
        psvc.confirm_review(p["id"])
        nxt = psvc.get_plan(TMR)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt["prev_plan_id"], p["id"])
        self.assertEqual(nxt["items"][0]["title"], "复习 LeetCode")
        self.assertEqual(nxt["items"][0]["expected_minutes"], 60)

    def test_confirm_wrong_state(self):
        p = self._plan()
        with self.assertRaises(psvc.BadRequest):
            psvc.confirm_review(p["id"])  # 还没 pending

    def test_reject_clears_adjustments(self):
        p = self._plan()
        psvc.submit_review(Y, "计划过量", "hmm", [
            {"action": "add", "title": "X", "category": "算法", "expected_minutes": 30},
        ])
        n_before = len(crud.fetch_all("tasks"))
        plan = psvc.reject_review(p["id"])
        self.assertEqual(plan["review_status"], "rejected")
        self.assertEqual(plan["adjustments"], [])
        self.assertEqual(len(crud.fetch_all("tasks")), n_before)


class TestFindUnreviewed(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_only_past_active_unreviewed(self):
        t = _new_task("算法一")
        # 今天的计划不被找
        psvc.create_plan(date.today().isoformat(), [{"task_id": t["id"], "expected_minutes": 60}])
        self.assertIsNone(psvc.find_unreviewed())
        # 昨天的计划 → 找到
        psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 60}])
        self.assertEqual(psvc.find_unreviewed()["plan_date"], Y)
        # 提交复盘（pending）后不再被找
        psvc.submit_review(Y, "计划过量", "r", [])
        self.assertIsNone(psvc.find_unreviewed())
        # 确认（applied）后仍不被找
        psvc.submit_review(Y, "计划过量", "r", [])
        p = psvc.get_plan(Y)
        psvc.confirm_review(p["id"])
        self.assertIsNone(psvc.find_unreviewed())


if __name__ == "__main__":
    unittest.main()
