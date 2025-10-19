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

print("=== Test con Parámetros Exactos de la App ===")

from provider_chain import provider_chain
from utils import ColoredStreamingCallbackHandler

print("1. Probando con parámetros exactos de utils.py...")
try:
    # Parámetros exactos como en utils.py
    common_params = {
        "temperature": 0.7,
        "streaming": True,
        "callbacks": [ColoredStreamingCallbackHandler()]
    }
    
    client = provider_chain.get_client(**common_params)
    
    if client:
        print(f"  ✓ Cliente creado: {type(client)}")
        print(f"  - Modelo: {getattr(client, 'model', 'N/A')}")
        
        # Probar invocación como en la app
        print("2. Probando invocación exacta...")
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        # Crear prompt como en la app
        prompt_template = """Genera un título atractivo y original para esta novela de fantasía y ciencia ficción.
    El título debe capturar la esencia de la historia y ser memorable.
    Devuelve solo el título, sin explicaciones adicionales.
    IMPORTANTE: El título debe estar EXCLUSIVAMENTE en español. No uses palabras en otros idiomas.

    Tema del libro: El tema del libro es una aventura épica que combina fantasía y ciencia ficción.
    Género del libro: Fantasía y Ciencia Ficción
    Estilo: Narrativo-Épico-Imaginativo

    Título:"""
        
        prompt = PromptTemplate(
            input_variables=[],
            template=prompt_template
        )
        
        chain = LLMChain(
            llm=client,
            prompt=prompt,
            verbose=True
        )
        
        result = chain({})
        print(f"  ✓ Resultado: {result}")
        
    else:
        print("  ✗ No se pudo crear cliente")
        
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")