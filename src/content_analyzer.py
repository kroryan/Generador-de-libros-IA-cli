import re
from collections import Counter

class ContentAnalyzer:
    """
    Sistema avanzado para analizar texto generado, detectar patrones de colapso
    y proporcionar diagnósticos detallados sobre problemas de coherencia.
    """
    
    def __init__(self):
        # Patrones de colapso conocidos
        self.collapse_patterns = [
            # Repetición de formatos de capítulo/sección
            r'(\*\*[^*\n]{1,30})\1{2,}',               # Repetición de texto con asteriscos
            r'(Capítulo\s*\d*\s*:?)\s*\1{1,}',         # Repetición de "Capítulo"
            r'(CAPÍTULO\s*\d*\s*:?)\s*\1{1,}',         # Repetición de "CAPÍTULO"
            r'(Parte\s*\d*\s*:?)\s*\1{1,}',            # Repetición de "Parte"
            r'([^\n]{10,30})\1{3,}',                  # Repetición de cualquier fragmento
            
            # Patrones indicativos de confusión del modelo
            r'(Continuación|Continúa|Continuando).*\1.*\1',  # Repetición de "Continuación"
            r'\.\.\..*\.\.\..*\.\.\..*\.\.\.',        # Exceso de puntos suspensivos
            r'\n\s*\n\s*\n\s*\n\s*\n',                # Exceso de líneas vacías 
        ]
        
        # Indicadores de calidad narrativa
        self.narrative_indicators = {
            "dialogue_pattern": r'"[^"]+"|\'[^\']+\'|--[^--]+--',  # Patrones de diálogo (con guiones normales)
            "description_pattern": r'[^.!?]{40,}[.!?]',     # Descripciones largas
            "action_pattern": r'\b(corrió|saltó|golpeó|movió|miró|observó|caminó|tocó|agarró)\b'  # Verbos de acción
        }
        
        # Historial para comparación
        self.history = []
        self.collapse_count = 0
        self.warnings_history = []
    
    def detect_collapse_risk(self, text, strict_mode=False):
        """
        Analiza un texto para detectar señales de colapso del modelo.
        Implementa múltiples criterios para una detección más precisa.
        
        Args:
            text: Texto generado a analizar
            strict_mode: Si activado, aplica criterios más estrictos
            
        Returns:
            tuple: (bool indicando colapso, str con detalles, dict con análisis)
        """
        if not text or len(text.strip()) < 20:
            return False, "Texto demasiado corto para analizar", {}
            
        # Análisis detallado
        analysis = self._analyze_text(text)
        
        # Limpiar texto para análisis
        clean_text = self._normalize_text(text)
        
        # 1. Verificar patrones explícitos de colapso
        for pattern in self.collapse_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                detail = f"Patrón de repetición detectado: '{match.group(1)[:20]}...'"
                self.collapse_count += 1
                self.warnings_history.append(detail)
                return True, detail, analysis
        
        # 2. Verificar longitud anormalmente corta con metadata
        if len(clean_text.strip()) < 50 and any(term in clean_text.lower() for term in ["capítulo", "continuación", "parte"]):
            detail = f"Respuesta truncada ({len(clean_text)} caracteres) con metadata"
            self.collapse_count += 1
            self.warnings_history.append(detail)
            return True, detail, analysis
            
        # 3. Detectar repeticiones excesivas de palabras
        word_counts = Counter(re.findall(r'\b\w+\b', clean_text.lower()))
        most_common = word_counts.most_common(5)
        # Si la palabra más común (excepto stopwords) aparece con frecuencia anormal
        for word, count in most_common:
            if (len(word) > 3 and 
                word not in ["para", "como", "esto", "esta", "pero", "cuando", "donde"] and
                count > 7 and 
                count / len(clean_text.split()) > 0.1):  # >10% del total de palabras
                
                detail = f"Repetición excesiva de palabra '{word}' ({count} veces)"
                self.collapse_count += 1
                self.warnings_history.append(detail)
                return True, detail, analysis
        
        # 4. Verificar coherencia narrativa
        has_dialogue = bool(re.search(self.narrative_indicators["dialogue_pattern"], clean_text))
        has_description = bool(re.search(self.narrative_indicators["description_pattern"], clean_text))
        has_action = bool(re.search(self.narrative_indicators["action_pattern"], clean_text))
        
        # En modo estricto, verificar si falta estructura narrativa básica
        if strict_mode and not (has_dialogue or has_description or has_action):
            detail = "Falta estructura narrativa (diálogo, descripción o acción)"
            self.warnings_history.append(detail)
            return True, detail, analysis
        
        # 5. En modo estricto, verificar similitud con texto anterior (repetición)
        if strict_mode and len(self.history) > 0:
            last_text = self.history[-1]
            similarity = self._calculate_text_similarity(clean_text, last_text)
            if similarity > 0.7:  # Más del 70% similar al texto anterior
                detail = f"Alta similitud ({similarity:.1%}) con texto anterior"
                self.warnings_history.append(detail)
                return True, detail, analysis
        
        # Agregar a historial
        self.history.append(clean_text)
        if len(self.history) > 5:  # Mantener solo los 5 textos más recientes
            self.history.pop(0)
            
        # Si llegamos aquí, no hay riesgo de colapso detectado
        return False, "Sin riesgo detectado", analysis
    
    def _normalize_text(self, text):
        """Normaliza el texto para análisis, eliminando espacios extra y caracteres especiales"""
        # Eliminar espacios en blanco extra
        normalized = re.sub(r'\s+', ' ', text)
        # Normalizar saltos de línea
        normalized = re.sub(r'\n+', '\n', normalized)
        return normalized
    
    def _analyze_text(self, text):
        """
        Realiza un análisis detallado del texto para extraer métricas y características.
        
        Returns:
            dict: Análisis detallado con varias métricas
        """
        # Limpieza básica
        clean_text = self._normalize_text(text)
        words = re.findall(r'\b\w+\b', clean_text.lower())
        
        # Contar frecuencias
        word_count = len(words)
        char_count = len(clean_text)
        sentence_count = len(re.split(r'[.!?]+', clean_text))
        paragraph_count = len([p for p in re.split(r'\n+', clean_text) if p.strip()])
        
        # Conteo de diálogos
        dialogue_count = len(re.findall(r'"[^"]+"', clean_text)) + len(re.findall(r"'[^']+'", clean_text))
        
        # Análisis de complejidad
        avg_word_length = sum(len(word) for word in words) / max(1, word_count)
        avg_sentence_length = word_count / max(1, sentence_count)
        
        # Análisis de diversidad léxica
        unique_words = len(set(words))
        lexical_diversity = unique_words / max(1, word_count)
        
        # Análisis de sentimiento (simplificado)
        positive_words = ['feliz', 'alegre', 'bueno', 'excelente', 'sonrisa', 'amor', 'satisfecho']
        negative_words = ['triste', 'enojado', 'malo', 'terrible', 'horror', 'miedo', 'odio']
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        sentiment_score = (positive_count - negative_count) / max(1, word_count)
        
        # Detectar posibles problemas 
        potential_issues = []
        
        if lexical_diversity < 0.4:
            potential_issues.append("Baja diversidad léxica")
            
        if avg_sentence_length > 30:
            potential_issues.append("Oraciones demasiado largas")
            
        if avg_sentence_length < 5 and sentence_count > 3:
            potential_issues.append("Oraciones demasiado cortas")
            
        if dialogue_count == 0 and word_count > 100:
            potential_issues.append("Sin diálogo en un texto largo")
        
        return {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "dialogue_count": dialogue_count,
            "avg_word_length": avg_word_length,
            "avg_sentence_length": avg_sentence_length,
            "lexical_diversity": lexical_diversity,
            "sentiment_score": sentiment_score,
            "potential_issues": potential_issues
        }
    
    def _calculate_text_similarity(self, text1, text2):
        """
        Calcula la similitud entre dos textos usando una versión simplificada
        de la similitud de Jaccard basada en n-gramas.
        
        Returns:
            float: Valor entre 0 y 1, donde 1 es máxima similitud
        """
        # Extraer n-gramas (secuencias de n palabras)
        def get_ngrams(text, n=3):
            words = re.findall(r'\b\w+\b', text.lower())
            return set(' '.join(words[i:i+n]) for i in range(len(words)-n+1))
        
        # Calcular similitud de Jaccard
        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)
        
        if not ngrams1 or not ngrams2:
            return 0.0
            
        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))
        
        return intersection / union if union > 0 else 0.0
    
    def get_collapse_stats(self):
        """Obtiene estadísticas sobre colapsos detectados"""
        return {
            "total_collapses": self.collapse_count,
            "recent_warnings": self.warnings_history[-5:] if self.warnings_history else [],
            "avg_text_length": sum(len(text) for text in self.history) / max(1, len(self.history))
        }
    
    def reset_history(self):
        """Reinicia el historial de análisis"""
        self.history = []
        self.warnings_history = []