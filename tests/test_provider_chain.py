#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

print("=== Test del ProviderChain ===")

print("1. Importando dependencias...")
from provider_chain import ProviderChain, ProviderRequest
from provider_registry import provider_registry

print("2. Configurando registry...")
provider_registry.discover_providers()
providers = provider_registry.list_providers()
print(f"  Proveedores disponibles: {[p.name for p in providers]}")

print("3. Creando ProviderChain...")
try:
    chain = ProviderChain()
    print("  ✓ ProviderChain creado")
except Exception as e:
    print(f"  ✗ Error creando chain: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("4. Creando ProviderRequest...")
try:
    request = ProviderRequest(
        common_params={"temperature": 0.7},
        exclude_providers=[]
    )
    print("  ✓ ProviderRequest creado")
except Exception as e:
    print(f"  ✗ Error creando request: {e}")
    exit(1)

print("5. Obteniendo LLM a través del chain...")
try:
    llm = chain.get_client(exclude=[], temperature=0.7)
    if llm:
        print("  ✓ LLM obtenido exitosamente")
        print(f"  Tipo: {type(llm)}")
    else:
        print("  ✗ No se pudo obtener LLM (retornó None)")
        exit(1)
except Exception as e:
    print(f"  ✗ Error obteniendo LLM: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("6. Probando consulta a través del chain...")
try:
    response = llm.invoke("Responde únicamente 'Hola desde chain'")
    print(f"  ✓ Respuesta: {response.content}")
except Exception as e:
    print(f"  ✗ Error en consulta: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")