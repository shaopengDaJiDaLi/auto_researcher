import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from auto_researcher.dispatch import RoleDispatcher
from auto_researcher.runner import AutoResearcher


class _OpenAIResponse:
    def __init__(self, content: str):
        self.choices = [
            types.SimpleNamespace(
                message=types.SimpleNamespace(content=content)
            )
        ]


class _AnthropicResponse:
    def __init__(self, content: str):
        self.content = [types.SimpleNamespace(text=content)]


class CompatibleProviderConfigTests(unittest.TestCase):
    def test_openai_compatible_provider_passes_base_url_and_custom_key_env(self):
        create = MagicMock(return_value=_OpenAIResponse("qwen ok"))
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create)
            )
        )
        ctor = MagicMock(return_value=client)
        fake_openai = types.SimpleNamespace(OpenAI=ctor)

        with patch.dict("sys.modules", {"openai": fake_openai}):
            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "secret-key"}, clear=False):
                dispatcher = RoleDispatcher(
                    provider="openai",
                    model="qwen-plus",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    api_key_env="DASHSCOPE_API_KEY",
                )
                result = dispatcher._call_openai(
                    "system prompt",
                    [{"role": "user", "content": "hello"}],
                )

        ctor.assert_called_once_with(
            api_key="secret-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["model"], "qwen-plus")
        self.assertEqual(result, "qwen ok")

    def test_anthropic_compatible_provider_passes_base_url_and_auth(self):
        create = MagicMock(return_value=_AnthropicResponse("minimax ok"))
        client = types.SimpleNamespace(
            messages=types.SimpleNamespace(create=create)
        )
        ctor = MagicMock(return_value=client)
        fake_anthropic = types.SimpleNamespace(Anthropic=ctor)

        with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
            with patch.dict(
                os.environ,
                {
                    "MINIMAX_API_KEY": "secret-key",
                    "MINIMAX_AUTH_TOKEN": "secret-token",
                },
                clear=False,
            ):
                dispatcher = RoleDispatcher(
                    provider="anthropic",
                    model="MiniMax-M2.1",
                    base_url="https://api.minimaxi.com/anthropic",
                    api_key_env="MINIMAX_API_KEY",
                    auth_token_env="MINIMAX_AUTH_TOKEN",
                )
                result = dispatcher._call_anthropic(
                    "system prompt",
                    [{"role": "user", "content": "hello"}],
                )

        ctor.assert_called_once_with(
            api_key="secret-key",
            auth_token="secret-token",
            base_url="https://api.minimaxi.com/anthropic",
        )
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["model"], "MiniMax-M2.1")
        self.assertEqual(result, "minimax ok")


