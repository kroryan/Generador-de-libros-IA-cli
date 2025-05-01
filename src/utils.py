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
    known_providers = ["openai", "deepseek", "groq", "anthropic"]
    
    if ":" in model_string:
        parts = model_string.split(":", 1)
        if parts[0].lower() in known_providers:
            # Es un proveedor conocido como openai:gpt-4
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
    if hasattr(response, 'content'):  # Para AIMessage, HumanMessage, etc.
        return response.content
    elif isinstance(response, dict) and "text" in response:  # Para diccionarios con clave 'text'
        return response["text"]
    elif isinstance(response, str):  # Para respuestas en texto plano
        return response
    else:  # Para cualquier otro tipo, convertir a string
        return str(response)

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
    """Elimina las cadenas de pensamiento del modelo en varios formatos posibles"""
    if not text:
        return text
        
    # Lista de patrones a limpiar
    patterns = [
        r'<think>.*?</think>\s*',  # Formato <think>...</think>
        r'\[pensamiento:.*?\]\s*',  # Formato [pensamiento:...]
        r'\[think:.*?\]\s*',       # Formato [think:...]
        r'\(pensando:.*?\)\s*',    # Formato (pensando:...)
        r'\(thinking:.*?\)\s*',    # Formato (thinking:...)
        r'<razonamiento>.*?</razonamiento>\s*',  # Formato <razonamiento>...</razonamiento>
        r'<reasoning>.*?</reasoning>\s*',  # Formato <reasoning>...</reasoning>
    ]
    
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # Eliminar líneas vacías extras que puedan quedar
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
    # Eliminar espacios extras al inicio y final
    cleaned = cleaned.strip()
    return cleaned

