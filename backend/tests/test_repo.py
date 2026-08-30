"""RunRepo 单测：建行 / 更新白名单 / 单运行锁 / 崩溃残留恢复。"""
import unittest

from helpers import reset_db

from app.agent.repo import RunRepo, gen_run_id


class TestRunRepo(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_create_and_get(self):
        rid = gen_run_id()
        RunRepo.create(rid, "目标", 3)
        row = RunRepo.get(rid)
        self.assertIsNotNone(row)
        self.assertEqual(row["goal"], "目标")
        self.assertEqual(row["available_time"], 3)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["iteration"], 0)

    def test_has_running(self):
        self.assertFalse(RunRepo.has_running())
        RunRepo.create(gen_run_id(), "g", 0)
        self.assertTrue(RunRepo.has_running())

    def test_update_whitelist_ignores_unknown(self):
        rid = gen_run_id()
        RunRepo.create(rid, "g", 0)
        RunRepo.update(rid, status="succeeded", final_reply="ok", hack=123)
        row = RunRepo.get(rid)
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(row["final_reply"], "ok")

    def test_recover_stale_runs(self):
        rid = gen_run_id()
        RunRepo.create(rid, "g", 0)
        n = RunRepo.recover_stale_runs()
        self.assertGreaterEqual(n, 1)
        row = RunRepo.get(rid)
        self.assertEqual(row["status"], "failed")
        self.assertIn("进程中断", row["error"])
        self.assertFalse(RunRepo.has_running())

    def test_list_orders_desc(self):
        for i in range(3):
            RunRepo.create(gen_run_id(), f"目标{i}", 0)
        runs = RunRepo.list(limit=2)
        self.assertEqual(len(runs), 2)
        # 后建的应排前面（ORDER BY id DESC）
        self.assertEqual(runs[0]["goal"], "目标2")


if __name__ == "__main__":
    unittest.main()
