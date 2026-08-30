"""AgentState：一次 run 内承载目标 / 观察 / 计划 / 执行的统一状态。可 JSON 序列化。"""
from dataclasses import asdict, dataclass, field


@dataclass
class AgentState:
    goal: str = ""
    current_date: str = ""
    available_time: int = 0                    # 每天可用学习小时
    learning_target: str = ""
    current_tasks: list = field(default_factory=list)
    weak_points: list = field(default_factory=list)
    recent_sessions: list = field(default_factory=list)
    course_progress: list = field(default_factory=list)
    algorithm_progress: dict = field(default_factory=dict)
    interview_progress: dict = field(default_factory=dict)
    project_progress: dict = field(default_factory=dict)
    recent_summaries: list = field(default_factory=list)
    memory: list = field(default_factory=list)        # 二期：长期记忆，本期留空
    observations: dict = field(default_factory=dict)  # 工具名 -> 最近一次结果
    current_plan: dict = field(default_factory=dict)
    executed_actions: list = field(default_factory=list)  # [{tool, args, ok, summary, error}]
    reflection: dict = field(default_factory=dict)
    iteration: int = 0
    status: str = "running"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentState":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (d or {}).items() if k in known})
