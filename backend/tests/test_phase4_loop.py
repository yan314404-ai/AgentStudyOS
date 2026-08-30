"""Phase 4 记忆闭环集成测试：FakeProvider 脚本化跑通「记住偏好 → 确认生效 → 规划遵守」。

- run1「记住我的偏好…」→ remember 落 pending（不参与规划）
- 用户确认 → active
- run2「安排明天的学习」→ 确定性注入 user_memories 出现在 planner 输入 → create_plan 可带 suggested_time
- pending 记忆不注入（零噪音）：确认前 planner 输入里没有 user_memories

全程无真实 LLM，用 LoopProvider 保证确定性。
"""
import unittest
from datetime import date, timedelta

from helpers import reset_db

from app import crud
from app.agent.repo import RunRepo
from app.agent.runtime import AgentRuntime
from app.agent.trace import TraceStore
from app.services import memories as msvc
from app.services import plans as psvc

TMR = (date.today() + timedelta(days=1)).isoformat()


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
        self.saw_memories = False  # planner 输入里是否含 user_memories 注入
        self.last_planner_user = ""

    def chat(self, system, user, temperature=0.7):
        return "【测试】记忆与计划结果见 Agent 页。"

    def structured_json(self, system, user, temperature=0.2):
        self.total_tokens += 10
        if "可用工具" in user:  # planner 的 user 含工具清单
            self.last_planner_user = user
            if "user_memories" in user:
                self.saw_memories = True
            return {"goal": "test", "reasoning_summary": "s", "steps": self.plan_steps}
        return {"goal_completed": True, "need_replan": False,
                "reason": "计划执行完毕", "next_action": "结束"}


class TestPhase4Loop(unittest.TestCase):
    def setUp(self):
        reset_db()

    # ---------- run1：记住偏好 → pending（不生效）→ 用户确认 → active ----------
    def test_remember_then_confirm_activates(self):
        provider = LoopProvider([
            {"tool": "remember", "arguments": {
                "key": "学习时段", "content": "工作日 20:00-23:00 学习效率最高",
                "type": "preference", "importance": 4,
            }},
        ])
        run_id = AgentRuntime(llm=provider).run("记住我的偏好：平时工作日 20:00-23:00 学习效率最高")

        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        # 记住走审计
        acts = crud.fetch_all("agent_actions", where="run_id=? AND tool='remember'", params=(run_id,))
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["ok"], 1)
        self.assertIn("pending", acts[0]["after_json"])
        # 落库待确认，注入还拿不到
        mems = msvc.get_memories()
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]["status"], "pending")
        self.assertEqual(msvc.active_memories(), [])
        # 确认 → active
        m = msvc.confirm_memory(mems[0]["id"])
        self.assertEqual(m["status"], "active")

    # ---------- run2：确认后安排学习 → planner 看到记忆 + 计划带 suggested_time ----------
    def test_plan_run_sees_active_memory_and_suggested_time(self):
        # 先记住 + 确认（跨 run 生效）
        m = msvc.remember("学习时段", "工作日 20:00-23:00 学习效率最高", "preference", 4)
        msvc.confirm_memory(m["id"])

        t = _new_task("算法-链表")
        provider = LoopProvider([
            {"tool": "create_plan", "arguments": {
                "plan_date": TMR,
                "items": [{"task_id": t["id"], "expected_minutes": 120, "suggested_time": "20:00-23:00"}],
                "goal": "按高效时段安排算法",
            }},
        ])
        run_id = AgentRuntime(llm=provider).run("安排明天的学习")

        row = RunRepo.get(run_id)
        self.assertEqual(row["status"], "succeeded")
        # 确定性注入真实出现在 planner 输入里，含记忆内容
        self.assertTrue(provider.saw_memories)
        self.assertIn("学习时段", provider.last_planner_user)
        self.assertIn('"status": "active"', provider.last_planner_user)
        # 计划落库且带建议时段
        plan = psvc.get_plan(TMR)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["items"][0]["suggested_time"], "20:00-23:00")
        # trace 里写了 user_memories 事件（前端时间线可见）
        types = [e["event_type"] for e in TraceStore.summary(run_id)]
        self.assertIn("user_memories", types)

    # ---------- 未确认（pending）不注入：零噪音 ----------
    def test_pending_memory_not_injected(self):
        msvc.remember("学习时段", "工作日 20:00-23:00 学习效率最高", "preference", 4)  # 不确认

        t = _new_task("算法-链表")
        provider = LoopProvider([
            {"tool": "create_plan", "arguments": {
                "plan_date": TMR, "items": [{"task_id": t["id"], "expected_minutes": 60}],
            }},
        ])
        run_id = AgentRuntime(llm=provider).run("安排明天的学习")

        # 无注入零噪音
        self.assertFalse(provider.saw_memories)
        self.assertNotIn("user_memories", provider.last_planner_user)
        types = [e["event_type"] for e in TraceStore.summary(run_id)]
        self.assertNotIn("user_memories", types)

    # ---------- forget 后不再注入 ----------
    def test_forgotten_memory_not_injected(self):
        m = msvc.remember("学习时段", "工作日 20:00-23:00 学习效率最高", "preference", 4)
        msvc.confirm_memory(m["id"])
        msvc.forget_memory(m["id"])  # 用户删除

        t = _new_task("算法-链表")
        provider = LoopProvider([
            {"tool": "create_plan", "arguments": {
                "plan_date": TMR, "items": [{"task_id": t["id"], "expected_minutes": 60}],
            }},
        ])
        AgentRuntime(llm=provider).run("安排明天的学习")
        self.assertFalse(provider.saw_memories)


if __name__ == "__main__":
    unittest.main()
