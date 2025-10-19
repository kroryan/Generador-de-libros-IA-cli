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

print("=== Test Debug Chain Completa ===")

print("1. Configurando registry...")
from provider_registry import provider_registry
provider_registry.discover_providers()

print("2. Probando cada handler individualmente...")
from provider_chain import (
    GroqProviderHandler, OpenAIProviderHandler, DeepSeekProviderHandler,
    AnthropicProviderHandler, OllamaProviderHandler, CustomProviderHandler,
    ProviderRequest
)

request = ProviderRequest(
    exclude_providers=[],
    common_params={"temperature": 0.7}
)

handlers = [
    ("Groq", GroqProviderHandler()),
    ("OpenAI", OpenAIProviderHandler()),
    ("DeepSeek", DeepSeekProviderHandler()),
    ("Anthropic", AnthropicProviderHandler()),
    ("Ollama", OllamaProviderHandler()),
    ("Custom", CustomProviderHandler())
]

for name, handler in handlers:
    print(f"  {name}: can_handle = {handler.can_handle(request)}")
    if handler.can_handle(request):
        try:
            result = handler._handle_internal(request)
            print(f"    -> Resultado: {type(result) if result else 'None'}")
            if result:
                break
        except Exception as e:
            print(f"    -> Error: {e}")

print("3. Probando cadena completa...")
from provider_chain import ProviderChain

try:
    chain = ProviderChain()
    client = chain._chain.handle(request)
    print(f"  Resultado de la cadena: {type(client) if client else 'None'}")
except Exception as e:
    print(f"  Error en cadena: {e}")
    import traceback
    traceback.print_exc()

print("Test completado")