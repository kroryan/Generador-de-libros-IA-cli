"""
Sistema Unificado de Limpieza de Texto para el Generador de Libros IA.

Este módulo consolida todos los sistemas de limpieza de texto dispersos en el código:
- clean_think_tags() de utils.py
- clean_content() de publishing.py  
- clean_ansi_codes() de server.py
- Lógica de limpieza en OutputCapture

Proporciona un sistema configurable y extensible para limpiar texto en diferentes etapas
del pipeline de generación.
"""

from enum import Enum
from typing import List, Dict, Optional, Callable, Pattern
import re
import os


class CleaningStage(Enum):
    """Etapas de limpieza de texto en orden de aplicación."""
    ANSI_CODES = "ansi_codes"           # Códigos de escape ANSI del terminal
    THINK_TAGS = "think_tags"           # Tags de pensamiento del modelo (<think>, etc.)
    METADATA = "metadata"               # Metadatos y notas de desarrollo
    NARRATIVE_MARKERS = "narrative_markers"  # Marcadores no narrativos
    WHITESPACE = "whitespace"           # Espacios y líneas extras


class CleaningPattern:
    """Representa un patrón de limpieza con su configuración."""
    
    def __init__(
        self,
        name: str,
        pattern: str,
        replacement: str = "",
        stage: CleaningStage = CleaningStage.METADATA,
        priority: int = 5,
        flags: int = re.DOTALL | re.IGNORECASE,
        is_regex: bool = True
    ):
        self.name = name
        self.pattern_str = pattern
        self.replacement = replacement
        self.stage = stage
        self.priority = priority
        self.flags = flags
        self.is_regex = is_regex
        
        # Compilar patrón regex si corresponde
        if is_regex:
            self.compiled_pattern = re.compile(pattern, flags)
        else:
            self.compiled_pattern = None
    
    def apply(self, text: str) -> str:
        """Aplica el patrón de limpieza al texto."""
        if not text:
            return text
            
        if self.is_regex and self.compiled_pattern:
            return self.compiled_pattern.sub(self.replacement, text)
        else:
            # Limpieza simple de strings
            return text.replace(self.pattern_str, self.replacement)


