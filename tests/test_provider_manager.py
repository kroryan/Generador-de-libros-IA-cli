"""Provider registry, API adapter, and dependency-free web interface tests."""

import json
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from logging_config import get_logger
from activity_log import ActivityLog, activity_log
from provider_manager import AnthropicAPIModel, ProviderManager, SubscriptionCLIModel


class ProviderManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Path(self.temporary.name) / "providers.json"
        self.manager = ProviderManager(self.store)

    def tearDown(self):
        self.temporary.cleanup()

    @patch.object(ProviderManager, "_builtin_providers", return_value=[])
    @patch.object(ProviderManager, "_environment_providers", return_value=[])
    def test_custom_provider_is_stored_without_exposing_key(self, _environment, _builtins):
        public = self.manager.create({
            "name": "Local Gateway",
            "kind": "openai_compatible",
            "base_url": "http://127.0.0.1:9000/v1",
            "api_key": "secret-key",
            "models": "writer-a, writer-b",
        })
        self.assertEqual(public["id"], "local-gateway")
        self.assertTrue(public["has_api_key"])
        self.assertNotIn("api_key", public)
        self.assertEqual(stat.S_IMODE(self.store.stat().st_mode), 0o600)
        self.assertIn("secret-key", self.store.read_text(encoding="utf-8"))

    @patch("provider_manager.requests.get")
    def test_ollama_filters_embedding_only_models(self, request_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"models": [
            {"name": "writer:latest", "capabilities": ["completion", "tools"], "details": {"parameter_size": "4B"}},
            {"name": "embed:latest", "capabilities": ["embedding"], "details": {}},
        ]}
        request_get.return_value = response
        records = self.manager._ollama_records()
        self.assertEqual([item["name"] for item in records], ["writer:latest"])
        self.assertTrue(records[0]["native_tools"])

    @patch("provider_manager.requests.post")
    def test_anthropic_messages_adapter(self, request_post):
        response = Mock(ok=True)
        response.json.return_value = {"content": [{"type": "text", "text": "Canonical answer"}]}
        request_post.return_value = response
        model = AnthropicAPIModel(model="claude-test", api_key="secret")
        self.assertEqual(model.invoke("Write one line"), "Canonical answer")
        headers = request_post.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "secret")

    def test_context_logger_accepts_stdlib_arguments(self):
        logger = get_logger("test.context")
        logger.error("Provider %s failed with %s", "glm", "timeout", extra={"operation": "test"})

    def test_activity_log_is_incremental_and_bounded(self):
        journal = ActivityLog(max_events=2)
        first = journal.emit("one")
        journal.emit("two")
        third = journal.emit("three")
        payload = journal.snapshot(after=first.sequence)
        self.assertEqual([event["message"] for event in payload["events"]], ["two", "three"])
        self.assertEqual(payload["last_sequence"], third.sequence)
        self.assertFalse(payload["cursor_reset"])

        restarted_cursor = journal.snapshot(after=100)
        self.assertTrue(restarted_cursor["cursor_reset"])
        self.assertEqual([event["message"] for event in restarted_cursor["events"]], ["two", "three"])

    def test_codex_json_events_are_published(self):
        activity_log.reset()
        SubscriptionCLIModel._publish_codex_event(json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 8},
        }))
        events = activity_log.snapshot()["events"]
        self.assertIn("12 input", events[-1]["message"])
        self.assertEqual(events[-1]["kind"], "usage")

    @patch("provider_manager.subprocess.Popen")
    def test_codex_cli_adapter_consumes_jsonl_and_returns_output_file(self, popen):
        class FakeProcess:
            def __init__(self):
                self.stdin = io.StringIO()
                self.stdout = iter([
                    json.dumps({"type": "thread.started", "thread_id": "test"}) + "\n",
                    json.dumps({
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "Visible draft"},
                    }) + "\n",
                    json.dumps({"type": "turn.completed", "usage": {"output_tokens": 3}}) + "\n",
                ])
                self.stderr = iter([])

            def wait(self):
                return 0

            def kill(self):
                return None

        def launch(command, **_kwargs):
            output_index = command.index("--output-last-message") + 1
            Path(command[output_index]).write_text("Final response", encoding="utf-8")
            return FakeProcess()

        popen.side_effect = launch
        activity_log.reset()
        model = SubscriptionCLIModel(provider_kind="codex_cli", timeout=2)
        self.assertEqual(model.invoke("A private generation prompt"), "Final response")
        command = popen.call_args.args[0]
        self.assertIn("--json", command)
        messages = [event["message"] for event in activity_log.snapshot()["events"]]
        self.assertTrue(any("Visible draft" in message for message in messages))
        self.assertTrue(any("completed" in message for message in messages))

    def test_web_routes_are_local_and_provider_aware(self):
        import server

        providers = [{
            "id": "ollama", "name": "Ollama", "kind": "ollama", "base_url": "http://localhost:11434",
            "models": [], "custom": False, "has_api_key": False, "available": True, "status": "ready",
        }]
        models = [{"name": "writer:latest", "display_name": "writer:latest [tools]", "capabilities": ["tools"], "native_tools": True}]
        with patch.object(server.provider_manager, "list_public", return_value=providers), patch.object(
            server.provider_manager, "models_for", return_value=models
        ):
            client = server.app.test_client()
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            html = page.get_data(as_text=True)
            self.assertIn("matrix-background", html)
            self.assertNotIn("https://cdnjs", html)
            self.assertNotIn("axios", html)
            self.assertEqual(client.get("/providers").get_json()["providers"], providers)
            payload = client.get("/models?provider=ollama").get_json()
            self.assertEqual(payload["models"][0]["name"], "writer:latest")
            self.assertEqual(client.get("/status").status_code, 200)
            activity = client.get("/activity?after=0").get_json()
            self.assertIn("events", activity)
            self.assertIn("running", activity)
            self.assertIn("source-vault", html)
            self.assertIn("generation-controls", html)
            self.assertIn('id="guidance-form"', html)
            self.assertIn('id="web-search"', html)
            self.assertIn('id="vault-context-options" class="form-row" hidden', html)
            with patch.object(server.guidance_manager, "add", return_value={
                "message": "Keep the date uncertain", "active_generation": False,
            }), patch.object(server.guidance_manager, "snapshot", return_value={
                "active_generation": False, "active_count": 0, "pending_count": 1,
            }):
                guidance = client.post("/guidance", json={"message": "Keep the date uncertain"})
            self.assertEqual(guidance.status_code, 202)
            self.assertEqual(guidance.get_json()["pending_count"], 1)
            self.assertEqual(client.post("/guidance", json={}).status_code, 400)

    def test_vault_discovery_returns_real_bookgen_vaults(self):
        import server
        from obsidian_vault import ObsidianVaultWriter

        vault = ObsidianVaultWriter().create(
            output_directory=self.temporary.name, title="Discovered Vault", language="en",
            metadata={}, framework="Framework", book_bible="Canon.",
        )
        client = server.app.test_client()
        payload = client.get(f"/vaults?root={self.temporary.name}").get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["vaults"][0]["title"], "Discovered Vault")
        self.assertEqual(payload["vaults"][0]["path"], str(vault.root))
        books = client.get(f"/vault-books?vault={vault.root}").get_json()
        self.assertEqual(books["count"], 1)
        self.assertEqual(books["books"][0]["id"], "discovered-vault")


if __name__ == "__main__":
    unittest.main()
