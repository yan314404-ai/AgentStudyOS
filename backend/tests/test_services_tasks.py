"""services/tasks.py 单测：进度不变量 + 记时事务 + 直接写任务（Agent 与手动页共享的行为）。"""
import unittest
from datetime import date

from helpers import reset_db

from app import crud
from app.db import connect
from app.services import tasks as svc


def _task_by_title(title: str):
    rows = crud.fetch_all("tasks", where="title=?", params=(title,))
    return rows[0] if rows else None


class TestServicesTasks(unittest.TestCase):
    def setUp(self):
        reset_db()

    # ---------- 进度不变量 ----------
    def test_recalc_manual_lock_wins(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        crud.update("tasks", t["id"], {"manual_progress": 50, "spent_minutes": 500})
        conn = connect()
        prog = svc.recalc_progress(conn, t["id"])
        conn.commit()
        conn.close()
        self.assertEqual(prog, 50)

    def test_recalc_auto_from_minutes(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")  # hours=30 → 1800 分钟 100%
        crud.update("tasks", t["id"], {"manual_progress": -1, "spent_minutes": 900})
        conn = connect()
        prog = svc.recalc_progress(conn, t["id"])
        conn.commit()
        conn.close()
        self.assertEqual(prog, 50)
        crud.update("tasks", t["id"], {"spent_minutes": 1800})
        conn = connect()
        prog = svc.recalc_progress(conn, t["id"])
        conn.commit()
        conn.close()
        self.assertEqual(prog, 100)

    # ---------- 打卡分类同步 ----------
    def test_add_to_daily_log_new_and_existing(self):
        today = date.today().isoformat()
        conn = connect()
        svc.add_to_daily_log(conn, today, "course_minutes", 30)
        conn.commit()
        conn.close()
        log = crud.fetch_all("daily_logs", where="log_date=?", params=(today,))[0]
        self.assertEqual(log["course_minutes"], 30)
        self.assertEqual(log["total_minutes"], 30)
        conn = connect()
        svc.add_to_daily_log(conn, today, "course_minutes", 30)
        conn.commit()
        conn.close()
        log = crud.fetch_all("daily_logs", where="log_date=?", params=(today,))[0]
        self.assertEqual(log["course_minutes"], 60)
        self.assertEqual(log["total_minutes"], 60)

    # ---------- 记时事务 ----------
    def test_add_session_syncs_everything(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        field = svc.CATEGORY_FIELD_MAP.get(t["category"], svc.DEFAULT_FIELD)
        res = svc.add_session(t["id"], 60, note="学了 Git 分支", source="agent")
        self.assertEqual(res["session_id"] > 0, True)
        self.assertEqual(res["task"]["spent_minutes"], (t["spent_minutes"] or 0) + 60)
        self.assertEqual(res["today_total"], 60)
        # session 落库 + 当天打卡分类同步
        sess = crud.fetch_all("task_sessions", where="task_id=?", params=(t["id"],))[0]
        self.assertEqual(sess["minutes"], 60)
        self.assertEqual(sess["source"], "agent")
        log = crud.fetch_all("daily_logs", where="log_date=?", params=(date.today().isoformat(),))[0]
        self.assertEqual(log[field], 60)
        self.assertEqual(log["total_minutes"], 60)

    def test_add_session_respects_manual_lock(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        svc.update_task(t["id"], {"manual_progress": 42})  # 手动锁定（update_task 会重算 → progress=42）
        res = svc.add_session(t["id"], 60)
        self.assertEqual(res["task"]["progress"], 42)  # 手动锁定不被自动重算覆盖
        self.assertEqual(res["task"]["spent_minutes"], (t["spent_minutes"] or 0) + 60)

    def test_add_session_validation(self):
        with self.assertRaises(svc.BadRequest):
            svc.add_session(1, 0)  # minutes 越界
        with self.assertRaises(svc.TaskNotFound):
            svc.add_session(999999, 30)

    # ---------- update_task：手动锁定 / 恢复自动 ----------
    def test_update_task_lock_and_restore(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        row = svc.update_task(t["id"], {"manual_progress": 50})
        self.assertEqual(row["progress"], 50)
        svc.add_session(t["id"], 900)
        svc.add_session(t["id"], 900)
        row = svc.update_task(t["id"], {"manual_progress": -1})
        self.assertEqual(row["progress"], 100)  # 恢复自动 → 1800 分钟 / 30h = 100%
        self.assertEqual(row["manual_progress"], -1)

    # ---------- complete_task / create_task / create_review_task ----------
    def test_complete_task(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        row = svc.complete_task(t["id"])
        self.assertEqual(row["status"], "已完成")
        self.assertEqual(row["progress"], 100)
        self.assertEqual(row["manual_progress"], 100)

    def test_create_task_direct_defaults(self):
        row = svc.create_task({"title": "新任务", "hours": 5})
        self.assertEqual(row["status"], "待开始")
        self.assertEqual(row["progress"], 0)
        self.assertEqual(row["phase"], "未分组")
        with self.assertRaises(svc.BadRequest):
            svc.create_task({})

    def test_create_review_task(self):
        t = _task_by_title("Git + Linux + HTTP/JSON/API")
        row = svc.create_review_task(t["id"], reason="还没记牢")
        self.assertEqual(row["title"], "复习：" + t["title"])
        self.assertEqual(row["phase"], t["phase"])
        self.assertIn("🤖 Agent 复习任务", row["note"])


if __name__ == "__main__":
    unittest.main()
