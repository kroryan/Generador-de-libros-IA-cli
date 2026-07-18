"""Regression tests for background-generation failure diagnostics."""

from pathlib import Path
import sys
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from activity_log import activity_log
from generation_state import GenerationStatus
from pipeline import BookGenerationRequest
import server


def test_background_failure_reports_exception_type_and_traceback(capsys):
    server.state_manager.reset()
    server.state_manager.update_state(
        status=GenerationStatus.STARTING,
        current_step="Starting generation...",
    )
    activity_log.reset()
    assert server._generation_lock.acquire(blocking=False)

    pipeline = server.BookGenerationPipeline()
    pipeline.run = lambda request: (_ for _ in ()).throw(NameError("missing_symbol"))
    request = BookGenerationRequest(
        subject="Diagnostic only",
        profile="Test",
        style="Test",
        genre="Test",
    )

    with patch.object(server, "BookGenerationPipeline", return_value=pipeline):
        server._generate_book(request, "")

    state = server.state_manager.get_state()
    messages = [event["message"] for event in activity_log.snapshot()["events"]]
    assert state.status is GenerationStatus.ERROR
    assert state.error == "NameError: missing_symbol"
    assert any("Generation failed: NameError: missing_symbol" in message for message in messages)
    assert any("Traceback (most recent call last)" in message for message in messages)
    assert "NameError: missing_symbol" in capsys.readouterr().err
    assert server._generation_lock.acquire(blocking=False)
    server._generation_lock.release()
