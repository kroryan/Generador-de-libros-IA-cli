"""Generate the title, narrative framework, and chapter outline."""

import re

from editorial_policy import editorial_policy, is_fiction
from language import get_language, language_instruction, language_quality_issues, normalize_language
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
Create a compact foundation seed appropriate to this book's genre. The six-volume bible will
expand and canonize all details after this step. For fiction, define the premise contract,
reader promise, central tensions, initial character-role requirements, essential world-rule
boundaries, thematic questions, and style boundaries. For nonfiction, define thesis questions,
scope boundaries, evidence classes, reader outcomes, and open research obligations.

Do not plan acts, chapters, scenes, chapter ranges, climax beats, or the ending. Do not provide
a bibliography, recommended sources, citations, quotations, or invented evidence. Do not lock
minor names not explicitly supplied by the user or live guidance, measurements, dates, or lore that belong in the audited bible. Use descriptive
Markdown headings and preserve genuine unknowns as questions.
{language_instruction}

Subject: {subject}
Genre: {genre}
Style: {style}
Title: {title}
Reader/profile brief: {profile}

The selected genre controls factuality: History/Historia requires sourced, qualified factual
claims; Historical fiction/Ficcion historica preserves credible period facts without losing
its freedom to invent story material.

Binding genre policy:
{genre_policy}

Quality correction from a previous attempt:
{quality_feedback}

Book framework:
"""

    def run(self, subject, genre, style, profile, title, language="en"):
        print_progress("Generating narrative framework...")
        feedback = "None; this is the first attempt."
        for _attempt in range(2):
            result = self.invoke(
                subject=clean_think_tags(subject), genre=clean_think_tags(genre),
                style=clean_think_tags(style), profile=clean_think_tags(profile),
                title=clean_think_tags(title), language_instruction=language_instruction(language),
                genre_policy=editorial_policy(genre), quality_feedback=feedback,
            )
            issues = _framework_issues(result, genre, language)
            if not issues:
                return result
            feedback = "Repair every issue and return the complete framework again:\n- " + "\n- ".join(issues)
        raise ValueError("The foundational framework still fixed downstream canon or contained unsupported material after repair")


def _framework_issues(value: str, genre: str, language: str = "") -> list[str]:
    text = str(value)
    issues = []
    if len(re.findall(r"\b\w+\b", text, flags=re.UNICODE)) < 180 or "##" not in text:
        issues.append("The foundation is too short or lacks descriptive level-two Markdown sections.")
    premature_patterns = (
        r"(?i)\b(?:chapters?|cap[ií]tulos?)\s+\d+\s*[-–—]\s*\d+",
        r"(?i)\b(?:act|acto)\s+[ivx\d]+\b",
        r"(?i)\b(?:chapter|cap[ií]tulo)\s+\d+\b",
    )
    if any(re.search(pattern, text) for pattern in premature_patterns):
        issues.append("It prematurely plans acts or numbered chapters; keep only pre-bible foundation constraints.")
    if re.search(r"(?im)^#{1,4}\s+(?:ending|final|resolution|resoluci[oó]n|desenlace)\b", text):
        issues.append("It prematurely fixes the ending; leave story outcomes for the audited architecture volume.")
    if is_fiction(genre) and re.search(
        r"(?i)\b(?:climax|cl[ií]max|resolution|resoluci[oó]n|ending|desenlace)\b",
        text,
    ):
        issues.append("It fixes downstream story architecture; the framework may define tensions but not climax or resolution beats.")
    if is_fiction(genre) and re.search(
        r"(?im)^#{1,4}\s+.*(?:main characters?|personajes principales|timeline|l[ií]nea de tiempo|"
        r"technology ledger|registro de tecnolog|ledger of laws?|registro de leyes|history of|historia de)",
        text,
    ):
        issues.append("It canonizes named cast or encyclopedia material that belongs in the audited bible volumes.")
    role_section = re.search(
        r"(?ims)^#{1,4}(?=[^\n]*(?:roles?|role))(?=[^\n]*(?:personaj|character))[^\n]*\n"
        r"(.*?)(?=^#{1,4}\s|\Z)",
        text,
    )
    named_role_rows = re.findall(
        r"(?im)^\|\s*\*\*[^|*]+\*\*[^|]*\|\s*(?:protagonist|protagonista|captain|capit[aá]n|"
        r"alchemist|alquimista|engineer|ingenier[oa]|antagonist|antagonista|enemy|enemig[oa]|leader|l[ií]der)",
        role_section.group(1) if role_section else "",
    )
    if is_fiction(genre) and len(named_role_rows) > 1:
        issues.append(
            "Role requirements may preserve a user-supplied protagonist name, but must not invent a named cast; "
            "the people/relationships bible volume owns secondary names and biographies."
        )
    if is_fiction(genre) and len(re.findall(
        r"(?i)\b\d+(?:[.,]\d+)?\s*(?:km|cm|kg|kelvin|°c|tw|gw|mw|kw|urc|years?|a[nñ]os?)\b",
        text,
    )) >= 2:
        issues.append("It locks clusters of arbitrary measurements before the world/domain bible is audited.")
    if is_fiction(genre) and re.search(
        r"(?i)\b(?:bibliograf[ií]a|fuentes? recomendadas?|recommended sources?|academic sources?|"
        r"fuentes acad[eé]micas|reference list)\b", text,
    ):
        issues.append("Fiction must not contain real-world source recommendations or claims of academic support.")
    if language:
        issues.extend(language_quality_issues(text, language))
    return issues


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
