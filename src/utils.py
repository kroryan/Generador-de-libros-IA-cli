from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import sys
import time
import re
import os
import requests

from activity_log import activity_log
from generation_control import generation_control
from guidance import guidance_manager

# Importar nuevos módulos de infraestructura
from retry_strategy import RetryStrategy, with_retry
from circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, with_circuit_breaker
from emergency_prompts import emergency_prompts
from logging_config import get_logger, print_progress
from model_profiles import model_profile_manager, detect_model_size as new_detect_model_size

# Logger para este módulo
logger = get_logger("utils")

# Códigos ANSI para colores
YELLOW = "\033[93m"
WHITE = "\033[97m"
PURPLE = "\033[95m"
RESET = "\033[0m"

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
            default_model = os.environ.get("OLLAMA_MODEL", "")
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
    """Discover usable generation models through the runtime provider manager."""
    from provider_manager import provider_manager

    models = []
    selected = os.environ.get("SELECTED_MODEL", "").strip()
    for provider in provider_manager.list_public():
        if not provider["available"]:
            continue
        try:
            provider_models = provider_manager.models_for(provider["id"])
        except ValueError:
            continue
        for model in provider_models:
            value = f"{provider['id']}:{model['name']}"
            models.append({
                "provider": provider["id"],
                "name": model["name"],
                "display_name": f"{provider['name']}: {model['display_name']}",
                "value": value,
                "capabilities": model.get("capabilities", []),
                "native_tools": model.get("native_tools", False),
                "selected": value == selected,
            })
    if selected:
        models.sort(key=lambda item: not item["selected"])
    return models

# Función para consultar Ollama si está disponible
def get_ollama_models():
    """Obtiene la lista de modelos disponibles en Ollama"""
    from provider_manager import provider_manager

    return sorted(item["name"] for item in provider_manager.models_for("ollama"))

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
    if ":" in model_string:
        parts = model_string.split(":", 1)
        try:
            from provider_manager import provider_manager

            provider_manager.get(parts[0].lower())
            return parts[0].lower(), parts[1]
        except ValueError:
            return "ollama", model_string
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
    try:
        encoding = sys.stdout.encoding or "utf-8"
        safe_message = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        safe_message = message
    print(f"\n{WHITE}> {safe_message}{RESET}")
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
    
    FASE 4: Usa configuración centralizada para todos los parámetros LLM.
    """
    logger.info("Obteniendo modelo LLM usando sistema de proveedores unificado")
    
    # FASE 4: Obtener parámetros de configuración centralizada
    from config.defaults import get_config
    config = get_config()
    llm_config = config.llm
    
    # Parámetros comunes para todos los proveedores desde configuración
    common_params = {
        "temperature": llm_config.temperature,
        "streaming": llm_config.streaming,
    }
    
    # Agregar callbacks si se proporcionan
    if callbacks is not None:
        common_params["callbacks"] = callbacks
    
    try:
        from provider_manager import provider_manager

        selection = os.environ.get("SELECTED_MODEL", "").strip()
        available = get_available_models()
        if not selection or not any(item["value"] == selection for item in available):
            preferred_ollama = os.environ.get("OLLAMA_MODEL", "").strip()
            preferred_value = f"ollama:{preferred_ollama}" if preferred_ollama else ""
            selection = next(
                (item["value"] for item in available if item["value"] == preferred_value),
                available[0]["value"] if available else "",
            )
        if not selection:
            raise ValueError("No usable LLM provider or generation model was detected")
        client = provider_manager.build_model(selection, common_params)
        logger.info(f"LLM client created for {selection}")
        return client
    except Exception as error:
        logger.error(f"Error obtaining LLM model: {error}")
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
            models = get_ollama_models()
            if models:
                return "ollama", models[0]
    
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

class BaseChain:
    PROMPT_TEMPLATE = ""

    def __init__(self) -> None:
        if not str(self.PROMPT_TEMPLATE).strip():
            raise ValueError(f"{self.__class__.__name__} cannot be initialized with an empty prompt template")

        # FASE 4: Usar configuración centralizada
        from config.defaults import get_config
        config = get_config()
        
        self.retry_config = config.retry
        self.llm_config = config.llm
        
        # Usar timeout de configuración
        self.TIMEOUT = self.retry_config.timeout
        
        # Configurar LLM con parámetros de configuración
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
        generation_control.checkpoint()
        selected_model = os.environ.get("SELECTED_MODEL", "configured model")
        operation = self.__class__.__name__
        started_at = time.monotonic()
        activity_log.emit(f"{operation} request started with {selected_model}", source="llm")

        rendered_prompt = self.prompt.format(**kwargs)
        if not rendered_prompt.strip():
            raise ValueError(f"{operation} produced an empty prompt")
        live_guidance = guidance_manager.context()

        def _successful_text(value):
            cleaned = clean_think_tags(value.strip())
            llm_type = str(getattr(self.llm, "_llm_type", ""))
            if llm_type not in {"codex_cli", "claude_cli"}:
                activity_log.emit(f"{operation} response:\n{cleaned}", kind="output", source="llm")
            return cleaned

        def _execute_chain():
            # Verificar que todos los parámetros necesarios estén presentes
            required_vars = set(self.prompt.input_variables)
            missing_keys = required_vars - set(kwargs.keys())
            if missing_keys:
                raise ValueError(f"Faltan parámetros requeridos: {missing_keys}")

            if live_guidance:
                guided_prompt = (
                    rendered_prompt
                    + "\n\n### LIVE USER GUIDANCE (newest instructions take precedence)\n"
                    + live_guidance
                    + "\nApply this guidance only where relevant. Preserve unaffected canon and files."
                )
                result = {"text": self.llm.invoke(guided_prompt)}
            else:
                result = self.chain(kwargs)
            
            if result:
                # Usar la función para extraer contenido independientemente del formato
                if "text" in result:
                    text_content = extract_content_from_llm_response(result["text"])
                    if text_content and text_content.strip():
                        return _successful_text(text_content)
                else:
                    # Manejar caso donde result no tiene una clave "text"
                    text_content = extract_content_from_llm_response(result)
                    if text_content and text_content.strip():
                        return _successful_text(text_content)
            
            raise ValueError("La respuesta del modelo está vacía")
        
        # Usar RetryStrategy para ejecutar con reintentos automáticos
        try:
            response = self.retry_strategy.execute(_execute_chain)
            generation_control.checkpoint()
            activity_log.emit(
                f"{operation} completed in {int(time.monotonic() - started_at)}s",
                kind="success",
                source="llm",
            )
            return response
        except Exception as error:
            activity_log.emit(f"{operation} failed: {error}", kind="error", source="llm")
            raise

    def process_input(self, text):
        """Limpia las cadenas de pensamiento de los inputs antes de usarlos en prompts"""
        return clean_think_tags(text)

class BaseStructureChain(BaseChain):
    pass

class BaseEventChain(BaseChain):
    pass
