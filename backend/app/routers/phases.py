"""学习路线各阶段讲解 + 目标岗位要求（静态数据）。"""
from fastapi import APIRouter

from ..phase_guides import PHASE_GUIDES

router = APIRouter(prefix="/api/phases", tags=["阶段讲解"])


@router.get("")
def list_phases():
    return PHASE_GUIDES
