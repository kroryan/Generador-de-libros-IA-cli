"""
Sistema de Cálculo Dinámico de Contexto.
Reemplaza límites estáticos con cálculos adaptativos basados en:
- Ventana de contexto real del modelo
- Complejidad narrativa 
- Calidad de resúmenes
"""

from typing import Dict, Optional
from dataclasses import dataclass
from logging_config import get_logger

logger = get_logger("dynamic_context")

@dataclass
class ModelContextProfile:
    """Perfil de contexto detectado del modelo"""
    context_window: int          # Ventana total del modelo
    safe_context_limit: int      # 80% de la ventana (margen de seguridad)
    section_limit: int           # Para previous_paragraphs
    chapter_limit: int           # Para contexto acumulado
    global_limit: int            # Para resumen global
    accumulation_threshold: int  # Trigger para limpieza

    def __post_init__(self):
        """Validar los límites después de la inicialización"""
        if self.safe_context_limit > self.context_window:
            logger.warning(f"Límite seguro ({self.safe_context_limit}) mayor que ventana ({self.context_window})")
            self.safe_context_limit = int(self.context_window * 0.8)

class DynamicContextCalculator:
    """Calcula límites de contexto dinámicamente"""
    
    def __init__(self, model_name: str, provider: str):
        self.model_name = model_name
        self.provider = provider
        self.profile = self._detect_model_profile()
        
        logger.info(f"Calculador dinámico inicializado para {model_name} ({provider})")
        logger.info(f"Ventana: {self.profile.context_window}, "
                   f"Límites: sección={self.profile.section_limit}, "
                   f"capítulo={self.profile.chapter_limit}, "
                   f"global={self.profile.global_limit}")
        
    def _detect_model_profile(self) -> ModelContextProfile:
        """
        Detecta ventana de contexto del modelo.
        Integra con model_profile_manager existente.
        """
        try:
            from model_profiles import model_profile_manager
            
            # Usar sistema existente de detección
            profile = model_profile_manager.detect_model_profile(
                self.model_name, 
                self.provider
            )
            
            if profile:
                context_window = profile.context_window
                logger.info(f"Perfil detectado desde base de datos: {profile.display_name}")
            else:
                # Fallback: heurística por nombre
                context_window = self._estimate_from_name()
                logger.warning(f"Perfil no encontrado, estimando desde nombre: {context_window}")
                
        except ImportError:
            logger.warning("ModelProfileManager no disponible, usando estimación")
            context_window = self._estimate_from_name()
        
        # Calcular límites seguros (80% de la ventana)
        safe_limit = int(context_window * 0.8)
        
        return ModelContextProfile(
            context_window=context_window,
            safe_context_limit=safe_limit,
            section_limit=int(safe_limit * 0.15),      # 15% para secciones
            chapter_limit=int(safe_limit * 0.50),      # 50% para capítulo
            global_limit=int(safe_limit * 0.10),       # 10% para global
            accumulation_threshold=int(safe_limit * 0.70)  # 70% trigger
        )
    
    def _estimate_from_name(self) -> int:
        """Estima ventana por nombre del modelo"""
        name_lower = self.model_name.lower()
        
        # Patrones conocidos - más conservadores para seguridad
        if 'gpt-4' in name_lower:
            if 'turbo' in name_lower or '1106' in name_lower:
                return 128000  # GPT-4 Turbo
            else:
                return 8192    # GPT-4 original
        elif 'gpt-3.5' in name_lower:
            return 16385 if 'turbo' in name_lower else 4096
        elif 'claude-3' in name_lower:
            if 'opus' in name_lower or 'sonnet' in name_lower:
                return 200000  # Claude-3 Opus/Sonnet
            else:
                return 100000  # Claude-3 Haiku
        elif 'claude-2' in name_lower:
            return 100000
        elif 'gemini' in name_lower:
            if 'pro' in name_lower:
                return 32768   # Gemini Pro
            else:
                return 30720   # Gemini estándar
        elif 'deepseek' in name_lower:
            return 4096        # Deepseek generalmente limitado
        elif 'qwen' in name_lower:
            if '32k' in name_lower:
                return 32768
            elif '14b' in name_lower or '72b' in name_lower:
                return 8192
            else:
                return 4096
        elif 'mixtral' in name_lower:
            return 32768
        elif any(x in name_lower for x in ['70b', '8x7b']):
            return 8192        # Modelos grandes típicamente 8K
        elif any(x in name_lower for x in ['7b', '8b', '9b']):
            return 4096        # Modelos pequeños 4K
        elif any(x in name_lower for x in ['13b', '14b']):
            return 8192        # Modelos medianos 8K
        elif 'llama' in name_lower:
            if '2' in name_lower:
                return 4096    # LLaMA 2 4K
            else:
                return 8192    # LLaMA 3/3.1 8K
        else:
            logger.warning(f"Modelo desconocido {self.model_name}, usando 4K por defecto")
            return 4096        # Default conservador
            
    def calculate_dynamic_limits(self, complexity_multiplier: float = 1.0, 
                               quality_factor: float = 1.0) -> Dict[str, int]:
        """
        Calcula límites dinámicos basados en multiplicadores.
        
        Args:
            complexity_multiplier: Factor de complejidad narrativa (1.0-1.6)
            quality_factor: Factor de calidad de resúmenes (0.7-1.5)
            
        Returns:
            Dict con límites actualizados
        """
        base_limits = {
            'section_limit': self.profile.section_limit,
            'chapter_limit': self.profile.chapter_limit,
            'global_limit': self.profile.global_limit,
            'accumulation_threshold': self.profile.accumulation_threshold
        }
        
        # Aplicar multiplicadores
        dynamic_limits = {}
        for key, base_value in base_limits.items():
            # Complejidad aumenta los límites, calidad los puede reducir o aumentar
            adjusted_value = int(base_value * complexity_multiplier * quality_factor)
            
            # No exceder el límite seguro total
            max_allowed = int(self.profile.safe_context_limit * 0.8)  # 80% del límite seguro
            dynamic_limits[key] = min(adjusted_value, max_allowed)
            
        logger.debug(f"Límites dinámicos calculados: {dynamic_limits} "
                    f"(complejidad={complexity_multiplier:.1f}, "
                    f"calidad={quality_factor:.1f})")
                    
        return dynamic_limits
    
    def get_token_estimate(self, text_length: int) -> int:
        """Estima tokens desde longitud de texto (aproximación 4:1)"""
        return text_length // 4
    
    def can_fit_context(self, estimated_text_length: int) -> bool:
        """Verifica si un texto cabe en la ventana de contexto"""
        estimated_tokens = self.get_token_estimate(estimated_text_length)
        return estimated_tokens <= self.profile.safe_context_limit
    
    def get_compression_ratio(self, target_length: int) -> float:
        """Calcula ratio de compresión necesario para ajustar a límites"""
        if target_length <= self.profile.safe_context_limit:
            return 1.0
        
        return self.profile.safe_context_limit / target_length
    
    def get_context_summary(self) -> Dict[str, any]:
        """Retorna resumen de la configuración de contexto"""
        return {
            "model": f"{self.provider}:{self.model_name}",
            "context_window": self.profile.context_window,
            "safe_limit": self.profile.safe_context_limit,
            "limits": {
                "section": self.profile.section_limit,
                "chapter": self.profile.chapter_limit, 
                "global": self.profile.global_limit,
                "accumulation_trigger": self.profile.accumulation_threshold
            },
            "usage_percentages": {
                "section": f"{(self.profile.section_limit / self.profile.safe_context_limit) * 100:.1f}%",
                "chapter": f"{(self.profile.chapter_limit / self.profile.safe_context_limit) * 100:.1f}%",
                "global": f"{(self.profile.global_limit / self.profile.safe_context_limit) * 100:.1f}%"
            }
        }