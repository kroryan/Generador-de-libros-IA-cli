"""Language normalization and prompt instructions for book generation."""

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
