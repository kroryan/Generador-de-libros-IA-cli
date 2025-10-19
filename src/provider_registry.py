"""
Registry centralizado de proveedores LLM con gestión de configuración y health checks.
Elimina la búsqueda manual de proveedores y centraliza la lógica de detección.
"""

import os
import time
import threading
from typing import Dict, List, Optional, Callable, Type, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy" 
    UNKNOWN = "unknown"

@dataclass
class ProviderConfig:
    """Configuración de un proveedor LLM"""
    name: str
    api_key: str
    api_base: str
    model: str
    priority: int
    health_check: Optional[Callable[[], bool]] = None
    client_class: Optional[Type] = None
    additional_params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}
    
    def is_configured(self) -> bool:
        """Verifica si el proveedor está correctamente configurado"""
        # Ollama no necesita API key
        if self.name.lower() == "ollama":
            return bool(self.api_base and self.model)
        
        # Otros proveedores necesitan API key
        return bool(self.api_key and self.model)

class HealthCheckCache:
    """Cache de health checks para evitar verificaciones innecesarias"""
    
    def __init__(self, ttl: float = None):
        self.ttl = ttl or float(os.environ.get("HEALTH_CHECK_CACHE_TTL", "30"))
        self._cache: Dict[str, tuple[bool, float]] = {}
        self._lock = threading.Lock()
    
    def get(self, provider: str) -> Optional[bool]:
        """Obtiene resultado cached de health check"""
        with self._lock:
            if provider in self._cache:
                result, timestamp = self._cache[provider]
                if time.time() - timestamp < self.ttl:
                    return result
                else:
                    # Cache expirado
                    del self._cache[provider]
            return None
    
    def set(self, provider: str, result: bool):
        """Guarda resultado de health check en cache"""
        with self._lock:
            self._cache[provider] = (result, time.time())
    
    def invalidate(self, provider: str):
        """Invalida el cache para un proveedor específico"""
        with self._lock:
            if provider in self._cache:
                del self._cache[provider]
    
    def clear(self):
        """Limpia todo el cache"""
        with self._lock:
            self._cache.clear()

