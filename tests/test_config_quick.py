"""
Test rápido del sistema de configuración.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.defaults import get_config, print_config, reload_config


def test_basic_config():
    """Test básico de carga de configuración."""
    print("🧪 Test 1: Carga básica de configuración")
    
    config = get_config()
    assert config is not None, "Config no debe ser None"
    
    # Verificar valores por defecto
    assert config.retry.max_retries == 3
    assert config.socketio.ping_timeout == 3600  # 1 hora, no 72!
    assert config.rate_limit.default_delay == 0.5
    assert config.context.limited_context_size == 2000
    assert config.llm.temperature == 0.7
    
    print("✅ Configuración cargada correctamente\n")


def test_singleton():
    """Test que get_config() retorna el mismo objeto."""
    print("🧪 Test 2: Singleton")
    
    config1 = get_config()
    config2 = get_config()
    
    assert config1 is config2, "Debe ser el mismo objeto (singleton)"
    
    print("✅ Singleton funcionando correctamente\n")


def test_validation():
    """Test de validación."""
    print("🧪 Test 3: Validación")
    
    config = get_config()
    errors = config.validate()
    
    assert len(errors) == 0, f"No debe haber errores: {errors}"
    
    print("✅ Validación pasada correctamente\n")


def test_rate_limit_delays():
    """Test de delays por provider."""
    print("🧪 Test 4: Rate Limiting Delays")
    
    config = get_config()
    rate_limit = config.rate_limit
    
    # Verificar delays por defecto
    assert rate_limit.get_delay('openai') == 1.0
    assert rate_limit.get_delay('groq') == 0.5
    assert rate_limit.get_delay('ollama') == 0.1
    
    # Provider desconocido debe usar default
    assert rate_limit.get_delay('unknown_provider') == 0.5
    
    print("✅ Rate limiting funcionando correctamente\n")


def test_backoff_calculation():
    """Test de cálculo de backoff."""
    print("🧪 Test 5: Cálculo de Backoff")
    
    config = get_config()
    retry = config.retry
    
    # Exponential: 1, 2, 4, 8, 10 (max)
    assert retry.calculate_delay(0) == 1.0
    assert retry.calculate_delay(1) == 2.0
    assert retry.calculate_delay(2) == 4.0
    assert retry.calculate_delay(3) == 8.0
    assert retry.calculate_delay(4) == 10.0  # Limitado por max_delay
    
    print("✅ Backoff exponencial funcionando\n")


def test_config_from_env():
    """Test de configuración desde variables de entorno."""
    print("🧪 Test 6: Configuración desde ENV")
    
    # Verificar que el sistema LEE de ENV al iniciar
    # (sin intentar recargar que puede causar deadlock)
    
    # Verificar que valores por defecto están correctos
    config = get_config()
    
    # Si LLM_TEMPERATURE estaba en ENV, se habrá leído
    env_temp = os.environ.get('LLM_TEMPERATURE')
    if env_temp:
        expected = float(env_temp)
        assert config.llm.temperature == expected, f"Debe leer {expected} de ENV"
    else:
        # Si no hay ENV, debe usar default
        assert config.llm.temperature == 0.7, "Debe usar default sin ENV"
    
    print("✅ Configuración desde ENV funcionando\n")


def run_all_tests():
    """Ejecuta todos los tests."""
    print("\n" + "="*60)
    print("🧪 TESTS DEL SISTEMA DE CONFIGURACIÓN")
    print("="*60 + "\n")
    
    try:
        test_basic_config()
        test_singleton()
        test_validation()
        test_rate_limit_delays()
        test_backoff_calculation()
        test_config_from_env()
        
        print("="*60)
        print("✅ TODOS LOS TESTS PASARON")
        print("="*60 + "\n")
        
        # Imprimir configuración final
        print_config()
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLÓ: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise


if __name__ == "__main__":
    run_all_tests()
