from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response, parse_model_string
from chapter_summary import ChapterSummaryChain, ProgressiveContextManager
from emergency_prompts import emergency_prompts
from example_library import ExampleLibrary
from section_quality_monitor import SectionQualityMonitor
import re
import random
import logging
import time  # Importación añadida para usar time.sleep()
import os    # Importación añadida para variables de entorno

# FASE 4: Importar configuración centralizada
from config.defaults import get_config
from retry_strategy import RetryStrategy, RetryableException
from language import language_instruction, normalize_language
from generation_control import GenerationCancelled, generation_control

# Obtener configuración
_config = get_config()
_context_config = _config.context
_rate_limit_config = _config.rate_limit
_summary_config = _config.summary

logger = logging.getLogger(__name__)

def _resolve_provider_name() -> str:
    model_type = os.environ.get("MODEL_TYPE", "").strip().lower()
    if model_type:
        return model_type
    selected_model = os.environ.get("SELECTED_MODEL", "").strip()
    if selected_model:
        provider, _ = parse_model_string(selected_model)
        if provider:
            return provider.lower()
    return "ollama"


def _sanitize_snippet(text: str, max_len: int = 120) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) > max_len:
        return cleaned[:max_len].rstrip() + "..."
    return cleaned


def _select_bible_context(book_bible: str, chapter_title: str, current_idea: str) -> str:
    """Select relevant bible sections instead of spending context on the entire vault note."""
    if not book_bible:
        return ""
    limit = max(_context_config.global_context_size, 800)
    sections = re.split(r"(?m)(?=^##\s+)", book_bible)
    terms = {
        word.casefold()
        for word in re.findall(r"\b[\w'-]{4,}\b", f"{chapter_title} {current_idea}")
    }
    ranked = []
    for index, section in enumerate(sections):
        folded = section.casefold()
        score = sum(1 for term in terms if term in folded)
        if "creative north star" in folded or "continuity ledger" in folded:
            score += 2
        ranked.append((score, -index, section.strip()))
    selected = []
    used = 0
    for _, _, section in sorted(ranked, reverse=True):
        if not section:
            continue
        remaining = limit - used
        if remaining <= 0:
            break
        selected.append(section[:remaining])
        used += min(len(section), remaining)
    return "\n\n".join(selected)


def _build_fallback_section_text(
    chapter_title: str,
    idea: str,
    genre: str,
    style: str,
    section_position: str,
    language: str = "en",
) -> str:
    language = normalize_language(language)
    chapter_hint = _sanitize_snippet(chapter_title, 80) or ("el capitulo actual" if language == "es" else "the current chapter")
    idea_hint = _sanitize_snippet(idea, 120) or ("un giro importante" if language == "es" else "an important turn")
    genre_hint = _sanitize_snippet(genre, 40) or ("la historia" if language == "es" else "the story")
    style_hint = _sanitize_snippet(style, 40) or ("un tono narrativo claro" if language == "es" else "a clear narrative tone")

    templates_es = {
        "inicio": [
            "Con el inicio de {chapter_hint}, {idea_hint} comienza a tomar forma, marcando el rumbo de {genre_hint}.",
            "El capitulo abre con {idea_hint}, presentando el conflicto principal y el estilo de {style_hint}."
        ],
        "medio": [
            "La tension crece mientras {idea_hint} se desarrolla en {chapter_hint}, con decisiones que cambian el rumbo.",
            "En el centro de {chapter_hint}, {idea_hint} empuja a los personajes a actuar y sostener {genre_hint}."
        ],
        "final": [
            "Hacia el cierre de {chapter_hint}, {idea_hint} deja un impacto que prepara el siguiente paso.",
            "El capitulo concluye con {idea_hint}, reforzando el tono de {style_hint} y abriendo nuevas preguntas."
        ],
        "default": [
            "La historia avanza en {chapter_hint} mientras {idea_hint} redefine las prioridades del grupo.",
            "En {chapter_hint}, {idea_hint} mantiene el impulso narrativo con {genre_hint} como telon de fondo."
        ]
    }
    templates_en = {
        "inicio": [
            "As {chapter_hint} opens, {idea_hint} begins to take shape and sets the direction of {genre_hint}.",
            "The chapter opens with {idea_hint}, establishing its conflict in {style_hint}.",
        ],
        "medio": [
            "Tension rises as {idea_hint} develops in {chapter_hint}, forcing decisions that alter the course ahead.",
            "At the center of {chapter_hint}, {idea_hint} pushes the characters to act and sustains {genre_hint}.",
        ],
        "final": [
            "Near the close of {chapter_hint}, {idea_hint} leaves consequences that prepare the next movement.",
            "The chapter closes with {idea_hint}, reinforcing {style_hint} while opening a consequential question.",
        ],
        "default": [
            "The story advances in {chapter_hint} as {idea_hint} changes the group's priorities.",
            "In {chapter_hint}, {idea_hint} maintains narrative momentum against the backdrop of {genre_hint}.",
        ],
    }
    templates = templates_es if language == "es" else templates_en

    key = section_position if section_position in templates else "default"
    seed = hash((chapter_hint, idea_hint, key)) & 0xFFFFFFFF
    rng = random.Random(seed)
    template = rng.choice(templates[key])
    return template.format(
        chapter_hint=chapter_hint,
        idea_hint=idea_hint,
        genre_hint=genre_hint,
        style_hint=style_hint
    )

