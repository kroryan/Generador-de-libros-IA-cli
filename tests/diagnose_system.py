#!/usr/bin/env python3
"""
Script de diagnóstico completo para el sistema de generación de libros con IA.
Verifica la conectividad y configuración de todos los proveedores LLM soportados.
"""

import sys
import os
import requests
import json
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple

# Agregar el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Cargar variables de entorno
load_dotenv()

class LLMDiagnostic:
    """Clase para diagnosticar la conectividad y configuración de todos los LLMs."""
    
    def __init__(self):
        self.results = {}
        self.supported_providers = [
            'ollama', 'openai', 'deepseek', 'groq', 'anthropic'
        ]
    
    def print_header(self, title: str):
        """Imprime un encabezado formateado."""
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    
    def print_section(self, title: str):
        """Imprime una sección formateada."""
        print(f"\n{'-'*40}")
        print(f" {title}")
        print(f"{'-'*40}")
    
    def check_environment_variables(self) -> Dict[str, str]:
        """Verifica todas las variables de entorno relacionadas con LLMs."""
        self.print_section("Variables de Entorno")
        
        env_vars = {}
        important_vars = [
            'MODEL_TYPE',
            'OLLAMA_API_BASE', 'OLLAMA_MODEL',
            'OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_API_BASE',
            'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_BASE',
            'GROQ_API_KEY', 'GROQ_MODEL', 'GROQ_API_BASE', 'GROQ_AVAILABLE_MODELS',
            'ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL', 'ANTHROPIC_API_BASE',
            'MODEL_CONTEXT_SIZE', 'PROVIDER_HEALTH_CHECK_ENABLED'
        ]
        
        for var in important_vars:
            value = os.environ.get(var)
            env_vars[var] = value
            # Ocultar claves API por seguridad
            display_value = value
            if value and "API_KEY" in var:
                display_value = f"{value[:10]}...{value[-5:] if len(value) > 15 else '***'}"
            status = "✅" if value else "❌"
            print(f"{status} {var}: {display_value if value else 'No definida'}")
        
        return env_vars
    
    def test_ollama_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión con Ollama."""
        self.print_section("Diagnóstico de Ollama")
        
        api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "gemma3:latest")
        
        print(f"API Base: {api_base}")
        print(f"Modelo configurado: {model}")
        
        try:
            # Test 1: Verificar que Ollama esté ejecutándose
            response = requests.get(f"{api_base}/api/tags", timeout=10)
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get('models', [])
                print(f"✅ Ollama conectado - {len(models)} modelos disponibles")
                
                model_names = [m['name'] for m in models]
                print("Modelos disponibles:")
                for model_name in model_names:
                    print(f"  • {model_name}")
                
                # Verificar si el modelo configurado existe
                if any(model in name for name in model_names):
                    print(f"✅ Modelo '{model}' encontrado")
                    
                    # Test 2: Probar generación simple
                    test_prompt = {
                        "model": model,
                        "prompt": "Responde solo 'Hola'",
                        "stream": False
                    }
                    
                    gen_response = requests.post(
                        f"{api_base}/api/generate", 
                        json=test_prompt, 
                        timeout=30
                    )
                    
                    if gen_response.status_code == 200:
                        result = gen_response.json()
                        print(f"✅ Generación exitosa: {result.get('response', '')[:50]}...")
                        return True, "Ollama funcionando correctamente"
                    else:
                        return False, f"Error en generación: {gen_response.status_code}"
                else:
                    return False, f"Modelo '{model}' no encontrado"
            else:
                return False, f"Error conectando a Ollama: {response.status_code}"
        
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {str(e)}"
    
    def test_openai_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión con OpenAI."""
        self.print_section("Diagnóstico de OpenAI")
        
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
        
        if not api_key:
            print("❌ OPENAI_API_KEY no configurada")
            return False, "API Key no configurada"
        
        print(f"API Base: {api_base}")
        print(f"Modelo: {model}")
        print(f"API Key: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else '***'}")
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test: Listar modelos
            response = requests.get(f"{api_base}/models", headers=headers, timeout=10)
            
            if response.status_code == 200:
                models = response.json().get('data', [])
                print(f"✅ OpenAI conectado - {len(models)} modelos disponibles")
                
                # Verificar si el modelo existe
                model_ids = [m['id'] for m in models]
                if model in model_ids:
                    print(f"✅ Modelo '{model}' disponible")
                    return True, "OpenAI funcionando correctamente"
                else:
                    print(f"⚠️  Modelo '{model}' no encontrado, pero conexión OK")
                    return True, "Conexión OK, verificar modelo"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
        
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {str(e)}"
    
    def test_deepseek_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión con DeepSeek."""
        self.print_section("Diagnóstico de DeepSeek")
        
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        
        if not api_key:
            print("❌ DEEPSEEK_API_KEY no configurada")
            return False, "API Key no configurada"
        
        print(f"API Base: {api_base}")
        print(f"Modelo: {model}")
        print(f"API Key: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else '***'}")
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test simple de chat
            test_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Responde solo 'Hola'"}],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{api_base}/chat/completions", 
                headers=headers, 
                json=test_data, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✅ DeepSeek funcionando: {content}")
                return True, "DeepSeek funcionando correctamente"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
        
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {str(e)}"
    
    def test_groq_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión con Groq."""
        self.print_section("Diagnóstico de Groq")
        
        api_key = os.environ.get("GROQ_API_KEY")
        api_base = os.environ.get("GROQ_API_BASE", "https://api.novita.ai/v3/openai")
        model = os.environ.get("GROQ_MODEL", "qwen/qwen3-8b-fp8")
        
        if not api_key:
            print("❌ GROQ_API_KEY no configurada")
            return False, "API Key no configurada"
        
        print(f"API Base: {api_base}")
        print(f"Modelo: {model}")
        print(f"API Key: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else '***'}")
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Test simple de chat
            test_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Responde solo 'Hola'"}],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{api_base}/chat/completions", 
                headers=headers, 
                json=test_data, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✅ Groq funcionando: {content}")
                return True, "Groq funcionando correctamente"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
        
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {str(e)}"
    
    def test_langchain_integration(self) -> Tuple[bool, str]:
        """Prueba la integración con LangChain."""
        self.print_section("Diagnóstico de Integración LangChain")
        
        try:
            from utils import get_llm_model, update_model_name
            from provider_registry import ProviderRegistry
            
            # Obtener el modelo configurado
            model_type = os.environ.get('MODEL_TYPE', 'ollama')
            print(f"Tipo de modelo configurado: {model_type}")
            
            # Probar registro de proveedores
            registry = ProviderRegistry()
            available_providers = registry.get_available_providers()
            provider_names = [p.name if hasattr(p, 'name') else str(p) for p in available_providers]
            print(f"Proveedores disponibles: {', '.join(provider_names)}")
            
            # Probar creación del LLM
            llm = get_llm_model()
            print(f"✅ LLM creado: {type(llm).__name__}")
            
            # Probar invocación simple
            print("Probando invocación...")
            response = llm.invoke("Responde solo 'Hola' en español")
            print(f"✅ Respuesta: {response}")
            
            return True, "Integración LangChain funcionando"
        
        except Exception as e:
            import traceback
            print(f"❌ Error: {str(e)}")
            traceback.print_exc()
            return False, f"Error en integración: {str(e)}"
    
    def test_web_server_endpoints(self) -> Tuple[bool, str]:
        """Prueba los endpoints del servidor web."""
        self.print_section("Diagnóstico de Endpoints Web")
        
        base_url = "http://localhost:5000"
        endpoints = [
            "/models",
            "/health",
        ]
        
        results = []
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    print(f"✅ {endpoint}: OK")
                    results.append(True)
                else:
                    print(f"❌ {endpoint}: Error {response.status_code}")
                    results.append(False)
            except requests.exceptions.RequestException as e:
                print(f"❌ {endpoint}: {str(e)}")
                results.append(False)
        
        success = all(results)
        return success, "Todos los endpoints funcionando" if success else "Algunos endpoints fallan"
    
    def run_full_diagnostic(self):
        """Ejecuta el diagnóstico completo del sistema."""
        self.print_header("DIAGNÓSTICO COMPLETO DEL SISTEMA")
        
        # 1. Variables de entorno
        env_vars = self.check_environment_variables()
        
        # 2. Pruebas de conectividad por proveedor
        model_type = os.environ.get('MODEL_TYPE', 'ollama')
        
        if model_type == 'ollama' or not model_type:
            success, msg = self.test_ollama_connection()
            self.results['ollama'] = (success, msg)
        
        if os.environ.get('OPENAI_API_KEY'):
            success, msg = self.test_openai_connection()
            self.results['openai'] = (success, msg)
        
        if os.environ.get('DEEPSEEK_API_KEY'):
            success, msg = self.test_deepseek_connection()
            self.results['deepseek'] = (success, msg)
        
        if os.environ.get('GROQ_API_KEY'):
            success, msg = self.test_groq_connection()
            self.results['groq'] = (success, msg)
        
        # 3. Integración LangChain
        success, msg = self.test_langchain_integration()
        self.results['langchain'] = (success, msg)
        
        # 4. Endpoints web
        success, msg = self.test_web_server_endpoints()
        self.results['web_server'] = (success, msg)
        
        # 5. Resumen final
        self.print_summary()
    
    def print_summary(self):
        """Imprime un resumen de todos los resultados."""
        self.print_header("RESUMEN DE DIAGNÓSTICO")
        
        total_tests = len(self.results)
        successful_tests = sum(1 for success, _ in self.results.values() if success)
        
        print(f"Tests ejecutados: {total_tests}")
        print(f"Tests exitosos: {successful_tests}")
        print(f"Tests fallidos: {total_tests - successful_tests}")
        
        print(f"\nDetalles:")
        for component, (success, message) in self.results.items():
            status = "✅" if success else "❌"
            print(f"{status} {component.upper()}: {message}")
        
        if successful_tests == total_tests:
            print(f"\n🎉 ¡TODOS LOS TESTS PASARON! El sistema está funcionando correctamente.")
        else:
            print(f"\n⚠️  Hay {total_tests - successful_tests} componente(s) con problemas.")
        
        print(f"\n{'='*60}")


def main():
    """Función principal."""
    diagnostic = LLMDiagnostic()
    diagnostic.run_full_diagnostic()


if __name__ == "__main__":
    main()