"""
Sistema Adaptativo de Extracción de Segmentos de Texto.

Este módulo proporciona un sistema inteligente para extraer segmentos clave
de textos largos, reemplazando la lógica hardcoded con estrategias configurables.

Características:
- Estrategias configurables (inicio/fin, uniforme, adaptativo)
- Ajuste automático del tamaño de segmento según longitud del texto
- Detección de límites naturales (párrafos, oraciones)
- Configuración por variables de entorno
- Soporte para diferentes tipos de contenido
"""

from enum import Enum, auto
from typing import List, Optional, Tuple
from dataclasses import dataclass
import re
import os


class ExtractionStrategy(Enum):
    """Estrategias de extracción de segmentos."""
    START_END = auto()        # Solo inicio y final (rápido, limitado)
    UNIFORM = auto()          # Distribución uniforme (equilibrado)
    ADAPTIVE = auto()         # Adaptativo según contenido (inteligente)
    FULL = auto()            # Texto completo (sin extracción)


@dataclass
class SegmentConfig:
    """Configuración de extracción de segmentos."""
    strategy: ExtractionStrategy = ExtractionStrategy.ADAPTIVE
    max_segments: int = 3
    base_segment_length: int = 1000
    adaptive_scaling: bool = True
    respect_boundaries: bool = True  # Respetar límites de párrafos/oraciones
    min_segment_length: int = 500
    max_segment_length: int = 2000
    
    @classmethod
    def from_env(cls) -> 'SegmentConfig':
        """Crea configuración desde variables de entorno."""
        strategy_str = os.environ.get('SEGMENT_EXTRACTION_STRATEGY', 'adaptive').upper()
        strategy_map = {
            'START_END': ExtractionStrategy.START_END,
            'UNIFORM': ExtractionStrategy.UNIFORM,
            'ADAPTIVE': ExtractionStrategy.ADAPTIVE,
            'FULL': ExtractionStrategy.FULL
        }
        strategy = strategy_map.get(strategy_str, ExtractionStrategy.ADAPTIVE)
        
        max_segments = int(os.environ.get('SEGMENT_MAX_COUNT', '3'))
        base_length = int(os.environ.get('SEGMENT_BASE_LENGTH', '1000'))
        adaptive = os.environ.get('SEGMENT_ADAPTIVE_SCALING', 'true').lower() in ['true', '1', 'yes']
        respect_boundaries = os.environ.get('SEGMENT_RESPECT_BOUNDARIES', 'true').lower() in ['true', '1', 'yes']
        
        min_length = int(os.environ.get('SEGMENT_MIN_LENGTH', '500'))
        max_length = int(os.environ.get('SEGMENT_MAX_LENGTH', '2000'))
        
        return cls(
            strategy=strategy,
            max_segments=max_segments,
            base_segment_length=base_length,
            adaptive_scaling=adaptive,
            respect_boundaries=respect_boundaries,
            min_segment_length=min_length,
            max_segment_length=max_length
        )