class WriterChain(BaseEventChain):
    # Template zero-shot original
    ZERO_SHOT_TEMPLATE = """
    You are a professional long-form author working in {genre}.
    {language_instruction}
    
    ### CANONICAL BOOK BIBLE:
    {book_bible}

    ### ESSENTIAL INFORMATION:
    - Title: "{title}"
    - Style: {style}
    - Current chapter: {chapter_title} ({current_chapter} of {total_chapters})
    - Position: {section_position}
    
    ### COMPACT CONTEXT:
    {summary}

    ### AUTHOR AGENT VAULT AND SOURCE RESEARCH:
    {agent_context}
    
    ### RECENT PROSE:
    {previous_paragraphs}
    
    ### SECTION OBJECTIVE TO WRITE NOW:
    {current_idea}
    
    Genre rule: History/Historia is factual historiography and requires verified, qualified
    claims. Historical fiction/Ficcion historica may invent story material while keeping
    relevant real-world context credible. Continue directly from the recent prose. For fiction, preserve canon, point of view,
    tense, motivations, and unresolved threads, and dramatize rather than summarize. For
    nonfiction, write clear, accurate, evidence-aware prose that advances the section's claim,
    chronology, explanation, or instruction; distinguish uncertainty and never invent facts,
    quotations, citations, or sources. Return only polished book prose without meta-commentary.

    Book prose:"""

    # Nuevo template few-shot con ejemplos
    FEW_SHOT_TEMPLATE = """
    You are a professional long-form author working in {genre}.
    {language_instruction}
    
    ### CANONICAL BOOK BIBLE:
    {book_bible}

    ### ESSENTIAL INFORMATION:
    - Title: "{title}"
    - Style: {style}
    - Current chapter: {chapter_title} ({current_chapter} of {total_chapters})
    - Position: {section_position}
    
    ### REFERENCE EXAMPLES:
    
    Use these only as quality and technique references. Do not copy their facts or wording:
    
    {examples}
    
    ### COMPACT CONTEXT:
    {summary}

    ### AUTHOR AGENT VAULT AND SOURCE RESEARCH:
    {agent_context}
    
    ### RECENT PROSE:
    {previous_paragraphs}
    
    ### SECTION OBJECTIVE TO WRITE NOW:
    {current_idea}
    
    Genre rule: History/Historia is factual historiography and requires verified, qualified
    claims. Historical fiction/Ficcion historica may invent story material while keeping
    relevant real-world context credible. Continue directly from the recent prose. For fiction, preserve canon, point of view,
    tense, motivations, and unresolved threads, and dramatize rather than summarize. For
    nonfiction, write clear, accurate, evidence-aware prose that advances the section's claim,
    chronology, explanation, or instruction; distinguish uncertainty and never invent facts,
    quotations, citations, or sources. Return only polished book prose without meta-commentary.

    Book prose:"""
    
    def __init__(self, use_few_shot: bool = True):
        """
        Args:
            use_few_shot: Si True, usa prompts con ejemplos. Si False, usa zero-shot.
        """
        self.use_few_shot = use_few_shot
        if self.use_few_shot:
            self.PROMPT_TEMPLATE = self.FEW_SHOT_TEMPLATE
        else:
            self.PROMPT_TEMPLATE = self.ZERO_SHOT_TEMPLATE
        # BaseChain compiles PROMPT_TEMPLATE, so the selected template must exist first.
        super().__init__()
        if self.use_few_shot:
            self.example_library = ExampleLibrary()

    def run(
        self,
        genre,
        style,
        title,
        context_manager,
        chapter_title,
        summary,
        previous_paragraphs,
        current_idea,
        current_chapter,
        total_chapters,
        section_position,
        section_number,
        total_sections,
        chapter_key,
        language="en",
        book_bible="",
        agent_context="",
    ):
        print_progress(f"Escribiendo sección {section_number}/{total_sections} del capítulo {current_chapter}")
        
        try:
            # Limpiar todas las entradas de posibles cadenas de pensamiento
            summary_clean = clean_think_tags(summary)
            previous_paragraphs_clean = clean_think_tags(previous_paragraphs)
            current_idea_clean = clean_think_tags(current_idea)
            
            # FASE 4: Usar configuración en lugar de valores mágicos
            # Optimizar longitud del contexto para evitar sobrecarga
            if len(previous_paragraphs_clean) > _context_config.limited_context_size:
                previous_paragraphs_clean = previous_paragraphs_clean[-_context_config.limited_context_size:] 
            
            # NUEVO: Obtener ejemplos relevantes si few-shot está activado
            examples_text = ""
            if self.use_few_shot:
                examples_text = self._get_formatted_examples(
                    genre=genre,
                    style=style,
                    section_position=section_position,
                    language=language,
                )
            
            # Invocar con o sin ejemplos según configuración
            invoke_params = {
                'genre': clean_think_tags(genre),
                'style': clean_think_tags(style),
                'title': clean_think_tags(title),
                'chapter_title': clean_think_tags(chapter_title),
                'summary': summary_clean,
                'previous_paragraphs': previous_paragraphs_clean,
                'current_idea': current_idea_clean,
                'current_chapter': current_chapter,
                'total_chapters': total_chapters,
                'section_position': section_position,
                'section_number': section_number,
                'total_sections': total_sections
                , 'language_instruction': language_instruction(language)
                , 'book_bible': clean_think_tags(_select_bible_context(book_bible, chapter_title, current_idea))
                , 'agent_context': clean_think_tags(agent_context)[-_context_config.standard_context_size:]
            }
            
            # Solo añadir ejemplos si estamos usando few-shot
            if self.use_few_shot:
                invoke_params['examples'] = examples_text
            
            result = self.invoke(**invoke_params)
            if self._looks_like_assistant_chatter(result):
                raise ValueError("The model returned assistant chatter instead of book prose")
            
            # El resultado ya viene limpio por el invoke() de BaseChain
            print_progress(f"Sección completada: {len(result)} caracteres")
            return result

        except Exception as e:
            print_progress(f"Error generando contenido: {str(e)}")
            logger.error(
                "writer chain failed",
                extra={"operation": "section_generation", "error": str(e)}
            )
            raise

    @staticmethod
    def _looks_like_assistant_chatter(text: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(text)).strip().casefold()
        markers = (
            "how can i assist you",
            "how can i help you",
            "your message might have been empty",
            "your message didn’t come through",
            "your message didn't come through",
            "feel free to let me know",
        )
        return len(normalized) < 500 and any(marker in normalized for marker in markers)
    
    def _get_formatted_examples(
        self, 
        genre: str, 
        style: str, 
        section_position: str,
        language: str = "en",
    ) -> str:
        """
        Recupera y formatea ejemplos relevantes para el prompt.
        
        Args:
            genre: Género del libro
            style: Estilo de escritura
            section_position: inicio/medio/final
            
        Returns:
            String formateado con 1-2 ejemplos
        """
        try:
            # Obtener número máximo de ejemplos desde configuración
            max_examples = _config.few_shot.max_examples_per_prompt
            
            # Obtener ejemplos de la biblioteca
            examples = self.example_library.get_examples(
                genre=genre,
                style=style,
                section_type=section_position,
                max_examples=max_examples,
                language=language,
            )
            
            if not examples:
                # Fallback: buscar sin filtro de tipo
                examples = self.example_library.get_examples(
                    genre=genre,
                    style=style,
                    max_examples=max_examples,
                    language=language,
                )
            
            if not examples:
                return "[No hay ejemplos disponibles para este género/estilo]"
            
            # Formatear ejemplos para el prompt
            formatted = []
            for i, ex in enumerate(examples, 1):
                formatted.append(f"""
**EJEMPLO {i}:**

Contexto previo:
{ex.context}

Idea desarrollada:
{ex.idea}

Texto generado:
{ex.content}

---
""")
            
            return "\n".join(formatted)
            
        except Exception as e:
            print_progress(f"⚠️ Error obteniendo ejemplos: {str(e)}")
            logger.warning(
                "example retrieval failed",
                extra={"operation": "few_shot_examples", "error": str(e)}
            )
            return "[Error cargando ejemplos]"

