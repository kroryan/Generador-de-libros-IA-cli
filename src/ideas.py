"""Generate detailed chapter briefs and ordered section plans."""

import re

from language import language_instruction, normalize_language
from utils import BaseEventChain, clean_think_tags, extract_content_from_llm_response, print_progress


class ChapterFrameworkChain(BaseEventChain):
    PROMPT_TEMPLATE = """
Act as a developmental editor. Create a compact but specific brief for the current chapter.
Cover its function, opening question or state, causal events or argument/evidence progression,
people and concepts involved, conflict or debate, key claim/reveal, closing synthesis or state,
continuity and source obligations, and setup for later chapters. For nonfiction, identify
claims requiring verification and never fabricate evidence or citations. Do not draft prose.
{language_instruction}

Book title: {title}
Subject: {subject}
Genre: {genre}
Style: {style}
Reader/profile brief: {profile}
Position: {chapter_num} of {total_chapters}
Current chapter: {chapter}
Outline description: {description}

Book framework:
{framework}

Full outline:
{outline}

Previous chapter briefs:
{previous_briefs}

Chapter brief:
"""

    def run(
        self, subject, genre, style, profile, title, framework, summaries_dict,
        chapter_dict, chapter, chapter_num, total_chapters, language="en"
    ):
        print_progress(f"Planning chapter {chapter_num}/{total_chapters}: {chapter}")
        outline = "\n".join(f"- {name}: {desc}" for name, desc in chapter_dict.items())
        previous = "\n\n".join(f"{name}:\n{brief}" for name, brief in summaries_dict.items()) or "None"
        return self.invoke(
            subject=clean_think_tags(str(subject)), genre=clean_think_tags(str(genre)),
            style=clean_think_tags(str(style)), profile=clean_think_tags(str(profile)),
            title=clean_think_tags(str(title)), framework=clean_think_tags(str(framework)),
            chapter=clean_think_tags(str(chapter)), description=clean_think_tags(str(chapter_dict.get(chapter, ""))),
            chapter_num=chapter_num, total_chapters=total_chapters,
            outline=clean_think_tags(outline), previous_briefs=clean_think_tags(previous),
            language_instruction=language_instruction(language),
        )


class IdeasChain(BaseEventChain):
    PROMPT_TEMPLATE = """
Create 3-5 ordered scene or section beats for the current chapter. Fiction beats must advance
plot or character causally. Nonfiction beats must advance chronology, argument, evidence, or
reader understanding and identify factual claims or source needs. State what changes in every
beat. Never invent evidence or citations. Return one concise bullet per beat.
{language_instruction}

Book title: {title}
Genre: {genre}
Style: {style}
Position: {chapter_num} of {total_chapters}
Book framework: {framework}
Chapter brief: {summary}
Previous scene plans: {previous_ideas}

Ordered scene plan:
"""

    def run(
        self, subject, genre, style, profile, title, framework, summary,
        idea_dict, chapter_num, total_chapters, language="en"
    ):
        previous = "\n".join(
            f"{chapter}: " + "; ".join(ideas) for chapter, ideas in idea_dict.items()
        ) or "None"
        result = self.invoke(
            title=clean_think_tags(str(title)), genre=clean_think_tags(str(genre)),
            style=clean_think_tags(str(style)), framework=clean_think_tags(str(framework)),
            summary=clean_think_tags(str(summary)), previous_ideas=clean_think_tags(previous),
            chapter_num=chapter_num, total_chapters=total_chapters,
            language_instruction=language_instruction(language),
        )
        return self.parse(result)

    @staticmethod
    def parse(response):
        if not isinstance(response, str):
            response = extract_content_from_llm_response(response)
        ideas = []
        for line in (response or "").splitlines():
            cleaned = re.sub(r"^\s*(?:[-*+] |\d+[.)]\s*)", "", line).strip()
            if cleaned:
                ideas.append(clean_think_tags(cleaned))
        if not ideas:
            raise ValueError("The model returned an empty section plan")
        return ideas[:5]


def get_ideas(
    subject, genre, style, profile, title, framework, chapter_dict, language="en",
    on_chapter_plan=None,
):
    language = normalize_language(language)
    print_progress("Generating chapter plans...")
    framework_chain = ChapterFrameworkChain()
    ideas_chain = IdeasChain()
    summaries_dict = {}
    idea_dict = {}
    total = len(chapter_dict)
    for index, chapter in enumerate(chapter_dict, 1):
        summary = framework_chain.run(
            subject, genre, style, profile, title, framework, summaries_dict,
            chapter_dict, chapter, index, total, language,
        )
        summaries_dict[chapter] = summary
        idea_dict[chapter] = ideas_chain.run(
            subject, genre, style, profile, title, framework, summary,
            idea_dict, index, total, language,
        )
        if on_chapter_plan:
            on_chapter_plan(chapter, summary, idea_dict[chapter], index, total)
        print_progress(f"Planned {chapter}: {len(idea_dict[chapter])} section beats")
    return summaries_dict, idea_dict
