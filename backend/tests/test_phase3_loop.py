"""Phase 3 闭环集成测试：FakeProvider 脚本化跑通「安排计划 → 执行 → 复盘 → 确认」。

- run1「安排明天的学习」→ create_plan 落库（明天计划）
- run2「复盘」→ 确定性注入 prior_plan_vs_actual 出现在 planner 输入 → submit_review 带调整 → pending
- 用户确认 → confirm_review 应用调整（新建任务 + 改时长）+ confirm:* 审计

全程无真实 LLM，用 LoopProvider 保证确定性。
"""
import json
import unittest
from datetime import date, timedelta

from helpers import reset_db

from app import crud
from app.agent.repo import RunRepo
from app.agent.runtime import AgentRuntime
from app.agent.trace import TraceStore
from app.services import plans as psvc
from app.services import tasks as tsvc

Y = (date.today() - timedelta(days=1)).isoformat()   # 昨日（计划执行日）
TMR = (date.today() + timedelta(days=1)).isoformat()  # 明天


def _new_task(title: str, category: str = "算法"):
    return crud.create("tasks", {
        "title": title, "phase": "未分组", "category": category,
        "status": "待开始", "progress": 0, "created_at": "2026-08-24T00:00:00",
    })


class LoopProvider:
    """确定性假 LLM：planner 返回脚本步骤；reflector 直接说完成；synthesizer 给一句话。"""

    def __init__(self, plan_steps: list):
        self.plan_steps = plan_steps
        self.total_tokens = 0
        self.model = "fake-model"
        self.saw_injection = False  # planner 输入里是否含「昨日计划 vs 实际」注入
        self.last_planner_user = ""

    def chat(self, system, user, temperature=0.7):
        return "【测试】学习计划与复盘结果见 Agent 页。"

    def structured_json(self, system, user, temperature=0.2):
        self.total_tokens += 10
        if "可用工具" in user:  # planner 的 user 含工具清单
            self.last_planner_user = user
            if "prior_plan_vs_actual" in user:
                self.saw_injection = True
            return {"goal": "test", "reasoning_summary": "s", "steps": self.plan_steps}
        return {"goal_completed": True, "need_replan": False,
                "reason": "计划执行完毕", "next_action": "结束"}


class TestPhase3Loop(unittest.TestCase):
    def setUp(self):
        reset_db()

    # ---------- run1：安排明天的学习 → create_plan 落库 ----------
    def test_arrange_tomorrow_creates_plan(self):
        t = _new_task("算法-链表")
        provider = LoopProvider([
            {"tool": "create_plan", "arguments": {
                "plan_date": TMR,
                "items": [{"task_id": t["id"], "expected_minutes": 120}],
                "goal": "复习链表",
                "reasoning_summary": "弱项在链表",
            }},
        ])
        run_id = AgentRuntime(llm=provider).run("帮我安排明天的学习", available_time=3)

        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        plan = psvc.get_plan(TMR)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["expected_total"], 120)
        self.assertEqual(plan["actual_total"], 0)
        self.assertEqual(plan["items"][0]["task_id"], t["id"])
        self.assertEqual(plan["items"][0]["title"], "算法-链表")
        self.assertEqual(plan["review_status"], "none")
        # 明天的计划还没到复盘时点 → 不注入
        self.assertFalse(provider.saw_injection)

    # ---------- run2：复盘 → 注入昨日计划vs实际 → submit_review 待确认 ----------
    def test_review_run_sees_injection_and_submits_pending(self):
        t = _new_task("算法-链表")
        psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 120}], goal="昨日计划")
        tsvc.add_session(t["id"], 90, log_date=Y, source="agent")  # 计划120 / 实际90 → -25% 计划过量
        item_id = psvc.get_plan(Y)["items"][0]["id"]

        provider = LoopProvider([
            {"tool": "submit_review", "arguments": {
                "plan_date": Y, "verdict": "计划过量", "reasoning": "实际只有 90 分钟，计划偏多",
                "adjustments": [{"action": "remove", "item_id": item_id}],
            }},
        ])
        run_id = AgentRuntime(llm=provider).run(f"复盘 {Y} 的学习计划执行情况")

        # 确定性注入真实出现在 planner 输入里，且偏差诚实
        self.assertTrue(provider.saw_injection)
        self.assertIn("prior_plan_vs_actual", provider.last_planner_user)
        self.assertIn('"actual_total": 90', provider.last_planner_user)
        self.assertIn('"verdict": "over"', provider.last_planner_user)

        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        # 复盘 run 写了 plan_compare trace 事件（前端时间线可见）
        types = [e["event_type"] for e in TraceStore.summary(run_id)]
        self.assertIn("plan_compare", types)

        # 调整待确认，不生效
        plan = psvc.get_plan(Y)
        self.assertEqual(plan["review_status"], "pending")
        self.assertEqual(plan["status"], "pending")
        self.assertEqual(len(plan["adjustments"]), 1)
        self.assertEqual(plan["adjustments"][0]["action"], "remove")
        self.assertEqual(len(plan["items"]), 1)  # 移除未应用，计划项还在

    # ---------- 用户确认：confirm_review 应用调整 + 审计 ----------
    def test_confirm_applies_adjustments_and_audits(self):
        t = _new_task("算法-链表")
        p = psvc.create_plan(Y, [{"task_id": t["id"], "expected_minutes": 120}])
        psvc.submit_review(Y, "计划过量", "拆任务", [
            {"action": "adjust", "item_id": p["items"][0]["id"], "expected_minutes": 90},
            {"action": "add", "title": "LeetCode 链表题", "category": "算法", "expected_minutes": 30},
        ])
        n_tasks = len(crud.fetch_all("tasks"))

        plan = psvc.confirm_review(p["id"])

        self.assertEqual(plan["review_status"], "applied")
        self.assertEqual(plan["status"], "reviewed")
        self.assertEqual(len(plan["items"]), 2)
        self.assertEqual(plan["items"][0]["expected_minutes"], 90)  # adjust 生效
        self.assertEqual(plan["items"][1]["title"], "LeetCode 链表题")  # add 生效
        self.assertEqual(len(crud.fetch_all("tasks")), n_tasks + 1)  # 确认后才建任务
        # confirm 阶段每步写 agent_actions 审计
        rows = crud.fetch_all("agent_actions", where="run_id=?", params=(f"confirm:{p['id']}",))
        tools = [r["tool"] for r in rows]
        self.assertIn("confirm:adjust", tools)
        self.assertIn("confirm:add", tools)
        self.assertTrue(all(r["ok"] for r in rows))
        # 复盘完成后 find_unreviewed 不再命中
        self.assertIsNone(psvc.find_unreviewed())


if __name__ == "__main__":
    unittest.main()
