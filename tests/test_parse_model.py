#!/usr/bin/env python3
import sys
import os
sys.path.append('src')

print("=== Debug de parse_model_string ===")

from utils import parse_model_string

test_cases = [
    "ollama:gemma3:latest",
    "openai:gpt-4",
    "groq:llama3-8b-8192",
    "gemma3:latest",
    "llama3"
]

for test_case in test_cases:
    provider, model_name = parse_model_string(test_case)
    print(f"  '{test_case}' -> provider='{provider}', model_name='{model_name}'")

print("Test completado")