"""Autonomous, bounded author agent with real Obsidian and research tools."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlparse

import requests

from language import language_instruction, normalize_language
from obsidian_vault import VaultProject, _entity_key, _safe_filename
from text_cleaning import clean_think_tags
from generation_control import generation_control
from guidance import guidance_manager
from editorial_policy import editorial_policy, is_documentary_history, is_historical_fiction
from web_research import read_public_page, search_duckduckgo


def _response_text(response) -> str:
    if hasattr(response, "content"):
        return str(response.content)
    if isinstance(response, dict):
        return str(response.get("text") or response.get("content") or "")
    return str(response or "")


class VaultAgentTools:
    """Path-contained Obsidian tools with validated writes and auditable results."""

    def __init__(self, project: VaultProject, result_limit: int = 4000, web_search_enabled: bool = False):
        self.project = project
        self.result_limit = max(500, result_limit)
        self.web_search_enabled = bool(web_search_enabled)

    def _notes(self) -> list[Path]:
        return sorted(self.project.root.rglob("*.md"))

    def _resolve(self, note: str) -> Path | None:
        requested = str(note).strip().replace("\\", "/").removesuffix(".md")
        direct = (self.project.root / f"{requested}.md").resolve()
        try:
            direct.relative_to(self.project.root.resolve())
        except ValueError:
            return None
        if direct.is_file():
            return direct
        matches = [path for path in self._notes() if path.stem.casefold() == Path(requested).name.casefold()]
        return matches[0] if len(matches) == 1 else None

    def search_vault(self, query: str, folder: str = "", limit: int = 5) -> str:
        terms = [term.casefold() for term in re.findall(r"[\w'-]{3,}", str(query))]
        if not terms:
            return "No usable search terms."
        folder_key = str(folder).strip().strip("/").casefold()
        matches = []
        for path in self._notes():
            relative = path.relative_to(self.project.root).as_posix()
            if folder_key and not relative.casefold().startswith(folder_key + "/"):
                continue
            text = path.read_text(encoding="utf-8")
            folded = text.casefold()
            score = sum(folded.count(term) for term in terms)
            if score:
                first = min((folded.find(term) for term in terms if term in folded), default=0)
                snippet = re.sub(r"\s+", " ", text[max(0, first - 120):first + 380]).strip()
                matches.append((score, relative, snippet))
        matches.sort(reverse=True)
        selected = matches[:max(1, min(int(limit), 10))]
        return "\n".join(f"[{path}] {snippet}" for _, path, snippet in selected) or "No matches."

    def read_note(self, note: str) -> str:
        path = self._resolve(note)
        if not path:
            return f"Note not found or ambiguous: {note}"
        text = path.read_text(encoding="utf-8")
        return f"[{path.relative_to(self.project.root)}]\n{text[:self.result_limit]}"

    def backlinks(self, note: str) -> str:
        target = self._resolve(note)
        if not target:
            return f"Note not found or ambiguous: {note}"
        target_stem = target.stem.casefold()
        target_relative = target.relative_to(self.project.root).with_suffix("").as_posix().casefold()
        pattern = re.compile(r"\[\[([^\]|#]+)")
        sources = []
        for path in self._notes():
            links = [
                value.strip().replace("\\", "/").casefold().removesuffix(".md")
                for value in pattern.findall(path.read_text(encoding="utf-8"))
            ]
            if target_stem in links or target_relative in links:
                sources.append(path.relative_to(self.project.root).as_posix())
        return "\n".join(sources) if sources else "No backlinks."

    def list_notes(self, folder: str = "") -> str:
        folder_key = str(folder).strip().strip("/").casefold()
        paths = [
            path.relative_to(self.project.root).as_posix()
            for path in self._notes()
            if not folder_key or path.relative_to(self.project.root).as_posix().casefold().startswith(folder_key + "/")
        ]
        return "\n".join(paths[:100]) or "No notes."

    def chapter_summary(self, chapter: str) -> str:
        entry = self._chapter_entry(chapter)
        if not entry:
            return f"Unknown chapter: {chapter}"
        path = self.project.root / entry["summary_path"]
        return path.read_text(encoding="utf-8")[:self.result_limit] if path.exists() else "Chapter has not been drafted yet."

    def graph_status(self) -> str:
        errors = self.project.validate_links()
        return "Graph valid." if not errors else "\n".join(errors[:20])

    def search_web(self, query: str, limit: int = 5) -> str:
        if not self.web_search_enabled:
            return "Web search is disabled for this generation."
        results = search_duckduckgo(query, limit)
        if not results:
            return "No web results found. Try a more specific query."
        return "\n\n".join(
            f"[{index}] {item['title']}\nURL: {item['url']}\nSnippet: {item['snippet'] or 'No snippet available.'}"
            for index, item in enumerate(results, 1)
        )

    def read_web_page(self, url: str, max_chars: int = 8000) -> str:
        if not self.web_search_enabled:
            return "Web research is disabled for this generation."
        page = read_public_page(url, max_chars)
        return f"Source URL: {page['url']}\n\n{page['content']}"

    def record_research_source(self, title: str, url: str, claim: str, assessment: str) -> str:
        if not self.web_search_enabled:
            return "Web research is disabled for this generation."
        parsed = urlparse(str(url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Research source was not recorded: a valid HTTP(S) URL is required."
        manifest = self.project.read_manifest()
        path = self.project.root / manifest["paths"]["research"] / "Web Sources.md"
        if not path.exists():
            path.write_text("---\ntype: research-source-ledger\n---\n\n# Web Sources\n", encoding="utf-8")
        safe_title = re.sub(r"[\r\n\[\]]+", " ", str(title)).strip()[:200] or parsed.netloc
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {safe_title}\n\n- **URL:** {parsed.geturl()}\n"
                f"- **Claim investigated:** {str(claim).strip()}\n"
                f"- **Assessment:** {str(assessment).strip()}\n"
                f"- **Recorded:** {datetime.now(timezone.utc).isoformat()}\n"
            )
        return f"Recorded source in {path.relative_to(self.project.root)}"

    def read_source_context(self, query: str = "") -> str:
        """Read the selected source manuscript/canon checkpoint in revision workflows."""
        manifest = self.project.read_manifest()
        source_value = str(manifest.get("metadata", {}).get("source_vault_path", "")).strip()
        source_root = Path(source_value).expanduser().resolve() if source_value else None
        if source_root and (source_root / ".bookgen" / "manifest.json").is_file():
            terms = [term.casefold() for term in re.findall(r"[\w'-]{3,}", str(query))]
            matches = []
            for source_note in source_root.rglob("*.md"):
                relative = source_note.relative_to(source_root)
                if any(part in {".bookgen", "Exports"} or part.startswith("90 -") or part.startswith("99 -") for part in relative.parts):
                    continue
                text = source_note.read_text(encoding="utf-8", errors="replace")
                folded = text.casefold()
                score = sum(folded.count(term) for term in terms) if terms else 1
                if score:
                    first = min((folded.find(term) for term in terms if term in folded), default=0)
                    snippet = text[max(0, first - 300):first + 900].strip()
                    matches.append((score, relative.as_posix(), snippet))
            matches.sort(reverse=True)
            if matches:
                return "\n\n".join(f"[source:{path}]\n{snippet}" for _, path, snippet in matches[:5])[:self.result_limit]
        path = self.project.root / ".bookgen" / "checkpoints" / "source-vault-context.md"
        if not path.is_file():
            return "No source vault context is attached to this project."
        text = path.read_text(encoding="utf-8")
        terms = [term.casefold() for term in re.findall(r"[\w'-]{3,}", str(query))]
        if not terms:
            return text[:self.result_limit]
        folded = text.casefold()
        positions = [folded.find(term) for term in terms if term in folded]
        start = max(0, min(positions) - 500) if positions else 0
        return text[start:start + self.result_limit]

    def create_canonical_note(self, category: str, title: str, content: str) -> str:
        manifest = self.project.read_manifest()
        category_map = {
            "core": "core", "story": "story", "character": "characters", "world": "world",
            "organization": "organizations", "object": "objects", "concept": "objects",
            "continuity": "continuity", "research": "research", "writing": "writing",
        }
        key = category_map.get(str(category).strip().casefold())
        if not key:
            return f"Unknown canonical category: {category}"
        directory = self.project.root / manifest["paths"][key]
        directory.mkdir(parents=True, exist_ok=True)
        requested_key = _entity_key(title)
        for entity in manifest.get("entities", []):
            known = [entity.get("name", ""), *entity.get("aliases", [])]
            if any(_entity_key(value) == requested_key for value in known):
                return f"Canonical entity already exists as {entity.get('name')}; edit that note instead."
        path = directory / f"{_safe_filename(title)}.md"
        if path.exists():
            return f"Note already exists; read and edit it instead: {path.relative_to(self.project.root)}"
        path.write_text(
            "---\ntype: canonical-note\nstatus: canonical\n---\n\n"
            f"# {str(title).strip()}\n\n{clean_think_tags(str(content)).strip()}\n",
            encoding="utf-8",
        )
        entity_categories = {
            "character": "characters", "world": "concepts", "organization": "organizations",
            "object": "objects", "concept": "concepts", "story": "events",
        }
        if str(category).strip().casefold() in entity_categories:
            manifest["entities"].append({
                "name": str(title).strip(), "aliases": [],
                "category": entity_categories[str(category).strip().casefold()],
                "subtype": str(category).strip().casefold(),
                "summary": re.sub(r"\s+", " ", str(content)).strip()[:500],
                "relationships": [], "path": path.relative_to(self.project.root).with_suffix("").as_posix(),
            })
            self.project.write_manifest(manifest)
            self.project.refresh_entity_indexes()
        repairs = self.project.repair_and_validate_graph()
        self.record_revision_decision(str(title), "Missing canonical context", f"Created {path.relative_to(self.project.root)}")
        return f"Created {path.relative_to(self.project.root)}; graph repairs: {len(repairs)}"

    def edit_canonical_note(self, note: str, old_text: str, new_text: str, reason: str) -> str:
        manifest = self.project.read_manifest()
        path = self._resolve(note)
        if not path:
            return f"Note not found or ambiguous: {note}"
        relative = path.relative_to(self.project.root)
        allowed_keys = ("core", "story", "characters", "world", "organizations", "objects", "continuity", "research", "writing")
        allowed = any(
            relative.as_posix().casefold().startswith(str(manifest["paths"].get(key, "")).casefold().rstrip("/") + "/")
            for key in allowed_keys
        )
        if not allowed:
            return f"Canonical edit denied for system/manuscript note: {relative}"
        old_text = str(old_text)
        if not old_text.strip():
            return "Edit denied: old_text must be a non-empty exact excerpt."
        text = path.read_text(encoding="utf-8")
        if text.count(old_text) != 1:
            return f"Edit not applied: old_text matched {text.count(old_text)} times."
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup = self.project.root / ".bookgen" / "revisions" / stamp / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        path.write_text(text.replace(old_text, clean_think_tags(str(new_text)), 1), encoding="utf-8")
        repairs = self.project.repair_and_validate_graph()
        self.record_revision_decision(relative.as_posix(), str(reason), "Applied exact canonical edit with backup")
        return f"Patched {relative}; backup: {backup.relative_to(self.project.root)}; graph repairs: {len(repairs)}"

    def record_revision_decision(self, chapter: str, issue: str, resolution: str) -> str:
        manifest = self.project.read_manifest()
        directory = self.project.root / manifest["paths"]["agent_notes"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "Revision Ledger.md"
        if not path.exists():
            path.write_text("---\ntype: revision-ledger\n---\n\n# Revision Ledger\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {_safe_filename(chapter)}\n\n- **Issue:** {str(issue).strip()}\n"
                f"- **Resolution:** {str(resolution).strip()}\n"
            )
        repairs = self.project.repair_and_validate_graph()
        return f"Recorded revision decision for {chapter}; graph repairs: {len(repairs)}"

    def create_agent_note(self, title: str, content: str) -> str:
        directory = self.project.root / self.project.read_manifest()["paths"]["agent_notes"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{_safe_filename(title)}.md"
        path.write_text(
            "---\ntype: agent-note\n---\n\n"
            f"# {str(title).strip()}\n\n{str(content).strip()}\n",
            encoding="utf-8",
        )
        repairs = self.project.repair_and_validate_graph()
        return f"Wrote {path.relative_to(self.project.root)}; graph repairs: {len(repairs)}"

    def append_chapter_continuity(self, chapter: str, fact: str) -> str:
        entry = self._chapter_entry(chapter)
        if not entry:
            return f"Unknown chapter: {chapter}"
        path = self.project.root / entry["plan_path"]
        text = path.read_text(encoding="utf-8").rstrip()
        text += f"\n- {str(fact).strip()}\n"
        path.write_text(text, encoding="utf-8")
        repairs = self.project.repair_and_validate_graph()
        return f"Updated {entry['plan_path']}; graph repairs: {len(repairs)}"

    def append_existing_note(self, note: str, section: str, content: str) -> str:
        path = self._resolve(note)
        if not path:
            return f"Note not found or ambiguous: {note}"
        relative = path.relative_to(self.project.root)
        if not self._is_editable(relative, include_drafts=False):
            return f"Write denied for canonical/system note: {relative}"
        heading = re.sub(r"[^\w\s-]", "", str(section)).strip()[:80] or "Agent update"
        text = path.read_text(encoding="utf-8").rstrip()
        text += f"\n\n## {heading}\n\n{str(content).strip()}\n"
        path.write_text(text, encoding="utf-8")
        repairs = self.project.repair_and_validate_graph()
        return f"Updated {relative}; graph repairs: {len(repairs)}"

    def edit_note(self, note: str, old_text: str, new_text: str) -> str:
        """Apply one exact, local patch like a coding agent's edit tool."""
        path = self._resolve(note)
        if not path:
            return f"Note not found or ambiguous: {note}"
        relative = path.relative_to(self.project.root)
        if not self._is_editable(relative, include_drafts=True):
            return f"Write denied for canonical/system note: {relative}"
        old_text = str(old_text)
        new_text = clean_think_tags(str(new_text))
        if not old_text.strip():
            return "Edit denied: old_text must be a non-empty exact excerpt."
        text = path.read_text(encoding="utf-8")
        occurrences = text.count(old_text)
        if occurrences != 1:
            return f"Edit not applied: old_text matched {occurrences} times; provide a unique exact excerpt."
        path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        repairs = self.project.repair_and_validate_graph()
        return f"Patched {relative}; graph repairs: {len(repairs)}"

    def _is_editable(self, relative: Path, include_drafts: bool) -> bool:
        paths = self.project.read_manifest().get("paths", {})
        keys = ["characters", "world", "organizations", "objects", "story", "plans", "continuity", "agent_notes"]
        if include_drafts:
            keys.extend(["chapters", "summaries"])
        candidate = relative.as_posix().casefold()
        return any(
            candidate == str(paths.get(key, "")).casefold()
            or candidate.startswith(str(paths.get(key, "")).casefold().rstrip("/") + "/")
            for key in keys if paths.get(key)
        )

    def _chapter_entry(self, chapter: str) -> dict | None:
        return next(
            (item for item in self.project.read_manifest()["chapters"] if item["name"].casefold() == str(chapter).casefold()),
            None,
        )

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        generation_control.checkpoint()
        tool = getattr(self, tool_name, None)
        if tool_name.startswith("_") or tool_name not in TOOL_SCHEMAS_BY_NAME or not callable(tool):
            return f"Unknown tool: {tool_name}"
        try:
            return str(tool(**arguments))[:self.result_limit]
        except (TypeError, ValueError, OSError) as error:
            return f"Tool error in {tool_name}: {error}"


