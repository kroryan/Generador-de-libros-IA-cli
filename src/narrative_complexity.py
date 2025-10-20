"""
Análisis de Complejidad Narrativa para Ajuste Dinámico de Contexto.
Analiza elementos narrativos para determinar cuánto contexto necesita la historia.
"""

import re
from typing import Set, Dict, List, Optional
from logging_config import get_logger

logger = get_logger("narrative_complexity")

class NarrativeComplexityAnalyzer:
    """Analiza complejidad narrativa para ajustar contexto"""
    
    def __init__(self):
        self.entities = {
            "characters": set(),
            "locations": set(),
            "plot_threads": [],
            "temporal_markers": set()
        }
        self.complexity_score = 1.0
        self.section_count = 0
        
        # Palabras que NO son nombres propios
        self.non_names = {
            "El", "La", "Los", "Las", "En", "Con", "Por", "Pero", "Sin", "Hasta",
            "Desde", "Durante", "Mientras", "Aunque", "Cuando", "Donde", "Como",
            "Si", "No", "Sí", "Muy", "Más", "Menos", "Tanto", "Todo", "Todos",
            "Esta", "Este", "Estos", "Estas", "Ese", "Esa", "Esos", "Esas",
            "Aquí", "Ahí", "Allí", "Ahora", "Después", "Antes", "Luego", "Ya"
        }
        
        # Patrones para detectar elementos narrativos
        self.dialogue_patterns = [
            r'["«»"""].*?["«»"""]',      # Diálogos entre comillas
            r'—.*?—',                    # Diálogos con rayas  
            r'-\s*¿?[A-Z].*?[?!.].*?-',  # Diálogos con guiones
            r'-\s*[A-ZÁÉÍÓÚÑ].*?[.!?]',  # Líneas de diálogo con guión
            r'¿[^?]*\?',                 # Preguntas
            r'¡[^!]*!'                   # Exclamaciones
        ]
        
        self.action_patterns = [
            r'\b(corrió|caminó|miró|vio|escuchó|sintió|pensó|dijo|gritó|susurró)\b',
            r'\b(abrió|cerró|tomó|dejó|encontró|perdió|buscó|halló)\b',
            r'\b(llegó|partió|entró|salió|subió|bajó|avanzó|retrocedió)\b'
        ]
        
        self.emotion_patterns = [
            r'\b(feliz|triste|enojado|nervioso|preocupado|emocionado|asustado)\b',
            r'\b(alegría|tristeza|ira|miedo|amor|odio|esperanza|desesperación)\b',
            r'\b(sonrió|lloró|suspiró|tembló|se estremeció|se ruborizó)\b'
        ]
    
    def analyze_section(self, text: str, section_number: int = None) -> Dict[str, any]:
        """Analiza una sección y actualiza métricas"""
        self.section_count += 1
        
        # Detectar nombres propios (entidades)
        new_characters = self._extract_characters(text)
        new_locations = self._extract_locations(text)
        
        # Actualizar entidades globales
        self.entities["characters"].update(new_characters)
        self.entities["locations"].update(new_locations)
        
        # Analizar elementos narrativos
        dialogue_count = self._count_dialogues(text)
        action_count = self._count_actions(text) 
        emotion_count = self._count_emotions(text)
        
        # Detectar cambios temporales o de escena
        scene_changes = self._detect_scene_changes(text)
        
        # Calcular score de complejidad
        char_count = len(self.entities["characters"])
        loc_count = len(self.entities["locations"])
        
        # Fórmula de complejidad narrativa
        base_complexity = self._calculate_base_complexity(char_count, loc_count)
        narrative_density = self._calculate_narrative_density(
            dialogue_count, action_count, emotion_count, len(text)
        )
        
        # Score final (combinación ponderada)
        self.complexity_score = (base_complexity * 0.6) + (narrative_density * 0.4)
        
        # Aplicar suavizado temporal para evitar cambios bruscos
        if hasattr(self, '_previous_complexity'):
            smoothing_factor = 0.3
            self.complexity_score = (
                (1 - smoothing_factor) * self.complexity_score +
                smoothing_factor * self._previous_complexity
            )
        
        self._previous_complexity = self.complexity_score
        
        analysis_result = {
            "section_number": section_number or self.section_count,
            "character_count": char_count,
            "location_count": loc_count,
            "new_characters": len(new_characters),
            "new_locations": len(new_locations),
            "dialogue_density": dialogue_count / max(1, len(text.split())),
            "action_density": action_count / max(1, len(text.split())),
            "emotion_density": emotion_count / max(1, len(text.split())),
            "scene_changes": scene_changes,
            "complexity_score": self.complexity_score,
            "narrative_elements": {
                "dialogues": dialogue_count,
                "actions": action_count,
                "emotions": emotion_count
            }
        }
        
        logger.debug(f"Sección {self.section_count}: {char_count} personajes, "
                    f"{loc_count} ubicaciones, complejidad={self.complexity_score:.2f}")
        
        return analysis_result
    
    def _extract_characters(self, text: str) -> Set[str]:
        """Extrae nombres de personajes del texto"""
        words = re.findall(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b', text)
        
        potential_names = set()
        for word in words:
            # Filtrar palabras que no son nombres
            if word not in self.non_names and len(word) > 2:
                # Verificar que aparece en contexto de personaje
                if self._appears_as_character(word, text):
                    potential_names.add(word)
        
        return potential_names
    
    def _extract_locations(self, text: str) -> Set[str]:
        """Extrae nombres de lugares del texto"""
        # Patrones para lugares
        location_patterns = [
            r'\ben\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
            r'\bdesde\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
            r'\bhacia\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
            r'\bla\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
            r'\bel\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)'
        ]
        
        locations = set()
        for pattern in location_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                location = match.group(1).strip()
                if len(location) > 3 and location not in self.non_names:
                    locations.add(location)
        
        return locations
    
    def _appears_as_character(self, name: str, text: str) -> bool:
        """Verifica si una palabra aparece como personaje"""
        # Buscar patrones que indican personajes
        character_patterns = [
            rf'\b{name}\s+(dijo|respondió|pensó|sintió|vio|escuchó)',
            rf'\b{name}\s+(caminó|corrió|se\s+dirigió|se\s+acercó)',
            rf'(dijo|respondió)\s+{name}',
            rf'\b{name}\s+(estaba|era|tenía|llevaba)',
            rf'(el|la)\s+{name}(?:\s|$|\.)'  # "el Juan", "la María"
        ]
        
        for pattern in character_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _count_dialogues(self, text: str) -> int:
        """Cuenta elementos de diálogo en el texto"""
        dialogue_count = 0
        for pattern in self.dialogue_patterns:
            dialogue_count += len(re.findall(pattern, text))
        return dialogue_count
    
    def _count_actions(self, text: str) -> int:
        """Cuenta elementos de acción en el texto"""
        action_count = 0
        for pattern in self.action_patterns:
            action_count += len(re.findall(pattern, text, re.IGNORECASE))
        return action_count
    
    def _count_emotions(self, text: str) -> int:
        """Cuenta elementos emocionales en el texto"""
        emotion_count = 0
        for pattern in self.emotion_patterns:
            emotion_count += len(re.findall(pattern, text, re.IGNORECASE))
        return emotion_count
    
    def _detect_scene_changes(self, text: str) -> int:
        """Detecta cambios de escena o temporales"""
        scene_markers = [
            r'\bmás\s+tarde\b', r'\bdespués\s+de\b', r'\bal\s+día\s+siguiente\b',
            r'\bmientras\s+tanto\b', r'\ben\s+otro\s+lugar\b', r'\bpor\s+su\s+parte\b',
            r'\b\*\*\*\b', r'\b---\b', r'^\s*\n\s*\n'  # Separadores visuales
        ]
        
        changes = 0
        for marker in scene_markers:
            changes += len(re.findall(marker, text, re.IGNORECASE | re.MULTILINE))
        
        return changes
    
    def _calculate_base_complexity(self, char_count: int, loc_count: int) -> float:
        """Calcula complejidad base según entidades"""
        # Fórmula: más personajes y lugares = mayor complejidad
        if char_count <= 2 and loc_count <= 1:
            return 1.0  # Baja complejidad: pocos personajes, un lugar
        elif char_count <= 5 and loc_count <= 3:
            return 1.3  # Media complejidad: varios personajes, pocos lugares
        elif char_count <= 8 and loc_count <= 5:
            return 1.5  # Alta complejidad: muchos personajes, varios lugares
        else:
            return 1.7  # Muy alta: cast complejo, múltiples ubicaciones
    
    def _calculate_narrative_density(self, dialogues: int, actions: int, 
                                   emotions: int, text_length: int) -> float:
        """Calcula densidad narrativa (riqueza de elementos por palabra)"""
        if text_length == 0:
            return 1.0
        
        word_count = len(text_length.split()) if isinstance(text_length, str) else max(1, text_length // 5)
        
        # Densidad de elementos narrativos
        total_elements = dialogues + actions + emotions
        density = total_elements / word_count
        
        # Normalizar a rango 0.8 - 1.4
        if density < 0.01:
            return 0.8  # Muy baja densidad narrativa
        elif density < 0.03:
            return 1.0  # Normal
        elif density < 0.05:
            return 1.2  # Alta densidad
        else:
            return 1.4  # Muy alta densidad
    
    def get_context_multiplier(self) -> float:
        """Retorna multiplicador para límites de contexto"""
        # Limitar el multiplicador a un rango razonable
        return max(0.8, min(1.8, self.complexity_score))
    
    def get_complexity_report(self) -> Dict[str, any]:
        """Genera reporte detallado de complejidad"""
        return {
            "overall_complexity": self.complexity_score,
            "context_multiplier": self.get_context_multiplier(),
            "entities": {
                "characters": list(self.entities["characters"]),
                "locations": list(self.entities["locations"]),
                "character_count": len(self.entities["characters"]),
                "location_count": len(self.entities["locations"])
            },
            "sections_analyzed": self.section_count,
            "complexity_category": self._get_complexity_category()
        }
    
    def _get_complexity_category(self) -> str:
        """Categoriza la complejidad actual"""
        if self.complexity_score <= 1.1:
            return "Baja"
        elif self.complexity_score <= 1.3:
            return "Media"
        elif self.complexity_score <= 1.5:
            return "Alta"
        else:
            return "Muy Alta"
    
    def reset_analysis(self):
        """Reinicia el análisis para una nueva historia"""
        self.entities = {
            "characters": set(),
            "locations": set(),
            "plot_threads": [],
            "temporal_markers": set()
        }
        self.complexity_score = 1.0
        self.section_count = 0
        if hasattr(self, '_previous_complexity'):
            delattr(self, '_previous_complexity')
        
        logger.info("Análisis de complejidad reiniciado")