def regenerate_problematic_section(writer_chain, context_manager, section_params, max_attempts=3):
    """
    Intenta regenerar una sección que ha mostrado problemas o señales de colapso.
    Ahora usa el sistema centralizado de prompts de emergencia.
    """
    print_progress("🔄 Intentando regenerar sección problemática...")
    
    # Extractores de parámetros clave
    chapter_title = section_params.get('chapter_title', 'este capítulo')
    current_idea = section_params.get('current_idea', '')
    
    try:
        # Usar prompt de emergencia centralizado en lugar de lógica de reintentos manual
        emergency_prompt = emergency_prompts.get_section_regeneration_prompt(
            context_summary=f"Capítulo: {chapter_title}",
            previous_content=section_params.get('previous_paragraphs', '')[:200]
        )
        
        # Ejecutar con el sistema de reintentos integrado en BaseChain
        response = writer_chain.llm.invoke(emergency_prompt)
        content = clean_think_tags(extract_content_from_llm_response(response))
        
        if content and len(content.strip()) >= _summary_config.section_min_chars:
            print_progress("✅ Regeneración exitosa usando prompt de emergencia")
            return content
            
    except Exception as e:
        print_progress(f"Error en regeneración con prompt de emergencia: {str(e)}")
        logger.warning(
            "section regeneration failed",
            extra={"operation": "section_regeneration", "error": str(e)}
        )
    
    # Si todo falla, usar texto de contingencia
    print_progress("⚠️ Usando texto de contingencia tras fallo de regeneración")
    return _build_fallback_section_text(
        chapter_title=chapter_title,
        idea=current_idea,
        genre="",
        style="",
        section_position="medio"
    )

