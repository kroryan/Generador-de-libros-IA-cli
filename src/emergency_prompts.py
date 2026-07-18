"""Centralized, language-aware fallback prompts."""

import os

from language import language_instruction, normalize_language


class EmergencyPromptGenerator:
    def __init__(self):
        self._templates = {
            "writing_emergency": """
Continue the book with one polished passage that fulfills the current section objective.
Chapter: {chapter_title}
Section objective: {idea_summary}
{language_instruction}
For nonfiction, do not invent facts, quotations, citations, or sources. Return book prose only,
without metadata or commentary.
""",
            "section_regeneration": """
Continue this book naturally and coherently from the available context.
Context: {context_summary}
Recent prose: {previous_content}
{language_instruction}
Return only the next polished passage. Do not introduce unsupported facts.
""",
            "summary_emergency": """
Summarize the essential continuity facts in this content in no more than three sentences.
{language_instruction}
Content: {content}
Continuity summary:
""",
            "fallback_generic": """
Produce appropriate content from this information.
{language_instruction}
Context: {context}
Response:
""",
        }

    def get_emergency_prompt(self, prompt_type: str, language="en", **kwargs) -> str:
        template = self._templates.get(prompt_type, self._templates["fallback_generic"])
        kwargs.setdefault("context", str(kwargs))
        kwargs["language_instruction"] = language_instruction(language)
        try:
            return template.format(**kwargs)
        except KeyError:
            return self._templates["fallback_generic"].format(
                context=str(kwargs), language_instruction=language_instruction(language)
            )

    def register_template(self, name: str, template: str):
        self._templates[name] = template

    def get_available_templates(self) -> list:
        return list(self._templates)

    def get_writing_emergency_prompt(self, chapter_title="", idea="", max_idea_length=100, language="en"):
        language = normalize_language(language)
        fallback = "continuar el contenido del libro" if language == "es" else "continue the book content"
        idea_summary = (idea[:max_idea_length] if idea else fallback) + ("..." if len(idea) > max_idea_length else "")
        return self.get_emergency_prompt(
            "writing_emergency", language=language,
            chapter_title=chapter_title or ("este capitulo" if language == "es" else "this chapter"),
            idea_summary=idea_summary,
        )

    def get_section_regeneration_prompt(self, context_summary="", previous_content="", max_context_length=200, language="en"):
        return self.get_emergency_prompt(
            "section_regeneration", language=language,
            context_summary=(context_summary or "story in progress")[:max_context_length],
            previous_content=(previous_content or "previous content")[-max_context_length:],
        )

    def get_summary_emergency_prompt(self, content="", max_length=300, language="en"):
        return self.get_emergency_prompt(
            "summary_emergency", language=language,
            content=(content or "content unavailable")[:max_length],
        )


emergency_prompts = EmergencyPromptGenerator()


def get_writing_emergency_prompt(chapter_title="", idea="", language="en"):
    return emergency_prompts.get_writing_emergency_prompt(chapter_title, idea, language=language)


def get_section_regeneration_prompt(context="", previous="", language="en"):
    return emergency_prompts.get_section_regeneration_prompt(context, previous, language=language)


def get_summary_emergency_prompt(content="", language="en"):
    return emergency_prompts.get_summary_emergency_prompt(content, language=language)


for key, value in os.environ.items():
    if key.startswith("EMERGENCY_PROMPT_"):
        emergency_prompts.register_template(key[len("EMERGENCY_PROMPT_"):].lower(), value)
