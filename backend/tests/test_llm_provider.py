"""AgentLLM 委托单测：mock llm 模块函数，验证委托 / token 累加 / model 跟随 / 结构回归。

不碰真实网络、真实 config.json、DB。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        with mock.patch("app.llm.chat_with_usage", return_value=("【测试】回复", 45)) as m:
            provider = AgentLLM()
            text = provider.chat("system", "user")
        m.assert_called_once()
        # 消息结构正确：system + user
        args = m.call_args.args[0]
        self.assertEqual([a["role"] for a in args], ["system", "user"])
        self.assertEqual(text, "【测试】回复")
        self.assertEqual(provider.total_tokens, 45)
        self.assertEqual(provider.model, llm.active_model())

    def test_structured_json_delegates_and_accumulates(self):
        with mock.patch("app.llm.structured_json", return_value=({"ok": True}, 123)) as m:
            provider = AgentLLM()
            obj = provider.structured_json("sys", "user query")
        m.assert_called_once()
        self.assertEqual(obj, {"ok": True})
        self.assertEqual(provider.total_tokens, 123)

    def test_tokens_accumulate_across_calls(self):
        provider = AgentLLM()
        with mock.patch("app.llm.chat_with_usage", return_value=("a", 10)), \
             mock.patch("app.llm.structured_json", return_value=({"ok": True}, 20)):
            provider.chat("s", "u")
            provider.structured_json("s", "u")
        self.assertEqual(provider.total_tokens, 30)

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
