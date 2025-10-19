#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

from dotenv import load_dotenv
load_dotenv()

print("=== Debug de Variables de Entorno ===")

print("1. Estado inicial después de load_dotenv():")
print(f"  OLLAMA_MODEL = '{os.environ.get('OLLAMA_MODEL', 'NOT_SET')}'")
print(f"  SELECTED_MODEL = '{os.environ.get('SELECTED_MODEL', 'NOT_SET')}'")

print("2. Simulando update_model_name('ollama:gemma3:latest'):")
from utils import update_model_name
update_model_name('ollama:gemma3:latest')

print("3. Estado después de update_model_name:")
print(f"  OLLAMA_MODEL = '{os.environ.get('OLLAMA_MODEL', 'NOT_SET')}'")
print(f"  SELECTED_MODEL = '{os.environ.get('SELECTED_MODEL', 'NOT_SET')}'")

print("4. Probando discovery del registry:")
from provider_registry import provider_registry
# Limpiar estado
provider_registry._providers = {}
provider_registry._discovered = False

provider_registry.discover_providers()

config = provider_registry.get_provider("ollama")
if config:
    print(f"  config.model = '{config.model}'")
else:
    print("  No se encontró config de Ollama")

print("Test completado")