from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import sys
import time
import re
import os
import json
import requests

# Importar nuevos módulos de infraestructura
from retry_strategy import RetryStrategy, with_retry
from circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, with_circuit_breaker
from emergency_prompts import emergency_prompts
from provider_chain import provider_chain
from logging_config import get_logger, print_progress
from model_profiles import model_profile_manager, detect_model_size as new_detect_model_size

# Logger para este módulo
logger = get_logger("utils")

# Códigos ANSI para colores
YELLOW = "\033[93m"
WHITE = "\033[97m"
PURPLE = "\033[95m"
RESET = "\033[0m"

# Configuración de modelo seleccionado
SELECTED_MODEL = os.environ.get("SELECTED_MODEL", "")

# Carga los proveedores disponibles desde el archivo .env
def load_providers_config():
    try:
        providers_json = os.environ.get("AVAILABLE_PROVIDERS", "{}")
        return json.loads(providers_json)
    except json.JSONDecodeError:
        print("\n> Error al cargar la configuración de proveedores del archivo .env. Usando valores predeterminados.")
        return {
            "ollama": ["llama2"],
            "openai": ["gpt-3.5-turbo", "gpt-4"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"]
        }

# Proveedores disponibles desde el archivo .env
AVAILABLE_PROVIDERS = load_providers_config()

# Función para obtener la configuración de un proveedor específico
def get_provider_config(provider_name):
    """Obtiene la configuración de un proveedor desde las variables de entorno"""
    provider = provider_name.upper()
    
    # Buscar configuraciones específicas del proveedor
    api_key = os.environ.get(f"{provider}_API_KEY", "")
    api_base = os.environ.get(f"{provider}_API_BASE", "")
    default_model = os.environ.get(f"{provider}_MODEL", "")
    
    # Si no hay configuración específica y es un proveedor estándar, usar configuraciones anteriores para compatibilidad
    if not api_key and not api_base and provider in ["OPENAI", "DEEPSEEK", "OLLAMA", "ANTHROPIC"]:
        if provider == "OPENAI":
            api_key = os.environ.get("OPENAI_API_KEY", "")
            api_base = os.environ.get("OPENAI_API_BASE", "")
            default_model = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
        elif provider == "DEEPSEEK":
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
            default_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        elif provider == "OLLAMA":
            api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
            default_model = os.environ.get("OLLAMA_MODEL", "llama2")
        elif provider == "ANTHROPIC":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            api_base = os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1")
            default_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-opus")
    
    return {
        "api_key": api_key,
        "api_base": api_base,
        "default_model": default_model
    }

def get_available_models():
    """
    Detecta automáticamente todos los modelos disponibles en todas las APIs configuradas.
    Devuelve una lista de diccionarios con información sobre cada modelo.
    """
    models = []
    
    # Recorrer todos los proveedores configurados en AVAILABLE_PROVIDERS
    for provider, provider_models in AVAILABLE_PROVIDERS.items():
        # Obtener la configuración del proveedor
        config = get_provider_config(provider)
        
        # Si hay modelos definidos para este proveedor
        if provider_models and isinstance(provider_models, list):
            for model in provider_models:
                models.append({
                    "provider": provider,
                    "name": model,
                    "display_name": f"{provider.capitalize()}: {model}",
                    "value": f"{provider}:{model}"  # Formato: "proveedor:modelo"
                })
    
    # Si no se encontró ningún modelo, añadir uno predeterminado
    if not models:
        models.append({
            "provider": "ollama",
            "name": "llama2",
            "display_name": "Ollama: llama2 (default)",
            "value": "ollama:llama2"
        })
    
    return models

# Función para consultar Ollama si está disponible
def get_ollama_models():
    """Obtiene la lista de modelos disponibles en Ollama"""
    try:
        config = get_provider_config("ollama")
        api_base = config["api_base"].rstrip("/")
        response = requests.get(f"{api_base}/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return sorted([model['name'] for model in models])
        return []
    except Exception:
        return []

def check_ollama_available():
    """Verifica si Ollama está disponible y funcionando"""
    try:
        config = get_provider_config("ollama")
        api_base = config["api_base"].rstrip("/")
        response = requests.get(f"{api_base}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def parse_model_string(model_string):
    """
    Parsea una cadena de modelo en formato 'provider:model_name' para obtener el proveedor y el nombre del modelo.
    Si no hay prefijo de proveedor, asume que es Ollama.
    """
    # Proveedores conocidos que usan el prefijo provider:model
    known_providers = ["openai", "deepseek", "groq", "anthropic", "ollama"]
    
    if ":" in model_string:
        parts = model_string.split(":", 1)
        if parts[0].lower() in known_providers:
            # Es un proveedor conocido como openai:gpt-4 u ollama:gemma3:latest
            return parts[0].lower(), parts[1]
        else:
            # Es un modelo de Ollama con ":" en su nombre como hf.co/.../model:Q8_0
            return "ollama", model_string
    else:
        # Sin prefijo, asumimos que es Ollama
        return "ollama", model_string

def update_model_name(model_string):
    """
    Actualiza el modelo a utilizar basándose en una cadena que puede incluir el proveedor.
    Formato: 'provider:model_name' o simplemente 'model_name' (default a Ollama)
    """
    os.environ["SELECTED_MODEL"] = model_string
    provider, model_name = parse_model_string(model_string)
    # Actualizar la variable de entorno para ese proveedor
    os.environ[f"{provider.upper()}_MODEL"] = model_name
    print(f"\n> Modelo actualizado a {provider.capitalize()}: {model_name}")

def update_model_type(model_type, model_name=None):
    """Actualiza el tipo de modelo a utilizar"""
    os.environ["SELECTED_MODEL"] = f"{model_type}:{model_name}" if model_name else model_type
    print(f"\n> Tipo de modelo actualizado a: {model_type}" + (f" ({model_name})" if model_name else ""))

def extract_content_from_llm_response(response):
    """Extrae el contenido de texto de diferentes tipos de respuestas LLM"""
    try:
        if hasattr(response, 'content'):  # Para AIMessage, HumanMessage, etc.
            return response.content
        elif isinstance(response, dict) and "text" in response:  # Para diccionarios con clave 'text'
            return response["text"]
        elif isinstance(response, str):  # Para respuestas en texto plano
            return response
        else:  # Para cualquier otro tipo
            # Convertir explícitamente a string y verificar que no sea None
            result = str(response) if response is not None else ""
            return result
    except Exception as e:
        print_progress(f"Error al extraer contenido de respuesta LLM: {str(e)}")
        # En caso de cualquier error, devolver una cadena vacía en lugar de propagar el error
        return ""

class ColoredStreamingCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self):
        super().__init__()
        self.in_think_block = False
        self.current_text = ""

    def on_llm_new_token(self, token: str, **kwargs):
        # Detectar inicio y fin de bloques de pensamiento
        if "<think>" in token:
            self.in_think_block = True
            sys.stdout.write(YELLOW)
        elif "</think>" in token:
            self.in_think_block = False
            sys.stdout.write(WHITE)
            # Almacenar el pensamiento completo para mostrarlo en púrpura después
            self.current_text += token
            return

        # Escribir el token con el color apropiado
        sys.stdout.write(token)
        sys.stdout.flush()
        self.current_text += token

    def on_llm_end(self, *args, **kwargs):
        # Mostrar los pensamientos en púrpura al final
        cleaned = self.current_text
        think_blocks = re.finditer(r'<think>.*?</think>', cleaned, re.DOTALL)
        for block in think_blocks:
            original = block.group(0)
            colored = original.replace('<think>', f'{PURPLE}<think>').replace('</think>', f'</think>{RESET}')
            cleaned = cleaned.replace(original, colored)
        self.current_text = ""

def print_progress(message):
    print(f"\n{WHITE}> {message}{RESET}")
    sys.stdout.flush()

def clean_think_tags(text):
    """
    Elimina las cadenas de pensamiento del modelo en varios formatos posibles.
    
    NOTA: Esta función ahora usa el sistema unificado de limpieza de texto.
    Mantenida por compatibilidad con código existente.
    """
    from text_cleaning import clean_think_tags as _clean_think_tags
    return _clean_think_tags(text)

def get_llm_model(callbacks=None):
    """
    Obtiene un modelo LLM usando el nuevo sistema de proveedores unificado.
    Reemplaza la lógica compleja anterior con un sistema limpio y mantenible.
    """
    logger.info("Obteniendo modelo LLM usando sistema de proveedores unificado")
    
    # Parámetros comunes para todos los proveedores
    common_params = {
        "temperature": 0.7,
        "streaming": True,
    }
    
    # Agregar callbacks si se proporcionan
    if callbacks is not None:
        common_params["callbacks"] = callbacks
    
    try:
        # Usar la nueva cadena de proveedores
        client = provider_chain.get_client(**common_params)
        logger.info("Cliente LLM creado exitosamente")
        return client
        
    except Exception as e:
        logger.error(f"Error obteniendo modelo LLM: {e}")
        raise

def get_provider_model(provider, model_name, common_params):
    """Función helper para obtener el modelo de un proveedor específico"""
    
    # Para OpenAI
    if provider == "openai":
        try:
            openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            openai_api_base = os.environ.get("OPENAI_API_BASE", "")
            
            if not openai_api_key:
                print_progress("API key de OpenAI no encontrada. Cambiando a otro modelo disponible.")
                provider, model_name = fallback_to_available_provider(exclude=["openai"])
                return get_provider_model(provider, model_name, common_params)
            
            # Parámetros específicos para OpenAI
            openai_params = {**common_params, "model": model_name}
            
            # Añadir API key si está disponible
            openai_params["api_key"] = openai_api_key
            
            # Si se ha especificado una API base alternativa
            if openai_api_base and openai_api_base.strip():
                openai_params["base_url"] = openai_api_base
                print_progress(f"Utilizando API compatible con OpenAI: {model_name} (Base: {openai_api_base})")
            else:
                print_progress(f"Utilizando modelo OpenAI: {model_name}")
                
            return ChatOpenAI(**openai_params)
        except Exception as e:
            print_progress(f"Error al inicializar OpenAI: {str(e)}")
            provider, model_name = fallback_to_available_provider(exclude=["openai"])
            return get_provider_model(provider, model_name, common_params)
    
    # Para DeepSeek
    if provider == "deepseek":
        try:
            deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            deepseek_api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
            
            if not deepseek_api_key:
                print_progress("API key de DeepSeek no encontrada. Cambiando a otro modelo disponible.")
                provider, model_name = fallback_to_available_provider(exclude=["deepseek"])
                return get_provider_model(provider, model_name, common_params)
            
            print_progress(f"Utilizando modelo DeepSeek: {model_name}")
            return ChatOpenAI(
                api_key=deepseek_api_key,
                base_url=deepseek_api_base,
                model=model_name,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar DeepSeek: {str(e)}")
            provider, model_name = fallback_to_available_provider(exclude=["deepseek"])
            return get_provider_model(provider, model_name, common_params)
    
    # Para modelos de Anthropic
    if provider == "anthropic":
        try:
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            
            if not anthropic_api_key:
                print_progress("API key de Anthropic no encontrada. Cambiando a otro modelo disponible.")
                provider, model_name = fallback_to_available_provider(exclude=["anthropic"])
                return get_provider_model(provider, model_name, common_params)
            
            print_progress(f"Utilizando modelo Anthropic: {model_name}")
            # Anthropic requiere configuración especial
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name,
                anthropic_api_key=anthropic_api_key,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar Anthropic: {str(e)}. Es posible que necesites instalar langchain_anthropic.")
            provider, model_name = fallback_to_available_provider(exclude=["anthropic"])
            return get_provider_model(provider, model_name, common_params)
    
    # Para cualquier otro proveedor personalizado (compatible con OpenAI)
    try:
        # Buscar configuración para este proveedor
        provider_api_key = os.environ.get(f"{provider.upper()}_API_KEY", "")
        provider_api_base = os.environ.get(f"{provider.upper()}_API_BASE", "")
        
        if not provider_api_key or not provider_api_base:
            print_progress(f"Configuración incompleta para {provider}. Cambiando a otro modelo disponible.")
            provider, model_name = fallback_to_available_provider(exclude=[provider])
            return get_provider_model(provider, model_name, common_params)
        
        print_progress(f"Utilizando modelo personalizado {provider.capitalize()}: {model_name}")
        return ChatOpenAI(
            model=model_name,
            api_key=provider_api_key,
            base_url=provider_api_base,
            **common_params
        )
    except Exception as e:
        print_progress(f"Error al inicializar proveedor personalizado {provider}: {str(e)}")
        provider, model_name = fallback_to_available_provider(exclude=[provider])
        return get_provider_model(provider, model_name, common_params)

def fallback_to_available_provider(exclude=None):
    """Encuentra un proveedor disponible para usar como fallback"""
    if exclude is None:
        exclude = []
    
    # Ordenar proveedores por prioridad
    # 1. Groq (rápido y buena calidad)
    if os.environ.get("GROQ_API_KEY", "") and "groq" not in exclude and os.environ.get("GROQ_MODEL", ""):
        return "groq", os.environ["GROQ_MODEL"]
    
    # 2. OpenAI (estable)
    if os.environ.get("OPENAI_API_KEY", "") and "openai" not in exclude and os.environ.get("OPENAI_MODEL", ""):
        return "openai", os.environ["OPENAI_MODEL"]
    
    # 3. DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY", "") and "deepseek" not in exclude and os.environ.get("DEEPSEEK_MODEL", ""):
        return "deepseek", os.environ["DEEPSEEK_MODEL"]
    
    # 4. Anthropic
    if os.environ.get("ANTHROPIC_API_KEY", "") and "anthropic" not in exclude and os.environ.get("ANTHROPIC_MODEL", ""):
        return "anthropic", os.environ["ANTHROPIC_MODEL"]
    
    # 5. Ollama como último recurso
    if "ollama" not in exclude and check_ollama_available():
        if os.environ.get("OLLAMA_MODEL", ""):
            return "ollama", os.environ["OLLAMA_MODEL"]
        else:
            return "ollama", "llama2" # modelo por defecto
    
    # Buscar proveedores personalizados
    for key in os.environ:
        if key.endswith("_API_KEY") and key not in ["OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"]:
            provider = key.replace("_API_KEY", "").lower()
            model = os.environ.get(f"{provider.upper()}_MODEL", "")
            if provider not in exclude and model:
                return provider, model
    
    # Si todo lo demás falla
    raise ValueError("No se pudo encontrar ningún proveedor de LLM disponible. Configure al menos un proveedor en el archivo .env")

def detect_model_size(llm):
    """
    Detecta automáticamente el tamaño del modelo usando el nuevo sistema de perfiles.
    Reemplaza la detección frágil basada en strings.
    
    Args:
        llm: Instancia del modelo de lenguaje
        
    Returns:
        str: Clasificación de tamaño ("small", "standard", "large")
    """
    try:
        logger.info("Detectando tamaño de modelo con sistema de perfiles")
        
        # Usar la nueva función basada en perfiles
        result = new_detect_model_size(llm)
        
        logger.info(f"Tamaño detectado: {result}")
        return result
        
    except Exception as e:
        logger.warning(f"Error en detección de modelo: {e}, usando fallback")
        return "standard"

def recover_from_model_collapse(llm, chapter_details, context_manager, section_position):
    """
    Versión simplificada que solo genera contenido directo sin protocolos de recuperación.
    """
    print_progress("Generando contenido alternativo")
    
    # Extraer información del capítulo
    chapter_title = chapter_details.get("title", "capítulo actual")
    idea = chapter_details.get("idea", "")
    
    # Crear un prompt directo para generar contenido
    prompt = f"""
    Escribe un párrafo narrativo para el capítulo "{chapter_title}".
    
    {idea if idea else "Desarrolla la siguiente sección de la historia."}
    
    IMPORTANTE: Escribe SOLO texto narrativo en español, sin encabezados ni metadata.
    """
    
    try:
        # Generar contenido directamente
        response = llm(prompt, temperature=0.7)
        content = extract_content_from_llm_response(response)
        return clean_think_tags(content)
    except:
        # En caso de error, devolver un texto simple
        return f"En las profundidades del espacio, la nave seguía su curso hacia nuevos destinos. La tripulación se preparaba para afrontar los desafíos que les aguardaban en {chapter_title}."

class BaseChain:
    PROMPT_TEMPLATE = ""
    TIMEOUT = 60

    def __init__(self) -> None:
        # Obtener el tipo de modelo actual directamente desde la variable de entorno
        current_model_type = os.environ.get("SELECTED_MODEL", "ollama")
        
        self.llm = get_llm_model()
        
        # Inicializar estrategia de reintentos
        self.retry_strategy = RetryStrategy()
        
        # Crear el prompt template desde la cadena de texto
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=self._get_input_variables()
        )
        
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.prompt,
            verbose=True
        )

    def _get_input_variables(self):
        # Extraer variables del template
        return [
            var.strip('{}') for var in 
            [x for x in self.PROMPT_TEMPLATE.split('{') 
             if '}' in x]
        ]

    def invoke(self, **kwargs):
        """
        Invoca la cadena LLM con reintentos automáticos usando RetryStrategy.
        Reemplaza la lógica de reintentos manual anterior.
        """
        def _execute_chain():
            # Verificar que todos los parámetros necesarios estén presentes
            required_vars = set(self.prompt.input_variables)
            missing_keys = required_vars - set(kwargs.keys())
            if missing_keys:
                raise ValueError(f"Faltan parámetros requeridos: {missing_keys}")

            start_time = time.time()
            result = self.chain(kwargs)
            
            if result:
                # Usar la función para extraer contenido independientemente del formato
                if "text" in result:
                    text_content = extract_content_from_llm_response(result["text"])
                    if text_content and text_content.strip():
                        return clean_think_tags(text_content.strip())
                else:
                    # Manejar caso donde result no tiene una clave "text"
                    text_content = extract_content_from_llm_response(result)
                    if text_content and text_content.strip():
                        return clean_think_tags(text_content.strip())
            
            raise ValueError("La respuesta del modelo está vacía")
        
        # Usar RetryStrategy para ejecutar con reintentos automáticos
        return self.retry_strategy.execute(_execute_chain)

    def process_input(self, text):
        """Limpia las cadenas de pensamiento de los inputs antes de usarlos en prompts"""
        return clean_think_tags(text)

class BaseStructureChain(BaseChain):
    pass

class BaseEventChain(BaseChain):
    pass
