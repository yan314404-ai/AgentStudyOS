"""Phase 4 记忆领域服务单测：迁移 v8 + 记住待确认/覆盖 + 注入只取 active + 确认/拒绝/忘记。"""
import unittest
from datetime import date, timedelta

from helpers import reset_db

from app import crud
from app.db import connect
from app.services import memories as msvc
from app.services import plans as psvc
from app.services import tasks as tsvc

Y = (date.today() - timedelta(days=1)).isoformat()


def _new_task(title: str, category: str = "算法"):
    return crud.create("tasks", {
        "title": title, "phase": "未分组", "category": category,
        "status": "待开始", "progress": 0, "created_at": "2026-08-24T00:00:00",
    })


class TestMigrationV8(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_agent_memories_table_and_suggested_time(self):
        conn = connect()
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("agent_memories", names)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(agent_plan_items)")]
        self.assertIn("suggested_time", cols)
        conn.close()


class TestRemember(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_remember_new_is_pending(self):
        m = msvc.remember("学习时段", "工作日 20:00-23:00 学习效率最高", "preference", 4, "时间,效率")
        self.assertEqual(m["status"], "pending")
        self.assertEqual(m["mtype"], "preference")
        self.assertEqual(m["importance"], 4)
        self.assertEqual(m["keywords"], "时间,效率")
        self.assertGreater(m["id"], 0)

    def test_remember_validation(self):
        with self.assertRaises(msvc.BadRequest):
            msvc.remember("", "内容")
        with self.assertRaises(msvc.BadRequest):
            msvc.remember("key", "")
        with self.assertRaises(msvc.BadRequest):
            msvc.remember("key", "内容", mtype="hack")
        with self.assertRaises(msvc.BadRequest):
            msvc.remember("key", "内容", importance="abc")

    def test_remember_importance_clamped(self):
        m = msvc.remember("k", "内容", importance=99)
        self.assertEqual(m["importance"], 5)

    def test_same_key_overrides_resets_to_pending(self):
        m1 = msvc.remember("学习时段", "工作日 20:00-23:00 高效", "preference", 3)
        msvc.confirm_memory(m1["id"])
        m2 = msvc.remember("学习时段", "改主意：晚上 22:00 前效率高", "preference", 5)
        # 同 mkey：同一条记录，覆盖 + 回到 pending（需重新确认）
        self.assertEqual(m2["id"], m1["id"])
        self.assertEqual(m2["status"], "pending")
        self.assertEqual(m2["content"], "改主意：晚上 22:00 前效率高")


class TestReadAndInject(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_get_memories_filters_pending_active(self):
        msvc.remember("a", "A", importance=2)   # pending imp2
        m2 = msvc.remember("b", "B", importance=5)
        msvc.confirm_memory(m2["id"])           # active imp5
        msvc.remember("c", "C", importance=3)   # pending imp3
        got = msvc.get_memories()
        # pending 在前（importance 降序 c3>a2），再 active；rejected/forgotten 被过滤
        self.assertEqual([m["mkey"] for m in got], ["c", "a", "b"])
        self.assertEqual([m["status"] for m in got], ["pending", "pending", "active"])

    def test_pending_first_then_active(self):
        a = msvc.remember("active1", "A", importance=1)
        msvc.confirm_memory(a["id"])
        msvc.remember("pending1", "P", importance=1)  # 仍 pending
        got = msvc.get_memories()
        # pending 在前，active 在后
        self.assertEqual([m["mkey"] for m in got], ["pending1", "active1"])

    def test_active_memories_only_active_importance_sorted(self):
        msvc.remember("p", "pending", importance=5)
        a1 = msvc.remember("a1", "active low", importance=1)
        msvc.confirm_memory(a1["id"])
        a2 = msvc.remember("a2", "active high", importance=5)
        msvc.confirm_memory(a2["id"])
        act = msvc.active_memories()
        self.assertEqual([m["mkey"] for m in act], ["a2", "a1"])  # importance 降序
        self.assertEqual([m["status"] for m in act], ["active", "active"])

    def test_active_memories_limit(self):
        for i in range(3):
            m = msvc.remember(f"k{i}", f"记忆 {i}", importance=3)
            msvc.confirm_memory(m["id"])
        self.assertEqual(len(msvc.active_memories(limit=2)), 2)

    def test_pending_never_injected(self):
        msvc.remember("p", "未确认", importance=5)
        self.assertEqual(msvc.active_memories(), [])


class TestStatusFlow(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_confirm_active(self):
        m = msvc.remember("k", "内容")
        m2 = msvc.confirm_memory(m["id"])
        self.assertEqual(m2["status"], "active")

    def test_reject_rejected(self):
        m = msvc.remember("k", "内容")
        m2 = msvc.reject_memory(m["id"])
        self.assertEqual(m2["status"], "rejected")

    def test_forget_hides(self):
        m = msvc.remember("k", "内容")
        msvc.forget_memory(m["id"])
        self.assertEqual(msvc.get_memories(), [])
        self.assertEqual(msvc.active_memories(), [])
        # 数据留痕（软删）
        conn = connect()
        row = conn.execute("SELECT status FROM agent_memories WHERE id=?", (m["id"],)).fetchone()
        conn.close()
        self.assertEqual(row["status"], "forgotten")

    def test_non_pending_reject_raises(self):
        m = msvc.remember("k", "内容")
        msvc.confirm_memory(m["id"])  # 已确认
        with self.assertRaises(msvc.BadRequest):
            msvc.reject_memory(m["id"])
        # 同 key 覆盖 → 回到 pending → 这次可以 reject
        m2 = msvc.remember("k", "改主意")
        self.assertEqual(m2["id"], m["id"])
        msvc.reject_memory(m["id"])  # 不抛错

    def test_forget_any_state_ok(self):
        m = msvc.remember("k", "内容")
        msvc.confirm_memory(m["id"])
        msvc.forget_memory(m["id"])  # 已确认的记忆也能直接删，不抛错

    def test_missing_memory_raises(self):
        with self.assertRaises(msvc.BadRequest):
            msvc.confirm_memory(999999)


class TestSuggestedTime(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_create_plan_with_suggested_time(self):
        t = _new_task("算法一")
        plan = psvc.create_plan(Y, [{
            "task_id": t["id"], "expected_minutes": 120, "suggested_time": "20:00-23:00",
        }], goal="G")
        self.assertEqual(plan["items"][0]["suggested_time"], "20:00-23:00")

    def test_create_plan_without_suggested_time_defaults_empty(self):
        t = _new_task("算法一")
        plan = psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 60}])
        self.assertEqual(plan["items"][0]["suggested_time"], "")

    def test_suggested_time_truncated(self):
        t = _new_task("算法一")
        plan = psvc.create_plan(Y, [{
            "task_id": t["id"], "expected_minutes": 30, "suggested_time": "x" * 100,
        }])
        self.assertEqual(len(plan["items"][0]["suggested_time"]), 50)

    def test_suggested_time_roundtrip_via_session(self):
        """计划落库后 get_plan 仍带回 suggested_time（迁移 v8 列存在）。"""
        t = _new_task("算法一")
        psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 30, "suggested_time": "08:00-09:00"}])
        got = psvc.get_plan(Y)
        self.assertEqual(got["items"][0]["suggested_time"], "08:00-09:00")


if __name__ == "__main__":
    unittest.main()
