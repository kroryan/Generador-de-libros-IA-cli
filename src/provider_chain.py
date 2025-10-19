"""
Implementación del patrón Chain of Responsibility para selección de proveedores LLM.
Elimina la lógica recursiva y caótica de fallbacks del código original.
"""

import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from provider_registry import ProviderConfig, provider_registry
from circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitBreakerOpenException

logger = logging.getLogger(__name__)

@dataclass
class ProviderRequest:
    """Request para obtener un cliente LLM de un proveedor"""
    exclude_providers: List[str]
    common_params: Dict[str, Any]
    callbacks: Optional[List] = None

class ProviderHandler(ABC):
    """Handler base para el patrón Chain of Responsibility"""
    
    def __init__(self):
        self._next_handler: Optional[ProviderHandler] = None
        self._circuit_breaker_registry = CircuitBreakerRegistry()
    
    def set_next(self, handler: 'ProviderHandler') -> 'ProviderHandler':
        """
        Establece el siguiente handler en la cadena.
        
        Args:
            handler: Siguiente handler
            
        Returns:
            ProviderHandler: El handler pasado como parámetro (para chaining)
        """
        self._next_handler = handler
        return handler
    
    def handle(self, request: ProviderRequest) -> Optional[Any]:
        """
        Maneja una request de proveedor. Si no puede manejarla, la pasa al siguiente.
        
        Args:
            request: Request del proveedor
            
        Returns:
            Cliente LLM o None si no se puede manejar
        """
        if self.can_handle(request):
            result = self._handle_internal(request)
            if result is not None:
                return result
        
        # Si no puede manejar o _handle_internal retornó None, pasar al siguiente
        if self._next_handler:
            return self._next_handler.handle(request)
        else:
            return None
    
    @abstractmethod
    def can_handle(self, request: ProviderRequest) -> bool:
        """
        Verifica si este handler puede manejar la request.
        
        Args:
            request: Request del proveedor
            
        Returns:
            bool: True si puede manejar la request
        """
        pass
    
    @abstractmethod
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        """
        Implementación interna del manejo de la request.
        
        Args:
            request: Request del proveedor
            
        Returns:
            Cliente LLM o None si no se puede crear
        """
        pass
    
    def _get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        """Obtiene circuit breaker para un proveedor específico"""
        return self._circuit_breaker_registry.get_circuit_breaker(f"provider_{provider_name}")

class GroqProviderHandler(ProviderHandler):
    """Handler específico para el proveedor Groq"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        return "groq" not in request.exclude_providers
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        config = provider_registry.get_provider("groq")
        if not config or not config.is_configured():
            logger.debug("Groq no configurado")
            return None
        
        try:
            circuit_breaker = self._get_circuit_breaker("groq")
            
            def create_groq_client():
                from langchain_community.chat_models import ChatOpenAI
                
                logger.info(f"Creando cliente Groq: {config.model}")
                return ChatOpenAI(
                    model=config.model,
                    api_key=config.api_key,
                    base_url=config.api_base,
                    **request.common_params
                )
            
            return circuit_breaker.call(create_groq_client)
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker abierto para Groq: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cliente Groq: {e}")
            return None

class OpenAIProviderHandler(ProviderHandler):
    """Handler específico para el proveedor OpenAI"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        return "openai" not in request.exclude_providers
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        config = provider_registry.get_provider("openai")
        if not config or not config.is_configured():
            logger.debug("OpenAI no configurado")
            return None
        
        try:
            circuit_breaker = self._get_circuit_breaker("openai")
            
            def create_openai_client():
                from langchain_community.chat_models import ChatOpenAI
                
                client_params = {
                    "model": config.model,
                    "api_key": config.api_key,
                    **request.common_params
                }
                
                # Solo agregar base_url si es diferente al default de OpenAI
                if config.api_base and config.api_base != "https://api.openai.com/v1":
                    client_params["base_url"] = config.api_base
                    logger.info(f"Usando OpenAI compatible: {config.model} (Base: {config.api_base})")
                else:
                    logger.info(f"Usando OpenAI oficial: {config.model}")
                
                return ChatOpenAI(**client_params)
            
            return circuit_breaker.call(create_openai_client)
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker abierto para OpenAI: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cliente OpenAI: {e}")
            return None

