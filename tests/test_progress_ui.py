"""Regressions for the bounded, structured generation activity panel."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "templates" / "app.css").read_text(encoding="utf-8")


def test_activity_panel_has_stable_columns_and_its_own_scroll():
    assert 'class="activity-table"' in HTML
    assert 'id="pipeline-log" class="activity-log"' in HTML
    assert "grid-template-columns: 78px 78px 82px minmax(0, 1fr)" in CSS
    assert "height: clamp(320px, 54vh, 560px)" in CSS
    assert "overflow: auto" in CSS
    assert "overscroll-behavior: contain" in CSS


def test_long_activity_messages_are_collapsible_and_wrapped():
    assert "const longMessage = value.length > 420" in HTML
    assert "document.createElement('details')" in HTML
    assert "body.textContent = value" in HTML
    assert "white-space: pre-wrap" in CSS
    assert "overflow-wrap: anywhere" in CSS


def test_activity_log_is_bounded_and_preserves_manual_scroll_position():
    assert "const shouldFollow = logElement.scrollHeight" in HTML
    assert "while (logElement.children.length > 500)" in HTML
    assert "if (shouldFollow) logElement.scrollTop" in HTML
