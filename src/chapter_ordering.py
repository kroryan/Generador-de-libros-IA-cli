"""
Sistema de Ordenamiento Inteligente de Capítulos.

Este módulo reemplaza la lógica manual de ordenamiento O(n²) con un sistema
configurable, extensible y O(n log n) que soporta múltiples formatos de capítulos.

Características:
- Detección automática de tipos de capítulos (prólogo, numerados, epílogo, etc.)
- Soporte para números arábigos y romanos
- Configuración por patrones regex
- Validación de secuencia (duplicados, saltos, etc.)
- Soporte multi-idioma
"""

from enum import Enum, auto
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import re
import os
import json


class ChapterType(Enum):
    """Tipos de capítulos reconocidos."""
    PROLOGUE = auto()      # Prólogo / Introduction
    NUMBERED = auto()      # Capítulo numerado
    EPILOGUE = auto()      # Epílogo / Conclusion
    PART = auto()          # Parte (para libros divididos en partes)
    SECTION = auto()       # Sección
    APPENDIX = auto()      # Apéndice
    UNKNOWN = auto()       # Formato no reconocido


@dataclass
class ChapterMetadata:
    """Metadata de un capítulo para ordenamiento."""
    key: str                              # Clave original del diccionario
    type: ChapterType                     # Tipo de capítulo
    number: Optional[int] = None          # Número del capítulo (arábigo)
    roman_number: Optional[str] = None    # Número romano original
    part_number: Optional[int] = None     # Número de parte
    section_id: Optional[str] = None      # ID de sección (A, B, C, etc.)
    original_index: int = 0               # Orden de inserción original
    
    def __lt__(self, other: 'ChapterMetadata') -> bool:
        """Implementa ordenamiento natural de capítulos."""
        # Orden de prioridad de tipos
        type_order = {
            ChapterType.PROLOGUE: 0,
            ChapterType.PART: 1,
            ChapterType.NUMBERED: 2,
            ChapterType.SECTION: 3,
            ChapterType.EPILOGUE: 4,
            ChapterType.APPENDIX: 5,
            ChapterType.UNKNOWN: 6
        }
        
        # Comparar por tipo primero
        if self.type != other.type:
            return type_order[self.type] < type_order[other.type]
        
        # Dentro del mismo tipo, comparar por número
        if self.type == ChapterType.NUMBERED:
            if self.number is not None and other.number is not None:
                return self.number < other.number
        elif self.type == ChapterType.PART:
            if self.part_number is not None and other.part_number is not None:
                return self.part_number < other.part_number
        elif self.type == ChapterType.SECTION:
            if self.section_id is not None and other.section_id is not None:
                return self.section_id < other.section_id
        
        # Para tipos sin número o UNKNOWN, preservar orden original
        return self.original_index < other.original_index
    
    def __repr__(self) -> str:
        if self.type == ChapterType.NUMBERED and self.number:
            return f"Chapter({self.key}, type={self.type.name}, num={self.number})"
        return f"Chapter({self.key}, type={self.type.name})"


