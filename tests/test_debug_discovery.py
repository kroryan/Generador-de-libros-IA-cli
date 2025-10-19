#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

# IMPORTANTE: Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

print("=== Debug Detallado del Discovery ===")

# Configurar logging para mostrar DEBUG
import logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

print("1. Verificando variables de entorno...")
upper_name = "OLLAMA"
api_key = os.environ.get(f"{upper_name}_API_KEY", "")
api_base = os.environ.get(f"{upper_name}_API_BASE", "")
model = os.environ.get(f"{upper_name}_MODEL", "")

print(f"  OLLAMA_API_KEY = '{api_key}'")
print(f"  OLLAMA_API_BASE = '{api_base}'")
print(f"  OLLAMA_MODEL = '{model}'")

print("2. Creando ProviderConfig...")
from provider_registry import ProviderConfig

config = ProviderConfig(
    name="ollama",
    api_key=api_key,
    api_base=api_base,
    model=model,
    priority=4
)

print(f"  config.name = '{config.name}'")
print(f"  config.api_key = '{config.api_key}'")
print(f"  config.api_base = '{config.api_base}'")
print(f"  config.model = '{config.model}'")

print("3. Verificando is_configured...")
is_conf = config.is_configured()
print(f"  is_configured() = {is_conf}")

# Verificar condición específica para Ollama
ollama_condition = bool(config.api_base and config.model)
print(f"  Condición Ollama (api_base and model) = {ollama_condition}")
print(f"  bool(api_base) = {bool(config.api_base)}")
print(f"  bool(model) = {bool(config.model)}")

print("4. Simulando discovery completo...")
from provider_registry import provider_registry

# Limpiar estado
provider_registry._providers = {}
provider_registry._discovered = False

provider_registry.discover_providers()

providers = provider_registry.list_providers()
print(f"  Proveedores encontrados: {providers}")

print("Test completado")