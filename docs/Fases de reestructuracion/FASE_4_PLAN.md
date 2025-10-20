# Fase 4 FINAL: Gestión de Configuración y Estado

## Estado: 🚧 POR INICIAR

**Fecha inicio**: Por determinar  
**Objetivo**: Eliminar toda configuración hardcoded y gestionar estado de forma inmutable y thread-safe.

---

## Contexto Post-Fase 2 y 3

### ✅ Lo que YA ESTÁ HECHO (No duplicar)

**De Fase 2:**
- ✅ Sistema unificado de limpieza de texto (`text_cleaning.py`)
- ✅ Streaming con máquina de estados (`streaming_cleaner.py`)
- ✅ Gestión unificada de contexto (`unified_context.py`)
- ✅ Todos con configuración por env variables

**De Fase 3:**
- ✅ Ordenamiento inteligente de capítulos (`chapter_ordering.py`)
- ✅ Extracción adaptativa de segmentos (`text_segment_extractor.py`)
- ✅ Código muerto eliminado (2 funciones)
- ✅ Configuración por env en nuevos sistemas

### ❌ Lo que FALTA (Objetivo de Fase 4)

**Problemas Identificados:**
1. **BaseChain**: `MAX_RETRIES = 3`, `TIMEOUT = 60` hardcodeados
2. **SocketIO**: `ping_timeout=259200` (72 horas!!), `async_mode='threading'` hardcodeado
3. **time.sleep()**: Dispersos por todo el código (server.py, writing.py, utils.py)
4. **Parámetros LLM**: `temperature=0.7`, `streaming=True` hardcodeados en get_llm_model()
5. **Valores de contexto**: 2000, 8000, 5000 caracteres hardcodeados
6. **Estado global mutable**: `generation_state = {}` dictionary modificado sin control
7. **Defaults de generación**: Subject, profile, style, genre hardcodeados en app.py

---

## 4.1 Sistema Centralizado de Configuración

### Objetivo
Crear un sistema de configuración unificado, validado y configurable por variables de entorno.

### 4.1.1 Crear `src/config/defaults.py`

**Estructuras a crear:**

```python
# 1. RetryConfig
@dataclass
class RetryConfig:
    max_retries: int = 3
    timeout: int = 60
    base_delay: float = 1.0
    max_delay: float = 10.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    
    @classmethod
    def from_env(cls) -> 'RetryConfig'
    
# 2. SocketIOConfig
@dataclass
class SocketIOConfig:
    ping_interval: int = 25
    ping_timeout: int = 3600  # ¡REDUCIR DE 72h a 1h!
    async_mode: AsyncMode = AsyncMode.THREADING
    cors_allowed_origins: str = "*"
    
    @classmethod
    def from_env(cls) -> 'SocketIOConfig'

# 3. RateLimitConfig
@dataclass
class RateLimitConfig:
    default_delay: float = 0.5
    provider_delays: Dict[str, float] = field(default_factory=dict)
    
    @classmethod
    def from_env(cls) -> 'RateLimitConfig'

# 4. ContextConfig (para complementar unified_context.py)
@dataclass
class ContextConfig:
    limited_context_size: int = 2000
    standard_context_size: int = 8000
    savepoint_interval: int = 3
    max_context_accumulation: int = 5000
    
    @classmethod
    def from_env(cls) -> 'ContextConfig'

# 5. LLMConfig
@dataclass
class LLMConfig:
    temperature: float = 0.7
    streaming: bool = True
    top_k: int = 50
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    
    @classmethod
    def from_env(cls) -> 'LLMConfig'

# 6. GenerationConfig
@dataclass
class GenerationConfig:
    default_subject: str = "Aventuras en un mundo cyberpunk"
    default_profile: str = "Protagonista rebelde en un entorno distópico"
    default_style: str = "Narrativo-Épico-Imaginativo"
    default_genre: str = "Cyberpunk"
    default_output_format: str = "docx"
    output_directory: str = "./docs"
    
    @classmethod
    def from_env(cls) -> 'GenerationConfig'

# 7. AppConfig (Contenedor principal)
@dataclass
class AppConfig:
    retry: RetryConfig
    socketio: SocketIOConfig
    rate_limit: RateLimitConfig
    context: ContextConfig
    llm: LLMConfig
    generation: GenerationConfig
    
    @classmethod
    def from_env(cls) -> 'AppConfig'
    
    def validate(self) -> List[str]:
        """Valida configuración y retorna errores"""

# 8. Singleton global
def get_config() -> AppConfig:
    """Obtiene configuración global (singleton)"""
```

