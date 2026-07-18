"""Generate a deep pre-planning bible and structured wiki entity corpus."""

from __future__ import annotations

import json
import os
import re

from language import language_instruction, normalize_language
from utils import BaseStructureChain, clean_think_tags, print_progress


BIBLE_VOLUMES = (
    (
        "Creative and editorial foundation",
        "Premise or thesis; short and complete synopsis; reader promise; genre and audience; themes; "
        "tone; structural rules; hard boundaries; central dramatic, historical, or explanatory question; "
        "scope, evidence standard, and research obligations when nonfiction.",
    ),
    (
        "People, actors, and relationships",
        "For fiction: main, opposing, and supporting cast, goals, wounds, voices, histories, secrets, "
        "knowledge states, relationships, and arcs. For nonfiction: relevant historical people, witnesses, "
        "experts, institutions, schools of thought, roles, documented positions, disputes, and evidentiary limits. "
        "Use stable unique names and never invent biography presented as fact.",
    ),
    (
        "World and domain encyclopedia",
        "Geography or subject domain; locations; territories; cultures; society; politics; economics; religions and myths; "
        "history; technology; magic or powers with costs and limits; nature; everyday life; travel and time. "
        "For nonfiction distinguish documented fact, interpretation, and open research. State concrete rules and "
        "sensory or operational details rather than generic possibilities.",
    ),
    (
        "Content and story architecture",
        "For fiction: plot, subplots, conflicts, mysteries, revelations, reversals, arcs, chronology, ending, and "
        "consequences. For nonfiction: thesis, subclaims, causal and chronological structure, evidence progression, "
        "case studies, counterarguments, controversies, synthesis, implications, and conclusion. Do not create chapter numbers yet.",
    ),
    (
        "Organizations, objects, and concepts",
        "Governments; factions; companies; orders; clandestine groups; important objects; weapons; artifacts; "
        "documents; vehicles; substances; terminology; source types; historical events. Define resources, constraints, "
        "relationships, ownership, public versions, and hidden truths.",
    ),
    (
        "Continuity and writing control",
        "Continuity laws; secret-information matrix; who knows and believes what; character states; calendar; "
        "open questions with proposed resolutions; contradiction risks; style guide; authorial voice; diction; "
        "research questions; source-ledger requirements; fact-checking status; revision checks; motifs and forbidden shortcuts.",
    ),
)


WIKI_DOMAINS = {
    "characters": "8-16 relevant fictional characters, historical people, experts, witnesses, thinkers, or institutional actors",
    "locations": "8-16 concrete locations, regions, nations, settlements, buildings or other places",
    "organizations": "4-10 governments, factions, families, companies, orders, religions or clandestine groups",
    "objects": "5-12 important objects, weapons, artifacts, documents, vehicles or substances",
    "concepts": "5-12 named systems, terminology, customs, technologies, powers, laws or abstract concepts",
    "events": "6-14 historical, conceptual, or planned events that materially shape the book",
}


class SourceChunkDigestChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
You are mapping chunk {chunk_index} of {chunk_total} from an existing Obsidian book vault.
Extract every useful fact present in this chunk for a later synthesis. Do not assume another
chunk will preserve it. Distinguish source fact from editorial inference.
{language_instruction}

Workflow mode: {mode}
Binding user request: {user_request}

Use dense Markdown sections for facts, characters and states, chronology, continuity,
voice/prose evidence, chapter-specific observations, and editing implications. Do not
invent details absent from this chunk. Preserve exact names and consequential specifics.

Source chunk:
{source_chunk}

Canonical names and continuity observations from the immediately preceding map. Use this
only to keep naming stable and flag contradictions; the current source chunk remains the evidence:
{prior_map}