class DeepSeekProviderHandler(ProviderHandler):
    """Handler específico para el proveedor DeepSeek"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        return "deepseek" not in request.exclude_providers
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        config = provider_registry.get_provider("deepseek")
        if not config or not config.is_configured():
            logger.debug("DeepSeek no configurado")
            return None
        
        try:
            circuit_breaker = self._get_circuit_breaker("deepseek")
            
            def create_deepseek_client():
                from langchain_community.chat_models import ChatOpenAI
                
                logger.info(f"Creando cliente DeepSeek: {config.model}")
                return ChatOpenAI(
                    model=config.model,
                    api_key=config.api_key,
                    base_url=config.api_base,
                    **request.common_params
                )
            
            return circuit_breaker.call(create_deepseek_client)
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker abierto para DeepSeek: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cliente DeepSeek: {e}")
            return None

class AnthropicProviderHandler(ProviderHandler):
    """Handler específico para el proveedor Anthropic"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        return "anthropic" not in request.exclude_providers
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        config = provider_registry.get_provider("anthropic")
        if not config or not config.is_configured():
            logger.debug("Anthropic no configurado")
            return None
        
        try:
            circuit_breaker = self._get_circuit_breaker("anthropic")
            
            def create_anthropic_client():
                try:
                    from langchain_anthropic import ChatAnthropic
                    logger.info(f"Creando cliente Anthropic: {config.model}")
                    return ChatAnthropic(
                        model=config.model,
                        anthropic_api_key=config.api_key,
                        **request.common_params
                    )
                except ImportError:
                    logger.error("langchain_anthropic no instalado. Instalar con: pip install langchain-anthropic")
                    raise
            
            return circuit_breaker.call(create_anthropic_client)
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker abierto para Anthropic: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cliente Anthropic: {e}")
            return None