class TextCleaner:
    """
    Sistema unificado de limpieza de texto con soporte para múltiples etapas
    y patrones configurables.
    """
    
    def __init__(self, enabled_stages: Optional[List[CleaningStage]] = None):
        """
        Inicializa el limpiador de texto.
        
        Args:
            enabled_stages: Lista de etapas habilitadas. Si es None, todas están habilitadas.
        """
        self.patterns: Dict[CleaningStage, List[CleaningPattern]] = {
            stage: [] for stage in CleaningStage
        }
        
        # Habilitar todas las etapas por defecto
        self.enabled_stages = set(enabled_stages) if enabled_stages else set(CleaningStage)
        
        # Registrar patrones por defecto
        self._register_default_patterns()
    
    def _register_default_patterns(self):
        """Registra todos los patrones de limpieza por defecto del sistema."""
        
        # ===== ANSI CODES =====
        # De clean_ansi_codes() en server.py
        self.register_pattern(CleaningPattern(
            name="ansi_escape_complex",
            pattern=r'\x1B\[[0-?]*[ -/]*[@-~]',
            stage=CleaningStage.ANSI_CODES,
            priority=1,
            flags=0
        ))
        
        self.register_pattern(CleaningPattern(
            name="ansi_escape_simple",
            pattern=r'\[\d+m',
            stage=CleaningStage.ANSI_CODES,
            priority=2,
            flags=0
        ))
        
        # ===== THINK TAGS =====
        # De clean_think_tags() en utils.py
        think_patterns = [
            (r'<think>.*?</think>\s*', 1),
            (r'<razonamiento>.*?</razonamiento>\s*', 1),
            (r'<reasoning>.*?</reasoning>\s*', 1),
            (r'\[pensamiento:.*?\]\s*', 2),
            (r'\[think:.*?\]\s*', 2),
            (r'\(pensando:.*?\)\s*', 3),
            (r'\(thinking:.*?\)\s*', 3),
        ]
        
        for pattern, priority in think_patterns:
            self.register_pattern(CleaningPattern(
                name=f"think_tag_{priority}",
                pattern=pattern,
                stage=CleaningStage.THINK_TAGS,
                priority=priority
            ))
        
        # ===== METADATA =====
        # De clean_content() en publishing.py - Etiquetas y notas
        metadata_patterns = [
            (r'<.*?>', "html_tags"),
            (r'\[Nota:.*?\]', "notas"),
            (r'\[Desarrollo:.*?\]', "desarrollo"),
            (r'\[Contexto:.*?\]', "contexto"),
            (r'\[Idea:.*?\]', "ideas"),
            (r'\[Continuación:.*?\]', "continuacion"),
            (r'\[Marco:.*?\]', "marco"),
            (r'\[Resumen:.*?\]', "resumen_tags"),
            (r'Resumen:.*?\n', "resumen_lines"),
            (r'RESUMEN.*?\n', "resumen_caps"),
            (r'\n-{3,}\n.*?\n-{3,}\n', "bloques_guiones"),
            (r'\[\.\.\.\]', "indicadores_omitidos"),
        ]
        
        for pattern, name in metadata_patterns:
            self.register_pattern(CleaningPattern(
                name=name,
                pattern=pattern,
                stage=CleaningStage.METADATA,
                priority=5
            ))
        
        # ===== NARRATIVE MARKERS =====
        # Marcadores de estructura que no son narrativa
        narrative_marker_patterns = [
            (r'Capítulo \d+:.*?(?=\n\n)', "chapter_markers_1"),
            (r'CAPÍTULO \d+:.*?(?=\n\n)', "chapter_markers_2"),
            (r'INICIO DEL CAPÍTULO:', "chapter_start"),
            (r'\[\.\.\.PARTE MEDIA DEL CAPÍTULO\.\.\.\]', "chapter_middle"),
            (r'\[\.\.\.FINAL DEL CAPÍTULO\.\.\.\]', "chapter_end"),
            (r'Progreso actual:.*?\n', "progress_indicator"),
            (r'Elementos clave:.*?\n', "key_elements"),
            (r'### .*? ###', "markdown_headers"),
            (r'\*\*\*.*?\*\*\*', "asterisk_blocks"),
            (r'--\s?Fin del capítulo\s?--', "end_markers"),
            (r'--\s?Continuará\s?--', "continuation_markers"),
        ]
        
        for pattern, name in narrative_marker_patterns:
            self.register_pattern(CleaningPattern(
                name=name,
                pattern=pattern,
                stage=CleaningStage.NARRATIVE_MARKERS,
                priority=5
            ))
    
    def register_pattern(self, pattern: CleaningPattern):
        """Registra un nuevo patrón de limpieza."""
        self.patterns[pattern.stage].append(pattern)
        # Ordenar por prioridad (menor número = mayor prioridad)
        self.patterns[pattern.stage].sort(key=lambda p: p.priority)
    
    def clean(
        self,
        text: str,
        stages: Optional[List[CleaningStage]] = None,
        aggressive: bool = False
    ) -> str:
        """
        Limpia el texto aplicando las etapas especificadas.
        
        Args:
            text: Texto a limpiar
            stages: Lista de etapas a aplicar. Si es None, aplica todas las habilitadas.
            aggressive: Si es True, aplica limpieza adicional de whitespace
            
        Returns:
            Texto limpio
        """
        if not text:
            return text
        
        # Determinar qué etapas aplicar
        if stages is None:
            stages_to_apply = [s for s in CleaningStage if s in self.enabled_stages]
        else:
            stages_to_apply = [s for s in stages if s in self.enabled_stages]
        
        result = text
        
        # Aplicar cada etapa en orden
        for stage in stages_to_apply:
            result = self.clean_stage(result, stage)
        
        # Limpieza de whitespace siempre al final si está habilitada
        if CleaningStage.WHITESPACE in self.enabled_stages:
            result = self._clean_whitespace(result, aggressive)
        
        return result
    
    def clean_stage(self, text: str, stage: CleaningStage) -> str:
        """
        Aplica todos los patrones de una etapa específica.
        
        Args:
            text: Texto a limpiar
            stage: Etapa de limpieza a aplicar
            
        Returns:
            Texto limpio
        """
        if not text or stage not in self.patterns:
            return text
        
        result = text
        
        # Aplicar cada patrón de la etapa en orden de prioridad
        for pattern in self.patterns[stage]:
            result = pattern.apply(result)
        
        return result
    
    def _clean_whitespace(self, text: str, aggressive: bool = False) -> str:
        """
        Limpia espacios en blanco y líneas vacías.
        
        Args:
            text: Texto a limpiar
            aggressive: Si es True, aplica limpieza más agresiva
            
        Returns:
            Texto limpio
        """
        if not text:
            return text
        
        result = text
        
        # Eliminar líneas que solo contienen números o símbolos
        if aggressive:
            result = re.sub(r'^\s*[\d\W]+\s*$', '', result, flags=re.MULTILINE)
        
        # Eliminar múltiples saltos de línea (más de 2)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # Eliminar múltiples espacios
        result = re.sub(r' {2,}', ' ', result)
        
        # Eliminar espacios al inicio y final
        result = result.strip()
        
        return result
    
    def clean_lines_starting_with(self, text: str, prefixes: List[str]) -> str:
        """
        Elimina líneas que comienzan con ciertos prefijos.
        Usado en publishing.py para eliminar líneas no narrativas.
        
        Args:
            text: Texto a limpiar
            prefixes: Lista de prefijos a eliminar
            
        Returns:
            Texto sin las líneas que comienzan con los prefijos
        """
        if not text or not prefixes:
            return text
        
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not any(stripped.startswith(prefix) for prefix in prefixes):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def get_patterns_for_stage(self, stage: CleaningStage) -> List[CleaningPattern]:
        """Obtiene todos los patrones registrados para una etapa."""
        return self.patterns.get(stage, [])
    
    def enable_stage(self, stage: CleaningStage):
        """Habilita una etapa de limpieza."""
        self.enabled_stages.add(stage)
    
    def disable_stage(self, stage: CleaningStage):
        """Deshabilita una etapa de limpieza."""
        self.enabled_stages.discard(stage)
    
    def is_stage_enabled(self, stage: CleaningStage) -> bool:
        """Verifica si una etapa está habilitada."""
        return stage in self.enabled_stages