def create_savepoint_summary(llm, title, chapter_num, chapter_title, current_summary, new_section, total_chapters=None, language="en"):
    """
    Sistema simplificado y autónomo para crear resúmenes incrementales como puntos de guardado.
    No depende de ChapterSummaryChain, evitando así los errores de parámetros faltantes.
    """
    print_progress(f"Actualizando resumen del capítulo {chapter_num} para savepoint...")
    
    try:
        # Si no hay resumen previo, crear uno básico
        if not current_summary or current_summary.strip() == "":
            current_summary = f"Inicio del capítulo {chapter_num}: {chapter_title}"
        safe_new_section = new_section or ""
        
        # Si la nueva sección es muy larga, limitarla para el análisis
        section_limit = _summary_config.savepoint_section_max_chars
        if len(safe_new_section) > section_limit:
            head_len = section_limit // 2
            tail_len = section_limit - head_len
            summary_section = safe_new_section[:head_len] + "\n\n[...]\n\n" + safe_new_section[-tail_len:]
        else:
            summary_section = safe_new_section
            
        # Prompt directo y simple para generar el resumen
        prompt = f"""
        Update the existing continuity summary with only the essential changes from the
        new section. Keep concrete facts, decisions, revelations, relationship changes,
        unresolved threads, and the final state. Maximum 150 words.
        {language_instruction(language)}

        Title: {clean_think_tags(title)}
        Chapter: {clean_think_tags(chapter_title)} ({chapter_num})

        Current summary:
        {clean_think_tags(current_summary)}

        New section:
        {clean_think_tags(summary_section)}

        Updated continuity summary:
        """
        
        try:
            retry_strategy = RetryStrategy()

            def _invoke_summary():
                result = llm.invoke(prompt)
                text_result = extract_content_from_llm_response(result)
                updated = clean_think_tags(text_result)
                if not updated or len(updated.strip()) < _summary_config.savepoint_summary_min_chars:
                    raise RetryableException("Resumen vacio o muy corto")
                return updated

            updated_summary = retry_strategy.execute(_invoke_summary)
            if len(updated_summary) > _summary_config.savepoint_summary_max_chars:
                updated_summary = updated_summary[:_summary_config.savepoint_summary_max_chars] + "..."
            return updated_summary

        except Exception as e:
            print_progress(f"Error creando resumen: {str(e)}")
            logger.error(
                "savepoint summary failed",
                extra={"operation": "savepoint_summary", "chapter": chapter_num, "error": str(e)}
            )
            # Usar prompt de emergencia como fallback
            try:
                emergency_prompt = emergency_prompts.get_summary_emergency_prompt(
                    safe_new_section[:_summary_config.savepoint_emergency_section_chars]
                )
                emergency_result = llm.invoke(emergency_prompt)
                emergency_summary = clean_think_tags(extract_content_from_llm_response(emergency_result))
                if emergency_summary and len(emergency_summary.strip()) >= _summary_config.savepoint_summary_min_chars:
                    if len(emergency_summary) > _summary_config.savepoint_summary_max_chars:
                        emergency_summary = emergency_summary[:_summary_config.savepoint_summary_max_chars] + "..."
                    return emergency_summary
                print_progress("No se pudo generar un nuevo resumen, manteniendo el actual")
                return current_summary
            except Exception as emergency_error:
                # Si todo falla, devolver el resumen actual sin cambios
                logger.error(
                    "savepoint emergency summary failed",
                    extra={"operation": "savepoint_summary", "chapter": chapter_num, "error": str(emergency_error)}
                )
                print_progress("No se pudo generar un nuevo resumen, manteniendo el actual")
                return current_summary
        
    except Exception as e:
        print_progress(f"Error creando savepoint: {str(e)}")
        logger.error(
            "savepoint summary crashed",
            extra={"operation": "savepoint_summary", "chapter": chapter_num, "error": str(e)}
        )
        return current_summary  # En caso de error, devolver el resumen anterior

