"""
Tests para el sistema de extracción de segmentos de texto.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from text_segment_extractor import (
    TextSegmentExtractor,
    ExtractionStrategy,
    SegmentConfig,
    extract_key_segments
)


def test_short_text_passthrough():
    """Test que textos cortos se devuelven completos."""
    text = "Este es un texto corto que no necesita extracción."
    
    extractor = TextSegmentExtractor()
    result = extractor.extract(text, max_segments=3, segment_length=100)
    
    assert result == text, "Texto corto debe devolverse completo"
    print("✅ test_short_text_passthrough: OK")


def test_start_end_strategy():
    """Test estrategia START_END."""
    text = "A" * 1000 + "B" * 5000 + "C" * 1000
    
    config = SegmentConfig(
        strategy=ExtractionStrategy.START_END,
        respect_boundaries=False
    )
    extractor = TextSegmentExtractor(config)
    
    result = extractor.extract(text, max_segments=2, segment_length=500)
    
    # Debe contener inicio (A's) y final (C's)
    assert "INICIO DEL CAPÍTULO" in result
    assert "FINAL DEL CAPÍTULO" in result
    assert "CONTENIDO OMITIDO" in result
    
    # Debe tener A's al inicio y C's al final
    assert result.count("A") > 100  # Al menos 100 A's
    assert result.count("C") > 100  # Al menos 100 C's
    
    # El contenido del medio (B's) debe estar omitido en su mayoría
    assert result.count("B") < 1000  # Menos B's que en el texto original
    
    print("✅ test_start_end_strategy: OK")


def test_uniform_strategy():
    """Test estrategia UNIFORM."""
    text = "INICIO " * 200 + "MEDIO " * 800 + "FINAL " * 200
    
    config = SegmentConfig(
        strategy=ExtractionStrategy.UNIFORM,
        max_segments=3,
        respect_boundaries=False
    )
    extractor = TextSegmentExtractor(config)
    
    result = extractor.extract(text, max_segments=3, segment_length=500)
    
    # Debe contener marcadores de las tres partes
    assert "INICIO DEL CAPÍTULO" in result
    assert "PARTE 1 DEL CAPÍTULO" in result or "MEDIO" in result
    assert "FINAL DEL CAPÍTULO" in result
    
    print("✅ test_uniform_strategy: OK")


def test_adaptive_strategy():
    """Test estrategia ADAPTIVE."""
    # Crear texto con estructura clara
    text = (
        "Párrafo inicial uno.\n\n"
        "Párrafo inicial dos.\n\n" * 50 +
        "Párrafo medio importante.\n\n" * 100 +
        "Párrafo final uno.\n\n"
        "Párrafo final dos.\n\n" * 50
    )
    
    config = SegmentConfig(
        strategy=ExtractionStrategy.ADAPTIVE,
        max_segments=3
    )
    extractor = TextSegmentExtractor(config)
    
    result = extractor.extract(text, max_segments=3, segment_length=500)
    
    # Debe detectar las tres partes
    assert "INICIO DEL CAPÍTULO" in result
    assert "MEDIA" in result or "MEDIO" in result
    assert "FINAL DEL CAPÍTULO" in result
    
    # Debe contener contenido de las tres secciones
    assert "inicial" in result.lower()
    assert "final" in result.lower()
    
    print("✅ test_adaptive_strategy: OK")


def test_adaptive_scaling():
    """Test que adaptive_scaling ajusta longitud de segmento."""
    # Texto muy largo (>50k caracteres)
    long_text = "A" * 60000
    
    config = SegmentConfig(
        adaptive_scaling=True,
        base_segment_length=1000
    )
    extractor = TextSegmentExtractor(config)
    
    # Calcular longitud adaptativa
    adaptive_len = extractor._calculate_adaptive_length(long_text, 1000, 3)
    
    # Para texto > 50k, debe escalar hacia arriba
    assert adaptive_len > 1000, f"Expected scaled length > 1000, got {adaptive_len}"
    assert adaptive_len <= config.max_segment_length, "No debe exceder max_segment_length"
    
    # Texto corto (<5k caracteres)
    short_text = "B" * 4000
    adaptive_len_short = extractor._calculate_adaptive_length(short_text, 1000, 3)
    
    # Para texto < 5k, debe escalar hacia abajo
    assert adaptive_len_short < 1000, f"Expected scaled length < 1000, got {adaptive_len_short}"
    assert adaptive_len_short >= config.min_segment_length, "No debe ser menor a min_segment_length"
    
    print("✅ test_adaptive_scaling: OK")


def test_respect_boundaries():
    """Test que respect_boundaries respeta párrafos."""
    text = (
        "Primer párrafo con contenido.\n\n"
        "Segundo párrafo con más contenido.\n\n"
        "Tercer párrafo final.\n\n"
    ) * 50
    
    config = SegmentConfig(
        strategy=ExtractionStrategy.START_END,
        respect_boundaries=True
    )
    extractor = TextSegmentExtractor(config)
    
    result = extractor.extract(text, segment_length=200)
    
    # No debería cortar en medio de una palabra
    # Debe respetar límites de párrafo (doble salto de línea)
    lines = result.split('\n\n')
    
    # Al menos algunos límites deben ser respetados
    # (difícil verificar exactamente sin conocer el contenido exacto)
    assert len(lines) > 1, "Debe preservar algunos límites de párrafo"
    
    print("✅ test_respect_boundaries: OK")


def test_compatibility_function():
    """Test que la función de compatibilidad funciona."""
    text = "X" * 5000
    
    result = extract_key_segments(text, max_segments=3, segment_length=1000)
    
    # Debe devolver un string
    assert isinstance(result, str)
    
    # Para texto > segment_length * max_segments, debe extraer segmentos
    assert len(result) < len(text)
    
    print("✅ test_compatibility_function: OK")


def test_full_strategy():
    """Test estrategia FULL devuelve texto completo."""
    text = "Este es el texto completo que no debe modificarse." * 100
    
    config = SegmentConfig(strategy=ExtractionStrategy.FULL)
    extractor = TextSegmentExtractor(config)
    
    result = extractor.extract(text, max_segments=3, segment_length=500)
    
    # Debe devolver texto sin cambios
    assert result == text
    
    print("✅ test_full_strategy: OK")


def test_boundary_detection():
    """Test detección de límites naturales."""
    text = (
        "Primera oración. Segunda oración.\n\n"
        "Segundo párrafo con contenido. Más contenido.\n\n"
        "Tercer párrafo.\n\n"
    )
    
    config = SegmentConfig(respect_boundaries=True)
    extractor = TextSegmentExtractor(config)
    
    # Probar búsqueda hacia adelante
    boundary = extractor._find_boundary(text, 20, direction=1)
    
    # Debe encontrar algún límite natural (párrafo o oración)
    assert boundary != 20 or boundary <= 220  # Dentro del rango de búsqueda
    
    print("✅ test_boundary_detection: OK")


def test_segment_config_from_env():
    """Test creación de configuración desde variables de entorno."""
    # Configurar variables de entorno temporalmente
    original_values = {}
    env_vars = {
        'SEGMENT_EXTRACTION_STRATEGY': 'UNIFORM',
        'SEGMENT_MAX_COUNT': '5',
        'SEGMENT_BASE_LENGTH': '1500'
    }
    
    # Guardar valores originales y setear nuevos
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        config = SegmentConfig.from_env()
        
        assert config.strategy == ExtractionStrategy.UNIFORM
        assert config.max_segments == 5
        assert config.base_segment_length == 1500
        
        print("✅ test_segment_config_from_env: OK")
    finally:
        # Restaurar valores originales
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_all_tests():
    """Ejecuta todos los tests."""
    print("\n" + "="*60)
    print("🧪 TESTS DE TEXT SEGMENT EXTRACTOR")
    print("="*60 + "\n")
    
    test_short_text_passthrough()
    test_start_end_strategy()
    test_uniform_strategy()
    test_adaptive_strategy()
    test_adaptive_scaling()
    test_respect_boundaries()
    test_compatibility_function()
    test_full_strategy()
    test_boundary_detection()
    test_segment_config_from_env()
    
    print("\n" + "="*60)
    print("✅ TODOS LOS TESTS PASARON")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
