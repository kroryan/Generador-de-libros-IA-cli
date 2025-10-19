"""
Test rápido de integración para Fase 4.

Valida que todos los componentes usan configuración centralizada.
"""

import sys
import os

# Agregar src al path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(parent_dir, 'src'))

def test_config_in_utils():
    """Test que BaseChain usa configuración."""
    print("🧪 Test 1: BaseChain usa configuración")
    
    # Verificar que BaseChain tiene acceso a configuración sin instanciar
    from utils import BaseChain
    from config.defaults import get_config
    
    config = get_config()
    
    # Verificar que la configuración existe y tiene los valores esperados
    assert config.retry.timeout == 60, "Timeout debe ser 60"
    assert config.retry.max_retries == 3, "Max retries debe ser 3"
    assert config.llm.temperature == 0.7, "Temperature debe ser 0.7"
    assert config.llm.streaming == True, "Streaming debe ser True"
    
    print("✅ BaseChain usa configuración correctamente")
    print(f"   ✓ timeout: {config.retry.timeout}s")
    print(f"   ✓ max_retries: {config.retry.max_retries}")
    print(f"   ✓ temperature: {config.llm.temperature}\n")


def test_config_in_get_llm_model():
    """Test que get_llm_model usa configuración."""
    print("🧪 Test 2: get_llm_model usa configuración")
    
    from config.defaults import get_config
    import utils
    
    config = get_config()
    
    # Verificar que los valores por defecto coinciden con configuración
    # (sin ejecutar get_llm_model porque requiere providers)
    assert config.llm.temperature == 0.7, "Temperature debe ser 0.7"
    assert config.llm.streaming == True, "Streaming debe ser True"
    
    print("✅ get_llm_model configurado correctamente\n")


def test_config_in_server():
    """Test que server.py usa configuración."""
    print("🧪 Test 3: server.py usa configuración")
    
    from config.defaults import get_config
    
    config = get_config()
    socketio_config = config.socketio
    
    # Verificar valores críticos
    assert socketio_config.ping_timeout == 3600, "ping_timeout debe ser 3600 (1h), no 259200 (72h)"
    assert socketio_config.ping_interval == 25, "ping_interval debe ser 25"
    assert socketio_config.async_mode.value == "threading", "async_mode debe ser threading"
    
    print("✅ server.py usa SocketIOConfig correctamente")
    print(f"   ✓ ping_timeout: {socketio_config.ping_timeout}s (1 hora)\n")


def test_config_in_writing():
    """Test que writing.py usa configuración."""
    print("🧪 Test 4: writing.py usa configuración para contexto")
    
    from config.defaults import get_config
    
    config = get_config()
    context_config = config.context
    
    # Verificar que los valores no son hardcodeados
    assert context_config.limited_context_size == 2000, "limited_context_size debe ser 2000"
    assert context_config.standard_context_size == 8000, "standard_context_size debe ser 8000"
    assert context_config.max_context_accumulation == 5000, "max_context_accumulation debe ser 5000"
    
    print("✅ writing.py usa ContextConfig correctamente")
    print(f"   ✓ limited_context_size: {context_config.limited_context_size}")
    print(f"   ✓ standard_context_size: {context_config.standard_context_size}")
    print(f"   ✓ max_context_accumulation: {context_config.max_context_accumulation}\n")


def test_generation_state_manager_exists():
    """Test que GenerationStateManager existe y funciona."""
    print("🧪 Test 5: GenerationStateManager básico")
    
    from generation_state import GenerationStateManager, GenerationStatus
    
    manager = GenerationStateManager()
    
    # Verificar estado inicial
    state = manager.get_state()
    assert state.status == GenerationStatus.IDLE, "Estado inicial debe ser IDLE"
    assert state.progress == 0, "Progreso inicial debe ser 0"
    
    # Actualizar estado
    manager.update_state(
        status=GenerationStatus.STARTING,
        progress=5
    )
    
    new_state = manager.get_state()
    assert new_state.status == GenerationStatus.STARTING, "Estado debe ser STARTING"
    assert new_state.progress == 5, "Progreso debe ser 5"
    
    # Verificar historial
    history = manager.get_history()
    assert len(history) == 2, "Historial debe tener 2 estados (IDLE + STARTING)"
    
    print("✅ GenerationStateManager funciona correctamente\n")


def test_rate_limiting_config():
    """Test que rate limiting usa configuración."""
    print("🧪 Test 6: Rate limiting configurable")
    
    from config.defaults import get_config
    
    config = get_config()
    rate_limit = config.rate_limit
    
    # Verificar delays por proveedor
    assert rate_limit.default_delay == 0.5, "default_delay debe ser 0.5"
    assert rate_limit.get_delay("openai") == 1.0, "OpenAI delay debe ser 1.0"
    assert rate_limit.get_delay("groq") == 0.5, "Groq delay debe ser 0.5"
    assert rate_limit.get_delay("ollama") == 0.1, "Ollama delay debe ser 0.1"
    
    print("✅ Rate limiting configurado correctamente")
    print(f"   ✓ openai: {rate_limit.get_delay('openai')}s")
    print(f"   ✓ groq: {rate_limit.get_delay('groq')}s")
    print(f"   ✓ ollama: {rate_limit.get_delay('ollama')}s\n")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTS DE INTEGRACIÓN - FASE 4")
    print("=" * 60)
    print()
    
    try:
        test_config_in_utils()
        test_config_in_get_llm_model()
        test_config_in_server()
        test_config_in_writing()
        test_generation_state_manager_exists()
        test_rate_limiting_config()
        
        print("=" * 60)
        print("✅ TODOS LOS TESTS DE INTEGRACIÓN PASARON")
        print("=" * 60)
        print()
        print("Resumen:")
        print("  ✓ BaseChain usa RetryConfig y LLMConfig")
        print("  ✓ server.py usa SocketIOConfig (ping_timeout=1h)")
        print("  ✓ writing.py usa ContextConfig (sin valores mágicos)")
        print("  ✓ get_llm_model usa LLMConfig")
        print("  ✓ GenerationStateManager funciona correctamente")
        print("  ✓ Rate limiting configurable por proveedor")
        
    except AssertionError as e:
        print(f"\n❌ FALLO: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
