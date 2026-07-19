"""
Tests para el sistema de ordenamiento de capítulos.
"""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chapter_ordering import (
    ChapterOrdering,
    ChapterType,
    ChapterMetadata,
    sort_chapters_intelligently
)
from writing import _ordered_progressive_chapters


def test_parse_prologue():
    """Test detección de prólogos."""
    ordering = ChapterOrdering()
    
    test_cases = [
        "Prólogo",
        "prólogo",
        "Prologo",
        "Introducción",
        "Prefacio"
    ]
    
    for key in test_cases:
        meta = ordering.parse_chapter(key, 0)
        assert meta.type == ChapterType.PROLOGUE, f"Failed for: {key}"
    
    print("✅ test_parse_prologue: OK")


def test_parse_epilogue():
    """Test detección de epílogos."""
    ordering = ChapterOrdering()
    
    test_cases = [
        "Epílogo",
        "epilogo",
        "Conclusión",
        "Final"
    ]
    
    for key in test_cases:
        meta = ordering.parse_chapter(key, 0)
        assert meta.type == ChapterType.EPILOGUE, f"Failed for: {key}"
    
    print("✅ test_parse_epilogue: OK")


def test_parse_numbered_arabic():
    """Test detección de capítulos con números arábigos."""
    ordering = ChapterOrdering()
    
    test_cases = [
        ("Capítulo 1", 1),
        ("capitulo 5", 5),
        ("Cap. 10", 10),
        ("Capítulo 42: El Sentido", 42)
    ]
    
    for key, expected_num in test_cases:
        meta = ordering.parse_chapter(key, 0)
        assert meta.type == ChapterType.NUMBERED, f"Wrong type for: {key}"
        assert meta.number == expected_num, f"Wrong number for: {key}, got {meta.number}"
    
    print("✅ test_parse_numbered_arabic: OK")


def test_parse_numbered_roman():
    """Test detección de capítulos con números romanos."""
    ordering = ChapterOrdering()
    
    test_cases = [
        ("Capítulo I", 1),
        ("Capitulo V", 5),
        ("Capítulo X", 10),
        ("Capítulo XIV: El Misterio", 14),
        ("Capitulo XX", 20)
    ]
    
    for key, expected_num in test_cases:
        meta = ordering.parse_chapter(key, 0)
        assert meta.type == ChapterType.NUMBERED, f"Wrong type for: {key}"
        assert meta.number == expected_num, f"Wrong number for: {key}, got {meta.number}"
        assert meta.roman_number is not None, f"No roman saved for: {key}"
    
    print("✅ test_parse_numbered_roman: OK")


def test_sort_basic_sequence():
    """Test ordenamiento básico de secuencia."""
    chapters = {
        "Capítulo 3": "content3",
        "Prólogo": "intro",
        "Capítulo 1": "content1",
        "Epílogo": "outro",
        "Capítulo 2": "content2"
    }
    
    sorted_keys = sort_chapters_intelligently(chapters)
    
    expected_order = [
        "Prólogo",
        "Capítulo 1",
        "Capítulo 2",
        "Capítulo 3",
        "Epílogo"
    ]
    
    assert sorted_keys == expected_order, f"Expected {expected_order}, got {sorted_keys}"
    print("✅ test_sort_basic_sequence: OK")


def test_sort_complex_book():
    """Test ordenamiento de libro complejo con varios tipos."""
    chapters = {
        "Capítulo 10": "content",
        "Sección B": "section",
        "Prólogo": "intro",
        "Capítulo 5": "content",
        "Parte 2": "part",
        "Epílogo": "outro",
        "Capítulo 1": "content",
        "Parte 1": "part",
        "Sección A": "section"
    }
    
    sorted_keys = sort_chapters_intelligently(chapters)
    
    # Verificar orden general
    assert sorted_keys[0] == "Prólogo", "Prólogo debe ser primero"
    assert sorted_keys[-1] == "Epílogo", "Epílogo debe ser último"
    
    # Verificar capítulos numerados están ordenados
    chapter_indices = [
        (i, key) for i, key in enumerate(sorted_keys)
        if key.startswith("Capítulo")
    ]
    
    assert len(chapter_indices) == 3
    # Deben estar en orden 1, 5, 10
    assert "Capítulo 1" in sorted_keys[chapter_indices[0][0]]
    assert "Capítulo 5" in sorted_keys[chapter_indices[1][0]]
    assert "Capítulo 10" in sorted_keys[chapter_indices[2][0]]
    
    print("✅ test_sort_complex_book: OK")


