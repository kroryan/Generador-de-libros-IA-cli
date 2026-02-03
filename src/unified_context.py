"""
Sistema Unificado de Gestión de Contexto para el Generador de Libros IA.

Este módulo consolida los diferentes sistemas de gestión de contexto:
- ProgressiveContextManager (actualmente en uso)
- IntelligentContextManager (características avanzadas no utilizadas)
- MemoryManager (sistema simple no utilizado)
- AdaptiveContextSystem (no funcional)

Proporciona un sistema único, configurable y extensible para gestionar
el contexto durante la generación de libros.
"""

from typing import Dict, List, Optional, Any
from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response
import os
import time
import logging
from config.defaults import get_config
from retry_strategy import RetryStrategy, RetryableException

logger = logging.getLogger(__name__)


class ContextMode:
    """Modos de gestión de contexto disponibles."""
    SIMPLE = "simple"           # Acumulación simple de contenido
    PROGRESSIVE = "progressive"  # Sistema progresivo con resúmenes básicos
    INTELLIGENT = "intelligent"  # Sistema inteligente con micro-resúmenes automáticos


class UnifiedContextManager:
    """
    Gestor de contexto unificado que combina lo mejor de todos los sistemas anteriores.
    
    Características:
    - Gestión progresiva de contenido de capítulos (de ProgressiveContextManager)
    - Micro-resúmenes opcionales automáticos (de IntelligentContextManager)
    - Resúmenes globales condensados (de IntelligentContextManager)
    - Configuración flexible por variables de entorno
    """
    
    def __init__(
        self,
        framework: str = "",
        llm: Optional[Any] = None,
        mode: str = ContextMode.PROGRESSIVE,
        max_context_size: Optional[int] = None,
        enable_micro_summaries: Optional[bool] = None,
        micro_summary_interval: Optional[int] = None,
        model_profile: Optional[Any] = None,
        context_calculator: Optional[Any] = None
    ):
        """
        Inicializa el gestor de contexto unificado.
        
        Args:
            framework: Marco narrativo general del libro
            llm: Modelo LLM para crear resúmenes inteligentes (opcional)
            mode: Modo de operación (simple, progressive, intelligent)
            max_context_size: Tamaño máximo del contexto en caracteres
            enable_micro_summaries: Si True, crea micro-resúmenes automáticos cada N secciones
            micro_summary_interval: Número de secciones entre micro-resúmenes
            model_profile: Perfil del modelo para contexto dinámico (NUEVO)
            context_calculator: Calculador dinámico opcional para actualizar límites
        """
        config = get_config()
        self._context_config = config.context
        self._summary_config = config.summary

        max_context_override = max_context_size
        if enable_micro_summaries is None:
            enable_micro_summaries = self._context_config.enable_micro_summaries
        if micro_summary_interval is None:
            micro_summary_interval = self._context_config.micro_summary_interval
        if max_context_size is None:
            max_context_size = self._context_config.limited_context_size

        self.framework = framework
        self.llm = llm
        self.mode = mode
        self.enable_micro_summaries = enable_micro_summaries
        self.micro_summary_interval = micro_summary_interval
        self.base_profile = model_profile or (context_calculator.profile if context_calculator else None)
        self._context_calculator = context_calculator
        
        # NUEVO: Analizadores dinámicos
        self.complexity_analyzer = None
        self.summary_evaluator = None
        self.dynamic_context_enabled = False
        dynamic_required = os.environ.get("CONTEXT_REQUIRE_DYNAMIC_ANALYZERS", "false").lower() in ["true", "1", "yes", "on"]
        try:
            from narrative_complexity import NarrativeComplexityAnalyzer
            from summary_quality import SummaryQualityEvaluator

            self.complexity_analyzer = NarrativeComplexityAnalyzer()
            self.summary_evaluator = SummaryQualityEvaluator()
            self.dynamic_context_enabled = True

            print_progress("🧠 Sistema de contexto dinámico inicializado")

        except ImportError as e:
            msg = f"Analizadores dinámicos no disponibles: {e}"
            logger.warning(msg, extra={"operation": "dynamic_context", "error": str(e)})
            if dynamic_required:
                raise ImportError(msg)
            print_progress(f"⚠️ {msg}")

        # Límites dinámicos (se ajustan en tiempo real)
        self.context_limits = self._calculate_initial_limits()
        if max_context_override is not None:
            self.context_limits["max_section_context"] = max_context_override
            self.max_context_size = max_context_override
        else:
            self.max_context_size = max_context_size or self.context_limits.get(
                "max_section_context", max_context_size
            )

        if self.enable_micro_summaries and not self.llm:
            logger.warning(
                "micro summaries enabled without llm, disabling",
                extra={"operation": "micro_summary", "reason": "missing_llm"}
            )
            self.enable_micro_summaries = False

        self._retry_strategy = RetryStrategy()
        self._micro_summary_failures = 0
        self._micro_summary_next_retry_time = 0.0
        
        # Estructuras de datos
        self.book_context = {}
        self.chapter_contexts: Dict[str, Dict[str, Any]] = {}
        self._chapter_order: List[str] = []
        self.global_entities = {}
        self.current_sections = {}
        
        # Para micro-resúmenes
        self.current_chapter_content: List[str] = []
        self.section_count = 0
        
        # Memoria global de 3 niveles (de IntelligentContextManager)
        self.book_memory = {
            "global_summary": "",
            "characters": {},           # Nivel 1: Información de personajes
            "plot_threads": [],         # Nivel 2: Hilos narrativos activos
            "world_building": {},       # Nivel 3: Construcción del mundo/contexto
            "chapter_summaries": {}
        }
        
        # Sistema de memoria jerárquica
        self.memory_levels = {
            "immediate": {},    # Contexto inmediato (sección actual)
            "chapter": {},      # Contexto del capítulo (resúmenes progresivos)
            "book": {}          # Contexto global del libro (memoria persistente)
        }
        
        # Configurar desde variables de entorno si existen
        self._configure_from_env()
    
    def _calculate_initial_limits(self) -> Dict[str, int]:
        """Límites iniciales basados en perfil del modelo o configuración."""
        if self.base_profile:
            return {
                "max_section_context": self.base_profile.section_limit,
                "max_chapter_context": self.base_profile.chapter_limit,
                "max_global_context": self.base_profile.global_limit,
                "max_accumulation": self.base_profile.accumulation_threshold
            }

        return {
            "max_section_context": self._context_config.limited_context_size,
            "max_chapter_context": self._context_config.standard_context_size,
            "max_global_context": self._context_config.global_context_size,
            "max_accumulation": self._context_config.max_context_accumulation
        }
    
    def _configure_from_env(self):
        """Configura el gestor desde variables de entorno."""
        mode_env = os.environ.get('CONTEXT_MODE', '').lower()
        if mode_env in [ContextMode.SIMPLE, ContextMode.PROGRESSIVE, ContextMode.INTELLIGENT]:
            self.mode = mode_env
        
        max_size_env = os.environ.get('CONTEXT_MAX_SIZE', '')
        if max_size_env.isdigit():
            self.max_context_size = int(max_size_env)
            self.context_limits["max_section_context"] = self.max_context_size
        
        enable_micro_env = os.environ.get('CONTEXT_ENABLE_MICRO_SUMMARIES', '').lower()
        if enable_micro_env in ['true', '1', 'yes', 'on']:
            self.enable_micro_summaries = True
        elif enable_micro_env in ['false', '0', 'no', 'off']:
            self.enable_micro_summaries = False
        
        interval_env = os.environ.get('CONTEXT_MICRO_SUMMARY_INTERVAL', '')
        if interval_env.isdigit():
            self.micro_summary_interval = int(interval_env)
    
    # ===== API PRINCIPAL (Compatible con ProgressiveContextManager) =====
    
    def register_chapter(self, chapter_key: str, title: str, summary: str):
        """
        Registra información básica de un capítulo.
        Compatible con ProgressiveContextManager.
        """
        self.chapter_contexts[chapter_key] = {
            "title": title,
            "summary": summary,
            "content": [],
            "entities": {},
            "section_count": 0
        }

        if chapter_key not in self._chapter_order:
            self._chapter_order.append(chapter_key)
        
        print_progress(f"📋 Capítulo registrado: {title}")
    
    def update_chapter_content(self, chapter_key: str, section_content: str):
        """
        Actualiza el contenido de un capítulo con una nueva sección.
        Compatible con ProgressiveContextManager.
        
        Args:
            chapter_key: Identificador del capítulo
            section_content: Contenido de la sección a agregar
        """
        if chapter_key not in self.chapter_contexts:
            self.register_chapter(chapter_key, f"Capítulo {chapter_key}", "")
        
        if "content" not in self.chapter_contexts[chapter_key]:
            self.chapter_contexts[chapter_key]["content"] = []
        
        # NUEVO: Analizar complejidad narrativa
        if self.dynamic_context_enabled and self.complexity_analyzer:
            section_number = self.chapter_contexts[chapter_key]["section_count"] + 1
            complexity = self.complexity_analyzer.analyze_section(section_content, section_number)
            
            # AJUSTE DINÁMICO: multiplicar límites por complejidad
            multiplier = self.complexity_analyzer.get_context_multiplier()
            
            # Obtener factor de calidad de resúmenes
            quality_factor = 1.0
            if self.summary_evaluator:
                quality_factor = self.summary_evaluator.get_aggressiveness_factor()
            
            # Recalcular límites dinámicos
            if self._context_calculator:
                try:
                    new_limits = self._context_calculator.calculate_dynamic_limits(
                        multiplier, quality_factor
                    )
                    mapped_limits = {
                        "max_section_context": new_limits.get(
                            "section_limit", self.context_limits.get("max_section_context")
                        ),
                        "max_chapter_context": new_limits.get(
                            "chapter_limit", self.context_limits.get("max_chapter_context")
                        ),
                        "max_global_context": new_limits.get(
                            "global_limit", self.context_limits.get("max_global_context")
                        ),
                        "max_accumulation": new_limits.get(
                            "accumulation_threshold", self.context_limits.get("max_accumulation")
                        )
                    }
                    self.context_limits.update(mapped_limits)
                except Exception as e:
                    logger.warning(
                        "dynamic limits update failed",
                        extra={"operation": "dynamic_context", "error": str(e)}
                    )
            
            print_progress(f"📊 Sección {section_number}: {complexity['character_count']} personajes, "
                          f"complejidad={multiplier:.1f}x, calidad={quality_factor:.1f}x")
        
        # Agregar contenido
        self.chapter_contexts[chapter_key]["content"].append(section_content)
        self.chapter_contexts[chapter_key]["section_count"] += 1
        
        # Gestión de micro-resúmenes si está habilitado
        if self.enable_micro_summaries and self.llm:
            self.current_chapter_content.append(section_content)
            self.section_count += 1
            
            if self.section_count % self.micro_summary_interval == 0:
                self._create_micro_summary(chapter_key)
    
    def get_context_for_section(
        self,
        chapter_number: int,
        position: str,
        chapter_key: str
    ) -> Dict[str, Any]:
        """
        Obtiene contexto para una sección específica de un capítulo.
        Compatible con ProgressiveContextManager.
        
        Args:
            chapter_number: Número del capítulo actual
            position: Posición en el capítulo (inicio, medio, final)
            chapter_key: Identificador del capítulo
            
        Returns:
            Diccionario con el contexto necesario
        """
        # Si no hay información del capítulo, devolver contexto vacío
        if chapter_key not in self.chapter_contexts:
            return {
                "framework": self.framework,
                "previous_chapters_summary": "",
                "current_chapter_summary": "",
                "key_entities": {}
            }
        
        # Resumen de capítulos anteriores
        previous_chapters = []
        if chapter_key in self._chapter_order:
            idx = self._chapter_order.index(chapter_key)
            for prev_key in self._chapter_order[:idx]:
                ctx = self.chapter_contexts.get(prev_key, {})
                title = ctx.get("title", f"Capítulo {prev_key}")
                summary = ctx.get("summary", "")
                if summary:
                    previous_chapters.append(f"{title}: {summary}")
        else:
            # Fallback heuristico si no se conoce el orden del capitulo
            for i in range(1, chapter_number):
                for key, ctx in self.chapter_contexts.items():
                    if str(i) in key:
                        title = ctx.get("title", f"Capítulo {key}")
                        summary = ctx.get("summary", "")
                        if summary:
                            previous_chapters.append(f"{title}: {summary}")
        
        # Contenido acumulado del capítulo actual
        current_content = self.chapter_contexts[chapter_key].get("content", [])
        current_summary = ""
        
        if current_content:
            # Usar las últimas 3 secciones como contexto
            paragraphs = current_content[-3:] if len(current_content) > 3 else current_content
            current_summary = "\n\n".join(paragraphs)
            
            # Limitar longitud del contexto actual
            max_section_context = self.context_limits.get(
                "max_section_context", self.max_context_size
            )
            if len(current_summary) > max_section_context:
                current_summary = current_summary[-max_section_context:]
        
        return {
            "framework": self.framework,
            "previous_chapters_summary": " ".join(previous_chapters),
            "current_chapter_summary": current_summary,
            "key_entities": self.global_entities.get(chapter_key, {})
        }
    
    # ===== CARACTERÍSTICAS AVANZADAS (De IntelligentContextManager) =====
    
    def _create_micro_summary(self, chapter_key: str):
        """
        Crea un micro-resumen de las últimas secciones para optimizar memoria.
        Característica de IntelligentContextManager con evaluación de calidad.
        """
        if not self.llm or len(self.current_chapter_content) < self.micro_summary_interval:
            return

        now = time.time()
        if self._micro_summary_next_retry_time and now < self._micro_summary_next_retry_time:
            return
        
        print_progress("🔄 Creando micro-resumen para optimizar contexto...")
        
        # Tomar las últimas N secciones para resumir
        recent_sections = self.current_chapter_content[-self.micro_summary_interval:]
        combined_text = "\n\n".join(recent_sections)
        
        # NUEVO: Ajustar límite de palabras según calidad histórica
        aggressiveness = 1.0
        if self.dynamic_context_enabled and self.summary_evaluator:
            aggressiveness = self.summary_evaluator.get_aggressiveness_factor()
        
        max_words = int(self._summary_config.micro_summary_base_max_words * aggressiveness)
        max_words = max(20, max_words)
        
        # Crear prompt para micro-resumen
        prompt = f"""
        Resume las siguientes secciones del capítulo actual manteniendo SOLO los elementos narrativos esenciales.
        Máximo {max_words} palabras, enfócate en:
        - Eventos clave que afectan la trama
        - Desarrollo de personajes importantes
        - Información que será relevante para continuar la historia
        
        IMPORTANTE: Responde SOLO en español, máximo {max_words} palabras.
        
        Secciones a resumir:
        {combined_text[:self._summary_config.micro_summary_prompt_max_chars]}
        
        Resumen esencial:
        """
        
        try:
            def _invoke_micro_summary():
                response = self.llm.invoke(prompt)
                summary = clean_think_tags(extract_content_from_llm_response(response))
                if not summary or len(summary.strip()) < self._summary_config.micro_summary_min_chars:
                    raise RetryableException("Micro resumen vacio o muy corto")
                return summary

            micro_summary = self._retry_strategy.execute(_invoke_micro_summary)
            self._micro_summary_failures = 0
            self._micro_summary_next_retry_time = 0.0
            
            # NUEVO: Evaluar calidad del resumen
            if self.dynamic_context_enabled and self.summary_evaluator:
                quality = self.summary_evaluator.evaluate_summary(
                    combined_text, 
                    micro_summary
                )
                
                print_progress(f"✓ Micro-resumen creado (calidad={quality:.2f}, "
                              f"agresividad={aggressiveness:.1f}x)")
            else:
                print_progress("✓ Micro-resumen creado")
            
            # Reemplazar las secciones resumidas con el micro-resumen
            if len(micro_summary) >= self._summary_config.micro_summary_min_chars:
                # Mantener solo la última sección completa + el micro-resumen
                self.current_chapter_content = [
                    f"[Resumen de secciones anteriores: {micro_summary}]",
                    self.current_chapter_content[-1]  # Última sección completa
                ]
                print_progress("✓ Contexto optimizado")
        
        except Exception as e:
            self._micro_summary_failures += 1
            cooldown = self._retry_strategy.get_delay(
                min(self._micro_summary_failures, self._retry_strategy.config.max_attempts - 1)
            )
            self._micro_summary_next_retry_time = time.time() + cooldown
            logger.warning(
                "micro summary failed",
                extra={"operation": "micro_summary", "error": str(e), "cooldown": cooldown}
            )
            print_progress(f"⚠️ Error en micro-resumen: {str(e)}, continuando...")
    
    def finalize_chapter(
        self,
        chapter_key: str,
        chapter_title: str,
        chapter_number: int,
        total_chapters: int
    ) -> str:
        """
        Finaliza un capítulo creando un resumen completo.
        Característica de IntelligentContextManager.
        
        Returns:
            Resumen del capítulo finalizado
        """
        print_progress(f"📝 Finalizando capítulo {chapter_number}: {chapter_title}")
        
        if chapter_key not in self.chapter_contexts or not self.chapter_contexts[chapter_key].get("content"):
            return self._create_fallback_summary(chapter_title, chapter_number)
        
        # Si no hay LLM, usar el resumen básico
        if not self.llm:
            return self.chapter_contexts[chapter_key].get("summary", 
                self._create_fallback_summary(chapter_title, chapter_number))
        
        # Crear resumen inteligente del capítulo completo
        full_chapter = "\n\n".join(self.chapter_contexts[chapter_key]["content"])
        chapter_summary = self._create_intelligent_chapter_summary(
            full_chapter, chapter_title, chapter_number, total_chapters
        )
        
        # Actualizar memoria global
        self._update_global_memory(chapter_summary, chapter_key, chapter_title)
        
        # Limpiar contenido del capítulo actual
        self.current_chapter_content = []
        self.section_count = 0
        
        return chapter_summary
    
    def _create_intelligent_chapter_summary(
        self,
        chapter_content: str,
        chapter_title: str,
        chapter_number: int,
        total_chapters: int
    ) -> str:
        """Crea un resumen inteligente del capítulo usando IA."""
        
        # Optimizar longitud del contenido si es muy largo
        optimized_limit = self._summary_config.chapter_summary_optimized_max_chars
        if len(chapter_content) > optimized_limit:
            start_len = self._summary_config.chapter_summary_optimized_part_chars
            middle_half = self._summary_config.chapter_summary_optimized_middle_chars
            start = chapter_content[:start_len]
            middle_pos = len(chapter_content) // 2
            middle = chapter_content[middle_pos - middle_half:middle_pos + middle_half]
            end = chapter_content[-start_len:]
            
            optimized_content = f"{start}\n\n[...SECCIÓN MEDIA...]\n\n{middle}\n\n[...SECCIÓN FINAL...]\n\n{end}"
        else:
            optimized_content = chapter_content
        
        prompt = f"""
        Como editor profesional, crea un resumen estratégico del capítulo que será usado para mantener 
        coherencia narrativa en los siguientes capítulos.
        
        IMPORTANTE: 
        - Máximo 200 palabras en español
        - Enfócate en elementos que afectarán capítulos futuros
        - Incluye personajes, eventos clave, y elementos de trama
        - NO incluyas detalles descriptivos innecesarios
        
        Capítulo: {chapter_title} (Capítulo {chapter_number} de {total_chapters})
        
        Contenido del capítulo:
        {optimized_content}
        
        Resumen estratégico para continuidad narrativa:
        """
        
        try:
            response = self.llm.invoke(prompt)
            summary = clean_think_tags(extract_content_from_llm_response(response))
            
            # Validar y limitar longitud
            if len(summary) > self._summary_config.intelligent_chapter_summary_max_chars:
                summary = summary[:self._summary_config.intelligent_chapter_summary_max_chars] + "..."
            
            if len(summary) < self._summary_config.chapter_summary_min_chars:
                return self._create_fallback_summary(chapter_title, chapter_number)
            
            print_progress(f"✓ Resumen inteligente del capítulo {chapter_number} creado ({len(summary)} caracteres)")
            return summary
        
        except Exception as e:
            print_progress(f"⚠️ Error en resumen inteligente: {str(e)}")
            logger.warning(
                "intelligent chapter summary failed",
                extra={"operation": "chapter_summary", "error": str(e)}
            )
            return self._create_fallback_summary(chapter_title, chapter_number)
    
    def _create_fallback_summary(self, chapter_title: str, chapter_number: int) -> str:
        """Crea un resumen básico en caso de error."""
        return f"Capítulo {chapter_number} ({chapter_title}): La historia continúa desarrollándose."
    
    def _update_global_memory(self, chapter_summary: str, chapter_key: str, chapter_title: str):
        """Actualiza la memoria global del libro con información del nuevo capítulo."""
        self.book_memory["chapter_summaries"][chapter_key] = {
            "title": chapter_title,
            "summary": chapter_summary,
            "key_elements": self._extract_key_elements(chapter_summary)
        }
        
        # Actualizar resumen global si hay múltiples capítulos
        if len(self.book_memory["chapter_summaries"]) > 1:
            self._update_global_summary()
    
    def _extract_key_elements(self, chapter_summary: str) -> Dict[str, List[str]]:
        """
        Extrae elementos clave del resumen (personajes, lugares, eventos).
        Migrado desde IntelligentContextManager.
        """
        key_elements = {
            "characters": [],
            "locations": [],
            "events": []
        }
        
        # Análisis simple basado en patrones comunes
        words = chapter_summary.split()
        for i, word in enumerate(words):
            # Buscar nombres propios (palabras que empiezan con mayúscula)
            if (word and len(word) > 2 and word[0].isupper() and 
                word not in ["El", "La", "Los", "Las", "En", "Con", "Por", "Un", "Una", 
                           "Cuando", "Donde", "Como", "Pero", "Sin", "Tras", "Durante"]):
                key_elements["characters"].append(word)
        
        return key_elements
    
    def _update_global_summary(self):
        """Actualiza el resumen global del libro basado en todos los capítulos."""
        if len(self.book_memory["chapter_summaries"]) < 2:
            return
        
        # Crear resumen global combinando resúmenes de capítulos
        chapter_summaries = []
        for key, data in self.book_memory["chapter_summaries"].items():
            chapter_summaries.append(f"{data['title']}: {data['summary'][:100]}...")
        
        combined = " | ".join(chapter_summaries)
        
        # Si el resumen global es muy largo y hay LLM, condensarlo
        if len(combined) > self._summary_config.global_summary_condense_threshold_chars and self.llm:
            self._condense_global_summary(combined)
        else:
            self.book_memory["global_summary"] = combined
    
    def _condense_global_summary(self, long_summary: str):
        """Condensa el resumen global usando IA."""
        if not self.llm:
            return
        
        prompt = f"""
        Condensa el siguiente resumen de la historia manteniendo SOLO los elementos más importantes
        para la coherencia narrativa general. Máximo 300 palabras en español.
        
        Resumen actual:
        {long_summary}
        
        Resumen condensado:
        """
        
        try:
            response = self.llm.invoke(prompt)
            condensed = clean_think_tags(extract_content_from_llm_response(response))
            
            if len(condensed) > 50:
                self.book_memory["global_summary"] = condensed[:self._summary_config.global_summary_max_chars]
                print_progress("✓ Resumen global condensado")
        
        except Exception as e:
            print_progress(f"⚠️ Error condensando resumen global: {str(e)}")
            logger.warning(
                "global summary condensation failed",
                extra={"operation": "global_summary", "error": str(e)}
            )
    
    def get_context_for_next_chapter(self, next_chapter_number: int) -> Dict[str, Any]:
        """
        Obtiene el contexto optimizado para el siguiente capítulo.
        Característica de IntelligentContextManager.
        """
        context = {
            "global_summary": self.book_memory.get("global_summary", ""),
            "previous_chapter": "",
            "key_characters": [],
            "plot_continuity": ""
        }
        
        # Obtener resumen del capítulo anterior
        if len(self.book_memory["chapter_summaries"]) > 0:
            last_chapter = list(self.book_memory["chapter_summaries"].values())[-1]
            context["previous_chapter"] = f"{last_chapter['title']}: {last_chapter['summary']}"
        
        # Limitar el contexto total
        total_context = f"{context['global_summary']} {context['previous_chapter']}"
        max_context = self.context_limits.get("max_chapter_context", self.max_context_size)
        if len(total_context) > max_context:
            # Dar prioridad al capítulo anterior sobre el resumen global
            context["global_summary"] = context["global_summary"][:self._summary_config.global_summary_truncate_chars] + "..."
        
        return context
    
    def get_current_chapter_context(self) -> str:
        """Obtiene el contexto del capítulo actual para la siguiente sección."""
        if not self.current_chapter_content:
            return ""
        
        # Devolver las últimas 1-2 secciones como contexto
        recent_sections = (self.current_chapter_content[-2:] 
                          if len(self.current_chapter_content) > 2 
                          else self.current_chapter_content)
        context = "\n\n".join(recent_sections)
        
        # Limitar longitud
        if len(context) > self._summary_config.current_chapter_context_max_chars:
            context = context[-self._summary_config.current_chapter_context_max_chars:]
        
        return context
    
    # ===== SISTEMA DE MEMORIA JERÁRQUICA (3 NIVELES) =====
    
    def update_character_memory(self, character_name: str, info: str, chapter_key: str = None):
        """
        Actualiza la información de un personaje en la memoria del libro.
        Nivel 1 de la memoria jerárquica.
        """
        if character_name not in self.book_memory["characters"]:
            self.book_memory["characters"][character_name] = {
                "description": "",
                "development": [],
                "appearances": []
            }
        
        self.book_memory["characters"][character_name]["description"] = info
        if chapter_key:
            self.book_memory["characters"][character_name]["appearances"].append(chapter_key)
    
    def add_plot_thread(self, thread_description: str, status: str = "active"):
        """
        Añade un hilo narrativo a la memoria del libro.
        Nivel 2 de la memoria jerárquica.
        """
        plot_thread = {
            "description": thread_description,
            "status": status,  # active, resolved, paused
            "chapters": []
        }
        self.book_memory["plot_threads"].append(plot_thread)
    
    def update_world_building(self, element: str, description: str):
        """
        Actualiza elementos de construcción del mundo.
        Nivel 3 de la memoria jerárquica.
        """
        self.book_memory["world_building"][element] = description
    
    def get_hierarchical_context(self, level: str = "all") -> Dict[str, Any]:
        """
        Obtiene contexto según el nivel jerárquico especificado.
        
        Args:
            level: 'immediate', 'chapter', 'book', o 'all'
        """
        if level == "immediate":
            return self.memory_levels["immediate"]
        elif level == "chapter":
            return self.memory_levels["chapter"]
        elif level == "book":
            return self.memory_levels["book"]
        else:  # all
            return {
                "immediate": self.memory_levels["immediate"],
                "chapter": self.memory_levels["chapter"],
                "book": self.memory_levels["book"],
                "global_memory": self.book_memory
            }
    
    def optimize_memory_for_context_window(self, max_size: int) -> str:
        """
        Optimiza la memoria total para caber en la ventana de contexto especificada.
        Prioriza información más reciente y relevante.
        """
        # Prioridad: Inmediato > Capítulo > Libro
        context_parts = []
        current_size = 0
        
        # 1. Contexto inmediato (siempre incluir)
        immediate = str(self.memory_levels.get("immediate", ""))
        if immediate:
            context_parts.append(f"Contexto inmediato: {immediate}")
            current_size += len(immediate)
        
        # 2. Contexto del capítulo (incluir si hay espacio)
        chapter = str(self.memory_levels.get("chapter", ""))
        if chapter and current_size + len(chapter) < max_size * 0.7:
            context_parts.append(f"Capítulo actual: {chapter}")
            current_size += len(chapter)
        
        # 3. Contexto del libro (resumen condensado si hay espacio)
        remaining_space = max_size - current_size
        if remaining_space > 200:
            book_summary = self.book_memory.get("global_summary", "")
            if book_summary:
                if len(book_summary) > remaining_space:
                    book_summary = book_summary[:remaining_space - 50] + "..."
                context_parts.append(f"Historia general: {book_summary}")
        
        return "\n\n".join(context_parts)
    
    # ===== COMPATIBILIDAD CON MemoryManager =====
    
    def add_chapter_memory(self, chapter_key: str, content: str):
        """
        Compatibilidad con MemoryManager: Añade contenido a la memoria de un capítulo.
        """
        self.update_chapter_content(chapter_key, content)
    
    def get_chapter_context(self, chapter_key: str, num_memories: Optional[int] = None) -> str:
        """
        Compatibilidad con MemoryManager: Obtiene el contexto completo para un capítulo.
        """
        if chapter_key not in self.chapter_contexts:
            return ""
        
        content_list = self.chapter_contexts[chapter_key].get("content", [])
        if not content_list:
            return ""
        
        if num_memories is None or num_memories >= len(content_list):
            return "\n\n".join(content_list)
        else:
            # Si se especifica un número, usar las más recientes
            return "\n\n".join(content_list[-num_memories:])
    
    def add_global_memory(self, key: str, value: str):
        """
        Compatibilidad con MemoryManager: Añade una memoria global con una clave específica.
        """
        self.book_memory[key] = value
    
    def get_global_memory(self, key: str) -> str:
        """
        Compatibilidad con MemoryManager: Obtiene una memoria global.
        """
        return self.book_memory.get(key, "")
    
    def get_summary_for_chapter(self, chapter_key: str) -> str:
        """
        Compatibilidad con MemoryManager: Obtiene un resumen para el capítulo.
        """
        return self.get_chapter_context(chapter_key)
    
    def get_context_for_writing(self, chapter_key: str, prev_chapters: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compatibilidad con MemoryManager: Obtiene contexto para escritura.
        """
        context = {}
        
        # Añadir el marco narrativo general
        context["framework"] = self.framework
        
        # Añadir contexto de capítulos previos si se especifican
        if prev_chapters:
            prev_context = []
            for prev_key in prev_chapters:
                if prev_key in self.chapter_contexts:
                    prev_context.append(self.get_summary_for_chapter(prev_key))
            context["previous_chapters"] = "\n\n".join(prev_context)
        
        # Añadir contexto del capítulo actual
        if chapter_key in self.chapter_contexts:
            context["current_chapter"] = self.get_chapter_context(chapter_key)
        
        # Añadir todas las memorias globales disponibles
        context["global"] = self.book_memory
        
        return context
    
    # ===== NUEVOS MÉTODOS PARA ANÁLISIS DINÁMICO =====
    
    def get_complexity_report(self) -> Dict[str, any]:
        """Obtiene reporte de complejidad narrativa"""
        if self.dynamic_context_enabled and self.complexity_analyzer:
            return self.complexity_analyzer.get_complexity_report()
        return {"status": "Análisis de complejidad no disponible"}
    
    def get_quality_report(self) -> Dict[str, any]:
        """Obtiene reporte de calidad de resúmenes"""
        if self.dynamic_context_enabled and self.summary_evaluator:
            return self.summary_evaluator.get_quality_report()
        return {"status": "Evaluación de calidad no disponible"}
    
    def get_context_limits(self) -> Dict[str, int]:
        """Obtiene límites de contexto actuales"""
        return self.context_limits.copy()
    
    def get_dynamic_status(self) -> Dict[str, any]:
        """Obtiene estado completo del sistema dinámico"""
        status = {
            "dynamic_enabled": self.dynamic_context_enabled,
            "current_limits": self.context_limits,
            "sections_processed": self.section_count
        }
        
        if self.dynamic_context_enabled:
            status["complexity_report"] = self.get_complexity_report()
            status["quality_report"] = self.get_quality_report()
        
        return status
    
    def reset_analysis(self):
        """Reinicia análisis para una nueva historia"""
        if self.dynamic_context_enabled:
            if self.complexity_analyzer:
                self.complexity_analyzer.reset_analysis()
            if self.summary_evaluator:
                self.summary_evaluator.reset_evaluation()
        
        # Reiniciar contadores
        self.section_count = 0
        self.current_chapter_content.clear()
        self._chapter_order.clear()
        
        print_progress("🔄 Análisis dinámico reiniciado para nueva historia")


# ===== ALIAS PARA COMPATIBILIDAD =====

# Mantener compatibilidad con código existente que usa ProgressiveContextManager
ProgressiveContextManager = UnifiedContextManager

# Alias para compatibilidad con MemoryManager (migrado)
MemoryManager = UnifiedContextManager


# ===== CADENA DE ESCRITURA INTELIGENTE (Migrada de IntelligentContextManager) =====

class ProgressiveWriterChain(BaseEventChain):
    """
    Cadena de escritura que utiliza el contexto progresivo inteligente.
    Migrada desde intelligent_context.py para consolidación.
    """
    
    PROMPT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### INFORMACIÓN ESENCIAL:
    - Título: "{title}"
    - Estilo: {style}
    - Capítulo actual: {chapter_title} (Capítulo {current_chapter} de {total_chapters})
    - Sección: {section_number} de {total_sections}
    
    ### CONTEXTO DE LA HISTORIA:
    {story_context}
    
    ### CONTENIDO RECIENTE DEL CAPÍTULO:
    {recent_content}
    
    ### IDEA A DESARROLLAR:
    {current_idea}
    
    IMPORTANTE: 
    - Escribe EXCLUSIVAMENTE texto narrativo en español
    - NO incluyas notas, comentarios ni explicaciones
    - Mantén la coherencia con el contexto previo
    - Desarrolla la idea de forma natural y envolvente
    
    Texto narrativo:"""

    def run(self, context_manager, genre, style, title, chapter_title, current_idea, 
            current_chapter, total_chapters, section_number, total_sections):
        
        print_progress(f"📝 Escribiendo sección {section_number}/{total_sections} (contexto inteligente)")
        
        try:
            # Obtener contexto optimizado
            story_context = context_manager.get_context_for_next_chapter(current_chapter)
            recent_content = context_manager.get_current_chapter_context()
            
            # Crear contexto narrativo condensado
            context_text = ""
            if story_context.get("global_summary"):
                context_text += f"Historia hasta ahora: {story_context['global_summary'][:300]}\n\n"
            if story_context.get("previous_chapter"):
                context_text += f"Capítulo anterior: {story_context['previous_chapter'][:200]}"
            
            # Generar contenido
            result = self.invoke(
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                title=clean_think_tags(title),
                chapter_title=clean_think_tags(chapter_title),
                story_context=clean_think_tags(context_text),
                recent_content=clean_think_tags(recent_content),
                current_idea=clean_think_tags(current_idea),
                current_chapter=current_chapter,
                total_chapters=total_chapters,
                section_number=section_number,
                total_sections=total_sections
            )
            
            print_progress(f"✓ Sección {section_number} completada ({len(result)} caracteres)")
            return result

        except Exception as e:
            print_progress(f"❌ Error generando sección {section_number}: {str(e)}")
            # Fallback simple
            return f"La historia continuó desarrollándose en este punto del capítulo {chapter_title}."