**Archivos a crear:**
- `src/config/__init__.py`
- `src/config/defaults.py` (~500 líneas)

---

### 4.1.2 Actualizar `.env.example`

**Variables nuevas a agregar:**

```bash
# ==== REINTENTOS ====
RETRY_MAX_ATTEMPTS=3
RETRY_TIMEOUT=60
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=10.0
RETRY_BACKOFF_STRATEGY=exponential

# ==== SOCKETIO ====
SOCKETIO_PING_INTERVAL=25
SOCKETIO_PING_TIMEOUT=3600  # ¡1 hora, NO 72!
SOCKETIO_ASYNC_MODE=threading
SOCKETIO_CORS_ORIGINS=*

# ==== RATE LIMITING ====
RATE_LIMIT_DEFAULT_DELAY=0.5
RATE_LIMIT_OPENAI_DELAY=1.0
RATE_LIMIT_GROQ_DELAY=0.5
RATE_LIMIT_DEEPSEEK_DELAY=1.0
RATE_LIMIT_ANTHROPIC_DELAY=1.0
RATE_LIMIT_OLLAMA_DELAY=0.1

# ==== CONTEXTO (complementa UNIFIED_CONTEXT_MODE) ====
CONTEXT_LIMITED_SIZE=2000
CONTEXT_STANDARD_SIZE=8000
CONTEXT_SAVEPOINT_INTERVAL=3
CONTEXT_MAX_ACCUMULATION=5000

# ==== LLM ====
LLM_TEMPERATURE=0.7
LLM_STREAMING=true
LLM_TOP_K=50
LLM_TOP_P=0.9
LLM_REPEAT_PENALTY=1.1

# ==== GENERACIÓN ====
GEN_DEFAULT_SUBJECT=Aventuras en un mundo cyberpunk
GEN_DEFAULT_PROFILE=Protagonista rebelde en un entorno distópico
GEN_DEFAULT_STYLE=Narrativo-Épico-Imaginativo
GEN_DEFAULT_GENRE=Cyberpunk
GEN_DEFAULT_OUTPUT_FORMAT=docx
GEN_OUTPUT_DIRECTORY=./docs
```

**Archivos a modificar:**
- `.env.example` (+50 líneas)

---

### 4.1.3 Refactorizar `utils.py` - BaseChain

**Cambios a realizar:**

```python
# ANTES (utils.py:434-437)
class BaseChain:
    PROMPT_TEMPLATE = ""
    MAX_RETRIES = 3
    TIMEOUT = 60

# DESPUÉS
from config.defaults import get_config

class BaseChain:
    PROMPT_TEMPLATE = ""
    
    def __init__(self):
        config = get_config()
        self.retry_config = config.retry
        self.llm_config = config.llm
        
        # Usar configuración en lugar de constantes
        self.MAX_RETRIES = self.retry_config.max_retries
        self.TIMEOUT = self.retry_config.timeout
        
        # ... resto del código
```

**También actualizar `get_llm_model()`:**

```python
# ANTES (hardcoded temperature, streaming)
def get_llm_model(callbacks=None):
    # ... código con temperature=0.7, streaming=True hardcodeados

# DESPUÉS
def get_llm_model(callbacks=None):
    config = get_config()
    llm_config = config.llm
    
    common_params = {
        "callbacks": callbacks or [ColoredStreamingCallbackHandler()],
        "temperature": llm_config.temperature,
        "streaming": llm_config.streaming,
    }
    
    # Para Ollama, agregar parámetros adicionales
    if model_type == "ollama":
        common_params.update({
            "top_k": llm_config.top_k,
            "top_p": llm_config.top_p,
            "repeat_penalty": llm_config.repeat_penalty
        })
```

