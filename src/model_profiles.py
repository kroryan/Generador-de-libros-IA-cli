"""
Gestor de perfiles de modelos LLM.
Reemplaza la detección frágil basada en strings con un sistema robusto y configurable.
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from logging_config import get_logger

logger = get_logger("model_profiles")

@dataclass
class ModelProfile:
    """Perfil completo de un modelo LLM"""
    name: str
    display_name: str
    provider: str
    size_category: str  # small, standard, large
    context_window: int
    max_output_tokens: int
    supports_streaming: bool
    cost_per_1k_tokens: float
    performance_tier: str  # local, fast, balanced, efficient, premium
    recommended_use: List[str]
    limitations: List[str]
    parameters: Dict[str, Any]
    
    def is_suitable_for(self, use_case: str) -> bool:
        """Verifica si el modelo es adecuado para un caso de uso específico"""
        return use_case in self.recommended_use
    
    def has_limitation(self, limitation: str) -> bool:
        """Verifica si el modelo tiene una limitación específica"""
        return limitation in self.limitations
    
    def get_optimal_parameters(self) -> Dict[str, Any]:
        """Obtiene parámetros optimizados para este modelo"""
        return self.parameters.copy()
    
    def estimate_tokens_needed(self, text_length: int) -> int:
        """Estima tokens necesarios basado en longitud del texto"""
        # Aproximación: 1 token ≈ 4 caracteres para texto en español
        return text_length // 4
    
    def can_handle_context(self, estimated_tokens: int) -> bool:
        """Verifica si el modelo puede manejar el contexto estimado"""
        # Reservar 20% del contexto para la respuesta
        available_context = int(self.context_window * 0.8)
        return estimated_tokens <= available_context

class ModelProfileManager:
    """
    Gestor centralizado de perfiles de modelos.
    Proporciona información detallada y selección inteligente de modelos.
    """
    
    def __init__(self, profiles_path: Optional[str] = None):
        self.profiles_path = profiles_path or self._get_default_profiles_path()
        self.profiles: Dict[str, ModelProfile] = {}
        self.size_categories: Dict[str, Dict] = {}
        self.performance_tiers: Dict[str, Dict] = {}
        self._load_profiles()
    
    def _get_default_profiles_path(self) -> str:
        """Obtiene la ruta por defecto del archivo de perfiles"""
        # Buscar en diferentes ubicaciones
        possible_paths = [
            os.path.join(os.getcwd(), "config", "model_profiles.json"),
            os.path.join(os.path.dirname(__file__), "..", "config", "model_profiles.json"),
            os.path.join(os.path.expanduser("~"), ".llm_profiles", "model_profiles.json")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Si no existe, usar la primera ruta como default
        return possible_paths[0]
    
    def _load_profiles(self):
        """Carga perfiles desde el archivo JSON"""
        try:
            if not os.path.exists(self.profiles_path):
                logger.warning(f"Archivo de perfiles no encontrado: {self.profiles_path}")
                self._create_minimal_profiles()
                return
            
            with open(self.profiles_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Cargar perfiles de modelos
            for name, profile_data in data.get("profiles", {}).items():
                try:
                    profile = ModelProfile(
                        name=name,
                        display_name=profile_data["display_name"],
                        provider=profile_data["provider"],
                        size_category=profile_data["size_category"],
                        context_window=profile_data["context_window"],
                        max_output_tokens=profile_data["max_output_tokens"],
                        supports_streaming=profile_data["supports_streaming"],
                        cost_per_1k_tokens=profile_data["cost_per_1k_tokens"],
                        performance_tier=profile_data["performance_tier"],
                        recommended_use=profile_data["recommended_use"],
                        limitations=profile_data["limitations"],
                        parameters=profile_data["parameters"]
                    )
                    self.profiles[name] = profile
                except KeyError as e:
                    logger.warning(f"Perfil incompleto para {name}: falta {e}")
            
            # Cargar categorías y tiers
            self.size_categories = data.get("size_categories", {})
            self.performance_tiers = data.get("performance_tiers", {})
            
            logger.info(f"Cargados {len(self.profiles)} perfiles de modelos")
            
        except Exception as e:
            logger.error(f"Error cargando perfiles: {e}")
            self._create_minimal_profiles()
    
    def _create_minimal_profiles(self):
        """Crea perfiles mínimos si no se puede cargar el archivo"""
        logger.info("Creando perfiles mínimos de fallback")
        
        # Perfiles básicos para proveedores comunes
        minimal_profiles = {
            "gpt-4": ModelProfile(
                name="gpt-4",
                display_name="GPT-4",
                provider="openai",
                size_category="large",
                context_window=8192,
                max_output_tokens=4096,
                supports_streaming=True,
                cost_per_1k_tokens=0.03,
                performance_tier="premium",
                recommended_use=["general", "writing", "analysis"],
                limitations=["high_cost"],
                parameters={"temperature": 0.7, "top_p": 1.0}
            ),
            "llama3": ModelProfile(
                name="llama3",
                display_name="Llama 3",
                provider="ollama",
                size_category="standard",
                context_window=8192,
                max_output_tokens=4096,
                supports_streaming=True,
                cost_per_1k_tokens=0.0,
                performance_tier="local",
                recommended_use=["general", "privacy_sensitive"],
                limitations=["requires_local_setup"],
                parameters={"temperature": 0.7, "top_p": 0.9, "top_k": 50}
            )
        }
        
        self.profiles = minimal_profiles
    
    def get_profile(self, model_name: str) -> Optional[ModelProfile]:
        """
        Obtiene el perfil de un modelo específico.
        
        Args:
            model_name: Nombre del modelo
            
        Returns:
            ModelProfile o None si no se encuentra
        """
        return self.profiles.get(model_name)
    
    def detect_model_profile(self, model_name: str, provider: str = None) -> Optional[ModelProfile]:
        """
        Detecta el perfil de un modelo basado en su nombre y proveedor.
        Reemplaza la detección frágil basada en strings.
        
        Args:
            model_name: Nombre del modelo
            provider: Proveedor opcional para mejorar la detección
            
        Returns:
            ModelProfile o None si no se puede detectar
        """
        # Búsqueda exacta primero
        if model_name in self.profiles:
            return self.profiles[model_name]
        
        # Búsqueda por nombre parcial
        model_lower = model_name.lower()
        
        for profile in self.profiles.values():
            # Si se especifica proveedor, debe coincidir
            if provider and profile.provider != provider:
                continue
            
            profile_name_lower = profile.name.lower()
            
            # Coincidencia exacta ignorando case
            if profile_name_lower == model_lower:
                return profile
            
            # Coincidencia parcial (el nombre del perfil está en el nombre del modelo)
            if profile_name_lower in model_lower or model_lower in profile_name_lower:
                logger.info(f"Detección parcial: {model_name} -> {profile.name}")
                return profile
        
        # Si no se encuentra, intentar crear perfil dinámico
        return self._create_dynamic_profile(model_name, provider)
    
    def _create_dynamic_profile(self, model_name: str, provider: str = None) -> Optional[ModelProfile]:
        """
        Crea un perfil dinámico para modelos no reconocidos.
        Usa heurísticas inteligentes en lugar de detección por strings.
        """
        logger.info(f"Creando perfil dinámico para: {model_name}")
        
        # Valores por defecto conservadores
        profile_data = {
            "name": model_name,
            "display_name": model_name,
            "provider": provider or "unknown",
            "size_category": "standard",
            "context_window": 4096,
            "max_output_tokens": 2048,
            "supports_streaming": True,
            "cost_per_1k_tokens": 0.0,
            "performance_tier": "balanced",
            "recommended_use": ["general"],
            "limitations": ["unknown_capabilities"],
            "parameters": {"temperature": 0.7}
        }
        
        # Ajustar basado en el proveedor
        if provider:
            if provider == "ollama":
                profile_data.update({
                    "cost_per_1k_tokens": 0.0,
                    "performance_tier": "local",
                    "limitations": ["requires_local_setup"],
                    "parameters": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 50,
                        "repeat_penalty": 1.1
                    }
                })
            elif provider in ["openai", "groq"]:
                profile_data.update({
                    "context_window": 8192,
                    "max_output_tokens": 4096
                })
        
        # Ajustar basado en patrones en el nombre (de forma conservadora)
        model_lower = model_name.lower()
        
        # Detectar tamaño por patrones comunes pero conservadores
        if any(pattern in model_lower for pattern in ["gpt-4", "claude-3", "70b", "large"]):
            profile_data.update({
                "size_category": "large",
                "context_window": 8192,
                "max_output_tokens": 4096
            })
        elif any(pattern in model_lower for pattern in ["3.5", "7b", "8b", "small"]):
            profile_data.update({
                "size_category": "standard",
                "context_window": 4096,
                "max_output_tokens": 2048
            })
        
        try:
            return ModelProfile(**profile_data)
        except Exception as e:
            logger.error(f"Error creando perfil dinámico: {e}")
            return None
    
    def get_models_by_category(self, size_category: str) -> List[ModelProfile]:
        """Obtiene todos los modelos de una categoría de tamaño específica"""
        return [profile for profile in self.profiles.values() 
                if profile.size_category == size_category]
    
    def get_models_by_provider(self, provider: str) -> List[ModelProfile]:
        """Obtiene todos los modelos de un proveedor específico"""
        return [profile for profile in self.profiles.values() 
                if profile.provider == provider]
    
    def get_models_for_use_case(self, use_case: str) -> List[ModelProfile]:
        """Obtiene modelos recomendados para un caso de uso específico"""
        suitable_models = [profile for profile in self.profiles.values() 
                          if profile.is_suitable_for(use_case)]
        
        # Ordenar por performance tier y costo
        tier_order = {"local": 0, "fast": 1, "efficient": 2, "balanced": 3, "premium": 4}
        suitable_models.sort(key=lambda p: (tier_order.get(p.performance_tier, 5), p.cost_per_1k_tokens))
        
        return suitable_models
    
    def recommend_model(self, 
                       use_case: str = "general",
                       max_cost: float = None,
                       min_context: int = None,
                       provider_preference: List[str] = None) -> Optional[ModelProfile]:
        """
        Recomienda el mejor modelo basado en criterios específicos.
        
        Args:
            use_case: Caso de uso específico
            max_cost: Costo máximo por 1K tokens
            min_context: Contexto mínimo requerido
            provider_preference: Lista de proveedores preferidos en orden
            
        Returns:
            ModelProfile recomendado o None
        """
        candidates = self.get_models_for_use_case(use_case)
        
        # Filtrar por costo
        if max_cost is not None:
            candidates = [p for p in candidates if p.cost_per_1k_tokens <= max_cost]
        
        # Filtrar por contexto
        if min_context is not None:
            candidates = [p for p in candidates if p.context_window >= min_context]
        
        # Aplicar preferencia de proveedor
        if provider_preference:
            for preferred_provider in provider_preference:
                provider_models = [p for p in candidates if p.provider == preferred_provider]
                if provider_models:
                    return provider_models[0]  # Ya están ordenados por calidad
        
        # Si no hay preferencia de proveedor, devolver el mejor
        return candidates[0] if candidates else None
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de los perfiles cargados"""
        if not self.profiles:
            return {"total_profiles": 0, "error": "No profiles loaded"}
        
        stats = {
            "total_profiles": len(self.profiles),
            "by_provider": {},
            "by_size_category": {},
            "by_performance_tier": {}
        }
        
        for profile in self.profiles.values():
            # Por proveedor
            if profile.provider not in stats["by_provider"]:
                stats["by_provider"][profile.provider] = 0
            stats["by_provider"][profile.provider] += 1
            
            # Por categoría de tamaño
            if profile.size_category not in stats["by_size_category"]:
                stats["by_size_category"][profile.size_category] = 0
            stats["by_size_category"][profile.size_category] += 1
            
            # Por tier de performance
            if profile.performance_tier not in stats["by_performance_tier"]:
                stats["by_performance_tier"][profile.performance_tier] = 0
            stats["by_performance_tier"][profile.performance_tier] += 1
        
        return stats
    
    def reload_profiles(self):
        """Recarga perfiles desde el archivo"""
        self.profiles.clear()
        self._load_profiles()

