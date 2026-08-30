"""llm.py HTTP 层单测：mock urllib.request.urlopen，验证三供应商请求/解析/错误映射/JSON 抽取。

不碰真实网络、真实 config.json、DB。
"""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from app import llm

DEEPSEEK_RESP = {
    "choices": [{"message": {"content": '{"ok": true}'}}],
    "usage": {"total_tokens": 42},
}
OPENAI_RESP = {
    "choices": [{"message": {"content": "hello"}}],
    "usage": {"total_tokens": 7},
}
ANTHROPIC_RESP = {
    "content": [{"type": "text", "text": "hi"}],
    "usage": {"input_tokens": 10, "output_tokens": 20},
}


class FakeResponse:
    """模拟 urlopen 返回的上下文管理器。"""

    def __init__(self, data: dict):
        self._data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._data


class HttpIsolation(unittest.TestCase):
    """隔离 CONFIG_PATH + 打桩 urllib.request.urlopen。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._config = Path(self._tmp.name) / "config.json"
        self._patcher = mock.patch.object(llm, "CONFIG_PATH", self._config)
        self._patcher.start()
        self._urlopen = mock.patch("urllib.request.urlopen")
        self.mock_open = self._urlopen.start()

    def tearDown(self):
        self._urlopen.stop()
        self._patcher.stop()
        self._tmp.cleanup()

    def write_config(self, cfg: dict) -> None:
        self._config.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    def capture_request(self):
        """捕获最后一次发给 urlopen 的 Request，返回 (url, headers, payload)。"""
        req = self.mock_open.call_args.args[0]
        return req.full_url, req.headers, json.loads(req.data.decode("utf-8"))

    @staticmethod
    def http_error(code: int, body: str = "oops"):
        return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body.encode()))

    def header(self, name: str) -> str:
        # urllib 会把 header 名 capitalize（x-api-key → X-api-key），HTTP 语义大小写不敏感，统一按小写找
        low = name.lower()
        _, headers, _ = self.capture_request()
        for k, v in headers.items():
            if k.lower() == low:
                return v
        raise KeyError(name)


class TestDeepSeekGpt(HttpIsolation):
    def test_deepseek_chat_url_and_headers(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "sk"})
        self.mock_open.return_value = FakeResponse(DEEPSEEK_RESP)
        text = llm.chat([{"role": "user", "content": "hi"}], timeout=5)
        url, headers, payload = self.capture_request()
        self.assertTrue(url.endswith("/chat/completions"))
        self.assertIn("https://api.deepseek.com", url)
        self.assertEqual(self.header("Authorization"), "Bearer sk")
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(text, '{"ok": true}')

    def test_openai_chat_and_usage(self):
        self.write_config({
            "provider": "openai",
            "openai_api_key": "sk-oai",
            "openai_model": "gpt-4o",
        })
        self.mock_open.return_value = FakeResponse(OPENAI_RESP)
        text, tokens = llm.chat_with_usage([{"role": "user", "content": "hi"}], timeout=5)
        url, headers, payload = self.capture_request()
        self.assertIn("https://api.openai.com/v1", url)
        self.assertEqual(self.header("Authorization"), "Bearer sk-oai")
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertEqual(text, "hello")
        self.assertEqual(tokens, 7)

    def test_structured_json_uses_response_format(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "sk"})
        self.mock_open.return_value = FakeResponse(DEEPSEEK_RESP)
        obj, tokens = llm.structured_json("sys", "user query", timeout=5)
        _, _, payload = self.capture_request()
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(obj, {"ok": True})
        self.assertEqual(tokens, 42)


class TestAnthropic(HttpIsolation):
    def test_anthropic_messages_endpoint_and_headers(self):
        self.write_config({
            "provider": "anthropic",
            "anthropic_api_key": "sk-ant",
            "anthropic_model": "claude-sonnet-5",
        })
        self.mock_open.return_value = FakeResponse(ANTHROPIC_RESP)
        text, tokens = llm.chat_with_usage(
            [{"role": "system", "content": "你是个助手"}, {"role": "user", "content": "hi"}],
            timeout=5,
        )
        url, headers, payload = self.capture_request()
        self.assertTrue(url.endswith("/messages"))
        self.assertEqual(self.header("x-api-key"), "sk-ant")
        self.assertEqual(self.header("anthropic-version"), llm.ANTHROPIC_VERSION)
        self.assertEqual(payload["model"], "claude-sonnet-5")
        self.assertEqual(payload["system"], "你是个助手")  # system 在顶层
        self.assertNotIn("system", payload["messages"][0])  # messages 里没有 system
        self.assertGreaterEqual(payload["max_tokens"], 1)
        self.assertEqual(text, "hi")
        self.assertEqual(tokens, 30)  # input 10 + output 20

    def test_anthropic_merges_adjacent_same_role(self):
        self.write_config({"provider": "anthropic", "anthropic_api_key": "sk-ant"})
        self.mock_open.return_value = FakeResponse(ANTHROPIC_RESP)
        llm.chat(
            [
                {"role": "user", "content": "a"},
                {"role": "user", "content": "b"},  # 连续两条 user（聊天失败后的场景）
                {"role": "assistant", "content": "c"},
            ],
            timeout=5,
        )
        _, _, payload = self.capture_request()
        msgs = payload["messages"]
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "a\nb")


class TestErrors(HttpIsolation):
    def test_401_maps_to_invalid_key(self):
        self.write_config({"provider": "openai", "openai_api_key": "bad"})
        self.mock_open.side_effect = self.http_error(401)
        with self.assertRaises(RuntimeError) as cm:
            llm.chat([{"role": "user", "content": "hi"}], timeout=5)
        self.assertIn("GPT API key 无效（401）", str(cm.exception))

    def test_402_and_429(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "k"})
        for code, kw in ((402, "余额不足"), (429, "过于频繁")):
            self.mock_open.side_effect = self.http_error(code)
            with self.assertRaises(RuntimeError) as cm:
                llm.chat([{"role": "user", "content": "hi"}], timeout=5)
            self.assertIn(kw, str(cm.exception))

    def test_urlerror_and_timeout(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "k"})
        self.mock_open.side_effect = urllib.error.URLError("refused")
        with self.assertRaises(RuntimeError) as cm:
            llm.chat([{"role": "user", "content": "hi"}], timeout=5)
        self.assertIn("无法连接", str(cm.exception))
        self.mock_open.side_effect = TimeoutError()
        with self.assertRaises(RuntimeError) as cm:
            llm.chat([{"role": "user", "content": "hi"}], timeout=5)
        self.assertIn("超时", str(cm.exception))

    def test_unconfigured_provider_raises_before_http(self):
        self.write_config({"provider": "openai"})  # 无 openai key
        with self.assertRaises(RuntimeError) as cm:
            llm.chat([{"role": "user", "content": "hi"}], timeout=5)
        self.assertIn("GPT API key", str(cm.exception))
        self.mock_open.assert_not_called()  # 没 key 时根本不该发请求


class TestExtractJson(unittest.TestCase):
    def test_code_fence(self):
        self.assertEqual(llm._extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_wrapped(self):
        obj = llm._extract_json('好的，这是结果：{"b": 2} 希望对你有帮助')
        self.assertEqual(obj, {"b": 2})

    def test_empty_raises(self):
        with self.assertRaises(RuntimeError):
            llm._extract_json("")

    def test_invalid_raises(self):
        with self.assertRaises(RuntimeError):
            llm._extract_json("no json here")

    def test_non_object_raises(self):
        with self.assertRaises(RuntimeError):
            llm._extract_json("[1, 2, 3]")


class TestStructuredJsonRetry(HttpIsolation):
    def test_retry_second_valid(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "k"})
        bad = FakeResponse({"choices": [{"message": {"content": "oops"}}], "usage": {"total_tokens": 1}})
        good = FakeResponse(DEEPSEEK_RESP)
        self.mock_open.side_effect = [bad, good]
        obj, _ = llm.structured_json("sys", "user", timeout=5)
        self.assertEqual(obj, {"ok": True})
        self.assertEqual(self.mock_open.call_count, 2)

    def test_retry_exhausted_raises_with_preview(self):
        self.write_config({"provider": "deepseek", "deepseek_api_key": "k"})
        bad = FakeResponse({"choices": [{"message": {"content": "still not json"}}], "usage": {"total_tokens": 1}})
        self.mock_open.return_value = bad
        with self.assertRaises(RuntimeError) as cm:
            llm.structured_json("sys", "user", timeout=5)
        self.assertIn("未返回合法 JSON", str(cm.exception))
        self.assertIn("still not json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
