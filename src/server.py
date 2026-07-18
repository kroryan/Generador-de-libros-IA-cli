"""Flask and Socket.IO interface for the canonical generation pipeline."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sys
import threading
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from flask_socketio import SocketIO

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from config.defaults import get_config
from activity_log import activity_log
from generation_state import GenerationStatus, LoggingObserver, SocketIOObserver, state_manager
from generation_control import GenerationCancelled, generation_control
from guidance import guidance_manager
from language import normalize_language
from pipeline import BookGenerationPipeline, BookGenerationRequest
from provider_manager import ProviderError, provider_manager
from publishing import SUPPORTED_OUTPUT_FORMATS
from utils import update_model_name


config = get_config()
app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "templates"),
)
socketio = SocketIO(
    app,
    cors_allowed_origins=config.socketio.cors_allowed_origins,
    async_mode=config.socketio.async_mode.value,
    ping_interval=config.socketio.ping_interval,
    ping_timeout=config.socketio.ping_timeout,
)
state_manager.add_observer(SocketIOObserver(socketio))
state_manager.add_observer(LoggingObserver())

_generation_lock = threading.Lock()
_latest_output: Path | None = None


def _book_records(manifest: dict) -> list[dict]:
    books = manifest.get("books")
    if isinstance(books, list) and books:
        return [{
            "id": str(item.get("id", "")),
            "title": str(item.get("title", "Untitled")),
            "path": str(item.get("path", "")),
            "chapter_count": len(item.get("chapters", [])),
            "drafted_count": sum(chapter.get("status") == "drafted" for chapter in item.get("chapters", [])),
        } for item in books]
    chapters = manifest.get("chapters", [])
    return [{
        "id": "legacy", "title": str(manifest.get("title", "Untitled")), "path": "",
        "chapter_count": len(chapters),
        "drafted_count": sum(chapter.get("status") == "drafted" for chapter in chapters),
    }]


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/providers")
def providers():
    return jsonify({"providers": provider_manager.list_public()})


@app.get("/models")
def models():
    provider_id = str(request.args.get("provider", "")).strip()
    try:
        if provider_id:
            discovered = provider_manager.models_for(provider_id)
        else:
            discovered = []
            for provider in provider_manager.list_public():
                if not provider["available"]:
                    continue
                for model in provider_manager.models_for(provider["id"]):
                    discovered.append({**model, "provider": provider["id"]})
        selection = os.environ.get("SELECTED_MODEL", "").strip()
        selected_provider, _, selected_model = selection.partition(":")
        if selected_provider != provider_id:
            env_prefix = provider_id.upper().replace("-", "_")
            selected_model = os.environ.get(f"{env_prefix}_MODEL", "").strip()
        return jsonify({"models": discovered, "count": len(discovered), "selected_model": selected_model})
    except ProviderError as error:
        return jsonify({"error": str(error)}), 400


@app.get("/vaults")
def vaults():
    requested_root = str(request.args.get("root", config.generation.output_directory)).strip()
    root = Path(requested_root).expanduser()
    if not root.is_absolute():
        root = ROOT / root
    root = root.resolve()
    if not root.exists():
        return jsonify({"vaults": [], "count": 0, "root": str(root)})
    discovered = []
    candidates = [root / ".bookgen" / "manifest.json", *root.glob("*/.bookgen/manifest.json")]
    for manifest_path in candidates[:200]:
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            vault_root = manifest_path.parent.parent.resolve()
            chapters = manifest.get("chapters", [])
            discovered.append({
                "path": str(vault_root),
                "title": manifest.get("title") or vault_root.name,
                "language": manifest.get("language", ""),
                "chapter_count": len(chapters),
                "drafted_count": sum(item.get("status") == "drafted" for item in chapters),
                "updated_at": manifest_path.stat().st_mtime,
            })
        except (OSError, TypeError, ValueError):
            continue
    discovered.sort(key=lambda item: item["updated_at"], reverse=True)
    return jsonify({"vaults": discovered, "count": len(discovered), "root": str(root)})


@app.get("/vault-books")
def vault_books():
    vault_root = Path(str(request.args.get("vault", ""))).expanduser().resolve()
    manifest_path = vault_root / ".bookgen" / "manifest.json"
    if not manifest_path.is_file():
        return jsonify({"error": "Selected vault is not a valid BookGen vault"}), 400
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return jsonify({"error": "Selected vault manifest is invalid"}), 400
    books = _book_records(manifest)
    return jsonify({"books": books, "count": len(books)})


@app.post("/providers")
def create_provider():
    try:
        provider = provider_manager.create(request.get_json(silent=True) or {})
        return jsonify({"provider": provider}), 201
    except ProviderError as error:
        return jsonify({"error": str(error)}), 400


@app.delete("/providers/<provider_id>")
def delete_provider(provider_id: str):
    try:
        provider_manager.delete(provider_id)
        return jsonify({"deleted": provider_id})
    except ProviderError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/providers/<provider_id>/test")
def test_provider(provider_id: str):
    try:
        result = provider_manager.test(provider_id)
        return jsonify(result), 200 if result["ok"] else 503
    except ProviderError as error:
        return jsonify({"ok": False, "error": str(error)}), 400


@app.get("/status")
def generation_status():
    """Dependency-free browser polling endpoint."""
    return jsonify(state_manager.get_state().to_dict())


@app.get("/activity")
def generation_activity():
    """Return incremental events produced by the pipeline and provider CLIs."""
    try:
        after = max(0, int(request.args.get("after", 0)))
        limit = int(request.args.get("limit", 250))
    except (TypeError, ValueError):
        return jsonify({"error": "after and limit must be integers"}), 400
    payload = activity_log.snapshot(after=after, limit=limit)
    payload["running"] = _generation_lock.locked()
    return jsonify(payload)


@app.post("/guidance")
def add_guidance():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Guidance message is required"}), 400
    if len(message) > 4000:
        return jsonify({"error": "Guidance message must be 4000 characters or fewer"}), 400
    item = guidance_manager.add(message)
    state = guidance_manager.snapshot()
    activity_log.emit(
        f"User guidance received: {message}", kind="guidance", source="user"
    )
    return jsonify({"guidance": item, **state}), 202


@app.post("/generation/pause")
def pause_generation():
    if not _generation_lock.locked():
        return jsonify({"error": "No generation is running"}), 409
    control = generation_control.pause()
    state_manager.update_state(paused=True, current_step="Generation paused after the active model call.")
    activity_log.emit("Pause requested; no new generation step will start.", kind="warning", source="server")
    return jsonify(control)


@app.post("/generation/resume")
def resume_generation():
    if not _generation_lock.locked():
        return jsonify({"error": "No generation is running"}), 409
    control = generation_control.resume()
    state_manager.update_state(paused=False, current_step="Generation resumed.")
    activity_log.emit("Generation resumed.", source="server")
    return jsonify(control)


@app.post("/generation/cancel")
def cancel_generation():
    if not _generation_lock.locked():
        return jsonify({"error": "No generation is running"}), 409
    control = generation_control.cancel()
    state_manager.update_state(paused=False, cancel_requested=True, current_step="Cancellation requested...")
    activity_log.emit("Cancellation requested.", kind="warning", source="server")
    return jsonify(control)


@app.get("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "generation_status": state_manager.get_state().status.value,
        "pipeline": "obsidian-first",
        "languages": ["en", "es"],
        "output_formats": list(SUPPORTED_OUTPUT_FORMATS),
    })


@app.post("/generate")
def generate():
    data = request.get_json(silent=True) or {}
    try:
        language = normalize_language(data.get("language", config.generation.default_language))
        output_format = str(data.get("outputFormat", config.generation.default_output_format)).lower()
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
        subject = str(data.get("subject", "")).strip()
        profile = str(data.get("profile", "")).strip()
        if not subject or not profile:
            raise ValueError("Subject and reader/profile brief are required")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    output_path = Path(str(data.get("outputPath", config.generation.output_directory))).expanduser()
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    provider_id = str(data.get("provider", "")).strip()
    model_name = str(data.get("model", "")).strip()
    if not provider_id or not model_name:
        return jsonify({"error": "Provider and model are required"}), 400
    try:
        provider_manager.get(provider_id)
    except ProviderError as error:
        return jsonify({"error": str(error)}), 400
    model = f"{provider_id}:{model_name}"
    source_vault_path = str(data.get("sourceVault", "")).strip()
    source_book_id = str(data.get("sourceBook", "")).strip()
    vault_mode = str(data.get("vaultMode", "new")).strip().lower()
    if source_vault_path:
        source_root = Path(source_vault_path).expanduser().resolve()
        if not (source_root / ".bookgen" / "manifest.json").is_file():
            return jsonify({"error": "Selected source vault is not a valid BookGen vault"}), 400
        if vault_mode not in {"continue", "related", "revise"}:
            return jsonify({"error": "Invalid source vault mode"}), 400
        try:
            source_manifest = json.loads((source_root / ".bookgen" / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError):
            return jsonify({"error": "Selected source vault manifest is invalid"}), 400
        valid_book_ids = {item["id"] for item in _book_records(source_manifest)}
        if source_book_id not in valid_book_ids:
            return jsonify({"error": "Select a valid book from the source vault"}), 400
    else:
        source_root = None
        vault_mode = "new"
    generation_request = BookGenerationRequest(
        subject=subject,
        profile=profile,
        style=str(data.get("style", config.generation.default_style)).strip(),
        genre=str(data.get("genre", config.generation.default_genre)).strip(),
        language=language,
        output_format=output_format,
        output_path=str(output_path.resolve()),
        agent_tools=bool(data.get("agentTools", config.generation.agent_tools_enabled)),
        web_search=bool(data.get("webSearch", False)),
        source_vault_path=str(source_root) if source_root else "",
        source_book_id=source_book_id if source_root else "",
        vault_mode=vault_mode,
    )

    if not _generation_lock.acquire(blocking=False):
        return jsonify({"error": "A generation is already running"}), 409
    state_manager.reset()
    generation_control.reset()
    guidance_manager.start_generation()
    queued_guidance = guidance_manager.snapshot()["active_count"]
    activity_log.reset()
    activity_log.emit(
        f"Generation accepted with {provider_id}:{model_name}",
        source="server",
    )
    if queued_guidance:
        activity_log.emit(f"Loaded {queued_guidance} queued user guidance message(s).", kind="guidance", source="user")
    state_manager.update_state(
        status=GenerationStatus.STARTING,
        current_step="Starting generation...",
        progress=0,
        output_format=output_format,
    )
    try:
        thread = threading.Thread(
            target=_generate_book,
            args=(generation_request, model),
            daemon=True,
        )
        thread.start()
    except Exception:
        guidance_manager.finish_generation()
        _generation_lock.release()
        raise
    return jsonify({"status": "started", "outputFormat": output_format, "language": language}), 202


def _generate_book(generation_request: BookGenerationRequest, model: str) -> None:
    global _latest_output
    try:
        activity_log.emit(f"Configuring model: {model}", source="pipeline")
        state_manager.update_state(
            status=GenerationStatus.CONFIGURING_MODEL,
            current_step=f"Configuring model: {model or 'environment default'}",
            progress=2,
        )
        if model:
            update_model_name(model)
            provider = model.split(":", 1)[0] if ":" in model else "ollama"
            os.environ["MODEL_TYPE"] = provider
        state_manager.update_state(
            status=GenerationStatus.GENERATING_STRUCTURE,
            current_step="Generating structure...",
            progress=4,
        )

        phase = {"ideas": False, "writing": False, "saving": False}

        def progress(message: str, value: int, data: dict) -> None:
            activity_log.emit(f"[{value}%] {message}", source="pipeline")
            updates = {"current_step": message, "progress": value}
            if data.get("title"):
                updates["title"] = data["title"]
            if data.get("chapter_count"):
                updates["chapter_count"] = data["chapter_count"]
                if data.get("current_chapter"):
                    updates["current_chapter"] = data["current_chapter"]
            if data.get("project_path"):
                updates["project_path"] = data["project_path"]

            if value >= 20 and not phase["ideas"]:
                state_manager.update_state(status=GenerationStatus.STRUCTURE_COMPLETE, **updates)
                state_manager.update_state(status=GenerationStatus.GENERATING_IDEAS, **updates)
                phase["ideas"] = True
            elif value >= 45 and not phase["writing"]:
                state_manager.update_state(status=GenerationStatus.IDEAS_COMPLETE, **updates)
                state_manager.update_state(status=GenerationStatus.WRITING_BOOK, **updates)
                phase["writing"] = True
            elif value >= 90 and not phase["saving"]:
                state_manager.update_state(status=GenerationStatus.WRITING_COMPLETE, **updates)
                state_manager.update_state(status=GenerationStatus.SAVING_DOCUMENT, **updates)
                phase["saving"] = True
            else:
                state_manager.update_state(**updates)

        result = BookGenerationPipeline(progress).run(generation_request)
        _latest_output = result.output_path.resolve()
        state_manager.update_state(
            status=GenerationStatus.COMPLETE,
            title=result.title,
            current_step=f"Complete. Project: {result.project_path.name}",
            progress=100,
            book_ready=True,
            file_path="download",
            project_path=str(result.project_path),
        )
        activity_log.emit(
            f"Generation complete. Published {result.output_path.name} inside project {result.project_path.name}",
            kind="success",
            source="pipeline",
        )
    except GenerationCancelled as error:
        current = state_manager.get_state()
        state_manager.update_state(
            status=GenerationStatus.CANCELLED,
            current_step="Generation cancelled. The project keeps its completed checkpoints.",
            progress=current.progress,
            paused=False,
            cancel_requested=True,
            error=None,
        )
        activity_log.emit(str(error), kind="warning", source="pipeline")
    except Exception as error:
        current = state_manager.get_state()
        state_manager.update_state(
            status=GenerationStatus.ERROR,
            current_step=f"Generation failed: {error}",
            progress=current.progress,
            error=str(error),
        )
        activity_log.emit(f"Generation failed: {error}", kind="error", source="pipeline")
    finally:
        guidance_manager.finish_generation()
        _generation_lock.release()


@app.get("/download")
def download():
    if not _latest_output or not _latest_output.is_file():
        return jsonify({"error": "No generated file is available"}), 404
    return send_file(_latest_output, as_attachment=True, download_name=_latest_output.name)


@socketio.on("connect")
def handle_connect():
    socketio.emit("status_update", state_manager.get_state().to_dict())


if __name__ == "__main__":
    startup_output = Path(config.generation.output_directory).expanduser()
    if not startup_output.is_absolute():
        startup_output = ROOT / startup_output
    startup_output.mkdir(parents=True, exist_ok=True)
    debug = os.getenv("WEB_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    socketio.run(
        app,
        host=os.getenv("WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_PORT", "5000")),
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
