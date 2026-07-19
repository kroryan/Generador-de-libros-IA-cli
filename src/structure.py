"""Generate the title, narrative framework, and chapter outline."""

import json
import os
import re

from editorial_policy import editorial_policy, is_fiction
from guidance import guidance_manager
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


def _framework_audit_payload(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", str(raw), re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _framework_audit_issue(item: object) -> str:
    if not isinstance(item, dict):
        return str(item)
    problem = str(item.get("problem") or item).strip()
    repair = str(item.get("repair", "")).strip()
    return f"{problem} Required repair: {repair}" if repair else problem


class FrameworkQualityAuditChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Act as an adversarial scope and canon auditor for a compact pre-bible book framework. Compare
the candidate only with the user's explicit premise, reader/profile brief, genre, style, and
live guidance. The generated title is not evidence for additional canon. Do not rewrite the
framework and do not invent facts.

Return valid JSON only:
{{"verdict":"pass or repair","issues":[{{"category":"unsupported canon, scope, character, world, architecture, language, or format","severity":"critical or major","problem":"specific unsupported claim","repair":"specific removal or conversion into an open requirement"}}]}}
Keep keys and verdict tokens in English. Use repair when the candidate assigns a user-supplied
person any occupation, rank, skill, affiliation, biography, knowledge, power, relationship, or
arc direction that the user did not state. Also repair any concrete artifact, discovery answer,
mission event, named law, protocol, mechanism, location, organization, vehicle, measurement,
story outcome, or world fact not explicitly supplied. A high-level tension, boundary, narrative
requirement, or complete open question is allowed when it does not answer itself. Generic role
requirements are allowed, but they must not become characters or settled biographies.
{language_instruction}

Explicit user premise:
{subject}

Reader/profile brief:
{profile}

Genre: {genre}
Style: {style}

Live user guidance already in force:
{guidance}

Candidate framework:
{candidate}
"""

    def run(self, subject, genre, style, profile, guidance, candidate, language) -> dict:
        for _attempt in range(2):
            raw = self.invoke(
                subject=clean_think_tags(str(subject)), genre=clean_think_tags(str(genre)),
                style=clean_think_tags(str(style)), profile=clean_think_tags(str(profile)),
                guidance=clean_think_tags(str(guidance or "No live guidance.")),
                candidate=clean_think_tags(str(candidate)),
                language_instruction=language_instruction(language),
            )
            payload = _framework_audit_payload(raw)
            verdict = str(payload.get("verdict", "")).casefold() if payload else ""
            if payload and verdict in {"pass", "repair"}:
                payload["verdict"] = verdict
                payload["issues"] = payload.get("issues", []) if isinstance(payload.get("issues", []), list) else []
                return payload
        raise ValueError("The framework semantic quality audit returned invalid JSON twice")


class FrameworkChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Create a compact foundation seed appropriate to this book's genre. The six-volume bible will
expand and canonize all details after this step. For fiction, define the premise contract,
reader promise, central tensions, initial character-role requirements, essential world-rule
boundaries, thematic questions, and style boundaries. For nonfiction, define thesis questions,
scope boundaries, evidence classes, reader outcomes, and open research obligations.

Do not plan acts, chapters, scenes, chapter ranges, climax beats, or the ending. Do not provide
a bibliography, recommended sources, citations, quotations, or invented evidence. Do not lock
minor character, place, organization, vehicle, artifact, or system names not explicitly supplied
by the user or live guidance. Do not use placeholder phrases such as TBD, "name to be decided",
"a definir", "a decidir", "sin nombre definido", or "si aplica". Generic role labels need no
placeholder commentary. Preserve genuine unknowns as complete questions without provisional
answers or names. Do not state what the character arc culminates in. Measurements, dates, and lore belong in the audited bible. Use descriptive
level-two Markdown headings. Do not repeat the generated title or add a level-one heading.
Do not assign a named person an occupation, rank, skill, affiliation, biography, special knowledge,
or arc direction unless the user supplied it. Do not convert an unspecified discovery into a
specific artifact, entity, technology, or explanation. World-rule boundaries must state what the
bible needs to decide; they must not name or define laws, protocols, mechanisms, or exact rules.
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

    def run(self, subject, genre, style, profile, title, language="en", on_quality=None):
        print_progress("Generating narrative framework...")
        feedback = "None; this is the first attempt."
        max_repairs = max(1, int(os.getenv("FRAMEWORK_QUALITY_MAX_REPAIRS", "2")))
        max_guidance_replays = max(1, int(os.getenv("FRAMEWORK_GUIDANCE_REPLAYS", "2")))
        max_adaptive_repairs = max(0, int(os.getenv("FRAMEWORK_ADAPTIVE_REPAIRS", "2")))
        guidance_replays = 0
        adaptive_repairs = 0
        encountered_issues = []
        last_issues = []
        previous_issues = None
        attempt = 0
        while attempt <= max_repairs + guidance_replays + adaptive_repairs:
            guidance_before = guidance_manager.context()
            result = self.invoke(
                subject=clean_think_tags(subject), genre=clean_think_tags(genre),
                style=clean_think_tags(style), profile=clean_think_tags(profile),
                title=clean_think_tags(title), language_instruction=language_instruction(language),
                genre_policy=editorial_policy(genre), quality_feedback=feedback,
            )
            guidance_for_audit = guidance_manager.context()
            user_context = "\n".join((str(subject), str(profile), guidance_for_audit))
            deterministic = _framework_issues(
                result,
                genre,
                language,
                user_context=user_context,
            )
            audit = FrameworkQualityAuditChain().run(
                subject, genre, style, profile, guidance_for_audit, result, language,
            )
            audit_issues = [_framework_audit_issue(item) for item in audit.get("issues", [])]
            issues = list(dict.fromkeys([*deterministic, *audit_issues]))
            guidance_after = guidance_manager.context()
            if guidance_after != guidance_before:
                issues.insert(
                    0,
                    "Live user guidance arrived during this model call. Regenerate the complete "
                    "framework using the newest guidance before accepting it.",
                )
                if guidance_replays < max_guidance_replays:
                    guidance_replays += 1
            issue_signature = tuple(issues)
            encountered_issues = list(dict.fromkeys([*encountered_issues, *issues]))
            at_current_limit = attempt >= max_repairs + guidance_replays + adaptive_repairs
            if (
                issues
                and at_current_limit
                and adaptive_repairs < max_adaptive_repairs
                and previous_issues is not None
                and issue_signature != previous_issues
            ):
                adaptive_repairs += 1
            last_issues = issues
            if on_quality:
                on_quality(attempt, {
                    "cycle": attempt,
                    "passed": not issues,
                    "issues": issues,
                    "deterministic_issues": deterministic,
                    "audit": audit,
                    "adaptive_repairs": adaptive_repairs,
                }, result)
            if not issues:
                return result
            feedback = (
                "Repair every issue found in any cycle and return the complete framework again. "
                "Do not reintroduce an earlier defect:\n- " + "\n- ".join(encountered_issues)
            )
            previous_issues = issue_signature
            attempt += 1
        rendered = "; ".join(last_issues) or "quality validation did not pass"
        raise ValueError(f"The foundational framework failed repair: {rendered}")


def _framework_issues(
    value: str,
    genre: str,
    language: str = "",
    user_context: str = "",
) -> list[str]:
    text = str(value)
    issues = []
    if len(re.findall(r"\b\w+\b", text, flags=re.UNICODE)) < 180 or "##" not in text:
        issues.append("The foundation is too short or lacks descriptive level-two Markdown sections.")
    if re.search(r"(?m)^#\s+", text):
        issues.append("Remove the duplicate book title or other level-one heading; the application owns the note title.")
    premature_patterns = (
        r"(?i)\b(?:chapters?|cap[ií]tulos?)\s+\d+\s*[-–—]\s*\d+",
        r"(?i)\b(?:act|acto)\s+[ivx\d]+\b",
        r"(?i)\b(?:chapter|cap[ií]tulo)\s+\d+\b",
    )
    if any(re.search(pattern, text) for pattern in premature_patterns):
        issues.append("It prematurely plans acts or numbered chapters; keep only pre-bible foundation constraints.")
    if re.search(r"(?im)^#{1,4}\s+(?:ending|final|resolution|resoluci[oó]n|desenlace)\b", text):
        issues.append("It prematurely fixes the ending; leave story outcomes for the audited architecture volume.")
    story_architecture_text = re.sub(
        r"(?i)\b(?:sin|without)\s+(?:revelar|se[nñ]alar|detallar|fijar|definir|anticipar|"
        r"reveal(?:ing)?|stat(?:e|ing)|specif(?:y|ying)|fix(?:ing)?|defin(?:e|ing)|detail(?:ing)?)\s+"
        r"(?:el\s+|la\s+|the\s+)?"
        r"(?:desenlace|final|ending|resolution|resoluci[oó]n)\b",
        "",
        text,
    )
    story_architecture_text = re.sub(
        r"(?i)\b(?:sin\s+(?:recurrir|apelar)\s+a|without\s+(?:using\s+|relying\s+on\s+)?)\s*"
        r"(?:predefinid[oa]s?\s+|predefined\s+)?"
        r"(?:(?:estructuras?|structures?|beats?)\s+(?:de|of)\s+)?"
        r"(?:climax|cl[ií]max)(?:\s+(?:predefinid[oa]s?|predefined|structures?|beats?))?\b",
        "",
        story_architecture_text,
    )
    if is_fiction(genre) and re.search(
        r"(?i)\b(?:climax|cl[ií]max|resolution|resoluci[oó]n|ending|desenlace)\b",
        story_architecture_text,
    ):
        issues.append("It fixes downstream story architecture; the framework may define tensions but not climax or resolution beats.")
    if is_fiction(genre) and (
        re.search(
            r"(?is)\barco\s+completo\b.{0,120}\bde(?:l|\s+la)?\b.{1,100}\b(?:a|al|hacia)\b",
            text,
        )
        or re.search(r"(?is)\bcomplete(?:\s+character)?\s+arc\b.{0,120}\bfrom\b.{1,100}\bto\b", text)
    ):
        issues.append("It fixes the protagonist's arc outcome; require a complete arc without deciding its endpoint before story architecture.")
    if is_fiction(genre) and re.search(
        r"(?i)\b(?:culmin(?:a|ando)\s+en\s+(?!(?:un|una)\s+arco\b)|"
        r"culminat(?:e|es|ing)\s+in\s+(?!(?:(?:a|an)\s+)?(?:complete\s+)?arc\b))",
        text,
    ):
        issues.append("It states what the story or character arc culminates in; defer that outcome to the architecture volume.")
    if is_fiction(genre) and re.search(
        r"(?im)^#{1,4}\s+.*(?:main characters?|personajes principales|timeline|l[ií]nea de tiempo|"
        r"technology ledger|registro de tecnolog|ledger of laws?|registro de leyes|history of|historia de)",
        text,
    ):
        issues.append("It canonizes named cast or encyclopedia material that belongs in the audited bible volumes.")
    role_section = re.search(
        r"(?ims)^#{1,4}(?=[^\n]*(?:personaj|character))"
        r"(?=[^\n]*(?:roles?|role|requisitos?|requirements?))[^\n]*\n"
        r"(.*?)(?=^#{1,4}\s|\Z)",
        text,
    )
    named_role_rows = re.findall(
        r"(?im)^\|\s*\*\*([^|*]+)\*\*[^|]*\|",
        role_section.group(1) if role_section else "",
    )
    named_role_rows.extend(re.findall(
        r"(?im)^\s*[-*]\s+\*\*([^*]+)\*\*",
        role_section.group(1) if role_section else "",
    ))
    source = str(user_context).casefold()
    generic_role = re.compile(
        r"(?i)^(?:(?:el|la|los|las|un|una)\s+)?(?:protagonistas?|antagonistas?|mentor(?:a|es|as)?|"
        r"rivales?|aliad[oa]s?|equipos?|tripulaci[oó]n|cient[ií]fic[oa]s?|hechicer[oa]s?|"
        r"magos?|brujas?|navegantes?|mec[aá]nic[oa]s?|guardias?|guardi[aá]n(?:es)?|capit[aá]n(?:es)?|"
        r"ingenier[oa]s?|coordinador(?:a|es|as)?|maestr[oa]s?|explorador(?:a|es|as)?|"
        r"cart[oó]graf[oa]s?|historiador(?:a|es|as)?|gu[ií]as?|s[aá]bi[oa]s?|"
        r"aprendices?|voces?|figuras?|entidades?|especialistas?)(?:\b.*)?$"
    )
    invented_role_names = [
        name.strip()
        for name in named_role_rows
        if name.strip().casefold() not in source and not generic_role.match(name.strip())
    ]
    if is_fiction(genre) and invented_role_names:
        issues.append(
            "Role requirements may preserve names supplied by the user, but must not invent a named cast; "
            "the people/relationships bible volume owns new names and biographies: "
            + ", ".join(dict.fromkeys(invented_role_names))
            + "."
        )
    if re.search(r"\bTODO\b", text) or re.search(
        r"(?i)\b(?:tbd|a\s+(?:decidir|definir|determinar)|por\s+(?:definir|determinar)|"
        r"sin\s+nombre\s+(?:definido|decidido|asignado)|to\s+be\s+(?:decided|defined|determined)|"
        r"name\s+pending|unnamed|without\s+a\s+name|si\s+aplica|if\s+applicable|"
        r"nombres?\b.{0,80}\b(?:se\s+)?mantienen?\s+abiertos?\s+(?:a|al)\s+desarrollo)\b",
        text,
    ):
        issues.append(
            "Replace unresolved placeholder phrases with complete open questions; do not assign provisional names or facts."
        )
    if re.search(
        r"(?is)\b(?:nombres?|names?)\b.{0,220}\b(?:durante\s+la\s+escritura|"
        r"during\s+(?:drafting|writing))\b",
        text,
    ):
        issues.append(
            "Do not defer canonical names until drafting; the audited people and encyclopedia volumes must establish them first."
        )
    if is_fiction(genre):
        invented_entities = []
        entity_kind = (
            r"nave|ship|corporaci[oó]n|corporation|compa[nñ][ií]a|company|orden|order|"
            r"ciudad|city|reliquia|relic|artefacto|artifact|entidad|entity|"
            r"expedici[oó]n|expedition|misi[oó]n|mission|flota|fleet|ley|law|c[oó]digo|code|"
            r"protocolo|protocol|mecanismo|mechanism"
        )
        proper_name = (
            r"[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'’-]*"
            r"(?:\s+(?:(?:de|del|la|los|las|of|the)\s+)?"
            r"[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ'’-]*){0,3}"
        )
        entity_patterns = (
            re.compile(
                rf"\b(?i:{entity_kind})\s+(?:(?i:de)\s+(?:(?i:los|las|la|el)\s+)?)?"
                rf"[*_]{{0,2}}[\"“”'‘’]?({proper_name})[\"“”'‘’]?"
            ),
            re.compile(
                rf"\b(?i:{entity_kind})\b[^\n,]{{0,35}},?\s*(?:(?i:la|el|the)\s+)?"
                rf"[*_]{{1,2}}({proper_name})[*_]{{1,2}}"
            ),
        )
        for pattern in entity_patterns:
            for match in pattern.finditer(text):
                name = match.group(1).strip("*_ ")
                if name.casefold() not in source:
                    invented_entities.append(name)
        if invented_entities:
            issues.append(
                "Do not invent named world entities in the framework; defer these names to the audited bible: "
                + ", ".join(dict.fromkeys(invented_entities))
                + "."
            )
        unsupported_concrete_terms = []
        for label, pattern in (
            ("artifact or relic", r"(?i)\b(?:artefactos?|artifacts?|reliquias?|relics?)\b"),
            ("portal", r"(?i)\b(?:portales?|portals?)\b"),
        ):
            if re.search(pattern, text) and not re.search(pattern, user_context):
                unsupported_concrete_terms.append(label)
        if unsupported_concrete_terms:
            issues.append(
                "The framework turns an unspecified premise into unsupported concrete story/world material: "
                + ", ".join(unsupported_concrete_terms)
                + ". Keep it as an open requirement for the audited bible."
            )
    if is_fiction(genre) and len(re.findall(
        r"(?i)\b\d+(?:[.,]\d+)?\s*(?:km|cm|kg|kelvin|°c|tw|gw|mw|kw|urc|years?|a[nñ]os?)\b",
        text,
    )) >= 2:
        issues.append("It locks clusters of arbitrary measurements before the world/domain bible is audited.")
    if is_fiction(genre) and re.search(r"(?i)\b(?:subnanom[eé]tric[oa]|subnanometric)\b", text):
        issues.append("It asserts unsupported precision before the world/domain bible can justify and audit it.")
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
    def framework_quality(cycle, report, candidate):
        if on_stage:
            on_stage("framework_quality", {
                **report,
                "cycle": cycle,
                "candidate": candidate,
            })

    framework = FrameworkChain().run(
        subject, genre, style, profile, title, language,
        on_quality=framework_quality,
    )
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
