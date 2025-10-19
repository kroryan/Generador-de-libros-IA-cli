#!/usr/bin/env python3
"""
Debug específico del ProviderRegistry para identificar el problema exacto.
"""

import os
import sys

# Cargar dotenv explícitamente
from dotenv import load_dotenv
load_dotenv()

# Configurar logging para debug
import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

# Agregar directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from provider_registry import ProviderRegistry, ProviderConfig

def debug_provider_discovery():
    """Debug específico del proceso de discovery"""
    print("🔍 DEBUG DETALLADO DEL PROVIDER DISCOVERY")
    print("="*50)
    
    # Variables de entorno relevantes
    print("📋 Variables de entorno cargadas:")
    for var in ["MODEL_TYPE", "OLLAMA_MODEL", "OLLAMA_API_BASE", "OLLAMA_API_KEY"]:
        value = os.environ.get(var, "NOT_SET")
        print(f"  {var}: {value}")
    
    # Simular discovery manual para Ollama
    print("\n🧪 Simulando discovery manual para Ollama:")
    provider_name = "ollama"
    upper_name = provider_name.upper()
    defaults = {
        "api_base": "http://localhost:11434",
        "client_class": "ChatOllama"
    }
    
    # Obtener valores como lo hace el código
    api_key = os.environ.get(f"{upper_name}_API_KEY", "")
    api_base = os.environ.get(f"{upper_name}_API_BASE", defaults.get("api_base", ""))
    model = os.environ.get(f"{upper_name}_MODEL", "")
    
    print(f"  api_key obtenido: '{api_key}'")
    print(f"  api_base obtenido: '{api_base}'")
    print(f"  model obtenido: '{model}'")
    
    # Crear configuración
    config = ProviderConfig(
        name=provider_name,
        api_key=api_key,
        api_base=api_base,
        model=model,
        priority=1,
        health_check=None,
        client_class=defaults.get("client_class")
    )
    
    print(f"\n📦 Configuración creada:")
    print(f"  name: {config.name}")
    print(f"  api_key: '{config.api_key}'")
    print(f"  api_base: '{config.api_base}'")
    print(f"  model: '{config.model}'")
    
    # Verificar is_configured
    is_configured = config.is_configured()
    print(f"\n✅ is_configured(): {is_configured}")
    
    # Debug individual de condiciones
    if config.name.lower() == "ollama":
        print(f"  Es Ollama: True")
        print(f"  bool(api_base): {bool(config.api_base)} (api_base='{config.api_base}')")
        print(f"  bool(model): {bool(config.model)} (model='{config.model}')")
        print(f"  Condición final: bool(api_base and model) = {bool(config.api_base and config.model)}")
    
    return is_configured

def test_full_registry():
    """Prueba el registry completo"""
    print("\n🏭 Probando ProviderRegistry completo:")
    print("-" * 40)
    
    registry = ProviderRegistry()
    
    # Antes del discovery
    print(f"Antes del discovery: {len(registry._providers)} proveedores")
    
    # Ejecutar discovery con debug paso a paso
    print("🔍 Iniciando discovery paso a paso...")
    
    # Verificar el lock
    print("📍 Checkpoint 1: Verificando lock...")
    with registry._lock:
        print("📍 Checkpoint 2: Lock adquirido")
        
        if registry._discovered:
            print("📍 Ya descubierto, saliendo...")
            return
        
        print("📍 Checkpoint 3: Comenzando discovery real...")
        
        # Proveedores conocidos
        known_providers = {
            "ollama": {
                "api_base": "http://localhost:11434",
                "client_class": "ChatOllama"
            }
        }
        
        print("📍 Checkpoint 4: Probando discovery de Ollama...")
        
        try:
            # Descubrir solo Ollama para empezar
            registry._discover_provider("ollama", known_providers["ollama"])
            print("📍 Checkpoint 5: _discover_provider completado")
        except Exception as e:
            print(f"❌ Error en _discover_provider: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"📍 Checkpoint 6: Proveedores después de Ollama: {len(registry._providers)}")
        
        try:
            registry._discovered = True
            print("📍 Checkpoint 7: Marcado como descubierto")
        except Exception as e:
            print(f"❌ Error marcando como descubierto: {e}")
            return False
    
    print("📍 Checkpoint 8: Saliendo del lock")
    
    # Después del discovery
    print(f"Después del discovery: {len(registry._providers)} proveedores")
    
    # Listar todos los proveedores
    if registry._providers:
        print("\nProveedores encontrados:")
        for name, config in registry._providers.items():
            configured = config.is_configured()
            print(f"  {name}: configured={configured}, model='{config.model}'")
    else:
        print("No se encontraron proveedores")
    
    return len(registry._providers) > 0

def main():
    """Ejecuta todos los debugs"""
    print("🐛 DEBUG COMPLETO DEL SISTEMA DE PROVEEDORES\n")
    
    # Debug manual
    manual_ok = debug_provider_discovery()
    
    # Debug del registry
    registry_ok = test_full_registry()
    
    print("\n" + "="*50)
    print("📊 RESUMEN DEL DEBUG")
    print("="*50)
    print(f"Discovery manual: {'✅ OK' if manual_ok else '❌ FALLO'}")
    print(f"Registry completo: {'✅ OK' if registry_ok else '❌ FALLO'}")
    
    if not manual_ok:
        print("\n⚠️ El problema está en la configuración individual")
    elif not registry_ok:
        print("\n⚠️ El problema está en el proceso de discovery del registry")
    else:
        print("\n🎉 Todo funciona correctamente!")

if __name__ == "__main__":
    main()