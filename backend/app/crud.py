"""通用增删改查助手。列名白名单，避免把任意字段写进 SQL。"""
from .db import connect

# 各表允许被写入的字段（白名单）
ALLOWED = {
    "tasks": [
        "phase", "category", "title", "description", "resource", "start_date",
        "due_date", "priority", "status", "progress", "hours", "note", "created_at",
        "spent_minutes", "manual_progress",
    ],
    "algorithm_problems": [
        "title", "source", "url", "difficulty", "category", "is_first", "is_solved",
        "saw_solution", "review_count", "last_review_date", "next_review_date",
        "mastery", "time_complexity", "space_complexity", "note", "mistake_reason", "created_at",
    ],
    "bago_questions": [
        "category", "question", "standard_answer", "my_answer", "mastery", "is_wrong",
        "mistake_reason", "last_review_date", "next_review_date", "tags", "created_at",
    ],
    "courses": [
        "name", "phase", "platform", "url", "teacher", "total_minutes", "learned_minutes",
        "progress", "status", "rating", "review", "note", "next_to_watch", "created_at",
        "task_id",
    ],
    "projects": [
        "name", "goal", "background", "users", "core_features", "tech_stack", "github",
        "demo", "version", "status", "progress", "current_phase", "next_step", "risks", "problems",
        "solutions", "difficulties", "interview_points", "metrics", "readme", "created_at",
    ],
    "milestones": [
        "project_id", "name", "status", "progress", "planned_time", "actual_time",
        "start_date", "end_date", "note",
    ],
    "daily_logs": [
        "log_date", "algorithm_count", "algorithm_minutes", "bago_minutes", "course_minutes",
        "project_minutes", "reading_minutes", "total_minutes", "mood", "completed",
        "problems", "learned", "tomorrow_plan", "created_at",
    ],
    "daily_summaries": [
        "log_date", "content", "created_at", "updated_at",
    ],
}


def _clean(table: str, data: dict) -> dict:
    return {k: data[k] for k in ALLOWED.get(table, []) if k in data and data[k] is not None}


def fetch_all(table: str, where: str = "", params: tuple = (), order: str = "id") -> list:
    conn = connect()
    sql = f"SELECT * FROM {table}"
    if where:
        sql += " WHERE " + where
    sql += f" ORDER BY {order}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_one(table: str, rid: int):
    conn = connect()
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create(table: str, data: dict):
    data = _clean(table, data)
    conn = connect()
    cur = conn.cursor()
    cols = list(data.keys())
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    cur.execute(sql, list(data.values()))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return fetch_one(table, rid)


def update(table: str, rid: int, data: dict):
    data = _clean(table, data)
    if not data:
        return fetch_one(table, rid)
    conn = connect()
    cur = conn.cursor()
    sets = ",".join(f"{k}=?" for k in data)
    cur.execute(f"UPDATE {table} SET {sets} WHERE id=?", list(data.values()) + [rid])
    conn.commit()
    conn.close()
    return fetch_one(table, rid)


def delete(table: str, rid: int) -> None:
    conn = connect()
    conn.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
    conn.commit()
    conn.close()


def distinct(table: str, column: str) -> list:
    conn = connect()
    rows = conn.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} != '' ORDER BY {column}").fetchall()
    conn.close()
    return [r[0] for r in rows]
