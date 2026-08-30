"""Phase 4 记忆工具单测：get_memories / remember（待确认+审计）/ forget_memory（软删+审计）。"""
import unittest

from helpers import reset_db

from app.agent.tools import build_registry
from app.services import memories as msvc


class FakeContext:
    """确定性审计捕获器：不写库，只记录工具提交的 before/after。"""

    def __init__(self):
        self.run_id = "test-run"
        self.actions = []

    def audit(self, tool, args, before, after, ok=True, error=""):
        self.actions.append({"tool": tool, "args": args, "before": before,
                             "after": after, "ok": ok, "error": error})


class TestMemoryTools(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.reg = build_registry()
        self.ctx = FakeContext()

    def _ok(self, tool, args=None, ctx=None):
        res = self.reg.execute(tool, args or {}, ctx)
        self.assertTrue(res["ok"], res.get("error"))
        return res["data"]

    # ---------- 读 ----------
    def test_get_memories_empty(self):
        data = self._ok("get_memories")
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["memories"], [])

    def test_get_memories_lists_pending_active(self):
        self._ok("remember", {"key": "学习时段", "content": "工作日 20:00-23:00 效率高"}, self.ctx)
        m = msvc.get_memories()[0]
        msvc.confirm_memory(m["id"])
        data = self._ok("get_memories")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["memories"][0]["status"], "active")

    def test_get_memories_type_filter(self):
        self._ok("remember", {"key": "时段", "content": "晚上效率高", "type": "preference"}, self.ctx)
        self._ok("remember", {"key": "目标", "content": "12月前拿到实习", "type": "goal"}, self.ctx)
        data = self._ok("get_memories", {"type": "goal"})
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["memories"][0]["mtype"], "goal")

    # ---------- 写：remember ----------
    def test_remember_pending_and_audited(self):
        data = self._ok("remember", {
            "key": "学习时段", "content": "工作日 20:00-23:00 学习效率最高",
            "type": "preference", "importance": 4, "keywords": "时间,效率",
        }, self.ctx)
        self.assertEqual(data["status"], "pending")  # 待确认，不生效
        self.assertEqual(data["mtype"], "preference")
        self.assertEqual(data["importance"], 4)
        self.assertIn("待确认", data["message"])
        # 审计：before={}，after=紧凑记忆
        self.assertEqual(len(self.ctx.actions), 1)
        act = self.ctx.actions[0]
        self.assertEqual(act["tool"], "remember")
        self.assertEqual(act["before"], {})
        self.assertEqual(act["after"]["status"], "pending")
        self.assertEqual(act["after"]["mkey"], "学习时段")
        # 注入仍拿不到（待确认）
        self.assertEqual(msvc.active_memories(), [])

    def test_remember_missing_fields_fail_with_audit(self):
        for bad in ({"key": "k"}, {"content": "c"}):
            res = self.reg.execute("remember", bad, self.ctx)
            self.assertFalse(res["ok"])
            self.assertIn("必填参数", res["error"])
        # 坏 type
        res = self.reg.execute("remember", {"key": "k", "content": "c", "type": "hack"}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("type", res["error"])
        # 失败也审计 ok=0
        self.assertEqual(len(self.ctx.actions), 3)
        self.assertTrue(all(a["ok"] == 0 for a in self.ctx.actions))

    def test_remember_same_key_overrides(self):
        self._ok("remember", {"key": "时段", "content": "晚上 8 点后效率高"}, self.ctx)
        m = msvc.get_memories()[0]
        msvc.confirm_memory(m["id"])
        data = self._ok("remember", {"key": "时段", "content": "改主意：下午效率高"}, self.ctx)
        self.assertEqual(data["memory_id"], m["id"])  # 同一条，覆盖
        self.assertEqual(data["status"], "pending")  # 回到待确认
        self.assertEqual(data["content"], "改主意：下午效率高")

    # ---------- 写：forget_memory ----------
    def test_forget_memory_soft_delete_audited(self):
        self._ok("remember", {"key": "时段", "content": "晚上效率高"}, self.ctx)
        data = self._ok("forget_memory", {"key": "时段"}, self.ctx)
        self.assertTrue(data["forgotten"])
        self.assertEqual(msvc.get_memories(), [])  # 列表过滤
        # 审计：before=原记忆，after={}
        act = self.ctx.actions[-1]
        self.assertEqual(act["tool"], "forget_memory")
        self.assertEqual(act["before"]["status"], "pending")
        self.assertEqual(act["after"], {})

    def test_forget_memory_missing_key(self):
        res = self.reg.execute("forget_memory", {}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertIn("key", res["error"])

    def test_forget_unknown_key_is_graceful(self):
        data = self._ok("forget_memory", {"key": "不存在"}, self.ctx)
        self.assertFalse(data["forgotten"])
        self.assertEqual(data["message"], "已忘记（软删留痕）")


if __name__ == "__main__":
    unittest.main()