**Archivos a modificar:**
- `src/utils.py` (~20 líneas modificadas)

---

### 4.1.4 Refactorizar `server.py` - SocketIO

**Cambios a realizar:**

```python
# ANTES (server.py:28-35)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_interval=25,
    ping_timeout=259200  # ¡72 horas!
)

# DESPUÉS
from config.defaults import get_config

config = get_config()
socketio_config = config.socketio

socketio = SocketIO(
    app,
    cors_allowed_origins=socketio_config.cors_allowed_origins,
    async_mode=socketio_config.async_mode.value,
    ping_interval=socketio_config.ping_interval,
    ping_timeout=socketio_config.ping_timeout  # Ahora 1 hora
)
```

**Eliminar todos los `time.sleep()` hardcodeados:**

```python
# ANTES (disperso en server.py:350, 365, etc.)
time.sleep(0.5)  # ¿Por qué 0.5? ¿Qué provider?

# DESPUÉS
from config.defaults import get_config
rate_limiter = RateLimiter(get_config().rate_limit)

# En cada punto donde se llama a una API
rate_limiter.wait(provider='openai')  # Usa delay específico
```

**Archivos a modificar:**
- `src/server.py` (~15 líneas modificadas + eliminación de sleep)

---

### 4.1.5 Refactorizar `app.py` y `writing.py`

**app.py - Defaults de generación:**

```python
# ANTES (app.py:137-160)
# Valores hardcodeados para subject, profile, style, genre

# DESPUÉS
from config.defaults import get_config

def run_cli_generation(model=None):
    config = get_config()
    gen_config = config.generation
    
    subject = gen_config.default_subject
    profile = gen_config.default_profile
    style = gen_config.default_style
    genre = gen_config.default_genre
```

**writing.py - Eliminar valores mágicos:**

```python
# ANTES (writing.py:67-69, 387-410)
if len(previous_paragraphs_clean) > 800:  # ¿Por qué 800?
    previous_paragraphs_clean = previous_paragraphs_clean[-800:]

if len(paragraphs_context) > 5000:  # ¿Por qué 5000?
    paragraphs_context = paragraphs_context[-3000:]  # ¿Por qué -3000?

# DESPUÉS
from config.defaults import get_config

config = get_config()
ctx_config = config.context

if len(previous_paragraphs_clean) > ctx_config.standard_context_size:
    previous_paragraphs_clean = previous_paragraphs_clean[-ctx_config.standard_context_size:]

if len(paragraphs_context) > ctx_config.max_context_accumulation:
    keep_size = ctx_config.max_context_accumulation // 2
    paragraphs_context = paragraphs_context[-keep_size:]
```

**Archivos a modificar:**
- `src/app.py` (~10 líneas)
- `src/writing.py` (~15 líneas)

---

## 4.2 Estado Inmutable y Thread-Safe

### Objetivo
Reemplazar el diccionario global mutable con un sistema inmutable basado en dataclasses y patrón Observer.

### 4.2.1 Crear `src/generation_state.py`

**Estructuras a crear:**

