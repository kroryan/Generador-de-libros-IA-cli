"""Regression tests for prompt construction and generation control."""

import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_community.llms.fake import FakeListLLM

from generation_control import GenerationCancelled, GenerationControl
from writing import WriterChain
from book_bible import (
    BIBLE_VOLUMES,
    BibleQualityAuditChain,
    BookBibleChain,
    WikiDomainChain,
    _balanced_markdown_excerpt,
    _chunk_source_context,
    _static_bible_issues,
)
from obsidian_vault import ObsidianVaultWriter
from vault_context import IncrementalVaultContextBuilder
from editorial_policy import (
    editorial_policy,
    is_documentary_history,
    is_fiction,
    is_historical_fiction,
    is_nonfiction,
)
from structure import FrameworkChain, _framework_issues
from guidance import GuidanceManager
from novelist_agent import NovelistAgent
from web_research import read_public_page, search_duckduckgo


def test_writer_chain_compiles_selected_template_before_base_init():
    with patch("utils.get_llm_model", return_value=FakeListLLM(responses=["Narrative prose with a concrete consequence."])):
        writer = WriterChain(use_few_shot=False)
    assert "CANONICAL BOOK BIBLE" in writer.prompt.template
    assert writer.prompt.template.strip()


def test_writer_rejects_short_assistant_chatter():
    assert WriterChain._looks_like_assistant_chatter("Hello! How can I assist you today?")
    assert not WriterChain._looks_like_assistant_chatter("Mara crossed the threshold and the archive sealed behind her.")


def test_pause_blocks_checkpoint_until_resume():
    control = GenerationControl()
    entered = threading.Event()
    finished = threading.Event()
    control.pause()

    def worker():
        entered.set()
        control.checkpoint()
        finished.set()

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(0.2)
    time.sleep(0.03)
    assert not finished.is_set()
    control.resume()
    thread.join(timeout=1)
    assert finished.is_set()


def test_cancel_raises_at_checkpoint():
    control = GenerationControl()
    control.cancel()
    with pytest.raises(GenerationCancelled):
        control.checkpoint()


def test_live_guidance_moves_from_queue_to_project_log():
    manager = GuidanceManager()
    queued = manager.add("Preserve the disputed date as uncertain.")
    assert not queued["active_generation"]
    assert manager.snapshot()["pending_count"] == 1
    manager.start_generation()
    with tempfile.TemporaryDirectory() as temporary:
        manager.attach_project(Path(temporary))
        manager.add("Add the newly verified archive reference.")
        context = manager.context()
        assert "disputed date" in context
        assert "archive reference" in context
        log = Path(temporary) / ".bookgen" / "guidance.jsonl"
        assert len(log.read_text(encoding="utf-8").splitlines()) == 2
    manager.finish_generation()
    assert not manager.snapshot()["active_generation"]


def test_history_and_historical_fiction_have_distinct_policies():
    assert is_documentary_history("Historia")
    assert not is_documentary_history("Ficcion historica")
    assert is_historical_fiction("Historical fiction")
    assert "Corroborate" in editorial_policy("History")
    assert "Story quality remains primary" in editorial_policy("Historical fiction")


def test_genre_policy_separates_fiction_from_nonfiction_sources():
    assert is_fiction("Fantasia cientifica")
    assert not is_nonfiction("Fantasia cientifica")
    assert is_nonfiction("Divulgacion cientifica")
    assert "Never fabricate or recommend real citations" in editorial_policy("Science fantasy")
    assert "Never invent quotations" in editorial_policy("Popular science")


def test_framework_rejects_premature_chapter_plan_and_fiction_bibliography():
    bad = "## Estructura\nActo 1. Capítulos 1-7.\n## Resolución\nTodo termina.\n## Fuentes recomendadas\nNASA Tech Memo. " + "detalle " * 190
    issues = _framework_issues(bad, "Fantasia cientifica")
    assert any("prematurely plans" in issue for issue in issues)
    assert any("source recommendations" in issue for issue in issues)
    assert any("fixes the ending" in issue for issue in issues)


