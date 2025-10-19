"""
Sistema unificado de reintentos con backoff exponencial y circuit breaker.
Centraliza toda la lógica de reintentos del proyecto eliminando duplicación.
"""

import time
import random
import os
from enum import Enum
from typing import Any, Callable, Optional, List, Type
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class BackoffStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"

@dataclass
class RetryConfig:
    """Configuración para la estrategia de reintentos"""
    max_attempts: int
    base_delay: float
    max_delay: float
    backoff_strategy: BackoffStrategy
    jitter_enabled: bool
    
    @classmethod
    def from_env(cls) -> 'RetryConfig':
        """Crea configuración desde variables de entorno"""
        return cls(
            max_attempts=int(os.environ.get("RETRY_MAX_ATTEMPTS", "3")),
            base_delay=float(os.environ.get("RETRY_BASE_DELAY", "1.0")),
            max_delay=float(os.environ.get("RETRY_MAX_DELAY", "10.0")),
            backoff_strategy=BackoffStrategy(
                os.environ.get("RETRY_BACKOFF_STRATEGY", "exponential")
            ),
            jitter_enabled=os.environ.get("RETRY_JITTER_ENABLED", "true").lower() == "true"
        )

class RetryableException(Exception):
    """Excepción base para errores que permiten reintentos"""
    pass

class NonRetryableException(Exception):
    """Excepción para errores que NO deben ser reintentados"""
    pass

class RetryStrategy:
    """
    Estrategia unificada de reintentos con backoff configurable y jitter.
    Reemplaza todas las implementaciones de reintentos dispersas en el código.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig.from_env()
        self._retriable_exceptions = [
            ConnectionError,
            TimeoutError,
            RetryableException,
            # Agregar excepciones específicas de LangChain/OpenAI aquí
        ]
        self._non_retriable_exceptions = [
            NonRetryableException,
            ValueError,  # Problemas de configuración no deben reintentarse
            KeyError,    # Parámetros faltantes no deben reintentarse
        ]
    
    def should_retry(self, exception: Exception) -> bool:
        """
        Determina si una excepción debe ser reintentada.
        
        Args:
            exception: La excepción que ocurrió
            
        Returns:
            bool: True si debe reintentarse, False en caso contrario
        """
        # Si es explícitamente no-retriable, no reintentar
        if any(isinstance(exception, exc_type) for exc_type in self._non_retriable_exceptions):
            return False
        
        # Si es explícitamente retriable, reintentar
        if any(isinstance(exception, exc_type) for exc_type in self._retriable_exceptions):
            return True
        
        # Para otras excepciones, aplicar lógica heurística
        error_msg = str(exception).lower()
        
        # Errores de red/API que típicamente permiten reintentos
        network_errors = [
            "connection", "timeout", "rate limit", "503", "502", "504",
            "temporarily unavailable", "service unavailable"
        ]
        
        if any(error in error_msg for error in network_errors):
            return True
        
        # Errores de configuración que NO deben reintentarse
        config_errors = [
            "api key", "authentication", "authorization", "invalid key",
            "forbidden", "401", "403"
        ]
        
        if any(error in error_msg for error in config_errors):
            return False
        
        # Por defecto, no reintentar excepciones desconocidas
        return False
    
    def get_delay(self, attempt_number: int) -> float:
        """
        Calcula el tiempo de espera para un intento específico.
        
        Args:
            attempt_number: Número del intento (empezando en 0)
            
        Returns:
            float: Tiempo de espera en segundos
        """
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.base_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * (attempt_number + 1)
        else:  # EXPONENTIAL
            delay = self.config.base_delay * (2 ** attempt_number)
        
        # Aplicar límite máximo
        delay = min(delay, self.config.max_delay)
        
        # Aplicar jitter para evitar thundering herd
        if self.config.jitter_enabled:
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        return delay
    
    def execute(self, callable_func: Callable, *args, **kwargs) -> Any:
        """
        Ejecuta una función con reintentos automáticos.
        
        Args:
            callable_func: Función a ejecutar
            *args: Argumentos posicionales para la función
            **kwargs: Argumentos nombrados para la función
            
        Returns:
            Any: Resultado de la función
            
        Raises:
            Exception: La última excepción si todos los reintentos fallan
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = callable_func(*args, **kwargs)
                
                # Verificar si el resultado es válido
                if self._is_valid_result(result):
                    if attempt > 0:
                        logger.info(f"Operación exitosa en intento {attempt + 1}")
                    return result
                else:
                    raise RetryableException("Resultado inválido o vacío")
                    
            except Exception as e:
                last_exception = e
                
                # Log del error
                logger.warning(f"Intento {attempt + 1}/{self.config.max_attempts} falló: {str(e)}")
                
                # Verificar si debemos reintentar
                if not self.should_retry(e) or attempt == self.config.max_attempts - 1:
                    logger.error(f"No se puede reintentar o se agotaron los intentos: {str(e)}")
                    raise e
                
                # Calcular y aplicar delay
                delay = self.get_delay(attempt)
                logger.info(f"Reintentando en {delay:.2f} segundos...")
                time.sleep(delay)
        
        # Si llegamos aquí, algo salió mal
        raise last_exception or Exception("Error desconocido en RetryStrategy")
    
    def _is_valid_result(self, result: Any) -> bool:
        """
        Verifica si un resultado es válido.
        
        Args:
            result: Resultado a verificar
            
        Returns:
            bool: True si el resultado es válido
        """
        if result is None:
            return False
        
        if isinstance(result, str) and not result.strip():
            return False
        
        if isinstance(result, dict) and not result:
            return False
        
        # Para diccionarios con clave 'text', verificar el contenido
        if isinstance(result, dict) and "text" in result:
            text_content = result["text"]
            return text_content is not None and str(text_content).strip() != ""
        
        return True

# Instancia global por defecto
default_retry_strategy = RetryStrategy()

def with_retry(func: Callable) -> Callable:
    """
    Decorador para agregar reintentos automáticos a una función.
    
    Args:
        func: Función a decorar
        
    Returns:
        Callable: Función decorada con reintentos
    """
    def wrapper(*args, **kwargs):
        return default_retry_strategy.execute(func, *args, **kwargs)
    
    wrapper.__name__ = f"retry_{func.__name__}"
    wrapper.__doc__ = f"Versión con reintentos de {func.__name__}"
    
    return wrapper