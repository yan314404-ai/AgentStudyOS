"""无窗口启动器（用 pythonw.exe 运行，双击不弹黑窗）。

点桌面图标 → 检测 8000 端口：已运行则直接开浏览器；
否则后台静默启动 uvicorn（日志写 backend/data/server.log），就绪后开浏览器。
测试时可用 --port 8001 和 --no-browser 参数（不弹浏览器）。
"""
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
LOG = ROOT / "backend" / "data" / "launch.log"
SERVER_LOG = ROOT / "backend" / "data" / "server.log"


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def _health_ok(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _msgbox(title: str, text: str) -> None:
    """无窗口弹一个提示框（不依赖控制台）。"""
    import ctypes
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)  # 0x40 = 信息图标
    except Exception:
        pass


def _open_app_window(url: str) -> bool:
    """优先用 Chrome/Edge 的「应用模式」开一个独立窗口（无地址栏/标签页）。

    找不到浏览器或启动失败时，退回默认浏览器打开。
    """
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for exe in candidates:
        if os.path.exists(exe):
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                subprocess.Popen([exe, f"--app={url}", "--window-size=1440,900"],
                                 creationflags=flags)
                return True
            except OSError:
                continue
    webbrowser.open(url)
    return False


def main() -> None:
    port = 8000
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            pass
    no_browser = "--no-browser" in sys.argv
    app_url = f"http://127.0.0.1:{port}"

    # 已运行：直接开浏览器
    if _health_ok(port):
        _log(f"端口 {port} 服务已在运行，打开独立窗口")
        if not no_browser:
            _open_app_window(app_url)
        return

    # 后台启动 uvicorn（无控制台窗口，日志进文件）
    py = str(PYTHONW) if PYTHONW.exists() else sys.executable
    cmd = [
        py, "-m", "uvicorn", "main:app",
        "--app-dir", str(ROOT / "backend"),
        "--host", "127.0.0.1", "--port", str(port),
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
        out = open(SERVER_LOG, "ab")
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=out, stderr=out, creationflags=flags)
        _log(f"已后台启动后端 PID={proc.pid}（端口 {port}），等待就绪…")
    except Exception as e:
        _log(f"启动失败: {e}")
        _msgbox("Agent 学习 OS", f"启动失败：{e}\n\n详见 backend/data/launch.log")
        return

    # 等待就绪（最多约 30 秒）
    ready = False
    for _ in range(60):
        if _health_ok(port):
            ready = True
            break
        time.sleep(0.5)

    if ready:
        _log("服务就绪，打开独立窗口")
        if not no_browser:
            _open_app_window(app_url)
    else:
        _log("等待就绪超时，请手动打开 " + app_url)
        _msgbox("Agent 学习 OS", f"服务启动较慢，请手动打开：\n{app_url}")


if __name__ == "__main__":
    main()
