"""Runtime provider registry for web-managed APIs, local models, and subscription CLIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlparse

from langchain_core.language_models.llms import LLM
import requests

from activity_log import activity_log
from generation_control import generation_control


ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = Path(os.getenv("BOOKGEN_PROVIDER_STORE", ROOT / ".bookgen" / "providers.json"))
PROVIDER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,47}$")
CUSTOM_KINDS = {"openai_compatible", "anthropic"}


class ProviderError(ValueError):
    """User-facing provider configuration error."""


@dataclass
class ProviderDefinition:
    id: str
    name: str
    kind: str
    base_url: str = ""
    api_key: str = ""
    models: list[str] | None = None
    custom: bool = True

    def __post_init__(self):
        self.models = list(self.models or [])

    def public(self, available=True, status="ready") -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "base_url": self.base_url,
            "models": self.models,
            "custom": self.custom,
            "has_api_key": bool(self.api_key),
            "available": available,
            "status": status,
        }


class SubscriptionCLIModel(LLM):
    """LangChain LLM adapter around an officially authenticated vendor CLI."""

    provider_kind: str
    model: str = "default"
    timeout: int = 600
    working_directory: str = str(ROOT)

    @property
    def _llm_type(self) -> str:
        return self.provider_kind

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"provider": self.provider_kind, "model": self.model}

    def _call(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
        if self.provider_kind == "codex_cli":
            return self._call_codex(prompt)
        if self.provider_kind == "claude_cli":
            return self._call_claude(prompt)
        raise ProviderError(f"Unsupported CLI provider: {self.provider_kind}")

    def _call_codex(self, prompt: str) -> str:
        with tempfile.NamedTemporaryFile(prefix="bookgen-codex-", suffix=".txt", delete=False) as output:
            output_path = Path(output.name)
        command = [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-rules",
            "--sandbox", "read-only", "--color", "never", "--json",
            "--output-last-message", str(output_path),
        ]
        if self.model and self.model != "default":
            command.extend(["--model", self.model])
        command.append("-")
        started_at = time.monotonic()
        activity_log.emit("Starting Codex CLI generation call", source="codex")
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self.working_directory,
            )
            generation_control.register_process(process)
            stderr_lines: list[str] = []
            raw_events: list[str] = []
            finished = threading.Event()
            timed_out = threading.Event()

            def read_stderr() -> None:
                if process.stderr is None:
                    return
                for line in process.stderr:
                    detail = line.strip()
                    if detail:
                        stderr_lines.append(detail)
                        activity_log.emit(detail, kind="warning", source="codex")

            def heartbeat() -> None:
                while not finished.wait(10):
                    elapsed = int(time.monotonic() - started_at)
                    activity_log.emit(
                        f"Codex is still processing this request ({elapsed}s elapsed)",
                        kind="heartbeat",
                        source="codex",
                    )

            def enforce_timeout() -> None:
                if not finished.wait(self.timeout):
                    timed_out.set()
                    process.kill()

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            timeout_thread = threading.Thread(target=enforce_timeout, daemon=True)
            stderr_thread.start()
            heartbeat_thread.start()
            timeout_thread.start()

            if process.stdin is None or process.stdout is None:
                process.kill()
                raise ProviderError("Codex CLI pipes could not be initialized")
            try:
                process.stdin.write(prompt)
                process.stdin.close()
                for line in process.stdout:
                    raw = line.strip()
                    if not raw:
                        continue
                    raw_events.append(raw)
                    self._publish_codex_event(raw)
                return_code = process.wait()
            finally:
                finished.set()
                generation_control.unregister_process(process)
                stderr_thread.join(timeout=2)
                heartbeat_thread.join(timeout=2)
                timeout_thread.join(timeout=2)

            generation_control.checkpoint()
            if timed_out.is_set():
                raise ProviderError(f"Codex CLI timed out after {self.timeout} seconds")
            content = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
            if return_code != 0 or not content:
                detail = "\n".join(stderr_lines[-10:] or raw_events[-5:] or ["No response"])[-2000:]
                raise ProviderError(f"Codex CLI failed: {detail}")
            activity_log.emit(
                f"Codex CLI call completed in {int(time.monotonic() - started_at)}s",
                kind="success",
                source="codex",
            )
            return content
        except OSError as error:
            raise ProviderError(f"Could not start Codex CLI: {error}") from error
        finally:
            output_path.unlink(missing_ok=True)

    @staticmethod
    def _publish_codex_event(raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            activity_log.emit(raw, source="codex")
            return

        event_type = str(event.get("type", "event"))
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type", ""))
        if event_type == "thread.started":
            activity_log.emit("Codex session initialized", source="codex")
        elif event_type == "turn.started":
            activity_log.emit("Codex started processing the generation task", source="codex")
        elif event_type in {"item.started", "item.updated", "item.completed"}:
            text = item.get("text") or item.get("message") or item.get("command")
            if item_type == "agent_message" and text:
                activity_log.emit(f"Codex response:\n{text}", kind="output", source="codex")
            elif item_type == "reasoning":
                activity_log.emit(
                    f"Codex reasoning: {text}" if text else "Codex completed a reasoning step",
                    kind="reasoning",
                    source="codex",
                )
            elif item_type:
                details = []
                if text:
                    details.append(str(text))
                if item.get("aggregated_output"):
                    details.append(str(item["aggregated_output"]))
                if item.get("exit_code") is not None:
                    details.append(f"exit code {item['exit_code']}")
                description = f": {' | '.join(details)}" if details else ""
                activity_log.emit(
                    f"Codex {event_type.removeprefix('item.')}: {item_type}{description}",
                    kind="tool",
                    source="codex",
                )
        elif event_type == "turn.completed":
            usage = event.get("usage") or {}
            if usage:
                activity_log.emit(
                    "Codex turn complete: "
                    f"{usage.get('input_tokens', 0)} input, "
                    f"{usage.get('cached_input_tokens', 0)} cached, "
                    f"{usage.get('output_tokens', 0)} output tokens",
                    kind="usage",
                    source="codex",
                )
            else:
                activity_log.emit("Codex turn complete", kind="success", source="codex")
        elif "error" in event_type:
            detail = event.get("message") or event.get("error") or event_type
            activity_log.emit(detail, kind="error", source="codex")

    def _call_claude(self, prompt: str) -> str:
        command = [
            "claude", "--print", "--output-format", "json", "--no-session-persistence",
            "--tools", "", "--permission-mode", "plan",
        ]
        if self.model and self.model != "default":
            command.extend(["--model", self.model])
        result = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=self.working_directory,
            timeout=self.timeout,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "No response").strip()[-2000:]
            raise ProviderError(f"Claude Code failed: {detail}")
        try:
            payload = json.loads(result.stdout)
            content = str(payload.get("result", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            content = result.stdout.strip()
        if not content:
            raise ProviderError("Claude Code returned an empty response")
        return content


class AnthropicAPIModel(LLM):
    """Small Anthropic Messages API adapter without an extra SDK dependency."""

    model: str
    api_key: str
    base_url: str = "https://api.anthropic.com/v1"
    timeout: int = 180
    max_tokens: int = 4096
    temperature: float = 0.7

    @property
    def _llm_type(self) -> str:
        return "anthropic_api"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model, "base_url": self.base_url}

    def _call(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
        response = requests.post(
            f"{self.base_url.rstrip('/')}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": prompt}],
                **({"stop_sequences": stop} if stop else {}),
            },
            timeout=self.timeout,
        )
        if not response.ok:
            raise ProviderError(f"Anthropic API returned {response.status_code}: {response.text[-1000:]}")
        blocks = response.json().get("content", [])
        return "\n".join(str(block.get("text", "")) for block in blocks if block.get("type") == "text").strip()


class ProviderManager:
    def __init__(self, store_path: Path = STORE_PATH):
        self.store_path = Path(store_path)
        self._lock = threading.RLock()

    def _load_custom(self) -> list[ProviderDefinition]:
        with self._lock:
            if not self.store_path.exists():
                return []
            try:
                payload = json.loads(self.store_path.read_text(encoding="utf-8"))
                return [ProviderDefinition(**item) for item in payload.get("providers", [])]
            except (OSError, ValueError, TypeError) as error:
                raise ProviderError(f"Cannot read provider store: {error}") from error

    def _save_custom(self, providers: list[ProviderDefinition]) -> None:
        with self._lock:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.store_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"version": 1, "providers": [asdict(item) for item in providers]}, indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(temporary, 0o600)
            temporary.replace(self.store_path)

    @staticmethod
    def _command_status(command: list[str], parser=None) -> tuple[bool, str]:
        if not shutil.which(command[0]):
            return False, "not installed"
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=6, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, str(error)
        output = (result.stdout or result.stderr).strip()
        if parser:
            try:
                return parser(result.returncode, output)
            except (ValueError, TypeError, KeyError):
                return False, "authentication status unavailable"
        return result.returncode == 0, output[-300:]

    def _builtin_providers(self) -> list[tuple[ProviderDefinition, bool, str]]:
        ollama_models = self._ollama_records()
        codex_ok, codex_status = self._command_status(
            ["codex", "login", "status"],
            lambda code, output: (code == 0 and "logged in" in output.lower(), output.splitlines()[-1]),
        )
        claude_ok, claude_status = self._command_status(
            ["claude", "auth", "status", "--json"],
            lambda code, output: (
                code == 0 and bool(json.loads(output).get("loggedIn")),
                json.loads(output).get("authMethod", "not authenticated"),
            ),
        )
        return [
            (
                ProviderDefinition("ollama", "Ollama", "ollama", os.getenv("OLLAMA_API_BASE", "http://localhost:11434"), custom=False),
                bool(ollama_models),
                f"{len(ollama_models)} generation models" if ollama_models else "not reachable or no generation models",
            ),
            (
                ProviderDefinition("codex-cli", "Codex CLI (ChatGPT subscription)", "codex_cli", models=["default"], custom=False),
                codex_ok,
                codex_status,
            ),
            (
                ProviderDefinition("claude-code", "Claude Code (Pro/Max subscription)", "claude_cli", models=["default", "sonnet", "opus"], custom=False),
                claude_ok,
                claude_status,
            ),
        ]

    def list_public(self) -> list[dict[str, Any]]:
        providers = [definition.public(available, status) for definition, available, status in self._builtin_providers()]
        providers.extend(item.public(True, "configured") for item in self._environment_providers())
        providers.extend(item.public(True, "configured") for item in self._load_custom())
        return providers

    def _environment_providers(self) -> list[ProviderDefinition]:
        providers = []
        known = {
            "openai-api": ("OpenAI API", "openai_compatible", "OPENAI", "https://api.openai.com/v1"),
            "anthropic-api": ("Anthropic API", "anthropic", "ANTHROPIC", "https://api.anthropic.com/v1"),
            "deepseek-api": ("DeepSeek API", "openai_compatible", "DEEPSEEK", "https://api.deepseek.com/v1"),
            "groq-api": ("Groq API", "openai_compatible", "GROQ", "https://api.groq.com/openai/v1"),
        }
        for provider_id, (name, kind, prefix, default_url) in known.items():
            api_key = os.getenv(f"{prefix}_API_KEY", "").strip()
            if not api_key:
                continue
            names = [item.strip() for item in os.getenv(f"{prefix}_AVAILABLE_MODELS", "").split(",") if item.strip()]
            default_model = os.getenv(f"{prefix}_MODEL", "").strip()
            if default_model and default_model not in names:
                names.insert(0, default_model)
            providers.append(ProviderDefinition(
                provider_id,
                name,
                kind,
                os.getenv(f"{prefix}_API_BASE", default_url).strip() or default_url,
                api_key,
                names,
                custom=False,
            ))
        return providers

    def _all_definitions(self) -> dict[str, ProviderDefinition]:
        definitions = {item.id: item for item, _, _ in self._builtin_providers()}
        definitions.update({item.id: item for item in self._environment_providers()})
        definitions.update({item.id: item for item in self._load_custom()})
        return definitions

    def get(self, provider_id: str) -> ProviderDefinition:
        provider = self._all_definitions().get(provider_id)
        if not provider:
            raise ProviderError(f"Unknown provider: {provider_id}")
        return provider

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        kind = str(payload.get("kind", "")).strip()
        provider_id = self._slug(str(payload.get("id") or name))
        base_url = self._validate_url(str(payload.get("base_url", "")).strip())
        api_key = str(payload.get("api_key", "")).strip()
        models = self._normalize_models(payload.get("models", []))
        if not name or kind not in CUSTOM_KINDS:
            raise ProviderError("Name, supported provider type, and endpoint are required")
        if kind == "anthropic" and not api_key:
            raise ProviderError("Anthropic providers require an API key")
        if provider_id in self._all_definitions():
            raise ProviderError(f"Provider id already exists: {provider_id}")
        provider = ProviderDefinition(provider_id, name, kind, base_url, api_key, models, custom=True)
        if not provider.models:
            provider.models = self.discover_models(provider)
        providers = self._load_custom()
        providers.append(provider)
        self._save_custom(providers)
        return provider.public(True, "configured")

    def delete(self, provider_id: str) -> None:
        providers = self._load_custom()
        remaining = [item for item in providers if item.id != provider_id]
        if len(remaining) == len(providers):
            raise ProviderError("Only web-created providers can be deleted")
        self._save_custom(remaining)

    def discover_models(self, provider: ProviderDefinition | str) -> list[str]:
        if isinstance(provider, str):
            provider = self.get(provider)
        if provider.kind == "ollama":
            return [record["name"] for record in self._ollama_records()]
        if provider.kind in {"codex_cli", "claude_cli"}:
            return list(provider.models)
        headers = {"accept": "application/json"}
        if provider.kind == "anthropic":
            headers.update({"x-api-key": provider.api_key, "anthropic-version": "2023-06-01"})
        elif provider.api_key:
            headers["authorization"] = f"Bearer {provider.api_key}"
        response = requests.get(f"{provider.base_url.rstrip('/')}/models", headers=headers, timeout=12)
        if not response.ok:
            raise ProviderError(f"Model discovery returned {response.status_code}: {response.text[-1000:]}")
        data = response.json().get("data", response.json().get("models", []))
        names = []
        for item in data:
            name = item.get("id") or item.get("name") or item.get("model") if isinstance(item, dict) else item
            if name:
                names.append(str(name))
        return sorted(set(names))

    def models_for(self, provider_id: str) -> list[dict[str, Any]]:
        provider = self.get(provider_id)
        if provider.kind == "ollama":
            return self._ollama_records()
        names = provider.models or self.discover_models(provider)
        return [{"name": name, "display_name": name, "capabilities": [], "native_tools": False} for name in names]

    def test(self, provider_id: str) -> dict[str, Any]:
        provider = self.get(provider_id)
        if provider.kind == "ollama":
            models = self._ollama_records()
            return {"ok": bool(models), "message": f"Detected {len(models)} generation models"}
        if provider.kind == "codex_cli":
            ok, status = self._command_status(["codex", "login", "status"])
            return {"ok": ok, "message": status}
        if provider.kind == "claude_cli":
            ok, status = self._command_status(["claude", "auth", "status", "--json"])
            return {"ok": ok, "message": status}
        models = self.discover_models(provider)
        return {"ok": True, "message": f"Endpoint authenticated; {len(models)} models discovered"}

    def build_model(self, selection: str, common_params: dict[str, Any]):
        provider_id, model_name = self.parse_selection(selection)
        provider = self.get(provider_id)
        temperature = float(common_params.get("temperature", 0.7))
        callbacks = common_params.get("callbacks")
        if provider.kind == "ollama":
            from langchain_community.chat_models import ChatOllama

            return ChatOllama(
                model=model_name,
                base_url=provider.base_url,
                temperature=temperature,
                streaming=bool(common_params.get("streaming", False)),
                callbacks=callbacks,
            )
        if provider.kind == "openai_compatible":
            from langchain_community.chat_models import ChatOpenAI

            return ChatOpenAI(
                model=model_name,
                api_key=provider.api_key or "not-required",
                base_url=provider.base_url,
                temperature=temperature,
                streaming=bool(common_params.get("streaming", False)),
                callbacks=callbacks,
            )
        if provider.kind == "anthropic":
            return AnthropicAPIModel(
                model=model_name,
                api_key=provider.api_key,
                base_url=provider.base_url,
                temperature=temperature,
                callbacks=callbacks,
            )
        if provider.kind in {"codex_cli", "claude_cli"}:
            return SubscriptionCLIModel(
                provider_kind=provider.kind,
                model=model_name,
                timeout=int(os.getenv("CLI_PROVIDER_TIMEOUT", "600")),
                working_directory=os.getenv("BOOKGEN_PROJECT_DIR", str(ROOT)),
                callbacks=callbacks,
            )
        raise ProviderError(f"Unsupported provider type: {provider.kind}")

    @staticmethod
    def parse_selection(selection: str) -> tuple[str, str]:
        if ":" not in selection:
            raise ProviderError("Model selection must use provider:model")
        provider_id, model_name = selection.split(":", 1)
        if not provider_id or not model_name:
            raise ProviderError("Provider and model are required")
        return provider_id, model_name

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        if not PROVIDER_ID_PATTERN.fullmatch(slug):
            raise ProviderError("Provider id must contain 2-48 lowercase letters, numbers, or hyphens")
        return slug

    @staticmethod
    def _validate_url(value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ProviderError("Endpoint must be an HTTP(S) URL without embedded credentials")
        return value.rstrip("/")

    @staticmethod
    def _normalize_models(value: Any) -> list[str]:
        if isinstance(value, str):
            value = value.split(",")
        if not isinstance(value, list):
            raise ProviderError("Models must be a list or comma-separated string")
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))

    def _ollama_records(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"{os.getenv('OLLAMA_API_BASE', 'http://localhost:11434').rstrip('/')}/api/tags",
                timeout=3,
            )
            response.raise_for_status()
        except (requests.RequestException, ValueError):
            return []
        records = []
        for item in response.json().get("models", []):
            name = str(item.get("name") or item.get("model") or "").strip()
            capabilities = [str(value) for value in item.get("capabilities", [])]
            if not name or (capabilities and "completion" not in capabilities):
                continue
            details = item.get("details") or {}
            labels = ["tools"] if "tools" in capabilities else []
            if details.get("parameter_size"):
                labels.append(str(details["parameter_size"]))
            suffix = f" [{', '.join(labels)}]" if labels else ""
            records.append({
                "name": name,
                "display_name": f"{name}{suffix}",
                "capabilities": capabilities,
                "native_tools": "tools" in capabilities,
            })
        return records


provider_manager = ProviderManager()