def _ordered_progressive_chapters(idea_dict):
    """Return a strict chapter order; never silently draft across a numbered gap."""
    from chapter_ordering import ChapterOrdering, ChapterType

    ordering = ChapterOrdering(strict_mode=True)
    metadata = [
        ordering.parse_chapter(key, index)
        for index, key in enumerate(idea_dict)
    ]
    numbers = sorted(
        item.number for item in metadata
        if item.type == ChapterType.NUMBERED and item.number is not None
    )
    if numbers and numbers[0] != 1:
        raise ValueError(
            f"Numbered chapter sequence must start at 1 before drafting; found {numbers[0]}"
        )
    return ordering.sort_chapters(idea_dict)


def _completed_chapter_context(context_manager, next_chapter_number: int, language: str) -> str:
    """Build bounded cumulative context with the immediately previous chapter kept intact."""
    context = context_manager.get_context_for_next_chapter(next_chapter_number)
    previous = str(context.get("previous_chapter", "")).strip()
    global_summary = str(context.get("global_summary", "")).strip()
    if not previous and not global_summary:
        return ""

    previous_label = "Capitulo anterior completado" if language == "es" else "Completed previous chapter"
    global_label = "Continuidad acumulada" if language == "es" else "Cumulative continuity"
    previous_block = f"### {previous_label}\n{previous}" if previous else ""
    limit = max(_context_config.standard_context_size, 1200)
    remaining = max(0, limit - len(previous_block) - 4)
    global_block = (
        f"### {global_label}\n{global_summary[:remaining]}"
        if global_summary and remaining
        else ""
    )
    return "\n\n".join(block for block in (global_block, previous_block) if block)


def _merge_progressive_context(current_summary: str, completed_context: str) -> str:
    current = str(current_summary).strip()
    if not completed_context:
        return current
    return f"{completed_context}\n\n### Current chapter plan and state\n{current}".strip()


