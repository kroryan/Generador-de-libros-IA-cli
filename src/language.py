"""Language normalization and prompt instructions for book generation."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSpec:
    code: str
    name: str
    native_name: str
    chapter: str
    prologue: str
    epilogue: str

    @property
    def prompt_instruction(self) -> str:
        return (
            f"Write all reader-facing content exclusively in {self.name}. "
            f"Keep proper nouns consistent and do not translate them between steps. "
            f"The user's input may be in another language; the requested output language is {self.name}."
        )


SUPPORTED_LANGUAGES = {
    "en": LanguageSpec("en", "English", "English", "Chapter", "Prologue", "Epilogue"),
    "es": LanguageSpec("es", "Spanish", "Espanol", "Capitulo", "Prologo", "Epilogo"),
}

_ALIASES = {
    "english": "en",
    "ingles": "en",
    "inglés": "en",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
}


def normalize_language(value: str | None, default: str = "en") -> str:
    normalized = (value or default).strip().lower().replace("_", "-")
    normalized = _ALIASES.get(normalized, normalized.split("-", 1)[0])
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
        raise ValueError(f"Unsupported language '{value}'. Supported languages: {supported}")
    return normalized


def get_language(value: str | None) -> LanguageSpec:
    return SUPPORTED_LANGUAGES[normalize_language(value)]


def language_instruction(value: str | None) -> str:
    return get_language(value).prompt_instruction


def language_quality_issues(text: str, language: str | None) -> list[str]:
    """Catch high-confidence language leakage before relying on an LLM self-audit."""
    code = normalize_language(language)
    value = str(text)
    issues = []
    if code == "es":
        if re.search(
            r"(?i)\b(?:loyalty\s+vs\.?\s+destiny|pacing|central dramatic question|"
            r"reader promise|main characters?|sci[ -]?fantasy|scope)\b",
            value,
        ):
            issues.append("Replace English labels or genre terms with natural Spanish equivalents.")
        if re.search(r"(?i)\bimersi[oó]n\b", value):
            issues.append("Correct the Spanish spelling 'Imersión' to 'Inmersión'.")
        if re.search(r"(?i)\bconflitos?\b", value):
            issues.append("Replace the Portuguese word 'Conflito' with the Spanish 'Conflicto'.")
    elif re.search(
        r"(?i)\b(?:promesa al lector|personajes principales|pregunta dram[aá]tica|"
        r"ritmo narrativo|fantas[ií]a cient[ií]fica)\b",
        value,
    ):
        issues.append("Replace Spanish labels or genre terms with natural English equivalents.")
    return issues
