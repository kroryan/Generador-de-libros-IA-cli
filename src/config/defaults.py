"""
Sistema Centralizado de Configuración.

Este módulo proporciona un sistema unificado de configuración para toda la aplicación,
eliminando valores hardcodeados y centralizando la gestión de parámetros.

Características:
- Configuración por variables de entorno
- Validación automática de valores
- Singleton global para acceso thread-safe
- Soporte para recargar configuración
- Valores por defecto razonables
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import os
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Estrategias de backoff para reintentos."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class AsyncMode(Enum):
    """Modos async disponibles para SocketIO."""
    THREADING = "threading"
    EVENTLET = "eventlet"
    GEVENT = "gevent"


@dataclass
class RetryConfig:
    """
    Configuración de reintentos y timeouts.
    
    Reemplaza los valores hardcodeados en BaseChain:
    - MAX_RETRIES = 3
    - TIMEOUT = 60
    """
    max_retries: int = 3
    timeout: int = 60
    base_delay: float = 1.0
    max_delay: float = 10.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    
    @classmethod
    def from_env(cls) -> 'RetryConfig':
        """Crea configuración desde variables de entorno."""
        strategy_str = os.getenv('RETRY_BACKOFF_STRATEGY', 'exponential').lower()
        strategy_map = {
            'exponential': BackoffStrategy.EXPONENTIAL,
            'linear': BackoffStrategy.LINEAR,
            'fixed': BackoffStrategy.FIXED
        }
        strategy = strategy_map.get(strategy_str, BackoffStrategy.EXPONENTIAL)
        
        return cls(
            max_retries=int(os.getenv('RETRY_MAX_ATTEMPTS', '3')),
            timeout=int(os.getenv('RETRY_TIMEOUT', '60')),
            base_delay=float(os.getenv('RETRY_BASE_DELAY', '1.0')),
            max_delay=float(os.getenv('RETRY_MAX_DELAY', '10.0')),
            backoff_strategy=strategy
        )
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calcula el delay para un intento dado según la estrategia.
        
        Args:
            attempt: Número de intento (0-indexed)
            
        Returns:
            Delay en segundos
        """
        if self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** attempt)
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        else:  # FIXED
            delay = self.base_delay
        
        return min(delay, self.max_delay)


@dataclass
class SocketIOConfig:
    """
    Configuración de SocketIO.
    
    Reemplaza los valores hardcodeados en server.py:
    - ping_interval=25
    - ping_timeout=259200 (¡72 horas!)
    - async_mode='threading'
    """
    ping_interval: int = 25
    ping_timeout: int = 3600  # 1 hora en lugar de 72
    async_mode: AsyncMode = AsyncMode.THREADING
    cors_allowed_origins: str = "*"
    
    @classmethod
    def from_env(cls) -> 'SocketIOConfig':
        """Crea configuración desde variables de entorno."""
        async_mode_str = os.getenv('SOCKETIO_ASYNC_MODE', 'threading').lower()
        async_mode_map = {
            'threading': AsyncMode.THREADING,
            'eventlet': AsyncMode.EVENTLET,
            'gevent': AsyncMode.GEVENT
        }
        async_mode = async_mode_map.get(async_mode_str, AsyncMode.THREADING)
        
        return cls(
            ping_interval=int(os.getenv('SOCKETIO_PING_INTERVAL', '25')),
            ping_timeout=int(os.getenv('SOCKETIO_PING_TIMEOUT', '3600')),
            async_mode=async_mode,
            cors_allowed_origins=os.getenv('SOCKETIO_CORS_ORIGINS', '*')
        )


