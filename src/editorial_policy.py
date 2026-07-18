"""Genre-sensitive factuality rules shared by planning and agent stages."""

from __future__ import annotations

import re


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def is_documentary_history(genre: str) -> bool:
    return _key(genre) in {"history", "historia"}


def is_historical_fiction(genre: str) -> bool:
    return _key(genre) in {"historical fiction", "ficcion historica", "ficción histórica"}


def editorial_policy(genre: str) -> str:
    if is_documentary_history(genre):
        return (
            "This is documentary history. Treat factual verification, chronology, source provenance, "
            "competing interpretations, and uncertainty as binding requirements. Corroborate consequential "
            "claims and never invent facts, quotations, citations, or sources."
        )
    if is_historical_fiction(genre):
        return (
            "This is historical fiction, not documentary history. Keep the real period, material culture, and "
            "major public facts credible when relevant, while allowing invented characters, scenes, dialogue, "
            "and deliberate deviations identified by the user. Story quality remains primary; do not force "
            "documentary exposition into the narrative."
        )
    return (
        "Apply the conventions and factuality standard appropriate to the selected genre. Nonfiction claims "
        "must be evidence-aware; fiction may invent within its declared canon."
    )