Quality correction from a previous attempt:
{quality_feedback}
"""

    def run(self, mode, user_request, source_chunk, chunk_index, chunk_total, language, prior_map="None; this is the first map."):
        feedback = "None; this is the first attempt."
        for _attempt in range(2):
            result = self.invoke(
                mode=mode, user_request=clean_think_tags(user_request),
                source_chunk=clean_think_tags(source_chunk), chunk_index=chunk_index, chunk_total=chunk_total,
                prior_map=clean_think_tags(prior_map)[-5000:],
                language_instruction=language_instruction(language), quality_feedback=feedback,
            )
            words = len(re.findall(r"\b\w+\b", result, flags=re.UNICODE))
            if words >= 180 and "##" in result:
                return result
            feedback = (
                f"The previous map had only {words} words or no sections. Extract more concrete facts from this chunk."
            )
        raise ValueError(f"Source-vault chunk {chunk_index} remained too short after repair")


class SourceDigestSynthesisChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Synthesize the complete mapped source vault into one canonical context dossier for a
professional author/editor agent. Every map covers a different part of the source.
Preserve details across all maps, reconcile repetition without silently resolving genuine
contradictions, and clearly label uncertainty.
{language_instruction}

Workflow mode: {mode}
Binding user request: {user_request}

The dossier must include: immutable canon and world rules; character/relationship/knowledge
states; chronology; resolved and unresolved arcs; secrets and promises; chapter/manuscript
map; POV, tense, voice and prose evidence; continuity risks; and a prioritized editing or
continuation contract mapping every user instruction to concrete action. Target at least
1200 useful words. Use ## and ### Markdown sections.

Chunk maps:
{chunk_maps}

Quality correction from a previous attempt:
{quality_feedback}
"""

    def run(self, mode, user_request, chunk_maps, language):
        feedback = "None; this is the first attempt."
        for _attempt in range(2):
            result = self.invoke(
                mode=mode, user_request=clean_think_tags(user_request),
                chunk_maps=clean_think_tags(chunk_maps), language_instruction=language_instruction(language),
                quality_feedback=feedback,
            )
            words = len(re.findall(r"\b\w+\b", result, flags=re.UNICODE))
            if words >= 500 and "##" in result:
                return result
            feedback = f"The synthesis had only {words} words or lacked sections. Integrate every map in a detailed dossier."
        raise ValueError("The source-vault synthesis remained too short after repair")


class SourceVaultDigestChain:
    def run(self, mode: str, user_request: str, source_context: str, language: str, on_chunk=None) -> str:
        chunks = _chunk_source_context(
            source_context,
            int(os.getenv("SOURCE_DIGEST_CHUNK_CHARS", "14000")),
            int(os.getenv("SOURCE_DIGEST_MAX_CHUNKS", "8")),
        )
        maps = []
        for index, chunk in enumerate(chunks, 1):
            mapped = SourceChunkDigestChain().run(
                mode, user_request, chunk, index, len(chunks), language,
                maps[-1] if maps else "None; this is the first map.",
            )
            maps.append(mapped)
            if on_chunk:
                on_chunk(index, len(chunks), mapped)
        joined = "\n\n".join(f"# Source map {index}\n\n{body}" for index, body in enumerate(maps, 1))
        return SourceDigestSynthesisChain().run(mode, user_request, joined, language)


class BibleVolumeChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
You are the lead book architect creating one volume of a canonical book bible before
chapters are planned. Write dense, specific, internally consistent Markdown. This is an
operational reference for another author agent, not a pitch or a brief summary.

Volume: {volume_name}
Required coverage: {requirements}
Target at least {target_words} useful words when the premise supports them. Prefer explicit
facts, tables, ledgers, constraints, examples, causal explanations, and named details.
Resolve ambiguity instead of offering alternatives, except where nonfiction evidence is
genuinely disputed; then preserve and label competing interpretations. History/Historia must
separate verified facts, source leads, inference, and open verification. Historical fiction
may invent narrative material while preserving relevant period context. Do not plan numbered
chapters or write finished book prose. Do not emit Obsidian wikilinks; application code creates only links
whose target notes exist.
{language_instruction}

Title: {title}
Premise: {subject}
Genre: {genre}
Style: {style}
Reader and constraints brief: {profile}

Foundational framework:
{framework}

Previously established canon (obey it and add detail without contradiction):
{prior_canon}

Quality correction from a previous attempt:
{quality_feedback}

