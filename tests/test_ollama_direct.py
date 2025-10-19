#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

import logging
from provider_registry import provider_registry
from provider_chain import ProviderChain, ProviderRequest

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)-8s %(name)-20s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def test_ollama_direct():
    """Prueba directa del proveedor Ollama"""
    print("=== Test directo de Ollama ===")
    
    # 1. Verificar configuración
    print("\n1. Verificando configuración de Ollama...")
    config = provider_registry.get_provider("ollama")
    if config:
        print(f"  ✓ Configuración encontrada:")
        print(f"    - Modelo: {config.model}")
        print(f"    - API Base: {config.api_base}")
        print(f"    - Configurado: {config.is_configured()}")
    else:
        print("  ✗ No se encontró configuración de Ollama")
        return
    
    # 2. Probar importación de ChatOllama
    print("\n2. Probando importación de ChatOllama...")
    try:
        from langchain_community.chat_models import ChatOllama
        print("  ✓ ChatOllama importado correctamente")
    except Exception as e:
        print(f"  ✗ Error importando ChatOllama: {e}")
        return
    
    # 3. Crear cliente directamente
    print("\n3. Creando cliente Ollama directamente...")
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
        
        # 4. Probar una consulta simple
        print("\n4. Probando consulta simple...")
        response = client.invoke("Di 'hola'")
        print(f"  ✓ Respuesta: {response.content}")
        
    except Exception as e:
        print(f"  ✗ Error creando o usando cliente: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Probar a través del chain
    print("\n5. Probando a través del ProviderChain...")
    try:
        chain = ProviderChain()
        request = ProviderRequest(
            common_params={"temperature": 0.7},
            exclude_providers=[]
        )
        
        llm = chain.get_llm(request)
        if llm:
            print("  ✓ Cliente obtenido desde chain")
            response = llm.invoke("Di 'hola desde chain'")
            print(f"  ✓ Respuesta: {response.content}")
        else:
            print("  ✗ No se pudo obtener cliente desde chain")
            
    except Exception as e:
        print(f"  ✗ Error usando chain: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ollama_direct()