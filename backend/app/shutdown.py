"""关闭本机服务（给网页里的「关闭服务」按钮用）。

本应用是单进程本地服务，没有守护进程托管，所以「关闭」= 让当前进程退出：

1. 先回 HTTP 200，让浏览器收到响应（否则前端只会看到连接被重置）；
2. 起一个守护线程，延迟几百毫秒后调退出钩子。

退出钩子默认是 os._exit(0)（硬退出，绕过 atexit）。本应用所有 SQLite 写都是
「每次操作各自 connect/commit/close」，请求返回时已经落盘，所以硬退出不会丢数据，
也不会留下半开事务。真正需要防的是「有 Agent run 正在跑时被关掉」——那种情况
接口直接 409，不让关。

测试可以用 set_exit_hook() 把退出动作换成打标记，避免把测试进程杀掉。
"""
import os
import threading
import time

# 延迟多久真正退出：够 HTTP 响应写回浏览器，又不至于让用户觉得点了没反应
DEFAULT_DELAY = 0.8

_lock = threading.Lock()
_exit_hook = None
_started = False


def _default_exit() -> None:
    os._exit(0)


def get_exit_hook():
    return _exit_hook or _default_exit


def set_exit_hook(fn) -> None:
    """替换退出动作（测试用；传 None 恢复默认）。"""
    global _exit_hook
    _exit_hook = fn


def request_shutdown(delay: float = DEFAULT_DELAY) -> bool:
    """安排一次退出，返回是否成功安排（重复调用只有第一次生效）。"""
    global _started
    with _lock:
        if _started:
            return False
        _started = True
    hook = get_exit_hook()

    def _run() -> None:
        try:
            time.sleep(max(0.0, delay))
        finally:
            hook()

    threading.Thread(target=_run, name="agentos-shutdown", daemon=True).start()
    return True


def reset_for_tests() -> None:
    """测试用：清掉「已安排退出」标记。"""
    global _started
    with _lock:
        _started = False