def get_llm_model(callbacks=None):
    """
    Selecciona el modelo LLM a utilizar basado en la configuración disponible y
    el tipo de modelo establecido en SELECTED_MODEL
    """
    if callbacks is None:
        callbacks = [ColoredStreamingCallbackHandler()]
    
    # Leer modelo desde SELECTED_MODEL env, si no está definido, usar prioridades por proveedor
    selected = os.environ.get("SELECTED_MODEL", "").strip()
    if selected:
        provider, model_name = parse_model_string(selected)
    else:
        # Fallback por prioridad de proveedores en env
        if os.environ.get("OLLAMA_MODEL", "").strip():
            provider = "ollama"
            model_name = os.environ["OLLAMA_MODEL"]
        elif os.environ.get("GROQ_MODEL", "").strip():
            provider = "groq"
            model_name = os.environ["GROQ_MODEL"]
        elif os.environ.get("OPENAI_MODEL", "").strip():
            provider = "openai"
            model_name = os.environ["OPENAI_MODEL"]
        elif os.environ.get("DEEPSEEK_MODEL", "").strip():
            provider = "deepseek"
            model_name = os.environ["DEEPSEEK_MODEL"]
        elif os.environ.get("ANTHROPIC_MODEL", "").strip():
            provider = "anthropic"
            model_name = os.environ["ANTHROPIC_MODEL"]
        else:
            provider, model_name = "ollama", "llama2"
    
    # Parámetros comunes
    common_params = {
        "callbacks": callbacks,
        "temperature": 0.7,
        "streaming": True,
    }
    
    # Caso especial para proveedores adicionales como Groq
    if provider == "groq":
        try:
            groq_api_key = os.environ.get("GROQ_API_KEY", "")
            groq_api_base = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")
            groq_model = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
            
            print_progress(f"Utilizando modelo Groq: {groq_model}")
            return ChatOpenAI(
                model=groq_model,
                api_key=groq_api_key,
                base_url=groq_api_base,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar Groq: {str(e)}")
            print_progress("Cambiando a otro modelo disponible.")
    
    # Caso especial para Ollama que usa ChatOllama
    if provider == "ollama":
        # Obtener la configuración de Ollama
        ollama_api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "llama2")
        
        if not check_ollama_available():
            print_progress(f"Ollama no está disponible en {ollama_api_base}. Cambiando a otro modelo disponible.")
            # Intentar con Groq si está configurado
            if os.environ.get("GROQ_API_KEY", ""):
                print_progress("Cambiando a Groq")
                os.environ["SELECTED_MODEL"] = "groq"
                return get_llm_model(callbacks)
            # Luego intentar con OpenAI
            elif os.environ.get("OPENAI_API_KEY", ""):
                print_progress("Cambiando a OpenAI")
                os.environ["SELECTED_MODEL"] = "openai"
                return get_llm_model(callbacks)
            # Finalmente DeepSeek
            elif os.environ.get("DEEPSEEK_API_KEY", ""):
                print_progress("Cambiando a DeepSeek")
                os.environ["SELECTED_MODEL"] = "deepseek"
                return get_llm_model(callbacks)
        else:
            try:
                print_progress(f"Utilizando modelo Ollama: {ollama_model}")
                return ChatOllama(
                    model=ollama_model,
                    base_url=ollama_api_base,
                    **common_params,
                    top_k=50,
                    top_p=0.9,
                    repeat_penalty=1.1
                )
            except Exception as e:
                print_progress(f"Error al inicializar Ollama: {str(e)}")
                print_progress("Cambiando a otro modelo disponible.")
    
    # Para OpenAI
    if provider == "openai":
        try:
            openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            openai_api_base = os.environ.get("OPENAI_API_BASE", "")
            openai_model = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
            
            # Parámetros específicos para OpenAI
            openai_params = {**common_params, "model": openai_model}
            
            # Añadir API key si está disponible
            if openai_api_key and openai_api_key.strip():
                openai_params["api_key"] = openai_api_key
            
            # Si se ha especificado una API base alternativa
            if openai_api_base and openai_api_base.strip():
                openai_params["base_url"] = openai_api_base
                print_progress(f"Utilizando API compatible con OpenAI: {openai_model} (Base: {openai_api_base})")
            else:
                print_progress(f"Utilizando modelo OpenAI: {openai_model}")
                
            return ChatOpenAI(**openai_params)
        except Exception as e:
            print_progress(f"Error al inicializar OpenAI: {str(e)}")
    
    # Para DeepSeek
    if provider == "deepseek":
        try:
            deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            deepseek_api_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
            deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
            
            print_progress(f"Utilizando modelo DeepSeek: {deepseek_model}")
            return ChatOpenAI(
                api_key=deepseek_api_key,
                base_url=deepseek_api_base,
                model=deepseek_model,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar DeepSeek: {str(e)}")
    
    # Para modelos de Anthropic
    if provider == "anthropic":
        try:
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            anthropic_api_base = os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1")
            anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-opus")
            
            print_progress(f"Utilizando modelo Anthropic: {anthropic_model}")
            # Anthropic requiere configuración especial
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar Anthropic: {str(e)}. Es posible que necesites instalar langchain_anthropic.")
    
    # Para cualquier otro proveedor personalizado (compatible con OpenAI)
    try:
        # Buscar configuración para este proveedor
        provider_api_key = os.environ.get(f"{provider.upper()}_API_KEY", "")
        provider_api_base = os.environ.get(f"{provider.upper()}_API_BASE", "")
        provider_model = os.environ.get(f"{provider.upper()}_MODEL", "")
        
        if provider_api_key and provider_api_base and provider_model:
            print_progress(f"Utilizando modelo personalizado {provider.capitalize()}: {provider_model}")
            return ChatOpenAI(
                model=provider_model,
                api_key=provider_api_key,
                base_url=provider_api_base,
                **common_params
            )
    except Exception as e:
        print_progress(f"Error al inicializar proveedor personalizado {provider}: {str(e)}")
    
    # Si todo lo demás falla, intentar un último recurso con Ollama
    if check_ollama_available():
        try:
            print_progress("Todos los modelos configurados fallaron. Intentando último recurso con Ollama...")
            return ChatOllama(
                model="llama2",  # Modelo básico que probablemente esté disponible
                base_url=os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
                **common_params,
                top_k=50,
                top_p=0.9,
                repeat_penalty=1.1
            )
        except Exception as e:
            print_progress(f"Error al inicializar Ollama como último recurso: {str(e)}")
    
    # Si todo lo demás falla, lanzar un error claro
    raise ValueError("No se pudo inicializar ningún modelo LLM. Por favor, configura al menos un proveedor en el archivo .env")

class BaseChain:
    PROMPT_TEMPLATE = ""
    MAX_RETRIES = 3
    TIMEOUT = 60

    def __init__(self) -> None:
        # Obtener el tipo de modelo actual directamente desde la variable de entorno
        # en lugar de usar la variable global SELECTED_MODEL
        current_model_type = os.environ.get("SELECTED_MODEL", "ollama")
        
        self.llm = get_llm_model()
        
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
        for attempt in range(self.MAX_RETRIES):
            try:
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
                
            except Exception as e:
                print_progress(f"Error en intento {attempt + 1}: {str(e)}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                wait_time = (attempt + 1) * 2
                print_progress(f"Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)

    def process_input(self, text):
        """Limpia las cadenas de pensamiento de los inputs antes de usarlos en prompts"""
        return clean_think_tags(text)

class BaseStructureChain(BaseChain):
    pass

class BaseEventChain(BaseChain):
    pass
