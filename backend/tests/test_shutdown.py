"""关闭服务（网页「关闭服务」按钮）单测：退出钩子调度 + 重复调用幂等 + 路由挂载。"""
import threading
import time
import unittest

from helpers import reset_db  # noqa: F401  —— 必须最先 import，它负责设 AGENT_STUDY_DB

from app import shutdown


class TestShutdownScheduler(unittest.TestCase):
    def setUp(self):
        shutdown.set_exit_hook(None)
        shutdown.reset_for_tests()

    def tearDown(self):
        shutdown.set_exit_hook(None)
        shutdown.reset_for_tests()

    def test_hook_runs_after_delay(self):
        called = threading.Event()
        shutdown.set_exit_hook(called.set)
        self.assertTrue(shutdown.request_shutdown(delay=0.05))
        self.assertTrue(called.wait(2.0), "退出钩子没有被调用")
        self.assertEqual(shutdown.get_exit_hook(), called.set)

    def test_second_call_is_rejected(self):
        """连点两次只安排一次退出（第二次返回 False → 路由层回 409）。"""
        called = threading.Event()
        shutdown.set_exit_hook(called.set)
        self.assertTrue(shutdown.request_shutdown(delay=0.05))
        self.assertFalse(shutdown.request_shutdown(delay=0.05))
        self.assertTrue(called.wait(2.0))

    def test_default_hook_is_os_exit(self):
        """默认钩子必须是 os._exit，不能是 sys.exit（守护线程里 sys.exit 退不了进程）。"""
        hook = shutdown.get_exit_hook()
        self.assertIs(hook, shutdown._default_exit)

    def test_reset_allows_again(self):
        shutdown.set_exit_hook(lambda: None)
        self.assertTrue(shutdown.request_shutdown(delay=0))
        self.assertFalse(shutdown.request_shutdown(delay=0))
        shutdown.reset_for_tests()
        self.assertTrue(shutdown.request_shutdown(delay=0))


class TestShutdownRoute(unittest.TestCase):
    """路由必须真的挂在 app 上，且是 POST。"""

    def test_route_registered(self):
        import main  # noqa: PLC0415 —— 放这里 import，避免影响其他用例的模块状态

        paths = {}
        for r in main.app.routes:
            paths.setdefault(getattr(r, "path", ""), set()).update(getattr(r, "methods", set()) or set())
        self.assertIn("/api/shutdown", paths)
        self.assertIn("POST", paths["/api/shutdown"])


if __name__ == "__main__":
    unittest.main()
