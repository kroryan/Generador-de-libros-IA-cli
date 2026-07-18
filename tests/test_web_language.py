"""Static regressions for browser language state and generation payloads."""

from pathlib import Path


HTML = (Path(__file__).parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def test_language_initialization_uses_persisted_or_visually_selected_value():
    assert "function initialLanguage()" in HTML
    assert "persistedLanguage() || (samples[selected] ? selected : 'en')" in HTML
    assert "applyLanguage(initialLanguage());" in HTML
    assert "applyLanguage('en');" not in HTML


def test_generation_payload_uses_the_live_language_selector():
    assert "language: languageSelect.value" in HTML
    assert "language: currentLanguage" not in HTML
    assert "window.localStorage.setItem(languageStorageKey, language)" in HTML
