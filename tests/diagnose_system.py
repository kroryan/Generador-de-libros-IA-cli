#!/usr/bin/env python3
"""
Script de diagnóstico rápido para identificar problemas en el sistema de proveedores.
"""

import os
import sys
import traceback

# Cargar dotenv explícitamente
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Archivo .env cargado exitosamente")
except ImportError:
    print("❌ python-dotenv no disponible, usando variables de entorno del sistema")
except Exception as e:
    print(f"⚠️ Error cargando .env: {e}")

# Agregar directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_provider_discovery():
    """Prueba el sistema de discovery de proveedores"""
    print("=== Diagnóstico del Sistema de Proveedores ===\n")
    
    try:
        from provider_registry import ProviderRegistry
        print("✅ Importación de ProviderRegistry exitosa")
        
        # Crear registry
        registry = ProviderRegistry()
        print("✅ Creación de ProviderRegistry exitosa")
        
        # Forzar discovery
        print("\n🔍 Iniciando discovery de proveedores...")
        registry.discover_providers()
        print("✅ Discovery completado")
        
        # Listar proveedores encontrados
        providers = registry.list_providers()
        print(f"\n📋 Proveedores encontrados: {len(providers)}")
        for provider in providers:
            status = "🟢" if provider.is_configured() else "🔴"
            print(f"  {status} {provider.name}: {provider.model}")
        
        # Debug adicional - verificar qué variables ve el registry
        print(f"\n🔍 Debug variables de entorno:")
        print(f"  MODEL_TYPE: {os.environ.get('MODEL_TYPE', 'NO_SET')}")
        print(f"  OLLAMA_MODEL: {os.environ.get('OLLAMA_MODEL', 'NO_SET')}")
        print(f"  OLLAMA_API_KEY: {os.environ.get('OLLAMA_API_KEY', 'NO_SET')}")
        print(f"  OLLAMA_API_BASE: {os.environ.get('OLLAMA_API_BASE', 'NO_SET')}")
        
        # Obtener stats del registry
        stats = registry.get_stats()
        print(f"\n📊 Stats del registry: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en discovery: {e}")
        traceback.print_exc()
        return False

def test_provider_chain():
    """Prueba el sistema de provider chain"""
    print("\n=== Diagnóstico del Provider Chain ===\n")
    
    try:
        from provider_chain import provider_chain
        print("✅ Importación de provider_chain exitosa")
        
        # Intentar obtener un LLM
        print("\n🔍 Intentando obtener LLM...")
        llm = provider_chain.get_llm()
        print(f"✅ LLM obtenido: {type(llm).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en provider chain: {e}")
        traceback.print_exc()
        return False

def test_simple_llm_call():
    """Prueba una llamada simple al LLM"""
    print("\n=== Diagnóstico de Llamada LLM ===\n")
    
    try:
        from provider_chain import provider_chain
        
        # Obtener LLM
        llm = provider_chain.get_llm()
        print(f"✅ LLM obtenido: {type(llm).__name__}")
        
        # Hacer una llamada simple
        print("\n🔍 Realizando llamada de prueba...")
        response = llm.invoke("Di 'Hola mundo' en una sola palabra.")
        print(f"✅ Respuesta recibida: {response[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en llamada LLM: {e}")
        traceback.print_exc()
        return False

def test_structure_generation():
    """Prueba específica de generación de estructura"""
    print("\n=== Diagnóstico de Generación de Estructura ===\n")
    
    try:
        from structure import get_structure
        print("✅ Importación de get_structure exitosa")
        
        # Parámetros de prueba
        subject = "Una aventura simple"
        genre = "Fantasía"
        style = "Narrativo"
        profile = "Libro de prueba"
        
        print("\n🔍 Iniciando generación de estructura...")
        print("⚠️ Esto puede tomar tiempo...")
        
        title, framework, chapters = get_structure(subject, genre, style, profile)
        
        print(f"✅ Estructura generada exitosamente!")
        print(f"  Título: {title}")
        print(f"  Capítulos: {len(chapters)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en generación de estructura: {e}")
        traceback.print_exc()
        return False

def check_environment():
    """Verifica variables de entorno relevantes"""
    print("\n=== Diagnóstico de Variables de Entorno ===\n")
    
    relevant_vars = [
        "MODEL_TYPE", "SELECTED_MODEL",
        "OLLAMA_MODEL", "OLLAMA_API_BASE",
        "OPENAI_API_KEY", "OPENAI_MODEL",
        "GROQ_API_KEY", "GROQ_MODEL",
        "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"
    ]
    
    for var in relevant_vars:
        value = os.environ.get(var, "<no configurado>")
        # Ocultar claves API por seguridad
        if "API_KEY" in var and value != "<no configurado>":
            value = f"{value[:8]}..." if len(value) > 8 else "***"
        print(f"  {var}: {value}")

def main():
    """Ejecuta todos los diagnósticos"""
    print("🩺 DIAGNÓSTICO COMPLETO DEL SISTEMA")
    print("="*50)
    
    # Verificar entorno
    check_environment()
    
    # Pruebas secuenciales
    tests = [
        ("Provider Discovery", test_provider_discovery),
        ("Provider Chain", test_provider_chain),
        ("Llamada LLM Simple", test_simple_llm_call),
        ("Generación de Estructura", test_structure_generation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except KeyboardInterrupt:
            print(f"\n⚠️ Test {test_name} interrumpido por el usuario")
            results.append((test_name, False))
            break
        except Exception as e:
            print(f"❌ Error inesperado en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen
    print("\n" + "="*50)
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("="*50)
    
    for test_name, result in results:
        status = "✅ ÉXITO" if result else "❌ FALLO"
        print(f"{test_name:25} {status}")
    
    failed_tests = [name for name, result in results if not result]
    
    if not failed_tests:
        print("\n🎉 Todos los tests pasaron. El sistema debería funcionar correctamente.")
    else:
        print(f"\n⚠️ {len(failed_tests)} test(s) fallaron:")
        for test_name in failed_tests:
            print(f"  - {test_name}")
        print("\nEsto indica dónde está el problema específico.")

if __name__ == "__main__":
    main()