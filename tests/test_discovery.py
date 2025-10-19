#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

print("=== Test con Discovery Forzado ===")

print("1. Importando provider_registry...")
from provider_registry import provider_registry

print("2. Forzando discovery de proveedores...")
try:
    provider_registry.discover_providers()
    print("  ✓ Discovery ejecutado")
except Exception as e:
    print(f"  ✗ Error en discovery: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("3. Verificando proveedores disponibles...")
try:
    providers = provider_registry.list_providers()
    print(f"  ✓ Proveedores encontrados: {providers}")
except Exception as e:
    print(f"  ✗ Error listando proveedores: {e}")
    exit(1)

print("4. Verificando configuración de Ollama...")
try:
    config = provider_registry.get_provider("ollama")
    if config:
        print(f"  ✓ Configuración encontrada:")
        print(f"    - Modelo: {config.model}")
        print(f"    - API Base: {config.api_base}")
        print(f"    - Configurado: {config.is_configured()}")
    else:
        print("  ✗ No se encontró configuración de Ollama")
except Exception as e:
    print(f"  ✗ Error obteniendo configuración: {e}")

print("Test completado")