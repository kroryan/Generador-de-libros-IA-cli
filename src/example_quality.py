# src/example_quality.py

import re
from typing import Dict

class ExampleQualityEvaluator:
    """Evalúa calidad de secciones para determinar si son buenos ejemplos"""
    
    @staticmethod
    def evaluate(section_content: str, context: str, idea: str) -> float:
        """
        Evalúa calidad de una sección (0.0-1.0).
        
        Criterios:
        - Longitud apropiada (200-500 palabras)
        - Riqueza léxica (diversidad de vocabulario)
        - Estructura narrativa (inicio-desarrollo-cierre)
        - Coherencia con contexto e idea
        - Ausencia de repeticiones
        """
        scores = []
        
        # 1. Longitud apropiada (peso: 0.15)
        word_count = len(section_content.split())
        if 200 <= word_count <= 500:
            length_score = 1.0
        elif 150 <= word_count < 200 or 500 < word_count <= 600:
            length_score = 0.7
        elif 100 <= word_count < 150 or 600 < word_count <= 800:
            length_score = 0.5
        else:
            length_score = 0.3
        scores.append(length_score * 0.15)
        
        # 2. Riqueza léxica (peso: 0.25)
        words = re.findall(r'\b\w+\b', section_content.lower())
        if words:
            unique_words = set(words)
            lexical_diversity = len(unique_words) / len(words)
            
            if lexical_diversity >= 0.7:
                lexical_score = 1.0
            elif lexical_diversity >= 0.5:
                lexical_score = 0.7
            elif lexical_diversity >= 0.3:
                lexical_score = 0.5
            else:
                lexical_score = 0.3
        else:
            lexical_score = 0.0
        scores.append(lexical_score * 0.25)
        
        # 3. Estructura de párrafos (peso: 0.20)
        paragraphs = [p.strip() for p in section_content.split('\n\n') if p.strip()]
        if 2 <= len(paragraphs) <= 5:
            structure_score = 1.0
        elif len(paragraphs) == 1 or len(paragraphs) == 6:
            structure_score = 0.7
        elif len(paragraphs) > 6:
            structure_score = 0.5
        else:
            structure_score = 0.3
        scores.append(structure_score * 0.20)
        
        # 4. Presencia de elementos narrativos (peso: 0.15)
        narrative_elements = 0
        
        # Diálogos
        if '"' in section_content or '—' in section_content or '\"' in section_content:
            narrative_elements += 1
        
        # Descripciones sensoriales (palabras que indican los 5 sentidos)
        sensory_words = ['vio', 'miró', 'observó', 'escuchó', 'oyó', 'sintió', 'tocó', 
                        'olió', 'sabor', 'áspero', 'suave', 'frío', 'caliente', 'brillante']
        if any(word in section_content.lower() for word in sensory_words):
            narrative_elements += 1
        
        # Emociones y estados internos
        emotion_words = ['sintió', 'pensó', 'recordó', 'emoción', 'miedo', 'alegría', 
                        'tristeza', 'ira', 'sorpresa', 'corazón', 'alma']
        if any(word in section_content.lower() for word in emotion_words):
            narrative_elements += 1
        
        narrative_score = min(1.0, narrative_elements / 2.0)  # Máximo 2 elementos
        scores.append(narrative_score * 0.15)
        
        # 5. Ausencia de repeticiones (peso: 0.25)
        sentences = re.split(r'[.!?]+', section_content)
        sentence_starts = [s.strip()[:20] for s in sentences if len(s.strip()) > 20]
        if sentence_starts:
            unique_starts = len(set(sentence_starts))
            repetition_score = unique_starts / len(sentence_starts)
        else:
            repetition_score = 0.5
        scores.append(repetition_score * 0.25)
        
        final_score = sum(scores)
        return min(1.0, max(0.0, final_score))  # Asegurar que esté entre 0.0 y 1.0
    
    @staticmethod
    def get_quality_breakdown(section_content: str, context: str, idea: str) -> Dict[str, float]:
        """
        Retorna un desglose detallado de los criterios de calidad.
        Útil para debugging y análisis.
        """
        breakdown = {}
        
        # Longitud
        word_count = len(section_content.split())
        breakdown['word_count'] = word_count
        if 200 <= word_count <= 500:
            breakdown['length_score'] = 1.0
        elif 150 <= word_count < 200 or 500 < word_count <= 600:
            breakdown['length_score'] = 0.7
        else:
            breakdown['length_score'] = 0.3
        
        # Riqueza léxica
        words = re.findall(r'\b\w+\b', section_content.lower())
        if words:
            unique_words = set(words)
            lexical_diversity = len(unique_words) / len(words)
            breakdown['lexical_diversity'] = lexical_diversity
            breakdown['unique_words'] = len(unique_words)
            breakdown['total_words'] = len(words)
        else:
            breakdown['lexical_diversity'] = 0.0
        
        # Estructura
        paragraphs = [p.strip() for p in section_content.split('\n\n') if p.strip()]
        breakdown['paragraph_count'] = len(paragraphs)
        
        # Elementos narrativos
        has_dialogue = '"' in section_content or '—' in section_content or '\"' in section_content
        breakdown['has_dialogue'] = has_dialogue
        
        # Score final
        breakdown['final_score'] = ExampleQualityEvaluator.evaluate(section_content, context, idea)
        
        return breakdown