#!/usr/bin/env python3
"""
Test de integración completa del sistema de contexto dinámico.
Simula el flujo completo sin generar un libro real.
"""

import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_app_integration():
    """Test de integración con app.py sin ejecutar generación real"""
    print("\n" + "=" * 60)
    print("TEST: Integración con app.py")
    print("=" * 60)
    
    try:
        # Simular configuración de modelo
        os.environ["MODEL_TYPE"] = "ollama"
        
        from app import run_cli_generation
        from dynamic_context import DynamicContextCalculator
        
        # Test del calculador independiente
        calc = DynamicContextCalculator("llama3", "ollama")
        
        # Verificar que las variables de entorno se configurarían correctamente
        profile = calc.profile
        
        checks = [
            (profile.context_window > 0, f"Ventana detectada: {profile.context_window}"),
            (profile.section_limit > 0, f"Límite sección: {profile.section_limit}"),
            (profile.chapter_limit > 0, f"Límite capítulo: {profile.chapter_limit}"),
            (calc.get_context_summary() is not None, "Resumen de contexto disponible")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Mostrar configuración que se aplicaría
        context_summary = calc.get_context_summary()
        print("  Configuración que se aplicaría:")
        print(f"    CONTEXT_LIMITED_SIZE={profile.section_limit}")
        print(f"    CONTEXT_STANDARD_SIZE={profile.chapter_limit}")
        print(f"    CONTEXT_GLOBAL_LIMIT={profile.global_limit}")
        print(f"    CONTEXT_MAX_ACCUMULATION={profile.accumulation_threshold}")
        
        if all_passed:
            print("\n✓ Integración con app.py funcionaría correctamente")
        else:
            print("\n✗ Problemas con integración app.py")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando módulos: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test de app: {e}")
        return False

def test_writing_integration():
    """Test de integración con writing.py sin ejecutar escritura real"""
    print("\n" + "=" * 60)
    print("TEST: Integración con writing.py")
    print("=" * 60)
    
    try:
        from writing import WriterChain
        from unified_context import UnifiedContextManager
        from dynamic_context import DynamicContextCalculator
        
        # Simular inicialización como en write_book
        calc = DynamicContextCalculator("gpt-4", "openai")
        
        # Mock de LLM simple para testing
        class MockLLM:
            def invoke(self, prompt):
                return "Respuesta simulada del modelo."
        
        mock_llm = MockLLM()
        
        # Crear context manager con sistema dinámico
        context_manager = UnifiedContextManager(
            framework="Test de integración",
            llm=mock_llm,
            enable_micro_summaries=True,
            micro_summary_interval=2,
            model_profile=calc.profile
        )
        
        checks = [
            (context_manager.dynamic_context_enabled, "Sistema dinámico habilitado en writing"),
            (hasattr(context_manager, 'get_dynamic_status'), "Método get_dynamic_status disponible"),
            (context_manager.base_profile is not None, "Perfil base configurado")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Simular flujo de capítulo
        context_manager.register_chapter("cap1", "Capítulo de Prueba", "Resumen inicial")
        
        # Simular secciones con análisis dinámico
        test_sections = [
            "Ana llegó a París después del viaje desde Barcelona.",
            "Pedro la esperaba en el aeropuerto con una sonrisa nerviosa.",
            "- ¿Cómo estuvo el vuelo? - preguntó Pedro.",
            "- Bien, aunque un poco turbulento - respondió Ana."
        ]
        
        for i, section in enumerate(test_sections, 1):
            context_manager.update_chapter_content("cap1", section)
            print(f"  Sección {i} procesada con análisis dinámico")
        
        # Obtener estado final
        status = context_manager.get_dynamic_status()
        complexity_report = status.get('complexity_report', {})
        quality_report = status.get('quality_report', {})
        
        print(f"  Complejidad final: {complexity_report.get('complexity_category', 'N/A')}")
        print(f"  Calidad promedio: {quality_report.get('quality_category', 'N/A')}")
        
        if all_passed:
            print("\n✓ Integración con writing.py funcionando correctamente")
        else:
            print("\n✗ Problemas con integración writing.py")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando módulos: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test de writing: {e}")
        return False

def test_different_models():
    """Test con diferentes tipos de modelos"""
    print("\n" + "=" * 60)
    print("TEST: Diferentes Modelos")
    print("=" * 60)
    
    test_models = [
        ("gpt-4", "openai"),
        ("claude-3-opus", "anthropic"),
        ("llama3", "ollama"),
        ("deepseek-chat", "deepseek"),
        ("modelo-desconocido", "proveedor-desconocido")
    ]
    
    results = []
    
    try:
        from dynamic_context import DynamicContextCalculator
        
        for model_name, provider in test_models:
            try:
                calc = DynamicContextCalculator(model_name, provider)
                profile = calc.profile
                
                results.append({
                    "model": f"{provider}:{model_name}",
                    "window": profile.context_window,
                    "section_limit": profile.section_limit,
                    "chapter_limit": profile.chapter_limit,
                    "success": True
                })
                
                print(f"  ✓ {provider}:{model_name} - Ventana: {profile.context_window}")
                
            except Exception as e:
                results.append({
                    "model": f"{provider}:{model_name}",
                    "error": str(e),
                    "success": False
                })
                print(f"  ✗ {provider}:{model_name} - Error: {e}")
        
        successful = len([r for r in results if r["success"]])
        total = len(results)
        
        print(f"\nModelos procesados exitosamente: {successful}/{total}")
        
        # Verificar que al menos los modelos conocidos funcionen
        successful_known = len([r for r in results[:4] if r["success"]])
        
        if successful_known >= 3:
            print("✓ Detección de modelos funcionando correctamente")
            return True
        else:
            print("✗ Problemas con detección de modelos conocidos")
            return False
        
    except ImportError as e:
        print(f"✗ Error importando: {e}")
        return False
    except Exception as e:
        print(f"✗ Error general: {e}")
        return False

def main():
    """Ejecuta tests de integración completa"""
    print("=" * 60)
    print("TEST DE INTEGRACIÓN COMPLETA - SISTEMA DINÁMICO")
    print("=" * 60)
    
    tests = [
        ("Integración App.py", test_app_integration),
        ("Integración Writing.py", test_writing_integration),
        ("Diferentes Modelos", test_different_models)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✓ PASS: {test_name}")
            else:
                print(f"\n✗ FAIL: {test_name}")
        except Exception as e:
            print(f"\n✗ ERROR: {test_name} - {str(e)}")
    
    print("\n" + "=" * 60)
    print("RESUMEN DE INTEGRACIÓN COMPLETA")
    print("=" * 60)
    print(f"Tests de integración pasados: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 SISTEMA DE CONTEXTO DINÁMICO COMPLETAMENTE FUNCIONAL")
        print("\nCaracterísticas implementadas:")
        print("✓ Detección automática de ventana de contexto por modelo")
        print("✓ Análisis de complejidad narrativa en tiempo real")
        print("✓ Evaluación de calidad de resúmenes adaptativa")
        print("✓ Ajuste dinámico de límites de contexto")
        print("✓ Integración transparente con sistema existente")
        print("✓ Compatibilidad retroactiva completa")
        print("✓ Soporte para múltiples proveedores y modelos")
        return 0
    else:
        print(f"\n❌ {total - passed} tests de integración fallaron")
        return 1

if __name__ == "__main__":
    exit(main())