class DomesticProviderPresetTests(unittest.TestCase):
    def test_preset_fills_base_url_and_key_env_and_routes_via_openai(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-secret"}, clear=False):
            d = RoleDispatcher(provider="deepseek", model="deepseek-chat")
        self.assertEqual(d.provider, "openai")          # routed through the OpenAI path
        self.assertEqual(d.provider_label, "deepseek")  # original name kept for logs
        self.assertEqual(d.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(d.api_key, "ds-secret")
        self.assertEqual(d.model, "deepseek-chat")      # model passed through verbatim

    def test_preset_aliases_resolve(self):
        for name, host in [
            ("qwen", "dashscope.aliyuncs.com"),
            ("kimi", "api.moonshot.cn"),
            ("glm", "open.bigmodel.cn"),
        ]:
            d = RoleDispatcher(provider=name, model="m")
            self.assertEqual(d.provider, "openai")
            self.assertIn(host, d.base_url)

    def test_explicit_cloud_base_url_and_key_env_override_preset(self):
        with patch.dict(os.environ, {"MY_KEY": "k"}, clear=False):
            d = RoleDispatcher(
                provider="deepseek", model="deepseek-chat",
                base_url="https://api.example-cloud.com/v1", api_key_env="MY_KEY",
            )
        self.assertEqual(d.base_url, "https://api.example-cloud.com/v1")
        self.assertEqual(d.api_key, "k")

    def test_preset_call_passes_base_url_and_model(self):
        create = MagicMock(return_value=_OpenAIResponse("deepseek ok"))
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        )
        ctor = MagicMock(return_value=client)
        with patch.dict("sys.modules", {"openai": types.SimpleNamespace(OpenAI=ctor)}):
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-secret"}, clear=False):
                d = RoleDispatcher(provider="deepseek", model="deepseek-reasoner")
                result = d._call_openai("sys", [{"role": "user", "content": "hi"}])
        ctor.assert_called_once_with(api_key="ds-secret", base_url="https://api.deepseek.com/v1")
        self.assertEqual(create.call_args.kwargs["model"], "deepseek-reasoner")
        self.assertEqual(result, "deepseek ok")

    def test_unknown_provider_error_mentions_presets(self):
        with self.assertRaisesRegex(ValueError, "deepseek"):
            RoleDispatcher(provider="not-a-provider", model="m")


class AutoResearcherProviderConfigTests(unittest.TestCase):
    @patch("auto_researcher.runner.RoleDispatcher")
    @patch("auto_researcher.runner.ResearchToolRegistry")
    @patch("auto_researcher.runner.NotesExporter")
    @patch("auto_researcher.runner.ExperimentMonitor")
    @patch("auto_researcher.runner.MemoryManager")
    @patch("auto_researcher.runner.build_execution_backend")
    def test_loop_passes_compatible_provider_config(
        self,
        build_backend_mock,
        _memory_mock,
        _monitor_mock,
        _obsidian_mock,
        _tool_registry_mock,
        dispatcher_mock,
    ):
        backend = MagicMock()
        build_backend_mock.return_value = backend

        with tempfile.TemporaryDirectory() as tmp:
            AutoResearcher(
                config={
                    "project": {"workspace": "workspace"},
                    "agent": {
                        "provider": "openai",
                        "model": "glm-4.5",
                        "base_url": "https://open.bigmodel.cn/api/paas/v4",
                        "api_key_env": "ZHIPUAI_API_KEY",
                        "auth_token_env": "",
                        "max_steps_per_cycle": 5,
                    },
                },
                project_dir=tmp,
            )

        dispatcher_mock.assert_any_call(
            model="glm-4.5",
            provider="openai",
            max_steps=5,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key_env="ZHIPUAI_API_KEY",
            auth_token_env="",
            workdir=tmp,
        )
        self.assertEqual(dispatcher_mock.call_count, 6)
        backend.validate.assert_called_once_with()

    @patch("auto_researcher.runner.RoleDispatcher")
    @patch("auto_researcher.runner.ResearchToolRegistry")
    @patch("auto_researcher.runner.NotesExporter")
    @patch("auto_researcher.runner.ExperimentMonitor")
    @patch("auto_researcher.runner.MemoryManager")
    @patch("auto_researcher.runner.build_execution_backend")
    def test_loop_accepts_role_specific_provider_config(
        self,
        build_backend_mock,
        _memory_mock,
        _monitor_mock,
        _obsidian_mock,
        _tool_registry_mock,
        dispatcher_mock,
    ):
        backend = MagicMock()
        build_backend_mock.return_value = backend

        with tempfile.TemporaryDirectory() as tmp:
            AutoResearcher(
                config={
                    "project": {"workspace": "workspace"},
                    "agent": {
                        "provider": "openai",
                        "model": "gpt-5.4",
                        "leader_provider": "codex_cli",
                        "reflect_provider": "codex_cli",
                        "idea_provider": "openai",
                        "idea_model": "gpt-5.5",
                        "code_modify_provider": "codex_cli",
                        "writing_provider": "openai",
                    },
                },
                project_dir=tmp,
            )

        dispatcher_mock.assert_any_call(
            model="gpt-5.4",
            provider="codex_cli",
            max_steps=3,
            base_url="",
            api_key_env="",
            auth_token_env="",
            workdir=tmp,
        )
        dispatcher_mock.assert_any_call(
            model="gpt-5.5",
            provider="openai",
            max_steps=3,
            base_url="",
            api_key_env="",
            auth_token_env="",
            workdir=tmp,
        )

    @patch("auto_researcher.runner.RoleDispatcher")
    @patch("auto_researcher.runner.ResearchToolRegistry")
    @patch("auto_researcher.runner.NotesExporter")
    @patch("auto_researcher.runner.ExperimentMonitor")
    @patch("auto_researcher.runner.MemoryManager")
    @patch("auto_researcher.runner.build_execution_backend")
    def test_openai_role_override_maps_default_anthropic_model(
        self,
        build_backend_mock,
        _memory_mock,
        _monitor_mock,
        _obsidian_mock,
        _tool_registry_mock,
        dispatcher_mock,
    ):
        backend = MagicMock()
        build_backend_mock.return_value = backend

        with tempfile.TemporaryDirectory() as tmp:
            AutoResearcher(
                config={
                    "project": {"workspace": "workspace"},
                    "agent": {
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-6",
                        "idea_provider": "openai",
                    },
                },
                project_dir=tmp,
            )

        dispatcher_mock.assert_any_call(
            model="codex-5.3",
            provider="openai",
            max_steps=3,
            base_url="",
            api_key_env="",
            auth_token_env="",
            workdir=tmp,
        )


if __name__ == "__main__":
    unittest.main()
