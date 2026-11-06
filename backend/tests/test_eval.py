"""Phase 5 评测执行器 + 成本看板的单元测试（只跑零成本用例，不调 LLM）。"""
import unittest

import helpers  # noqa: F401
from app import db
from app.agent import cost, eval_cases, eval_runner
from app.services import usage


class TestCostModule(unittest.TestCase):
    def test_known_model_price(self):
        pin, pout, known = cost.price_for("deepseek-chat")
        self.assertTrue(known)
        self.assertEqual((pin, pout), (2.0, 8.0))

    def test_longer_prefix_wins(self):
        """deepseek-reasoner 必须先于 deepseek 命中，否则价格算错。"""
        pin, pout, known = cost.price_for("deepseek-reasoner")
        self.assertTrue(known)
        self.assertEqual((pin, pout), (4.0, 16.0))

    def test_unknown_model_falls_back_and_flags(self):
        pin, pout, known = cost.price_for("some-local-llm")
        self.assertFalse(known)
        self.assertEqual((pin, pout), cost.DEFAULT_PRICE)

    def test_estimate_cost(self):
        # 1M 输入 + 1M 输出 deepseek = 2 + 8
        self.assertEqual(cost.estimate_cost("deepseek-chat", 1_000_000, 1_000_000), 10.0)
        self.assertEqual(cost.estimate_cost("deepseek-chat", 0, 0), 0.0)

    def test_usage_summary_shape(self):
        u = cost.usage_summary("deepseek-chat", 1000, 500, latency_ms=1234)
        self.assertEqual(u["total_tokens"], 1500)
        self.assertEqual(u["input_tokens"], 1000)
        self.assertEqual(u["output_tokens"], 500)
        self.assertEqual(u["latency_ms"], 1234)
        self.assertTrue(u["price_known"])
        self.assertGreater(u["cost_cny"], 0)

    def test_negative_tokens_clamped(self):
        u = cost.usage_summary("deepseek-chat", -100, -50)
        self.assertEqual(u["input_tokens"], 0)
        self.assertEqual(u["output_tokens"], 0)


class TestEvalCases(unittest.TestCase):
    def test_relative_dates_resolved(self):
        exp = eval_cases.resolve_expected({"slots": {"date": "$tomorrow"}})
        self.assertNotEqual(exp["slots"]["date"], "$tomorrow")
        self.assertEqual(len(exp["slots"]["date"]), 10)

    def test_case_rows_shape(self):
        rows = eval_cases.case_rows()
        self.assertGreaterEqual(len(rows), 10)
        for r in rows:
            self.assertIn(r["kind"], ("intent", "dialog", "run"))
            self.assertTrue(r["name"])


class TestEvalRunner(unittest.TestCase):
    def setUp(self):
        helpers.reset_db()

    def test_seed_cases_is_idempotent(self):
        n1 = eval_runner.seed_cases()
        n2 = eval_runner.seed_cases()
        self.assertEqual(n1, n2)

    def test_cheap_eval_passes_and_costs_nothing(self):
        report = eval_runner.run_eval()
        self.assertEqual(report["status"], "succeeded")
        self.assertGreater(report["total"], 0)
        self.assertEqual(report["passed"], report["total"],
                         "零成本用例应该全过；失败详情见 results[].detail.reasons")
        self.assertEqual(report["total_tokens"], 0, "intent/dialog 用例不该花 token")
        self.assertEqual(report["cost_cny"], 0.0)

    def test_run_kind_not_included_by_default(self):
        eval_runner.run_eval()
        kinds = {r["kind"] for r in eval_runner.list_cases() if r["enabled"]}
        self.assertIn("run", kinds, "用例集里应该有 run 类")
        report = eval_runner.run_eval()
        self.assertNotIn("run", {r["kind"] for r in report["results"]},
                         "默认不该跑会花钱的 run 类")

    def test_limit_caps_cases(self):
        report = eval_runner.run_eval(limit=2)
        self.assertEqual(report["total"], 2)

    def test_get_eval_and_list(self):
        report = eval_runner.run_eval()
        again = eval_runner.get_eval(report["eval_id"])
        self.assertEqual(again["eval_id"], report["eval_id"])
        self.assertEqual(len(again["results"]), report["total"])
        self.assertTrue(any(e["eval_id"] == report["eval_id"]
                            for e in eval_runner.list_evals()))
        self.assertIsNone(eval_runner.get_eval("nope"))

    def test_unknown_kind_falls_back_to_cheap(self):
        report = eval_runner.run_eval(kinds=("bogus",))
        self.assertGreater(report["total"], 0)
        self.assertNotIn("bogus", {r["kind"] for r in report["results"]})


