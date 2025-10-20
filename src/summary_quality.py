"""
Evaluador de Calidad de Resúmenes para Optimización Adaptativa.
Evalúa la efectividad de los resúmenes para ajustar la agresividad de compresión.
"""

import re
from typing import Set, Dict, List, Optional, Tuple
from logging_config import get_logger

logger = get_logger("summary_quality")

class SummaryQualityEvaluator:
    """Evalúa calidad de resúmenes para ajustar agresividad"""
    
    def __init__(self):
        self.quality_history: List[float] = []
        self.avg_quality = 0.5  # Neutral inicial
        self.evaluation_count = 0
        
        # Umbrales para evaluación
        self.ideal_compression_range = (0.1, 0.3)  # 10-30% del original
        self.ideal_word_range = (50, 250)          # 50-250 palabras
        self.min_entity_retention = 0.6           # 60% de entidades clave
        
        # Palabras clave que indican calidad narrativa
        self.narrative_indicators = {
            'plot_words': {'después', 'entonces', 'mientras', 'cuando', 'donde', 
                          'porque', 'aunque', 'sin embargo', 'además', 'finalmente'},
            'character_words': {'personaje', 'protagonista', 'héroe', 'heroína', 
                               'villano', 'amigo', 'enemigo', 'aliado'},
            'emotion_words': {'sintió', 'pensó', 'recordó', 'decidió', 'quiso', 
                             'temió', 'esperó', 'amó', 'odió'},
            'action_words': {'descubrió', 'encontró', 'perdió', 'ganó', 'luchó',
                            'escapó', 'rescató', 'salvó', 'destruyó', 'creó'}
        }
    
    def evaluate_summary(self, original_text: str, summary: str, 
                        context_info: Optional[Dict] = None) -> float:
        """
        Evalúa calidad del resumen (0.0 = malo, 1.0 = excelente).
        
        Métricas evaluadas:
        - Ratio de compresión apropiado
        - Retención de entidades clave
        - Longitud apropiada  
        - Coherencia narrativa
        - Presencia de elementos esenciales
        """
        self.evaluation_count += 1
        
        if not summary.strip() or not original_text.strip():
            logger.warning("Texto o resumen vacío en evaluación")
            return 0.0
        
        # 1. Evaluar ratio de compresión
        compression_score = self._evaluate_compression_ratio(original_text, summary)
        
        # 2. Evaluar retención de entidades
        entity_score = self._evaluate_entity_retention(original_text, summary)
        
        # 3. Evaluar longitud apropiada
        length_score = self._evaluate_length(summary)
        
        # 4. Evaluar coherencia narrativa
        narrative_score = self._evaluate_narrative_quality(original_text, summary)
        
        # 5. Evaluar completitud (elementos esenciales)
        completeness_score = self._evaluate_completeness(original_text, summary)
        
        # Score final (promedio ponderado)
        weights = {
            'compression': 0.15,
            'entities': 0.25, 
            'length': 0.15,
            'narrative': 0.25,
            'completeness': 0.20
        }
        
        quality = (
            compression_score * weights['compression'] +
            entity_score * weights['entities'] +
            length_score * weights['length'] + 
            narrative_score * weights['narrative'] +
            completeness_score * weights['completeness']
        )
        
        # Actualizar historial con ventana deslizante
        self.quality_history.append(quality)
        if len(self.quality_history) > 15:  # Mantener últimas 15 evaluaciones
            self.quality_history.pop(0)
        
        # Calcular promedio con más peso a evaluaciones recientes
        weights_recent = [0.5 + (i * 0.1) for i in range(len(self.quality_history))]
        weighted_sum = sum(q * w for q, w in zip(self.quality_history, weights_recent))
        weight_total = sum(weights_recent)
        self.avg_quality = weighted_sum / weight_total if weight_total > 0 else quality
        
        logger.debug(f"Evaluación #{self.evaluation_count}: calidad={quality:.3f}, "
                    f"promedio={self.avg_quality:.3f}")
        
        return quality
    
    def _evaluate_compression_ratio(self, original: str, summary: str) -> float:
        """Evalúa si el ratio de compresión es apropiado"""
        original_len = len(original)
        summary_len = len(summary)
        
        if original_len == 0:
            return 0.0
        
        compression_ratio = summary_len / original_len
        
        # Evaluar contra rango ideal
        min_ratio, max_ratio = self.ideal_compression_range
        
        if min_ratio <= compression_ratio <= max_ratio:
            return 1.0  # Perfecto
        elif compression_ratio < min_ratio:
            # Demasiado comprimido (posible pérdida de información)
            return max(0.3, compression_ratio / min_ratio)
        else:
            # Insuficientemente comprimido
            excess = compression_ratio - max_ratio
            penalty = min(0.7, excess * 2)  # Penalidad progresiva
            return max(0.2, 1.0 - penalty)
    
    def _evaluate_entity_retention(self, original: str, summary: str) -> float:
        """Evalúa retención de entidades clave (nombres, lugares, conceptos)"""
        original_entities = self._extract_entities(original)
        summary_entities = self._extract_entities(summary)
        
        if not original_entities:
            return 1.0  # No hay entidades que retener
        
        # Calcular retención
        retained_entities = summary_entities & original_entities
        retention_rate = len(retained_entities) / len(original_entities)
        
        # Bonificación por retener entidades más importantes (más frecuentes)
        entity_frequencies = self._get_entity_frequencies(original, original_entities)
        important_entities = {e for e, f in entity_frequencies.items() if f > 1}
        
        if important_entities:
            important_retained = retained_entities & important_entities
            important_retention = len(important_retained) / len(important_entities)
            # Promedio ponderado (70% todas las entidades, 30% importantes)
            retention_rate = retention_rate * 0.7 + important_retention * 0.3
        
        # Convertir a score
        if retention_rate >= self.min_entity_retention:
            return min(1.0, retention_rate + 0.2)  # Bonificación por buena retención
        else:
            return retention_rate / self.min_entity_retention * 0.8
    
    def _evaluate_length(self, summary: str) -> float:
        """Evalúa si la longitud del resumen es apropiada"""
        word_count = len(summary.split())
        min_words, max_words = self.ideal_word_range
        
        if min_words <= word_count <= max_words:
            return 1.0
        elif word_count < min_words:
            # Demasiado corto
            return max(0.4, word_count / min_words)
        else:
            # Demasiado largo
            excess = word_count - max_words
            penalty = min(0.6, excess / max_words)
            return max(0.3, 1.0 - penalty)
    
    def _evaluate_narrative_quality(self, original: str, summary: str) -> float:
        """Evalúa mantenimiento de calidad narrativa"""
        # Contar indicadores narrativos en original y resumen
        original_indicators = self._count_narrative_indicators(original)
        summary_indicators = self._count_narrative_indicators(summary)
        
        if not original_indicators:
            return 0.8  # Texto original sin elementos narrativos claros
        
        # Evaluar presencia proporcional de indicadores
        scores = {}
        for category, original_count in original_indicators.items():
            summary_count = summary_indicators.get(category, 0)
            
            if original_count == 0:
                scores[category] = 1.0
            else:
                # Proporción mantenida (ajustada por compresión esperada)
                expected_ratio = 0.2  # Esperamos mantener 20% de indicadores
                actual_ratio = summary_count / original_count
                scores[category] = min(1.0, actual_ratio / expected_ratio)
        
        # Promedio de categorías con peso especial para plot y character
        weights = {'plot_words': 0.3, 'character_words': 0.3, 
                   'emotion_words': 0.2, 'action_words': 0.2}
        
        weighted_score = sum(scores.get(cat, 0.5) * weight 
                           for cat, weight in weights.items())
        
        return weighted_score
    
    def _evaluate_completeness(self, original: str, summary: str) -> float:
        """Evalúa si el resumen captura elementos esenciales"""
        # Identificar elementos esenciales del original
        original_sentences = re.split(r'[.!?]+', original)
        original_sentences = [s.strip() for s in original_sentences if s.strip()]
        
        if len(original_sentences) < 3:
            return 1.0  # Texto demasiado corto para evaluar
        
        # Buscar elementos clave que deberían preservarse
        key_elements = {
            'questions': len(re.findall(r'\?', original)),
            'exclamations': len(re.findall(r'!', original)),  
            'dialogue_markers': len(re.findall(r'["«»""]', original)),
            'temporal_markers': len(re.findall(r'\b(después|entonces|luego|mientras|cuando)\b', 
                                              original, re.IGNORECASE)),
            'causal_markers': len(re.findall(r'\b(porque|debido|ya que|por eso|por tanto)\b', 
                                            original, re.IGNORECASE))
        }
        
        summary_elements = {
            'questions': len(re.findall(r'\?', summary)),
            'exclamations': len(re.findall(r'!', summary)),
            'dialogue_markers': len(re.findall(r'["«»""]', summary)), 
            'temporal_markers': len(re.findall(r'\b(después|entonces|luego|mientras|cuando)\b', 
                                              summary, re.IGNORECASE)),
            'causal_markers': len(re.findall(r'\b(porque|debido|ya que|por eso|por tanto)\b', 
                                            summary, re.IGNORECASE))
        }
        
        # Evaluar preservación proporcional
        element_scores = []
        for element, original_count in key_elements.items():
            if original_count == 0:
                element_scores.append(1.0)
            else:
                summary_count = summary_elements.get(element, 0)
                # Para elementos estructurales, esperamos menor retención
                expected_retention = 0.3 if element in ['questions', 'exclamations'] else 0.15
                actual_retention = summary_count / original_count
                score = min(1.0, actual_retention / expected_retention)
                element_scores.append(score)
        
        return sum(element_scores) / len(element_scores) if element_scores else 0.8
    
    def _extract_entities(self, text: str) -> Set[str]:
        """Extrae entidades (nombres propios) del texto"""
        # Nombres propios (palabras que empiezan con mayúscula)
        words = re.findall(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b', text)
        
        # Filtrar palabras comunes que no son nombres
        common_words = {'El', 'La', 'Los', 'Las', 'En', 'Con', 'Por', 'Pero', 'Sin',
                       'Durante', 'Desde', 'Hasta', 'Cuando', 'Donde', 'Como', 'Muy',
                       'Esta', 'Este', 'Ese', 'Esa', 'Todo', 'Todos', 'Ahora', 'Después'}
        
        entities = {w for w in words if w not in common_words and len(w) > 2}
        return entities
    
    def _get_entity_frequencies(self, text: str, entities: Set[str]) -> Dict[str, int]:
        """Calcula frecuencias de entidades en el texto"""
        frequencies = {}
        text_lower = text.lower()
        
        for entity in entities:
            count = text_lower.count(entity.lower())
            frequencies[entity] = count
            
        return frequencies
    
    def _count_narrative_indicators(self, text: str) -> Dict[str, int]:
        """Cuenta indicadores narrativos por categoría"""
        text_lower = text.lower()
        counts = {}
        
        for category, words in self.narrative_indicators.items():
            count = sum(text_lower.count(word) for word in words)
            counts[category] = count
            
        return counts
    
    def get_aggressiveness_factor(self) -> float:
        """
        Retorna factor de agresividad para resúmenes.
        Calidad alta = más agresivo (más compresión)
        Calidad baja = menos agresivo (más conservador)
        """
        if len(self.quality_history) < 3:
            return 1.0  # Neutral hasta tener suficientes datos
        
        if self.avg_quality >= 0.8:
            return 1.4  # Muy agresivo: resúmenes de alta calidad
        elif self.avg_quality >= 0.65:
            return 1.2  # Moderadamente agresivo
        elif self.avg_quality >= 0.5:
            return 1.0  # Normal
        elif self.avg_quality >= 0.35:
            return 0.8  # Conservador
        else:
            return 0.6  # Muy conservador: resúmenes de baja calidad
    
    def get_quality_report(self) -> Dict[str, any]:
        """Genera reporte detallado de calidad"""
        if not self.quality_history:
            return {"status": "No evaluations performed yet"}
        
        return {
            "evaluations_count": self.evaluation_count,
            "average_quality": self.avg_quality,
            "recent_quality": self.quality_history[-1] if self.quality_history else None,
            "quality_trend": self._calculate_trend(),
            "aggressiveness_factor": self.get_aggressiveness_factor(),
            "quality_category": self._get_quality_category(),
            "recommendations": self._get_recommendations()
        }
    
    def _calculate_trend(self) -> str:
        """Calcula tendencia de calidad reciente"""
        if len(self.quality_history) < 5:
            return "Insufficient data"
        
        recent_5 = self.quality_history[-5:]
        older_5 = self.quality_history[-10:-5] if len(self.quality_history) >= 10 else self.quality_history[:-5]
        
        if not older_5:
            return "Insufficient data"
        
        recent_avg = sum(recent_5) / len(recent_5)
        older_avg = sum(older_5) / len(older_5)
        
        diff = recent_avg - older_avg
        
        if diff > 0.1:
            return "Improving"
        elif diff < -0.1:
            return "Declining"
        else:
            return "Stable"
    
    def _get_quality_category(self) -> str:
        """Categoriza la calidad actual"""
        if self.avg_quality >= 0.8:
            return "Excelente"
        elif self.avg_quality >= 0.65:
            return "Buena"
        elif self.avg_quality >= 0.5:
            return "Aceptable"
        elif self.avg_quality >= 0.35:
            return "Regular"
        else:
            return "Deficiente"
    
    def _get_recommendations(self) -> List[str]:
        """Genera recomendaciones basadas en la calidad"""
        recommendations = []
        
        if self.avg_quality < 0.5:
            recommendations.append("Considerar reducir agresividad de compresión")
            recommendations.append("Verificar retención de entidades clave")
        elif self.avg_quality > 0.8:
            recommendations.append("Calidad excelente, se puede aumentar compresión")
            recommendations.append("Resúmenes muy efectivos")
        
        if len(self.quality_history) >= 5:
            recent_variance = self._calculate_variance(self.quality_history[-5:])
            if recent_variance > 0.1:
                recommendations.append("Alta variabilidad en calidad reciente")
        
        return recommendations
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calcula varianza de una lista de valores"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    def reset_evaluation(self):
        """Reinicia el evaluador para una nueva historia"""
        self.quality_history.clear()
        self.avg_quality = 0.5
        self.evaluation_count = 0
        
        logger.info("Evaluador de calidad reiniciado")