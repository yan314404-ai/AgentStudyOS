"""SQLite 连接、建库、迁移。路径由环境变量 AGENT_STUDY_DB 覆盖，否则放在 backend/data/ 下。"""
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = Path(os.environ.get("AGENT_STUDY_DB", str(DATA_DIR / "agent_study.db")))

# schema_version 从 1 开始，未来每加一张表/字段就追加一条迁移
MIGRATIONS = [
    # v1: 初始表结构
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase TEXT NOT NULL,
        category TEXT DEFAULT '',
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        resource TEXT DEFAULT '',
        start_date TEXT DEFAULT '',
        due_date TEXT DEFAULT '',
        priority TEXT DEFAULT '中',
        status TEXT DEFAULT '待开始',
        progress INTEGER DEFAULT 0,
        hours REAL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS algorithm_problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        source TEXT DEFAULT 'LeetCode',
        url TEXT DEFAULT '',
        difficulty TEXT DEFAULT '中等',
        category TEXT DEFAULT '数组',
        is_first INTEGER DEFAULT 1,
        is_solved INTEGER DEFAULT 0,
        saw_solution INTEGER DEFAULT 0,
        review_count INTEGER DEFAULT 0,
        last_review_date TEXT DEFAULT '',
        next_review_date TEXT DEFAULT '',
        mastery INTEGER DEFAULT 0,
        time_complexity TEXT DEFAULT '',
        space_complexity TEXT DEFAULT '',
        note TEXT DEFAULT '',
        mistake_reason TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bago_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        question TEXT NOT NULL,
        standard_answer TEXT DEFAULT '',
        my_answer TEXT DEFAULT '',
        mastery INTEGER DEFAULT 0,
        is_wrong INTEGER DEFAULT 0,
        mistake_reason TEXT DEFAULT '',
        last_review_date TEXT DEFAULT '',
        next_review_date TEXT DEFAULT '',
        tags TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phase TEXT DEFAULT '',
        platform TEXT DEFAULT '',
        url TEXT DEFAULT '',
        teacher TEXT DEFAULT '',
        total_minutes INTEGER DEFAULT 0,
        learned_minutes INTEGER DEFAULT 0,
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT '待开始',
        rating INTEGER DEFAULT 0,
        review TEXT DEFAULT '',
        note TEXT DEFAULT '',
        next_to_watch TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        goal TEXT DEFAULT '',
        background TEXT DEFAULT '',
        users TEXT DEFAULT '',
        core_features TEXT DEFAULT '',
        tech_stack TEXT DEFAULT '',
        github TEXT DEFAULT '',
        demo TEXT DEFAULT '',
        version TEXT DEFAULT 'V1',
        status TEXT DEFAULT '待开始',
        progress INTEGER DEFAULT 0,
        current_phase TEXT DEFAULT '',
        next_step TEXT DEFAULT '',
        risks TEXT DEFAULT '',
        problems TEXT DEFAULT '',
        solutions TEXT DEFAULT '',
        difficulties TEXT DEFAULT '',
        interview_points TEXT DEFAULT '',
        metrics TEXT DEFAULT '',
        readme TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT DEFAULT '待开始',
        progress INTEGER DEFAULT 0,
        planned_time TEXT DEFAULT '',
        actual_time TEXT DEFAULT '',
        start_date TEXT DEFAULT '',
        end_date TEXT DEFAULT '',
        note TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS daily_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT UNIQUE NOT NULL,
        algorithm_count INTEGER DEFAULT 0,
        algorithm_minutes INTEGER DEFAULT 0,
        bago_minutes INTEGER DEFAULT 0,
        course_minutes INTEGER DEFAULT 0,
        project_minutes INTEGER DEFAULT 0,
        reading_minutes INTEGER DEFAULT 0,
        total_minutes INTEGER DEFAULT 0,
        mood INTEGER DEFAULT 3,
        completed TEXT DEFAULT '',
        problems TEXT DEFAULT '',
        learned TEXT DEFAULT '',
        tomorrow_plan TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """,
    # v2: 第二阶段 —— 每日总结（手写）+ 周报/月报缓存（AI 生成后存起来，避免重复花钱）
    """
    CREATE TABLE IF NOT EXISTS daily_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_date TEXT UNIQUE NOT NULL,
        content TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        stats_json TEXT DEFAULT '',
        content TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(period_type, period_start)
    );
    """,
    # v3: 第三阶段 —— AI 助手聊天记录（持久化，重启不丢）
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,          -- 'user' | 'assistant'
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
    # v4: 学习路线重构 —— 自动计时/自动进度 + 课程关联任务
    # hours 字段复用为目标小时数（自动进度 = spent_minutes / (hours*60)）
    """
    ALTER TABLE tasks ADD COLUMN spent_minutes INTEGER DEFAULT 0;
    ALTER TABLE tasks ADD COLUMN manual_progress INTEGER DEFAULT -1;
    ALTER TABLE courses ADD COLUMN task_id INTEGER DEFAULT NULL;

    CREATE TABLE IF NOT EXISTS task_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        minutes INTEGER NOT NULL,
        log_date TEXT NOT NULL,
        note TEXT DEFAULT '',
        source TEXT DEFAULT 'timer',     -- 'timer' 计时器 / 'quick' 记一笔
        created_at TEXT NOT NULL
    );

    -- 旧版没有 manual_progress：已有 progress>0 的任务都是手动划的，迁移成「手动锁定」，避免自动模式把进度重置为 0
    UPDATE tasks SET manual_progress=progress WHERE progress>0 AND manual_progress=-1;

    -- 给已有 15 个种子任务补目标小时数（hours=0 才补，不覆盖用户改过的）
    UPDATE tasks SET hours=60  WHERE title='Python 基础：函数/类/异常/文件/虚拟环境' AND hours=0;
    UPDATE tasks SET hours=30  WHERE title='Git + Linux + HTTP/JSON/API' AND hours=0;
    UPDATE tasks SET hours=40  WHERE title='FastAPI + MySQL/Redis + Docker 入门' AND hours=0;
    UPDATE tasks SET hours=40  WHERE title='Transformer / Attention / Token / Embedding' AND hours=0;
    UPDATE tasks SET hours=30  WHERE title='大模型 API / Prompt / Structured Output' AND hours=0;
    UPDATE tasks SET hours=50  WHERE title='文档解析 / Chunk / Embedding / 检索' AND hours=0;
    UPDATE tasks SET hours=40  WHERE title='BM25 / Hybrid / Rerank / Query Rewrite' AND hours=0;
    UPDATE tasks SET hours=40  WHERE title='Tool Calling / Function Calling / ReAct' AND hours=0;
    UPDATE tasks SET hours=50  WHERE title='Memory / Workflow / LangGraph' AND hours=0;
    UPDATE tasks SET hours=30  WHERE title='MCP / Tool Registry / 权限与重试' AND hours=0;
    UPDATE tasks SET hours=50  WHERE title='Tracing / Eval / Cost / Latency / Cache' AND hours=0;
    UPDATE tasks SET hours=200 WHERE title='LeetCode Hot 100 + 高频题型' AND hours=0;
    UPDATE tasks SET hours=80  WHERE title='OS / 网络 / MySQL / Redis / Java·Python' AND hours=0;
    UPDATE tasks SET hours=120 WHERE title='Research Agent / Coding Agent 二选一深挖' AND hours=0;
    UPDATE tasks SET hours=40  WHERE title='简历 / 面试 / 牛客面经复盘' AND hours=0;

    -- 课程挂到对应任务
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='Python 基础：函数/类/异常/文件/虚拟环境') WHERE name LIKE '黑马%Python%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='Transformer / Attention / Token / Embedding') WHERE name LIKE '%动手学深度学习%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='文档解析 / Chunk / Embedding / 检索') WHERE name LIKE '%RAG 项目实战%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='Memory / Workflow / LangGraph') WHERE name LIKE 'LangChain + RAG + Agent + LangGraph%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='MCP / Tool Registry / 权限与重试') WHERE name LIKE 'LLM + RAG + Agent + LangChain + MCP%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='简历 / 面试 / 牛客面经复盘') WHERE name LIKE '%面试%' AND task_id IS NULL;
    UPDATE courses SET task_id=(SELECT id FROM tasks WHERE title='LeetCode Hot 100 + 高频题型') WHERE name='LeetCode Hot 100' AND task_id IS NULL;
    """,
    # v5: Agent Runtime —— 一次 run 的档案 + 逐步执行轨迹
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL,
        goal TEXT NOT NULL,
        available_time INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running',        -- running / succeeded / failed / cancelled
        model TEXT DEFAULT '',
        iteration INTEGER DEFAULT 0,
        started_at TEXT NOT NULL,
        finished_at TEXT DEFAULT '',
        state_json TEXT DEFAULT '',
        planner_output_json TEXT DEFAULT '',
        final_reply TEXT DEFAULT '',
        reflection_json TEXT DEFAULT '',
        error TEXT DEFAULT '',
        token_usage_json TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_trace_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        event_type TEXT NOT NULL,   -- observe / plan / tool_call / tool_result / reflect / replan / error
        content_json TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """,
    # v6: Agent 操作审计 —— 每次写操作的参数 + before/after 快照（全直接模式的回滚兜底依据）
    """
    CREATE TABLE IF NOT EXISTS agent_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        tool TEXT NOT NULL,
        args_json TEXT DEFAULT '',
        before_json TEXT DEFAULT '',
        after_json TEXT DEFAULT '',
        ok INTEGER DEFAULT 1,
        error TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """,
    # v7: Phase 3 跨天计划 —— Agent 生成计划(agent_plans) + 计划项(agent_plan_items)
    # 计划按执行日 plan_date UNIQUE 一份，可被多次 run 更新/复盘；复盘调整走 review_status + adjustments_json（待确认）
    """
    CREATE TABLE IF NOT EXISTS agent_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_date TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'active',      -- active / pending(有待确认调整) / reviewed
        goal TEXT NOT NULL DEFAULT '',
        reasoning_summary TEXT NOT NULL DEFAULT '',
        run_id TEXT NOT NULL DEFAULT '',
        prev_plan_id INTEGER DEFAULT NULL,          -- 计划链：上一份计划 id
        expected_total INTEGER DEFAULT 0,
        review_status TEXT NOT NULL DEFAULT 'none', -- none / pending / applied / rejected
        review_verdict TEXT NOT NULL DEFAULT '',
        review_reasoning TEXT NOT NULL DEFAULT '',
        review_run_id TEXT NOT NULL DEFAULT '',
        adjustments_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_plan_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'task',          -- task(复用) / new(新建) / review(复习)
        expected_minutes INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',      -- active / removed
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    """,
    # v8: Phase 4 长期记忆（结构化，非向量库）—— 用户偏好/事实/目标，Agent 记住 → 用户确认 → 规划遵守
    # + 计划项补可选「建议时段」suggested_time，让时间类偏好（如"工作日 20:00-23:00 高效"）落实到计划卡
    """
    CREATE TABLE IF NOT EXISTS agent_memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mkey TEXT NOT NULL UNIQUE,               -- 短中文标识，同主题覆盖更新（"改主意"复用同 key）
        mtype TEXT NOT NULL DEFAULT 'preference',-- preference / fact / goal / rule
        content TEXT NOT NULL,                   -- 结构化事实，如 "工作日 20:00-23:00 学习效率最高"
        keywords TEXT NOT NULL DEFAULT '',       -- 逗号分隔，二期检索用
        importance INTEGER NOT NULL DEFAULT 3,   -- 1-5，注入排序
        status TEXT NOT NULL DEFAULT 'pending',  -- pending(待确认) / active(已确认) / rejected(已拒绝) / forgotten(已忘记)
        source_run_id TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    ALTER TABLE agent_plan_items ADD COLUMN suggested_time TEXT NOT NULL DEFAULT '';
    """,
]


def get_db_path() -> Path:
    return DB_PATH


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def schema_version() -> int:
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    return int(row["value"]) if row else 0


def init_db() -> None:
    """应用所有未执行的迁移。幂等，可反复调用。"""
    conn = connect()
    conn.executescript("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
    ver = schema_version()
    target = len(MIGRATIONS)
    for i in range(ver, target):
        conn.executescript(MIGRATIONS[i])
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('schema_version',?)",
            (str(i + 1),),
        )
        conn.commit()
    conn.close()