```python
# 1. Enum de estados
class GenerationStatus(Enum):
    IDLE = "idle"
    STARTING = "starting"
    CONFIGURING_MODEL = "configuring_model"
    GENERATING_STRUCTURE = "generating_structure"
    STRUCTURE_COMPLETE = "structure_complete"
    GENERATING_IDEAS = "generating_ideas"
    IDEAS_COMPLETE = "ideas_complete"
    WRITING_BOOK = "writing_book"
    WRITING_COMPLETE = "writing_complete"
    SAVING_DOCUMENT = "saving_document"
    COMPLETE = "complete"
    ERROR = "error"

# 2. Estado inmutable
@dataclass(frozen=True)
class GenerationState:
    status: GenerationStatus = GenerationStatus.IDLE
    title: str = ''
    current_step: str = ''
    progress: int = 0
    chapter_count: int = 0
    current_chapter: int = 0
    error: Optional[str] = None
    book_ready: bool = False
    file_path: str = ''
    output_format: str = 'docx'
    timestamp: datetime = field(default_factory=datetime.now)
    
    def update(self, **kwargs) -> 'GenerationState':
        """Crea nuevo estado con cambios"""
        return replace(self, timestamp=datetime.now(), **kwargs)
    
    def can_transition_to(self, new_status: GenerationStatus) -> bool:
        """Valida transiciones de estado"""
        # Tabla de transiciones válidas

# 3. Patrón Observer
class StateObserver:
    def on_state_changed(self, old: GenerationState, new: GenerationState):
        pass

class SocketIOObserver(StateObserver):
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
    
    def on_state_changed(self, old, new):
        self.socketio.emit('status_update', new.to_dict())

class LoggingObserver(StateObserver):
    def on_state_changed(self, old, new):
        logger.info(f"State: {old.status.value} -> {new.status.value}")

# 4. Manager thread-safe
class GenerationStateManager:
    def __init__(self):
        self._state = GenerationState()
        self._lock = Lock()
        self._observers: List[StateObserver] = []
        self._history: List[GenerationState] = []
    
    def get_state(self) -> GenerationState:
        with self._lock:
            return self._state
    
    def update_state(self, **kwargs) -> GenerationState:
        with self._lock:
            old = self._state
            new = old.update(**kwargs)
            
            # Validar transición si cambió status
            if 'status' in kwargs:
                if not old.can_transition_to(kwargs['status']):
                    raise ValueError(f"Invalid transition")
            
            self._state = new
            self._history.append(new)
        
        # Notificar observers (fuera del lock)
        for observer in self._observers:
            observer.on_state_changed(old, new)
        
        return new
```

**Archivos a crear:**
- `src/generation_state.py` (~400 líneas)

---

### 4.2.2 Refactorizar `server.py` - Estado Global

**Cambios a realizar:**

```python
# ANTES (server.py:271-283)
generation_state = {
    'status': 'idle',
    'title': '',
    'current_step': '',
    # ... más campos
}

def update_generation_state(status, step, progress):
    generation_state['status'] = status
    generation_state['current_step'] = step
    generation_state['progress'] = progress

# DESPUÉS
from generation_state import GenerationStateManager, GenerationStatus, SocketIOObserver

state_manager = GenerationStateManager()
state_manager.add_observer(SocketIOObserver(socketio))
state_manager.add_observer(LoggingObserver())

# Eliminar update_generation_state() - ya no existe

# En generate_book():
state_manager.update_state(
    status=GenerationStatus.CONFIGURING_MODEL,
    current_step='Configurando modelo...',
    progress=2
)

# El SocketIOObserver automáticamente emite el evento
# ¡No más socketio.emit() manual!
```

**Eliminar:**
- Diccionario `generation_state`
- Función `update_generation_state()`
- Todos los `socketio.emit('status_update')` manuales

**Archivos a modificar:**
- `src/server.py` (~30 líneas modificadas, ~20 eliminadas)

---

## 4.3 Optimización de SocketIO

### Problemas a resolver

1. **Timeout de 72 horas**: Reducir a 1 hora (3600s)
2. **Async mode**: Documentar por qué threading
3. **Reconexión**: Añadir lógica de reconexión automática

### Cambios específicos

```python
# Ya cubierto en 4.1.4, pero agregar:

# En el cliente (templates/index.html)
socket.on('disconnect', function() {
    console.log('Desconectado, reintentando...');
    setTimeout(() => {
        socket.connect();
    }, 1000);
});

socket.on('connect_error', function() {
    console.log('Error de conexión, reintentando...');
});
```

**Archivos a modificar:**
- `templates/index.html` (~10 líneas)
- `docs/CONFIGURATION.md` (documentar async_mode)

---

## 4.4 Rate Limiting Inteligente

### Objetivo
Centralizar TODOS los `time.sleep()` en un sistema inteligente de rate limiting.

### 4.4.1 Crear `src/rate_limiter.py`

