class HierarchicalMemoryManager:
    """
    Sistema avanzado de gestión de memoria jerárquica para LLMs con tres niveles
    de abstracción que imita la memoria humana: a corto plazo, a medio plazo y a largo plazo.
    Elimina completamente el problema de colapso de contexto maximizando la coherencia.
    """
    
    def __init__(self, title, framework, total_chapters):
        self.title = title
        self.framework = framework
        self.total_chapters = total_chapters
        
        # Memoria a corto plazo (detalles inmediatos y específicos - volátil)
        self.short_term_memory = {
            "current_scene": "",  # Último párrafo/escena siendo procesada
            "recent_paragraphs": [],  # Últimos 2-3 párrafos (solo para continuidad)
            "current_entities": set()  # Personajes/elementos activos en la escena actual
        }
        
        # Memoria a medio plazo (información del capítulo actual)
        self.medium_term_memory = {
            "chapter_key_events": [],  # Eventos principales del capítulo actual
            "active_plotlines": [],  # Subtramas activas en el capítulo
            "character_states": {},  # Estado emocional/situacional de personajes
        }
        
        # Memoria a largo plazo (estructurada por importancia, no cronológicamente)
        self.long_term_memory = {
            "core_narrative": self._extract_core_narrative(framework),  # Esencia narrativa inmutable
            "character_profiles": {},  # Perfiles condensados de personajes principales
            "world_rules": [],  # Reglas fundamentales del mundo/universo
            "major_events": [],  # Solo eventos transformadores
            "chapter_summaries": {},  # Resúmenes ultra-condensados por capítulo
        }
        
        # Índice vectorial para búsqueda semántica (simulado)
        self.semantic_index = []
        
        # Metadatos para seguimiento y estadísticas
        self.token_usage = {"short": 0, "medium": 0, "long": 0, "total": 0}
        self.refresh_counts = {"short": 0, "medium": 0, "long": 0}
        self.last_access = {"short": 0, "medium": 0, "long": 0}
    
    def _extract_core_narrative(self, framework):
        """Extrae solo la esencia narrativa absolutamente inmutable del framework"""
        if not framework:
            return ""
            
        core_elements = []
        key_terms = ["premisa", "conflicto principal", "protagonista", "objetivo", "mundo"]
        
        for line in framework.split('\n'):
            line = line.strip()
            if any(term in line.lower() for term in key_terms):
                # Extraer solo la información, sin etiquetas
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        core_elements.append(parts[1].strip())
                else:
                    core_elements.append(line)
        
        # Si no encontramos elementos clave, tomar la primera línea
        if not core_elements and framework:
            core_elements = [framework.split('\n')[0]]
            
        return ". ".join(core_elements)
    
    def get_context_for_generation(self, generation_stage, section_position, chapter_num=None, idea=None):
        """
        Construye un contexto optimizado según la etapa específica de generación
        adaptando dinámicamente el nivel de detalle según necesidad exacta.
        
        Args:
            generation_stage: Etapa de generación ('planning', 'writing', 'revision')
            section_position: Posición en la narración ('inicio', 'medio', 'final')
            chapter_num: Número de capítulo actual
            idea: Idea a desarrollar en esta sección
            
        Returns:
            dict: Contexto optimizado para esta etapa específica
        """
        context = {}
        
        # 1. Información básica invariable - siempre incluida
        context["core_narrative"] = self.long_term_memory["core_narrative"]
        
        # 2. Contexto según la etapa de generación
        if generation_stage == "planning":
            # Para planificación: enfoque en estructura y arco narrativo
            context["world_rules"] = self.long_term_memory["world_rules"]
            context["major_events"] = self.long_term_memory["major_events"]
            # Omitimos detalles específicos de escenas
            
        elif generation_stage == "writing":
            # Para escritura: foco en continuidad inmediata y desarrollo de la idea actual
            context["recent_paragraphs"] = "\n\n".join(self.short_term_memory["recent_paragraphs"][-2:])
            context["current_entities"] = ", ".join(list(self.short_term_memory["current_entities"]))
            
            # Solo incluir estados de personajes que aparecen en la escena actual
            relevant_characters = {}
            for character in self.short_term_memory["current_entities"]:
                if character in self.medium_term_memory["character_states"]:
                    relevant_characters[character] = self.medium_term_memory["character_states"][character]
            context["character_states"] = relevant_characters
            
            # Si tenemos una idea específica a desarrollar
            if idea:
                context["current_idea"] = idea
                
            # Para posición 'inicio' o 'final', agregar contexto adicional
            if section_position == "inicio" and chapter_num > 1:
                # Recuperar resumen del capítulo anterior para conectar eventos
                prev_chapter_key = f"Capítulo {chapter_num-1}"
                if prev_chapter_key in self.long_term_memory["chapter_summaries"]:
                    context["previous_chapter"] = self.long_term_memory["chapter_summaries"][prev_chapter_key]
            
            elif section_position == "final":
                # Incluir subtramas activas para ayudar a resolverlas o conectarlas al siguiente capítulo
                context["active_plotlines"] = self.medium_term_memory["active_plotlines"]
                
        elif generation_stage == "revision":
            # Para revisión: enfoque en coherencia global y consistencia
            context["chapter_key_events"] = self.medium_term_memory["chapter_key_events"]
            
            # Incluir resúmenes de capítulos relevantes
            relevant_summaries = {}
            if chapter_num:
                # Capítulo actual y anterior
                current_key = f"Capítulo {chapter_num}"
                prev_key = f"Capítulo {chapter_num-1}" if chapter_num > 1 else None
                
                if current_key in self.long_term_memory["chapter_summaries"]:
                    relevant_summaries[current_key] = self.long_term_memory["chapter_summaries"][current_key]
                    
                if prev_key and prev_key in self.long_term_memory["chapter_summaries"]:
                    relevant_summaries[prev_key] = self.long_term_memory["chapter_summaries"][prev_key]
                    
            context["relevant_summaries"] = relevant_summaries
        
        # Actualizar contadores de acceso
        self._update_access_counters(generation_stage)
        
        # Estimar uso de tokens y actualizar estadísticas
        self._update_token_usage(context)
        
        return context
    
    def update_short_term_memory(self, new_text, active_entities=None):
        """
        Actualiza la memoria a corto plazo con el texto más reciente generado
        y las entidades (personajes, objetos) activas en la escena actual.
        """
        # Actualizar texto actual
        self.short_term_memory["current_scene"] = new_text
        
        # Mantener solo los últimos 3 párrafos para continuidad inmediata
        paragraphs = new_text.split('\n\n')
        self.short_term_memory["recent_paragraphs"].extend(paragraphs)
        if len(self.short_term_memory["recent_paragraphs"]) > 3:
            self.short_term_memory["recent_paragraphs"] = self.short_term_memory["recent_paragraphs"][-3:]
        
        # Actualizar entidades activas
        if active_entities:
            self.short_term_memory["current_entities"] = set(active_entities)
        
        # Incrementar contador de refrescos
        self.refresh_counts["short"] += 1
    
    def update_medium_term_memory(self, key_event=None, plotline_update=None, character_updates=None):
        """
        Actualiza la memoria a medio plazo con eventos importantes del capítulo actual,
        cambios en subtramas y actualizaciones de estado de personajes.
        """
        # Añadir evento clave del capítulo si se proporciona
        if key_event:
            self.medium_term_memory["chapter_key_events"].append(key_event)
            # Limitar a los 5 eventos más importantes
            if len(self.medium_term_memory["chapter_key_events"]) > 5:
                self.medium_term_memory["chapter_key_events"] = self.medium_term_memory["chapter_key_events"][-5:]
        
        # Actualizar subtramas
        if plotline_update:
            # Si es una nueva subtrama, añadirla
            if plotline_update not in self.medium_term_memory["active_plotlines"]:
                self.medium_term_memory["active_plotlines"].append(plotline_update)
            
            # Limitar a 3-4 subtramas activas
            if len(self.medium_term_memory["active_plotlines"]) > 4:
                self.medium_term_memory["active_plotlines"] = self.medium_term_memory["active_plotlines"][-4:]
        
        # Actualizar estados de personajes
        if character_updates:
            for character, state in character_updates.items():
                self.medium_term_memory["character_states"][character] = state
        
        # Incrementar contador de refrescos
        self.refresh_counts["medium"] += 1
    
    def update_long_term_memory(self, chapter_num=None, chapter_summary=None, major_event=None, character_profile=None):
        """
        Actualiza la memoria a largo plazo con información estructural importante
        como resúmenes de capítulos, eventos transformadores y perfiles de personajes.
        """
        # Actualizar resumen de capítulo
        if chapter_num and chapter_summary:
            chapter_key = f"Capítulo {chapter_num}"
            # Condensar el resumen para almacenamiento a largo plazo
            condensed_summary = self._create_ultra_condensed_summary(chapter_summary)
            self.long_term_memory["chapter_summaries"][chapter_key] = condensed_summary
            
            # Actualizar índice semántico (simulado)
            self.semantic_index.append({
                "type": "chapter_summary",
                "key": chapter_key,
                "content": condensed_summary,
                "chapter_num": chapter_num
            })
        
        # Añadir evento transformador
        if major_event:
            self.long_term_memory["major_events"].append(major_event)
            
            # Actualizar índice semántico
            self.semantic_index.append({
                "type": "major_event",
                "content": major_event
            })
        
        # Actualizar perfil de personaje
        if character_profile and "name" in character_profile:
            char_name = character_profile["name"]
            self.long_term_memory["character_profiles"][char_name] = character_profile
            
            # Actualizar índice semántico
            self.semantic_index.append({
                "type": "character_profile",
                "key": char_name,
                "content": str(character_profile)
            })
        
        # Incrementar contador de refrescos
        self.refresh_counts["long"] += 1
    
    def clear_medium_term_memory(self):
        """
        Limpia la memoria a medio plazo al finalizar un capítulo,
        guardando primero la información relevante en la memoria a largo plazo.
        """
        # Extraer información relevante para memoria a largo plazo
        key_events = ". ".join(self.medium_term_memory["chapter_key_events"])
        
        # Determinar si algún evento es lo suficientemente importante
        if key_events and len(key_events) > 100:
            self.update_long_term_memory(major_event=key_events)
        
        # Actualizar perfiles de personaje con sus estados actuales
        for character, state in self.medium_term_memory["character_states"].items():
            if character in self.long_term_memory["character_profiles"]:
                # Actualizar solo cambios significativos
                self.long_term_memory["character_profiles"][character]["current_state"] = state
        
        # Reiniciar memoria a medio plazo
        self.medium_term_memory = {
            "chapter_key_events": [],
            "active_plotlines": [],
            "character_states": {},
        }
        
        # Limpiar también la memoria a corto plazo
        self.short_term_memory = {
            "current_scene": "",
            "recent_paragraphs": [],
            "current_entities": set()
        }
    
    def _create_ultra_condensed_summary(self, summary):
        """Crea un resumen ultra condensado para almacenamiento a largo plazo"""
        if not summary or len(summary) < 100:
            return summary
            
        # Extraer solo frases clave con información crítica
        sentences = summary.split('. ')
        if len(sentences) <= 2:
            return summary
            
        # Para resúmenes más largos, tomar solo primera y última frase
        condensed = f"{sentences[0]}. {sentences[-1]}"
        
        # Eliminar palabras menos importantes para reducir aún más
        stop_words = ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'e', 'o', 'u', 'que', 'como']
        for word in stop_words:
            condensed = condensed.replace(f' {word} ', ' ')
            
        return condensed
    
    def semantic_search(self, query, result_count=2):
        """
        Realiza una búsqueda semántica en el índice para encontrar
        información relevante a la consulta actual.
        
        Args:
            query: Consulta o tema para buscar
            result_count: Número de resultados a devolver
            
        Returns:
            list: Información relevante encontrada
        """
        # Simulación simple de búsqueda semántica
        # En un sistema real, utilizaríamos embeddings y búsqueda de similitud coseno
        
        # Convertir query a palabras clave
        keywords = query.lower().split()
        scored_results = []
        
        # Puntuar cada entrada en el índice
        for entry in self.semantic_index:
            score = 0
            content = entry["content"].lower()
            
            # Contar coincidencias de palabras clave
            for keyword in keywords:
                if keyword in content:
                    score += 1
            
            # Añadir bonus por tipo específico si se menciona
            if "character" in query.lower() and entry["type"] == "character_profile":
                score += 2
            elif "event" in query.lower() and entry["type"] == "major_event":
                score += 2
            elif "chapter" in query.lower() and entry["type"] == "chapter_summary":
                score += 2
                
            if score > 0:
                scored_results.append((entry, score))
        
        # Ordenar por puntuación y devolver los mejores resultados
        sorted_results = sorted(scored_results, key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in sorted_results[:result_count]]
    
    def _update_access_counters(self, memory_type):
        """Actualiza contadores de acceso para todas las memorias"""
        for mem_type in ["short", "medium", "long"]:
            self.last_access[mem_type] += 1
            
        # Resetear contador para el tipo que acabamos de acceder
        if memory_type == "planning":
            self.last_access["long"] = 0
        elif memory_type == "writing":
            self.last_access["short"] = 0
            self.last_access["medium"] = 0
        elif memory_type == "revision":
            self.last_access["medium"] = 0
    
    def _update_token_usage(self, context):
        """Estima y actualiza el uso de tokens para el contexto actual"""
        # Función simple para estimar tokens (4 caracteres ~ 1 token)
        def estimate_tokens(text):
            if not text:
                return 0
            return len(str(text)) // 4
        
        # Calcular uso por tipo de memoria
        short_tokens = estimate_tokens(context.get("recent_paragraphs", "")) + \
                      estimate_tokens(context.get("current_entities", ""))
                      
        medium_tokens = estimate_tokens(context.get("character_states", {})) + \
                       estimate_tokens(context.get("active_plotlines", []))
                       
        long_tokens = estimate_tokens(context.get("core_narrative", "")) + \
                     estimate_tokens(context.get("major_events", [])) + \
                     estimate_tokens(context.get("relevant_summaries", {}))
        
        # Actualizar contadores
        self.token_usage["short"] = short_tokens
        self.token_usage["medium"] = medium_tokens
        self.token_usage["long"] = long_tokens
        self.token_usage["total"] = short_tokens + medium_tokens + long_tokens
        
        return self.token_usage
    
    def get_memory_stats(self):
        """Devuelve estadísticas sobre el uso de memoria y tokens"""
        return {
            "token_usage": self.token_usage,
            "refresh_counts": self.refresh_counts,
            "last_access": self.last_access,
            "long_term_items": {
                "chapters": len(self.long_term_memory["chapter_summaries"]),
                "characters": len(self.long_term_memory["character_profiles"]),
                "major_events": len(self.long_term_memory["major_events"])
            },
            "semantic_index_size": len(self.semantic_index)
        }