"""系统提示词加载器：按名读取 prompts/*.txt，带内存缓存。"""
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_cache = {}


def load(name: str) -> str:
    if name not in _cache:
        _cache[name] = (_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return _cache[name]