def write_book(
    genre, style, profile, title, framework, summaries_dict, idea_dict,
    chapter_summaries=None, language="en", book_bible="", on_chapter_complete=None,
    vault_project=None, agent_tools=True, web_search=False,
):
    print_progress("Iniciando escritura del libro...")
    language = normalize_language(language)
    
    # NUEVO: Usar configuración centralizada para few-shot learning
    config = _config
    few_shot_config = config.few_shot
    
    # Inicializar monitor de calidad con configuración
    quality_monitor = SectionQualityMonitor(
        quality_threshold=few_shot_config.quality_threshold,
        auto_save=few_shot_config.auto_save_examples
    )
    
    # Inicializar WriterChain con configuración few-shot
    writer_chain = WriterChain(use_few_shot=few_shot_config.enabled)
    book = {}

    provider_name = _resolve_provider_name()
    provider_delay = _rate_limit_config.get_delay(provider_name)
    logger.info(
        "rate limit resolved",
        extra={"operation": "rate_limit", "provider": provider_name, "delay": provider_delay}
    )

    summary_quality_evaluator = None
    try:
        from summary_quality import SummaryQualityEvaluator
        summary_quality_evaluator = SummaryQualityEvaluator()
    except Exception as e:
        logger.warning(
            "summary quality evaluator not available",
            extra={"operation": "savepoint_quality", "error": str(e)}
        )
    
    # Si no hay resúmenes de capítulos, crear un diccionario vacío
    if chapter_summaries is None:
        chapter_summaries = {}

    # NUEVO: Inicializar el gestor de contexto con sistema dinámico
    try:
        from dynamic_context import DynamicContextCalculator
        
        # Intentar detectar el modelo desde variables de entorno
        model_type = os.environ.get("MODEL_TYPE", "ollama").strip().lower() or "ollama"
        model_name = "unknown"
        selected_model = os.environ.get("SELECTED_MODEL", "").strip()
        if selected_model:
            parsed_provider, parsed_model = parse_model_string(selected_model)
            if parsed_provider:
                model_type = parsed_provider
            model_name = parsed_model or model_name
        else:
            model_name = os.environ.get(f"{model_type.upper()}_MODEL", model_name)
        
        # Crear calculador dinámico
        context_calc = DynamicContextCalculator(model_name, model_type)
        
        # Inicializar contexto manager con perfil dinámico y LLM
        context_manager = ProgressiveContextManager(
            framework=framework,
            llm=writer_chain.llm,  # Pasar LLM para micro-resúmenes
            enable_micro_summaries=_context_config.enable_micro_summaries,
            micro_summary_interval=_context_config.micro_summary_interval,
            model_profile=context_calc.profile,
            context_calculator=context_calc,
            max_context_size=_context_config.limited_context_size
            , language=language
        )
        
        print_progress("🧠 Sistema de contexto dinámico inicializado")
        
    except Exception as e:
        print_progress(f"⚠️ Error inicializando contexto dinámico: {e}")
        logger.warning(
            "dynamic context init failed",
            extra={"operation": "dynamic_context", "error": str(e)}
        )
        print_progress("🔄 Usando sistema de contexto tradicional")
        context_manager = ProgressiveContextManager(
            framework=framework,
            llm=writer_chain.llm,
            enable_micro_summaries=_context_config.enable_micro_summaries,
            micro_summary_interval=_context_config.micro_summary_interval,
            max_context_size=_context_config.limited_context_size
            , language=language
        )
    
    summary_chain = ChapterSummaryChain()
    novelist_agent = None
    if agent_tools and vault_project is not None:
        try:
            from novelist_agent import NovelistAgent
            novelist_agent = NovelistAgent(
                vault_project, writer_chain.llm, language=language,
                web_search_enabled=web_search, genre=genre,
            )
            print_progress(f"Author agent tools enabled (web search: {'on' if web_search else 'off'})")
        except Exception as error:
            logger.warning("novelist agent unavailable", extra={"operation": "agent_init", "error": str(error)})

    try:
        total_chapters = len(idea_dict)
        
        ordered_chapters = _ordered_progressive_chapters(idea_dict)
        
        # Procesar capítulos en el orden establecido
        for i, chapter in enumerate(ordered_chapters, 1):
            generation_control.checkpoint()
            idea_list = idea_dict[chapter]
            completed_context = _completed_chapter_context(context_manager, i, language)
            
            print_progress("======================================")
            print_progress(f"CAPÍTULO {i}/{total_chapters}: {chapter}")
            print_progress("======================================")
            
            book[chapter] = []
            ideas_total = len(idea_list)
            chapter_content = []
            
            # Obtener resumen del capítulo
            chapter_summary = summaries_dict.get(chapter, "")
            agent_context = ""
            if novelist_agent:
                try:
                    print_progress(f"Agent researching vault context for {chapter}...")
                    agent_context = novelist_agent.research_chapter(chapter, chapter_summary, idea_list)
                except Exception as error:
                    logger.warning(
                        "novelist agent research failed",
                        extra={"operation": "agent_research", "chapter": chapter, "error": str(error)},
                    )
            
            # Registrar el capítulo en el gestor de contexto
            context_manager.register_chapter(chapter, chapter, chapter_summary)
            
            # Acumular texto para contexto
            paragraphs_context = ""
            
            # Crear un resumen incremental que se actualizará durante la escritura
            savepoint_summary = f"Inicio del capítulo {i}: {chapter}"
            
            # Definir intervalo para puntos de guardado (cada cuántas ideas se crea un savepoint)
            savepoint_interval = max(1, _context_config.savepoint_interval)
            
            for j, idea in enumerate(idea_list, 1):
                generation_control.checkpoint()
                # Determinar posición en el capítulo
                section_position = "medio"
                if j == 1:
                    section_position = "inicio"
                elif j == ideas_total:
                    section_position = "final"
                
                # Mostrar parte de la idea en la consola
                idea_preview = idea[:40] + "..." if len(idea) > 40 else idea
                print_progress(f">> Idea {j}/{ideas_total}: {idea_preview}")
                
                # SISTEMA DE SAVEPOINTS: Verificar si toca crear un punto de guardado
                is_savepoint = (j == 1 or j == ideas_total or j % savepoint_interval == 0)
                
                if is_savepoint and paragraphs_context:
                    try:
                        print_progress("📌 Creando punto de guardado (savepoint)...")
                        # Usar nuestra nueva función independiente que no requiere de ChapterSummaryChain
                        savepoint_summary = create_savepoint_summary(
                            llm=writer_chain.llm,
                            title=title,
                            chapter_num=i,
                            chapter_title=chapter,
                            current_summary=savepoint_summary,
                            new_section=paragraphs_context[-_summary_config.savepoint_section_max_chars:]
                            if len(paragraphs_context) > _summary_config.savepoint_section_max_chars
                            else paragraphs_context,
                            total_chapters=total_chapters
                            , language=language
                        )
                        print_progress("✓ Punto de guardado creado")

                        if summary_quality_evaluator:
                            try:
                                quality = summary_quality_evaluator.evaluate_summary(
                                    paragraphs_context,
                                    savepoint_summary
                                )
                                print_progress(f"📏 Calidad de savepoint: {quality:.2f}")
                            except Exception as quality_error:
                                logger.warning(
                                    "savepoint quality evaluation failed",
                                    extra={"operation": "savepoint_quality", "error": str(quality_error)}
                                )
                        
                        # Cada ciertos savepoints (2-3), limpiar el contexto acumulado para evitar sobrecarga
                        if j > savepoint_interval * 2:
                            # Mantener solo las últimas 2-3 secciones y reemplazar el resto con el resumen
                            recent_sections = chapter_content[-2:] if len(chapter_content) > 2 else chapter_content
                            paragraphs_context = f"[Resumen hasta ahora: {savepoint_summary}]\n\n" + "\n\n".join(recent_sections)
                            print_progress("🧹 Contexto optimizado para continuar")
                    except Exception as e:
                        print_progress(f"⚠️ Error creando savepoint: {str(e)}")
                        logger.warning(
                            "savepoint creation failed",
                            extra={"operation": "savepoint_summary", "chapter": i, "error": str(e)}
                        )
                        # Si ocurre un error al crear el savepoint, seguir adelante con el resumen actual
                        # Esto garantiza que un error en el resumen no interrumpa la generación del libro
                
                # Preparar los parámetros para la generación de contenido
                section_params = {
                    'genre': genre,
                    'style': style,
                    'title': title,
                    'context_manager': context_manager,
                    'chapter_title': chapter,
                    'summary': _merge_progressive_context(
                        chapter_summary if j == 1 else savepoint_summary,
                        completed_context,
                    ),
                    # FASE 4: Usar configuración en lugar de valor mágico 800
                    'previous_paragraphs': paragraphs_context[-_context_config.limited_context_size:] if paragraphs_context else "",
                    'current_idea': idea,
                    'current_chapter': i,
                    'total_chapters': total_chapters,
                    'section_position': section_position,
                    'section_number': j,
                    'total_sections': ideas_total,
                    'chapter_key': chapter
                    , 'language': language
                    , 'book_bible': book_bible
                    , 'agent_context': agent_context
                }
                
                # Usar un sistema simplificado sin reintentos manuales
                try:
                    # Usar BaseChain que ya tiene reintentos integrados
                    section_content = writer_chain.run(**section_params)
                    
                    # Verificar si el contenido es válido
                    if section_content and len(section_content.strip()) >= _summary_config.section_min_chars:
                        pass  # Contenido válido, continuar
                    else:
                        # Si el contenido no es válido, usar prompt de emergencia
                        emergency_prompt = emergency_prompts.get_writing_emergency_prompt(
                            chapter_title=chapter,
                            idea=idea[:100],
                            language=language,
                        )
                        raw_response = writer_chain.llm.invoke(emergency_prompt)
                        section_content = clean_think_tags(extract_content_from_llm_response(raw_response))
                        if writer_chain._looks_like_assistant_chatter(section_content):
                            section_content = ""
                
                except GenerationCancelled:
                    raise
                except Exception as e:
                    print_progress(f"Error en generación: {str(e)}")
                    logger.error(
                        "section generation failed",
                        extra={
                            "operation": "section_generation",
                            "chapter": chapter,
                            "section": j,
                            "error": str(e)
                        }
                    )
                    # Usar prompt de emergencia como fallback
                    emergency_prompt = emergency_prompts.get_writing_emergency_prompt(
                        chapter_title=chapter,
                        idea=idea[:100],
                        language=language,
                    )
                    try:
                        raw_response = writer_chain.llm.invoke(emergency_prompt)
                        section_content = clean_think_tags(extract_content_from_llm_response(raw_response))
                        if writer_chain._looks_like_assistant_chatter(section_content):
                            section_content = ""
                    except GenerationCancelled:
                        raise
                    except Exception:
                        logger.warning(
                            "emergency prompt failed",
                            extra={
                                "operation": "section_generation",
                                "chapter": chapter,
                                "section": j
                            }
                        )
                        section_content = ""
                
                # Never contaminate a manuscript with generic filler after provider failure.
                if not section_content or len(section_content.strip()) < _summary_config.section_min_chars:
                    raise RuntimeError(
                        f"No valid book prose was produced for {chapter}, section {j}; "
                        "the project checkpoint was preserved"
                    )
                
                # NUEVO: Evaluar y potencialmente guardar como ejemplo
                quality_score = quality_monitor.evaluate_and_store(
                    section_content=section_content,
                    genre=genre,
                    style=style,
                    section_position=section_position,
                    context=paragraphs_context[-200:] if paragraphs_context else "",
                    idea=idea,
                    book_title=title,
                    language=language,
                )
                
                if quality_score:
                    print_progress(f"📊 Calidad de sección: {quality_score:.2f}")
                
                # Actualizar contexto en el gestor y guardar el contenido
                context_manager.update_chapter_content(chapter, section_content)
                
                # FASE 4: Usar configuración en lugar de valores mágicos 5000/3000
                # Actualizar contexto acumulado (limitar para evitar sobrecarga)
                if len(paragraphs_context) > _context_config.max_context_accumulation:
                    # Mantener solo la parte más reciente
                    paragraphs_context = paragraphs_context[-_context_config.standard_context_size:]
                    
                # Añadir nuevo contenido al contexto
                paragraphs_context += "\n\n" + section_content
                
                # Guardar el contenido generado
                chapter_content.append(section_content)
                book[chapter].append(section_content)
                
                # FASE 4: Usar rate limiting de configuración
                # Pequeña pausa entre secciones para evitar problemas con APIs
                time.sleep(provider_delay)
            
            # Al finalizar el capítulo, generar un resumen completo para usar en el siguiente capítulo
            try:
                chapter_complete_text = "\n\n".join(chapter_content)
                chapter_summaries[chapter] = summary_chain.run(
                    title=title,
                    chapter_num=i,
                    chapter_title=chapter,
                    chapter_content=chapter_complete_text,
                    total_chapters=total_chapters
                    , language=language
                )
                print_progress(f"✓ Resumen final del capítulo {i} generado")
            except Exception as e:
                print_progress(f"⚠️ Error generando resumen final: {str(e)}")
                logger.warning(
                    "final chapter summary failed",
                    extra={"operation": "chapter_summary", "chapter": chapter, "error": str(e)}
                )
                chapter_summaries[chapter] = savepoint_summary

            context_manager.record_completed_chapter(
                chapter, chapter, chapter_summaries[chapter]
            )

            if on_chapter_complete:
                on_chapter_complete(chapter, list(chapter_content), chapter_summaries[chapter])
                if novelist_agent:
                    try:
                        print_progress(f"Agent reviewing persisted chapter {chapter}...")
                        novelist_agent.review_chapter(chapter, chapter_summaries[chapter])
                    except Exception as error:
                        logger.warning(
                            "novelist agent post-draft review failed",
                            extra={"operation": "agent_review", "chapter": chapter, "error": str(error)},
                        )
            
            # NUEVO: Mostrar reporte dinámico al finalizar el capítulo
            try:
                if hasattr(context_manager, 'get_dynamic_status'):
                    dynamic_status = context_manager.get_dynamic_status()
                    if dynamic_status.get('dynamic_enabled', False):
                        complexity_report = dynamic_status.get('complexity_report', {})
                        quality_report = dynamic_status.get('quality_report', {})
                        
                        print_progress("📊 REPORTE DINÁMICO DEL CAPÍTULO:")
                        if complexity_report.get('overall_complexity'):
                            print_progress(f"   Complejidad narrativa: {complexity_report['complexity_category']} "
                                         f"({complexity_report['overall_complexity']:.2f})")
                            entities = complexity_report.get('entities', {})
                            print_progress(f"   Personajes detectados: {entities.get('character_count', 0)}")
                            print_progress(f"   Ubicaciones detectadas: {entities.get('location_count', 0)}")
                        
                        if quality_report.get('average_quality'):
                            print_progress(f"   Calidad de resúmenes: {quality_report['quality_category']} "
                                         f"({quality_report['average_quality']:.2f})")
                            print_progress(f"   Factor de agresividad: {quality_report['aggressiveness_factor']:.1f}x")
                        
                        current_limits = dynamic_status.get('current_limits', {})
                        if current_limits:
                            print_progress("   Límites dinámicos actuales:")
                            print_progress(f"     - Sección: {current_limits.get('max_section_context', 'N/A')} chars")
                            print_progress(f"     - Capítulo: {current_limits.get('max_chapter_context', 'N/A')} chars")
            except Exception as e:
                print_progress(f"⚠️ Error mostrando reporte dinámico: {e}")
                logger.warning(
                    "dynamic status report failed",
                    extra={"operation": "dynamic_context", "error": str(e)}
                )
            
            print_progress(f"✓ Capítulo {chapter} completado: {len(chapter_content)} secciones")

        # Al final de la generación, mostrar estadísticas de calidad
        stats = quality_monitor.get_session_stats()
        print_progress("\n" + "="*50)
        print_progress("📈 ESTADÍSTICAS DE FEW-SHOT LEARNING:")
        print_progress(f"  Secciones evaluadas: {stats['sections_evaluated']}")
        print_progress(f"  Secciones guardadas como ejemplos: {stats['sections_saved']}")
        print_progress(f"  Calidad promedio: {stats['average_quality']:.2f}")
        print_progress(f"  Calidad máxima: {stats['max_quality']:.2f}")
        print_progress(f"  Calidad mínima: {stats['min_quality']:.2f}")
        print_progress(f"  Tasa de guardado: {stats['save_rate']:.1%}")
        print_progress("="*50 + "\n")
        
        print_progress("======================================")
        print_progress("ESCRITURA DEL LIBRO FINALIZADA")
        print_progress("======================================")
        return book

    except Exception as e:
        print_progress(f"Error general en la escritura del libro: {str(e)}")
        logger.error(
            "write_book failed",
            extra={"operation": "write_book", "error": str(e)}
        )
        raise  # Propagar el error para detener la ejecución

def optimize_prompt_for_limited_context(prompt, max_length=None, preserve_instructions=True):
    """
    Versión simplificada que no modifica los prompts.
    Todos los modelos reciben el prompt completo sin optimizaciones.
    """
    # Devolver el prompt original sin modificaciones
    return prompt

def extract_first_sentence(text):
    """Extrae la primera frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[0] if sentences else ""

def extract_last_sentence(text):
    """Extrae la última frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[-1] if sentences else ""
