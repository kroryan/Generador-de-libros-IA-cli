#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

print("=== Test de Cliente Ollama Directo ===")

print("1. Verificando instalación de langchain_community...")
try:
    from langchain_community.chat_models import ChatOllama
    print("  ✓ ChatOllama importado correctamente")
except ImportError as e:
    print(f"  ✗ Error importando ChatOllama: {e}")
    exit(1)

print("2. Obteniendo configuración...")
from provider_registry import provider_registry
provider_registry.discover_providers()
config = provider_registry.get_provider("ollama")

if not config:
    print("  ✗ No se encontró configuración de Ollama")
    exit(1)

print(f"  ✓ Configuración: {config.model} en {config.api_base}")

print("3. Creando cliente Ollama...")
try:
    ollama_params = {
        "model": config.model,
        "base_url": config.api_base,
        "top_k": 50,
        "top_p": 0.9,
        "repeat_penalty": 1.1
    }
    
    print(f"  Parámetros: {ollama_params}")
    client = ChatOllama(**ollama_params)
    print("  ✓ Cliente creado exitosamente")
    
except Exception as e:
    print(f"  ✗ Error creando cliente: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("4. Probando consulta simple...")
try:
    response = client.invoke("Responde únicamente 'Hola'")
    print(f"  ✓ Respuesta: {response.content}")
    
except Exception as e:
    print(f"  ✗ Error en consulta: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")