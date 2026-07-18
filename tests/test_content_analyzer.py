"""Regression tests for lightweight generated-content analysis."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from content_analyzer import ContentAnalyzer


def test_content_analysis_counts_words_without_name_errors():
    risk, message, analysis = ContentAnalyzer().detect_collapse_risk(
        "A complete sentence with enough content for basic analysis."
    )

    assert risk is False
    assert message
    assert analysis["word_count"] == 9