class ChapterOrdering:
    """
    Sistema inteligente de ordenamiento de capítulos.
    
    Reemplaza la lógica manual dispersa con un sistema centralizado,
    configurable y extensible.
    """
    
    # Patrones por defecto (español)
    DEFAULT_PATTERNS = {
        "prologue": [
            r"^prólogo$",
            r"^prologo$",
            r"^introducción$",
            r"^introduccion$",
            r"^prefacio$"
        ],
        "epilogue": [
            r"^epílogo$",
            r"^epilogo$",
            r"^conclusión$",
            r"^conclusion$",
            r"^final$"
        ],
        "numbered": [
            r"^capítulo\s+(\d+)",
            r"^capitulo\s+(\d+)",
            r"^cap\.?\s+(\d+)",
            r"^capítulo\s+([IVX]+)",
            r"^capitulo\s+([IVX]+)"
        ],
        "part": [
            r"^parte\s+(\d+)",
            r"^part\s+(\d+)"
        ],
        "section": [
            r"^sección\s+([A-Z])",
            r"^seccion\s+([A-Z])",
            r"^section\s+([A-Z])"
        ],
        "appendix": [
            r"^apéndice",
            r"^apendice",
            r"^appendix"
        ]
    }
    
    # Tabla de conversión de números romanos
    ROMAN_TO_INT = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }
    
    def __init__(
        self,
        patterns: Optional[Dict[str, List[str]]] = None,
        locale: str = "es",
        strict_mode: bool = False,
        preserve_unknown_order: bool = True
    ):
        """
        Inicializa el sistema de ordenamiento.
        
        Args:
            patterns: Patrones regex personalizados por tipo
            locale: Idioma para patrones por defecto
            strict_mode: Si True, lanza error ante duplicados
            preserve_unknown_order: Mantener orden original para capítulos desconocidos
        """
        self.patterns = self._compile_patterns(patterns or self.DEFAULT_PATTERNS)
        self.locale = locale
        self.strict_mode = strict_mode
        self.preserve_unknown_order = preserve_unknown_order
        
        # Configurar desde variables de entorno
        self._configure_from_env()
    
    def _configure_from_env(self):
        """Configurar desde variables de entorno."""
        locale_env = os.environ.get('CHAPTER_ORDERING_LOCALE', '').lower()
        if locale_env:
            self.locale = locale_env
        
        strict_env = os.environ.get('CHAPTER_ORDERING_STRICT_MODE', '').lower()
        if strict_env in ['true', '1', 'yes']:
            self.strict_mode = True
        
        preserve_env = os.environ.get('CHAPTER_ORDERING_PRESERVE_UNKNOWN', '').lower()
        if preserve_env in ['false', '0', 'no']:
            self.preserve_unknown_order = False
    
    def _compile_patterns(self, patterns: Dict[str, List[str]]) -> Dict[str, List[re.Pattern]]:
        """Compila los patrones regex."""
        compiled = {}
        for category, pattern_list in patterns.items():
            compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in pattern_list
            ]
        return compiled
    
    def parse_chapter(self, key: str, index: int) -> ChapterMetadata:
        """
        Parsea una clave de capítulo para extraer metadata.
        
        Args:
            key: Clave del capítulo (ej: "Capítulo 1: El Inicio")
            index: Índice original en el diccionario
            
        Returns:
            ChapterMetadata con información extraída
        """
        key_lower = key.lower().strip()
        
        # Detectar prólogo
        for pattern in self.patterns.get("prologue", []):
            if pattern.search(key_lower):
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.PROLOGUE,
                    original_index=index
                )
        
        # Detectar epílogo
        for pattern in self.patterns.get("epilogue", []):
            if pattern.search(key_lower):
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.EPILOGUE,
                    original_index=index
                )
        
        # Detectar capítulos numerados
        for pattern in self.patterns.get("numbered", []):
            match = pattern.search(key_lower)
            if match:
                number_str = match.group(1)
                
                # Convertir número romano si es necesario
                if self._is_roman_number(number_str):
                    number = self._roman_to_int(number_str)
                    roman = number_str.upper()
                else:
                    number = int(number_str)
                    roman = None
                
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.NUMBERED,
                    number=number,
                    roman_number=roman,
                    original_index=index
                )
        
        # Detectar partes
        for pattern in self.patterns.get("part", []):
            match = pattern.search(key_lower)
            if match:
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.PART,
                    part_number=int(match.group(1)),
                    original_index=index
                )
        
        # Detectar secciones
        for pattern in self.patterns.get("section", []):
            match = pattern.search(key_lower)
            if match:
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.SECTION,
                    section_id=match.group(1).upper(),
                    original_index=index
                )
        
        # Detectar apéndices
        for pattern in self.patterns.get("appendix", []):
            if pattern.search(key_lower):
                return ChapterMetadata(
                    key=key,
                    type=ChapterType.APPENDIX,
                    original_index=index
                )
        
        # Tipo desconocido
        return ChapterMetadata(
            key=key,
            type=ChapterType.UNKNOWN,
            original_index=index
        )
    
    def _is_roman_number(self, s: str) -> bool:
        """Verifica si un string es un número romano."""
        return bool(re.match(r'^[IVXLCDMivxlcdm]+$', s))
    
    def _roman_to_int(self, s: str) -> int:
        """Convierte número romano a entero."""
        s = s.upper()
        result = 0
        prev_value = 0
        
        for char in reversed(s):
            value = self.ROMAN_TO_INT.get(char, 0)
            if value < prev_value:
                result -= value
            else:
                result += value
            prev_value = value
        
        return result
    
    def sort_chapters(self, chapters: Dict[str, Any]) -> List[str]:
        """
        Ordena capítulos de manera inteligente.
        
        Args:
            chapters: Diccionario de capítulos {key: content}
            
        Returns:
            Lista de claves ordenadas
        """
        # Parsear todos los capítulos
        metadata_list = [
            self.parse_chapter(key, idx)
            for idx, key in enumerate(chapters.keys())
        ]
        
        # Validar secuencia
        warnings = self.validate_sequence(metadata_list)
        if warnings:
            from utils import print_progress
            for warning in warnings:
                print_progress(f"⚠️ {warning}")
            
            if self.strict_mode:
                raise ValueError(f"Errores en secuencia de capítulos: {warnings}")
        
        # Ordenar usando comparadores nativos
        metadata_list.sort()
        
        # Devolver claves ordenadas
        return [meta.key for meta in metadata_list]
    
    def validate_sequence(self, chapters: List[ChapterMetadata]) -> List[str]:
        """
        Valida la secuencia de capítulos y detecta problemas.
        
        Args:
            chapters: Lista de metadata de capítulos
            
        Returns:
            Lista de warnings/errores detectados
        """
        warnings = []
        
        # Verificar duplicados en capítulos numerados
        seen_numbers = {}
        for ch in chapters:
            if ch.type == ChapterType.NUMBERED and ch.number:
                if ch.number in seen_numbers:
                    warnings.append(
                        f"Capítulo {ch.number} duplicado: '{ch.key}' y '{seen_numbers[ch.number]}'"
                    )
                seen_numbers[ch.number] = ch.key
        
        # Verificar saltos en numeración
        numbers = sorted([
            ch.number for ch in chapters
            if ch.type == ChapterType.NUMBERED and ch.number
        ])
        
        if numbers:
            for i in range(len(numbers) - 1):
                if numbers[i+1] - numbers[i] > 1:
                    warnings.append(
                        f"Salto en numeración: del capítulo {numbers[i]} al {numbers[i+1]}"
                    )
        
        # Verificar múltiples prólogos
        prologues = [ch for ch in chapters if ch.type == ChapterType.PROLOGUE]
        if len(prologues) > 1:
            warnings.append(
                f"Múltiples prólogos detectados: {[ch.key for ch in prologues]}"
            )
        
        # Verificar múltiples epílogos
        epilogues = [ch for ch in chapters if ch.type == ChapterType.EPILOGUE]
        if len(epilogues) > 1:
            warnings.append(
                f"Múltiples epílogos detectados: {[ch.key for ch in epilogues]}"
            )
        
        return warnings
    
    @classmethod
    def from_config_file(cls, config_path: str) -> 'ChapterOrdering':
        """
        Crea una instancia desde un archivo de configuración JSON.
        
        Args:
            config_path: Ruta al archivo JSON con patrones
            
        Returns:
            Instancia configurada de ChapterOrdering
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        locale = config.get('locale', 'es')
        patterns = config.get('patterns', cls.DEFAULT_PATTERNS)
        
        return cls(patterns=patterns, locale=locale)
    
    @classmethod
    def from_env(cls) -> 'ChapterOrdering':
        """Crea una instancia configurada desde variables de entorno."""
        return cls()


# Función de compatibilidad para reemplazar código existente
def sort_chapters_intelligently(chapters_dict: Dict[str, Any]) -> List[str]:
    """
    Función helper para ordenar capítulos de manera inteligente.
    
    Reemplaza la lógica manual O(n²) con un sistema O(n log n).
    
    Args:
        chapters_dict: Diccionario de capítulos {key: content}
        
    Returns:
        Lista de claves ordenadas
    """
    ordering = ChapterOrdering.from_env()
    return ordering.sort_chapters(chapters_dict)
