from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import sys
import time
import re

# Códigos ANSI para colores
YELLOW = "\033[93m"
WHITE = "\033[97m"
PURPLE = "\033[95m"
RESET = "\033[0m"

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

class BaseChain:
    PROMPT_TEMPLATE = ""
    MAX_RETRIES = 3
    TIMEOUT = 60

    def __init__(self) -> None:
        self.llm = ChatOllama(
            model="hf.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF:Q4_K_M",
            callbacks=[ColoredStreamingCallbackHandler()],
            temperature=0.7,
            top_k=50,
            top_p=0.9,
            repeat_penalty=1.1
        )
        
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
                
                if result and "text" in result and result["text"].strip():
                    # Limpiar las cadenas de pensamiento antes de devolver el resultado
                    return clean_think_tags(result["text"].strip())
                
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
