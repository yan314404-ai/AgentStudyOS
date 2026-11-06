"""AgentLLM 委托单测：mock llm 模块函数，验证委托 / token 累加 / model 跟随 / 结构回归。

不碰真实网络、真实 config.json、DB。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401 —— 先把 backend/ 加进 sys.path，单独跑本文件才不会 ModuleNotFoundError
from app import llm
from app.agent.llm_provider import AgentLLM


class AgentLLMTest(unittest.TestCase):
    def setUp(self):
        # AgentLLM.__init__ 会读 active_model → 需要隔离 config
        self._tmp = tempfile.TemporaryDirectory()
        self._config = Path(self._tmp.name) / "config.json"
        self._patcher = mock.patch.object(llm, "CONFIG_PATH", self._config)
        self._patcher.start()
        self.write_config({"provider": "deepseek", "deepseek_api_key": "sk"})

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def write_config(self, cfg: dict) -> None:
        self._config.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    def test_chat_delegates_and_accumulates(self):
        usage = {"model": "deepseek-chat", "input_tokens": 30, "output_tokens": 15,
                 "total_tokens": 45, "latency_ms": 800}
        with mock.patch("app.llm.chat_with_detail", return_value=("【测试】回复", usage)) as m:
            provider = AgentLLM()
            text = provider.chat("system", "user")
        m.assert_called_once()
        # 消息结构正确：system + user
        args = m.call_args.args[0]
        self.assertEqual([a["role"] for a in args], ["system", "user"])
        self.assertEqual(text, "【测试】回复")
        self.assertEqual(provider.total_tokens, 45)
        self.assertEqual(provider.input_tokens, 30)
        self.assertEqual(provider.output_tokens, 15)
        self.assertEqual(provider.latency_ms, 800)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(provider.model, "deepseek-chat")

    def test_structured_json_delegates_and_accumulates(self):
        usage = {"model": "deepseek-chat", "input_tokens": 100, "output_tokens": 23,
                 "total_tokens": 123, "latency_ms": 1200}
        with mock.patch("app.llm.structured_json_detail", return_value=({"ok": True}, usage)) as m:
            provider = AgentLLM()
            obj = provider.structured_json("sys", "user query")
        m.assert_called_once()
        self.assertEqual(obj, {"ok": True})
        self.assertEqual(provider.total_tokens, 123)
        self.assertEqual(provider.input_tokens, 100)

    def test_tokens_accumulate_across_calls(self):
        u1 = {"model": "deepseek-chat", "input_tokens": 8, "output_tokens": 2, "total_tokens": 10, "latency_ms": 100}
        u2 = {"model": "deepseek-chat", "input_tokens": 15, "output_tokens": 5, "total_tokens": 20, "latency_ms": 200}
        provider = AgentLLM()
        with mock.patch("app.llm.chat_with_detail", return_value=("a", u1)), \
             mock.patch("app.llm.structured_json_detail", return_value=({"ok": True}, u2)):
            provider.chat("s", "u")
            provider.structured_json("s", "u")
        self.assertEqual(provider.total_tokens, 30)
        self.assertEqual(provider.input_tokens, 23)
        self.assertEqual(provider.output_tokens, 7)
        self.assertEqual(provider.latency_ms, 300)
        self.assertEqual(provider.calls, 2)

    def test_usage_snapshot_has_cost(self):
        """成本快照：token 真值 + 按价目表折算的人民币，且标注是否命中已知价。"""
        usage = {"model": "deepseek-chat", "input_tokens": 1_000_000, "output_tokens": 0,
                 "total_tokens": 1_000_000, "latency_ms": 500}
        with mock.patch("app.llm.chat_with_detail", return_value=("x", usage)):
            provider = AgentLLM()
            provider.chat("s", "u")
        snap = provider.usage_snapshot()
        self.assertEqual(snap["input_tokens"], 1_000_000)
        self.assertEqual(snap["total_tokens"], 1_000_000)
        self.assertEqual(snap["cost_cny"], 2.0)   # deepseek 输入 2 元/百万 token
        self.assertTrue(snap["price_known"])
        self.assertEqual(snap["llm_calls"], 1)

    def test_init_model_is_active_model(self):
        self.write_config({"provider": "openai", "openai_api_key": "k", "openai_model": "gpt-4o"})
        provider = AgentLLM()
        self.assertEqual(provider.model, "gpt-4o")

    def test_structure_regression_no_own_http(self):
        # AgentLLM 不应再自带第二套 HTTP 层 / 模型解析
        provider = AgentLLM()
        self.assertFalse(hasattr(provider, "_post"))
        self.assertFalse(hasattr(provider, "_model"))
        self.assertFalse(hasattr(AgentLLM, "RETRY_TIMES"))

    def test_is_configured_delegates(self):
        provider = AgentLLM()
        self.assertTrue(provider.is_configured())
        self.write_config({"provider": "openai"})  # 无 openai key
        self.assertFalse(provider.is_configured())


if __name__ == "__main__":
    unittest.main()
