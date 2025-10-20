#!/usr/bin/env python3
"""
Test básico del sistema de contexto dinámico.
Verifica las nuevas funcionalidades implementadas.
"""

import sys
import os

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_dynamic_context_calculator():
    """Test del calculador de contexto dinámico"""
    print("\n" + "=" * 60)
    print("TEST: DynamicContextCalculator")
    print("=" * 60)
    
    try:
        from dynamic_context import DynamicContextCalculator, ModelContextProfile
        
        # Test con modelo conocido
        calc = DynamicContextCalculator("gpt-4", "openai")
        
        checks = [
            (calc.profile.context_window > 0, "Ventana de contexto detectada"),
            (calc.profile.safe_context_limit > 0, "Límite seguro calculado"),
            (calc.profile.section_limit > 0, "Límite de sección definido"),
            (calc.profile.chapter_limit > 0, "Límite de capítulo definido"),
            (calc.profile.global_limit > 0, "Límite global definido"),
            (calc.profile.accumulation_threshold > 0, "Umbral de acumulación definido")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Test de límites dinámicos
        dynamic_limits = calc.calculate_dynamic_limits(1.3, 1.2)  # Complejidad alta, calidad buena
        print(f"  Límites dinámicos calculados: {dynamic_limits}")
        
        # Test de estimación de tokens
        token_estimate = calc.get_token_estimate(1000)
        print(f"  Estimación de tokens para 1000 chars: {token_estimate}")
        
        if all_passed:
            print("\n✓ DynamicContextCalculator funcionando correctamente")
        else:
            print("\n✗ Problemas con DynamicContextCalculator")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando DynamicContextCalculator: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test: {e}")
        return False

def test_narrative_complexity_analyzer():
    """Test del analizador de complejidad narrativa"""
    print("\n" + "=" * 60)
    print("TEST: NarrativeComplexityAnalyzer")
    print("=" * 60)
    
    try:
        from narrative_complexity import NarrativeComplexityAnalyzer
        
        analyzer = NarrativeComplexityAnalyzer()
        
        # Texto de ejemplo con personajes y acciones
        test_text = """
        María caminó hacia la casa donde esperaba Juan. El viento soplaba fuerte
        mientras ella pensaba en lo que había ocurrido en Madrid. 
        - ¿Estás bien? - preguntó Juan cuando la vio llegar.
        - Sí, solo estoy preocupada - respondió María con una sonrisa triste.
        """
        
        # Analizar el texto
        analysis = analyzer.analyze_section(test_text, 1)
        
        checks = [
            (analysis is not None, "Análisis completado"),
            (analysis.get('character_count', 0) > 0, f"Personajes detectados: {analysis.get('character_count', 0)}"),
            (analysis.get('complexity_score', 0) > 0, f"Score de complejidad: {analysis.get('complexity_score', 0):.2f}"),
            (analysis.get('dialogue_density', 0) > 0, f"Densidad de diálogo: {analysis.get('dialogue_density', 0):.3f}"),
            (analysis.get('narrative_elements', {}).get('dialogues', 0) > 0, "Diálogos detectados")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Test del multiplicador de contexto
        multiplier = analyzer.get_context_multiplier()
        print(f"  Multiplicador de contexto: {multiplier:.2f}")
        
        if all_passed:
            print("\n✓ NarrativeComplexityAnalyzer funcionando correctamente")
        else:
            print("\n✗ Problemas con NarrativeComplexityAnalyzer")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando NarrativeComplexityAnalyzer: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test: {e}")
        return False

def test_summary_quality_evaluator():
    """Test del evaluador de calidad de resúmenes"""
    print("\n" + "=" * 60)
    print("TEST: SummaryQualityEvaluator")
    print("=" * 60)
    
    try:
        from summary_quality import SummaryQualityEvaluator
        
        evaluator = SummaryQualityEvaluator()
        
        # Texto original y resumen de ejemplo
        original_text = """
        María caminó lentamente por las calles de Madrid, recordando los días cuando
        Juan y ella solían pasear juntos por estos mismos lugares. La nostalgia la
        invadió mientras observaba las tiendas que habían visitado tantas veces.
        Decidió entrar en la librería donde se habían conocido, esperando encontrar
        alguna pista sobre el paradero de Juan, quien había desaparecido misteriosamente
        la semana anterior sin dejar rastro alguno.
        """
        
        summary = """
        María recorrió Madrid recordando a Juan. Visitó la librería donde se conocieron
        buscando pistas sobre su misteriosa desaparición de la semana pasada.
        """
        
        # Evaluar calidad
        quality = evaluator.evaluate_summary(original_text, summary)
        
        checks = [
            (0.0 <= quality <= 1.0, f"Calidad en rango válido: {quality:.3f}"),
            (len(evaluator.quality_history) > 0, "Historial de calidad actualizado"),
            (evaluator.avg_quality > 0, f"Promedio de calidad: {evaluator.avg_quality:.3f}")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Test del factor de agresividad
        aggressiveness = evaluator.get_aggressiveness_factor()
        print(f"  Factor de agresividad: {aggressiveness:.2f}")
        
        # Test de múltiples evaluaciones para ver evolución
        for i in range(3):
            test_summary = f"Resumen de prueba {i+1} con diferentes características."
            quality = evaluator.evaluate_summary(original_text, test_summary)
            print(f"  Evaluación {i+1}: calidad={quality:.3f}")
        
        report = evaluator.get_quality_report()
        print(f"  Reporte final: {report.get('quality_category', 'N/A')}")
        
        if all_passed:
            print("\n✓ SummaryQualityEvaluator funcionando correctamente")
        else:
            print("\n✗ Problemas con SummaryQualityEvaluator")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando SummaryQualityEvaluator: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test: {e}")
        return False

def test_unified_context_integration():
    """Test de integración del contexto dinámico con UnifiedContextManager"""
    print("\n" + "=" * 60)
    print("TEST: Integración Sistema Dinámico")
    print("=" * 60)
    
    try:
        from unified_context import UnifiedContextManager
        from dynamic_context import DynamicContextCalculator
        
        # Crear calculador
        calc = DynamicContextCalculator("llama3", "ollama")
        
        # Crear manager con perfil dinámico
        manager = UnifiedContextManager(
            framework="Test dinámico",
            model_profile=calc.profile,
            enable_micro_summaries=False  # Sin LLM para test
        )
        
        checks = [
            (manager.dynamic_context_enabled, "Sistema dinámico habilitado"),
            (hasattr(manager, 'complexity_analyzer'), "Analizador de complejidad presente"),
            (hasattr(manager, 'summary_evaluator'), "Evaluador de calidad presente"),
            (hasattr(manager, 'get_dynamic_status'), "Método get_dynamic_status disponible"),
            (hasattr(manager, 'get_complexity_report'), "Método get_complexity_report disponible")
        ]
        
        all_passed = True
        for check, description in checks:
            status = "✓ PASS" if check else "✗ FAIL"
            print(f"  {status}: {description}")
            if not check:
                all_passed = False
        
        # Test de funcionalidad dinámica
        manager.register_chapter("cap1", "Capítulo 1", "Resumen de prueba")
        
        # Añadir contenido con elementos narrativos
        test_content = """
        Ana llegó a Barcelona después del viaje desde Valencia. Encontró a Pedro 
        esperándola en la estación, tal como habían acordado. 
        - ¿Cómo estuvo el viaje? - preguntó Pedro con una sonrisa.
        - Largo, pero al fin llegué - respondió Ana aliviada.
        """
        
        manager.update_chapter_content("cap1", test_content)
        
        # Obtener estado dinámico
        status = manager.get_dynamic_status()
        
        print(f"  Estado dinámico obtenido: {bool(status)}")
        if status.get('complexity_report'):
            complexity = status['complexity_report']
            print(f"  Complejidad detectada: {complexity.get('overall_complexity', 'N/A')}")
        
        if all_passed:
            print("\n✓ Integración del sistema dinámico funcionando")
        else:
            print("\n✗ Problemas con la integración dinática")
        
        return all_passed
        
    except ImportError as e:
        print(f"✗ Error importando módulos: {e}")
        return False
    except Exception as e:
        print(f"✗ Error ejecutando test de integración: {e}")
        return False

def main():
    """Ejecuta todos los tests del sistema dinámico"""
    print("=" * 60)
    print("TESTS DEL SISTEMA DE CONTEXTO DINÁMICO")
    print("=" * 60)
    
    tests = [
        ("DynamicContextCalculator", test_dynamic_context_calculator),
        ("NarrativeComplexityAnalyzer", test_narrative_complexity_analyzer),
        ("SummaryQualityEvaluator", test_summary_quality_evaluator),
        ("Integración Sistema Dinámico", test_unified_context_integration)
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
    print("RESUMEN DE TESTS DEL SISTEMA DINÁMICO")
    print("=" * 60)
    print(f"Tests pasados: {passed}/{total}")
    
    if passed == total:
        print("\n✓ TODOS LOS TESTS DEL SISTEMA DINÁMICO PASARON")
        return 0
    else:
        print(f"\n✗ {total - passed} tests fallaron")
        return 1

if __name__ == "__main__":
    exit(main())