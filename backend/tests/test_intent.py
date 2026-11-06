"""Phase 5 意图识别 + 对话管理的单元测试（零成本，不调 LLM、不花 token）。"""
import json
import unittest

import helpers  # noqa: F401
from app.agent import intent as I
from app.services import conversations as cvs


class TestIntentClassify(unittest.TestCase):
    def test_plan_with_relative_date(self):
        r = I.classify("安排明天的学习")
        self.assertEqual(r["intent"], I.INTENT_PLAN)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["slots"]["date"])
        self.assertEqual(r["label"], "安排计划")

    def test_plan_with_absolute_date_and_minutes(self):
        r = I.classify("帮我安排 2026-12-01 的学习，共 180 分钟")
        self.assertEqual(r["intent"], I.INTENT_PLAN, "「安排学习，共 N 分钟」不能被误判成记录学习")
        self.assertEqual(r["slots"]["date"], "2026-12-01")
        self.assertEqual(r["slots"]["minutes"], 180)

    def test_record_with_task_and_minutes(self):
        r = I.classify("记录今天在任务 12 上学习了 40 分钟")
        self.assertEqual(r["intent"], I.INTENT_RECORD)
        self.assertEqual(r["slots"]["task_id"], 12)
        self.assertEqual(r["slots"]["minutes"], 40)

    def test_record_hours_converted_to_minutes(self):
        r = I.classify("我学了 1.5 小时")
        self.assertEqual(r["intent"], I.INTENT_RECORD)
        self.assertEqual(r["slots"]["minutes"], 90)

    def test_record_missing_minutes_asks(self):
        r = I.classify("帮我记录在任务 5 上学习")
        self.assertEqual(r["intent"], I.INTENT_RECORD)
        self.assertEqual(r["missing"], ["minutes"])

    def test_remember_extracts_content(self):
        r = I.classify("记住：我晚上效率最高")
        self.assertEqual(r["intent"], I.INTENT_REMEMBER)
        self.assertIn("晚上", r["slots"]["content"])

    def test_remember_colloquial(self):
        r = I.classify("以后都按 20:00-23:00 安排学习")
        self.assertEqual(r["intent"], I.INTENT_REMEMBER)
        self.assertIn("20:00", r["slots"]["content"])

    def test_forget_strips_noun_prefix(self):
        r = I.classify("忘掉记忆：学习时段")
        self.assertEqual(r["intent"], I.INTENT_FORGET)
        self.assertEqual(r["slots"]["key"], "学习时段", "「记忆：」是名词不能算进 key")

    def test_review_and_query(self):
        self.assertEqual(I.classify("复盘昨天的计划")["intent"], I.INTENT_REVIEW)
        self.assertEqual(I.classify("分析我当前的学习状态")["intent"], I.INTENT_QUERY)

    def test_chat_fallback_and_empty(self):
        r = I.classify("今天天气怎么样")
        self.assertEqual(r["intent"], I.INTENT_CHAT)
        self.assertLessEqual(r["confidence"], 0.5)
        e = I.classify("")
        self.assertEqual(e["intent"], I.INTENT_CHAT)
        self.assertEqual(e["confidence"], 0.0)


class TestDateExtraction(unittest.TestCase):
    def test_long_word_wins(self):
        """「大后天」不能被「后天」先吃掉。"""
        import datetime
        today = datetime.date.today()
        self.assertEqual(I.extract_date("大后天"),
                         (today + datetime.timedelta(days=3)).isoformat())
        self.assertEqual(I.extract_date("后天"),
                         (today + datetime.timedelta(days=2)).isoformat())

    def test_invalid_date_returns_empty(self):
        self.assertEqual(I.extract_date("2026-13-45"), "")

    def test_weekday(self):
        out = I.extract_date("下周一")
        self.assertTrue(out)
        self.assertEqual(len(out), 10)


class TestDialogMerge(unittest.TestCase):
    def test_merge_fills_slot(self):
        r = I.merge_pending({"intent": I.INTENT_PLAN, "slots": {}}, "明天")
        self.assertEqual(r["intent"], I.INTENT_PLAN)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["resumed"])

    def test_merge_keeps_previous_slots(self):
        r = I.merge_pending({"intent": I.INTENT_RECORD, "slots": {"minutes": 40}}, "任务 12")
        self.assertEqual(r["slots"]["minutes"], 40)
        self.assertEqual(r["slots"]["task_id"], 12)

    def test_switch_intent_drops_pending(self):
        r = I.merge_pending({"intent": I.INTENT_PLAN, "slots": {}}, "算了，先复盘昨天的")
        self.assertEqual(r["intent"], I.INTENT_REVIEW)
        self.assertNotIn("date", r["slots"])

    def test_merge_without_pending_is_plain_classify(self):
        r = I.merge_pending({}, "安排明天的学习")
        self.assertEqual(r["intent"], I.INTENT_PLAN)
        self.assertNotIn("resumed", r)


