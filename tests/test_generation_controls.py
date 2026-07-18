"""Regression tests for prompt construction and generation control."""

import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_community.llms.fake import FakeListLLM

from generation_control import GenerationCancelled, GenerationControl
from writing import WriterChain
from book_bible import _chunk_source_context
from obsidian_vault import ObsidianVaultWriter
from vault_context import IncrementalVaultContextBuilder
from editorial_policy import editorial_policy, is_documentary_history, is_historical_fiction
from guidance import GuidanceManager
from novelist_agent import NovelistAgent
from web_research import read_public_page, search_duckduckgo


def test_writer_chain_compiles_selected_template_before_base_init():
    with patch("utils.get_llm_model", return_value=FakeListLLM(responses=["Narrative prose with a concrete consequence."])):
        writer = WriterChain(use_few_shot=False)
    assert "CANONICAL BOOK BIBLE" in writer.prompt.template
    assert writer.prompt.template.strip()


def test_writer_rejects_short_assistant_chatter():
    assert WriterChain._looks_like_assistant_chatter("Hello! How can I assist you today?")
    assert not WriterChain._looks_like_assistant_chatter("Mara crossed the threshold and the archive sealed behind her.")


def test_pause_blocks_checkpoint_until_resume():
    control = GenerationControl()
    entered = threading.Event()
    finished = threading.Event()
    control.pause()

    def worker():
        entered.set()
        control.checkpoint()
        finished.set()

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(0.2)
    time.sleep(0.03)
    assert not finished.is_set()
    control.resume()
    thread.join(timeout=1)
    assert finished.is_set()


def test_cancel_raises_at_checkpoint():
    control = GenerationControl()
    control.cancel()
    with pytest.raises(GenerationCancelled):
        control.checkpoint()


def test_live_guidance_moves_from_queue_to_project_log():
    manager = GuidanceManager()
    queued = manager.add("Preserve the disputed date as uncertain.")
    assert not queued["active_generation"]
    assert manager.snapshot()["pending_count"] == 1
    manager.start_generation()
    with tempfile.TemporaryDirectory() as temporary:
        manager.attach_project(Path(temporary))
        manager.add("Add the newly verified archive reference.")
        context = manager.context()
        assert "disputed date" in context
        assert "archive reference" in context
        log = Path(temporary) / ".bookgen" / "guidance.jsonl"
        assert len(log.read_text(encoding="utf-8").splitlines()) == 2
    manager.finish_generation()
    assert not manager.snapshot()["active_generation"]


def test_history_and_historical_fiction_have_distinct_policies():
    assert is_documentary_history("Historia")
    assert not is_documentary_history("Ficcion historica")
    assert is_historical_fiction("Historical fiction")
    assert "Corroborate" in editorial_policy("History")
    assert "Story quality remains primary" in editorial_policy("Historical fiction")


def test_duckduckgo_search_parses_real_source_metadata_without_network():
    html = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Farchive">Archive record</a>
    <a class="result__snippet">A primary-source catalogue entry.</a>
    """
    response = type("Response", (), {"text": html, "raise_for_status": lambda self: None})()
    with patch("web_research.requests.get", return_value=response) as request_mock:
        results = search_duckduckgo("documented event", 3)
    assert results == [{
        "title": "Archive record", "url": "https://example.org/archive",
        "snippet": "A primary-source catalogue entry.",
    }]
    assert request_mock.call_args.kwargs["params"] == {"q": "documented event"}


def test_author_agent_exposes_web_tool_only_when_enabled():
    with tempfile.TemporaryDirectory() as temporary:
        project = ObsidianVaultWriter().create(
            temporary, "Research Book", "en", {}, "Framework", book_bible="Canon."
        )
        disabled = NovelistAgent(project, object(), genre="History", web_search_enabled=False)
        enabled = NovelistAgent(project, object(), genre="History", web_search_enabled=True)
        disabled_names = {item["function"]["name"] for item in disabled.tool_schemas}
        enabled_names = {item["function"]["name"] for item in enabled.tool_schemas}
        assert "search_web" not in disabled_names
        assert "read_web_page" not in disabled_names
        assert "record_research_source" not in disabled_names
        assert "search_web" in enabled_names
        assert "read_web_page" in enabled_names
        result = enabled.tools.record_research_source(
            "Archive record", "https://example.org/archive", "The event date", "Primary catalogue lead"
        )
        assert "Recorded source" in result
        ledger = enabled.project.root / enabled.project.read_manifest()["paths"]["research"] / "Web Sources.md"
        assert "https://example.org/archive" in ledger.read_text(encoding="utf-8")


def test_web_page_reader_blocks_private_addresses_before_request():
    with pytest.raises(ValueError, match="Local web addresses"):
        read_public_page("http://localhost/private")


def test_source_context_chunking_preserves_all_markdown_sections():
    source = "\n\n".join(
        f"## Chapter {index}\n\nMARKER-{index} " + ("detail " * 300)
        for index in range(1, 13)
    )
    chunks = _chunk_source_context(source, target_chars=6000, max_chunks=5)
    joined = "\n".join(chunks)
    assert 1 < len(chunks) <= 5
    for index in range(1, 13):
        assert f"MARKER-{index}" in joined


def test_incremental_vault_index_only_resummarizes_changed_files():
    with tempfile.TemporaryDirectory() as temporary:
        project = ObsidianVaultWriter().create(
            temporary, "Indexed Book", "en", {}, "Framework", book_bible="Canon."
        )

        def summarize(records, _language):
            return {item["path"]: f"Summary for {item['path']}" for item in records}

        with patch("vault_context.SourceFileBatchChain.run", side_effect=summarize), patch(
            "vault_context.SourceVaultDigestChain.run", return_value="## Canonical dossier\nDetailed reusable canon."
        ), patch("vault_context.SourceIntentChain.run", return_value="## Operational brief\nApply the request."):
            _, first = IncrementalVaultContextBuilder().build(project, "revise", "indexed-book", "Edit", "en")
        assert first["strategy"] == "full-rebuild"

        status_path = project.root / f"{project.read_manifest()['paths']['status']}.md"
        status_path.write_text(status_path.read_text(encoding="utf-8") + "\nNew context fact.\n", encoding="utf-8")
        seen = []

        def summarize_delta(records, _language):
            seen.extend(item["path"] for item in records)
            return {item["path"]: f"Updated summary for {item['path']}" for item in records}

        with patch("vault_context.SourceFileBatchChain.run", side_effect=summarize_delta), patch(
            "vault_context.SourceVaultDigestChain.run"
        ) as full_rebuild, patch(
            "vault_context.SourceDossierUpdateChain.run", return_value="## Updated dossier\nPreserved canon plus the delta."
        ), patch("vault_context.SourceIntentChain.run", return_value="## Operational brief\nApply the request."):
            _, second = IncrementalVaultContextBuilder().build(project, "revise", "indexed-book", "Edit", "en")
        assert second["strategy"] == "incremental-update"
        assert seen == [status_path.relative_to(project.root).as_posix()]
        full_rebuild.assert_not_called()