class TextSegmentExtractor:
    """
    Extrae segmentos clave de textos largos usando estrategias configurables.
    
    Reemplaza la lógica hardcoded de extract_key_segments() con un sistema
    más flexible y adaptativo.
    """
    
    def __init__(self, config: Optional[SegmentConfig] = None):
        """
        Inicializa el extractor.
        
        Args:
            config: Configuración de extracción, por defecto desde env
        """
        self.config = config or SegmentConfig.from_env()
        
        # Patrones para detectar límites naturales
        self.paragraph_pattern = re.compile(r'\n\s*\n')
        self.sentence_pattern = re.compile(r'[.!?]+[\s\n]+')
    
    def extract(
        self,
        text: str,
        max_segments: Optional[int] = None,
        segment_length: Optional[int] = None
    ) -> str:
        """
        Extrae segmentos clave del texto.
        
        Args:
            text: Texto completo a procesar
            max_segments: Número máximo de segmentos (override de config)
            segment_length: Longitud base de segmento (override de config)
            
        Returns:
            Texto con segmentos extraídos y separadores
        """
        # Usar valores de config si no se especifican
        max_seg = max_segments or self.config.max_segments
        seg_len = segment_length or self.config.base_segment_length
        
        # Ajustar tamaño de segmento si adaptive_scaling está activo
        if self.config.adaptive_scaling:
            seg_len = self._calculate_adaptive_length(text, seg_len, max_seg)
        
        # Verificar si el texto es lo suficientemente corto
        if len(text) <= seg_len * max_seg:
            return text
        
        # Ejecutar estrategia correspondiente
        if self.config.strategy == ExtractionStrategy.FULL:
            return text
        elif self.config.strategy == ExtractionStrategy.START_END:
            return self._extract_start_end(text, seg_len)
        elif self.config.strategy == ExtractionStrategy.UNIFORM:
            return self._extract_uniform(text, seg_len, max_seg)
        elif self.config.strategy == ExtractionStrategy.ADAPTIVE:
            return self._extract_adaptive(text, seg_len, max_seg)
        else:
            # Fallback a uniform
            return self._extract_uniform(text, seg_len, max_seg)
    
    def _calculate_adaptive_length(
        self,
        text: str,
        base_length: int,
        max_segments: int
    ) -> int:
        """
        Calcula longitud adaptativa de segmento basada en la longitud del texto.
        
        Para textos muy largos, aumenta el tamaño de segmento para capturar más contexto.
        Para textos cortos, reduce el tamaño para evitar redundancia.
        """
        text_len = len(text)
        
        # Calcular factor de escala
        # Textos > 50k caracteres: segmentos más grandes
        # Textos < 10k caracteres: segmentos más pequeños
        if text_len > 50000:
            scale_factor = 1.5
        elif text_len > 20000:
            scale_factor = 1.2
        elif text_len < 5000:
            scale_factor = 0.7
        elif text_len < 10000:
            scale_factor = 0.85
        else:
            scale_factor = 1.0
        
        adaptive_length = int(base_length * scale_factor)
        
        # Aplicar límites
        adaptive_length = max(self.config.min_segment_length, adaptive_length)
        adaptive_length = min(self.config.max_segment_length, adaptive_length)
        
        return adaptive_length
    
    def _find_boundary(
        self,
        text: str,
        target_pos: int,
        direction: int = 1
    ) -> int:
        """
        Encuentra el límite natural más cercano (párrafo o oración).
        
        Args:
            text: Texto completo
            target_pos: Posición objetivo
            direction: 1 para buscar adelante, -1 para buscar atrás
            
        Returns:
            Posición del límite natural más cercano
        """
        if not self.config.respect_boundaries:
            return target_pos
        
        # Buscar el límite de párrafo más cercano
        search_range = 200  # Buscar en un rango de 200 caracteres
        
        if direction > 0:
            search_start = target_pos
            search_end = min(target_pos + search_range, len(text))
            search_text = text[search_start:search_end]
        else:
            search_start = max(target_pos - search_range, 0)
            search_end = target_pos
            search_text = text[search_start:search_end]
        
        # Buscar párrafo
        paragraph_matches = list(self.paragraph_pattern.finditer(search_text))
        if paragraph_matches:
            match = paragraph_matches[0] if direction > 0 else paragraph_matches[-1]
            return search_start + match.end()
        
        # Si no hay párrafo, buscar oración
        sentence_matches = list(self.sentence_pattern.finditer(search_text))
        if sentence_matches:
            match = sentence_matches[0] if direction > 0 else sentence_matches[-1]
            return search_start + match.end()
        
        # Si no hay límite natural, usar posición original
        return target_pos
    
    def _extract_start_end(self, text: str, segment_length: int) -> str:
        """Estrategia START_END: solo inicio y final."""
        start_end = self._find_boundary(text, segment_length, direction=1)
        end_start = self._find_boundary(text, len(text) - segment_length, direction=-1)
        
        start_segment = text[:start_end]
        end_segment = text[end_start:]
        
        result = f"INICIO DEL CAPÍTULO:\n{start_segment}"
        result += f"\n\n[...CONTENIDO OMITIDO...]\n\n"
        result += f"FINAL DEL CAPÍTULO:\n{end_segment}"
        
        return result
    
    def _extract_uniform(
        self,
        text: str,
        segment_length: int,
        max_segments: int
    ) -> str:
        """Estrategia UNIFORM: distribución uniforme a lo largo del texto."""
        text_len = len(text)
        segments = []
        labels = []
        
        # Calcular posiciones uniformemente distribuidas
        if max_segments == 2:
            positions = [0, text_len - segment_length]
            labels = ["INICIO DEL CAPÍTULO", "FINAL DEL CAPÍTULO"]
        else:
            # Distribuir uniformemente
            step = (text_len - segment_length) // (max_segments - 1)
            positions = [i * step for i in range(max_segments)]
            
            labels.append("INICIO DEL CAPÍTULO")
            for i in range(1, max_segments - 1):
                labels.append(f"PARTE {i} DEL CAPÍTULO")
            labels.append("FINAL DEL CAPÍTULO")
        
        # Extraer segmentos en posiciones calculadas
        for pos in positions:
            end_pos = self._find_boundary(text, pos + segment_length, direction=1)
            start_pos = self._find_boundary(text, pos, direction=1)
            segments.append(text[start_pos:end_pos])
        
        # Ensamblar resultado
        result = f"{labels[0]}:\n{segments[0]}"
        for i in range(1, len(segments)):
            result += f"\n\n[...PARTE OMITIDA...]\n\n{labels[i]}:\n{segments[i]}"
        
        return result
    
    def _extract_adaptive(
        self,
        text: str,
        segment_length: int,
        max_segments: int
    ) -> str:
        """
        Estrategia ADAPTIVE: ajusta posiciones basándose en estructura del texto.
        
        Intenta capturar:
        - Inicio (establecimiento de escena)
        - Puntos de inflexión (detectados por cambios de párrafo)
        - Final (resolución)
        """
        text_len = len(text)
        segments = []
        labels = []
        
        # Siempre incluir inicio
        start_end = self._find_boundary(text, segment_length, direction=1)
        segments.append(text[:start_end])
        labels.append("INICIO DEL CAPÍTULO")
        
        # Calcular cuántos segmentos intermedios se pueden extraer
        middle_segments = max_segments - 2  # Restar inicio y final
        
        if middle_segments > 0:
            # Encontrar puntos de inflexión (cambios de párrafo significativos)
            paragraphs = self.paragraph_pattern.split(text)
            
            # Seleccionar párrafos clave del medio
            middle_start = len(paragraphs) // 3
            middle_end = 2 * len(paragraphs) // 3
            key_paragraphs = paragraphs[middle_start:middle_end]
            
            # Extraer segmento del medio
            middle_text = '\n\n'.join(key_paragraphs)
            if len(middle_text) > segment_length:
                # Tomar una muestra del medio
                mid_point = len(middle_text) // 2
                mid_start = max(0, mid_point - segment_length // 2)
                mid_end = min(len(middle_text), mid_start + segment_length)
                mid_start = self._find_boundary(middle_text, mid_start, direction=1)
                mid_end = self._find_boundary(middle_text, mid_end, direction=-1)
                segments.append(middle_text[mid_start:mid_end])
            else:
                segments.append(middle_text)
            
            labels.append("PARTE MEDIA DEL CAPÍTULO")
        
        # Siempre incluir final
        end_start = self._find_boundary(text, text_len - segment_length, direction=-1)
        segments.append(text[end_start:])
        labels.append("FINAL DEL CAPÍTULO")
        
        # Ensamblar resultado
        result = f"{labels[0]}:\n{segments[0]}"
        for i in range(1, len(segments)):
            result += f"\n\n[...CONTENIDO OMITIDO...]\n\n{labels[i]}:\n{segments[i]}"
        
        return result


# Función de compatibilidad para reemplazar código existente
def extract_key_segments(
    text: str,
    max_segments: int = 3,
    segment_length: int = 1000
) -> str:
    """
    Función helper para compatibilidad con código existente.
    
    Reemplaza la implementación hardcoded con el sistema adaptativo.
    
    Args:
        text: Texto completo
        max_segments: Número máximo de segmentos
        segment_length: Longitud base de segmento
        
    Returns:
        Texto con segmentos extraídos
    """
    extractor = TextSegmentExtractor()
    return extractor.extract(text, max_segments, segment_length)