class ProviderRegistry:
    """
    Registry centralizado de proveedores LLM.
    Gestiona configuración, health checks y selección de proveedores.
    """
    
    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._health_cache = HealthCheckCache()
        self._lock = threading.Lock()
        self._discovered = False
        
        # Configuración desde variables de entorno
        self.health_check_enabled = os.environ.get("PROVIDER_HEALTH_CHECK_ENABLED", "true").lower() == "true"
        self.health_check_timeout = float(os.environ.get("PROVIDER_HEALTH_CHECK_TIMEOUT", "2"))
        
        # Orden de prioridad por defecto
        priority_order = os.environ.get("PROVIDER_PRIORITY_ORDER", "groq,openai,deepseek,anthropic,ollama")
        self.default_priorities = {name.strip(): i for i, name in enumerate(priority_order.split(","))}
    
    def register_provider(self, config: ProviderConfig):
        """
        Registra un proveedor en el registry.
        
        Args:
            config: Configuración del proveedor
        """
        # No usar lock aquí ya que puede ser llamado desde discover_providers
        # que ya tiene el lock adquirido
        self._providers[config.name] = config
        logger.info(f"Proveedor registrado: {config.name} (prioridad: {config.priority})")
    
    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """
        Obtiene la configuración de un proveedor específico.
        
        Args:
            name: Nombre del proveedor
            
        Returns:
            ProviderConfig o None si no existe
        """
        if not self._discovered:
            self.discover_providers()
        
        return self._providers.get(name)
    
    def get_available_providers(self, exclude: Optional[List[str]] = None) -> List[ProviderConfig]:
        """
        Obtiene lista de proveedores disponibles ordenados por prioridad.
        
        Args:
            exclude: Lista de proveedores a excluir
            
        Returns:
            Lista de ProviderConfig ordenada por prioridad
        """
        if not self._discovered:
            self.discover_providers()
        
        exclude = exclude or []
        available = []
        
        for name, config in self._providers.items():
            if name not in exclude and config.is_configured():
                # Verificar health si está habilitado
                if self.health_check_enabled:
                    status = self._check_provider_health(config)
                    if status != ProviderStatus.HEALTHY:
                        logger.debug(f"Proveedor {name} no saludable, excluyendo")
                        continue
                
                available.append(config)
        
        # Ordenar por prioridad
        available.sort(key=lambda p: p.priority)
        return available
    
    def discover_providers(self):
        """
        Descubre automáticamente proveedores configurados desde variables de entorno.
        Solo se ejecuta una vez para optimizar rendimiento.
        """
        with self._lock:
            if self._discovered:
                return
            
            logger.info("Descubriendo proveedores configurados...")
            
            # Proveedores conocidos con sus configuraciones por defecto
            known_providers = {
                "groq": {
                    "api_base": "https://api.groq.com/openai/v1",
                    "client_class": "ChatOpenAI"
                },
                "openai": {
                    "api_base": "https://api.openai.com/v1",
                    "client_class": "ChatOpenAI"
                },
                "deepseek": {
                    "api_base": "https://api.deepseek.com",
                    "client_class": "ChatOpenAI"
                },
                "anthropic": {
                    "api_base": "https://api.anthropic.com/v1",
                    "client_class": "ChatAnthropic"
                },
                "ollama": {
                    "api_base": "http://localhost:11434",
                    "client_class": "ChatOllama"
                }
            }
            
            # Descubrir proveedores conocidos
            for provider_name, defaults in known_providers.items():
                self._discover_provider(provider_name, defaults)
            
            # Descubrir proveedores personalizados
            self._discover_custom_providers()
            
            self._discovered = True
            logger.info(f"Descubrimiento completado. {len(self._providers)} proveedores registrados.")
    
    def _discover_provider(self, provider_name: str, defaults: dict):
        """Descubre un proveedor específico desde variables de entorno"""
        logger.debug(f"DEBUG: Iniciando discovery para {provider_name}")
        
        upper_name = provider_name.upper()
        logger.debug(f"DEBUG: upper_name = {upper_name}")
        
        # Obtener configuración desde env vars
        api_key = os.environ.get(f"{upper_name}_API_KEY", "")
        api_base = os.environ.get(f"{upper_name}_API_BASE", defaults.get("api_base", ""))
        model = os.environ.get(f"{upper_name}_MODEL", "")
        
        logger.debug(f"DEBUG: api_key = '{api_key}', api_base = '{api_base}', model = '{model}'")
        
        # Determinar prioridad
        priority = self.default_priorities.get(provider_name, 999)
        logger.debug(f"DEBUG: priority = {priority}")
        
        # Solo registrar si está configurado
        config = ProviderConfig(
            name=provider_name,
            api_key=api_key,
            api_base=api_base,
            model=model,
            priority=priority,
            health_check=None,  # No hacer health check durante discovery
            client_class=defaults.get("client_class")
        )
        
        logger.debug(f"DEBUG: config creado")
        
        is_configured = config.is_configured()
        logger.debug(f"DEBUG: is_configured = {is_configured}")
        
        if is_configured:
            logger.debug(f"DEBUG: Registrando proveedor {provider_name}")
            self.register_provider(config)
            logger.debug(f"DEBUG: Proveedor {provider_name} registrado exitosamente")
        else:
            logger.debug(f"Proveedor {provider_name} no configurado correctamente, omitiendo")
    
    def _discover_custom_providers(self):
        """Descubre proveedores personalizados desde variables de entorno"""
        # Buscar patrones API_KEY que no sean de proveedores conocidos
        known_keys = {"GROQ_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"}
        
        for key, value in os.environ.items():
            if key.endswith("_API_KEY") and key not in known_keys and value:
                provider_name = key[:-8].lower()  # Remover "_API_KEY"
                
                api_base = os.environ.get(f"{provider_name.upper()}_API_BASE", "")
                model = os.environ.get(f"{provider_name.upper()}_MODEL", "")
                
                if api_base and model:
                    config = ProviderConfig(
                        name=provider_name,
                        api_key=value,
                        api_base=api_base,
                        model=model,
                        priority=self.default_priorities.get(provider_name, 999),
                        health_check=None,  # Sin health check para proveedores personalizados
                        client_class="ChatOpenAI"  # Asumir compatibilidad OpenAI
                    )
                    self.register_provider(config)
                    logger.info(f"Proveedor personalizado descubierto: {provider_name}")
    
    def _get_health_check_function(self, provider_name: str) -> Optional[Callable[[], bool]]:
        """Obtiene función de health check para un proveedor específico"""
        if provider_name == "ollama":
            return self._ollama_health_check
        # Otros proveedores podrían tener sus propios health checks
        return None
    
    def _ollama_health_check(self) -> bool:
        """Health check específico para Ollama"""
        try:
            import requests
            ollama_config = self.get_provider("ollama")
            if not ollama_config:
                return False
            
            api_base = ollama_config.api_base.rstrip("/")
            response = requests.get(
                f"{api_base}/api/tags", 
                timeout=self.health_check_timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama health check falló: {e}")
            return False
    
    def _check_provider_health(self, config: ProviderConfig) -> ProviderStatus:
        """
        Verifica la salud de un proveedor usando cache.
        
        Args:
            config: Configuración del proveedor
            
        Returns:
            ProviderStatus: Estado de salud del proveedor
        """
        # Verificar cache primero
        cached_result = self._health_cache.get(config.name)
        if cached_result is not None:
            return ProviderStatus.HEALTHY if cached_result else ProviderStatus.UNHEALTHY
        
        # Ejecutar health check
        if config.health_check:
            try:
                result = config.health_check()
                self._health_cache.set(config.name, result)
                return ProviderStatus.HEALTHY if result else ProviderStatus.UNHEALTHY
            except Exception as e:
                logger.warning(f"Health check falló para {config.name}: {e}")
                self._health_cache.set(config.name, False)
                return ProviderStatus.UNHEALTHY
        
        # Sin health check, asumir saludable si está configurado
        return ProviderStatus.UNKNOWN
    
    def force_health_check(self, provider_name: str) -> bool:
        """
        Fuerza un health check inmediato para un proveedor.
        
        Args:
            provider_name: Nombre del proveedor
            
        Returns:
            bool: True si está saludable
        """
        self._health_cache.invalidate(provider_name)
        config = self.get_provider(provider_name)
        if config:
            status = self._check_provider_health(config)
            return status == ProviderStatus.HEALTHY
        return False
    
    def list_providers(self) -> List[ProviderConfig]:
        """Lista todos los proveedores registrados"""
        if not self._discovered:
            self.discover_providers()
        return list(self._providers.values())
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del registry"""
        if not self._discovered:
            self.discover_providers()
        
        stats = {
            "total_providers": len(self._providers),
            "configured_providers": len([p for p in self._providers.values() if p.is_configured()]),
            "providers": {}
        }
        
        for name, config in self._providers.items():
            stats["providers"][name] = {
                "configured": config.is_configured(),
                "priority": config.priority,
                "model": config.model,
                "health_status": self._check_provider_health(config).value if config.is_configured() else "not_configured"
            }
        
        return stats

# Instancia global del registry
provider_registry = ProviderRegistry()