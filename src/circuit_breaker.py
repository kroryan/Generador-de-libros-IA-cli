"""
Implementación del patrón Circuit Breaker para evitar cascadas de fallos.
Protege el sistema de llamadas repetidas a servicios que están fallando.
"""

import time
import os
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass
import logging
import threading

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Funcionamiento normal
    OPEN = "open"          # Bloqueando llamadas
    HALF_OPEN = "half_open" # Permitiendo llamadas de prueba

@dataclass
class CircuitBreakerConfig:
    """Configuración para el Circuit Breaker"""
    failure_threshold: int
    timeout: float
    half_open_attempts: int
    
    @classmethod
    def from_env(cls) -> 'CircuitBreakerConfig':
        """Crea configuración desde variables de entorno"""
        return cls(
            failure_threshold=int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", "5")),
            timeout=float(os.environ.get("CIRCUIT_BREAKER_TIMEOUT", "60")),
            half_open_attempts=int(os.environ.get("CIRCUIT_BREAKER_HALF_OPEN_ATTEMPTS", "1"))
        )

class CircuitBreakerOpenException(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto"""
    pass

class CircuitBreaker:
    """
    Implementación del patrón Circuit Breaker.
    
    Estados:
    - CLOSED: Funcionamiento normal, todas las llamadas pasan
    - OPEN: Bloqueando llamadas, devuelve error inmediatamente
    - HALF_OPEN: Permitiendo llamadas de prueba limitadas
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig.from_env()
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_attempts = 0
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Estado actual del circuit breaker"""
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Número de fallos consecutivos"""
        return self._failure_count
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Ejecuta una función a través del circuit breaker.
        
        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados
            
        Returns:
            Any: Resultado de la función
            
        Raises:
            CircuitBreakerOpenException: Si el circuit breaker está abierto
        """
        with self._lock:
            # Verificar si necesitamos cambiar de OPEN a HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                    logger.info(f"Circuit breaker '{self.name}' cambiando a HALF_OPEN")
                else:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{self.name}' está abierto. "
                        f"Reintente en {self._time_until_retry():.1f} segundos."
                    )
            
            # Si estamos en HALF_OPEN, verificar límite de intentos
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_attempts >= self.config.half_open_attempts:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = time.time()
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{self.name}' volviendo a OPEN después de fallos en HALF_OPEN"
                    )
                self._half_open_attempts += 1
        
        # Ejecutar la función
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure()
            raise e
    
    def _record_success(self):
        """Registra una llamada exitosa"""
        with self._lock:
            logger.debug(f"Circuit breaker '{self.name}': Éxito registrado")
            
            if self._state == CircuitState.HALF_OPEN:
                # Éxito en HALF_OPEN -> volver a CLOSED
                self._state = CircuitState.CLOSED
                logger.info(f"Circuit breaker '{self.name}' cambiando a CLOSED después de éxito")
            
            # Resetear contador de fallos
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_attempts = 0
    
    def _record_failure(self):
        """Registra una llamada fallida"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            logger.warning(
                f"Circuit breaker '{self.name}': Fallo #{self._failure_count} registrado"
            )
            
            # Verificar si debemos abrir el circuit breaker
            if (self._state == CircuitState.CLOSED and 
                self._failure_count >= self.config.failure_threshold):
                
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker '{self.name}' ABIERTO después de "
                    f"{self._failure_count} fallos consecutivos"
                )
            
            elif self._state == CircuitState.HALF_OPEN:
                # Fallo en HALF_OPEN -> volver a OPEN
                self._state = CircuitState.OPEN
                self._half_open_attempts = 0
                logger.error(
                    f"Circuit breaker '{self.name}' volviendo a OPEN después de fallo en HALF_OPEN"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Verifica si es tiempo de intentar resetear el circuit breaker"""
        if self._last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.config.timeout
    
    def _time_until_retry(self) -> float:
        """Calcula cuánto tiempo falta para permitir reintentos"""
        if self._last_failure_time is None:
            return 0
        
        time_since_failure = time.time() - self._last_failure_time
        return max(0, self.config.timeout - time_since_failure)
    
    def reset(self):
        """Resetea manualmente el circuit breaker al estado CLOSED"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_attempts = 0
            logger.info(f"Circuit breaker '{self.name}' reseteado manualmente")
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del circuit breaker"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "time_until_retry": self._time_until_retry() if self._state == CircuitState.OPEN else 0,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "timeout": self.config.timeout,
                    "half_open_attempts": self.config.half_open_attempts
                }
            }

class CircuitBreakerRegistry:
    """Registro global de circuit breakers para diferentes servicios"""
    
    def __init__(self):
        self._circuit_breakers = {}
        self._lock = threading.Lock()
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Obtiene o crea un circuit breaker para un servicio específico.
        
        Args:
            name: Nombre del servicio/circuit breaker
            config: Configuración opcional, si None usa la configuración por defecto
            
        Returns:
            CircuitBreaker: Instancia del circuit breaker
        """
        with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name, config)
                logger.info(f"Creado nuevo circuit breaker: '{name}'")
            
            return self._circuit_breakers[name]
    
    def get_all_stats(self) -> dict:
        """Obtiene estadísticas de todos los circuit breakers"""
        with self._lock:
            return {
                name: cb.get_stats() 
                for name, cb in self._circuit_breakers.items()
            }
    
    def reset_all(self):
        """Resetea todos los circuit breakers"""
        with self._lock:
            for cb in self._circuit_breakers.values():
                cb.reset()
            logger.info("Todos los circuit breakers han sido reseteados")

# Instancia global del registro
circuit_breaker_registry = CircuitBreakerRegistry()

def with_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorador para agregar circuit breaker a una función.
    
    Args:
        name: Nombre del circuit breaker
        config: Configuración opcional
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            cb = circuit_breaker_registry.get_circuit_breaker(name, config)
            return cb.call(func, *args, **kwargs)
        
        wrapper.__name__ = f"cb_{func.__name__}"
        wrapper.__doc__ = f"Versión con circuit breaker de {func.__name__}"
        
        return wrapper
    
    return decorator