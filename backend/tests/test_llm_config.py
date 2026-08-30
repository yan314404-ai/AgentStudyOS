"""llm.py 配置层单测：provider 切换 / 旧键兼容 / save_config 合并语义。

用 mock.patch.object 把 CONFIG_PATH 指向临时文件，不碰真实 config.json，也不碰 DB。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import llm


class ConfigIsolation(unittest.TestCase):
    """基类：把 llm.CONFIG_PATH 隔离到临时文件。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self._tmp.name) / "config.json"
        self._patcher = mock.patch.object(llm, "CONFIG_PATH", self.config_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def write(self, cfg: dict) -> None:
        self.config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


class TestProviderResolution(ConfigIsolation):
    def test_old_config_without_provider_falls_back_to_deepseek(self):
        # 旧 config.json：只有 deepseek_*，无 provider 键
        self.write({"deepseek_api_key": "sk-old", "deepseek_model": "deepseek-chat"})
        self.assertEqual(llm.active_provider_id(), "deepseek")
        self.assertEqual(llm.active_model(), "deepseek-chat")
        self.assertTrue(llm.is_configured())

    def test_unknown_provider_falls_back_to_deepseek(self):
        self.write({"provider": "nope", "deepseek_api_key": "k"})
        self.assertEqual(llm.active_provider_id(), "deepseek")
        self.assertTrue(llm.is_configured())

    def test_active_model_uses_current_provider_model(self):
        self.write({"provider": "openai", "openai_api_key": "k", "openai_model": "gpt-4o"})
        self.assertEqual(llm.active_provider_id(), "openai")
        self.assertEqual(llm.active_model(), "gpt-4o")
        self.assertTrue(llm.is_configured())

    def test_is_configured_only_reads_active_provider_key(self):
        # provider=openai 但只配了 deepseek key → 未配置
        self.write({"provider": "openai", "deepseek_api_key": "sk"})
        self.assertFalse(llm.is_configured())

    def test_active_model_falls_back_to_provider_default(self):
        # openai_model 为空 → 回退默认 gpt-4o-mini
        self.write({"provider": "openai", "openai_api_key": "k"})
        self.assertEqual(llm.active_model(), "gpt-4o-mini")


class TestSaveConfig(ConfigIsolation):
    def test_save_preserves_existing_keys_across_provider_switch(self):
        # 关键：save_config 必须合并当前文件内容，切供应商不冲掉已存 key
        self.write({
            "provider": "deepseek",
            "deepseek_api_key": "sk-deep",
            "deepseek_model": "deepseek-chat",
        })
        merged = llm.save_config({"provider": "openai", "openai_api_key": "sk-oai"})
        self.assertEqual(merged["deepseek_api_key"], "sk-deep")  # 旧 key 保留
        self.assertEqual(merged["openai_api_key"], "sk-oai")
        self.assertEqual(merged["provider"], "openai")
        self.assertTrue(llm.is_configured())
        # 切回 deepseek：key 还在
        llm.save_config({"provider": "deepseek"})
        self.assertTrue(llm.is_configured())

    def test_save_empty_value_does_not_overwrite(self):
        self.write({"provider": "deepseek", "deepseek_api_key": "sk-old"})
        merged = llm.save_config({"deepseek_api_key": ""})  # 空值不覆盖
        self.assertEqual(merged["deepseek_api_key"], "sk-old")

    def test_save_merges_defaults(self):
        merged = llm.save_config({"provider": "anthropic", "anthropic_api_key": "sk-ant"})
        self.assertEqual(merged["anthropic_base_url"], "https://api.anthropic.com/v1")
        self.assertEqual(merged["anthropic_model"], "claude-sonnet-5")
        self.assertEqual(merged["provider"], "anthropic")
        self.assertTrue(llm.is_configured())

    def test_resolve_raises_when_key_missing(self):
        self.write({"provider": "openai"})
        with self.assertRaises(RuntimeError) as cm:
            llm._resolve()
        self.assertIn("GPT", str(cm.exception))
        self.assertIn("设置", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
