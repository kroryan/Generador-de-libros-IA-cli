from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response

class ChapterSummaryChain(BaseEventChain):
    """Genera resúmenes de capítulos para mantener la coherencia narrativa entre ellos."""
    
    PROMPT_TEMPLATE = """
    Como editor profesional, crea un resumen breve y esencial del siguiente capítulo.
    El resumen debe capturar SOLO los elementos más importantes para mantener coherencia.
    
    IMPORTANTE: El resumen debe estar en español y ser muy conciso (máximo 150 palabras).
    
    Título del libro: {title}
    Capítulo: {chapter_title} (Capítulo {chapter_num} de {total_chapters})
    
    Contenido del capítulo:
    {chapter_content}
    
    <think>
    Identificaré solo los elementos narrativos cruciales:
    1. Eventos principales que afectan la trama general
    2. Desarrollo significativo de personajes principales
    3. Revelaciones importantes o giros en la trama
    4. Elementos específicos que necesitarán continuidad
    
    Seré extremadamente conciso y preciso, enfocándome solo en lo esencial.
    </think>
    
    Genera un resumen breve y esencial:"""

    # Prompt para resumir incremental por secciones
    PROGRESSIVE_SUMMARY_TEMPLATE = """
    Actualiza el resumen existente para incorporar solo los elementos esenciales 
    de la nueva sección. Mantén el resumen muy breve y centrado solo en lo crucial.
    
    IMPORTANTE: Máximo 150 palabras, solo en español.
    
    Título: {title}
    Capítulo: {chapter_title} (Capítulo {chapter_num})
    
    Resumen actual:
    {current_summary}
    
    Nueva sección:
    {new_section}
    
    <think>
    Analizaré qué elementos nuevos son verdaderamente importantes:
    - ¿Introduce algún evento crítico para la trama?
    - ¿Revela información esencial sobre personajes principales?
    - ¿Presenta un giro o cambio significativo?
    
    Incorporaré solo lo verdaderamente relevante, manteniendo el resumen muy conciso.
    </think>
    
    Resumen actualizado:"""

    def extract_key_segments(self, text, max_segments=3, segment_length=1000):
        """
        Extrae segmentos clave del texto (inicio, medio y final) de manera más eficiente
        con segmentos más pequeños.
        """
        if len(text) <= segment_length * max_segments:
            return text
            
        segments = []
        
        # Incluir inicio (establece personajes y escenario)
        segments.append(text[:segment_length])
        
        # Si hay espacio para más de 2 segmentos, incluir segmento del medio
        if max_segments > 2:
            # Extraer una sección del medio
            middle_pos = len(text) // 2
            middle_start = max(middle_pos - segment_length // 2, segment_length)
            middle_end = min(middle_start + segment_length, len(text) - segment_length)
            segments.append(text[middle_start:middle_end])
        
        # Incluir final (resoluciones, giros finales)
        segments.append(text[-segment_length:])
        
        # Unir los segmentos con indicadores claros
        result = "INICIO DEL CAPÍTULO:\n" + segments[0]
        
        for i in range(1, len(segments) - 1):
            result += f"\n\n[...PARTE MEDIA DEL CAPÍTULO...]\n\n{segments[i]}"
            
        result += f"\n\n[...FINAL DEL CAPÍTULO...]\n\n{segments[-1]}"
            
        return result

    def update_summary_incrementally(self, title, chapter_num, chapter_title, current_summary, new_section, total_chapters):
        """Actualiza un resumen existente incorporando nueva información esencial"""
        print_progress(f"Actualizando resumen incremental del capítulo {chapter_num}...")
        
        # Si no hay resumen actual, crear uno básico
        if not current_summary or current_summary.strip() == "":
            current_summary = f"Inicio del capítulo {chapter_num} ({chapter_title})."
        
        try:
            # Extraer solo fragmentos clave de la nueva sección
            if len(new_section) > 1500:
                # Tomar solo inicio y final (donde suele estar la información clave)
                summary_section = new_section[:750] + "\n\n[...]\n\n" + new_section[-750:]
            else:
                summary_section = new_section
                
            # Nota: El error era que aquí se esperaban parámetros no proporcionados
            # Cambiamos para usar el template directamente con los parámetros correctos
            result = self.invoke(
                title=clean_think_tags(title),
                chapter_num=chapter_num,
                chapter_title=clean_think_tags(chapter_title),
                current_summary=clean_think_tags(current_summary),
                new_section=clean_think_tags(summary_section)
            )
            
            if not result:
                raise ValueError("No se generó contenido válido para el resumen")
                
            # Limitar longitud del resumen incremental para evitar crecimiento excesivo
            if len(result) > 500:
                print_progress("Resumen demasiado largo, truncando...")
                result = result[:500] + "..."
                
            return result
            
        except Exception as e:
            print_progress(f"Error actualizando resumen incremental: {str(e)}")
            return current_summary  # Devolver el resumen anterior sin cambios
    
    def run(self, title, chapter_num, chapter_title, chapter_content, total_chapters):
        """Genera un resumen final conciso del capítulo"""
        print_progress(f"Generando resumen final del capítulo {chapter_num}: {chapter_title}")
        
        try:
            # Preparar el contenido de manera más eficiente
            summarized_content = self.extract_key_segments(chapter_content, 
                                                          max_segments=3, 
                                                          segment_length=1000)
                
            result = self.invoke(
                title=clean_think_tags(title),
                chapter_num=chapter_num,
                chapter_title=clean_think_tags(chapter_title),
                chapter_content=clean_think_tags(summarized_content),
                total_chapters=total_chapters
            )
            
            if not result:
                raise ValueError("No se generó contenido válido para el resumen")
            
            # Limitar longitud del resumen final para no sobrecargar el contexto
            if len(result) > 300:
                print_progress("Resumen final demasiado largo, truncando...")
                result = result[:300] + "..."
                
            print_progress(f"Resumen final del capítulo {chapter_num} completado")
            return result
            
        except Exception as e:
            print_progress(f"Error generando resumen para el capítulo {chapter_num}: {str(e)}")
            return f"Capítulo {chapter_num}: Continúa la historia."

class ProgressiveContextManager:
    """
    Administra el contexto proporcionado al modelo de manera progresiva y minimalista,
    adaptándose a modelos con diferentes capacidades de contexto como Gemma 9B.
    """
    
    def __init__(self, title, framework, total_chapters, model_capacity="standard"):
        self.title = title
        self.framework = self._create_minimal_framework(framework)
        self.total_chapters = total_chapters
        self.chapter_summaries = {}
        self.incremental_summaries = {}
        # Clasificación de capacidad del modelo: "limited" (como Gemma 9B), "standard", "extended"
        self.model_capacity = model_capacity
        # Historial de contexto reciente para capítulos
        self.recent_context_history = {}
        # Caché para resúmenes ultra compactos
        self.ultra_compact_cache = {}
        # Factor de ajuste por capacidad de modelo (en tokens aproximados)
        self.model_capacity_tokens = {
            "limited": 8000,    # Para modelos como Gemma 9B
            "standard": 16000,  # Para modelos estándar
            "extended": 32000   # Para modelos con contexto extendido
        }
        # Seguimiento de uso de tokens
        self.token_usage_history = []
        # Umbral para compresión agresiva (% del presupuesto total)
        self.aggressive_compression_threshold = 0.75

    def _estimate_tokens(self, text):
        """
        Estima el número de tokens en un texto para controlar el uso de contexto.
        Esta es una estimación aproximada - 4 caracteres ≈ 1 token para inglés,
        pero para español usamos un factor un poco menor (3.5 caracteres).
        """
        if not text:
            return 0
            
        # Factores de conversión aproximados por idioma
        chars_per_token = 3.5  # Para español
        
        # Ajuste por espacios y puntuación
        whitespace_count = len([c for c in text if c.isspace()])
        punctuation_count = len([c for c in text if c in ".,;:!?-()[]{}\"'"])
        
        # Los espacios y signos suelen contar como tokens separados en algunos modelos
        adjusted_length = len(text) + (whitespace_count * 0.2) + (punctuation_count * 0.3)
        estimated_tokens = adjusted_length / chars_per_token
        
        return int(estimated_tokens)
        
    def _get_available_context_budget(self):
        """
        Calcula el presupuesto de tokens disponible según la capacidad del modelo,
        reservando espacio para la respuesta y sistema.
        """
        total_capacity = self.model_capacity_tokens.get(self.model_capacity, 16000)
        
        # Reservar aproximadamente 30% para la respuesta y sistema
        available_budget = int(total_capacity * 0.7)
        
        return available_budget
    
    def _create_minimal_framework(self, framework):
        """Crea una versión mínima del marco narrativo con solo puntos clave"""
        # Extraer solo información esencial del framework
        if len(framework) > 500:
            lines = framework.split('\n')
            essential_lines = []
            
            key_terms = [
                "protagonista", "personaje principal", "antagonista", 
                "conflicto central", "objetivo principal", "mundo", 
                "premisa", "trama principal"
            ]
            
            # Extraer solo líneas con información clave
            for line in lines:
                line = line.strip()
                if any(term in line.lower() for term in key_terms):
                    essential_lines.append(line)
            
            # Si no encontramos suficientes líneas esenciales, tomar algunas principales
            if len(essential_lines) < 3:
                return "\n".join(lines[:3])
                
            return "\n".join(essential_lines[:5])  # Limitar a máximo 5 líneas
        return framework
    
    def _extract_framework_essence(self, framework):
        """Extrae la esencia mínima del marco para modelos con contexto limitado"""
        if not framework:
            return ""
            
        # Para modelos limitados, extraer solo 2-3 conceptos clave
        key_phrases = []
        lines = framework.split('\n')
        
        # Identificar las frases más cruciales
        for line in lines:
            line = line.strip()
            if "protagonista:" in line.lower() or "conflicto:" in line.lower() or "premisa:" in line.lower():
                key_phrases.append(line)
                
        # Si no encontramos frases clave, tomar las primeras 2 líneas
        if not key_phrases and len(lines) > 0:
            return "\n".join(lines[:2])
            
        # Limitar a 2-3 frases clave para contexto muy limitado
        return "\n".join(key_phrases[:3])
    
    def add_chapter_summary(self, chapter_num, chapter_key, summary):
        """Añade el resumen de un capítulo a la memoria contextual"""
        # Para modelos con contexto limitado, reducir aún más los resúmenes
        if self.model_capacity == "limited" and len(summary) > 150:
            summary = self._create_ultra_condensed_summary(summary)
            
        self.chapter_summaries[chapter_key] = summary
        
        # Mantener también un registro de los resúmenes más recientes
        # con mayor detalle para los últimos capítulos
        self.recent_context_history[chapter_key] = {
            "summary": summary,
            "chapter_num": chapter_num,
            "last_accessed": 0  # Contador para seguimiento de acceso
        }
    
    def _create_ultra_condensed_summary(self, summary):
        """Crea un resumen ultra condensado para modelos con capacidad limitada"""
        if not summary:
            return ""
            
        # Mejora: implementar técnica de reducción de tokens más agresiva
        if len(summary) < 100:
            return summary
            
        # Para resúmenes largos, aplicar compresión agresiva
        sentences = summary.split('. ')
        
        # Seleccionar solo primera y última oración si hay más de 3
        if len(sentences) > 3:
            key_sentences = [sentences[0], sentences[-1]]
            condensed = '. '.join(key_sentences)
            
            # Eliminar palabras menos importantes para reducir aún más
            stop_words = ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'e', 'o', 'u', 'que', 'como', 'cuando', 'donde']
            for word in stop_words:
                condensed = condensed.replace(f' {word} ', ' ')
                
            return condensed + '.'
        
        # Para resúmenes cortos, eliminar solo palabras de relleno
        else:
            condensed = summary
            stop_words = ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas']
            for word in stop_words:
                condensed = condensed.replace(f' {word} ', ' ')
            return condensed
    
    def get_incremental_summary(self, chapter_num, chapter_key):
        """Obtiene el resumen incremental actual para un capítulo específico"""
        return self.incremental_summaries.get(chapter_key, "")
        
    def update_incremental_summary(self, chapter_num, chapter_key, summary):
        """Actualiza el resumen incremental para un capítulo específico"""
        # Para modelos con contexto limitado, condensar aún más
        if self.model_capacity == "limited" and len(summary) > 150:
            summary = self._create_ultra_condensed_summary(summary)
            
        self.incremental_summaries[chapter_key] = summary
        
    def get_context_for_section(self, current_chapter, section_position, chapter_key):
        """
        Obtiene un contexto progresivo y adaptativo según la posición actual y tipo de modelo.
        """
        # Actualizar contadores de acceso para implementar ventana deslizante
        self._update_access_counters(current_chapter)
        
        # Determinar número de capítulos a incluir según capacidad del modelo
        num_relevant_chapters = self._get_relevant_chapter_count()
        
        # 1. Obtener solo los capítulos más relevantes 
        relevant_chapters = self._get_most_relevant_chapters(current_chapter, num_relevant_chapters)
        
        # 2. Preparar un resumen adaptativo de capítulos anteriores
        previous_chapters_summary = self._create_adaptive_previous_summary(relevant_chapters)
        
        # 3. Adaptar el framework según posición y capacidad del modelo
        adjusted_framework = self._get_adapted_framework(current_chapter, section_position)
            
        # 4. Incluir solo pistas específicas según la posición
        position_context = self._get_position_specific_context(section_position, current_chapter)
        
        # 5. Resumen incremental del capítulo actual (si existe)
        current_chapter_summary = ""
        if chapter_key in self.incremental_summaries and self.incremental_summaries[chapter_key]:
            current_chapter_summary = f"Progreso actual: {self.incremental_summaries[chapter_key]}"
            
        return {
            "framework": adjusted_framework,
            "previous_chapters_summary": previous_chapters_summary,
            "position_context": position_context,
            "current_chapter_summary": current_chapter_summary
        }
    
    def _update_access_counters(self, current_chapter):
        """Actualiza contadores de acceso para implementar ventana deslizante de contexto"""
        for chapter_key, data in self.recent_context_history.items():
            # Incrementar todos los contadores
            data["last_accessed"] += 1
            
            # Para el capítulo inmediatamente anterior, resetear contador
            if data["chapter_num"] == current_chapter - 1:
                data["last_accessed"] = 0
                
            # Para el primer capítulo, mantener contador bajo
            if data["chapter_num"] == 1:
                data["last_accessed"] = min(data["last_accessed"], 3)
                
    def _get_relevant_chapter_count(self):
        """Determina cuántos capítulos incluir según capacidad del modelo"""
        if self.model_capacity == "limited":  # Modelos como Gemma 9B
            return 2  # Solo 1-2 capítulos más relevantes
        elif self.model_capacity == "standard":
            return 3  # 2-3 capítulos relevantes
        else:  # Para modelos con contexto extendido
            return 4  # Hasta 4 capítulos relevantes
    
    def _create_adaptive_previous_summary(self, relevant_chapters):
        """Crea un resumen adaptativo de capítulos previos según capacidad del modelo"""
        if not relevant_chapters:
            return ""
            
        # Para modelos con contexto limitado, formato ultra conciso
        if self.model_capacity == "limited":
            previous_chapters_summary = "Esencial de capítulos previos:\n"
            for ch_key in relevant_chapters:
                if ch_key in self.chapter_summaries:
                    # Solo 1-2 frases para modelos limitados
                    summary = self.chapter_summaries[ch_key]
                    if len(summary) > 100:
                        # Extraer solo las primeras frases
                        sentences = summary.split('.')
                        if len(sentences) > 2:
                            summary = sentences[0].strip() + "."
                    
                    previous_chapters_summary += f"- {ch_key.split(':')[0]}: {summary}\n"
        else:
            # Para modelos estándar, formato más completo
            previous_chapters_summary = "Resumen de capítulos relevantes:\n"
            for ch_key in relevant_chapters:
                if ch_key in self.chapter_summaries:
                    previous_chapters_summary += f"- {ch_key}: {self.chapter_summaries[ch_key]}\n"
        
        return previous_chapters_summary
    
    def _get_adapted_framework(self, current_chapter, section_position):
        """Obtiene una versión del framework adaptada a la posición y capacidad del modelo"""
        # Para capítulos iniciales, proporcionar más contexto del framework
        if current_chapter <= 2:
            if self.model_capacity == "limited":
                return self._extract_framework_essence(self.framework)
            else:
                return self.framework
                
        # Para capítulos intermedios, reducir framework
        elif current_chapter < self.total_chapters - 1:
            if self.model_capacity == "limited":
                # Solo una frase clave para modelos limitados
                framework_lines = self.framework.split('\n')
                if len(framework_lines) > 0:
                    return framework_lines[0]
                return ""
            else:
                # Versión reducida para modelos estándar
                framework_lines = self.framework.split('\n')
                if len(framework_lines) > 2:
                    return "\n".join(framework_lines[:2])
                return self.framework
                
        # Para capítulos finales, incluir pistas de resolución
        else:
            if self.model_capacity == "limited":
                return "Recuerda resolver la trama principal."
            else:
                return "Resuelve las tramas pendientes siguiendo el marco narrativo original."
    
    def _get_position_specific_context(self, section_position, current_chapter):
        """Obtiene contexto específico según la posición en el capítulo"""
        if section_position == "inicio":
            if current_chapter > 1:
                return "Conecta con eventos del capítulo anterior."
            else:
                return "Introduce personajes y escenario principal."
        elif section_position == "medio":
            return "Desarrolla conflicto principal de este capítulo."
        elif section_position == "final":
            if current_chapter < self.total_chapters:
                return "Prepara elementos clave para el siguiente capítulo."
            else:
                return "Cierra la historia resolviendo conflictos principales."
        return ""
    
    def _get_most_relevant_chapters(self, current_chapter, max_chapters=2):
        """
        Implementa una ventana deslizante para obtener solo los capítulos más relevantes,
        priorizando capítulos recientes y capítulos importantes (1er capítulo).
        """
        if not self.chapter_summaries:
            return []
            
        # Convertir chapter_summaries a una lista ordenada por número de capítulo
        all_chapter_keys = sorted(self.chapter_summaries.keys(), 
                               key=lambda x: int(x.split(':')[0].replace('Capítulo ', '')))
        
        relevant_keys = []
        
        # 1. Siempre incluir capítulo inmediatamente anterior si existe
        if current_chapter > 1 and len(all_chapter_keys) >= current_chapter - 1:
            previous_chapter_key = all_chapter_keys[current_chapter - 2]  # -2 por índice 0
            relevant_keys.append(previous_chapter_key)
        
        # 2. Para capítulos posteriores, añadir primer capítulo (establece premisas)
        if current_chapter > 3 and len(all_chapter_keys) > 0:
            relevant_keys.append(all_chapter_keys[0])
            
        # 3. Para la ventana deslizante, añadir capítulos con menor contador de acceso
        if len(all_chapter_keys) > 2 and len(relevant_keys) < max_chapters:
            # Ordenar historial de acceso por contador (menor = más reciente/relevante)
            sorted_by_access = sorted(
                [(k, self.recent_context_history.get(k, {"last_accessed": 999})["last_accessed"]) 
                for k in all_chapter_keys if k not in relevant_keys],
                key=lambda x: x[1]
            )
            
            # Añadir capítulos hasta alcanzar el máximo permitido
            for ch_key, _ in sorted_by_access:
                if len(relevant_keys) >= max_chapters:
                    break
                if ch_key not in relevant_keys:
                    relevant_keys.append(ch_key)
        
        return relevant_keys
        
    def set_model_capacity(self, capacity):
        """
        Establece la capacidad del modelo para ajustar estrategias de contexto.
        capacity: "limited" (como Gemma 9B), "standard", "extended"
        """
        if capacity in ["limited", "standard", "extended"]:
            self.model_capacity = capacity

    def visualize_token_usage(self, context_dict):
        """
        Visualiza el uso de tokens en el contexto actual y genera advertencias
        cuando se acerca al límite del modelo.
        
        Args:
            context_dict: Diccionario con las diferentes partes del contexto
            
        Returns:
            dict: Estadísticas de uso de tokens y advertencias
        """
        import sys
        
        # Calcular tokens por cada componente de contexto
        token_usage = {}
        total_tokens = 0
        
        for key, content in context_dict.items():
            if not content:
                token_usage[key] = 0
                continue
                
            tokens = self._estimate_tokens(content)
            token_usage[key] = tokens
            total_tokens += tokens
        
        # Añadir al historial para seguimiento
        self.token_usage_history.append(total_tokens)
        if len(self.token_usage_history) > 10:
            self.token_usage_history.pop(0)  # Mantener solo los 10 más recientes
            
        # Calcular porcentaje del presupuesto disponible
        available_budget = self._get_available_context_budget()
        usage_percentage = (total_tokens / available_budget) * 100
        
        # Generar visualización
        result = {
            "total_tokens": total_tokens,
            "available_budget": available_budget,
            "usage_percentage": round(usage_percentage, 1),
            "component_usage": token_usage,
            "warnings": []
        }
        
        # Generar advertencias si es necesario
        if usage_percentage > 90:
            result["warnings"].append("¡CRÍTICO! Uso de contexto extremadamente alto")
        elif usage_percentage > 75:
            result["warnings"].append("ADVERTENCIA: Uso de contexto alto, considere comprimir más")
            
        # Si el uso ha aumentado significativamente desde la última vez
        if len(self.token_usage_history) > 1 and total_tokens > self.token_usage_history[-2] * 1.2:
            result["warnings"].append("ALERTA: Crecimiento rápido del contexto detectado")
            
        # Imprimir visualización en modo de depuración
        if 'debug' in sys.argv or self.model_capacity == "limited":
            print(f"\n--- 📊 Uso de contexto ({self.model_capacity}) ---")
            print(f"Total: {total_tokens} tokens ({usage_percentage:.1f}% del presupuesto)")
            print(f"Framework: {token_usage.get('framework', 0)} tokens")
            print(f"Resúmenes previos: {token_usage.get('previous_chapters_summary', 0)} tokens")
            print(f"Capítulo actual: {token_usage.get('current_chapter_summary', 0)} tokens")
            for warning in result["warnings"]:
                print(f"⚠️ {warning}")
            print("-----------------------------------\n")
            
        return result
        
    def apply_adaptive_compression(self, context_dict):
        """
        Aplica compresión adaptativa al contexto basado en el uso actual de tokens
        y la capacidad del modelo, especialmente útil para Gemma 9B.
        
        Args:
            context_dict: Diccionario con componentes del contexto
            
        Returns:
            dict: Contexto comprimido adaptado a la capacidad del modelo
        """
        # Analizar uso actual
        usage_stats = self.visualize_token_usage(context_dict)
        
        # Si estamos por debajo del umbral, no comprimir
        if usage_stats["usage_percentage"] < 70:
            return context_dict
            
        compressed_context = context_dict.copy()
        
        # Para modelos limitados o cuando se excede el umbral
        if self.model_capacity == "limited" or usage_stats["usage_percentage"] > self.aggressive_compression_threshold * 100:
            # 1. Comprimir framework a su mínima expresión
            framework = compressed_context.get("framework", "")
            if framework and len(framework) > 100:
                # Extraer solo la primera línea o frase
                compressed_context["framework"] = framework.split('\n')[0].split('.')[0] + '.'
            
            # 2. Reducir drásticamente resúmenes de capítulos previos
            prev_summary = compressed_context.get("previous_chapters_summary", "")
            if prev_summary:
                lines = prev_summary.split('\n')
                # Mantener solo la primera línea de cada capítulo
                compressed_lines = []
                for line in lines:
                    if line.startswith('-') or line.startswith('•'):
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            # Tomar solo la primera frase del resumen
                            first_sentence = parts[1].split('.')[0].strip() + '.'
                            compressed_lines.append(f"{parts[0]}: {first_sentence}")
                
                if compressed_lines:
                    compressed_context["previous_chapters_summary"] = "Esencial:\n" + '\n'.join(compressed_lines[:3])
                else:
                    compressed_context["previous_chapters_summary"] = "Esencial: Continúa la historia."
            
            # 3. Reducir contexto de capítulo actual
            current_summary = compressed_context.get("current_chapter_summary", "")
            if current_summary and len(current_summary) > 100:
                sentences = current_summary.split('.')
                compressed_context["current_chapter_summary"] = sentences[0].strip() + '.'
        
        # Verificar reducción lograda
        new_usage = self.visualize_token_usage(compressed_context)
        savings = usage_stats["total_tokens"] - new_usage["total_tokens"]
        
        if savings > 0:
            print(f"Compresión adaptativa aplicada: {savings} tokens ahorrados")
            
        return compressed_context

    def detect_collapse_risk(self, response_text):
        """
        Detecta señales tempranas de que el modelo podría estar colapsando.
        
        Args:
            response_text: Texto generado por el modelo
            
        Returns:
            tuple: (bool indicando riesgo, mensaje de diagnóstico)
        """
        import re
        
        # Si no hay texto o es muy corto, no podemos analizar
        if not response_text or len(response_text) < 20:
            return False, "Texto demasiado corto para analizar"
        
        # Patrones de repetición que indican colapso
        collapse_patterns = [
            r'(\*\*[^*\n]{1,20})\1{3,}',  # Repetición de patrones con asteriscos
            r'(Capítulo\s*\d*\s*:?)\s*\1{2,}',  # Repetición de "Capítulo"
            r'([^\n]{5,20})\1{4,}',  # Cualquier fragmento repetido muchas veces
        ]
        
        # Verificar patrones de colapso
        for pattern in collapse_patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                return True, "Patrón de repetición detectado: posible colapso de modelo"
        
        # Verificar longitud extremadamente corta (respuesta truncada)
        if len(response_text.strip()) < 50 and "capítulo" in response_text.lower():
            return True, "Respuesta truncada: posible contexto excesivo"
            
        # Verificar si hay líneas vacías excesivas
        empty_lines = len(re.findall(r'\n\s*\n\s*\n', response_text))
        if empty_lines > 5:
            return True, "Formato degradado: exceso de líneas vacías"
            
        return False, "Sin riesgo detectado"

    def get_minimal_context(self):
        """
        Obtiene un contexto mínimo para recuperar un modelo en riesgo de colapso.
        Solo incluye lo absolutamente esencial.
        
        Returns:
            dict: Contexto ultra mínimo para evitar colapso
        """
        # Para modelos en riesgo, solo regresar lo absolutamente indispensable
        minimal_context = {}
        
        # Extraer datos esenciales del título
        title_essence = self.title.split(':')[0] if ':' in self.title else self.title
        
        # 1. Obtener solo una frase crucial del framework
        framework_essence = ""
        if self.framework:
            framework_lines = self.framework.split('\n')
            if framework_lines:
                for line in framework_lines:
                    if "premisa" in line.lower() or "protagonista" in line.lower():
                        framework_essence = line
                        break
                
                # Si no encontramos líneas con premisa, usar la primera
                if not framework_essence and framework_lines:
                    framework_essence = framework_lines[0]
        
        # 2. Para contexto previo, solo el capítulo inmediatamente anterior
        previous_context = ""
        if len(self.recent_context_history) > 0:
            # Ordenar por último acceso (0 = más reciente)
            recent_chapters = sorted(
                [(k, v) for k, v in self.recent_context_history.items()],
                key=lambda x: x[1]["last_accessed"]
            )
            
            if recent_chapters:
                chapter_key, data = recent_chapters[0]
                # Extraer solo la primera oración
                summary = data["summary"].split('.')[0] + '.' if data["summary"] else ""
                previous_context = f"Anterior: {summary}"
        
        # Construir el contexto mínimo
        minimal_context["framework"] = framework_essence
        minimal_context["previous_chapters_summary"] = previous_context
        minimal_context["position_context"] = "Continúa la narrativa."
        minimal_context["current_chapter_summary"] = ""
            
        return minimal_context
    
    def apply_emergency_compression(self, context_dict):
        """
        Aplica una compresión de emergencia cuando se detecta riesgo de colapso.
        Mucho más agresiva que la compresión adaptativa normal.
        
        Args:
            context_dict: Diccionario con componentes del contexto
            
        Returns:
            dict: Contexto ultra-comprimido para recuperar al modelo
        """
        import re
        from utils import print_progress
        
        emergency_context = {}
        
        # 1. Framework: solo conservar 1 oración clave
        framework = context_dict.get("framework", "")
        if framework:
            # Buscar la línea más importante (contiene premisa o protagonista)
            key_line = ""
            for line in framework.split('\n'):
                if "premisa" in line.lower() or "protagonista" in line.lower():
                    key_line = line
                    break
            
            # Si no hay línea clave, tomar la primera línea o frase
            if not key_line:
                sentences = framework.split('.')
                key_line = sentences[0] if sentences else framework[:50]
            
            emergency_context["framework"] = key_line[:100].strip() + "."
            
        # 2. Resumen previo: solo mencionar capítulo anterior si existe
        prev_summary = context_dict.get("previous_chapters_summary", "")
        if prev_summary:
            chapter_mentions = re.findall(r'Capítulo \d+', prev_summary)
            if chapter_mentions:
                latest_chapter = chapter_mentions[-1]
                emergency_context["previous_chapters_summary"] = f"Continúa desde {latest_chapter}."
            else:
                emergency_context["previous_chapters_summary"] = "Continúa la narrativa anterior."
                
        # 3. Simplificar contexto de posición
        position = context_dict.get("position_context", "")
        if position:
            emergency_context["position_context"] = position.split('.')[0] + "."
            
        # 4. Eliminar resumen incremental para ahorrar tokens
        emergency_context["current_chapter_summary"] = ""
        
        print_progress("⚠️ APLICANDO COMPRESIÓN DE EMERGENCIA - RIESGO DE COLAPSO")
        return emergency_context