class TestGoalAndQuestion(unittest.TestCase):
    def test_build_goal_looks_like_user_speech(self):
        g = I.build_goal(I.INTENT_PLAN, {"date": "2026-11-07", "minutes": 120})
        self.assertIn("2026-11-07", g)
        self.assertIn("120", g)
        self.assertIn("安排", g)

    def test_next_question_asks_one_at_a_time(self):
        q = I.next_question(I.INTENT_RECORD, ["minutes", "task_id"])
        self.assertIn("分钟", q)
        self.assertEqual(I.next_question(I.INTENT_PLAN, []), "")

    def test_describe(self):
        s = I.describe(I.INTENT_PLAN, {"date": "2026-11-07", "minutes": 120})
        self.assertTrue(s.startswith("安排计划"))
        self.assertIn("2026-11-07", s)


class TestConversations(unittest.TestCase):
    def setUp(self):
        helpers.reset_db()

    def test_create_and_turns(self):
        conv = cvs.create()
        self.assertTrue(conv["conv_id"].startswith("cv"))
        cvs.add_turn(conv["conv_id"], "user", "安排明天的学习", {"intent": "plan"})
        cvs.add_turn(conv["conv_id"], "assistant", "好的")
        full = cvs.get(conv["conv_id"])
        self.assertEqual(len(full["turns"]), 2)
        self.assertEqual(full["turns"][0]["role"], "user")
        self.assertEqual(full["turns"][0]["intent"]["intent"], "plan")

    def test_get_or_create_is_stable(self):
        a = cvs.get_or_create()
        b = cvs.get_or_create(a["conv_id"])
        self.assertEqual(a["conv_id"], b["conv_id"])

    def test_pending_roundtrip(self):
        conv = cvs.create()
        cvs.set_pending(conv["conv_id"], {"intent": "plan", "slots": {}})
        self.assertEqual(cvs.get(conv["conv_id"])["pending"]["intent"], "plan")
        cvs.set_pending(conv["conv_id"], None)
        self.assertEqual(cvs.get(conv["conv_id"])["pending"], {})

    def test_close_clears_pending(self):
        conv = cvs.create()
        cvs.set_pending(conv["conv_id"], {"intent": "plan"})
        closed = cvs.close(conv["conv_id"])
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["pending"], {})

    def test_bad_role_rejected(self):
        conv = cvs.create()
        with self.assertRaises(cvs.BadRequest):
            cvs.add_turn(conv["conv_id"], "system", "x")

    def test_list_has_turn_count(self):
        conv = cvs.create()
        cvs.add_turn(conv["conv_id"], "user", "hi")
        items = cvs.list_conversations()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["turn_count"], 1)

    def test_create_is_idempotent(self):
        """重复 conv_id 不抛 UNIQUE 冲突，返回原会话。

        前端「新会话」每次都生成新 id，但双击、重试、外部调用都可能撞同一个 id，
        抛 IntegrityError 会变成 500。
        """
        a = cvs.create()
        b = cvs.create(a["conv_id"])
        self.assertEqual(a["conv_id"], b["conv_id"])
        cvs.add_turn(a["conv_id"], "user", "hi")
        self.assertEqual(len(cvs.get(a["conv_id"])["turns"]), 1)

    def test_closed_conv_rejects_pending_and_turns(self):
        """已结束的会话不能再挂起、不能追加轮次（close 要真的有约束力）。"""
        conv = cvs.create()
        cvs.close(conv["conv_id"])
        with self.assertRaises(cvs.BadRequest):
            cvs.set_pending(conv["conv_id"], {"intent": "plan"})
        with self.assertRaises(cvs.BadRequest):
            cvs.add_turn(conv["conv_id"], "user", "还在吗")
        self.assertEqual(cvs.get(conv["conv_id"])["pending"], {})

    def test_get_or_create_skips_closed(self):
        """close 后再 get_or_create 应开新会话，而不是复用已关闭的。"""
        old = cvs.create()
        cvs.close(old["conv_id"])
        new = cvs.get_or_create(old["conv_id"])
        self.assertNotEqual(new["conv_id"], old["conv_id"])
        self.assertEqual(new["status"], "active")

    def test_turn_on_missing_conv_rejected(self):
        with self.assertRaises(cvs.BadRequest):
            cvs.add_turn("cv_nope", "user", "hi")
        with self.assertRaises(cvs.BadRequest):
            cvs.set_pending("cv_nope", {"intent": "plan"})


if __name__ == "__main__":
    unittest.main()
