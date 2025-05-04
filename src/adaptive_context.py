#esto no hace nada por ahora, solo es un ejemplo de como se puede hacer un sistema de contexto adaptativo

from utils import print_progress, clean_think_tags, extract_content_from_llm_response

"""
Sistema para generar contenido sin restricciones por tipo de modelo.
Todos los modelos se tratan igual, sin limitaciones de contexto.
"""

class AdaptiveContextSystem:
    """
    Sistema simplificado de contexto que trata todos los modelos por igual,
    sin restricciones basadas en tamaño de contexto.
    """
    
    def __init__(self):
        """Inicializa un sistema básico sin clasificación de modelos."""
        pass
        
    def get_context_for_model(self, llm, full_context, context_type="standard"):
        """
        Devuelve el contexto completo sin importar el modelo.
        Trata todos los modelos de la misma manera.
        """
        # Siempre devuelve el contexto completo
        return full_context
    
    def optimize_prompt_for_model(self, llm, prompt, prompt_type="standard"):
        """
        No realiza ninguna optimización, devuelve el prompt original completo.
        """
        # Devolver el prompt sin modificar
        return prompt