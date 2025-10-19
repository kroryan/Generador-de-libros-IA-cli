#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)-8s %(name)-20s | %(message)s',
    datefmt='%H:%M:%S'
)

print("=== Test Debug del ProviderChain ===")

print("1. Configurando registry...")
from provider_registry import provider_registry
provider_registry.discover_providers()
providers = provider_registry.list_providers()
print(f"  Proveedores disponibles: {[p.name for p in providers]}")

print("2. Probando OllamaProviderHandler directamente...")
from provider_chain import OllamaProviderHandler, ProviderRequest

try:
    handler = OllamaProviderHandler()
    request = ProviderRequest(
        exclude_providers=[],
        common_params={"temperature": 0.7}
    )
    
    print(f"  can_handle: {handler.can_handle(request)}")
    
    result = handler._handle_internal(request)
    print(f"  Resultado: {result}")
    print(f"  Tipo: {type(result)}")
    
    if result:
        response = result.invoke("Di 'Hola'")
        print(f"  Respuesta: {response.content}")
    
except Exception as e:
    print(f"  ✗ Error en handler: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")