class TestUsageDashboard(unittest.TestCase):
    def setUp(self):
        helpers.reset_db()

    def test_empty_dashboard(self):
        s = usage.summary(30)
        self.assertEqual(s["totals"]["runs"], 0)
        self.assertEqual(s["by_day"], [])
        self.assertEqual(s["by_model"], [])
        self.assertTrue(s["price_note"])

    def test_aggregates_tokens_and_cost(self):
        conn = db.connect()
        conn.execute(
            "INSERT INTO agent_runs(run_id,goal,available_time,status,model,intent,started_at,"
            "created_at,token_usage_json) VALUES(?,?,?,?,?,?,?,?,?)",
            ("r1", "安排计划", 0, "succeeded", "deepseek-chat", "plan",
             "2026-11-06T10:00:00", "2026-11-06T10:00:00",
             '{"model":"deepseek-chat","input_tokens":1000,"output_tokens":500,'
             '"total_tokens":1500,"cost_cny":0.006,"latency_ms":2000,"llm_calls":3,'
             '"price_known":true}'),
        )
        conn.execute(
            "INSERT INTO agent_runs(run_id,goal,available_time,status,model,intent,started_at,"
            "created_at,token_usage_json) VALUES(?,?,?,?,?,?,?,?,?)",
            ("r2", "复盘", 0, "succeeded", "deepseek-chat", "review",
             "2026-11-06T11:00:00", "2026-11-06T11:00:00",
             '{"model":"deepseek-chat","input_tokens":2000,"output_tokens":1000,'
             '"total_tokens":3000,"cost_cny":0.012,"latency_ms":3000,"llm_calls":4,'
             '"price_known":true}'),
        )
        conn.commit()
        conn.close()

        s = usage.summary(365)
        self.assertEqual(s["totals"]["runs"], 2)
        self.assertEqual(s["totals"]["total_tokens"], 4500)
        self.assertEqual(s["totals"]["input_tokens"], 3000)
        self.assertEqual(s["totals"]["output_tokens"], 1500)
        self.assertAlmostEqual(s["totals"]["cost_cny"], 0.018, places=6)
        self.assertEqual(s["totals"]["llm_calls"], 7)
        self.assertEqual(len(s["by_model"]), 1)
        self.assertEqual(s["by_model"][0]["model"], "deepseek-chat")
        self.assertEqual({b["intent"] for b in s["by_intent"]}, {"plan", "review"})
        self.assertEqual(s["legacy_runs"], 0)

    def test_legacy_run_without_detail_is_flagged(self):
        """老 run 只有 total_tokens，不能瞎拆成输入/输出，要标 legacy。"""
        conn = db.connect()
        conn.execute(
            "INSERT INTO agent_runs(run_id,goal,available_time,status,model,started_at,"
            "created_at,token_usage_json) VALUES(?,?,?,?,?,?,?,?)",
            ("old", "老 run", 0, "succeeded", "", "2026-11-06T09:00:00",
             "2026-11-06T09:00:00", '{"total_tokens":5278}'),
        )
        conn.commit()
        conn.close()
        s = usage.summary(365)
        self.assertEqual(s["totals"]["total_tokens"], 5278)
        self.assertEqual(s["legacy_runs"], 1)
        self.assertEqual(s["recent"][0]["input_tokens"], 0,
                         "没有分项数据时不能编一个输入 token 数")
        self.assertFalse(s["recent"][0]["detail_available"])

    def test_price_table(self):
        t = usage.price_table()
        self.assertEqual(t["unit"], "元 / 百万 token")
        self.assertGreaterEqual(len(t["items"]), 5)
        self.assertIn("default", t)
        self.assertTrue(t["note"])


if __name__ == "__main__":
    unittest.main()
