"""Single Obsidian-first book-generation pipeline for CLI and web."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Callable

from book_bible import BookBibleChain, WikiDataChain
from book_project import BookProjectWorkspace
from generation_control import GenerationCancelled, generation_control
from guidance import guidance_manager
from editorial_policy import editorial_policy, is_documentary_history
from ideas import get_ideas
from language import normalize_language
from obsidian_vault import ObsidianVaultWriter, VaultProject
from publishing import VaultPublisher
from structure import get_chapter_outline, get_foundation
from writing import write_book
from vault_context import IncrementalVaultContextBuilder
from web_research import search_duckduckgo


ProgressCallback = Callable[[str, int, dict], None]


@dataclass(frozen=True)
class BookGenerationRequest:
    subject: str
    profile: str
    style: str
    genre: str
    language: str = "en"
    output_format: str = "docx"
    output_path: str = "./books"
    agent_tools: bool = True
    web_search: bool = False
    source_vault_path: str = ""
    source_book_id: str = ""
    vault_mode: str = "new"


@dataclass(frozen=True)
class BookGenerationResult:
    title: str
    project_path: Path
    vault_path: Path
    output_path: Path
    graph_repairs: int


class BookGenerationPipeline:
    def __init__(self, progress_callback: ProgressCallback | None = None):
        self.progress_callback = progress_callback

    def _progress(self, message: str, progress: int, **data) -> None:
        generation_control.checkpoint()
        print(f"\n> {message}", flush=True)
        if self.progress_callback:
            self.progress_callback(message, progress, data)

    def run(self, request: BookGenerationRequest) -> BookGenerationResult:
        language = normalize_language(request.language)
        output_path = Path(request.output_path).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        request_data = {
            "subject": request.subject, "profile": request.profile, "style": request.style,
            "genre": request.genre, "language": language, "output_format": request.output_format,
            "agent_tools": request.agent_tools,
            "web_search": request.web_search,
            "source_vault_path": request.source_vault_path,
            "source_book_id": request.source_book_id,
            "vault_mode": request.vault_mode,
        }
        workspace = BookProjectWorkspace.create(output_path, request_data)
        guidance_manager.attach_project(workspace.root)
        previous_project = os.environ.get("BOOKGEN_PROJECT_DIR")
        os.environ["BOOKGEN_PROJECT_DIR"] = str(workspace.root)
        self._progress("Project workspace created.", 3, project_path=str(workspace.root))

        title = ""
        try:
            subject = request.subject
            profile = request.profile
            source_digest = ""
            source_book_title = ""
            source_book_chapters: list[dict] = []
            if request.source_vault_path:
                source_project = VaultProject(Path(request.source_vault_path).expanduser().resolve())
                if not source_project.manifest_path.is_file():
                    raise ValueError("The selected source vault has no valid BookGen manifest")
                intent = {
                    "continue": "Continue this established story without resetting resolved arcs or contradicting its canon.",
                    "related": "Create a distinct second book in or around this established canon; preserve shared facts and avoid retelling the first book.",
                    "revise": (
                        "Act as a senior developmental and line editor. Produce a revised edition in a new project. "
                        "Treat the user premise field as binding revision instructions; preserve deliberate canon and voice, "
                        "diagnose causal, continuity, pacing, characterization, and prose problems, then resolve them in the new manuscript."
                    ),
                }.get(request.vault_mode, "Use this vault only as canonical background for the requested book.")
                self._progress("Updating the incremental source-vault context index...", 4)
                def source_batch_checkpoint(index, total, paths) -> None:
                    workspace.write_checkpoint(f"source-index-batch-{index:02d}.json", paths)
                    self._progress(f"Changed source batch {index}/{total} indexed.", 4)

                source_digest, context_stats = IncrementalVaultContextBuilder().build(
                    source_project, request.vault_mode, request.source_book_id,
                    request.subject, language, on_batch=source_batch_checkpoint,
                )
                source_manifest = source_project.read_manifest()
                source_books = source_manifest.get("books", [])
                selected_source_book = next(
                    (item for item in source_books if item.get("id") == request.source_book_id), None
                )
                if selected_source_book:
                    source_book_title = str(selected_source_book.get("title") or source_manifest.get("title") or "Source Book")
                    source_book_chapters = list(selected_source_book.get("chapters", []))
                else:
                    source_book_title = str(source_manifest.get("title") or "Source Book")
                    source_book_chapters = list(source_manifest.get("chapters", []))
                workspace.write_checkpoint("source-context-stats.json", context_stats)
                workspace.write_checkpoint("source-vault-context.md", source_digest)
                workspace.write_checkpoint("source-vault-dossier.md", source_digest)
                self._progress(
                    f"Source context ready: {context_stats['strategy']} "
                    f"({context_stats['changed_files']} changed, {context_stats['total_files']} total).",
                    4,
                )
                subject = f"{request.subject}\n\nSOURCE VAULT INTENT: {intent}\n\nCANONICAL SOURCE DOSSIER:\n{source_digest}"
                profile = f"{request.profile}\n\nTreat the selected source vault as established evidence. Do not invent changes to its past facts without an explicit revision instruction."
                self._progress(
                    f"Loaded source vault context for mode: {request.vault_mode}", 4,
                    project_path=str(workspace.root),
                )

            policy = editorial_policy(request.genre)
            profile = f"{profile}\n\nEDITORIAL FACTUALITY POLICY: {policy}"
            if is_documentary_history(request.genre) and request.web_search:
                self._progress("Researching initial historical source leads with DuckDuckGo...", 5)
                query = " ".join(request.subject.split())[:300]
                try:
                    research_leads = search_duckduckgo(query, 8)
                except Exception as error:
                    research_leads = []
                    self._progress(f"Initial web research unavailable; claims remain marked for verification: {error}", 5)
                workspace.write_checkpoint("web-research-leads.json", research_leads)
                if research_leads:
                    rendered_leads = "\n".join(
                        f"- {item['title']} | {item['url']} | {item['snippet']}" for item in research_leads
                    )
                    subject = (
                        f"{subject}\n\nINITIAL WEB RESEARCH LEADS (discovery snippets, not final proof; "
                        f"cross-check before asserting):\n{rendered_leads}"
                    )
                    self._progress(f"Saved {len(research_leads)} historical research leads with source URLs.", 6)

            def foundation_checkpoint(stage: str, value) -> None:
                nonlocal title, workspace
                if stage == "title":
                    title = str(value)
                    previous_root = workspace.root
                    workspace = workspace.rename_for_title(title)
                    guidance_manager.relocate_project(previous_root, workspace.root)
                    os.environ["BOOKGEN_PROJECT_DIR"] = str(workspace.root)
                    workspace.update(status="running", current_stage="title")
                    workspace.write_checkpoint("01-title.md", f"# Title\n\n{title}")
                    self._progress(
                        "Project workspace named from the generated title.", 5,
                        title=title, project_path=str(workspace.root),
                    )
                elif stage == "framework":
                    workspace.update(status="running", current_stage="framework")
                    workspace.write_checkpoint("02-framework.md", str(value))

            self._progress("Generating title and foundational framework...", 5)
            title, framework = get_foundation(
                subject, request.genre, request.style, profile, language,
                on_stage=foundation_checkpoint,
            )
            previous_root = workspace.root
            workspace = workspace.rename_for_title(title)
            guidance_manager.relocate_project(previous_root, workspace.root)
            os.environ["BOOKGEN_PROJECT_DIR"] = str(workspace.root)
            workspace.update(title=title, status="running", current_stage="book_bible")

            self._progress("Creating the visible Obsidian vault foundation...", 7, title=title)
            project = ObsidianVaultWriter().create(
                output_directory=output_path, vault_root=workspace.root, title=title,
                language=language, metadata=request_data, framework=framework,
                book_bible="",
            )
            workspace.update(status="running", current_stage="book_bible", vault_path=".")

            bible_volumes: list[tuple[str, str]] = []
            def bible_checkpoint(index, total, name, body, volumes) -> None:
                bible_volumes[:] = volumes
                workspace.write_checkpoint(f"bible-{index:02d}-{_checkpoint_name(name)}.md", body)
                project.write_bible_volumes(volumes)
                self._progress(
                    f"Canonical bible volume {index}/{total} saved: {name}",
                    8 + int(20 * index / max(1, total)), title=title,
                )

            def bible_quality_checkpoint(index, total, name, cycle, report, candidate) -> None:
                stem = f"bible-quality-{index:02d}-cycle-{cycle:02d}-{_checkpoint_name(name)}"
                workspace.write_checkpoint(f"{stem}.json", report)
                workspace.write_checkpoint(f"{stem}-candidate.md", candidate)
                outcome = "passed" if report.get("passed") else "requires repair"
                self._progress(
                    f"Bible quality audit {index}/{total}, cycle {cycle + 1}: {outcome}",
                    8 + int(20 * (index - 1) / max(1, total)), title=title,
                )

            self._progress("Building the canonical book bible before chapter planning...", 8, title=title)
            bible = BookBibleChain().run(
                subject, request.genre, request.style, profile,
                title, framework, language, on_volume=bible_checkpoint,
                on_quality=bible_quality_checkpoint,
            )
            workspace.write_checkpoint("bible-complete.md", bible)
            project.write_bible(bible)
            self._progress("Canonical bible complete in the visible Obsidian vault.", 29, title=title)
            workspace.update(status="running", current_stage="wiki", vault_path=".")

            def wiki_checkpoint(index, total, domain, items, partial) -> None:
                workspace.write_checkpoint(f"wiki-{index:02d}-{domain}.json", items)
                project.write_wiki(partial)
                self._progress(
                    f"Canonical wiki domain {index}/{total} saved: {domain}",
                    30 + int(14 * index / max(1, total)), title=title,
                )

            def wiki_quality_checkpoint(index, total, domain, cycle, report, items) -> None:
                stem = f"wiki-quality-{index:02d}-{domain}-cycle-{cycle:02d}"
                workspace.write_checkpoint(f"{stem}.json", report)
                workspace.write_checkpoint(f"{stem}-candidate.json", items)
                outcome = "passed" if report.get("passed") else "requires repair"
                self._progress(
                    f"Wiki quality audit {index}/{total}, cycle {cycle + 1}: {outcome}",
                    30 + int(14 * (index - 1) / max(1, total)), title=title,
                )

            self._progress("Expanding and linking the canonical wiki...", 30, title=title)
            wiki_data = WikiDataChain().run(
                bible, language, on_domain=wiki_checkpoint, on_quality=wiki_quality_checkpoint,
            )
            workspace.write_checkpoint("wiki-complete.json", wiki_data)
            project.write_wiki(wiki_data)
            if source_digest:
                project.write_source_book_context(
                    source_book_title, source_digest, request.source_vault_path,
                    request.source_book_id, request.vault_mode, source_book_chapters,
                )
                self._progress("Previous-book context wiki saved separately from full manuscripts.", 44, title=title)

            planning_context = project.planning_context()
            workspace.write_checkpoint("planning-context.md", planning_context)
            self._progress("Planning chapters from the completed bible and wiki...", 45, title=title)
            chapter_dict = get_chapter_outline(
                subject, request.genre, request.style, profile,
                title, framework, planning_context, language,
            )
            workspace.write_checkpoint("chapter-outline.json", chapter_dict)

            partial_summaries: dict[str, str] = {}
            partial_ideas: dict[str, list[str]] = {}
            def plan_checkpoint(chapter, summary, ideas, index, total) -> None:
                partial_summaries[chapter] = summary
                partial_ideas[chapter] = ideas
                workspace.write_checkpoint(
                    f"plan-{index:03d}-{_checkpoint_name(chapter)}.json",
                    {"chapter": chapter, "summary": summary, "ideas": ideas},
                )
                self._progress(
                    f"Detailed chapter plan {index}/{total} saved: {chapter}",
                    47 + int(12 * index / max(1, total)), title=title,
                    chapter_count=total,
                )

            self._progress("Generating detailed chapter and section plans...", 47, title=title, chapter_count=len(chapter_dict))
            summaries, ideas = get_ideas(
                subject, request.genre, request.style, profile,
                title, framework, chapter_dict, language, on_chapter_plan=plan_checkpoint,
            )
            project.write_plans(chapter_dict, summaries, ideas)

            # Drafting always reloads canonical inputs from disk.
            canonical_bible, canonical_summaries, canonical_ideas = project.load_generation_inputs()
            chapter_summaries: dict[str, str] = {}
            completed, total = 0, max(1, len(canonical_ideas))
            def persist_chapter(chapter: str, sections: list[str], summary: str) -> None:
                nonlocal completed
                project.write_chapter(chapter, sections, summary)
                project.repair_and_validate_graph()
                completed += 1
                workspace.update(current_stage=f"draft_{completed}", status="running")
                self._progress(
                    f"Drafted and saved {chapter}", 60 + int(29 * completed / total),
                    title=title, current_chapter=completed, chapter_count=total,
                )

            self._progress("Drafting chapters from canonical Obsidian plans...", 60, title=title)
            write_book(
                request.genre, request.style, request.profile, title, framework,
                canonical_summaries, canonical_ideas, chapter_summaries=chapter_summaries,
                language=language, book_bible=canonical_bible,
                on_chapter_complete=persist_chapter, vault_project=project,
                agent_tools=request.agent_tools,
                web_search=request.web_search,
            )

            self._progress(f"Publishing {request.output_format.upper()} from the vault...", 90, title=title)
            repairs = project.repair_and_validate_graph()
            published = VaultPublisher().publish(project, request.output_format, workspace.exports_directory)
            workspace.mark_complete(title, published)
            self._progress("Book generation complete.", 100, title=title, file_path=str(published))
            return BookGenerationResult(title, workspace.root, project.root, published, len(repairs))
        except GenerationCancelled:
            workspace.mark_cancelled()
            raise
        except Exception as error:
            workspace.mark_failed(error)
            raise
        finally:
            if previous_project is None:
                os.environ.pop("BOOKGEN_PROJECT_DIR", None)
            else:
                os.environ["BOOKGEN_PROJECT_DIR"] = previous_project


def _checkpoint_name(value: str) -> str:
    return "-".join(re.findall(r"[\w]+", str(value).casefold(), flags=re.UNICODE))[:60] or "item"