Return this volume with descriptive level-two and level-three Markdown headings.
"""

    def run(self, volume_name, requirements, subject, genre, style, profile, title, framework, prior_canon, language):
        minimum = int(os.getenv("BIBLE_VOLUME_MIN_WORDS", "500"))
        best = ""
        feedback = "None; this is the first attempt."
        for _attempt in range(2):
            best = self.invoke(
                volume_name=volume_name, requirements=requirements,
                target_words=os.getenv("BIBLE_VOLUME_TARGET_WORDS", "1400"),
                language_instruction=language_instruction(language),
                subject=clean_think_tags(str(subject)), genre=clean_think_tags(str(genre)),
                style=clean_think_tags(str(style)), profile=clean_think_tags(str(profile)),
                title=clean_think_tags(str(title)), framework=clean_think_tags(str(framework)),
                prior_canon=clean_think_tags(prior_canon or "No earlier volume; establish the canon now."),
                quality_feedback=feedback,
            )
            word_count = len(re.findall(r"\b\w+\b", best, flags=re.UNICODE))
            if word_count >= minimum and "##" in best:
                return best
            feedback = (
                f"The previous response had only {word_count} words or lacked Markdown sections. "
                f"Expand it beyond {minimum} useful words with concrete facts and ## headings; do not apologize."
            )
        raise ValueError(f"Bible volume '{volume_name}' remained too short or unstructured after repair")


class BookBibleChain:
    def run(self, subject, genre, style, profile, title, framework, language="en", on_volume=None):
        language = normalize_language(language)
        print_progress("Generating the multi-volume canonical book bible...")
        volumes: list[tuple[str, str]] = []
        prior_limit = int(os.getenv("BIBLE_PRIOR_CONTEXT_CHARS", "24000"))
        for index, (name, requirements) in enumerate(BIBLE_VOLUMES, 1):
            prior = _balanced_volume_context(volumes, prior_limit)
            body = BibleVolumeChain().run(
                name, requirements, subject, genre, style, profile, title, framework,
                prior, language,
            )
            volumes.append((name, body))
            if on_volume:
                on_volume(index, len(BIBLE_VOLUMES), name, body, volumes)
        return "\n\n".join(
            [f"# {title} - Canonical Book Bible"]
            + [f"# Volume {index}: {name}\n\n{body}" for index, (name, body) in enumerate(volumes, 1)]
        ).strip()


class WikiDomainChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
Extract and expand the {domain} required by this canonical book bible. Return valid JSON
only, with no Markdown fence, using this shape:
{{"items":[{{"name":"unique natural name","aliases":["known alternate name"],"subtype":"specific category","summary":"2-4 sentence summary","
details":"substantial Markdown with ## sections and concrete canonical detail","relationships":["exact canonical entity name"]}}]}}

Create {quantity}. Include only useful named entities grounded in or necessarily implied by
the canon. Details must cover narrative function, history, present state, rules or limits,
continuity facts, secrets when relevant, and sensory or behavioral specifics. Do not use
Obsidian wikilinks or empty placeholders. Relationship names must be exact natural names;
application code will keep only targets that receive real notes.
Never create a second entity for a concept already present in the canonical entity catalog.
Reuse its exact canonical name and put alternate terminology in aliases. A related aspect,
rule, title, or former name is not a separate entity unless the bible clearly treats it as one.
{language_instruction}

Canonical entity catalog already accepted from earlier domains:
{entity_catalog}

Quality correction from a previous attempt:
{quality_feedback}

Canonical bible:
{book_bible}
"""

    def run(self, domain: str, quantity: str, book_bible: str, language: str, entity_catalog: str = "None yet.") -> list[dict]:
        feedback = "None; this is the first attempt."
        for _attempt in range(2):
            raw = self.invoke(
                domain=domain, quantity=quantity, language_instruction=language_instruction(language),
                book_bible=clean_think_tags(book_bible), entity_catalog=clean_think_tags(entity_catalog),
                quality_feedback=feedback,
            )
            result = self._parse(raw, domain)
            if result:
                return result
            feedback = "The previous response was invalid JSON or had no usable items. Return only the required JSON object."
        raise ValueError(f"Wiki domain '{domain}' remained invalid after JSON repair")

    @staticmethod
    def _parse(raw: str, domain: str) -> list[dict]:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except (TypeError, json.JSONDecodeError):
            return []
        result = []
        for item in payload.get("items", []):
            if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                continue
            result.append({
                "name": str(item["name"]).strip(),
                "aliases": [str(value).strip() for value in item.get("aliases", []) if str(value).strip()],
                "subtype": str(item.get("subtype", domain.rstrip("s"))).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "details": str(item.get("details", "")).strip(),
                "relationships": [str(value).strip() for value in item.get("relationships", []) if str(value).strip()],
            })
        return result


class WikiDataChain:
    def run(self, book_bible, language="en", on_domain=None):
        language = normalize_language(language)
        result = {}
        context_limit = int(os.getenv("WIKI_BIBLE_CONTEXT_CHARS", "50000"))
        context = _balanced_text_context(str(book_bible), context_limit)
        for index, (domain, quantity) in enumerate(WIKI_DOMAINS.items(), 1):
            catalog = _entity_catalog(result)
            generated = WikiDomainChain().run(domain, quantity, context, language, catalog)
            result[domain] = _merge_domain_entities(generated, result)
            if on_domain:
                on_domain(index, len(WIKI_DOMAINS), domain, result[domain], result)
        return result