# Instancia global del gestor de perfiles
model_profile_manager = ModelProfileManager()

# Funciones de conveniencia para mantener compatibilidad
def detect_model_size(llm_or_model_name) -> str:
    """
    Función de compatibilidad que reemplaza detect_model_size original.
    Ahora usa el sistema de perfiles en lugar de detección por strings.
    """
    if hasattr(llm_or_model_name, 'model'):
        model_name = llm_or_model_name.model
    elif hasattr(llm_or_model_name, 'model_name'):
        model_name = llm_or_model_name.model_name
    else:
        model_name = str(llm_or_model_name)
    
    profile = model_profile_manager.detect_model_profile(model_name)
    
    if profile:
        # Mapear categorías del nuevo sistema al sistema anterior
        category_mapping = {
            "small": "small",
            "standard": "standard",
            "large": "large"
        }
        return category_mapping.get(profile.size_category, "standard")
    
    # Fallback al comportamiento anterior solo como último recurso
    logger.warning(f"No se pudo detectar perfil para {model_name}, usando fallback")
    return "standard"

def get_model_context_window(model_name: str) -> int:
    """Obtiene el tamaño de ventana de contexto para un modelo"""
    profile = model_profile_manager.detect_model_profile(model_name)
    return profile.context_window if profile else 4096

def get_model_optimal_parameters(model_name: str, provider: str = None) -> Dict[str, Any]:
    """Obtiene parámetros optimizados para un modelo específico"""
    profile = model_profile_manager.detect_model_profile(model_name, provider)
    return profile.get_optimal_parameters() if profile else {"temperature": 0.7}