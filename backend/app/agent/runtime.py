"""AgentRuntime：Observe → Plan → Execute → Reflect 最小闭环编排。

- run() 是同步入口（测试用）；run_async() 是后台线程入口（路由用），二者行为一致
- run 全程不抛异常：任何内部异常都会落库 status='failed' + error，保证线程不会裸崩
- 观察阶段固定跑种子只读工具；随后进入 Plan→Execute→Reflect 循环，最多 MAX_ITERATIONS 轮
- 结束时用 synthesizer 生成中文最终建议，落 final_reply
"""
import json
import threading
from datetime import datetime

from .context import AgentContext
from .executor import Executor
from .llm_provider import AgentLLM
from .planner import Planner
from .prompts import load
from .reflector import Reflector
from .repo import STATUS_CANCELLED, RunRepo, gen_run_id, now
from ..services import memories
from ..services.plans import compute_plan_vs_actual, find_unreviewed
from .state import AgentState
from .tools import build_registry
from .trace import TraceStore

MAX_ITERATIONS = 3  # 硬上限：防止循环烧钱
# 种子观察工具：本轮先固定跑这 4 个只读工具收集状态
SEED_OBSERVE_TOOLS = [
    "get_learning_overview",
    "get_recent_learning_sessions",
    "get_weak_points",
    "get_task_list",
]


class AgentRuntime:
    def __init__(self, llm=None, registry=None):
        self.llm = llm or AgentLLM()
        self.registry = registry or build_registry()
        self.planner = Planner(self.llm)
        self.executor = Executor(self.registry)
        self.reflector = Reflector(self.llm)
        self.max_iterations = MAX_ITERATIONS

    # ---------- 入口 ----------
    def run(self, goal: str, available_time: int = 0) -> str:
        """同步执行（测试用）：建行 + 跑完 + 返回 run_id。全程不抛异常。"""
        run_id = gen_run_id()
        RunRepo.create(run_id, goal, available_time, model=self.llm.model)
        self._safe_execute(run_id, goal, available_time)
        return run_id

    def run_async(self, goal: str, available_time: int = 0) -> str:
        """后台线程执行（路由用）：建行后立即返回 run_id，循环在子线程跑。"""
        run_id = gen_run_id()
        RunRepo.create(run_id, goal, available_time, model=self.llm.model)
        threading.Thread(target=self._safe_execute, args=(run_id, goal, available_time), daemon=True).start()
        return run_id

    def _safe_execute(self, run_id: str, goal: str, available_time: int) -> None:
        try:
            self._execute(run_id, goal, available_time)
        except Exception as e:  # noqa: BLE001 —— run 不能裸崩，异常要落库
            self._fail(run_id, f"{type(e).__name__}: {e}")

    # ---------- 主循环 ----------
    def _execute(self, run_id: str, goal: str, available_time: int) -> None:
        trace = TraceStore(run_id)
        ctx = AgentContext(run_id)
        state = AgentState(
            goal=goal,
            current_date=datetime.now().date().isoformat(),
            available_time=available_time or 0,
        )

        # 1) Observe（确定性）：固定种子只读工具
        for tool in SEED_OBSERVE_TOOLS:
            res = self.registry.execute(tool, {}, ctx)
            state.observations[tool] = res
            trace.observe(tool, res)

        # 1b) 反馈回路：注入最久未复盘的过去计划 vs 实际对比（确定性，Planner/Reflector 都可见）
        self._inject_prior_plan_vs_actual(state, trace)
        # 1c) 长期记忆：注入已确认（active）的用户记忆，规划时遵守
        self._inject_memories(state, trace)

        # 2) Plan → Execute → Reflect 循环
        for iteration in range(1, self.max_iterations + 1):
            if self._cancelled(run_id):
                trace.replan("run 已被用户取消，提前结束")
                return
            state.iteration = iteration
            plan = self.planner.plan(goal, state, self.registry)
            state.current_plan = plan
            trace.plan(plan)
            RunRepo.update(
                run_id,
                iteration=iteration,
                planner_output_json=json.dumps(plan, ensure_ascii=False),
            )

            step_results = self.executor.run(state, plan, trace, ctx)
            state.executed_actions.extend(step_results)

            reflection = self.reflector.reflect(goal, state)
            state.reflection = reflection
            trace.reflect(reflection)
            RunRepo.update(run_id, reflection_json=json.dumps(reflection, ensure_ascii=False))

            if not reflection.get("need_replan"):
                break
            if iteration >= self.max_iterations:
                trace.replan("达到最大迭代次数，停止重规划")
                break
            trace.replan(reflection.get("reason") or "需要补充观察，重规划")

        # 3) Synthesize：中文最终建议
        if self._cancelled(run_id):
            return  # 保持 cancelled，不再覆盖为 succeeded
        final_reply = self._synthesize(goal, state)
        state.status = "succeeded"
        RunRepo.update(
            run_id,
            status="succeeded",
            finished_at=now(),
            final_reply=final_reply,
            state_json=json.dumps(state.to_dict(), ensure_ascii=False),
            token_usage_json=json.dumps({"total_tokens": self.llm.total_tokens}, ensure_ascii=False),
        )

    def _cancelled(self, run_id: str) -> bool:
        row = RunRepo.get(run_id)
        return bool(row and row["status"] == STATUS_CANCELLED)

    # ---------- 反馈回路注入 ----------
    def _inject_prior_plan_vs_actual(self, state: AgentState, trace: TraceStore) -> None:
        """有未复盘的过去计划 → 确定性注入「计划 vs 实际」对比，无则不注入（零噪音）。

        放在 observations 里，planner / reflector 每次 run 自动看到；
        数字走 task_sessions 真实 SUM，不由 LLM 编造。
        """
        target = find_unreviewed()
        if not target:
            return
        diff = compute_plan_vs_actual(target["plan_date"])
        if not diff:
            return
        state.observations["prior_plan_vs_actual"] = {"ok": True, "data": diff}
        trace.write("plan_compare", diff)

    def _inject_memories(self, state: AgentState, trace: TraceStore) -> None:
        """已确认的用户记忆（active）→ 注入 observations，规划时遵守；无则零噪音。

        只注入 active：pending（待确认）不参与规划，与 Phase 3「调整待确认不生效」同构。
        取 importance 降序前 20 条，防止烧 token。
        """
        mems = memories.active_memories()
        if not mems:
            return
        state.observations["user_memories"] = {"ok": True, "data": mems}
        trace.write("user_memories", {"count": len(mems), "mkeys": [m["mkey"] for m in mems]})

    # ---------- 失败落库 ----------
    def _fail(self, run_id: str, message: str) -> None:
        RunRepo.update(
            run_id,
            status="failed",
            finished_at=now(),
            error=message[:1000],
            token_usage_json=json.dumps({"total_tokens": self.llm.total_tokens}, ensure_ascii=False),
        )

    # ---------- 最终回复 ----------
    def _synthesize(self, goal: str, state) -> str:
        system = load("synthesizer")
        obs = {
            name: (res.get("data") if res.get("ok") else {"error": res.get("error")})
            for name, res in (state.observations or {}).items()
        }
        user = json.dumps({
            "goal": goal,
            "observations": obs,
            "plan": state.current_plan or {},
            "executed_actions": state.executed_actions,
            "reflection": state.reflection or {},
        }, ensure_ascii=False)
        return self.llm.chat(system, user, temperature=0.5)
