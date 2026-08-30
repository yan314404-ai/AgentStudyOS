"""AgentRuntime 全流程单测：FakeProvider 保证确定性，验证闭环真实跑通。

Observe → Plan → Execute → Reflect → Synthesize 全覆盖：
  - agent_runs 落库（状态 / 计划 / 最终回复 / token 用量）
  - trace 事件序列齐全
  - create_task 直接生效（生成「待开始」任务）
  - need_replan 触发第二轮（不无限循环）
  - Planner 引用未知工具 → run 标记 failed 且带中文错误
"""
import json
import unittest

from helpers import reset_db

from app import crud
from app.agent.repo import RunRepo
from app.agent.runtime import AgentRuntime
from app.agent.trace import TraceStore

PLAN_STEPS = [
    {"tool": "get_learning_overview", "arguments": {}},
    {"tool": "create_task", "arguments": {"title": "Agent 测试任务", "hours": 2}},
]


class FakeProvider:
    """确定性 LLM 假件：planner / reflector / synthesizer 都返回脚本答案。"""

    def __init__(self, replan_once: bool = False, bad_plan: bool = False):
        self.total_tokens = 0
        self.model = "fake-model"
        self.plan_calls = 0
        self.reflect_calls = 0
        self.replan_once = replan_once
        self.bad_plan = bad_plan

    def chat(self, system, user, temperature=0.7):
        return "【测试】已分析你的学习状态，明天优先补弱项。"

    def structured_json(self, system, user, temperature=0.2):
        self.total_tokens += 10  # 模拟 token 累计
        if "可用工具" in user:  # planner 的 user 含「可用工具」清单
            self.plan_calls += 1
            if self.bad_plan:
                return {"goal": "g", "reasoning_summary": "x",
                        "steps": [{"tool": "no_such_tool", "arguments": {}}]}
            return {"goal": "分析我的学习状态，并提出明天计划",
                    "reasoning_summary": "测试计划", "steps": PLAN_STEPS}
        # reflector
        self.reflect_calls += 1
        if self.replan_once and self.reflect_calls == 1:
            return {"goal_completed": False, "need_replan": True,
                    "reason": "需要先确认任务列表", "next_action": "补充观察"}
        return {"goal_completed": True, "need_replan": False,
                "reason": "计划执行完毕", "next_action": "结束"}


class TestRuntime(unittest.TestCase):
    def setUp(self):
        reset_db()
        self.llm = FakeProvider()
        self.runtime = AgentRuntime(llm=self.llm)

    def test_full_loop_succeeds(self):
        run_id = self.runtime.run("分析我的学习状态，并提出明天计划", available_time=3)

        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        self.assertIn("测试", row["final_reply"])
        self.assertGreaterEqual(self.llm.plan_calls, 1)

        # 计划落库
        plan = json.loads(row["planner_output_json"])
        self.assertEqual(plan["goal"], "分析我的学习状态，并提出明天计划")
        self.assertEqual(len(plan["steps"]), 2)

        # create_task 生效：落库一条任务（直接生效，status=待开始）
        created = [t for t in crud.fetch_all("tasks") if t["title"] == "Agent 测试任务"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["status"], "待开始")
        self.assertEqual(created[0]["progress"], 0)

        # trace 事件序列覆盖五类关键事件
        types = [e["event_type"] for e in TraceStore.summary(run_id)]
        for t in ("observe", "plan", "tool_call", "tool_result", "reflect"):
            self.assertIn(t, types)

        # token 用量累计入库
        usage = json.loads(row["token_usage_json"])
        self.assertEqual(usage["total_tokens"], self.llm.total_tokens)
        self.assertGreater(usage["total_tokens"], 0)

    def test_replan_loops_then_stops(self):
        llm = FakeProvider(replan_once=True)
        runtime = AgentRuntime(llm=llm)
        run_id = runtime.run("分析我的学习状态，并提出明天计划")
        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        # 第一次 reflect 要求重规划 → planner 被调了两次
        self.assertEqual(llm.plan_calls, 2)
        self.assertEqual(row["iteration"], 2)
        types = [e["event_type"] for e in TraceStore.summary(run_id)]
        self.assertIn("replan", types)

    def test_planner_unknown_tool_marks_failed(self):
        llm = FakeProvider(bad_plan=True)
        runtime = AgentRuntime(llm=llm)
        run_id = runtime.run("分析我的学习状态")
        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "failed")
        self.assertIn("未知工具", row["error"])


if __name__ == "__main__":
    unittest.main()
