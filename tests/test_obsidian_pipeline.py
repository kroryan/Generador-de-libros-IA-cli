#!/usr/bin/env python3
"""Focused tests for canonical vault storage, graph repair, and publication."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from language import normalize_language
from book_project import BookProjectWorkspace
from obsidian_vault import ObsidianVaultWriter, VaultProject
from publishing import VaultPublisher
from novelist_agent import NovelistAgent
from pipeline import BookGenerationPipeline, BookGenerationRequest, _checkpoint_name


class StubAgentLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        if self.calls == 1:
            return '{"calls":[{"tool":"search_vault","arguments":{"query":"Mara station"}}],"done":false,"focus":"Verify Mara and the station."}'
        return '{"calls":[],"done":true,"focus":"Preserve the established evidence."}'


class FakeChatOllama:
    model = "tool-model"
    base_url = "http://ollama.test"


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class ObsidianPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.chapter_dict = {
            "Prologue": "Mara discovers the signal.",
            "Chapter 1": "Mara follows it into the old station.",
            "Epilogue": "The station changes the inhabited systems.",
        }
        self.summaries = {
            name: f"Canonical brief for {name}." for name in self.chapter_dict
        }
        self.ideas = {
            name: [f"Open {name} with a consequential choice.", "End with a changed story state."]
            for name in self.chapter_dict
        }
        self.project = ObsidianVaultWriter().create(
            output_directory=self.root,
            title="Signal Archive",
            language="en",
            metadata={"genre": "Science fiction"},
            framework="A causal mystery about memory.",
            chapter_dict=self.chapter_dict,
            summaries_dict=self.summaries,
            idea_dict=self.ideas,
            book_bible="## Creative North Star\nMara follows evidence. [[Ghost Note]]",
            wiki_data={
                "characters": [{"name": "Mara", "summary": "An investigator.", "details": "Mara enters the Old Station.", "relationships": ["Old Station", "Missing"]}],
                "locations": [{"name": "Old Station", "summary": "A silent archive.", "details": "Mara studies its records.", "relationships": ["Mara"]}],
            },
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_workspace_uses_generated_title_instead_of_prompt(self):
        prompt = "A very long user prompt that must never become a project directory"
        workspace = BookProjectWorkspace.create(self.root / "books", {"subject": prompt})
        temporary_root = workspace.root
        self.assertTrue(temporary_root.name.startswith("pending-book-"))
        self.assertNotIn("long-user-prompt", temporary_root.name)

        renamed = workspace.rename_for_title("The Cartographer's Paradox")

        self.assertEqual(renamed.root.name, "the-cartographers-paradox")
        self.assertFalse(temporary_root.exists())
        self.assertTrue((renamed.root / "Work" / "00 Request.md").is_file())
        manifest = renamed.read_manifest()
        self.assertEqual(manifest["project_id"], "the-cartographers-paradox")
        self.assertEqual(manifest["title"], "The Cartographer's Paradox")

    def test_workspace_title_collision_uses_stable_suffix(self):
        output = self.root / "books"
        first = BookProjectWorkspace.create(output, {"subject": "First"}).rename_for_title("Shared Title")
        second = BookProjectWorkspace.create(output, {"subject": "Second"}).rename_for_title("Shared Title")

        self.assertEqual(first.root.name, "shared-title")
        self.assertEqual(second.root.name, "shared-title-2")

    def test_language_validation(self):
        self.assertEqual(normalize_language("English"), "en")
        self.assertEqual(normalize_language("espanol"), "es")
        with self.assertRaises(ValueError):
            normalize_language("fr")

    def test_spanish_vault_localizes_application_owned_notes(self):
        project = ObsidianVaultWriter().create(
            output_directory=self.root / "spanish", title="Archivo historico", language="es",
            metadata={"genre": "Historia"}, framework="Marco factual.",
            chapter_dict={"Capitulo 1": "Expone la cronologia."},
            summaries_dict={"Capitulo 1": "Brief factual."},
            idea_dict={"Capitulo 1": ["Presentar las pruebas documentales."]},
            book_bible="## Tesis\nLa cronologia se apoya en archivos.",
        )
        manifest = project.read_manifest()
        plan = (project.root / manifest["chapters"][0]["plan_path"]).read_text(encoding="utf-8")
        portal = (project.root / f"{manifest['paths']['portal']}.md").read_text(encoding="utf-8")
        templates = {path.name for path in (project.root / manifest["paths"]["templates"]).glob("*.md")}
        self.assertIn("## Plan de secciones", plan)
        self.assertIn("|Biblia del libro]]", portal)
        self.assertIn("Template - Fuente de investigacion.md", templates)
        self.assertEqual(project.load_generation_inputs()[2]["Capitulo 1"], ["Presentar las pruebas documentales."])
        self.assertEqual(project.validate_links(), [])

    def test_plans_are_reloaded_from_vault(self):
        bible, summaries, ideas = self.project.load_generation_inputs()
        self.assertIn("Creative North Star", bible)
        self.assertEqual(summaries, self.summaries)
        self.assertEqual(ideas, self.ideas)
        manifest = self.project.read_manifest()
        self.assertIn("/Books/Book - Signal Archive/", manifest["chapters"][0]["plan_path"])
        self.assertEqual(manifest["books"][0]["id"], "signal-archive")

    def test_bible_volumes_are_visible_and_incremental(self):
        project = ObsidianVaultWriter().create(
            output_directory=self.root, title="Incremental Canon", language="es",
            metadata={}, framework="## Premisa\nMarco generado.", book_bible="", progressive=True,
        )
        initial = project.read_manifest()
        self.assertEqual(initial["book_bible_volumes"], [])
        self.assertFalse((project.root / f"{initial['book_bible']}.md").exists())
        self.assertFalse((project.root / f"{initial['wiki_index']}.md").exists())
        self.assertFalse((project.root / f"{initial['outline']}.md").exists())
        self.assertTrue((project.root / f"{initial['framework_note']}.md").is_file())

        project.write_bible_volumes([
            ("Creative and editorial foundation", "## Premisa\nCanon inicial."),
        ])
        first = project.read_manifest()
        self.assertEqual(len(first["book_bible_volumes"]), 1)
        first_path = project.root / first["book_bible_volumes"][0]
        self.assertTrue(first_path.is_file())
        self.assertIn("Fundamentos creativos", first_path.read_text(encoding="utf-8"))
        first_path.write_text(
            first_path.read_text(encoding="utf-8").replace("Canon inicial", "Canon editado por el usuario"),
            encoding="utf-8",
        )

        project.write_bible_volumes([
            ("Creative and editorial foundation", "## Premisa\nCanon inicial."),
            ("People, actors, and relationships", "## Personas\nReparto canonico."),
        ])
        final = project.read_manifest()
        self.assertEqual(len(final["book_bible_volumes"]), 2)
        self.assertIn("Canon editado por el usuario", project.read_bible())
        project.write_wiki({
            "characters": [{
                "name": "Alfredo", "aliases": [], "subtype": "protagonista",
                "summary": "Astromago dividido entre dos tradiciones.",
                "details": "## Funcion\nSostiene el conflicto central.", "relationships": [],
            }],
        })
        wiki_manifest = project.read_manifest()
        self.assertTrue((project.root / f"{wiki_manifest['wiki_index']}.md").is_file())
        self.assertTrue((project.root / "04 - Personajes/Index - Personajes.md").is_file())
        self.assertFalse((project.root / "05 - Mundo/Index - Lugares.md").exists())
        self.assertFalse((project.root / "06 - Organizaciones/Index - Organizaciones.md").exists())
        self.assertEqual(project.validate_links(), [])

    def test_graph_is_repaired_and_valid(self):
        self.assertEqual(self.project.validate_links(), [])
        bible = self.project.read_bible()
        self.assertIn("Ghost Note", bible)
        self.assertNotIn("[[Ghost Note]]", bible)
        manifest = self.project.read_manifest()
        mara_path = next(item["path"] for item in manifest["entities"] if item["name"] == "Mara")
        station_path = next(item["path"] for item in manifest["entities"] if item["name"] == "Old Station")
        mara = (self.project.root / f"{mara_path}.md").read_text(encoding="utf-8")
        self.assertIn(f"[[{station_path}|Old Station]]", mara)
        self.assertNotIn("[[Missing]]", mara)
        report = json.loads((self.project.root / ".bookgen" / "link-repairs.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["reason"] == "missing" for item in report))
        extensionless_files = [path for path in self.project.root.rglob("*") if path.is_file() and not path.suffix]
        self.assertEqual(extensionless_files, [])

    def test_chapters_publish_from_vault(self):
        for chapter in self.chapter_dict:
            self.project.write_chapter(chapter, [f"Narrative prose for {chapter}."], f"Summary of {chapter}.")
        markdown = VaultPublisher().publish(self.project, "md", self.root)
        archive = VaultPublisher().publish(self.project, "obsidian", self.root)
        self.assertTrue(markdown.is_file())
        self.assertTrue(archive.is_file())
        compiled = markdown.read_text(encoding="utf-8")
        self.assertIn("# Signal Archive", compiled)
        self.assertIn("Narrative prose for Chapter 1.", compiled)
        self.assertEqual(self.project.validate_links(), [])

    def test_ambiguous_links_are_delinked(self):
        manifest = self.project.read_manifest()
        first = self.project.root / manifest["paths"]["characters"] / "Duplicate.md"
        second = self.project.root / manifest["paths"]["world"] / "Duplicate.md"
        first.write_text("# One\n", encoding="utf-8")
        second.write_text("# Two\n", encoding="utf-8")
        source = self.project.root / "Ambiguous.md"
        source.write_text("See [[Duplicate|the duplicate]].\n", encoding="utf-8")
        repairs = self.project.repair_and_validate_graph()
        self.assertTrue(any(item["reason"] == "ambiguous" for item in repairs))
        self.assertEqual(source.read_text(encoding="utf-8"), "See the duplicate.\n")

    def test_novelist_agent_uses_read_only_vault_tools(self):
        llm = StubAgentLLM()
        packet = NovelistAgent(self.project, llm, language="en", max_rounds=2, max_calls=2).research_chapter(
            "Chapter 1", self.summaries["Chapter 1"], self.ideas["Chapter 1"]
        )
        self.assertEqual(llm.calls, 2)
        self.assertIn("search_vault", packet)
        trace = self.project.root / ".bookgen" / "agent-traces" / "002-pre.json"
        self.assertTrue(trace.is_file())
        trace_data = json.loads(trace.read_text(encoding="utf-8"))
        self.assertEqual(trace_data["chapter"], "Chapter 1")
        self.assertEqual(trace_data["rounds"][0]["results"][0]["tool"], "search_vault")

    def test_ollama_uses_native_tool_calls(self):
        responses = [
            FakeHTTPResponse({"message": {"content": "", "tool_calls": [{"function": {"name": "search_vault", "arguments": {"query": "Mara"}}}]}}),
            FakeHTTPResponse({"message": {"content": "Canon verified.", "tool_calls": []}}),
        ]
        agent = NovelistAgent(self.project, FakeChatOllama(), max_rounds=3, max_calls=3)
        with patch("novelist_agent.requests.post", side_effect=responses) as request_mock:
            packet = agent.research_chapter("Chapter 1", self.summaries["Chapter 1"], self.ideas["Chapter 1"])
        self.assertEqual(request_mock.call_count, 2)
        self.assertIn("Canon verified", packet)
        first_payload = request_mock.call_args_list[0].kwargs["json"]
        self.assertTrue(first_payload["tools"])
        trace = json.loads((self.project.root / ".bookgen" / "agent-traces" / "002-pre.json").read_text(encoding="utf-8"))
        self.assertTrue(trace["native_tool_calling"])
        self.assertEqual(trace["native_adapter"], "ollama-api-chat")

    def test_agent_writes_are_graph_validated(self):
        tools = NovelistAgent(self.project, StubAgentLLM(), max_rounds=1, max_calls=1).tools
        result = tools.append_chapter_continuity("Chapter 1", "Mara verifies [[Missing Canon]] and returns.")
        self.assertIn("Updated", result)
        plan = (self.project.root / self.project.read_manifest()["chapters"][1]["plan_path"]).read_text(encoding="utf-8")
        self.assertIn("Missing Canon", plan)
        self.assertNotIn("[[Missing Canon]]", plan)
        self.assertEqual(self.project.validate_links(), [])

    def test_agent_can_apply_exact_chapter_patch(self):
        self.project.write_chapter("Chapter 1", ["Mara entered the archive."], "Mara enters.")
        tools = NovelistAgent(self.project, StubAgentLLM(), max_rounds=1, max_calls=1).tools
        result = tools.edit_note("002 Chapter 1", "Mara entered the archive.", "Mara entered the silent archive.")
        self.assertIn("Patched", result)
        chapter_path = self.project.root / self.project.read_manifest()["chapters"][1]["draft_path"]
        self.assertIn("silent archive", chapter_path.read_text(encoding="utf-8"))
        self.assertEqual(self.project.validate_links(), [])

    def test_revision_agent_can_edit_vault_with_backup_and_ledger(self):
        project = ObsidianVaultWriter().create(
            output_directory=self.root, title="Editable Canon", language="en",
            metadata={"vault_mode": "revise"}, framework="Framework",
            book_bible="The city gate is blue.",
        )
        tools = NovelistAgent(project, StubAgentLLM(), max_rounds=1, max_calls=1).tools
        volume = project.read_manifest()["book_bible_volumes"][0]
        result = tools.edit_canonical_note(
            volume, "The city gate is blue.", "The city gate is green.",
            "Apply the binding color correction.",
        )
        self.assertIn("backup:", result)
        self.assertIn("green", (project.root / volume).read_text(encoding="utf-8"))
        self.assertTrue(any((project.root / ".bookgen" / "revisions").rglob("*.md")))
        ledger = project.root / project.read_manifest()["paths"]["agent_notes"] / "Revision Ledger.md"
        self.assertIn("binding color correction", ledger.read_text(encoding="utf-8"))
        created = tools.create_canonical_note("character", "New Witness", "A verified witness in the revised canon.")
        self.assertIn("Created", created)
        self.assertTrue(any(item["name"] == "New Witness" for item in project.read_manifest()["entities"]))
        self.assertEqual(project.validate_links(), [])

    def test_alias_collision_creates_one_canonical_entity(self):
        project = ObsidianVaultWriter().create(
            output_directory=self.root, title="Alias Test", language="en", metadata={},
            framework="Framework", book_bible="Canonical bible.",
            wiki_data={
                "concepts": [
                    {"name": "Aether Law", "aliases": ["Magic System"], "summary": "A rule.", "details": "First detail."},
                    {"name": "Magic System", "aliases": [], "summary": "Same rule.", "details": "Second detail."},
                ]
            },
        )
        manifest = project.read_manifest()
        self.assertEqual(len(manifest["entities"]), 1)
        self.assertEqual(manifest["entities"][0]["name"], "Aether Law")
        note = (project.root / f"{manifest['entities'][0]['path']}.md").read_text(encoding="utf-8")
        self.assertIn("First detail", note)
        self.assertIn("Second detail", note)
        self.assertEqual(project.validate_links(), [])

    def test_pipeline_builds_wiki_before_planning_chapters(self):
        output = self.root / "ordered-books"
        request = BookGenerationRequest(
            subject="Premise", profile="Readers", style="Precise", genre="Science fiction",
            output_path=str(output), output_format="md", agent_tools=False,
        )
        events = []

        def foundation(*args, **kwargs):
            kwargs["on_stage"]("title", "Ordered")
            kwargs["on_stage"]("framework", "Framework")
            return "Ordered", "Framework"

        def bible(*args, **kwargs):
            events.append("bible")
            kwargs["on_quality"](
                1, 1, "Core Canon & Continuity", 0,
                {"passed": True, "audit": {"verdict": "pass", "issues": []}},
                "Canonical bible.",
            )
            kwargs["on_volume"](
                1,
                1,
                "Core Canon & Continuity",
                "Canonical bible.",
                [("Core Canon & Continuity", "Canonical bible.")],
            )
            return "Canonical bible."

        def wiki(*args, **kwargs):
            events.append("wiki")
            result = {key: [] for key in ("characters", "locations", "organizations", "objects", "concepts", "events")}
            kwargs["on_quality"](
                1, 6, "characters", 0,
                {"passed": True, "audit": {"verdict": "pass", "issues": []}}, [],
            )
            kwargs["on_domain"](1, 6, "characters", [], {"characters": []})
            return result

        def outline(*args, **kwargs):
            events.append("outline")
            self.assertIn("wiki", events)
            return self.chapter_dict

        def plans(*args, **kwargs):
            events.append("plans")
            return self.summaries, self.ideas

        def draft(*args, **kwargs):
            events.append("draft")
            for chapter in args[6]:
                kwargs["on_chapter_complete"](chapter, ["Narrative prose."], "Summary.")

        with patch("pipeline.get_foundation", side_effect=foundation), patch(
            "pipeline.BookBibleChain.run", side_effect=bible
        ), patch("pipeline.WikiDataChain.run", side_effect=wiki), patch(
            "pipeline.get_chapter_outline", side_effect=outline
        ), patch("pipeline.get_ideas", side_effect=plans), patch("pipeline.write_book", side_effect=draft):
            BookGenerationPipeline().run(request)
        self.assertEqual(events, ["bible", "wiki", "outline", "plans", "draft"])
        self.assertTrue((output / "ordered").is_dir())
        checkpoints = list(output.glob("*/.bookgen/checkpoints/bible-01-core-canon-continuity.md"))
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(len(list(output.glob("*/.bookgen/checkpoints/bible-quality-*.json"))), 1)
        self.assertEqual(len(list(output.glob("*/.bookgen/checkpoints/wiki-quality-*-cycle-00.json"))), 1)
        self.assertEqual(len(list(output.glob("*/.bookgen/checkpoints/wiki-quality-*-candidate.json"))), 1)

    def test_checkpoint_name_normalizes_unicode_and_symbols(self):
        self.assertEqual(_checkpoint_name("  Núcleo & Continuidad  "), "núcleo-continuidad")
        self.assertEqual(_checkpoint_name("***"), "item")

    def test_revision_mode_loads_selected_manuscript_and_creates_brief(self):
        output = self.root / "revisions"
        captured = {}
        request = BookGenerationRequest(
            subject="Tighten the middle and preserve Mara's restrained voice.",
            profile="Adult readers", style="Precise", genre="Science fiction",
            output_path=str(output), output_format="md", agent_tools=False,
            source_vault_path=str(self.project.root), source_book_id="signal-archive", vault_mode="revise",
        )

        def foundation(subject, *args, **kwargs):
            captured["subject"] = subject
            return "Signal Archive Revised", "Framework"

        def draft(*args, **kwargs):
            for chapter in args[6]:
                kwargs["on_chapter_complete"](chapter, ["Revised narrative prose."], "Summary.")

        empty_wiki = {key: [] for key in ("characters", "locations", "organizations", "objects", "concepts", "events")}
        with patch("pipeline.get_foundation", side_effect=foundation), patch(
            "pipeline.IncrementalVaultContextBuilder.build", return_value=(
                "## Canonical source dossier\nMara and all binding revision decisions.",
                {"strategy": "incremental-update", "changed_files": 1, "total_files": 10, "deleted_files": 0, "batches": 1},
            )
        ), patch(
            "pipeline.BookBibleChain.run", return_value="Canonical revised bible."
        ), patch("pipeline.WikiDataChain.run", return_value=empty_wiki), patch(
            "pipeline.get_chapter_outline", return_value=self.chapter_dict
        ), patch("pipeline.get_ideas", return_value=(self.summaries, self.ideas)), patch(
            "pipeline.write_book", side_effect=draft
        ):
            result = BookGenerationPipeline().run(request)

        self.assertIn("CANONICAL SOURCE DOSSIER", captured["subject"])
        self.assertIn("binding revision decisions", captured["subject"])
        manifest = json.loads((result.project_path / ".bookgen" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue((result.project_path / f"{manifest['paths']['revision_brief']}.md").is_file())
        source_context = (result.project_path / ".bookgen" / "checkpoints" / "source-vault-context.md").read_text(encoding="utf-8")
        self.assertIn("Canonical source dossier", source_context)
        context_root = result.project_path / "11 - Book Context Wiki" / "Book - Signal Archive"
        self.assertTrue((context_root / "00 - Source Book Portal.md").is_file())
        self.assertIn(
            "Canonical source dossier",
            (context_root / "01 - Compressed Context.md").read_text(encoding="utf-8"),
        )
        self.assertFalse((result.project_path / "03 - Manuscript" / "Books" / "Book - Signal Archive").exists())
        planning_context = VaultProject(result.project_path).planning_context()
        self.assertIn("Previous-book context", planning_context)
        self.assertEqual(VaultProject(result.project_path).validate_links(), [])

    def test_book_bible_checkpoint_survives_wiki_failure(self):
        output = self.root / "books"
        request = BookGenerationRequest(
            subject="A station preserves forbidden memories",
            profile="Adult science-fiction readers",
            style="Precise",
            genre="Science fiction",
            output_path=str(output),
            output_format="md",
        )
        with patch("pipeline.get_foundation", return_value=("Signal Archive", "Framework")), patch(
            "pipeline.get_chapter_outline", return_value=self.chapter_dict
        ), patch(
            "pipeline.get_ideas", return_value=(self.summaries, self.ideas)
        ), patch("pipeline.BookBibleChain.run", return_value="## Creative North Star\nPersistent canon."), patch(
            "pipeline.WikiDataChain.run", side_effect=RuntimeError("wiki service stopped")
        ):
            with self.assertRaisesRegex(RuntimeError, "wiki service stopped"):
                BookGenerationPipeline().run(request)

        projects = list(output.iterdir())
        self.assertEqual(len(projects), 1)
        project_root = projects[0]
        bible_checkpoint = project_root / ".bookgen" / "checkpoints" / "bible-complete.md"
        self.assertTrue(bible_checkpoint.is_file())
        self.assertIn("Persistent canon", bible_checkpoint.read_text(encoding="utf-8"))
        manifest = json.loads((project_root / ".bookgen" / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("wiki service stopped", manifest["error"])

    def test_accepted_bible_volume_is_visible_before_later_volume_failure(self):
        output = self.root / "books"
        request = BookGenerationRequest(
            subject="A station preserves forbidden memories",
            profile="Adult science-fiction readers",
            style="Precise",
            genre="Science fiction",
            output_path=str(output),
            output_format="md",
        )

        def partial_bible(*_args, **kwargs):
            volumes = [("Creative and editorial foundation", "## Premise\nAccepted visible canon.")]
            kwargs["on_volume"](1, 6, volumes[0][0], volumes[0][1], volumes)
            raise RuntimeError("second volume stopped")

        with patch("pipeline.get_foundation", return_value=("Visible Canon", "Framework")), patch(
            "pipeline.BookBibleChain.run", side_effect=partial_bible
        ):
            with self.assertRaisesRegex(RuntimeError, "second volume stopped"):
                BookGenerationPipeline().run(request)

        project_root = next(output.iterdir())
        vault = VaultProject(project_root)
        manifest = vault.read_manifest()
        self.assertEqual(len(manifest["book_bible_volumes"]), 1)
        visible = project_root / manifest["book_bible_volumes"][0]
        self.assertTrue(visible.is_file())
        self.assertIn("Accepted visible canon", visible.read_text(encoding="utf-8"))
        self.assertEqual(vault.validate_links(), [])

    def test_completed_generation_is_confined_to_one_project(self):
        output = self.root / "books"
        request = BookGenerationRequest(
            subject="A station preserves forbidden memories",
            profile="Adult science-fiction readers",
            style="Precise",
            genre="Science fiction",
            output_path=str(output),
            output_format="md",
            agent_tools=False,
        )

        def draft_book(*args, **kwargs):
            for chapter in args[6]:
                kwargs["on_chapter_complete"](
                    chapter,
                    [f"Narrative prose for {chapter}."],
                    f"Summary for {chapter}.",
                )

        with patch("pipeline.get_foundation", return_value=("Signal Archive", "Framework")), patch(
            "pipeline.get_chapter_outline", return_value=self.chapter_dict
        ), patch(
            "pipeline.get_ideas", return_value=(self.summaries, self.ideas)
        ), patch("pipeline.BookBibleChain.run", return_value="## Creative North Star\nPersistent canon."), patch(
            "pipeline.WikiDataChain.run", return_value={"characters": [], "locations": [], "organizations": [], "objects": [], "concepts": [], "events": []}
        ), patch("pipeline.write_book", side_effect=draft_book):
            result = BookGenerationPipeline().run(request)

        projects = list(output.iterdir())
        self.assertEqual(projects, [result.project_path])
        self.assertEqual(result.project_path.name, "signal-archive")
        self.assertEqual(result.vault_path, result.project_path)
        self.assertEqual(result.output_path.parent, result.project_path / "Exports")
        self.assertTrue((result.project_path / "Work" / "00 Request.md").is_file())
        self.assertTrue((result.project_path / ".bookgen" / "checkpoints" / "bible-complete.md").is_file())
        vault_manifest = json.loads((result.project_path / ".bookgen" / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue((result.project_path / f"{vault_manifest['book_bible']}.md").is_file())
        self.assertTrue((result.project_path / "Project Dashboard.md").is_file())
        self.assertEqual(json.loads((result.project_path / ".bookgen" / "project.json").read_text(encoding="utf-8"))["status"], "complete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