# ===== FUNCIONES DE COMPATIBILIDAD =====
# Estas funciones mantienen compatibilidad con el código existente

# Instancia global del limpiador
_global_cleaner = TextCleaner()


def clean_think_tags(text: str) -> str:
    """
    Función de compatibilidad para clean_think_tags() de utils.py.
    Limpia tags de pensamiento del texto.
    """
    return _global_cleaner.clean_stage(text, CleaningStage.THINK_TAGS)


def clean_ansi_codes(text: str) -> str:
    """
    Función de compatibilidad para clean_ansi_codes() de server.py.
    Limpia códigos de escape ANSI del texto.
    """
    return _global_cleaner.clean_stage(text, CleaningStage.ANSI_CODES)


def clean_content(text: str, aggressive: bool = True) -> str:
    """
    Función de compatibilidad para clean_content() de publishing.py.
    Limpia todo el contenido no narrativo del texto.
    """
    # Aplicar todas las etapas excepto ANSI_CODES (no debería haber en documentos)
    stages = [
        CleaningStage.THINK_TAGS,
        CleaningStage.METADATA,
        CleaningStage.NARRATIVE_MARKERS,
    ]
    
    result = _global_cleaner.clean(text, stages, aggressive=aggressive)
    
    # Aplicar limpieza de líneas con prefijos no narrativos
    non_narrative_prefixes = [
        "Nota:", "Resumen:", "Contexto:", "RESUMEN", "CONTEXTO",
        "IMPORTANTE:", "IDEA:", "PROGRESO:", "CAPÍTULO ANTERIOR:",
        "MARCO NARRATIVO:"
    ]
    
    result = _global_cleaner.clean_lines_starting_with(result, non_narrative_prefixes)
    
    return result


def clean_all(text: str, aggressive: bool = False) -> str:
    """
    Limpia el texto aplicando todas las etapas de limpieza.
    
    Args:
        text: Texto a limpiar
        aggressive: Si es True, aplica limpieza más agresiva de whitespace
        
    Returns:
        Texto limpio
    """
    return _global_cleaner.clean(text, aggressive=aggressive)


def get_global_cleaner() -> TextCleaner:
    """Obtiene la instancia global del limpiador de texto."""
    return _global_cleaner


# ===== CONFIGURACIÓN DESDE VARIABLES DE ENTORNO =====

def configure_from_env():
    """
    Configura el limpiador global desde variables de entorno.
    
    Variables de entorno soportadas:
    - TEXT_CLEANING_ENABLED_STAGES: Lista separada por comas de etapas habilitadas
    - TEXT_CLEANING_AGGRESSIVE_MODE: true/false para modo agresivo
    """
    # Configurar etapas habilitadas
    enabled_stages_env = os.environ.get('TEXT_CLEANING_ENABLED_STAGES', '')
    if enabled_stages_env:
        stage_names = [s.strip().lower() for s in enabled_stages_env.split(',')]
        enabled_stages = []
        
        for name in stage_names:
            try:
                stage = CleaningStage(name)
                enabled_stages.append(stage)
            except ValueError:
                pass  # Ignorar nombres inválidos
        
        if enabled_stages:
            global _global_cleaner
            _global_cleaner = TextCleaner(enabled_stages=enabled_stages)


# Configurar al importar el módulo
configure_from_env()
