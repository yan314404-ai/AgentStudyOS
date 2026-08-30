"""测试共享夹具：固定临时 DB 路径 + reset_db() 每次重建干净库。

必须在 import 任何 app 模块之前 import 本模块（它负责设置 AGENT_STUDY_DB 环境变量，
因为 app/db.py 在 import 时读该变量决定 DB 路径）。
"""
import os
import sys
import tempfile
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="agent_study_tests_"))
DB_FILE = _TMP_DIR / "test.db"
os.environ["AGENT_STUDY_DB"] = str(DB_FILE)

from app import db  # noqa: E402  必须在 env 设置好之后导入
from app import seed  # noqa: E402


def reset_db() -> None:
    """删掉旧库文件 + 建表 + 播种，得到一份干净夹具。"""
    if DB_FILE.exists():
        DB_FILE.unlink()
    db.init_db()
    seed.seed_if_empty()
