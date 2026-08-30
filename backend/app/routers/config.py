"""模型配置：GET 当前是否已配置 + 活动供应商/模型，PUT 保存 key（存 backend/config.json，不回传）。

PUT /api/config 写死 deepseek_*，是给旧 Reports 内联表单的向后兼容入口；
新 UI（设置页）走 /api/settings。
"""
from fastapi import APIRouter

from .. import llm

router = APIRouter(prefix="/api/config", tags=["配置"])


@router.get("")
def get_config():
    return {
        "configured": llm.is_configured(),
        "provider": llm.active_provider_id(),
        "model": llm.active_model(),
    }


@router.put("")
def put_config(body: dict):
    cfg = llm.save_config(
        {
            "deepseek_api_key": body.get("api_key"),
            "deepseek_base_url": body.get("base_url"),
            "deepseek_model": body.get("model"),
        }
    )
    return {"configured": bool((cfg.get("deepseek_api_key") or "").strip())}