def test_framework_rejects_downstream_architecture_and_encyclopedia_material():
    bad = (
        "## Personajes principales\nElias lidera la expedicion.\n"
        "## Estructura narrativa\nEl climax destruye el motor y la resolucion restaura la alianza.\n"
        "## Registro de tecnologias\nEl motor produce 500 TW y el escudo consume 200 GW.\n"
        + "detalle " * 190
    )
    issues = _framework_issues(bad, "Fantasia cientifica")
    assert any("story architecture" in issue for issue in issues)
    assert any("encyclopedia material" in issue for issue in issues)
    assert any("arbitrary measurements" in issue for issue in issues)


def test_framework_rejects_named_cast_hidden_in_role_requirements():
    bad = (
        "## **4. Requisitos iniciales de roles de personajes**  \n"
        "| Rol | Funcion |\n|---|---|\n"
        "| **Elias Varga** (protagonista) | Ingeniero dividido entre dos tradiciones. |\n"
        "| **Liora Venn** | Ingeniera de la nave. |\n"
        "## Preguntas tematicas\n" + "pregunta abierta " * 190
    )
    issues = _framework_issues(bad, "Fantasia cientifica")
    assert any("must not invent a named cast" in issue for issue in issues)


def test_framework_rejects_observed_reversed_role_heading_and_language_leaks():
    bad = (
        "## Requisitos Iniciales de Personaje y Roles\n"
        "| Personaje | Rol |\n|---|---|\n"
        "| **Alfredo** | Protagonista |\n| **Liora** | Ingeniera |\n| **Merik** | Lider |\n"
        "## Promesa\n- **Imersion sensorial** completa.\n"
        "## Tensiones\n- **Loyalty vs. Destiny** domina el conflicto.\n"
        "## Estilo\n- **Pacing** alternado.\n" + "detalle " * 190
    )
    issues = _framework_issues(bad, "Fantasia cientifica", "es")
    assert any("must not invent a named cast" in issue for issue in issues)
    assert any("English labels" in issue for issue in issues)
    assert any("Inmersión" in issue for issue in issues)


def test_framework_rejects_observed_character_requirements_bypass_and_placeholders():
    bad = (
        "## Requisitos de Personajes Iniciales\n"
        "| Rol | Descripcion | Preguntas |\n|---|---|---|\n"
        "| **Arion** (Protagonista) | Ingeniero orbital. | Nombre a decidir. |\n"
        "| **Evelyn** | Capitana. | Motivacion a definir. |\n"
        "| **Lucio** | Mago de runas. | Secreto por determinar. |\n"
        "## Mundo\nLa nave *Prometeo* obedece a la Corporacion *AstraTech*.\n"
        + "pregunta abierta " * 190
    )
    issues = _framework_issues(bad, "Fantasia cientifica", "es")
    assert any("must not invent a named cast" in issue for issue in issues)
    assert any("placeholder phrases" in issue for issue in issues)
    assert any("named world entities" in issue for issue in issues)


def test_framework_preserves_names_explicitly_supplied_by_user():
    candidate = (
        "## Requisitos de Personajes Iniciales\n"
        "| Rol | Descripcion |\n|---|---|\n"
        "| **Arion** | Protagonista. |\n| **Evelyn** | Capitana. |\n"
        "## Limites del mundo\nLa nave *Prometeo* pertenece a la Corporacion *AstraTech*.\n"
        + "pregunta abierta " * 190
    )
    issues = _framework_issues(
        candidate,
        "Fantasia cientifica",
        "es",
        user_context="Arion, Evelyn, la Prometeo y AstraTech ya existen.",
    )
    assert not any("named cast" in issue for issue in issues)
    assert not any("named world entities" in issue for issue in issues)


