"""
Test del sistema unificado de limpieza de texto.

Valida que todas las funciones de limpieza funcionan correctamente
y son compatibles con el código existente.
"""

import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from text_cleaning import (
    clean_think_tags,
    clean_ansi_codes,
    clean_content,
    clean_all,
    TextCleaner,
    CleaningStage
)


def test_clean_think_tags():
    """Test de limpieza de tags de pensamiento."""
    print("=" * 60)
    print("TEST: clean_think_tags()")
    print("=" * 60)
    
    test_cases = [
        (
            "Texto antes <think>Esto es pensamiento</think> texto después",
            "Texto antes texto después"
        ),
        (
            "[pensamiento: algo aquí] texto normal",
            "texto normal"
        ),
        (
            "Inicio <razonamiento>razonamiento aquí</razonamiento> fin",
            "Inicio fin"
        ),
        (
            "(thinking: thoughts) normal text",
            "normal text"
        )
    ]
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = clean_think_tags(input_text)
        success = result.strip() == expected.strip()
        print(f"\nCaso {i}: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"  Input:    {input_text[:60]}...")
        print(f"  Expected: {expected[:60]}...")
        print(f"  Got:      {result[:60]}...")
        
        if not success:
            return False
    
    print("\n✓ Todos los casos de clean_think_tags() pasaron")
    return True


def test_clean_ansi_codes():
    """Test de limpieza de códigos ANSI."""
    print("\n" + "=" * 60)
    print("TEST: clean_ansi_codes()")
    print("=" * 60)
    
    test_cases = [
        (
            "\x1B[97mTexto con color\x1B[0m",
            "Texto con color"
        ),
        (
            "[97mTexto[0m normal",
            "Texto normal"
        ),
        (
            "\x1B[1;31mRojo\x1B[0m y \x1B[1;32mVerde\x1B[0m",
            "Rojo y Verde"
        )
    ]
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = clean_ansi_codes(input_text)
        success = result.strip() == expected.strip()
        print(f"\nCaso {i}: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"  Input:    {repr(input_text[:40])}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")
        
        if not success:
            return False
    
    print("\n✓ Todos los casos de clean_ansi_codes() pasaron")
    return True


def test_clean_content():
    """Test de limpieza de contenido completo."""
    print("\n" + "=" * 60)
    print("TEST: clean_content()")
    print("=" * 60)
    
    test_input = """
    <think>Pensamiento del modelo</think>
    
    Este es el texto narrativo normal que debe permanecer.
    
    [Nota: Esto debe ser eliminado]
    
    Más texto narrativo aquí.
    
    [Desarrollo: notas de desarrollo]
    
    ### Encabezado Markdown ###
    
    Texto final.
    
    Resumen: esto debe irse
    """
    
    result = clean_content(test_input)
    
    # Verificar que se eliminaron los elementos no narrativos
    checks = [
        ("<think>" not in result, "Tags <think> eliminados"),
        ("[Nota:" not in result, "Notas eliminadas"),
        ("[Desarrollo:" not in result, "Notas de desarrollo eliminadas"),
        ("###" not in result, "Encabezados markdown eliminados"),
        ("Resumen:" not in result, "Líneas de resumen eliminadas"),
        ("texto narrativo" in result, "Texto narrativo preservado"),
        ("Texto final" in result, "Contenido válido preservado")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    print(f"\nResultado limpio (primeros 200 chars):")
    print(f"  {result[:200]}...")
    
    if all_passed:
        print("\n✓ Todos los checks de clean_content() pasaron")
    else:
        print("\n✗ Algunos checks fallaron")
    
    return all_passed


def test_text_cleaner_stages():
    """Test de etapas individuales del TextCleaner."""
    print("\n" + "=" * 60)
    print("TEST: TextCleaner con etapas específicas")
    print("=" * 60)
    
    cleaner = TextCleaner()
    
    test_text = "\x1B[97m<think>pensamiento</think> [Nota: nota] texto normal"
    
    # Test de aplicación por etapas
    result_ansi = cleaner.clean_stage(test_text, CleaningStage.ANSI_CODES)
    result_think = cleaner.clean_stage(result_ansi, CleaningStage.THINK_TAGS)
    result_metadata = cleaner.clean_stage(result_think, CleaningStage.METADATA)
    
    checks = [
        ("\x1B" not in result_ansi, "Etapa ANSI_CODES funcionó"),
        ("<think>" not in result_think, "Etapa THINK_TAGS funcionó"),
        ("[Nota:" not in result_metadata, "Etapa METADATA funcionó"),
        ("texto normal" in result_metadata, "Texto preservado")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Todas las etapas funcionaron correctamente")
    else:
        print("\n✗ Algunas etapas fallaron")
    
    return all_passed


def test_backwards_compatibility():
    """Test de compatibilidad con código existente."""
    print("\n" + "=" * 60)
    print("TEST: Compatibilidad con código existente")
    print("=" * 60)
    
    # Simular uso como en utils.py
    text_with_think = "Texto <think>pensamiento</think> más texto"
    result = clean_think_tags(text_with_think)
    check1 = "<think>" not in result and "Texto" in result
    
    # Simular uso como en server.py
    text_with_ansi = "\x1B[97mTexto coloreado\x1B[0m"
    result = clean_ansi_codes(text_with_ansi)
    check2 = "\x1B" not in result and "Texto coloreado" in result
    
    # Simular uso como en publishing.py
    text_with_metadata = "Texto <think>x</think> [Nota: y] narrativo"
    result = clean_content(text_with_metadata)
    check3 = "<think>" not in result and "[Nota:" not in result and "narrativo" in result
    
    checks = [
        (check1, "Compatibilidad con utils.py (clean_think_tags)"),
        (check2, "Compatibilidad con server.py (clean_ansi_codes)"),
        (check3, "Compatibilidad con publishing.py (clean_content)")
    ]
    
    all_passed = True
    for check, description in checks:
        status = "✓ PASS" if check else "✗ FAIL"
        print(f"  {status}: {description}")
        if not check:
            all_passed = False
    
    if all_passed:
        print("\n✓ Compatibilidad con código existente verificada")
    else:
        print("\n✗ Problemas de compatibilidad detectados")
    
    return all_passed


def main():
    """Ejecuta todos los tests."""
    print("\n" + "=" * 60)
    print("INICIANDO TESTS DEL SISTEMA UNIFICADO DE LIMPIEZA")
    print("=" * 60)
    
    tests = [
        test_clean_think_tags,
        test_clean_ansi_codes,
        test_clean_content,
        test_text_cleaner_stages,
        test_backwards_compatibility
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
        print("\n✓ TODOS LOS TESTS PASARON - Sistema unificado de limpieza funcionando correctamente")
        return 0
    else:
        print(f"\n✗ {total - passed} TESTS FALLARON - Revisar implementación")
        return 1


if __name__ == "__main__":
    exit(main())
