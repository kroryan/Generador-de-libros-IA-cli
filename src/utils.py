from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import sys
import time
import re
import os

# Códigos ANSI para colores
YELLOW = "\033[93m"
WHITE = "\033[97m"
PURPLE = "\033[95m"
RESET = "\033[0m"

# Configuración de modelos
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "")  # Para servicios compatibles con OpenAI
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")  # Valores posibles: deepseek-chat, deepseek-reasoner
DEEPSEEK_API_BASE = "https://api.deepseek.com"

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
    Selecciona el modelo LLM a utilizar basado en la configuración disponible.
    Prioridad: 
    1. Ollama (si OLLAMA_MODEL no está vacío)
    2. DeepSeek (si DEEPSEEK_API_KEY está disponible)
    3. OpenAI o API compatible (si OPENAI_API_KEY está disponible)
    """
    if callbacks is None:
        callbacks = [ColoredStreamingCallbackHandler()]
    
    # Parámetros comunes para todos los modelos
    common_params = {
        "callbacks": callbacks,
        "temperature": 0.7,
        "streaming": True,
    }
    
    # Primero intentar con Ollama si hay un modelo especificado
    if OLLAMA_MODEL and OLLAMA_MODEL.strip():
        try:
            print_progress(f"Utilizando modelo Ollama: {OLLAMA_MODEL}")
            return ChatOllama(
                model=OLLAMA_MODEL,
                **common_params,
                top_k=50,
                top_p=0.9,
                repeat_penalty=1.1
            )
        except Exception as e:
            print_progress(f"Error al inicializar Ollama: {str(e)}")
    
    # Luego intentar con DeepSeek si hay una API key
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY.strip():
        try:
            print_progress(f"Utilizando modelo DeepSeek: {DEEPSEEK_MODEL}")
            # Usar ChatOpenAI con la configuración de DeepSeek
            # El parámetro correcto es base_url, no api_base
            return ChatOpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_API_BASE,
                model=DEEPSEEK_MODEL,
                **common_params
            )
        except Exception as e:
            print_progress(f"Error al inicializar DeepSeek: {str(e)}")
    
    # Finalmente intentar con OpenAI o compatible si hay una API key
    if OPENAI_API_KEY and OPENAI_API_KEY.strip():
        try:
            openai_params = {**common_params, "model": OPENAI_MODEL, "api_key": OPENAI_API_KEY}
            
            # Si se ha especificado una API base alternativa (compatible con OpenAI)
            if OPENAI_API_BASE and OPENAI_API_BASE.strip():
                # También usamos base_url en lugar de api_base para mantener consistencia
                openai_params["base_url"] = OPENAI_API_BASE
                print_progress(f"Utilizando API compatible con OpenAI: {OPENAI_MODEL} (Base: {OPENAI_API_BASE})")
            else:
                print_progress(f"Utilizando modelo OpenAI: {OPENAI_MODEL}")
                
            return ChatOpenAI(**openai_params)
        except Exception as e:
            print_progress(f"Error al inicializar OpenAI: {str(e)}")
    
    # Si no se pudo inicializar ningún modelo, volver a intentar con Ollama en modo de error
    print_progress("No se pudo inicializar ninguno de los modelos configurados. Intentando con Ollama por defecto...")
    return ChatOllama(
        model="llama2",  # Modelo básico que probablemente esté disponible
        **common_params,
        top_k=50,
        top_p=0.9,
        repeat_penalty=1.1
    )

class BaseChain:
    PROMPT_TEMPLATE = ""
    MAX_RETRIES = 3
    TIMEOUT = 60

    def __init__(self) -> None:
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