def test_framework_rejects_observed_h1_arc_outcome_drafting_deferral_and_precision():
    candidate = (
        "# El Vortice de los Engranajes\n"
        "## Promesa\nUn protagonista con un arco completo: de la duda cientifica al reconocimiento de su linaje.\n"
        "## Roles\nLos nombres de los personajes secundarios se mantendran en libre desarrollo durante la escritura.\n"
        "## Limites\nLa ingenieria exige precision de escala subnanometrica.\n"
        + "pregunta abierta " * 190
    )
    issues = _framework_issues(candidate, "Fantasia cientifica", "es")
    assert any("level-one heading" in issue for issue in issues)
    assert any("arc outcome" in issue for issue in issues)
    assert any("until drafting" in issue for issue in issues)
    assert any("unsupported precision" in issue for issue in issues)


def test_framework_entity_detection_ignores_lowercase_descriptors_and_vs():
    candidate = (
        "## Premisa\nUna nave estelar cruza el vacio.\n"
        "## Tensiones\nOrden vs. Rebelion divide a la sociedad.\n"
        "La nave estelar, la *Astra Seraphine*, responde a la Orden de los Engranajes.\n"
        + "pregunta abierta " * 190
    )
    issues = _framework_issues(candidate, "Fantasia cientifica", "es")
    entity_issue = next(issue for issue in issues if "named world entities" in issue)
    assert "Astra Seraphine" in entity_issue
    assert "Engranajes" in entity_issue
    assert "estelar" not in entity_issue
    assert "vs" not in entity_issue


def test_framework_rejects_named_cast_hidden_in_markdown_bullets():
    candidate = (
        "## Requisitos iniciales de personajes y roles\n"
        "- **Encris**: protagonista aportado por el usuario.\n"
        "- **Dr. Liora Voss**: astrofisica.\n"
        "- **Sayeris**: mago de la tripulacion.\n"
        "- **El equipo de la expedicion**: roles genericos.\n"
        "- **Antagonistas**: fuerzas genericas.\n"
        + "detalle " * 190
    )
    issues = _framework_issues(
        candidate, "Fantasia cientifica", "es",
        user_context="El protagonista se llama Encris.",
    )
    cast_issue = next(issue for issue in issues if "named cast" in issue)
    assert "Encris" not in cast_issue
    assert "Dr. Liora Voss" in cast_issue
    assert "Sayeris" in cast_issue
    assert "equipo" not in cast_issue
    assert "Antagonistas" not in cast_issue


def test_framework_detects_quoted_expedition_and_deferred_secondary_names():
    candidate = (
        "## Premisa\nLa expedicion “Astra” atraviesa el vortice.\n"
        "## Roles\nLos nombres de los personajes secundarios se mantienen abiertos a desarrollo.\n"
        + "detalle " * 190
    )
    issues = _framework_issues(candidate, "Fantasia cientifica", "es")
    assert any("Astra" in issue and "named world entities" in issue for issue in issues)
    assert any("placeholder phrases" in issue for issue in issues)


def test_framework_quality_uses_bounded_second_repair_and_reports_each_cycle(monkeypatch):
    monkeypatch.setenv("FRAMEWORK_QUALITY_MAX_REPAIRS", "2")
    first = "## Roles\nAliado sin nombre definido.\n" + "detalle " * 190
    second = "## Roles\nAliado unnamed.\n" + "detalle " * 190
    accepted = "## Roles\nAliado funcional cuya identidad se canonizara en la biblia.\n" + "detalle " * 190
    reports = []
    with patch("utils.get_llm_model", return_value=FakeListLLM(responses=[first, second, accepted])):
        result = FrameworkChain().run(
            "Tema", "Fantasia cientifica", "Epico", "Adultos", "Titulo", "es",
            on_quality=lambda cycle, report, candidate: reports.append((cycle, report, candidate)),
        )
    assert result == accepted.strip()
    assert [report["passed"] for _, report, _ in reports] == [False, False, True]


