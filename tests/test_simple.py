#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

print("=== Test Simple ===")

print("1. Importando provider_registry...")
try:
    from provider_registry import provider_registry
    print("  ✓ provider_registry importado")
except Exception as e:
    print(f"  ✗ Error importando provider_registry: {e}")
    exit(1)

print("2. Verificando configuración de Ollama...")
try:
    config = provider_registry.get_provider("ollama")
    if config:
        print(f"  ✓ Configuración encontrada: {config.model}")
    else:
        print("  ✗ No se encontró configuración")
except Exception as e:
    print(f"  ✗ Error obteniendo configuración: {e}")
    exit(1)

print("3. Importando ProviderChain...")
try:
    from provider_chain import ProviderChain
    print("  ✓ ProviderChain importado")
except Exception as e:
    print(f"  ✗ Error importando ProviderChain: {e}")
    exit(1)

print("4. Creando instancia de ProviderChain...")
try:
    chain = ProviderChain()
    print("  ✓ Chain creado")
except Exception as e:
    print(f"  ✗ Error creando chain: {e}")
    exit(1)

print("Test completado sin colgarse")