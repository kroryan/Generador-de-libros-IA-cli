#!/usr/bin/env python3
"""
Script de prueba para el nuevo sistema de perfiles de modelos.
Valida que la migración fue exitosa y los perfiles funcionan correctamente.
"""

import os
import sys

# Agregar directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from model_profiles import model_profile_manager, detect_model_size, get_model_context_window, get_model_optimal_parameters

def test_profile_loading():
    """Prueba que los perfiles se carguen correctamente"""
    print("=== Prueba de carga de perfiles ===")
    
    stats = model_profile_manager.get_stats()
    print(f"Perfiles cargados: {stats['total_profiles']}")
    
    if stats['total_profiles'] > 0:
        print("✅ Perfiles cargados exitosamente")
        print(f"Por proveedor: {stats.get('by_provider', {})}")
        print(f"Por categoría: {stats.get('by_size_category', {})}")
        print(f"Por tier: {stats.get('by_performance_tier', {})}")
    else:
        print("❌ No se cargaron perfiles")
    
    return stats['total_profiles'] > 0

def test_model_detection():
    """Prueba la detección de modelos específicos"""
    print("\n=== Prueba de detección de modelos ===")
    
    test_models = [
        ("gpt-4", "openai"),
        ("gpt-3.5-turbo", "openai"),
        ("claude-3-sonnet", "anthropic"),
        ("llama3", "ollama"),
        ("deepseek-chat", "deepseek"),
        ("mixtral-8x7b", "groq"),
        ("modelo-desconocido", None)
    ]
    
    success_count = 0
    
    for model_name, provider in test_models:
        print(f"\nProbando: {model_name} ({provider or 'sin proveedor'})")
        
        # Probar detección de perfil
        profile = model_profile_manager.detect_model_profile(model_name, provider)
        
        if profile:
            print(f"✅ Perfil detectado: {profile.display_name}")
            print(f"   Categoría: {profile.size_category}")
            print(f"   Contexto: {profile.context_window} tokens")
            print(f"   Tier: {profile.performance_tier}")
            print(f"   Costo: ${profile.cost_per_1k_tokens}/1K tokens")
            success_count += 1
        else:
            print(f"❌ No se detectó perfil para {model_name}")
        
        # Probar función de compatibilidad
        try:
            size = detect_model_size(model_name)
            print(f"   Tamaño detectado: {size}")
        except Exception as e:
            print(f"   Error en detect_model_size: {e}")
    
    print(f"\nDetecciones exitosas: {success_count}/{len(test_models)}")
    return success_count >= len(test_models) * 0.7  # 70% de éxito mínimo

def test_recommendations():
    """Prueba el sistema de recomendaciones"""
    print("\n=== Prueba de recomendaciones ===")
    
    test_cases = [
        {"use_case": "writing", "max_cost": 0.0},  # Solo modelos gratuitos
        {"use_case": "general", "min_context": 8000},  # Contexto grande
        {"use_case": "analysis", "provider_preference": ["openai", "anthropic"]},
        {"use_case": "privacy_sensitive", "max_cost": 0.01}
    ]
    
    for i, criteria in enumerate(test_cases, 1):
        print(f"\nCaso {i}: {criteria}")
        
        recommended = model_profile_manager.recommend_model(**criteria)
        
        if recommended:
            print(f"✅ Recomendado: {recommended.display_name}")
            print(f"   Proveedor: {recommended.provider}")
            print(f"   Contexto: {recommended.context_window}")
            print(f"   Costo: ${recommended.cost_per_1k_tokens}/1K")
        else:
            print("❌ No se encontró modelo que cumpla los criterios")

def test_utility_functions():
    """Prueba las funciones de utilidad"""
    print("\n=== Prueba de funciones de utilidad ===")
    
    # Probar ventana de contexto
    context = get_model_context_window("gpt-4")
    print(f"Contexto GPT-4: {context} tokens")
    
    # Probar parámetros optimizados
    params = get_model_optimal_parameters("llama3", "ollama")
    print(f"Parámetros Llama3: {params}")
    
    # Probar modelos por caso de uso
    writing_models = model_profile_manager.get_models_for_use_case("writing")
    print(f"Modelos para writing: {len(writing_models)}")
    
    if writing_models:
        print(f"Mejor para writing: {writing_models[0].display_name}")

def test_legacy_compatibility():
    """Prueba que la compatibilidad con el código anterior funcione"""
    print("\n=== Prueba de compatibilidad legacy ===")
    
    # Simular objetos LLM como los usaba el código anterior
    class MockLLM:
        def __init__(self, model_name):
            self.model = model_name
            self.model_name = model_name
    
    test_llms = [
        MockLLM("gpt-4"),
        MockLLM("llama3"),
        MockLLM("deepseek-chat")
    ]
    
    success_count = 0
    
    for llm in test_llms:
        try:
            size = detect_model_size(llm)
            print(f"✅ {llm.model}: {size}")
            success_count += 1
        except Exception as e:
            print(f"❌ Error con {llm.model}: {e}")
    
    print(f"Compatibilidad: {success_count}/{len(test_llms)} exitosos")
    return success_count == len(test_llms)

def main():
    """Ejecuta todas las pruebas"""
    print("🧪 Iniciando pruebas del sistema de perfiles de modelos\n")
    
    tests = [
        ("Carga de perfiles", test_profile_loading),
        ("Detección de modelos", test_model_detection),
        ("Recomendaciones", test_recommendations),
        ("Funciones de utilidad", test_utility_functions),
        ("Compatibilidad legacy", test_legacy_compatibility)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result if result is not None else True))
        except Exception as e:
            print(f"❌ Error en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen final
    print("\n" + "="*50)
    print("📊 RESUMEN DE PRUEBAS")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    print(f"\nPruebas exitosas: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 ¡Todas las pruebas pasaron! El sistema de perfiles funciona correctamente.")
        return True
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar la implementación.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)