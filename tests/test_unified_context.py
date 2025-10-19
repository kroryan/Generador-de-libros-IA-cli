"""
Test del sistema unificado de gestión de contexto.

Valida que UnifiedContextManager funciona correctamente y es compatible
con el código existente que usaba ProgressiveContextManager.
"""

import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unified_context import UnifiedContextManager, ContextMode, ProgressiveContextManager


def test_basic_context_operations():
    """Test de operaciones básicas del contexto."""
    print("=" * 60)
    print("TEST: Operaciones básicas de contexto")
    print("=" * 60)
    
    manager = UnifiedContextManager(framework="Marco narrativo de prueba")
    
    # Registrar un capítulo
    manager.register_chapter("cap1", "Capítulo 1: El Inicio", "Resumen del capítulo 1")
    
    # Actualizar contenido
    manager.update_chapter_content("cap1", "Primera sección de contenido")
    manager.update_chapter_content("cap1", "Segunda sección de contenido")
    
    # Obtener contexto
    context = manager.get_context_for_section(1, "medio", "cap1")
    
    checks = [
        (context is not None, "Contexto obtenido correctamente"),
        ("framework" in context, "Framework presente en contexto"),
        (context["framework"] == "Marco narrativo de prueba", "Framework correcto"),
        ("current_chapter_summary" in context, "Resumen del capítulo actual presente"),
        ("Primera sección" in context["current_chapter_summary"], "Contenido preservado")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Todas las operaciones básicas funcionaron correctamente")
    else:
        print("\n✗ Algunas operaciones fallaron")
    
    return all_passed


def test_multiple_chapters():
    """Test de gestión de múltiples capítulos."""
    print("\n" + "=" * 60)
    print("TEST: Gestión de múltiples capítulos")
    print("=" * 60)
    
    manager = UnifiedContextManager(framework="Historia épica")
    
    # Registrar múltiples capítulos
    for i in range(1, 4):
        chapter_key = f"cap{i}"
        manager.register_chapter(chapter_key, f"Capítulo {i}", f"Resumen cap {i}")
        manager.update_chapter_content(chapter_key, f"Contenido del capítulo {i}")
    
    # Obtener contexto para capítulo 3 (debería incluir info de cap 1 y 2)
    context = manager.get_context_for_section(3, "medio", "cap3")
    
    checks = [
        (context is not None, "Contexto para capítulo 3 obtenido"),
        ("previous_chapters_summary" in context, "Resumen de capítulos previos presente"),
        (len(context["previous_chapters_summary"]) > 0, "Resumen de capítulos previos no vacío"),
        ("current_chapter_summary" in context, "Resumen actual presente")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Gestión de múltiples capítulos funciona correctamente")
    else:
        print("\n✗ Problemas con múltiples capítulos")
    
    return all_passed


def test_backwards_compatibility():
    """Test de compatibilidad con ProgressiveContextManager."""
    print("\n" + "=" * 60)
    print("TEST: Compatibilidad con ProgressiveContextManager")
    print("=" * 60)
    
    # Usar el alias de compatibilidad
    manager = ProgressiveContextManager(framework="Test de compatibilidad")
    
    # Usar la API antigua
    manager.register_chapter("cap1", "Capítulo 1", "Resumen")
    manager.update_chapter_content("cap1", "Contenido")
    context = manager.get_context_for_section(1, "inicio", "cap1")
    
    checks = [
        (manager is not None, "Manager instanciado con alias"),
        (isinstance(manager, UnifiedContextManager), "Es instancia de UnifiedContextManager"),
        (context is not None, "Contexto obtenido con API antigua"),
        ("framework" in context, "Estructura de contexto compatible")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Compatibilidad retroactiva verificada")
    else:
        print("\n✗ Problemas de compatibilidad")
    
    return all_passed


def test_context_modes():
    """Test de diferentes modos de contexto."""
    print("\n" + "=" * 60)
    print("TEST: Modos de contexto (simple, progressive, intelligent)")
    print("=" * 60)
    
    # Test modo simple
    simple_manager = UnifiedContextManager(
        framework="Test",
        mode=ContextMode.SIMPLE
    )
    
    # Test modo progressive
    progressive_manager = UnifiedContextManager(
        framework="Test",
        mode=ContextMode.PROGRESSIVE
    )
    
    # Test modo intelligent (sin LLM, debe funcionar con fallback)
    intelligent_manager = UnifiedContextManager(
        framework="Test",
        mode=ContextMode.INTELLIGENT,
        llm=None  # Sin LLM
    )
    
    checks = [
        (simple_manager.mode == ContextMode.SIMPLE, "Modo SIMPLE configurado"),
        (progressive_manager.mode == ContextMode.PROGRESSIVE, "Modo PROGRESSIVE configurado"),
        (intelligent_manager.mode == ContextMode.INTELLIGENT, "Modo INTELLIGENT configurado"),
        (simple_manager is not None, "Manager simple funcional"),
        (progressive_manager is not None, "Manager progressive funcional"),
        (intelligent_manager is not None, "Manager intelligent funcional sin LLM")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Todos los modos de contexto funcionan")
    else:
        print("\n✗ Problemas con modos de contexto")
    
    return all_passed


def test_context_size_limits():
    """Test de límites de tamaño de contexto."""
    print("\n" + "=" * 60)
    print("TEST: Límites de tamaño de contexto")
    print("=" * 60)
    
    manager = UnifiedContextManager(
        framework="Test",
        max_context_size=100  # Límite muy pequeño para testing
    )
    
    # Agregar contenido largo
    manager.register_chapter("cap1", "Capítulo 1", "Resumen")
    
    # Agregar muchas secciones largas
    for i in range(5):
        long_content = "Esta es una sección muy larga. " * 50  # ~1500 chars
        manager.update_chapter_content("cap1", long_content)
    
    context = manager.get_context_for_section(1, "medio", "cap1")
    
    # El contexto actual debería estar limitado
    current_summary_len = len(context["current_chapter_summary"])
    
    checks = [
        (context is not None, "Contexto obtenido con límite de tamaño"),
        (current_summary_len <= manager.max_context_size, 
         f"Resumen limitado a {manager.max_context_size} chars (actual: {current_summary_len})")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Límites de tamaño funcionan correctamente")
    else:
        print("\n✗ Problemas con límites de tamaño")
    
    return all_passed


def test_from_chapter_summary():
    """Test de importación desde chapter_summary.py."""
    print("\n" + "=" * 60)
    print("TEST: Importación desde chapter_summary.py")
    print("=" * 60)
    
    try:
        # Simular el import que hace writing.py
        from chapter_summary import ProgressiveContextManager as PCM
        
        # Verificar que es realmente UnifiedContextManager
        manager = PCM(framework="Test")
        
        checks = [
            (PCM is not None, "ProgressiveContextManager importado"),
            (isinstance(manager, UnifiedContextManager), "Es UnifiedContextManager"),
            (hasattr(manager, 'register_chapter'), "Tiene método register_chapter"),
            (hasattr(manager, 'update_chapter_content'), "Tiene método update_chapter_content"),
            (hasattr(manager, 'get_context_for_section'), "Tiene método get_context_for_section")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        if all_passed:
            print("\n✓ Importación desde chapter_summary.py funciona")
        else:
            print("\n✗ Problemas con importación")
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ ERROR en importación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests."""
    print("\n" + "=" * 60)
    print("INICIANDO TESTS DEL SISTEMA UNIFICADO DE CONTEXTO")
    print("=" * 60)
    
    tests = [
        test_basic_context_operations,
        test_multiple_chapters,
        test_backwards_compatibility,
        test_context_modes,
        test_context_size_limits,
        test_from_chapter_summary
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n✗ ERROR en {test_func.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_func.__name__, False))
    
    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DE TESTS")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nResultado final: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("\n✓ TODOS LOS TESTS PASARON - Sistema unificado de contexto funcionando correctamente")
        return 0
    else:
        print(f"\n✗ {total - passed} TESTS FALLARON - Revisar implementación")
        return 1


if __name__ == "__main__":
    exit(main())