def test_framework_adapts_when_last_cycle_has_a_new_issue(monkeypatch):
    monkeypatch.setenv("FRAMEWORK_QUALITY_MAX_REPAIRS", "1")
    monkeypatch.setenv("FRAMEWORK_ADAPTIVE_REPAIRS", "1")
    first = "## Roles\nAliado sin nombre definido.\n" + "detalle " * 190
    changed = "## Arco\nLa historia culmina en una eleccion final.\n" + "detalle " * 190
    accepted = "## Arco\nLa historia mantiene abierto el resultado.\n" + "detalle " * 190
    reports = []
    with patch.object(FrameworkChain, "invoke", side_effect=[first, changed, accepted]), patch(
        "structure.guidance_manager.context", return_value=""
    ):
        result = FrameworkChain().run(
            "Tema", "Fantasia cientifica", "Epico", "Adultos", "Titulo", "es",
            on_quality=lambda cycle, report, candidate: reports.append(report),
        )
    assert result == accepted
    assert [report["passed"] for report in reports] == [False, False, True]


def test_framework_replays_when_guidance_arrives_during_model_call(monkeypatch):
    monkeypatch.setenv("FRAMEWORK_QUALITY_MAX_REPAIRS", "1")
    monkeypatch.setenv("FRAMEWORK_GUIDANCE_REPLAYS", "1")
    generic = "## Roles\nProtagonista dividido entre dos tradiciones.\n" + "detalle " * 190
    guided = "## Roles\nArcrys es el protagonista vampiro mago.\n" + "detalle " * 190
    reports = []
    contexts = ["", "- Arcrys es un vampiro mago", "- Arcrys es un vampiro mago",
                "- Arcrys es un vampiro mago", "- Arcrys es un vampiro mago",
                "- Arcrys es un vampiro mago"]
    with patch.object(FrameworkChain, "invoke", side_effect=[generic, guided]), patch(
        "structure.guidance_manager.context", side_effect=contexts
    ):
        result = FrameworkChain().run(
            "Tema", "Fantasia cientifica", "Epico", "Adultos", "Titulo", "es",
            on_quality=lambda cycle, report, candidate: reports.append(report),
        )
    assert result == guided
    assert "Live user guidance arrived" in reports[0]["issues"][0]
    assert [report["passed"] for report in reports] == [False, True]


def test_framework_does_not_treat_normal_spanish_todo_as_placeholder():
    candidate = (
        "## Alcance\nEl conflicto afecta a todo el sistema estelar.\n"
        "## Roles\nEl guardian se incluye si aplica y su arco culmina en una eleccion final.\n"
        + "detalle " * 190
    )
    issues = _framework_issues(candidate, "Fantasia cientifica", "es")
    assert any("placeholder phrases" in issue for issue in issues)
    assert any("culminates" in issue for issue in issues)
    clean = candidate.replace(
        "El guardian se incluye si aplica y su arco culmina en una eleccion final.",
        "El guardian plantea una pregunta abierta sobre el conflicto.",
    )
    assert not any("placeholder phrases" in issue for issue in _framework_issues(
        clean, "Fantasia cientifica", "es"
    ))


def test_framework_allows_negative_ending_reference_and_complete_arc_promise():
    candidate = (
        "## Promesa\nLa experiencia culmina en un arco completo, sin revelar el desenlace.\n"
        + "detalle " * 190
    )
    issues = _framework_issues(candidate, "Fantasia cientifica", "es")
    assert not any("story architecture" in issue for issue in issues)
    assert not any("culminates" in issue for issue in issues)


