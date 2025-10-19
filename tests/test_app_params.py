#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

print("=== Test de Parámetros Ollama ===")

from provider_registry import provider_registry
from provider_chain import ProviderChain, ProviderRequest

# Configurar discovery
provider_registry.discover_providers()

print("1. Probando parámetros como en la app...")
try:
    from utils import ColoredStreamingCallbackHandler
    
    chain = ProviderChain()
    client = chain.get_client(
        exclude=[],
        temperature=0.7,
        callbacks=[ColoredStreamingCallbackHandler()]
    )
    
    if client:
        print(f"  ✓ Cliente creado: {type(client)}")
        print(f"  - Modelo: {client.model}")
        print(f"  - Base URL: {getattr(client, 'base_url', 'N/A')}")
        print(f"  - Temperature: {getattr(client, 'temperature', 'N/A')}")
        
        # Probar invocación
        print("2. Probando invocación...")
        response = client.invoke("Di solo 'Hola'")
        print(f"  ✓ Respuesta: {response.content}")
        
    else:
        print("  ✗ No se pudo crear cliente")
        
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")