def _entity_key(value: str) -> str:
    return re.sub(r"[^\w]+", "", str(value), flags=re.UNICODE).casefold()


def _chunk_source_context(text: str, target_chars: int, max_chunks: int) -> list[str]:
    """Adapt to Markdown boundaries and preserve coverage across the whole source."""
    text = str(text).strip()
    if not text:
        return ["No source text was available."]
    target_chars = max(6000, target_chars)
    max_chunks = max(1, max_chunks)
    desired_chunks = min(max_chunks, max(1, (len(text) + target_chars - 1) // target_chars))
    adaptive_budget = max(6000, (len(text) + desired_chunks - 1) // desired_chunks)

    sections = [
        section.strip() for section in re.split(r"(?m)(?=^#{1,3}\s+\S)", text)
        if section.strip()
    ] or [text]
    units: list[str] = []
    overlap = int(os.getenv("SOURCE_DIGEST_OVERLAP_CHARS", "350"))
    for section in sections:
        if len(section) <= adaptive_budget:
            units.append(section)
            continue
        heading = section.splitlines()[0] if section.startswith("#") else "Oversized source section"
        body = section[len(heading):].lstrip()
        cursor = 0
        part = 1
        while cursor < len(body):
            end = min(len(body), cursor + adaptive_budget - len(heading) - 40)
            if end < len(body):
                boundary = body.rfind("\n\n", cursor + adaptive_budget // 2, end)
                if boundary > cursor:
                    end = boundary
            units.append(f"{heading}\n\n[Part {part}]\n\n{body[cursor:end].strip()}")
            if end >= len(body):
                break
            cursor = max(cursor + 1, end - overlap)
            part += 1

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for unit in units:
        projected = current_size + len(unit) + 2
        if current and projected > adaptive_budget:
            chunks.append("\n\n".join(current))
            current, current_size = [], 0
        current.append(unit)
        current_size += len(unit) + 2
    if current:
        chunks.append("\n\n".join(current))
    while len(chunks) > max_chunks:
        pair_index = min(
            range(len(chunks) - 1),
            key=lambda index: len(chunks[index]) + len(chunks[index + 1]),
        )
        chunks[pair_index:pair_index + 2] = [chunks[pair_index] + "\n\n" + chunks[pair_index + 1]]
    return chunks


def _balanced_volume_context(volumes: list[tuple[str, str]], limit: int) -> str:
    if not volumes:
        return "No earlier volume; establish the canon now."
    allowance = max(500, limit // len(volumes))
    return "\n\n".join(f"## {name}\n{body[:allowance]}" for name, body in volumes)


def _balanced_text_context(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    sections = [value.strip() for value in re.split(r"(?m)(?=^# Volume \d+:)", text) if value.strip()]
    if len(sections) <= 1:
        return text[:limit]
    allowance = max(500, limit // len(sections))
    return "\n\n".join(section[:allowance] for section in sections)


def _entity_catalog(wiki_data: dict) -> str:
    lines = []
    for domain, items in wiki_data.items():
        for item in items:
            aliases = ", ".join(item.get("aliases", [])) or "none"
            lines.append(f"- {item['name']} ({domain}; aliases: {aliases})")
    return "\n".join(lines) or "None yet."


def _merge_domain_entities(items: list[dict], accepted: dict) -> list[dict]:
    """Merge exact name/alias collisions so one concept owns one Obsidian note."""
    owners: dict[str, dict] = {}
    for existing_items in accepted.values():
        for existing in existing_items:
            for value in [existing.get("name", ""), *existing.get("aliases", [])]:
                if _entity_key(value):
                    owners[_entity_key(value)] = existing

    merged: list[dict] = []
    for item in items:
        keys = {_entity_key(item.get("name", "")), *(_entity_key(alias) for alias in item.get("aliases", []))}
        keys.discard("")
        duplicate = next((owners[key] for key in keys if key in owners), None)
        if duplicate is not None:
            aliases = [*duplicate.get("aliases", []), item.get("name", ""), *item.get("aliases", [])]
            duplicate["aliases"] = list(dict.fromkeys(
                alias for alias in aliases
                if alias and _entity_key(alias) != _entity_key(duplicate.get("name", ""))
            ))
            duplicate["relationships"] = list(dict.fromkeys(
                [*duplicate.get("relationships", []), *item.get("relationships", [])]
            ))
            if item.get("details") and item["details"] not in duplicate.get("details", ""):
                duplicate["details"] = (duplicate.get("details", "").rstrip() + "\n\n" + item["details"].strip()).strip()
            continue
        merged.append(item)
        for key in keys:
            owners[key] = item
    return merged
