"""Agent 工具规格定义。

每个工具 = ToolSpec：
  name          工具名（Planner 引用的唯一标识）
  description   给 LLM 看的一句话说明
  input_schema  给 LLM/文档看的 JSON Schema（描述参数）
  args_handler  参数校验 + 清洗：入参 dict → 干净 dict；失败抛 ValueError(中文)
  handler       执行函数：接收干净参数 dict + ctx（AgentContext，写工具用）→ 返回 dict
  permission    权限分级 read / append / mutate（全直接模式下不拦写，作元数据）
  category      工具分组（planner 提示词按组列出），如 观察 / 任务 / 课程·报告 / 写操作
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Permission(str, Enum):
    READ = "read"      # 只读，不写库
    APPEND = "append"  # 只插新行（create_task / add_session / create_review_task）
    MUTATE = "mutate"  # 可改既有行（update_task / complete_task）


@dataclass
class ToolSpec:
    name: str
    description: str
    args_handler: Callable[[dict], dict]
    handler: Callable[[dict, object], dict]
    permission: Permission = Permission.READ
    input_schema: dict = field(default_factory=dict)
    category: str = "读取"

    def __post_init__(self):
        if not isinstance(self.permission, Permission):
            self.permission = Permission(self.permission)
