"""多模型 LLM 统一调用入口（DeepSeek / GPT / Claude）。

API key 存 backend/config.json（本机明文，不进数据库、不被 /api/backup 导出）。
用标准库 urllib 发请求，避免引入 requests 依赖。

三家差异（请求 URL / Header / payload / 响应解析 / token 提取）封装在 Provider 类，
对外只暴露 chat / generate / chat_with_usage / structured_json / ping。
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
CONFIG_PATH = BACKEND_DIR / "config.json"

# 兼容旧键：provider 缺省 = deepseek（旧 config 只有 deepseek_* 也自动走 deepseek）
DEFAULTS = {
    "provider": "deepseek",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-chat",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "anthropic_base_url": "https://api.anthropic.com/v1",
    "anthropic_model": "claude-sonnet-5",
}

ANTHROPIC_MAX_TOKENS = 2048        # Claude 自由文本（chat/generate）
ANTHROPIC_MAX_TOKENS_JSON = 4096   # Claude 结构化输出（planner/reflector 计划可能含多步）
ANTHROPIC_VERSION = "2023-06-01"
JSON_RETRY_TIMES = 1               # 结构化输出解析失败的重试次数（对齐原 AgentLLM）


class Provider:
    """单个供应商的差异封装：请求 URL / Header / payload / 响应解析 / token 提取。"""

    __slots__ = (
        "id", "label", "default_model", "default_base_url", "json_mode",
        "suggested_models", "console_url",
    )

    def __init__(self, id_, label, default_model, default_base_url, json_mode,
                 suggested_models, console_url):
        self.id = id_
        self.label = label
        self.default_model = default_model
        self.default_base_url = default_base_url
        self.json_mode = json_mode          # 是否有原生 json_object（Claude 没有）
        self.suggested_models = suggested_models
        self.console_url = console_url

    # ---------- 请求差异 ----------
    def chat_url(self, base_url) -> str:
        # Claude 走 /v1/messages，其余 OpenAI 兼容 /chat/completions
        suffix = "/messages" if self.id == "anthropic" else "/chat/completions"
        return base_url.rstrip("/") + suffix

    def headers(self, api_key) -> dict:
        if self.id == "anthropic":
            return {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            }
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def payload(self, model, messages, temperature, *, require_json=False, max_tokens=None) -> dict:
        # Claude：system 在顶层、max_tokens 必填、相邻同 role 合并（Anthropic 拒绝连续相同 role）
        if self.id == "anthropic":
            system_parts = [m["content"] for m in messages if m.get("role") == "system"]
            rest = _merge_adjacent([m for m in messages if m.get("role") != "system"])
            body = {
                "model": model,
                "max_tokens": max_tokens or ANTHROPIC_MAX_TOKENS,
                "messages": rest,
                "temperature": temperature,
            }
            if system_parts:
                body["system"] = "\n".join(system_parts)
            return body
        body = {"model": model, "messages": messages, "temperature": temperature}
        if require_json:
            body["response_format"] = {"type": "json_object"}
        return body

    # ---------- 响应差异 ----------
    def extract_text(self, data) -> str:
        if self.id == "anthropic":
            try:
                return data["content"][0]["text"].strip()
            except (KeyError, IndexError, TypeError):
                pass
        else:
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                pass
        raise RuntimeError(f"{self.label} 返回格式异常：{json.dumps(data, ensure_ascii=False)[:200]}")

    def extract_tokens(self, data) -> int:
        if self.id == "anthropic":
            usage = data.get("usage") or {}
            return int((usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0))
        usage = data.get("usage") or {}
        return int(usage.get("total_tokens") or 0)

    def extract_usage(self, data) -> tuple:
        """拆出 (输入 token, 输出 token)。成本估算要分开算，两家字段名不同。

        OpenAI 兼容：usage.prompt_tokens / completion_tokens（老接口也叫 input/output_tokens）
        Claude：usage.input_tokens / output_tokens
        拿不到细分时回退 (0, total)，调用方据 total 兜底，不编造。
        """
        usage = data.get("usage") or {}
        if self.id == "anthropic":
            it = int(usage.get("input_tokens") or 0)
            ot = int(usage.get("output_tokens") or 0)
            return it, ot
        it = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        ot = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        if not it and not ot:
            return 0, int(usage.get("total_tokens") or 0)
        return it, ot


def _merge_adjacent(messages: list) -> list:
    """合并相邻同 role 消息（聊天失败后可能出现连续两条 user，Claude 会 422 拒绝）。"""
    if not messages:
        return messages
    merged = [dict(messages[0])]
    for m in messages[1:]:
        if m.get("role") == merged[-1].get("role"):
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


PROVIDERS = {
    "deepseek": Provider(
        id_="deepseek", label="DeepSeek", default_model="deepseek-chat",
        default_base_url="https://api.deepseek.com", json_mode=True,
        # 2026-08-25 真机实测：四个名字 API 都接受（chat 返回文本、其余为思考模式返回空 content）。
        # 网络有传言说 deepseek-chat 已退役，实测未发生，保留。
        suggested_models=["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro"],
        console_url="https://platform.deepseek.com",
    ),
    "openai": Provider(
        id_="openai", label="GPT", default_model="gpt-4o-mini",
        default_base_url="https://api.openai.com/v1", json_mode=True,
        # 名单来自网络资料，本机无 GPT key 未逐一实测；旧名保留（官方退役传言未经证实）。
        suggested_models=[
            "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
            "gpt-5", "gpt-5-mini", "gpt-5-nano", "o3", "o3-mini", "o4-mini",
        ],
        console_url="https://platform.openai.com",
    ),
    "anthropic": Provider(
        id_="anthropic", label="Claude", default_model="claude-sonnet-5",
        default_base_url="https://api.anthropic.com/v1", json_mode=False,
        # 官方文档 + 当前模型线：dateless 都是固定快照，非通配指针。
        suggested_models=["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5", "claude-fable-5"],
        console_url="https://console.anthropic.com",
    ),
}


# ---------- 配置助手 ----------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: dict) -> dict:
    # 合并当前文件内容：切供应商时保留各家已存 key / 模型，空值不覆盖。
    merged = {**DEFAULTS, **load_config(), **{k: v for k, v in cfg.items() if v}}
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def active_provider_id(cfg=None) -> str:
    """当前活动供应商 id；缺省/非法一律回退 deepseek（旧 config 兼容）。"""
    cfg = cfg if cfg is not None else load_config()
    pid = (cfg.get("provider") or "deepseek").strip().lower()
    return pid if pid in PROVIDERS else "deepseek"


def active_model(cfg=None) -> str:
    """当前活动供应商的模型名；没填就回退该供应商默认模型。"""
    cfg = cfg if cfg is not None else load_config()
    pid = active_provider_id(cfg)
    return (cfg.get(f"{pid}_model") or "").strip() or PROVIDERS[pid].default_model


def is_configured() -> bool:
    cfg = load_config()
    pid = active_provider_id(cfg)
    return bool((cfg.get(f"{pid}_api_key") or "").strip())


def _resolve(cfg=None) -> tuple:
    """返回 (Provider, api_key, model, base_url)；未配置 key 抛中文 RuntimeError。"""
    cfg = cfg if cfg is not None else load_config()
    pid = active_provider_id(cfg)
    p = PROVIDERS[pid]
    key = (cfg.get(f"{pid}_api_key") or "").strip()
    if not key:
        raise RuntimeError(f"未配置 {p.label} API key，请在「⚙️ 设置」页配置")
    model = (cfg.get(f"{pid}_model") or "").strip() or p.default_model
    base = (cfg.get(f"{pid}_base_url") or "").strip() or p.default_base_url
    return p, key, model, base


# ---------- 统一 HTTP 层（合并原 llm.py 与 AgentLLM._post 两套 urllib） ----------

def _http_post(url, payload, headers, label, timeout) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        if e.code == 401:
            raise RuntimeError(f"{label} API key 无效（401），请检查 key 是否正确") from e
        if e.code == 402:
            raise RuntimeError(f"{label} 账户余额不足（402），请去平台充值") from e
        if e.code == 429:
            raise RuntimeError(f"{label} 请求过于频繁（429），请稍后重试") from e
        raise RuntimeError(f"{label} 接口返回错误 {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 {label}：{e.reason}（请检查网络）") from e
    except TimeoutError:
        raise RuntimeError(f"{label} 请求超时，请稍后重试") from None


# ---------- 公开 API（chat / generate 签名向后兼容，路由零改动） ----------

def _chat(messages, temperature, timeout) -> tuple:
    p, key, model, base = _resolve()
    data = _http_post(
        p.chat_url(base),
        p.payload(model, messages, temperature),
        p.headers(key),
        p.label,
        timeout,
    )
    return p.extract_text(data), p.extract_tokens(data)


def _chat_detail(messages, temperature, timeout) -> tuple:
    """同 _chat，但返回 (文本, {model, input_tokens, output_tokens, total_tokens, latency_ms})。

    成本看板要输入/输出分开计价，所以单独走一条；老接口 chat_with_usage 签名不变。
    """
    p, key, model, base = _resolve()
    t0 = time.time()
    data = _http_post(
        p.chat_url(base),
        p.payload(model, messages, temperature),
        p.headers(key),
        p.label,
        timeout,
    )
    latency_ms = int((time.time() - t0) * 1000)
    it, ot = p.extract_usage(data)
    total = p.extract_tokens(data) or (it + ot)
    return p.extract_text(data), {
        "model": model,
        "input_tokens": it,
        "output_tokens": ot,
        "total_tokens": total,
        "latency_ms": latency_ms,
    }


def chat(messages: list, temperature: float = 0.7, timeout: int = 60) -> str:
    """调用当前供应商的 chat 接口（支持多轮），返回回复文本。失败抛带中文信息的 RuntimeError。"""
    return _chat(messages, temperature, timeout)[0]


def chat_with_usage(messages: list, temperature: float = 0.7, timeout: int = 60) -> tuple:
    """同 chat，但额外返回本次消耗的 token 数（AgentLLM 用它累计 usage）。"""
    return _chat(messages, temperature, timeout)


def chat_with_detail(messages: list, temperature: float = 0.7, timeout: int = 60) -> tuple:
    """同 chat，返回 (文本, usage 明细)。usage 含 model/输入输出 token/总 token/延迟毫秒。"""
    return _chat_detail(messages, temperature, timeout)


def generate(system: str, user: str, temperature: float = 0.7) -> str:
    """单轮调用（报告用）。内部走 chat()，保持向后兼容。"""
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        timeout=30,
    )


# ---------- 结构化 JSON ----------

def _extract_json(content: str) -> dict:
    """把模型输出里的 JSON 对象剥出来解析。三家共用：DeepSeek/GPT 是兜底，Claude 是主路径。"""
    if not content:
        raise RuntimeError("模型返回空内容，无法解析 JSON")
    text = content.strip()
    if text.startswith("```"):  # 剥 ```json ... ``` 代码围栏
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise RuntimeError(f"模型未返回合法 JSON：{content[:200]}")
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        raise RuntimeError(f"模型返回的 JSON 无法解析：{text[start:end + 1][:200]}")
    if not isinstance(obj, dict):
        raise RuntimeError("JSON 不是对象")
    return obj


def structured_json(system: str, user: str, temperature: float = 0.2, timeout: int = 90) -> tuple:
    """要求模型只输出 JSON 对象。返回 (dict, tokens)。解析失败重试 JSON_RETRY_TIMES 次再抛 RuntimeError。

    诚实标注：Claude 没有 json_object 原生模式，靠「system 强提示 + _extract_json 抽取兜底 + 重试」，
    失败会把内容预览上抛成中文 RuntimeError（Agent 页直接显示 ⚠️ 模型未返回合法 JSON…）。
    """
    obj, usage = _structured_json_detail(system, user, temperature, timeout)
    return obj, usage["total_tokens"]


def structured_json_detail(system: str, user: str, temperature: float = 0.2, timeout: int = 90) -> tuple:
    """同 structured_json，返回 (dict, usage 明细)。重试时的 token 累加，不丢账。"""
    return _structured_json_detail(system, user, temperature, timeout)


def _structured_json_detail(system: str, user: str, temperature: float, timeout: int) -> tuple:
    p, key, model, base = _resolve()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if p.json_mode:
        require_json, max_tokens = True, None
    else:
        messages[0]["content"] = (
            system + "\n\n请严格只输出一个合法的 JSON 对象，不要输出任何其他文字、解释或代码围栏。"
        ).strip()
        require_json, max_tokens = False, ANTHROPIC_MAX_TOKENS_JSON

    attempts = 0
    t0 = time.time()
    acc_in = acc_out = 0
    while True:
        data = _http_post(
            p.chat_url(base),
            p.payload(model, messages, temperature, require_json=require_json, max_tokens=max_tokens),
            p.headers(key),
            p.label,
            timeout,
        )
        it, ot = p.extract_usage(data)
        acc_in += it
        acc_out += ot
        content = p.extract_text(data)
        usage = {
            "model": model,
            "input_tokens": acc_in,
            "output_tokens": acc_out,
            "total_tokens": acc_in + acc_out or p.extract_tokens(data),
            "latency_ms": int((time.time() - t0) * 1000),
        }
        try:
            return _extract_json(content), usage
        except RuntimeError:
            attempts += 1
            if attempts > JSON_RETRY_TIMES:
                raise RuntimeError(
                    f"模型未返回合法 JSON（重试 {attempts} 次仍失败）：{content[:200]}"
                ) from None


# ---------- 测试连接 ----------

def ping(provider_id: str, api_key: str, model: str = "", timeout: int = 30) -> tuple:
    """测试连接：用表单当前值（未保存）打一次最小请求。返回 (ok, err)。"""
    pid = (provider_id or "").strip().lower()
    p = PROVIDERS.get(pid)
    if not p:
        return False, "未知的模型供应商"
    if not (api_key or "").strip():
        return False, "请输入该供应商的 API key"
    m = (model or "").strip() or p.default_model
    try:
        data = _http_post(
            p.chat_url(p.default_base_url),
            p.payload(
                m,
                [{"role": "user", "content": "请只回复两个字符：ok"}],
                0.0,
                max_tokens=8 if p.id == "anthropic" else None,
            ),
            p.headers(api_key.strip()),
            p.label,
            timeout,
        )
        p.extract_text(data)
        return True, ""
    except RuntimeError as e:
        return False, str(e)
