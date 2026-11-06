"""学习路线升级测试：改路线不能让用户已有进度丢失。

覆盖三件事：
1. seed_if_empty 写入的是当前路线版本，并标记 route_version（否则每次启动都白跑一次升级）
2. upgrade_route 幂等：第一次 True，第二次 False
3. upgrade_route 保留已有进度：改名前任务的 progress / spent_minutes / id 全部不动
"""
import unittest

from helpers import reset_db
from app import db, seed


class TestRouteUpgrade(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_seed_marks_route_version(self):
        conn = db.connect()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key='route_version'").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "seed_if_empty 应写入 route_version")
        self.assertEqual(row["value"], seed.ROUTE_VERSION)

    def test_upgrade_is_idempotent(self):
        # 干净库已经是当前版本 → 不该再升级
        self.assertFalse(seed.upgrade_route())
        # 把版本标记清掉模拟老库
        conn = db.connect()
        conn.execute("DELETE FROM settings WHERE key='route_version'")
        conn.commit()
        conn.close()
        self.assertTrue(seed.upgrade_route())
        self.assertFalse(seed.upgrade_route())

    def test_upgrade_keeps_progress_and_ids(self):
        """老库里的任务改个名、减个目标小时，但 id / 进度 / 已花时间必须原样保留。"""
        conn = db.connect()
        try:
            # 造一个「老库」状态：把版本标记删掉，并把一个任务改成老标题 + 带进度
            conn.execute("DELETE FROM settings WHERE key='route_version'")
            old_title = "Git + Linux + HTTP/JSON/API"
            new_title = seed.RENAMES[old_title]
            conn.execute(
                "UPDATE tasks SET title=?, progress=40, spent_minutes=99, status='进行中' WHERE title=?",
                (old_title, new_title),
            )
            row = conn.execute("SELECT id FROM tasks WHERE title=?", (old_title,)).fetchone()
            old_id = row["id"]
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(seed.upgrade_route())

        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT id, title, progress, spent_minutes, status FROM tasks WHERE title=?",
                (new_title,),
            ).fetchone()
            # 老标题不该残留
            stale = conn.execute("SELECT 1 FROM tasks WHERE title=?", (old_title,)).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row, "改名的任务应该还在")
        self.assertEqual(row["id"], old_id, "改名不能换 id（计划项/会话都挂在 id 上）")
        self.assertEqual(row["progress"], 40)
        self.assertEqual(row["spent_minutes"], 99)
        self.assertEqual(row["status"], "进行中")
        self.assertIsNone(stale, "老标题不该残留成重复任务")

    def test_upgrade_has_no_duplicate_titles(self):
        """升级后同一标题只能出现一次，否则页面会显示两张一样的卡。"""
        conn = db.connect()
        conn.execute("DELETE FROM settings WHERE key='route_version'")
        conn.commit()
        conn.close()

        seed.upgrade_route()

        conn = db.connect()
        try:
            dups = conn.execute(
                "SELECT title, COUNT(*) c FROM tasks GROUP BY title HAVING c > 1"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([(d["title"], d["c"]) for d in dups], [])

    def test_route_covers_jd_keywords(self):
        """路线必须覆盖岗位 JD 的核心能力词，防止后续改动把关键项删掉。"""
        titles = " ".join(t[2] for t in seed.TASKS)
        for keyword in ["Tool Calling", "ReAct", "记忆", "任务规划", "意图识别",
                        "工作流", "MCP", "多智能体", "评测", "Context Engineering", "RAG"]:
            self.assertIn(keyword, titles, f"路线缺少 JD 要求的能力：{keyword}")


if __name__ == "__main__":
    unittest.main()
