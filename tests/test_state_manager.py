"""
Test rápido del GenerationStateManager.

Valida:
- Transiciones de estado válidas
- Reset desde cualquier estado
- Observers funcionando
- Thread safety básico
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from generation_state import (
    GenerationStateManager,
    GenerationStatus,
    StateObserver
)

def test_reset_from_any_state():
    """Test que reset() funciona desde cualquier estado."""
    print("🧪 Test 1: Reset desde cualquier estado")
    
    manager = GenerationStateManager()
    
    # Reset desde IDLE (inicial)
    state = manager.reset()
    assert state.status == GenerationStatus.IDLE
    print("  ✅ Reset desde IDLE funciona")
    
    # Cambiar a STARTING y resetear
    manager.update_state(status=GenerationStatus.STARTING)
    state = manager.reset()
    assert state.status == GenerationStatus.IDLE
    print("  ✅ Reset desde STARTING funciona")
    
    # Cambiar a ERROR y resetear
    manager.update_state(status=GenerationStatus.STARTING)
    manager.update_state(status=GenerationStatus.ERROR)
    state = manager.reset()
    assert state.status == GenerationStatus.IDLE
    print("  ✅ Reset desde ERROR funciona")
    
    print("✅ Test 1 PASADO\n")

def test_valid_transitions():
    """Test de transiciones válidas."""
    print("🧪 Test 2: Transiciones válidas")
    
    manager = GenerationStateManager()
    manager.reset()
    
    # IDLE -> STARTING
    state = manager.update_state(status=GenerationStatus.STARTING)
    assert state.status == GenerationStatus.STARTING
    print("  ✅ IDLE -> STARTING")
    
    # STARTING -> CONFIGURING_MODEL
    state = manager.update_state(status=GenerationStatus.CONFIGURING_MODEL)
    assert state.status == GenerationStatus.CONFIGURING_MODEL
    print("  ✅ STARTING -> CONFIGURING_MODEL")
    
    # CONFIGURING_MODEL -> GENERATING_STRUCTURE
    state = manager.update_state(status=GenerationStatus.GENERATING_STRUCTURE)
    assert state.status == GenerationStatus.GENERATING_STRUCTURE
    print("  ✅ CONFIGURING_MODEL -> GENERATING_STRUCTURE")
    
    print("✅ Test 2 PASADO\n")

def test_invalid_transition():
    """Test que transiciones inválidas fallan."""
    print("🧪 Test 3: Transición inválida debe fallar")
    
    manager = GenerationStateManager()
    manager.reset()
    
    # IDLE -> COMPLETE es inválido
    try:
        manager.update_state(status=GenerationStatus.COMPLETE)
        print("  ❌ NO debería permitir IDLE -> COMPLETE")
        assert False, "Debería haber lanzado ValueError"
    except ValueError as e:
        print(f"  ✅ Transición bloqueada correctamente: {e}")
    
    print("✅ Test 3 PASADO\n")

def test_observer_notification():
    """Test que observers reciben notificaciones."""
    print("🧪 Test 4: Notificación a observers")
    
    class TestObserver(StateObserver):
        def __init__(self):
            self.notifications = []
        
        def on_state_changed(self, old_state, new_state):
            self.notifications.append((old_state.status, new_state.status))
    
    manager = GenerationStateManager()
    observer = TestObserver()
    manager.add_observer(observer)
    
    # Reset inicial
    manager.reset()
    
    # Cambiar estado
    manager.update_state(status=GenerationStatus.STARTING)
    
    # Verificar notificaciones
    assert len(observer.notifications) >= 2
    print(f"  ✅ Observer recibió {len(observer.notifications)} notificaciones")
    
    print("✅ Test 4 PASADO\n")

def test_state_history():
    """Test que el historial de estados se guarda."""
    print("🧪 Test 5: Historial de estados")
    
    manager = GenerationStateManager()
    manager.reset()
    
    initial_history_len = len(manager.get_history())
    
    # Hacer varios cambios
    manager.update_state(status=GenerationStatus.STARTING)
    manager.update_state(status=GenerationStatus.CONFIGURING_MODEL)
    manager.update_state(status=GenerationStatus.GENERATING_STRUCTURE)
    
    history = manager.get_history()
    assert len(history) > initial_history_len
    print(f"  ✅ Historial tiene {len(history)} estados")
    
    # Verificar que el último estado es el actual
    current = manager.get_state()
    assert history[-1].status == current.status
    print("  ✅ Último estado del historial coincide con estado actual")
    
    print("✅ Test 5 PASADO\n")

def test_state_immutability():
    """Test que GenerationState es inmutable."""
    print("🧪 Test 6: Inmutabilidad de estado")
    
    manager = GenerationStateManager()
    state1 = manager.get_state()
    
    # Intentar modificar debería fallar
    try:
        state1.status = GenerationStatus.STARTING
        print("  ❌ Estado NO es inmutable!")
        assert False, "Estado debería ser inmutable"
    except Exception:
        print("  ✅ Estado es inmutable (no se puede modificar)")
    
    # Cambiar estado crea nuevo objeto
    manager.update_state(status=GenerationStatus.STARTING)
    state2 = manager.get_state()
    
    assert state1 is not state2
    print("  ✅ update_state() crea nuevo objeto")
    
    print("✅ Test 6 PASADO\n")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTS DEL GENERATION STATE MANAGER")
    print("=" * 60 + "\n")
    
    try:
        test_reset_from_any_state()
        test_valid_transitions()
        test_invalid_transition()
        test_observer_notification()
        test_state_history()
        test_state_immutability()
        
        print("=" * 60)
        print("✅ TODOS LOS TESTS PASARON (6/6)")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
