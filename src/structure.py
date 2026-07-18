"""Generate the title, narrative framework, and chapter outline."""

from language import get_language, language_instruction, normalize_language
from utils import (
    BaseStructureChain,
    clean_think_tags,
    extract_content_from_llm_response,
    print_progress,
)


class TitleChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Create an original, memorable title for the requested book. Capture its central promise,
genre, and tone. Return only the title without quotation marks or commentary.
{language_instruction}

Subject: {subject}
Genre: {genre}
Style: {style}
Reader/profile brief: {profile}

Title:
"""

    def run(self, subject, genre, style, profile, language="en"):
        print_progress("Generating title...")
        return self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            profile=clean_think_tags(profile),
            language_instruction=language_instruction(language),
        ).strip().strip('"')


class FrameworkChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Create a specific long-form framework appropriate to this book's genre. For fiction,
define setting rules, characters, motivations, causal plot movement, stakes, and themes.
For nonfiction, define thesis, scope, chronology or conceptual progression, key people and
institutions, evidence standards, competing interpretations, reader outcomes, and source
requirements. Establish only facts later steps may safely treat as canonical; explicitly
mark claims that require research. Do not draft chapters or invent facts, quotations, or sources.
{language_instruction}

Subject: {subject}
Genre: {genre}
Style: {style}
Title: {title}
Reader/profile brief: {profile}

The selected genre controls factuality: History/Historia requires sourced, qualified factual
claims; Historical fiction/Ficcion historica preserves credible period facts without losing
its freedom to invent story material.

Book framework:
"""

    def run(self, subject, genre, style, profile, title, language="en"):
        print_progress("Generating narrative framework...")
        return self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            profile=clean_think_tags(profile),
            title=clean_think_tags(title),
            language_instruction=language_instruction(language),
        )


class ChaptersChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Create a 9-14 entry chapter outline appropriate to the genre. For fiction, use a localized
prologue when useful, numbered chapters, and an epilogue when useful. For nonfiction, use
{introduction_label}, numbered {chapter_label} entries, and {conclusion_label}. Use exactly
one line per entry and exactly this delimiter: " | ". Each description must state how the
story, argument, chronology, evidence, or reader understanding materially advances.
{language_instruction}

Subject: {subject}
Genre: {genre}
Style: {style}
Title: {title}
Reader/profile brief: {profile}
Narrative framework: {framework}
Canonical pre-planning bible and wiki context:
{book_bible}

Chapter outline:
"""

    def run(self, subject, genre, style, profile, title, framework, language="en", book_bible=""):
        print_progress("Generating chapter outline...")
        spec = get_language(language)
        response = self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            title=clean_think_tags(title),
            profile=clean_think_tags(profile),
            framework=clean_think_tags(framework),
            book_bible=clean_think_tags(book_bible or "Use the narrative framework as canon."),
            language_instruction=language_instruction(language),
            prologue_label=spec.prologue,
            chapter_label=spec.chapter,
            epilogue_label=spec.epilogue,
            introduction_label="Introduccion" if spec.code == "es" else "Introduction",
            conclusion_label="Conclusion" if spec.code == "es" else "Conclusion",
        )
        return self.parse(response, language)

    def parse(self, response, language="en"):
        if not isinstance(response, str):
            response = extract_content_from_llm_response(response)
        if not response:
            raise ValueError("The model returned an empty chapter outline")

        chapters = {}
        for raw_line in response.splitlines():
            line = raw_line.strip().lstrip("-*0123456789. ")
            if " | " in line:
                name, description = line.split(" | ", 1)
            elif ":" in line:
                name, description = line.split(":", 1)
            else:
                continue
            if name.strip() and description.strip():
                chapters[name.strip()] = description.strip()
        if chapters:
            return chapters

        spec = get_language(language)
        introduction = "Introduccion" if spec.code == "es" else "Introduction"
        conclusion = "Conclusion"
        fallback = {introduction: "Define the book's central promise, scope, and organizing question."}
        fallback.update(
            {f"{spec.chapter} {index}": f"Advance the story, argument, or evidence through consequential step {index}." for index in range(1, 8)}
        )
        fallback[conclusion] = "Synthesize the central outcome, implications, and remaining questions."
        return fallback


def get_foundation(subject, genre, style, profile, language="en", on_stage=None):
    language = normalize_language(language)
    print_progress("Generating the pre-planning book foundation...")
    title = TitleChain().run(subject, genre, style, profile, language)
    if on_stage:
        on_stage("title", title)
    framework = FrameworkChain().run(subject, genre, style, profile, title, language)
    if on_stage:
        on_stage("framework", framework)
    return title, framework


def get_chapter_outline(subject, genre, style, profile, title, framework, book_bible, language="en"):
    language = normalize_language(language)
    print_progress("Planning chapters from the canonical vault context...")
    chapters = ChaptersChain().run(
        subject, genre, style, profile, title, framework, language, book_bible=book_bible
    )
    print_progress(f"Generated an outline with {len(chapters)} chapters")
    return chapters


def get_structure(subject, genre, style, profile, language="en", on_stage=None):
    """Compatibility helper; the canonical pipeline uses the two pre/post-bible steps."""
    title, framework = get_foundation(subject, genre, style, profile, language, on_stage)
    chapters = get_chapter_outline(
        subject, genre, style, profile, title, framework, framework, language
    )
    if on_stage:
        on_stage("outline", chapters)
    return title, framework, chapters