def test_guidance_ui_uses_only_canonical_server_activity_event():
    html = (Path(__file__).parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    handler = html.split("byId('guidance-form').addEventListener", 1)[1].split(
        "function startMatrixBackground", 1
    )[0]
    assert "await pollActivity();" in handler
    assert "guidanceSent}: ${message}" not in handler
    assert "if (data.cursor_reset) lastActivitySequence = 0;" in html


def test_static_bible_gate_catches_observed_volume_and_source_failures(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Volumen 1 - Personas\nLos personajes avanzan.\n"
        "## Fuentes recomendadas\nDatos basados en fuentes académicas verificables y NASA Tech Memo."
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica")
    assert any("volume number" in issue for issue in issues)
    assert any("scholarship" in issue for issue in issues)


def test_foundation_gate_rejects_observed_scope_drift_and_fake_precision(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Premisa\nUna expedicion combina ciencia y magia.\n"
        "## Personajes principales\nElias y Mara dirigen la nave.\n"
        "## Ledger de tecnologias\nEl motor usa 500 TW y el transmisor 10 GW.\n"
        "## Linea de tiempo\nEl consorcio nace en el ano cero.\n"
        "## Fuentes de la historia\nUn diario interno acredita los hechos.\n"
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica", volume_index=1)
    assert any("editorial scope" in issue for issue in issues)
    assert any("exact fictional measurements" in issue for issue in issues)


def test_foundation_gate_rejects_repaired_scope_drift_policy_negation_and_language(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Premisa\nAlfredo debe elegir entre dos tradiciones.\n"
        "## Limites y reglas del mundo\n### Tecnologia\nSe detallan motores y escudos.\n"
        "## Notas de construccion para el agente\n"
        "1. **Objetos clave**: artefacto y escudo.\n"
        "2. **Organizaciones**: Orden y Consorcio.\n"
        "3. **Relaciones temporales**: el viaje dura varios anos.\n"
        "## Estilo\n**Pacing** alternado e **Imersion** sensorial.\n"
        "- No cumplir con la politica de citas reales.\n"
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica", volume_index=1, language="es")
    assert any("encyclopedia/story material" in issue for issue in issues)
    assert any("negate" in issue for issue in issues)
    assert any("English labels" in issue for issue in issues)
    assert any("Inmersión" in issue for issue in issues)


def test_foundation_gate_rejects_observed_synopsis_and_reversed_cast_table(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Premisa\nCiencia y magia compiten por controlar el viaje.\n"
        "## Sinopsis\nLa Prometeo parte, descubre una reliquia y obliga a Arion a elegir un bando.\n"
        "## Requisitos de Personajes Iniciales\n"
        "| Rol | Descripcion | Preguntas |\n|---|---|---|\n"
        "| **Arion** | Ingeniero orbital. | Que desea? |\n"
        "| **Evelyn** | Capitana. | Que oculta? |\n"
        "## Estructura narrativa\nPreparacion, revelacion y resolucion.\n"
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica", volume_index=1, language="es")
    assert any("editorial scope" in issue for issue in issues)
    assert any("encyclopedia/story material" in issue for issue in issues)


def test_foundation_allows_high_level_boundary_labels_but_rejects_observed_precision(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    high_level = (
        "## Premisa\nCiencia y magia deben coexistir.\n"
        "## Limites del mundo\n**Magia**: tiene un coste.\n**Tecnologia**: funciona sin magia.\n"
        "## Preguntas\nComo cambia su relacion?\n"
    )
    assert not any(
        "encyclopedia/story material" in issue
        for issue in _static_bible_issues(high_level, "Fantasia cientifica", 1, "es")
    )

    precise = high_level + (
        "## Detalles\nEl motor opera a 10¹² Hz, tolera 0.005 nanometros, genera 20 newtons "
        "y falla al 70%.\n"
    )
    issues = _static_bible_issues(precise, "Fantasia cientifica", 1, "es")
    assert any("exact fictional measurements" in issue for issue in issues)


def test_foundation_rejects_fixed_arc_solution_and_observed_language_leaks(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Promesa\nAlfredo tiene un arco completo: de la duda al reconocimiento de su linaje.\n"
        "## Tensiones\n**Conflito interno** entre deber y deseo.\n"
        "## Scope y evidencias\nLa solucion requiere integrar ciencia y magia.\n"
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica", 1, "es")
    assert any("story or character-arc solution" in issue for issue in issues)
    assert any("English labels" in issue for issue in issues)
    assert any("Portuguese" in issue for issue in issues)


def test_people_volume_flags_ambiguous_shared_parent_claim(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    candidate = (
        "## Alfredo - El astromago\nSu padre, **Jorlan**, fue asesinado por Eris.\n"
        "## Eris - El renegado\nEl asesinato de Jorlan, su padre, lo marco profundamente.\n"
        + "detalle " * 20
    )
    issues = _static_bible_issues(candidate, "Fantasia cientifica", volume_index=2, language="es")
    assert any("shared-parent relationship" in issue for issue in issues)


def test_bible_quality_gate_repairs_before_accepting(monkeypatch):
    monkeypatch.setenv("BIBLE_VOLUME_MIN_WORDS", "10")
    monkeypatch.setenv("BIBLE_QUALITY_MAX_REPAIRS", "2")
    bad = "## Volumen 1\nFuentes académicas verificables. " + "detalle " * 20
    repaired = "## Canon coherente\n" + "detalle " * 30
    reports = []
    audits = [
        {"verdict": "repair", "issues": [{"problem": "Elias is both dead and active."}]},
        {"verdict": "pass", "issues": []},
    ]
    with patch("book_bible.BibleQualityAuditChain.run", side_effect=audits), patch(
        "book_bible.BibleVolumeRepairChain.run", return_value=repaired
    ) as repair:
        accepted = BookBibleChain._quality_gate(
            bad, BIBLE_VOLUMES[0][0], 1, BIBLE_VOLUMES[0][1], "Premise",
            "Fantasia cientifica", "Framework", "No prior canon", "es",
            lambda *args: reports.append(args[4]),
        )
    assert accepted == repaired
    assert repair.call_count == 2
    assert [report["passed"] for report in reports] == [False, False, True]


def test_bible_auditor_accepts_strict_json_and_normalizes_verdict():
    response = '{"verdict":"PASS","issues":[]}'
    with patch("utils.get_llm_model", return_value=FakeListLLM(responses=[response])):
        result = BibleQualityAuditChain().run(
            "Foundation", 1, 6, "Coverage", "Premise", "Science fiction",
            "Framework", "No prior canon", "## Candidate\nConcrete canon.", "en",
        )
    assert result == {"verdict": "pass", "issues": []}


def test_wiki_domain_repairs_semantic_taxonomy_before_accepting(monkeypatch):
    monkeypatch.setenv("WIKI_ITEM_MIN_WORDS", "5")
    monkeypatch.setenv("WIKI_QUALITY_MAX_REPAIRS", "2")
    first = '{"items":[{"name":"Planeta Eterna","subtype":"planet","summary":"A planet.","details":"## Detail\\nUseful canonical detail for the planet.","relationships":[]}]}'
    second = '{"items":[{"name":"Concordia","subtype":"order","summary":"An order.","details":"## Detail\\nUseful canonical detail for the established order.","relationships":[]}]}'
    audits = [
        {"verdict": "repair", "issues": [{"problem": "A planet is not an organization."}]},
        {"verdict": "pass", "issues": []},
    ]
    with patch("utils.get_llm_model", return_value=FakeListLLM(responses=[first, second])), patch(
        "book_bible.WikiQualityAuditChain.run", side_effect=audits
    ):
        items = WikiDomainChain().run("organizations", "1-2 organizations", "Canon", "en")
    assert [item["name"] for item in items] == ["Concordia"]


def test_balanced_markdown_excerpt_keeps_late_sections_visible():
    source = "\n\n".join(f"## Section {index}\n" + (str(index) * 200) for index in range(1, 8))
    excerpt = _balanced_markdown_excerpt(source, 700)
    assert len(excerpt) <= 700
    assert "## Section 1" in excerpt
    assert "## Section 7" in excerpt


def test_duckduckgo_search_parses_real_source_metadata_without_network():
    html = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Farchive">Archive record</a>
    <a class="result__snippet">A primary-source catalogue entry.</a>
    """
    response = type("Response", (), {"text": html, "raise_for_status": lambda self: None})()
    with patch("web_research.requests.get", return_value=response) as request_mock:
        results = search_duckduckgo("documented event", 3)
    assert results == [{
        "title": "Archive record", "url": "https://example.org/archive",
        "snippet": "A primary-source catalogue entry.",
    }]
    assert request_mock.call_args.kwargs["params"] == {"q": "documented event"}


def test_author_agent_exposes_web_tool_only_when_enabled():
    with tempfile.TemporaryDirectory() as temporary:
        project = ObsidianVaultWriter().create(
            temporary, "Research Book", "en", {}, "Framework", book_bible="Canon."
        )
        disabled = NovelistAgent(project, object(), genre="History", web_search_enabled=False)
        enabled = NovelistAgent(project, object(), genre="History", web_search_enabled=True)
        disabled_names = {item["function"]["name"] for item in disabled.tool_schemas}
        enabled_names = {item["function"]["name"] for item in enabled.tool_schemas}
        assert "search_web" not in disabled_names
        assert "read_web_page" not in disabled_names
        assert "record_research_source" not in disabled_names
        assert "search_web" in enabled_names
        assert "read_web_page" in enabled_names
        result = enabled.tools.record_research_source(
            "Archive record", "https://example.org/archive", "The event date", "Primary catalogue lead"
        )
        assert "Recorded source" in result
        ledger = enabled.project.root / enabled.project.read_manifest()["paths"]["research"] / "Web Sources.md"
        assert "https://example.org/archive" in ledger.read_text(encoding="utf-8")


def test_web_page_reader_blocks_private_addresses_before_request():
    with pytest.raises(ValueError, match="Local web addresses"):
        read_public_page("http://localhost/private")


def test_source_context_chunking_preserves_all_markdown_sections():
    source = "\n\n".join(
        f"## Chapter {index}\n\nMARKER-{index} " + ("detail " * 300)
        for index in range(1, 13)
    )
    chunks = _chunk_source_context(source, target_chars=6000, max_chunks=5)
    joined = "\n".join(chunks)
    assert 1 < len(chunks) <= 5
    for index in range(1, 13):
        assert f"MARKER-{index}" in joined


def test_incremental_vault_index_only_resummarizes_changed_files():
    with tempfile.TemporaryDirectory() as temporary:
        project = ObsidianVaultWriter().create(
            temporary, "Indexed Book", "en", {}, "Framework", book_bible="Canon."
        )

        def summarize(records, _language):
            return {item["path"]: f"Summary for {item['path']}" for item in records}

        with patch("vault_context.SourceFileBatchChain.run", side_effect=summarize), patch(
            "vault_context.SourceVaultDigestChain.run", return_value="## Canonical dossier\nDetailed reusable canon."
        ), patch("vault_context.SourceIntentChain.run", return_value="## Operational brief\nApply the request."):
            _, first = IncrementalVaultContextBuilder().build(project, "revise", "indexed-book", "Edit", "en")
        assert first["strategy"] == "full-rebuild"

        status_path = project.root / f"{project.read_manifest()['paths']['status']}.md"
        status_path.write_text(status_path.read_text(encoding="utf-8") + "\nNew context fact.\n", encoding="utf-8")
        seen = []

        def summarize_delta(records, _language):
            seen.extend(item["path"] for item in records)
            return {item["path"]: f"Updated summary for {item['path']}" for item in records}

        with patch("vault_context.SourceFileBatchChain.run", side_effect=summarize_delta), patch(
            "vault_context.SourceVaultDigestChain.run"
        ) as full_rebuild, patch(
            "vault_context.SourceDossierUpdateChain.run", return_value="## Updated dossier\nPreserved canon plus the delta."
        ), patch("vault_context.SourceIntentChain.run", return_value="## Operational brief\nApply the request."):
            _, second = IncrementalVaultContextBuilder().build(project, "revise", "indexed-book", "Edit", "en")
        assert second["strategy"] == "incremental-update"
        assert seen == [status_path.relative_to(project.root).as_posix()]
        full_rebuild.assert_not_called()