def test_validate_sequence_duplicates():
    """Test validación de capítulos duplicados."""
    ordering = ChapterOrdering()
    
    chapters_meta = [
        ChapterMetadata("Capítulo 1", ChapterType.NUMBERED, number=1, original_index=0),
        ChapterMetadata("Capítulo 1 (bis)", ChapterType.NUMBERED, number=1, original_index=1),
        ChapterMetadata("Capítulo 2", ChapterType.NUMBERED, number=2, original_index=2)
    ]
    
    warnings = ordering.validate_sequence(chapters_meta)
    
    assert len(warnings) > 0, "Debería detectar duplicado"
    assert "duplicado" in warnings[0].lower(), "Warning debe mencionar duplicado"
    
    print("✅ test_validate_sequence_duplicates: OK")


def test_validate_sequence_gaps():
    """Test validación de saltos en numeración."""
    ordering = ChapterOrdering()
    
    chapters_meta = [
        ChapterMetadata("Capítulo 1", ChapterType.NUMBERED, number=1, original_index=0),
        ChapterMetadata("Capítulo 5", ChapterType.NUMBERED, number=5, original_index=1),
        ChapterMetadata("Capítulo 6", ChapterType.NUMBERED, number=6, original_index=2)
    ]
    
    warnings = ordering.validate_sequence(chapters_meta)
    
    assert len(warnings) > 0, "Debería detectar salto"
    assert "salto" in warnings[0].lower(), "Warning debe mencionar salto"
    
    print("✅ test_validate_sequence_gaps: OK")


def test_progressive_drafting_rejects_missing_previous_numbered_chapter():
    with pytest.raises(ValueError, match="Salto en numeración"):
        _ordered_progressive_chapters({
            "Capítulo 1": ["Inicio"],
            "Capítulo 30": ["Final prematuro"],
        })


def test_progressive_drafting_rejects_sequence_that_does_not_start_at_one():
    with pytest.raises(ValueError, match="must start at 1"):
        _ordered_progressive_chapters({"Chapter 30": ["Premature ending"]})


def test_comparison_operators():
    """Test operadores de comparación para ordenamiento."""
    ch1 = ChapterMetadata("Prólogo", ChapterType.PROLOGUE, original_index=0)
    ch2 = ChapterMetadata("Capítulo 1", ChapterType.NUMBERED, number=1, original_index=1)
    ch3 = ChapterMetadata("Capítulo 10", ChapterType.NUMBERED, number=10, original_index=2)
    ch4 = ChapterMetadata("Epílogo", ChapterType.EPILOGUE, original_index=3)
    
    # Prólogo antes de capítulos
    assert ch1 < ch2, "Prólogo debe venir antes de capítulos"
    
    # Capítulos ordenados numéricamente
    assert ch2 < ch3, "Capítulo 1 antes de Capítulo 10"
    
    # Capítulos antes de epílogo
    assert ch3 < ch4, "Capítulos antes de epílogo"
    
    # Prólogo antes de epílogo
    assert ch1 < ch4, "Prólogo antes de epílogo"
    
    print("✅ test_comparison_operators: OK")


def test_preserve_unknown_order():
    """Test preservación de orden para capítulos desconocidos."""
    chapters = {
        "Algo raro 1": "content1",
        "Capítulo 1": "chapter",
        "Otro formato extraño": "content2",
        "Capítulo 2": "chapter",
        "Sin formato": "content3"
    }
    
    sorted_keys = sort_chapters_intelligently(chapters)
    
    # Los capítulos conocidos deben estar ordenados
    ch1_idx = sorted_keys.index("Capítulo 1")
    ch2_idx = sorted_keys.index("Capítulo 2")
    assert ch1_idx < ch2_idx, "Capítulos numerados deben estar ordenados"
    
    # Los desconocidos deben preservar orden relativo original
    unknown_keys = ["Algo raro 1", "Otro formato extraño", "Sin formato"]
    unknown_indices = [sorted_keys.index(key) for key in unknown_keys]
    
    # Deben aparecer en el mismo orden relativo
    assert unknown_indices == sorted(unknown_indices), "Orden de desconocidos debe preservarse"
    
    print("✅ test_preserve_unknown_order: OK")


def run_all_tests():
    """Ejecuta todos los tests."""
    print("\n" + "="*60)
    print("🧪 TESTS DE CHAPTER ORDERING")
    print("="*60 + "\n")
    
    test_parse_prologue()
    test_parse_epilogue()
    test_parse_numbered_arabic()
    test_parse_numbered_roman()
    test_sort_basic_sequence()
    test_sort_complex_book()
    test_validate_sequence_duplicates()
    test_validate_sequence_gaps()
    test_comparison_operators()
    test_preserve_unknown_order()
    
    print("\n" + "="*60)
    print("✅ TODOS LOS TESTS PASARON")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