class OllamaProviderHandler(ProviderHandler):
    """Handler específico para el proveedor Ollama"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        return "ollama" not in request.exclude_providers
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        config = provider_registry.get_provider("ollama")
        if not config or not config.is_configured():
            logger.debug("Ollama no configurado")
            return None

        # Solo verificar health check si está habilitado en el registry
        if provider_registry.health_check_enabled:
            if not provider_registry.force_health_check("ollama"):
                logger.warning(f"Ollama no disponible en {config.api_base}")
                return None
        else:
            logger.debug("Health check deshabilitado, asumiendo Ollama disponible")

        try:
            circuit_breaker = self._get_circuit_breaker("ollama")
            
            def create_ollama_client():
                from langchain_community.chat_models import ChatOllama
                
                logger.info(f"Creando cliente Ollama: {config.model}")
                
                # Empezar con common_params y luego asegurar parámetros específicos
                ollama_params = dict(request.common_params)
                
                # Asegurar que estos parámetros estén configurados correctamente
                ollama_params.update({
                    "model": config.model,  # Siempre usar el modelo del config
                    "base_url": config.api_base,
                    "top_k": 50,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                })
                
                logger.debug(f"Parámetros finales de Ollama: {ollama_params}")
                
                return ChatOllama(**ollama_params)
            
            return circuit_breaker.call(create_ollama_client)
            
        except CircuitBreakerOpenException as e:
            logger.warning(f"Circuit breaker abierto para Ollama: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cliente Ollama: {e}")
            return None

class CustomProviderHandler(ProviderHandler):
    """Handler genérico para proveedores personalizados"""
    
    def can_handle(self, request: ProviderRequest) -> bool:
        # Puede manejar cualquier proveedor que no haya sido manejado por handlers específicos
        available_providers = provider_registry.get_available_providers(request.exclude_providers)
        
        # Verificar si hay proveedores personalizados disponibles
        known_providers = {"groq", "openai", "deepseek", "anthropic", "ollama"}
        custom_providers = [p for p in available_providers if p.name not in known_providers]
        
        return len(custom_providers) > 0
    
    def _handle_internal(self, request: ProviderRequest) -> Optional[Any]:
        available_providers = provider_registry.get_available_providers(request.exclude_providers)
        known_providers = {"groq", "openai", "deepseek", "anthropic", "ollama"}
        
        for config in available_providers:
            if config.name not in known_providers:
                try:
                    circuit_breaker = self._get_circuit_breaker(config.name)
                    
                    def create_custom_client():
                        from langchain_community.chat_models import ChatOpenAI
                        
                        logger.info(f"Creando cliente personalizado {config.name}: {config.model}")
                        return ChatOpenAI(
                            model=config.model,
                            api_key=config.api_key,
                            base_url=config.api_base,
                            **request.common_params
                        )
                    
                    return circuit_breaker.call(create_custom_client)
                    
                except CircuitBreakerOpenException as e:
                    logger.warning(f"Circuit breaker abierto para {config.name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error creando cliente {config.name}: {e}")
                    continue
        
        return None

class ProviderChain:
    """
    Cadena de responsabilidad para selección de proveedores LLM.
    Reemplaza la lógica recursiva y caótica del código original.
    """
    
    def __init__(self):
        self._chain = self._build_default_chain()
    
    def _build_default_chain(self) -> ProviderHandler:
        """Construye la cadena de handlers por defecto"""
        groq_handler = GroqProviderHandler()
        openai_handler = OpenAIProviderHandler()
        deepseek_handler = DeepSeekProviderHandler()
        anthropic_handler = AnthropicProviderHandler()
        ollama_handler = OllamaProviderHandler()
        custom_handler = CustomProviderHandler()
        
        # Encadenar handlers en orden de prioridad
        groq_handler.set_next(openai_handler).set_next(deepseek_handler).set_next(
            anthropic_handler
        ).set_next(ollama_handler).set_next(custom_handler)
        
        return groq_handler
    
    def get_client(self, exclude: Optional[List[str]] = None, **common_params) -> Any:
        """
        Obtiene un cliente LLM del primer proveedor disponible.
        
        Args:
            exclude: Lista de proveedores a excluir
            **common_params: Parámetros comunes para el cliente
            
        Returns:
            Cliente LLM configurado
            
        Raises:
            ValueError: Si no se encuentra ningún proveedor disponible
        """
        exclude = exclude or []
        
        # Callbacks por defecto si no se especifican
        if "callbacks" not in common_params:
            from utils import ColoredStreamingCallbackHandler
            common_params["callbacks"] = [ColoredStreamingCallbackHandler()]
        
        request = ProviderRequest(
            exclude_providers=exclude,
            common_params=common_params
        )
        
        logger.info(f"Buscando proveedor LLM (excluyendo: {exclude})")
        
        client = self._chain.handle(request)
        
        if client is None:
            available_providers = provider_registry.get_available_providers(exclude)
            if available_providers:
                available_names = [p.name for p in available_providers]
                raise ValueError(
                    f"No se pudo crear cliente para ningún proveedor disponible: {available_names}. "
                    f"Verifique la configuración y conectividad."
                )
            else:
                raise ValueError(
                    "No se encontró ningún proveedor de LLM configurado y disponible. "
                    "Configure al menos un proveedor en el archivo .env"
                )
        
        return client
    
    def get_llm(self, exclude: Optional[List[str]] = None, **common_params) -> Any:
        """
        Método de conveniencia que es un alias para get_client.
        Mantenido para compatibilidad con código existente.
        
        Args:
            exclude: Lista de proveedores a excluir
            **common_params: Parámetros comunes para el cliente
            
        Returns:
            Cliente LLM configurado
        """
        return self.get_client(exclude=exclude, **common_params)
    
    def get_provider_stats(self) -> dict:
        """Obtiene estadísticas de todos los proveedores"""
        return provider_registry.get_stats()

# Instancia global de la cadena de proveedores
provider_chain = ProviderChain()