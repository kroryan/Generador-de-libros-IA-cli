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
from utils import print_progress, clean_think_tags, extract_content_from_llm_response
import os


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
        max_context_size: int = 2000,
        enable_micro_summaries: bool = False,
        micro_summary_interval: int = 3
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
        """
        self.framework = framework
        self.llm = llm
        self.mode = mode
        self.max_context_size = max_context_size
        self.enable_micro_summaries = enable_micro_summaries
        self.micro_summary_interval = micro_summary_interval
        
        # Estructuras de datos
        self.book_context = {}
        self.chapter_contexts: Dict[str, Dict[str, Any]] = {}
        self.global_entities = {}
        self.current_sections = {}
        
        # Para micro-resúmenes
        self.current_chapter_content: List[str] = []
        self.section_count = 0
        
        # Memoria global (de IntelligentContextManager)
        self.book_memory = {
            "global_summary": "",
            "characters": {},
            "plot_threads": [],
            "world_building": {},
            "chapter_summaries": {}
        }
        
        # Configurar desde variables de entorno si existen
        self._configure_from_env()
    
    def _configure_from_env(self):
        """Configura el gestor desde variables de entorno."""
        mode_env = os.environ.get('CONTEXT_MODE', '').lower()
        if mode_env in [ContextMode.SIMPLE, ContextMode.PROGRESSIVE, ContextMode.INTELLIGENT]:
            self.mode = mode_env
        
        max_size_env = os.environ.get('CONTEXT_MAX_SIZE', '')
        if max_size_env.isdigit():
            self.max_context_size = int(max_size_env)
        
        enable_micro_env = os.environ.get('CONTEXT_ENABLE_MICRO_SUMMARIES', '').lower()
        if enable_micro_env in ['true', '1', 'yes']:
            self.enable_micro_summaries = True
        
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
        for i in range(1, chapter_number):
            for key, ctx in self.chapter_contexts.items():
                # Buscar capítulos con número menor al actual
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
            if len(current_summary) > self.max_context_size:
                current_summary = current_summary[-self.max_context_size:]
        
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
        Característica de IntelligentContextManager.
        """
        if not self.llm or len(self.current_chapter_content) < self.micro_summary_interval:
            return
        
        print_progress("🔄 Creando micro-resumen para optimizar contexto...")
        
        # Tomar las últimas N secciones para resumir
        recent_sections = self.current_chapter_content[-self.micro_summary_interval:]
        combined_text = "\n\n".join(recent_sections)
        
        # Crear prompt para micro-resumen
        prompt = f"""
        Resume las siguientes secciones del capítulo actual manteniendo SOLO los elementos narrativos esenciales.
        Máximo 100 palabras, enfócate en:
        - Eventos clave que afectan la trama
        - Desarrollo de personajes importantes
        - Información que será relevante para continuar la historia
        
        IMPORTANTE: Responde SOLO en español, máximo 100 palabras.
        
        Secciones a resumir:
        {combined_text[:1500]}
        
        Resumen esencial:
        """
        
        try:
            response = self.llm.invoke(prompt)
            micro_summary = clean_think_tags(extract_content_from_llm_response(response))
            
            # Reemplazar las secciones resumidas con el micro-resumen
            if len(micro_summary) > 20:
                # Mantener solo la última sección completa + el micro-resumen
                self.current_chapter_content = [
                    f"[Resumen de secciones anteriores: {micro_summary}]",
                    self.current_chapter_content[-1]  # Última sección completa
                ]
                print_progress("✓ Micro-resumen creado, contexto optimizado")
        
        except Exception as e:
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
        if len(chapter_content) > 3000:
            start = chapter_content[:1000]
            middle_pos = len(chapter_content) // 2
            middle = chapter_content[middle_pos-500:middle_pos+500]
            end = chapter_content[-1000:]
            
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
            if len(summary) > 500:
                summary = summary[:500] + "..."
            
            if len(summary) < 30:
                return self._create_fallback_summary(chapter_title, chapter_number)
            
            print_progress(f"✓ Resumen inteligente del capítulo {chapter_number} creado ({len(summary)} caracteres)")
            return summary
        
        except Exception as e:
            print_progress(f"⚠️ Error en resumen inteligente: {str(e)}")
            return self._create_fallback_summary(chapter_title, chapter_number)
    
    def _create_fallback_summary(self, chapter_title: str, chapter_number: int) -> str:
        """Crea un resumen básico en caso de error."""
        return f"Capítulo {chapter_number} ({chapter_title}): La historia continúa desarrollándose."
    
    def _update_global_memory(self, chapter_summary: str, chapter_key: str, chapter_title: str):
        """Actualiza la memoria global del libro con información del nuevo capítulo."""
        self.book_memory["chapter_summaries"][chapter_key] = {
            "title": chapter_title,
            "summary": chapter_summary,
            "key_elements": {}
        }
        
        # Actualizar resumen global si hay múltiples capítulos
        if len(self.book_memory["chapter_summaries"]) > 1:
            self._update_global_summary()
    
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
        if len(combined) > 800 and self.llm:
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
                self.book_memory["global_summary"] = condensed[:400]
                print_progress("✓ Resumen global condensado")
        
        except Exception as e:
            print_progress(f"⚠️ Error condensando resumen global: {str(e)}")
    
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
        if len(total_context) > self.max_context_size:
            # Dar prioridad al capítulo anterior sobre el resumen global
            context["global_summary"] = context["global_summary"][:500] + "..."
        
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
        if len(context) > 800:
            context = context[-800:]
        
        return context


# ===== ALIAS PARA COMPATIBILIDAD =====

# Mantener compatibilidad con código existente que usa ProgressiveContextManager
ProgressiveContextManager = UnifiedContextManager
