"""Command-line entry point for the AI book generator."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

load_dotenv()


def configure_model(model: str | None) -> None:
    if not model:
        return
    from utils import parse_model_string, update_model_name

    update_model_name(model)
    provider, _ = parse_model_string(model)
    os.environ["MODEL_TYPE"] = provider


def run_cli_generation(args) -> None:
    from config.defaults import get_config
    from pipeline import BookGenerationPipeline, BookGenerationRequest

    config = get_config().generation
    configure_model(args.model)
    request = BookGenerationRequest(
        subject=args.subject or config.default_subject,
        profile=args.profile or config.default_profile,
        style=args.style or config.default_style,
        genre=args.genre or config.default_genre,
        language=args.language or config.default_language,
        output_format=args.output_format or config.default_output_format,
        output_path=args.output_path or config.output_directory,
        agent_tools=config.agent_tools_enabled and not args.no_agent_tools,
        web_search=args.web_search,
        source_vault_path=args.source_vault or "",
        source_book_id=args.source_book or "",
        vault_mode=args.vault_mode or "new",
    )
    result = BookGenerationPipeline().run(request)
    print(f"\nBook complete: {result.output_path}")
    print(f"Project workspace: {result.project_path}")
    print(f"Obsidian vault: {result.vault_path}")


def list_available_models() -> None:
    from utils import get_available_models

    for model in get_available_models():
        print(f"{model['display_name']}: {model['value']}")


def run_web_interface(model: str | None = None) -> None:
    configure_model(model)
    from server import app, socketio

    print("Web interface: http://localhost:5000/")
    debug = os.getenv("WEB_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    socketio.run(
        app,
        host=os.getenv("WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_PORT", "5000")),
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate coherent books through an Obsidian-first pipeline")
    parser.add_argument("--web", action="store_true", help="Start the web interface")
    parser.add_argument("--model", help="Model as provider:model (for example ollama:gpt-oss:20b-cloud)")
    parser.add_argument("--list-models", action="store_true", help="List configured models")
    parser.add_argument("--language", choices=("en", "es"), help="Book language (default: en)")
    parser.add_argument("--output-format", choices=("obsidian", "md", "txt", "html", "docx", "pdf"))
    parser.add_argument("--output-path", help="Output directory")
    parser.add_argument("--subject", help="Book premise or subject")
    parser.add_argument("--profile", help="Audience, content, voice, evidence, and constraints brief")
    parser.add_argument("--style", help="Writing style")
    parser.add_argument("--genre", help="Genre or book type")
    parser.add_argument("--no-agent-tools", action="store_true", help="Disable autonomous author-agent tool loops")
    parser.add_argument("--web-search", action="store_true", help="Allow the author agent to search the web with DuckDuckGo")
    parser.add_argument("--source-vault", help="Existing BookGen vault used as canonical context")
    parser.add_argument("--source-book", help="Book ID inside --source-vault")
    parser.add_argument("--vault-mode", choices=("new", "continue", "related", "revise"), default="new",
                        help="How to use --source-vault; all modes create a new non-destructive project")
    return parser


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    if arguments.list_models:
        list_available_models()
    elif arguments.web:
        run_web_interface(arguments.model)
    else:
        run_cli_generation(arguments)
