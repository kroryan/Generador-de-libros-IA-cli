"""
Test de integración para validar la Fase 2.

Verifica que los cambios en sistemas de limpieza y contexto
no rompieron la funcionalidad existente.
"""

import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_imports():
    """Test de que todos los imports funcionan correctamente."""
    print("=" * 60)
    print("TEST: Imports de módulos actualizados")
    print("=" * 60)
    
    try:
        # Imports de limpieza de texto
        from text_cleaning import clean_think_tags, clean_ansi_codes, clean_content
        print("  ✓ PASS: text_cleaning importado")
        
        from streaming_cleaner import StreamingCleaner, OutputCapture
        print("  ✓ PASS: streaming_cleaner importado")
        
        # Imports de contexto
        from unified_context import UnifiedContextManager, ContextMode
        print("  ✓ PASS: unified_context importado")
        
        from chapter_summary import ProgressiveContextManager, ChapterSummaryChain
        print("  ✓ PASS: chapter_summary importado con compatibilidad")
        
        # Verificar alias
        assert ProgressiveContextManager == UnifiedContextManager
        print("  ✓ PASS: Alias de compatibilidad correcto")
        
        # Imports de módulos principales
        from utils import clean_think_tags as utils_clean
        print("  ✓ PASS: utils.clean_think_tags importado")
        
        # Verificar que clean_think_tags de utils usa el nuevo sistema
        test_text = "<think>test</think> normal"
        result = utils_clean(test_text)
        assert "<think>" not in result
        print("  ✓ PASS: utils.clean_think_tags funciona correctamente")
        
        print("\n✓ Todos los imports funcionan correctamente")
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR en imports: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_writing_chain_mock():
    """Test simulado de WriterChain con el nuevo sistema."""
    print("\n" + "=" * 60)
    print("TEST: Simulación de WriterChain con nuevo contexto")
    print("=" * 60)
    
    try:
        from chapter_summary import ProgressiveContextManager
        from utils import clean_think_tags
        
        # Simular lo que hace write_book()
        framework = "Marco narrativo de prueba"
        context_manager = ProgressiveContextManager(framework)
        
        # Simular operaciones de un capítulo
        chapter_key = "cap1"
        chapter_title = "Capítulo 1: El Inicio"
        chapter_summary = "Un capítulo de prueba"
        
        context_manager.register_chapter(chapter_key, chapter_title, chapter_summary)
        print("  ✓ PASS: Capítulo registrado")
        
        # Simular escritura de secciones
        for i in range(3):
            content = f"Sección {i+1}: Contenido de prueba con <think>pensamiento</think> y texto normal."
            cleaned_content = clean_think_tags(content)
            context_manager.update_chapter_content(chapter_key, cleaned_content)
            print(f"  ✓ PASS: Sección {i+1} agregada y limpiada")
        
        # Obtener contexto
        context = context_manager.get_context_for_section(1, "medio", chapter_key)
        
        checks = [
            (context is not None, "Contexto obtenido"),
            ("framework" in context, "Framework en contexto"),
            (context["framework"] == framework, "Framework correcto"),
            ("current_chapter_summary" in context, "Resumen actual presente"),
            ("<think>" not in context["current_chapter_summary"], "Contenido limpiado correctamente")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        if all_passed:
            print("\n✓ Simulación de WriterChain funciona correctamente")
        else:
            print("\n✗ Problemas en simulación de WriterChain")
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ ERROR en simulación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_server_output_capture_mock():
    """Test simulado de OutputCapture para server.py."""
    print("\n" + "=" * 60)
    print("TEST: Simulación de OutputCapture para server")
    print("=" * 60)
    
    try:
        from streaming_cleaner import OutputCapture
        
        # Lista para capturar emisiones simuladas
        emissions = []
        
        def mock_emit(event_type, data):
            emissions.append((event_type, data))
        
        # Crear OutputCapture con emit simulado
        capture = OutputCapture(socketio_emit_func=mock_emit)
        
        # Simular escritura de datos
        capture.write("Texto normal ")
        capture.write("<think>Esto es pensamiento ")
        capture.write("más pensamiento</think> ")
        capture.write("más texto normal")
        capture.flush()
        
        # Verificar que se emitieron eventos
        has_result = any(event_type == 'result_update' for event_type, _ in emissions)
        has_thinking = any(event_type == 'thinking_update' for event_type, _ in emissions)
        
        checks = [
            (len(emissions) > 0, "Se emitieron eventos"),
            (has_result, "Se emitió result_update"),
            (has_thinking, "Se emitió thinking_update")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        print(f"  ℹ️  Total de eventos emitidos: {len(emissions)}")
        
        if all_passed:
            print("\n✓ Simulación de OutputCapture funciona correctamente")
        else:
            print("\n✗ Problemas en simulación de OutputCapture")
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ ERROR en simulación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_publishing_clean_content_mock():
    """Test simulado de limpieza de contenido para publishing."""
    print("\n" + "=" * 60)
    print("TEST: Simulación de limpieza para publishing")
    print("=" * 60)
    
    try:
        from text_cleaning import clean_content
        
        # Simular contenido de un capítulo con varios tipos de ruido
        dirty_content = """
        <think>Pensamiento del modelo</think>
        
        Este es el texto narrativo real que debe permanecer.
        
        [Nota: Esto debe eliminarse]
        
        Más narrativa aquí con diálogos importantes.
        
        [Desarrollo: notas internas]
        
        ### Encabezado que debe irse ###
        
        Final del capítulo con contenido válido.
        
        Resumen: esto no debería estar
        """
        
        cleaned = clean_content(dirty_content, aggressive=True)
        
        checks = [
            ("<think>" not in cleaned, "Tags de pensamiento eliminados"),
            ("[Nota:" not in cleaned, "Notas eliminadas"),
            ("[Desarrollo:" not in cleaned, "Notas de desarrollo eliminadas"),
            ("###" not in cleaned, "Encabezados markdown eliminados"),
            ("Resumen:" not in cleaned, "Líneas de resumen eliminadas"),
            ("texto narrativo real" in cleaned, "Texto narrativo preservado"),
            ("diálogos importantes" in cleaned, "Contenido importante preservado"),
            ("Final del capítulo" in cleaned, "Contenido final preservado")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        if all_passed:
            print("\n✓ Limpieza de contenido para publishing funciona correctamente")
        else:
            print("\n✗ Problemas en limpieza de contenido")
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ ERROR en simulación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests de integración."""
    print("\n" + "=" * 60)
    print("TESTS DE INTEGRACIÓN - FASE 2")
    print("Validación de cambios en sistemas de limpieza y contexto")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_writing_chain_mock,
        test_server_output_capture_mock,
        test_publishing_clean_content_mock
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
    print("RESUMEN DE TESTS DE INTEGRACIÓN")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nResultado final: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("\n✓ TODOS LOS TESTS DE INTEGRACIÓN PASARON")
        print("✓ Los cambios de Fase 2 no rompieron funcionalidad existente")
        print("✓ Sistema listo para validación end-to-end")
        return 0
    else:
        print(f"\n✗ {total - passed} TESTS FALLARON")
        print("✗ Revisar problemas de integración antes de continuar")
        return 1


if __name__ == "__main__":
    exit(main())
