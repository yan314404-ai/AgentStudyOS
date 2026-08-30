"""多模型设置：GET/PUT 全局供应商+模型，POST 测试连接（用表单当前值，不落库）。

key 只存本机 config.json，永不回传；本 router 不做任何 DB 读写。
"""
from fastapi import APIRouter, HTTPException

from .. import llm

router = APIRouter(prefix="/api/settings", tags=["设置"])


@router.get("")
def get_settings():
    cfg = llm.load_config()
    return {
        "provider": llm.active_provider_id(cfg),
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "default_model": p.default_model,
                "suggested_models": p.suggested_models,
                "console_url": p.console_url,
            }
            for p in llm.PROVIDERS.values()
        ],
        "model": llm.active_model(cfg),
        "has_key": llm.is_configured(),
        # 每家各自已选的模型（切供应商时表单回填用）
        "models": {
            pid: (cfg.get(f"{pid}_model") or "").strip() or llm.PROVIDERS[pid].default_model
            for pid in llm.PROVIDERS
        },
        # 每家是否已存 key（前端 tab 显示「已配置」徽章用；key 本体永不回传）
        "has_keys": {
            pid: bool((cfg.get(f"{pid}_api_key") or "").strip())
            for pid in llm.PROVIDERS
        },
    }


@router.put("")
def put_settings(body: dict):
    pid = (body.get("provider") or "").strip().lower()
    if pid not in llm.PROVIDERS:
        raise HTTPException(400, "provider 必须是 deepseek / openai / anthropic 之一")
    cfg = {"provider": pid}
    key = (body.get("api_key") or "").strip()
    if key:
        cfg[f"{pid}_api_key"] = key
    model = (body.get("model") or "").strip()
    if model:
        cfg[f"{pid}_model"] = model
    llm.save_config(cfg)  # 合并当前文件：空值不覆盖、切供应商保留各家 key
    return {
        "configured": llm.is_configured(),
        "provider": pid,
        "model": llm.active_model(),
    }


@router.post("/test")
def test_settings(body: dict):
    ok, err = llm.ping(body.get("provider"), body.get("api_key"), body.get("model"), timeout=30)
    if not ok:
        return {"ok": False, "error": err}
    pid = (body.get("provider") or "").strip().lower() or "deepseek"
    model = (body.get("model") or "").strip() or llm.PROVIDERS[pid].default_model
    return {"ok": True, "provider": pid, "model": model}
