from memory_manager import HierarchicalMemoryManager
from entity_extractor import EntityExtractor
from content_analyzer import ContentAnalyzer
from utils import print_progress, clean_think_tags, extract_content_from_llm_response
import re
import time

class AdaptiveContextSystem:
    """
    Sistema inteligente que gestiona el contexto para la generación de libros
    de forma adaptativa, utilizando estrategias avanzadas para prevenir
    la sobrecarga de contexto y mantener la coherencia narrativa.
    """
    
    def __init__(self, title, framework, total_chapters, model_size="standard"):
        # Inicializar gestores de memoria y extractores
        self.memory_manager = HierarchicalMemoryManager(title, framework, total_chapters)
        self.entity_extractor = EntityExtractor()
        self.content_analyzer = ContentAnalyzer()
        
        # Información global del libro
        self.title = title
        self.framework = framework
        self.total_chapters = total_chapters
        self.current_chapter = 1
        
        # Seguimiento de estado
        self.generation_state = {
            "model_size": model_size,       # "small", "standard", "large"
            "context_mode": "standard",     # "minimal", "standard", "extended"
            "risk_level": "low",            # "low", "medium", "high", "critical"
            "strict_checking": False,       # Activar verificación estricta
            "collapse_count": 0,            # Contador de colapsos detectados
            "recovery_attempts": 0,         # Intentos de recuperación
        }
        
        # Límites de tokens por modelo - LÍMITE UNIVERSAL para prevenir sobrecarga
        self.token_limits = {
            "small": 15000,       # Para modelos pequeños (7B-9B)
            "standard": 30000,    # Límite universal: 2K por debajo del máximo de deepseek (32K)
            "large": 30000        # Mismo límite universal para todos
        }
        
        # Umbral de advertencia (porcentaje del límite)
        self.warning_threshold = 0.85  # Advertencia cuando se alcanza el 85% del límite
        
        # Umbral de activación de compresión de emergencia (porcentaje del límite)
        self.emergency_threshold = 0.92  # Activar compresión de emergencia al 92% del límite
        
        # Estrategias avanzadas
        self.enable_progressive_generation = True  # Generar en trozos pequeños
        self.enable_entity_tracking = True         # Seguimiento de personajes/lugares
        self.enable_narrative_planning = True      # Planificar antes de generar
        self.adaptive_polling_frequency = 5        # Verificar salud cada N secciones
        
        # Verificar si hay una configuración de contexto en variables de entorno
        self._check_env_context_config()
        
        print_progress(f"🧠 Sistema de contexto adaptativo inicializado: Modelo {model_size}")
    
    def _check_env_context_config(self):
        """Verifica si hay configuración de contexto en variables de entorno"""
        import os
        
        # Detectar configuración de tamaño de modelo
        model_context_size = os.environ.get("MODEL_CONTEXT_SIZE", "").strip().lower()
        if model_context_size in ["limited", "small"]:
            self.set_model_size("small")
            print_progress("⚙️ Configurando contexto limitado desde variable de entorno")
            
            # Para deepseek y modelos similares, usar límites más estrictos
            model_name = os.environ.get("MODEL_NAME", "").lower()
            if "deepseek" in model_name:
                self.token_limits["small"] = 10000  # Reducir aún más para deepseek (era 12000)
                print_progress("⚠️ Ajustando límites para modelo deepseek")
                
                # Umbrales más agresivos para deepseek
                self.warning_threshold = 0.75  # Advertencia al 75% (antes 85%)
                self.emergency_threshold = 0.85  # Compresión al 85% (antes 92%)
                print_progress("⚠️ Umbrales de compresión más agresivos para deepseek")
                
                # Forzar contexto minimalista siempre para deepseek
                self.generation_state["context_mode"] = "minimal"
                self.generation_state["strict_checking"] = True
        elif model_context_size == "extended":
            self.set_model_size("large")
            print_progress("⚙️ Configurando contexto extendido desde variable de entorno")
    
    def set_model_size(self, size):
        """Establece el tamaño/capacidad del modelo en uso"""
        valid_sizes = ["small", "standard", "large"]
        if size in valid_sizes:
            self.generation_state["model_size"] = size
            # Ajustar automáticamente modo de contexto según tamaño
            if size == "small":
                self.generation_state["context_mode"] = "minimal"
                self.generation_state["strict_checking"] = True
                print_progress("⚙️ Modo de contexto mínimo activado para modelo pequeño")
            elif size == "standard":
                self.generation_state["context_mode"] = "standard"
                print_progress("⚙️ Modo de contexto estándar activado")
            else:
                self.generation_state["context_mode"] = "extended"
                print_progress("⚙️ Modo de contexto extendido activado para modelo grande")
    
    def start_chapter(self, chapter_num, chapter_title, chapter_summary):
        """Inicializa la gestión de contexto para un nuevo capítulo"""
        self.current_chapter = chapter_num
        
        # Reiniciar memoria de corto y medio plazo
        self.memory_manager.clear_medium_term_memory()
        self.content_analyzer.reset_history()
        
        # Guardar resumen del capítulo en memoria a largo plazo
        self.memory_manager.update_long_term_memory(
            chapter_num=chapter_num,
            chapter_summary=chapter_summary
        )
        
        # Extraer entidades iniciales del resumen
        initial_entities = self.entity_extractor.extract_entities_from_text(
            chapter_summary,
            chapter_num=chapter_num,
            is_new_character=True  # Buscar agresivamente nuevos personajes
        )
        
        # Registrar información del capítulo
        chapter_info = {
            "title": chapter_title,
            "number": chapter_num,
            "summary": chapter_summary,
            "initial_entities": initial_entities
        }
        
        print_progress(f"📑 Iniciando capítulo {chapter_num}: {chapter_title}")
        print_progress(f"🔍 Entidades detectadas: {len(initial_entities['characters'])} personajes, {len(initial_entities['locations'])} lugares")
        
        return chapter_info
    
    def get_context_for_section(self, section_position, idea, previous_content="", section_number=1, total_sections=1):
        """
        Obtiene el contexto óptimo para generar una sección específica,
        basado en la posición, contenido previo y modo de contexto actual.
        
        Args:
            section_position: Posición en capítulo ("inicio", "medio", "final")
            idea: Idea a desarrollar en esta sección
            previous_content: Contenido generado previamente en el capítulo
            section_number: Número de sección actual
            total_sections: Total de secciones en el capítulo
            
        Returns:
            dict: Contexto optimizado para esta sección
        """
        # Extraer entidades activas del contenido previo
        active_entities = []
        if previous_content:
            active_entities = self.entity_extractor.get_active_entities(
                previous_content, 
                chapter_num=self.current_chapter
            )
            
            # Actualizar memoria de corto plazo con contenido previo y entidades
            self.memory_manager.update_short_term_memory(
                new_text=previous_content,
                active_entities=active_entities
            )
        
        # Modo de contexto específico para la etapa actual
        if self.generation_state["context_mode"] == "minimal":
            # Para modelos pequeños o en riesgo alto: contexto ultra-minimalista
            context = self._get_minimal_context(section_position, idea, active_entities)
            
        elif self.generation_state["context_mode"] == "standard":
            # Modo estándar: balance entre información y economía de tokens
            context = self._get_standard_context(section_position, idea, active_entities)
            
        else:  # extended
            # Modo extendido: más información para modelos con mayor capacidad
            context = self._get_extended_context(section_position, idea, active_entities, previous_content)
        
        # Modificar según posición en el capítulo
        context = self._adjust_for_section_position(
            context, 
            section_position, 
            section_number, 
            total_sections
        )
        
        # Añadir idea a desarrollar
        context["current_idea"] = idea
        
        return context
    
    def _get_minimal_context(self, section_position, idea, active_entities=None):
        """
        Obtiene el contexto mínimo para modelos pequeños o situaciones de alto riesgo.
        Proporciona solo la información esencial para mantener coherencia.
        
        Args:
            section_position: Posición en el capítulo ("inicio", "medio", "final")
            idea: Idea a desarrollar
            active_entities: Lista de entidades activas en la escena actual
            
        Returns:
            dict: Contexto mínimo optimizado
        """
        minimal_context = {}
        
        # 1. Esencia narrativa ultra-condensada del libro
        book_essence = self.memory_manager.get_book_essence(max_length=150)
        minimal_context["core_narrative"] = book_essence
        
        # 2. Personajes activos actuales (mínimo imprescindible)
        if active_entities:
            minimal_context["active_entities"] = ", ".join(active_entities[:3])
        else:
            # Si no hay entidades activas, usar las más importantes del capítulo
            key_entities = self.memory_manager.get_key_entities(
                chapter_num=self.current_chapter,
                max_entities=2
            )
            if key_entities:
                minimal_context["active_entities"] = ", ".join(key_entities)
        
        # 3. Guía simplificada según posición
        if section_position == "inicio":
            minimal_context["position_guidance"] = "Esta es la apertura del capítulo."
        elif section_position == "final":
            minimal_context["position_guidance"] = "Esta es la conclusión del capítulo."
        else:
            minimal_context["position_guidance"] = "Continuando el desarrollo del capítulo."
        
        # Información absolutamente esencial del capítulo actual (una frase)
        chapter_summary = self.memory_manager.get_chapter_summary(
            self.current_chapter, 
            max_length=100
        )
        if chapter_summary:
            minimal_context["chapter_essence"] = chapter_summary
            
        return minimal_context
        
    def _get_standard_context(self, section_position, idea, active_entities=None):
        """
        Obtiene el contexto estándar para la mayoría de situaciones.
        Balance entre información y economía de tokens.
        
        Args:
            section_position: Posición en el capítulo ("inicio", "medio", "final")
            idea: Idea a desarrollar
            active_entities: Lista de entidades activas en la escena actual
            
        Returns:
            dict: Contexto estándar optimizado
        """
        # Partir del contexto mínimo y expandirlo
        context = self._get_minimal_context(section_position, idea, active_entities)
        
        # 1. Expandir esencia narrativa
        book_essence = self.memory_manager.get_book_essence(max_length=300)
        context["core_narrative"] = book_essence
        
        # 2. Añadir contexto de últimos eventos relevantes
        recent_events = self.memory_manager.get_recent_events(max_events=3)
        if recent_events:
            context["recent_events"] = recent_events
            
        # 3. Expandir información sobre personajes activos
        if active_entities:
            # Obtener más detalles sobre los personajes activos (hasta 3)
            character_details = {}
            for character in active_entities[:3]:
                # Obtener estado actual e información relevante del personaje
                char_info = self.memory_manager.get_character_state(character)
                if char_info:
                    character_details[character] = char_info
                    
            if character_details:
                context["character_states"] = character_details
                
        # 4. Añadir contenido reciente si está en medio o final
        if section_position in ["medio", "final"]:
            recent_content = self.memory_manager.get_recent_content(max_paragraphs=2)
            if recent_content:
                context["recent_paragraphs"] = recent_content
                
        # 5. Guía para mantener tono y estilo
        context["style_guidance"] = self.memory_manager.get_writing_style()
        
        return context
        
    def _get_extended_context(self, section_position, idea, active_entities=None, previous_content=""):
        """
        Obtiene el contexto extendido para modelos grandes.
        Proporciona información detallada para máxima coherencia y calidad.
        
        Args:
            section_position: Posición en el capítulo ("inicio", "medio", "final")
            idea: Idea a desarrollar
            active_entities: Lista de entidades activas en la escena actual
            previous_content: Contenido generado previamente
            
        Returns:
            dict: Contexto extendido rico en detalles
        """
        # Partir del contexto estándar y expandirlo
        context = self._get_standard_context(section_position, idea, active_entities)
        
        # 1. Narrativa completa del libro
        full_narrative = self.memory_manager.get_book_essence(max_length=500)
        context["core_narrative"] = full_narrative
        
        # 2. Historia completa de los capítulos anteriores
        previous_chapters = self.memory_manager.get_previous_chapters_summaries(
            current_chapter=self.current_chapter,
            max_chapters=3
        )
        if previous_chapters:
            context["previous_chapters"] = previous_chapters
            
        # 3. Detalles completos de personajes y lugares
        if active_entities:
            # Expandir información de todos los personajes activos
            character_details = {}
            for character in active_entities:
                # Obtener estado completo e historia del personaje
                char_info = self.memory_manager.get_character_state(character, include_history=True)
                if char_info:
                    character_details[character] = char_info
                    
            if character_details:
                context["character_states"] = character_details
        
        # 4. Reglas del mundo y sistema mágico-tecnológico
        world_rules = self.memory_manager.get_world_rules()
        if world_rules:
            context["world_rules"] = world_rules
            
        # 5. Añadir más contenido reciente si está en medio o final
        if section_position in ["medio", "final"]:
            recent_content = self.memory_manager.get_recent_content(max_paragraphs=5)
            if recent_content:
                context["recent_paragraphs"] = recent_content
                
        # 6. Arcos narrativos activos
        active_arcs = self.memory_manager.get_active_plot_arcs()
        if active_arcs:
            context["active_arcs"] = active_arcs
            
        # 7. Lista de eventos principales de todo el libro
        major_events = self.memory_manager.get_major_events()
        if major_events:
            context["major_events"] = major_events
            
        return context
        
    def _adjust_for_section_position(self, context, section_position, section_number, total_sections):
        """
        Ajusta el contexto según la posición específica dentro del capítulo.
        
        Args:
            context: Contexto base a ajustar
            section_position: Posición general en el capítulo ("inicio", "medio", "final")
            section_number: Número exacto de sección actual
            total_sections: Total de secciones en el capítulo
            
        Returns:
            dict: Contexto ajustado según posición
        """
        adjusted_context = context.copy()
        
        # Calcular porcentaje de avance en el capítulo
        progress_percent = (section_number / total_sections) * 100
        
        # Preparar guía de posición precisa
        if section_position == "inicio":
            position_guidance = f"Estamos en el {progress_percent:.0f}% inicial del capítulo {self.current_chapter}. "
            if section_number == 1:
                position_guidance += "Esta es la primera sección del capítulo, establece la escena y presenta la situación inicial."
            else:
                position_guidance += "Continuamos en la parte inicial del capítulo, desarrollando la premisa."
                
        elif section_position == "final":
            position_guidance = f"Estamos en el {progress_percent:.0f}% final del capítulo {self.current_chapter}. "
            if section_number == total_sections:
                position_guidance += "Esta es la última sección del capítulo, concluye los eventos y prepara el siguiente capítulo."
            else:
                position_guidance += "Avanzamos hacia la conclusión del capítulo, intensificando la tensión narrativa."
                
        else:  # "medio"
            position_guidance = f"Estamos al {progress_percent:.0f}% del capítulo {self.current_chapter}. "
            position_guidance += "Desarrolla los eventos centrales del capítulo, mantén el ritmo narrativo."
            
        # Actualizar guía de posición
        adjusted_context["position_guidance"] = position_guidance
        
        # Ajustes específicos por posición
        if section_position == "inicio":
            # Para inicio, priorizar presentación y referencias a capítulos anteriores
            chapter_intro = self.memory_manager.get_chapter_introduction(self.current_chapter)
            if chapter_intro:
                adjusted_context["chapter_intro"] = chapter_intro
                
        elif section_position == "final":
            # Para final, priorizar cierre y conexión con siguiente capítulo
            next_chapter_hint = self.memory_manager.get_next_chapter_preview(self.current_chapter)
            if next_chapter_hint and self.current_chapter < self.total_chapters:
                adjusted_context["next_chapter_hint"] = next_chapter_hint
                
        return adjusted_context
    
    def create_chapter_summary(self, chapter_num, chapter_title, contents):
        """
        Crea un resumen condensado del capítulo a partir de su contenido.
        
        Args:
            chapter_num: Número del capítulo
            chapter_title: Título del capítulo
            contents: Contenido completo del capítulo
            
        Returns:
            str: Resumen condensado del capítulo
        """
        # Si el contenido es muy corto, devolverlo como resumen
        if len(contents) < 200:
            return contents
            
        # Extraer párrafos significativos (primero, algunos del medio, último)
        paragraphs = contents.split('\n\n')
        
        # Seleccionar párrafos clave
        key_paragraphs = []
        
        # Incluir primer párrafo si existe
        if paragraphs:
            key_paragraphs.append(paragraphs[0])
            
        # Incluir algunos párrafos del medio si hay suficientes
        if len(paragraphs) > 4:
            mid_point = len(paragraphs) // 2
            key_paragraphs.append(paragraphs[mid_point])
            
        # Incluir último párrafo si existe y es diferente del primero
        if len(paragraphs) > 1:
            key_paragraphs.append(paragraphs[-1])
            
        # Extraer entidades principales
        entities = self.entity_extractor.extract_entities_from_text(
            contents,
            chapter_num=chapter_num
        )
        
        # Construir resumen estructurado
        summary_parts = [
            f"Capítulo {chapter_num}: {chapter_title}",
            f"Personajes principales: {', '.join(entities['characters'][:5]) if entities['characters'] else 'No detectados'}",
            f"Ubicaciones: {', '.join(entities['locations'][:3]) if entities['locations'] else 'No detectadas'}",
            "\nResumen:",
            "\n".join(key_paragraphs)
        ]
        
        # Unir todo en un resumen cohesivo
        summary = "\n\n".join(summary_parts)
        
        # Almacenar este resumen en memoria
        self.memory_manager.update_long_term_memory(
            chapter_num=chapter_num,
            chapter_summary=summary
        )
        
        return summary
    
    def estimate_token_count(self, context):
        """
        Estima el número de tokens en el contexto para controlar límites.
        Usa aproximación basada en caracteres, que es más rápida pero menos precisa.
        
        Args:
            context: Diccionario con elementos de contexto o cadena de texto
            
        Returns:
            int: Número estimado de tokens
        """
        # Para contexto en formato diccionario
        if isinstance(context, dict):
            total_chars = 0
            
            # Procesar cada clave del contexto
            for key, value in context.items():
                if isinstance(value, str):
                    total_chars += len(value)
                elif isinstance(value, list):
                    # Para listas, contar caracteres de cada elemento si son strings
                    for item in value:
                        if isinstance(item, str):
                            total_chars += len(item)
                elif isinstance(value, dict):
                    # Para diccionarios anidados, contar caracteres de valores
                    for v in value.values():
                        if isinstance(v, str):
                            total_chars += len(v)
            
            # Aproximación general: en español ~3.5 caracteres = 1 token
            estimated_tokens = total_chars / 3.5
            return int(estimated_tokens)
        
        # Para contexto en formato texto
        elif isinstance(context, str):
            # Aproximación general: en español ~3.5 caracteres = 1 token
            return int(len(context) / 3.5)
        
        # Tipo no compatible
        return 0
    
    def check_context_size(self, context, model_size="standard"):
        """
        Verifica si el contexto supera los límites establecidos y advierte/comprime
        si es necesario.
        
        Args:
            context: Diccionario con elementos de contexto
            model_size: Tamaño del modelo para usar límites correspondientes
            
        Returns:
            tuple: (Contexto (posiblemente comprimido), dict con info de tamaño)
        """
        # Estimar tokens en el contexto actual
        estimated_tokens = self.estimate_token_count(context)
        
        # Obtener límite para el tipo de modelo actual
        token_limit = self.token_limits.get(model_size, self.token_limits["standard"])
        
        # Calcular porcentaje de uso
        usage_percentage = (estimated_tokens / token_limit) * 100
        
        # Información de diagnóstico
        size_info = {
            "estimated_tokens": estimated_tokens,
            "limit": token_limit,
            "usage_percentage": round(usage_percentage, 1),
            "compressed": False,
            "emergency_compressed": False
        }
        
        # Si supera umbral de advertencia, mostrar alerta
        if usage_percentage > self.warning_threshold * 100:
            print_progress(f"⚠️ Advertencia: Uso alto de contexto ({usage_percentage:.1f}% del límite)")
        
        # Si supera umbral de emergencia, aplicar compresión agresiva
        if usage_percentage > self.emergency_threshold * 100:
            print_progress(f"🚨 Contexto excesivo detectado: {estimated_tokens} tokens ({usage_percentage:.1f}%)")
            compressed_context = self.apply_emergency_compression(context)
            size_info["compressed"] = True
            size_info["emergency_compressed"] = True
            
            # Recalcular información
            new_tokens = self.estimate_token_count(compressed_context)
            size_info["estimated_tokens"] = new_tokens
            size_info["usage_percentage"] = round((new_tokens / token_limit) * 100, 1)
            size_info["tokens_saved"] = estimated_tokens - new_tokens
            
            print_progress(f"✂️ Compresión de emergencia aplicada: {new_tokens} tokens ({size_info['usage_percentage']}%)")
            return compressed_context, size_info
            
        # Si está cercano al umbral, aplicar compresión moderada
        elif usage_percentage > self.warning_threshold * 100:
            compressed_context = self.apply_adaptive_compression(context)
            size_info["compressed"] = True
            
            # Recalcular información
            new_tokens = self.estimate_token_count(compressed_context)
            size_info["estimated_tokens"] = new_tokens
            size_info["usage_percentage"] = round((new_tokens / token_limit) * 100, 1)
            size_info["tokens_saved"] = estimated_tokens - new_tokens
            
            print_progress(f"✂️ Compresión adaptativa aplicada: {new_tokens} tokens ({size_info['usage_percentage']}%)")
            return compressed_context, size_info
        
        # Contexto en rango seguro
        return context, size_info
    
    def apply_emergency_compression(self, context):
        """
        Aplica compresión de emergencia muy agresiva cuando estamos cerca del límite
        de tokens, priorizando solo el contenido absolutamente esencial.
        
        Args:
            context: Diccionario con elementos de contexto
            
        Returns:
            dict: Contexto ultra-comprimido
        """
        if not isinstance(context, dict):
            return context
            
        emergency_context = {}
        
        # Preservar solo elementos críticos para continuidad
        if "recent_paragraphs" in context:
            # Recortar drásticamente párrafos recientes
            paragraphs = context["recent_paragraphs"].split('\n\n')
            if len(paragraphs) > 1:
                # Mantener solo el último párrafo (el más reciente)
                emergency_context["recent_paragraphs"] = paragraphs[-1]
            else:
                emergency_context["recent_paragraphs"] = context["recent_paragraphs"][:500]
        
        # Preservar personajes activos (crítico para consistencia)
        if "active_entities" in context:
            emergency_context["active_entities"] = context["active_entities"]
            
        # Mantener la idea actual sin modificar (crítico para la tarea)
        if "current_idea" in context:
            emergency_context["current_idea"] = context["current_idea"]
            
        # Guía de posición muy simplificada
        if "position_guidance" in context:
            parts = context["position_guidance"].split('.')
            if parts:
                emergency_context["position_guidance"] = parts[0] + "."
                
        # Para esencia narrativa, recortar brutalmente
        if "core_narrative" in context:
            core = context["core_narrative"]
            if len(core) > 200:
                # Extraer solo primera oración o frase
                sentences = core.split('.')
                if sentences:
                    emergency_context["core_narrative"] = sentences[0].strip() + "."
            else:
                emergency_context["core_narrative"] = core
                
        print_progress("🚨 Compresión de emergencia aplicada - Contexto crítico")
        return emergency_context
    
    def apply_adaptive_compression(self, context):
        """
        Aplica compresión adaptativa cuando estamos cerca del umbral de advertencia
        pero no en situación crítica.
        
        Args:
            context: Diccionario con elementos de contexto
            
        Returns:
            dict: Contexto comprimido adaptativamente
        """
        if not isinstance(context, dict):
            return context
            
        compressed_context = context.copy()
        
        # Reducir longitud de párrafos recientes
        if "recent_paragraphs" in compressed_context:
            paragraphs = compressed_context["recent_paragraphs"].split('\n\n')
            if len(paragraphs) > 3:
                # Mantener solo los 3 últimos párrafos
                compressed_context["recent_paragraphs"] = '\n\n'.join(paragraphs[-3:])
            
        # Para elementos de narrativa, recortar solo si son extensos
        if "core_narrative" in compressed_context and len(compressed_context["core_narrative"]) > 500:
            # Reducir a la mitad aproximadamente
            sentences = compressed_context["core_narrative"].split('.')
            if len(sentences) > 5:
                # Tomar primera oración y últimas 2-3
                reduced = sentences[0] + '. ' + '. '.join(sentences[-3:])
                compressed_context["core_narrative"] = reduced + '.'
                
        # Eliminar elementos menos críticos si existen
        for key in ["world_rules", "semantic_context", "major_events"]:
            if key in compressed_context:
                del compressed_context[key]
                
        # Reducir información de personajes menos relevantes
        if "character_states" in compressed_context and isinstance(compressed_context["character_states"], dict):
            character_states = compressed_context["character_states"]
            # Mantener solo los 3 personajes más mencionados
            if len(character_states) > 3:
                active_entities = compressed_context.get("active_entities", "").split(", ")
                # Priorizar los personajes activos en la escena actual
                priority_chars = [c for c in active_entities if c in character_states]
                
                # Si no hay suficientes, agregar hasta completar 3
                remaining = list(character_states.keys())
                for char in priority_chars:
                    if char in remaining:
                        remaining.remove(char)
                        
                # Combinar prioritarios con algunos restantes hasta tener 3
                final_chars = priority_chars + remaining[:max(0, 3-len(priority_chars))]
                
                # Crear diccionario reducido
                compressed_context["character_states"] = {
                    char: state for char, state in character_states.items() 
                    if char in final_chars
                }
        
        print_progress("✂️ Compresión adaptativa aplicada - Optimizando contexto")
        return compressed_context
    
    def process_generated_content(self, content, section_position, idea):
        """
        Procesa y analiza el contenido generado para detectar problemas
        como colapsos del modelo, repeticiones excesivas o incoherencias.
        
        Args:
            content: Texto generado por el modelo
            section_position: Posición en el capítulo ("inicio", "medio", "final")
            idea: Idea que se intentó desarrollar
            
        Returns:
            tuple: (Contenido procesado, análisis, bool indicando si hay colapso)
        """
        if not content or len(content.strip()) < 20:
            print_progress("⚠️ Contenido generado demasiado corto o vacío")
            return content, {"analysis": {"potential_issues": ["Contenido vacío o muy corto"]}}, True
            
        # Utilizar ContentAnalyzer para detectar riesgo de colapso
        strict_mode = self.generation_state["strict_checking"]
        is_collapsed, detail, analysis = self.content_analyzer.detect_collapse_risk(content, strict_mode)
        
        if is_collapsed:
            # Incrementar contador de colapsos
            self.generation_state["collapse_count"] += 1
            print_progress(f"⚠️ Posible colapso detectado: {detail}")
            
            # Si hemos detectado varios colapsos seguidos, aumentar nivel de riesgo
            if self.generation_state["collapse_count"] > 2:
                self.generation_state["risk_level"] = "high"
                print_progress("🚨 Nivel de riesgo aumentado a ALTO por colapsos repetidos")
                
                # Cambiar a modo de contexto mínimo si el riesgo es alto
                if self.generation_state["context_mode"] != "minimal":
                    self.generation_state["context_mode"] = "minimal"
                    print_progress("🔄 Cambiando a modo de contexto MÍNIMO para recuperación")
        else:
            # Reiniciar contador de colapsos si el contenido es bueno
            if self.generation_state["collapse_count"] > 0:
                self.generation_state["collapse_count"] = 0
                
            # Si estamos en modo mínimo pero el riesgo es bajo, considerar volver a modo estándar
            if (self.generation_state["context_mode"] == "minimal" and 
                self.generation_state["risk_level"] == "high" and 
                len(self.content_analyzer.history) > 3):
                    
                self.generation_state["risk_level"] = "medium"
                print_progress("✅ Reduciendo nivel de riesgo a MEDIO tras generación estable")
        
        # Actualizar memoria con el contenido generado
        self.memory_manager.update_short_term_memory(new_text=content)
        
        # Extraer entidades del contenido para seguimiento
        entities = self.entity_extractor.extract_entities_from_text(
            content, 
            chapter_num=self.current_chapter
        )
        
        # Detectar y almacenar eventos importantes
        if len(content) > 200:  # Solo para contenido sustancial
            self.memory_manager.detect_and_store_events(content, entities)
        
        return content, {"analysis": analysis}, is_collapsed
    
    def regenerate_section_safely(self, llm, idea, section_position, chapter_info):
        """
        Intenta regenerar una sección de forma segura cuando se ha detectado
        un colapso o problema en la generación anterior.
        
        Args:
            llm: Modelo de lenguaje a utilizar
            idea: Idea original a desarrollar
            section_position: Posición en el capítulo
            chapter_info: Información del capítulo actual
            
        Returns:
            str: Contenido regenerado
        """
        print_progress("🔄 Regenerando sección con estrategia de recuperación")
        
        # Guardar estado actual
        original_context_mode = self.generation_state["context_mode"]
        
        try:
            # Cambiar temporalmente a modo de contexto mínimo
            self.generation_state["context_mode"] = "minimal"
            
            # Extraer solo lo esencial del capítulo
            chapter_title = chapter_info.get("title", "este capítulo")
            chapter_num = chapter_info.get("number", self.current_chapter)
            
            # Simplificar la idea al máximo
            simple_idea = idea.split('.')[0] if '.' in idea else idea
            
            # Obtener un contexto ultra minimalista
            minimal_context = self._get_minimal_context(
                section_position,
                simple_idea,
                []  # Sin entidades activas para simplificar
            )
            
            # Crear un prompt muy directo y simple
            prompt = f"""
            Escribe un párrafo narrativo para continuar esta historia.
            
            Estamos en el capítulo {chapter_num}: "{chapter_title}"
            
            Idea a desarrollar: {simple_idea}
            
            {minimal_context.get('core_narrative', '')}
            
            IMPORTANTE: Escribe SOLO texto narrativo en español, sin encabezados ni metadata.
            """
            
            # Generar con temperatura ligeramente más baja para estabilidad
            response = llm(prompt, temperature=0.7)
            
            # Procesar respuesta
            content = clean_think_tags(extract_content_from_llm_response(response))
            
            # Verificar si la regeneración fue exitosa
            is_collapsed, _, _ = self.content_analyzer.detect_collapse_risk(content, False)
            
            if is_collapsed:
                # Si aún falla, intentar una última vez con prompt ultra simplificado
                emergency_prompt = f"""
                Escribe un solo párrafo narrativo para el capítulo "{chapter_title}" 
                desarrollando esta idea: {simple_idea}.
                
                Texto narrativo directo, sin introducción ni comentarios meta:
                """
                
                response = llm(emergency_prompt, temperature=0.65)
                content = clean_think_tags(extract_content_from_llm_response(response))
                
                # Si aún así falla, usar texto de contingencia
                is_still_collapsed, _, _ = self.content_analyzer.detect_collapse_risk(content, False)
                if is_still_collapsed or len(content.strip()) < 50:
                    return f"La historia siguió avanzando. Los personajes continuaron explorando {chapter_title}, enfrentando nuevos desafíos mientras perseguían su objetivo."
            
            print_progress("✅ Regeneración exitosa")
            return content
            
        except Exception as e:
            print_progress(f"Error en regeneración: {str(e)}")
            return f"La narrativa continuó desarrollándose en {chapter_title}."
            
        finally:
            # Restaurar el modo de contexto original
            self.generation_state["context_mode"] = original_context_mode
    
    def health_check(self, llm):
        """
        Realiza un chequeo de salud del sistema para detectar
        posibles problemas antes de que ocurran.
        
        Args:
            llm: Modelo de lenguaje para probar si es necesario
            
        Returns:
            bool: True si el sistema está saludable
        """
        # Verificar estadísticas de colapso
        collapse_stats = self.content_analyzer.get_collapse_stats()
        
        # Si hay demasiados colapsos recientes, el sistema no está saludable
        if collapse_stats["total_collapses"] > 3:
            self.generation_state["risk_level"] = "high"
            return False
            
        # Si el nivel de riesgo es alto, hacer una prueba simple
        if self.generation_state["risk_level"] in ["high", "critical"]:
            try:
                # Prueba simple para verificar si el modelo responde coherentemente
                test_prompt = "Completa esta frase de manera coherente: El sol brillaba en el cielo mientras los pájaros"
                response = llm(test_prompt, temperature=0.2)
                
                # Verificar si la respuesta parece coherente
                if len(response) < 10 or "error" in response.lower():
                    print_progress("❌ Prueba de salud fallida: respuesta incoherente")
                    return False
                    
            except Exception:
                print_progress("❌ Prueba de salud fallida: error en la generación")
                return False
                
        # Sistema saludable por defecto
        return True

    def reset_and_rebuild_context(self, current_narrative_point, idea_to_continue=None, recent_content=None):
        """
        Reinicia el contexto y lo reconstruye con información esencial para continuar
        desde el punto actual de la narrativa manteniendo coherencia.
        
        Esta función es crucial cuando se alcanza el límite de tokens y se necesita
        "refrescar" el contexto manteniendo continuidad narrativa.
        
        Args:
            current_narrative_point: Descripción del punto actual en la narrativa
            idea_to_continue: Idea específica que se estaba desarrollando
            recent_content: Contenido más reciente generado (últimos párrafos)
            
        Returns:
            dict: Contexto reconstruido mínimo pero suficiente para continuar
        """
        print_progress("🔄 Reiniciando y reconstruyendo contexto para continuar generación")
        
        # 1. Limpiar memoria de trabajo (pero preservar memoria a largo plazo)
        self.memory_manager.clear_medium_term_memory()
        
        # 2. Construir contexto minimalista pero suficiente
        rebuilt_context = {}
        
        # Identificar entidades activas en el contenido reciente
        active_entities = []
        if recent_content:
            # Extraer entidades clave del contenido reciente
            active_entities = self.entity_extractor.get_active_entities(
                recent_content,
                chapter_num=self.current_chapter,
                max_entities=3  # Limitar a las 3 más relevantes
            )
            
            # Añadir contenido reciente (últimos 1-2 párrafos) como punto de continuación
            paragraphs = recent_content.split('\n\n')
            if paragraphs:
                # Solo usar el último o los dos últimos párrafos
                if len(paragraphs) > 1:
                    rebuilt_context["continuation_point"] = '\n\n'.join(paragraphs[-2:])
                else:
                    rebuilt_context["continuation_point"] = paragraphs[-1]
        
        # 3. Añadir esencia narrativa ultra-condensada
        book_essence = self.memory_manager.get_book_essence(max_length=150)
        rebuilt_context["core_narrative"] = book_essence
        
        # 4. Añadir descripción del punto actual si está disponible
        if current_narrative_point:
            rebuilt_context["current_point"] = current_narrative_point
            
        # 5. Añadir idea a continuar desarrollando
        if idea_to_continue:
            rebuilt_context["current_idea"] = idea_to_continue
            
        # 6. Añadir personajes activos con descripción mínima
        if active_entities:
            character_mini_info = {}
            for character in active_entities[:3]:  # Solo los 3 más importantes
                # Obtener información ultra-condensada del personaje
                mini_desc = self.memory_manager.get_character_state(
                    character, 
                    include_history=False, 
                    max_length=50  # Descripción muy breve
                )
                if mini_desc:
                    character_mini_info[character] = mini_desc
                    
            if character_mini_info:
                rebuilt_context["active_characters"] = character_mini_info
                
        # 7. Añadir guía de posición actual
        rebuilt_context["position_guidance"] = f"Continuando el capítulo {self.current_chapter} desde donde quedó la narración."
        
        print_progress("✅ Contexto reconstruido para continuar con la generación")
        return rebuilt_context
    
    def manage_token_overflow(self, llm, content_so_far, idea_current, section_position, retry_count=0):
        """
        Maneja situaciones donde se ha excedido el límite de tokens del modelo,
        reiniciando el contexto y permitiendo continuar la generación.
        
        Args:
            llm: Modelo de lenguaje a utilizar
            content_so_far: Contenido generado hasta el momento
            idea_current: Idea que se estaba desarrollando
            section_position: Posición en la sección ("inicio", "medio", "final")
            retry_count: Número de intentos realizados
            
        Returns:
            tuple: (Contenido generado, booleano indicando éxito)
        """
        # Si ya hemos intentado demasiadas veces, abortar para evitar bucles
        if retry_count >= 3:
            print_progress("⚠️ Demasiados intentos de recuperación, generando contenido de emergencia")
            return self._generate_emergency_continuation(content_so_far, idea_current), False
            
        # Crear punto actual narrativo más preciso
        current_point = f"Estamos en el capítulo {self.current_chapter}, {section_position} de la sección, desarrollando: {idea_current[:50]}..."
        
        # Extraer últimos párrafos como punto de continuación
        recent_paragraphs = ""
        if content_so_far:
            paragraphs = content_so_far.split('\n\n')
            if len(paragraphs) > 2:
                recent_paragraphs = '\n\n'.join(paragraphs[-2:])  # Últimos 2 párrafos
            else:
                recent_paragraphs = content_so_far
        
        try:
            # 1. Reiniciar y reconstruir contexto
            fresh_context = self.reset_and_rebuild_context(
                current_point,
                idea_current,
                recent_paragraphs
            )
            
            # 2. Preparar prompt para continuación directa
            continuation_prompt = f"""
            Continúa exactamente desde este punto de la narración, 
            manteniendo el mismo tono y estilo.
            
            CONTEXTO ACTUAL:
            {fresh_context.get('core_narrative', '')}
            
            PUNTO ACTUAL:
            {fresh_context.get('current_point', '')}
            
            IDEA A DESARROLLAR:
            {fresh_context.get('current_idea', '')}
            
            ÚLTIMO CONTENIDO GENERADO:
            {fresh_context.get('continuation_point', '')}
            
            IMPORTANTE: Continúa la narración de forma natural, como si no hubiera
            habido interrupción. No repitas lo anterior ni hagas resúmenes.
            Escribe SOLO texto narrativo en español, sin encabezados ni metadata.
            """
            
            # 3. Generar continuación con temperatura ligeramente reducida para estabilidad
            response = llm(continuation_prompt, temperature=0.7)
            
            # 4. Procesar respuesta
            from utils import clean_think_tags, extract_content_from_llm_response
            new_content = clean_think_tags(extract_content_from_llm_response(response))
            
            # 5. Verificar calidad
            is_collapsed, detail, _ = self.content_analyzer.detect_collapse_risk(new_content, False)
            
            if is_collapsed or len(new_content.strip()) < 50:
                # Si falla, intentar una vez más con un prompt aún más simplificado
                print_progress(f"⚠️ Continuación problemática: {detail}. Reintentando con prompt simplificado.")
                return self.manage_token_overflow(llm, content_so_far, idea_current, section_position, retry_count + 1)
            
            # 6. Si tenemos buen contenido, combinar con el contenido anterior
            if content_so_far and not content_so_far.endswith((".", "!", "?", ":", ";", "—")):
                # Si el contenido anterior no termina con puntuación, añadir punto
                combined_content = content_so_far + ". " + new_content
            else:
                # Si el contenido anterior tiene puntuación final, simplemente añadir nueva línea
                combined_content = content_so_far + "\n\n" + new_content
                
            print_progress("✅ Continuación generada exitosamente tras reinicio de contexto")
            return combined_content, True
            
        except Exception as e:
            print_progress(f"Error durante manejo de overflow: {str(e)}")
            return self._generate_emergency_continuation(content_so_far, idea_current), False
    
    def _generate_emergency_continuation(self, content_so_far, idea_current):
        """
        Genera un contenido de emergencia cuando todos los intentos de
        recuperación han fallado.
        
        Args:
            content_so_far: Contenido generado hasta ahora
            idea_current: Idea que se estaba desarrollando
            
        Returns:
            str: Contenido de emergencia para continuar
        """
        # Extraer palabras clave de la idea actual
        keywords = idea_current.split()[:5]  # Primeras 5 palabras
        keywords_text = " ".join(keywords)
        
        # Generar texto genérico que podría funcionar en cualquier situación
        emergency_text = f"""
        
        La narrativa avanzó mientras los personajes enfrentaban nuevos desafíos. 
        {keywords_text} se convirtió en el centro de atención mientras 
        la historia continuaba desarrollándose con giros inesperados.
        
        """
        
        if content_so_far:
            combined = content_so_far + "\n\n" + emergency_text
            return combined
        else:
            return emergency_text