```python
class RateLimiter:
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.last_call: Dict[str, float] = {}
        self._lock = Lock()
    
    def wait(self, provider: str):
        """Espera el tiempo necesario para respetar rate limit"""
        with self._lock:
            delay = self.config.provider_delays.get(
                provider.lower(),
                self.config.default_delay
            )
            
            last = self.last_call.get(provider, 0)
            now = time.time()
            elapsed = now - last
            
            if elapsed < delay:
                time.sleep(delay - elapsed)
            
            self.last_call[provider] = time.time()
```

**Archivos a crear:**
- `src/rate_limiter.py` (~100 líneas)

---

### 4.4.2 Reemplazar TODOS los time.sleep()

**Ubicaciones a reemplazar:**

1. `server.py:350` → `rate_limiter.wait('selected_provider')`
2. `server.py:365` → `rate_limiter.wait('selected_provider')`
3. `writing.py:203` → `rate_limiter.wait(current_provider)`
4. `writing.py:387` → `rate_limiter.wait(current_provider)`
5. `writing.py:410` → `rate_limiter.wait(current_provider)`

**Archivos a modificar:**
- `src/server.py` (~5 ubicaciones)
- `src/writing.py` (~5 ubicaciones)

---

## 4.5 Validación de Configuración

### Objetivo
Validar configuración al inicio de la aplicación y mostrar errores claros.

### Cambios a realizar

```python
# En app.py (al inicio de __main__)
from config.defaults import get_config

try:
    config = get_config()
    errors = config.validate()
    if errors:
        print("❌ Errores de configuración:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("✅ Configuración validada correctamente")
except Exception as e:
    print(f"❌ Error fatal al cargar configuración: {e}")
    sys.exit(1)

# Lo mismo en server.py
```

**Archivos a modificar:**
- `src/app.py` (~10 líneas al inicio)
- `src/server.py` (~10 líneas al inicio)

---

## 4.6 Tests Unitarios

### Tests a crear

#### `tests/test_config.py`

```python
def test_retry_config_from_env()
def test_socketio_config_from_env()
def test_rate_limit_config_from_env()
def test_context_config_from_env()
def test_llm_config_from_env()
def test_generation_config_from_env()
def test_app_config_validation()
def test_config_singleton()
def test_config_reload()
```

#### `tests/test_generation_state.py`

```python
def test_state_immutability()
def test_state_update()
def test_valid_transitions()
def test_invalid_transitions()
def test_state_manager_thread_safety()
def test_socketio_observer()
def test_logging_observer()
def test_state_history()
```

#### `tests/test_rate_limiter.py`

```python
def test_rate_limiter_default_delay()
def test_rate_limiter_provider_specific()
def test_rate_limiter_thread_safety()
def test_rate_limiter_timing()
```

**Archivos a crear:**
- `tests/test_config.py` (~400 líneas)
- `tests/test_generation_state.py` (~300 líneas)
- `tests/test_rate_limiter.py` (~200 líneas)

---

## 4.7 Documentación

### `docs/CONFIGURATION.md`

**Contenido:**
1. Tabla de todas las variables de entorno
2. Valores recomendados por caso de uso
3. Ejemplos de configuración:
   - Para modelos locales (Ollama)
   - Para OpenAI/GPT-4
   - Para Groq (alta velocidad)
   - Para DeepSeek/Anthropic
4. Guía de migración desde hardcoded
5. Troubleshooting de configuración

**Archivos a crear:**
- `docs/CONFIGURATION.md` (~500 líneas)

---

## 4.8 Validación Integral

### Checklist de validación

- [ ] Ejecutar `tests/test_config.py` (9 tests)
- [ ] Ejecutar `tests/test_generation_state.py` (8 tests)
- [ ] Ejecutar `tests/test_rate_limiter.py` (4 tests)
- [ ] Ejecutar TODOS los tests de Fase 2 (11 tests)
- [ ] Ejecutar TODOS los tests de Fase 3 (20 tests)
- [ ] **Total**: 52 tests deben pasar

### Tests de integración

- [ ] Generar libro con configuración por defecto
- [ ] Generar libro con timeout reducido
- [ ] Generar libro con rate limiting agresivo
- [ ] Probar reconexión de SocketIO
- [ ] Verificar transiciones de estado

### Análisis de código