@dataclass
class RateLimitConfig:
    """
    Configuración de rate limiting por provider.
    
    Reemplaza todos los time.sleep() dispersos con delays configurables.
    """
    default_delay: float = 0.5
    provider_delays: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Inicializa delays por defecto si no se especifican."""
        if not self.provider_delays:
            self.provider_delays = {
                'openai': 1.0,
                'groq': 0.5,
                'deepseek': 1.0,
                'anthropic': 1.0,
                'ollama': 0.1
            }
    
    @classmethod
    def from_env(cls) -> 'RateLimitConfig':
        """Crea configuración desde variables de entorno."""
        config = cls(
            default_delay=float(os.getenv('RATE_LIMIT_DEFAULT_DELAY', '0.5'))
        )
        
        # Cargar delays específicos por proveedor
        for provider in ['openai', 'groq', 'deepseek', 'anthropic', 'ollama']:
            env_var = f'RATE_LIMIT_{provider.upper()}_DELAY'
            delay = os.getenv(env_var)
            if delay:
                config.provider_delays[provider.lower()] = float(delay)
        
        return config
    
    def get_delay(self, provider: str) -> float:
        """
        Obtiene el delay para un provider específico.
        
        Args:
            provider: Nombre del provider (case-insensitive)
            
        Returns:
            Delay en segundos
        """
        return self.provider_delays.get(
            provider.lower(),
            self.default_delay
        )


@dataclass
class ContextConfig:
    """
    Configuración de gestión de contexto.
    
    Reemplaza valores mágicos dispersos:
    - 2000 caracteres (contexto limitado)
    - 8000 caracteres (contexto estándar)
    - 5000 caracteres (acumulación máxima)
    """
    limited_context_size: int = 2000
    standard_context_size: int = 8000
    savepoint_interval: int = 3  # Cada cuántas secciones crear savepoint
    max_context_accumulation: int = 5000
    
    @classmethod
    def from_env(cls) -> 'ContextConfig':
        """Crea configuración desde variables de entorno."""
        return cls(
            limited_context_size=int(os.getenv('CONTEXT_LIMITED_SIZE', '2000')),
            standard_context_size=int(os.getenv('CONTEXT_STANDARD_SIZE', '8000')),
            savepoint_interval=int(os.getenv('CONTEXT_SAVEPOINT_INTERVAL', '3')),
            max_context_accumulation=int(os.getenv('CONTEXT_MAX_ACCUMULATION', '5000'))
        )


@dataclass
class LLMConfig:
    """
    Configuración de parámetros de LLM.
    
    Reemplaza valores hardcodeados en get_llm_model():
    - temperature=0.7
    - streaming=True
    """
    temperature: float = 0.7
    streaming: bool = True
    top_k: int = 50
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    max_tokens: Optional[int] = None  # None = sin límite
    
    @classmethod
    def from_env(cls) -> 'LLMConfig':
        """Crea configuración desde variables de entorno."""
        streaming_str = os.getenv('LLM_STREAMING', 'true').lower()
        streaming = streaming_str in ['true', '1', 'yes', 'on']
        
        max_tokens_str = os.getenv('LLM_MAX_TOKENS')
        max_tokens = int(max_tokens_str) if max_tokens_str else None
        
        return cls(
            temperature=float(os.getenv('LLM_TEMPERATURE', '0.7')),
            streaming=streaming,
            top_k=int(os.getenv('LLM_TOP_K', '50')),
            top_p=float(os.getenv('LLM_TOP_P', '0.9')),
            repeat_penalty=float(os.getenv('LLM_REPEAT_PENALTY', '1.1')),
            max_tokens=max_tokens
        )


@dataclass
class FewShotConfig:
    """
    Configuración de few-shot learning para prompts.
    
    Controla el sistema de ejemplos y evaluación de calidad.
    """
    enabled: bool = True
    quality_threshold: float = 0.75
    max_examples_per_prompt: int = 2
    examples_storage_path: str = "./data/examples"
    auto_save_examples: bool = True
    
    @classmethod
    def from_env(cls) -> 'FewShotConfig':
        """Crea configuración desde variables de entorno."""
        enabled_str = os.getenv('USE_FEW_SHOT_LEARNING', 'true').lower()
        enabled = enabled_str in ['true', '1', 'yes', 'on']
        
        auto_save_str = os.getenv('FEW_SHOT_AUTO_SAVE', 'true').lower()
        auto_save = auto_save_str in ['true', '1', 'yes', 'on']
        
        return cls(
            enabled=enabled,
            quality_threshold=float(os.getenv('EXAMPLE_QUALITY_THRESHOLD', '0.75')),
            max_examples_per_prompt=int(os.getenv('MAX_EXAMPLES_PER_PROMPT', '2')),
            examples_storage_path=os.getenv('EXAMPLES_STORAGE_PATH', './data/examples'),
            auto_save_examples=auto_save
        )


@dataclass
class GenerationConfig:
    """
    Configuración de parámetros de generación de libros.
    
    Reemplaza defaults hardcodeados en app.py.
    """
    default_subject: str = "Aventuras en un mundo cyberpunk"
    default_profile: str = "Protagonista rebelde en un entorno distópico"
    default_style: str = "Narrativo-Épico-Imaginativo"
    default_genre: str = "Cyberpunk"
    default_output_format: str = "docx"
    output_directory: str = "./docs"
    
    @classmethod
    def from_env(cls) -> 'GenerationConfig':
        """Crea configuración desde variables de entorno."""
        return cls(
            default_subject=os.getenv(
                'GEN_DEFAULT_SUBJECT',
                'Aventuras en un mundo cyberpunk'
            ),
            default_profile=os.getenv(
                'GEN_DEFAULT_PROFILE',
                'Protagonista rebelde en un entorno distópico'
            ),
            default_style=os.getenv(
                'GEN_DEFAULT_STYLE',
                'Narrativo-Épico-Imaginativo'
            ),
            default_genre=os.getenv(
                'GEN_DEFAULT_GENRE',
                'Cyberpunk'
            ),
            default_output_format=os.getenv(
                'GEN_DEFAULT_OUTPUT_FORMAT',
                'docx'
            ),
            output_directory=os.getenv(
                'GEN_OUTPUT_DIRECTORY',
                './docs'
            )
        )


@dataclass
class AppConfig:
    """
    Configuración global de la aplicación.
    
    Contenedor principal que agrupa todas las configuraciones específicas.
    """
    retry: RetryConfig = field(default_factory=RetryConfig)
    socketio: SocketIOConfig = field(default_factory=SocketIOConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    few_shot: FewShotConfig = field(default_factory=FewShotConfig)
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """
        Crea configuración completa desde variables de entorno.
        
        Returns:
            Instancia de AppConfig con toda la configuración cargada
        """
        return cls(
            retry=RetryConfig.from_env(),
            socketio=SocketIOConfig.from_env(),
            rate_limit=RateLimitConfig.from_env(),
            context=ContextConfig.from_env(),
            llm=LLMConfig.from_env(),
            generation=GenerationConfig.from_env(),
            few_shot=FewShotConfig.from_env()
        )
    
    def validate(self) -> List[str]:
        """
        Valida la configuración completa.
        
        Returns:
            Lista de mensajes de error (vacía si todo es válido)
        """
        errors = []
        
        # Validar RetryConfig
        if self.retry.max_retries < 1:
            errors.append("RETRY_MAX_ATTEMPTS debe ser >= 1")
        
        if self.retry.timeout < 1:
            errors.append("RETRY_TIMEOUT debe ser >= 1 segundo")
        
        if self.retry.base_delay < 0:
            errors.append("RETRY_BASE_DELAY debe ser >= 0")
        
        if self.retry.max_delay < self.retry.base_delay:
            errors.append("RETRY_MAX_DELAY debe ser >= RETRY_BASE_DELAY")
        
        # Validar SocketIOConfig
        if self.socketio.ping_interval < 1:
            errors.append("SOCKETIO_PING_INTERVAL debe ser >= 1 segundo")
        
        if self.socketio.ping_timeout < self.socketio.ping_interval:
            errors.append(
                "SOCKETIO_PING_TIMEOUT debe ser >= SOCKETIO_PING_INTERVAL"
            )
        
        # Validar RateLimitConfig
        if self.rate_limit.default_delay < 0:
            errors.append("RATE_LIMIT_DEFAULT_DELAY debe ser >= 0")
        
        for provider, delay in self.rate_limit.provider_delays.items():
            if delay < 0:
                errors.append(
                    f"RATE_LIMIT_{provider.upper()}_DELAY debe ser >= 0"
                )
        
        # Validar ContextConfig
        if self.context.limited_context_size < 100:
            errors.append("CONTEXT_LIMITED_SIZE debe ser >= 100 caracteres")
        
        if self.context.standard_context_size < self.context.limited_context_size:
            errors.append(
                "CONTEXT_STANDARD_SIZE debe ser >= CONTEXT_LIMITED_SIZE"
            )
        
        if self.context.savepoint_interval < 1:
            errors.append("CONTEXT_SAVEPOINT_INTERVAL debe ser >= 1")
        
        if self.context.max_context_accumulation < 1000:
            errors.append(
                "CONTEXT_MAX_ACCUMULATION debe ser >= 1000 caracteres"
            )
        
        # Validar LLMConfig
        if self.llm.temperature < 0 or self.llm.temperature > 2:
            errors.append("LLM_TEMPERATURE debe estar entre 0 y 2")
        
        if self.llm.top_k < 1:
            errors.append("LLM_TOP_K debe ser >= 1")
        
        if self.llm.top_p < 0 or self.llm.top_p > 1:
            errors.append("LLM_TOP_P debe estar entre 0 y 1")
        
        if self.llm.repeat_penalty < 0:
            errors.append("LLM_REPEAT_PENALTY debe ser >= 0")
        
        if self.llm.max_tokens is not None and self.llm.max_tokens < 1:
            errors.append("LLM_MAX_TOKENS debe ser >= 1 o None")
        
        # Validar GenerationConfig
        valid_formats = ['docx', 'pdf', 'txt', 'html', 'md']
        if self.generation.default_output_format.lower() not in valid_formats:
            errors.append(
                f"GEN_DEFAULT_OUTPUT_FORMAT debe ser uno de: {', '.join(valid_formats)}"
            )
        
        # Validar FewShotConfig
        if self.few_shot.quality_threshold < 0 or self.few_shot.quality_threshold > 1:
            errors.append("EXAMPLE_QUALITY_THRESHOLD debe estar entre 0 y 1")
        
        if self.few_shot.max_examples_per_prompt < 1:
            errors.append("MAX_EXAMPLES_PER_PROMPT debe ser >= 1")
        
        if not self.few_shot.examples_storage_path:
            errors.append("EXAMPLES_STORAGE_PATH no puede estar vacío")
        
        return errors
    
    def __repr__(self) -> str:
        """Representación legible de la configuración."""
        return (
            f"AppConfig(\n"
            f"  retry={self.retry},\n"
            f"  socketio={self.socketio},\n"
            f"  rate_limit={self.rate_limit},\n"
            f"  context={self.context},\n"
            f"  llm={self.llm},\n"
            f"  generation={self.generation}\n"
            f")"
        )


# ============================================================================
# Singleton Global
# ============================================================================

_config: Optional[AppConfig] = None
_config_lock = __import__('threading').Lock()


def get_config() -> AppConfig:
    """
    Obtiene la configuración global de la aplicación (singleton).
    
    La configuración se carga una sola vez desde variables de entorno
    y se valida automáticamente.
    
    Returns:
        Instancia singleton de AppConfig
        
    Raises:
        ValueError: Si la configuración tiene errores de validación
    """
    global _config
    
    if _config is None:
        with _config_lock:
            # Double-check locking
            if _config is None:
                logger.info("Cargando configuración desde variables de entorno...")
                _config = AppConfig.from_env()
                
                # Validar configuración
                errors = _config.validate()
                if errors:
                    error_msg = "Errores en la configuración:\n  - " + "\n  - ".join(errors)
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                logger.info("✓ Configuración cargada y validada correctamente")
    
    return _config


def reload_config() -> AppConfig:
    """
    Recarga la configuración desde variables de entorno.
    
    Útil para testing o para recargar configuración sin reiniciar.
    
    Returns:
        Nueva instancia de AppConfig
        
    Raises:
        ValueError: Si la nueva configuración tiene errores
    """
    global _config
    
    with _config_lock:
        logger.info("Recargando configuración...")
        _config = None
        return get_config()


def print_config(config: Optional[AppConfig] = None):
    """
    Imprime la configuración actual de forma legible.
    
    Args:
        config: Configuración a imprimir (None = usar singleton global)
    """
    if config is None:
        config = get_config()
    
    print("\n" + "="*60)
    print("CONFIGURACIÓN DE LA APLICACIÓN")
    print("="*60)
    
    print("\n🔄 RETRY CONFIGURATION")
    print(f"  Max Retries: {config.retry.max_retries}")
    print(f"  Timeout: {config.retry.timeout}s")
    print(f"  Base Delay: {config.retry.base_delay}s")
    print(f"  Max Delay: {config.retry.max_delay}s")
    print(f"  Strategy: {config.retry.backoff_strategy.value}")
    
    print("\n🌐 SOCKETIO CONFIGURATION")
    print(f"  Ping Interval: {config.socketio.ping_interval}s")
    print(f"  Ping Timeout: {config.socketio.ping_timeout}s")
    print(f"  Async Mode: {config.socketio.async_mode.value}")
    print(f"  CORS Origins: {config.socketio.cors_allowed_origins}")
    
    print("\n⏱️  RATE LIMIT CONFIGURATION")
    print(f"  Default Delay: {config.rate_limit.default_delay}s")
    print("  Provider Delays:")
    for provider, delay in sorted(config.rate_limit.provider_delays.items()):
        print(f"    {provider}: {delay}s")
    
    print("\n📝 CONTEXT CONFIGURATION")
    print(f"  Limited Size: {config.context.limited_context_size} chars")
    print(f"  Standard Size: {config.context.standard_context_size} chars")
    print(f"  Savepoint Interval: {config.context.savepoint_interval}")
    print(f"  Max Accumulation: {config.context.max_context_accumulation} chars")
    
    print("\n🤖 LLM CONFIGURATION")
    print(f"  Temperature: {config.llm.temperature}")
    print(f"  Streaming: {config.llm.streaming}")
    print(f"  Top K: {config.llm.top_k}")
    print(f"  Top P: {config.llm.top_p}")
    print(f"  Repeat Penalty: {config.llm.repeat_penalty}")
    print(f"  Max Tokens: {config.llm.max_tokens or 'None (unlimited)'}")
    
    print("\n📚 GENERATION CONFIGURATION")
    print(f"  Default Subject: {config.generation.default_subject}")
    print(f"  Default Profile: {config.generation.default_profile}")
    print(f"  Default Style: {config.generation.default_style}")
    print(f"  Default Genre: {config.generation.default_genre}")
    print(f"  Output Format: {config.generation.default_output_format}")
    print(f"  Output Directory: {config.generation.output_directory}")
    
    print("\n🎯 FEW-SHOT LEARNING CONFIGURATION")
    print(f"  Enabled: {config.few_shot.enabled}")
    print(f"  Quality Threshold: {config.few_shot.quality_threshold}")
    print(f"  Max Examples per Prompt: {config.few_shot.max_examples_per_prompt}")
    print(f"  Storage Path: {config.few_shot.examples_storage_path}")
    print(f"  Auto Save Examples: {config.few_shot.auto_save_examples}")
    
    print("\n" + "="*60 + "\n")