def _schema(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


_STRING = {"type": "string"}
TOOL_SCHEMAS = [
    _schema("search_vault", "Full-text search over actual Markdown notes.", {"query": _STRING, "folder": _STRING, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"]),
    _schema("read_note", "Read an existing note by path or unique note name.", {"note": _STRING}, ["note"]),
    _schema("backlinks", "List notes that link to an existing note.", {"note": _STRING}, ["note"]),
    _schema("list_notes", "List real notes, optionally under one folder.", {"folder": _STRING}),
    _schema("chapter_summary", "Read a generated continuity summary for a chapter.", {"chapter": _STRING}, ["chapter"]),
    _schema("graph_status", "Validate all Obsidian wikilinks.", {}),
    _schema("search_web", "Search the public web through DuckDuckGo. Returns source titles, URLs, and snippets; verify important claims across sources.", {"query": _STRING, "limit": {"type": "integer", "minimum": 1, "maximum": 8}}, ["query"]),
    _schema("read_web_page", "Read bounded text from a public HTTP(S) source URL returned by web search. Private and local network addresses are blocked.", {"url": _STRING, "max_chars": {"type": "integer", "minimum": 1000, "maximum": 16000}}, ["url"]),
    _schema("record_research_source", "Persist a consulted web source, investigated claim, and reliability assessment in the Obsidian research ledger.", {"title": _STRING, "url": _STRING, "claim": _STRING, "assessment": _STRING}, ["title", "url", "claim", "assessment"]),
    _schema("read_source_context", "Read canon, plans, summaries, and prose from the selected source book; use a query to focus the excerpt.", {"query": _STRING}),
    _schema("record_revision_decision", "Record an editing problem and its chosen resolution in the revision ledger.", {"chapter": _STRING, "issue": _STRING, "resolution": _STRING}, ["chapter", "issue", "resolution"]),
    _schema("create_canonical_note", "Create a real canonical vault note during revision; categories: core, story, character, world, organization, object, concept, continuity, research, writing.", {"category": _STRING, "title": _STRING, "content": _STRING}, ["category", "title", "content"]),
    _schema("edit_canonical_note", "Apply one exact canonical-vault edit with mandatory reason, automatic backup, revision ledger, and graph validation.", {"note": _STRING, "old_text": _STRING, "new_text": _STRING, "reason": _STRING}, ["note", "old_text", "new_text", "reason"]),
    _schema("create_agent_note", "Create or replace a non-canonical working note in Agent Notes.", {"title": _STRING, "content": _STRING}, ["title", "content"]),
    _schema("append_chapter_continuity", "Append a verified continuity fact to an existing chapter plan.", {"chapter": _STRING, "fact": _STRING}, ["chapter", "fact"]),
    _schema("append_existing_note", "Append a section to an existing character, location, plot-thread, plan, or agent note.", {"note": _STRING, "section": _STRING, "content": _STRING}, ["note", "section", "content"]),
    _schema("edit_note", "Apply one exact replacement to an editable vault note, including a drafted chapter. Read the note first and provide a unique old_text excerpt.", {"note": _STRING, "old_text": _STRING, "new_text": _STRING}, ["note", "old_text", "new_text"]),
]
TOOL_SCHEMAS_BY_NAME = {item["function"]["name"]: item for item in TOOL_SCHEMAS}


class NovelistAgent:
    """A native-tool-first agent loop with a provider-neutral ReAct fallback."""

    def __init__(self, project: VaultProject, llm, language="en", max_rounds=None, max_calls=None, result_limit=None, web_search_enabled=False, genre=""):
        self.project = project
        self.llm = llm
        self.language = normalize_language(language)
        self.max_rounds = max(1, int(max_rounds or os.getenv("AGENT_MAX_ROUNDS", "8")))
        self.max_calls = max(1, int(max_calls or os.getenv("AGENT_MAX_CALLS_PER_CHAPTER", "16")))
        self.web_search_enabled = bool(web_search_enabled)
        self.genre = str(genre)
        self.tool_schemas = [
            schema for schema in TOOL_SCHEMAS
            if self.web_search_enabled or schema["function"]["name"] not in {"search_web", "read_web_page", "record_research_source"}
        ]
        self.tools = VaultAgentTools(
            project, int(result_limit or os.getenv("AGENT_RESULT_MAX_CHARS", "4000")),
            web_search_enabled=self.web_search_enabled,
        )

    @staticmethod
    def _parse_plan(raw: str) -> dict:
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if not match:
            return {"calls": [], "done": True, "final": raw.strip()}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {"calls": [], "done": True, "final": raw.strip()}
        except json.JSONDecodeError:
            return {"calls": [], "done": True, "final": raw.strip()}

    def _system_prompt(self) -> str:
        live_guidance = guidance_manager.context()
        return (
            "You are an autonomous long-form author, editor, researcher, and continuity agent operating on a real Obsidian vault. "
            "Inspect evidence before asserting facts. Use tools iteratively, observe results, correct failed "
            "queries, and stop when the goal is satisfied. Read tools are always safe. Write tools may update "
            "working notes, plans, entities, summaries, and surgical chapter revisions, but never overwrite the canonical Book Bible. "
            "For nonfiction, separate established evidence, disputed claims, and inference; never invent facts, quotations, or sources. "
            "Do not create wikilinks to notes you have not verified. " + language_instruction(self.language)
            + f" Editorial policy: {editorial_policy(self.genre)}"
            + " When a source book is attached, use read_source_context before revising and record substantive editing decisions."
            + (
                " Web research is enabled. Use search_web to discover sources, read_web_page to inspect them, and record_research_source for evidence used or rejected. Retain source URLs and cross-check consequential claims. "
                + ("For documentary history, corroborate important factual claims with at least two independent source leads before relying on them." if is_documentary_history(self.genre) else "")
                + ("For historical fiction, research only the real-world details that materially support credibility; do not let research displace the invented story." if is_historical_fiction(self.genre) else "")
                if self.web_search_enabled else " Web search is disabled; do not imply that you searched the internet. Mark unresolved nonfiction claims for later verification."
            )
            + (f" Live user guidance (newest takes precedence):\n{live_guidance}" if live_guidance else "")
        )

    def _execute_calls(self, calls: list[dict], remaining: int, round_trace: dict) -> tuple[list[dict], int]:
        observations = []
        for call in calls[:remaining]:
            name = str(call.get("name") or call.get("tool") or "")
            arguments = call.get("args", call.get("arguments", {}))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            result = self.tools.execute(name, arguments)
            item = {"tool": name, "arguments": arguments, "result": result, "id": call.get("id", "")}
            observations.append(item)
            round_trace.setdefault("results", []).append(item)
            remaining -= 1
            if remaining <= 0:
                break
        return observations, remaining

    def _run_native(self, goal: str, trace: dict) -> tuple[str, list[dict]]:
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

        bound = self.llm.bind_tools(self.tool_schemas)
        messages = [SystemMessage(content=self._system_prompt()), HumanMessage(content=goal)]
        all_observations = []
        remaining = self.max_calls
        final = ""
        for round_number in range(1, self.max_rounds + 1):
            generation_control.checkpoint()
            response = bound.invoke(messages)
            calls = []
            for call in getattr(response, "tool_calls", []) or []:
                calls.append({"name": call.get("name"), "args": call.get("args", {}), "id": call.get("id", "")})
            round_trace = {"round": round_number, "mode": "native", "assistant": _response_text(response), "calls": calls, "results": []}
            trace["rounds"].append(round_trace)
            messages.append(response)
            if not calls:
                final = clean_think_tags(_response_text(response))
                break
            observations, remaining = self._execute_calls(calls, remaining, round_trace)
            all_observations.extend(observations)
            for item in observations:
                messages.append(ToolMessage(content=item["result"], tool_call_id=item["id"] or item["tool"]))
            if remaining <= 0:
                final = "Tool-call budget exhausted. Use the gathered evidence only."
                break
        return final, all_observations

    def _is_ollama_model(self) -> bool:
        module = self.llm.__class__.__module__.casefold()
        name = self.llm.__class__.__name__.casefold()
        return "ollama" in module or "ollama" in name

    def _run_ollama_native(self, goal: str, trace: dict) -> tuple[str, list[dict]]:
        model = getattr(self.llm, "model", None) or os.getenv("OLLAMA_MODEL", "")
        if not model:
            raise ValueError("Ollama model name is unavailable")
        base_url = str(getattr(self.llm, "base_url", None) or os.getenv("OLLAMA_API_BASE", "http://localhost:11434")).rstrip("/")
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": goal},
        ]
        observations = []
        remaining = self.max_calls
        final = ""
        for round_number in range(1, self.max_rounds + 1):
            generation_control.checkpoint()
            response = requests.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "tools": self.tool_schemas, "stream": False},
                timeout=float(os.getenv("AGENT_OLLAMA_TIMEOUT", "60")),
            )
            response.raise_for_status()
            message = response.json().get("message", {})
            calls = []
            for index, call in enumerate(message.get("tool_calls", []) or []):
                function = call.get("function", {})
                calls.append({
                    "name": function.get("name", ""),
                    "args": function.get("arguments", {}),
                    "id": call.get("id", f"ollama-{round_number}-{index}"),
                })
            round_trace = {"round": round_number, "mode": "ollama-native", "assistant": message.get("content", ""), "calls": calls, "results": []}
            trace["rounds"].append(round_trace)
            messages.append({"role": "assistant", "content": message.get("content", ""), "tool_calls": message.get("tool_calls", [])})
            if not calls:
                final = clean_think_tags(str(message.get("content", "")))
                break
            new_observations, remaining = self._execute_calls(calls, remaining, round_trace)
            observations.extend(new_observations)
            for item in new_observations:
                messages.append({"role": "tool", "tool_name": item["tool"], "content": item["result"]})
            if remaining <= 0:
                final = "Tool-call budget exhausted. Use the gathered evidence only."
                break
        return final, observations

    def _run_react(self, goal: str, trace: dict) -> tuple[str, list[dict]]:
        observations = []
        remaining = self.max_calls
        final = ""
        tool_spec = json.dumps(self.tool_schemas, ensure_ascii=False)
        for round_number in range(1, self.max_rounds + 1):
            generation_control.checkpoint()
            history = "\n\n".join(
                f"TOOL {item['tool']} {json.dumps(item['arguments'], ensure_ascii=False)}\nOBSERVATION:\n{item['result']}"
                for item in observations
            ) or "No observations yet."
            prompt = f"""
{self._system_prompt()}

GOAL:
{goal}

TOOLS (JSON Schema):
{tool_spec}

OBSERVATION HISTORY:
{history[-10000:]}

Choose the next real tool calls after considering the observations. Return JSON only:
{{"calls":[{{"tool":"tool_name","arguments":{{}}}}],"done":false,"final":""}}
Use no more than {remaining} further calls. Set done=true and provide a concise final when
the goal is complete. Do not claim a tool result you have not observed.
"""
            response = self.llm.invoke(prompt)
            raw = clean_think_tags(_response_text(response))
            plan = self._parse_plan(raw)
            calls = plan.get("calls", []) if isinstance(plan.get("calls", []), list) else []
            round_trace = {"round": round_number, "mode": "react", "plan": plan, "results": []}
            trace["rounds"].append(round_trace)
            new_observations, remaining = self._execute_calls(calls, remaining, round_trace)
            observations.extend(new_observations)
            final = str(plan.get("final") or plan.get("focus") or final).strip()
            if plan.get("done") or remaining <= 0 or not new_observations:
                break
        return final, observations

    def _trace_path(self, chapter: str, phase: str) -> Path:
        directory = self.project.root / ".bookgen" / "agent-traces"
        directory.mkdir(parents=True, exist_ok=True)
        order = next((item["order"] for item in self.project.read_manifest()["chapters"] if item["name"] == chapter), 0)
        return directory / f"{order:03d}-{phase}.json"

    def run(self, goal: str, chapter: str, phase: str) -> str:
        trace = {
            "chapter": chapter,
            "phase": phase,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rounds": [],
            "native_tool_calling": False,
        }
        try:
            if self._is_ollama_model():
                final, observations = self._run_ollama_native(goal, trace)
                trace["native_adapter"] = "ollama-api-chat"
            else:
                final, observations = self._run_native(goal, trace)
                trace["native_adapter"] = "langchain-bind-tools"
            trace["native_tool_calling"] = True
        except (AttributeError, ImportError, NotImplementedError, TypeError, ValueError, requests.RequestException) as error:
            trace["native_fallback_reason"] = str(error)
            final, observations = self._run_react(goal, trace)
        trace["final"] = final
        self._trace_path(chapter, phase).write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        packet = [f"Agent conclusion: {final}"] if final else []
        packet.extend(f"{item['tool']}:\n{item['result']}" for item in observations)
        return "\n\n".join(packet) or "The agent determined that no additional vault operation was required."

    def research_chapter(self, chapter: str, brief: str, beats: list[str]) -> str:
        return self.run(
            goal=(
                f"Prepare verified continuity context before drafting {chapter}.\n"
                f"Chapter brief: {brief}\nScene beats: {json.dumps(beats, ensure_ascii=False)}\n"
                "Search the bible, wiki, plans, and prior summaries as needed. Record a working note only if it adds value."
            ),
            chapter=chapter,
            phase="pre",
        )

    def review_chapter(self, chapter: str, summary: str) -> str:
        return self.run(
            goal=(
                f"Review the persisted draft and continuity summary for {chapter}.\nSummary: {summary}\n"
                "Read the actual chapter note, compare it with its plan and canonical entities, verify the graph, "
                "append useful verified continuity/entity updates, and use exact edit_note patches only for concrete "
                "continuity contradictions or clear prose defects. Avoid broad stylistic rewrites."
            ),
            chapter=chapter,
            phase="post",
        )
