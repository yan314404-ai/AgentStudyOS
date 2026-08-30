"""无窗口停止器（用 pythonw.exe 运行）：结束监听指定端口的后端进程。

点桌面图标 → 杀掉监听 8000 的 uvicorn，弹出确认框。
测试时可用 --port 8001 指定端口。
"""
import ctypes
import subprocess
import sys


def _find_pids(port: int) -> list:
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
    except Exception as e:
        return [f"ERR:{e}"]
    pids = []
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.append(parts[-1])
    return pids


def _msgbox(title: str, text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except Exception:
        pass


def main() -> None:
    port = 8000
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            pass
    no_msg = "--no-msg" in sys.argv

    pids = _find_pids(port)
    if not pids or (len(pids) == 1 and pids[0].startswith("ERR")):
        if not no_msg:
            _msgbox("Agent 学习 OS", f"端口 {port} 没有正在运行的服务")
        return

    killed = []
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=10)
            killed.append(pid)
        except Exception:
            pass

    if killed:
        if not no_msg:
            _msgbox("Agent 学习 OS", f"已停止服务（PID {', '.join(killed)}）\n端口 {port} 已释放")
    else:
        if not no_msg:
            _msgbox("Agent 学习 OS", "停止失败，请手动在任务管理器结束 python 进程")


if __name__ == "__main__":
    main()