```bash
# Buscar valores hardcodeados restantes
grep -r "time\.sleep" src/  # ¡Debe dar 0 resultados!
grep -r "MAX_RETRIES = " src/  # ¡Debe dar 0 resultados!
grep -r "ping_timeout=" src/  # Solo en config
```

---

## Estadísticas Estimadas

### Archivos Nuevos (7)
1. `src/config/__init__.py`
2. `src/config/defaults.py` (~500 líneas)
3. `src/generation_state.py` (~400 líneas)
4. `src/rate_limiter.py` (~100 líneas)
5. `tests/test_config.py` (~400 líneas)
6. `tests/test_generation_state.py` (~300 líneas)
7. `tests/test_rate_limiter.py` (~200 líneas)
8. `docs/CONFIGURATION.md` (~500 líneas)

### Archivos Modificados (5)
1. `src/utils.py` (~30 líneas modificadas)
2. `src/server.py` (~60 líneas modificadas, ~20 eliminadas)
3. `src/app.py` (~20 líneas modificadas)
4. `src/writing.py` (~20 líneas modificadas)
5. `.env.example` (~50 líneas añadidas)

### Archivos Eliminados (0)
- Solo se eliminan fragmentos de código dentro de archivos existentes

### Total Estimado
- **Nuevas líneas**: ~2,400
- **Modificadas**: ~180
- **Eliminadas**: ~50
- **Neto**: +2,330 líneas

### Tests
- **Nuevos tests**: 21
- **Tests previos**: 31 (Fase 2 + Fase 3)
- **Total**: 52 tests

---

## Cronograma Estimado

### Semana 1: Configuración
- **Día 1-2**: 4.1.1 Crear config/defaults.py
- **Día 3**: 4.1.2 Actualizar .env.example
- **Día 4-5**: 4.1.3-4.1.5 Refactorizar utils, server, app, writing

### Semana 2: Estado
- **Día 6-7**: 4.2.1 Crear generation_state.py
- **Día 8-9**: 4.2.2 Refactorizar server.py con StateManager
- **Día 10**: 4.3 Optimizar SocketIO

### Semana 3: Rate Limiting y Tests
- **Día 11-12**: 4.4 Crear rate_limiter.py y reemplazar sleeps
- **Día 13-14**: 4.5-4.6 Validación + tests unitarios
- **Día 15**: 4.7 Documentación

### Semana 4: Validación Final
- **Día 16-17**: 4.8 Validación integral, generación de libros
- **Día 18-19**: Correcciones y ajustes
- **Día 20**: Release y documentación final

**Duración Total**: ~20 días (4 semanas)

---

## Criterios de Éxito

### Técnicos
- ✅ 0 valores hardcodeados en código (verificado con grep)
- ✅ Todas las configuraciones via env variables
- ✅ Estado inmutable con validación de transiciones
- ✅ Thread-safety en GenerationStateManager
- ✅ 52/52 tests pasando

### Funcionales
- ✅ Generación de libro exitosa con nueva configuración
- ✅ SocketIO estable con timeout de 1h
- ✅ Rate limiting respeta delays por provider
- ✅ Reconexión automática funciona
- ✅ Errores de configuración claros y útiles

### Calidad
- ✅ Código limpio y documentado
- ✅ Sin regresiones
- ✅ Documentación completa
- ✅ Migración sin breaking changes

---

## Notas Importantes

1. **NO duplicar lo de Fase 2/3**: Los sistemas de context, text_cleaning, streaming ya tienen configuración por env
2. **Validar transiciones**: GenerationState debe rechazar transiciones inválidas
3. **Thread-safety**: StateManager debe usar Lock correctamente
4. **Backward compatibility**: Mantener compatibilidad con código existente
5. **Testing exhaustivo**: Esta es la última fase, debe quedar perfecto

---

## Fase 5 (Opcional - Post-Fase 4)

Si queda tiempo o se necesita:
- Caching de resultados de LLM
- Async/await para I/O
- Profiling de performance
- Property-based testing
- Integration tests end-to-end

**Pero PRIMERO completar Fase 4 al 100%.**
