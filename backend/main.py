"""Agent 学习 OS · FastAPI 入口。

启动时自动建库 + 写种子数据；/api/* 走后端；/ 下托管前端构建产物(frontend/dist)。
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from app import db, seed, shutdown
from app.routers import (
    agent,
    algorithms,
    bago,
    chat,
    checkins,
    config,
    courses,
    dashboard,
    phases,
    projects,
    reports,
    search,
    settings,
    summaries,
    tasks,
)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    seed.seed_if_empty()
    seed.upgrade_route()        # 学习路线按 ROUTE_VERSION 幂等升级（保留已有进度）
    agent.recover_stale_runs()  # 清理进程崩溃后遗留的 running run
    agent.maybe_auto_review()   # 半自动提醒：有未复盘的过去计划 → 后台自动补一次复盘 run
    yield


app = FastAPI(title="Agent 学习 OS", version="0.1.0", lifespan=lifespan)

# ---------- API ----------
app.include_router(dashboard.router)
app.include_router(tasks.router)
app.include_router(phases.router)
app.include_router(algorithms.router)
app.include_router(bago.router)
app.include_router(courses.router)
app.include_router(projects.router)
app.include_router(checkins.router)
app.include_router(search.router)
app.include_router(reports.router)
app.include_router(summaries.router)
app.include_router(config.router)
app.include_router(settings.router)
app.include_router(chat.router)
app.include_router(agent.router)


@app.get("/api/backup")
def backup():
    """下载数据库备份文件。"""
    path = db.get_db_path()
    if not path.exists():
        return HTMLResponse("数据库尚未创建", status_code=404)
    return FileResponse(str(path), filename="agent_study_backup.db", media_type="application/octet-stream")


@app.get("/api/health")
def health():
    return {"ok": True, "db": str(db.get_db_path())}


@app.post("/api/shutdown")
def shutdown_app():
    """关闭本机服务（网页「关闭服务」按钮调用）。

    有 Agent run 正在跑时不关（返回 409），避免用户误点打断正在花钱的 LLM 调用。
    正常情况返回 200 + shutting_down，进程在约 0.8 秒后退出。
    """
    if agent.has_running_run():
        return JSONResponse(
            {"ok": False, "detail": "有 Agent 任务正在运行，等它结束或先取消再关闭"},
            status_code=409,
        )
    if not shutdown.request_shutdown():
        return JSONResponse({"ok": False, "detail": "服务已在关闭中"}, status_code=409)
    return {"ok": True, "detail": "服务正在关闭，可以关掉这个窗口了"}


@app.get("/api/version")
def version():
    """前端构建版本号：dist/index.html 的 mtime+size 摘要。

    前端用它判断"有没有新版"：每次改完前端重新构建、重启后端后，
    已打开的窗口会在切到前台/定时检查时发现版本变了 → 自动刷新成最新版。
    """
    idx = FRONTEND_DIST / "index.html"
    if not idx.exists():
        return JSONResponse({"version": "none"}, headers={"Cache-Control": "no-store"})
    st = idx.stat()
    return JSONResponse({"version": f"{st.st_mtime_ns}-{st.st_size}"},
                        headers={"Cache-Control": "no-store"})


# ---------- 前端静态文件（构建产物） ----------
IMMUTABLE_EXTS = ("js", "css", "png", "jpg", "jpeg", "gif", "svg", "ico",
                  "woff", "woff2", "ttf", "webp")


class FrontendStatic(StaticFiles):
    """托管前端构建产物：HTML 不缓存（每次都回源校验拿最新），哈希资源长缓存。

    Vite 构建的 JS/CSS 文件名带内容哈希（如 index-1a2b3c.js），
    所以资源可放心 immutable 长缓存；index.html 必须每次校验，
    浏览器才会拿到引用新哈希资源的最新入口文件。
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        ctype = response.headers.get("content-type", "")
        if ctype.startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.split(".")[-1].lower() in IMMUTABLE_EXTS:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


if FRONTEND_DIST.exists():
    app.mount("/", FrontendStatic(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/")
    def not_built():
        return HTMLResponse(
            "<h2>前端还没构建</h2><p>请先运行 <code>启动.bat</code>，或进入 frontend 目录执行 <code>npm run build</code>。</p>"
        )
