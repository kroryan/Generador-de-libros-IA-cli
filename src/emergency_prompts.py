"""
Centralización de todos los prompts de emergencia del sistema.
Elimina la duplicación de prompts hardcodeados en múltiples archivos.
"""

from typing import Dict, Any, Optional
import os

class EmergencyPromptGenerator:
    """
    Generador centralizado de prompts de emergencia para situaciones de fallback.
    Mantiene templates reutilizables y permite personalización por contexto.
    """
    
    def __init__(self):
        self._templates = {
            "writing_emergency": """
Escribe un párrafo narrativo para continuar esta historia.

Capítulo: {chapter_title}
Idea a desarrollar: {idea_summary}

IMPORTANTE: Escribe SOLO texto narrativo en español, sin encabezados ni metadata.
""",
            
            "section_regeneration": """
Continúa esta historia de manera natural y coherente.

Contexto: {context_summary}
Último contenido: {previous_content}

Escribe el siguiente párrafo de la historia manteniendo el estilo y la coherencia narrativa.
""",
            
            "summary_emergency": """
Crea un resumen breve de este contenido:

{content}

Resumen en máximo 3 oraciones:
""",
            
            "chapter_continuation": """
Continúa el desarrollo de este capítulo.

Título del capítulo: {chapter_title}
Contexto previo: {previous_context}

Escribe el siguiente párrafo manteniendo la coherencia narrativa:
""",
            
            "simple_narrative": """
Escribe un párrafo narrativo simple y coherente.

Tema: {topic}
Estilo: {style}

Contenido:
""",
            
            "context_recovery": """
Basándote en este contexto limitado, continúa la narración de manera natural.

Información disponible: {available_context}

Continúa la historia:
""",
            
            "fallback_generic": """
Genera contenido narrativo apropiado basado en esta información:

{context}

Respuesta:
"""
        }
    
    def get_emergency_prompt(self, prompt_type: str, **kwargs) -> str:
        """
        Genera un prompt de emergencia del tipo especificado.
        
        Args:
            prompt_type: Tipo de prompt de emergencia
            **kwargs: Variables para sustituir en el template
            
        Returns:
            str: Prompt de emergencia formateado
            
        Raises:
            ValueError: Si el tipo de prompt no existe
        """
        if prompt_type not in self._templates:
            # Usar template genérico como fallback absoluto
            prompt_type = "fallback_generic"
            if "context" not in kwargs:
                kwargs["context"] = str(kwargs)
        
        template = self._templates[prompt_type]
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Si faltan variables, usar template más simple
            missing_var = str(e).strip("'")
            simplified_context = f"Información disponible: {str(kwargs)}"
            
            return self._templates["fallback_generic"].format(context=simplified_context)
    
    def register_template(self, name: str, template: str):
        """
        Registra un nuevo template de prompt de emergencia.
        
        Args:
            name: Nombre del template
            template: Template con placeholders {variable}
        """
        self._templates[name] = template
    
    def get_available_templates(self) -> list:
        """
        Obtiene lista de templates disponibles.
        
        Returns:
            list: Lista de nombres de templates disponibles
        """
        return list(self._templates.keys())
    
    def get_writing_emergency_prompt(
        self, 
        chapter_title: str = "", 
        idea: str = "", 
        max_idea_length: int = 100
    ) -> str:
        """
        Genera prompt de emergencia específico para escritura narrativa.
        Versión simplificada para reemplazar prompts hardcodeados.
        
        Args:
            chapter_title: Título del capítulo actual
            idea: Idea a desarrollar (será truncada si es muy larga)
            max_idea_length: Longitud máxima de la idea
            
        Returns:
            str: Prompt de emergencia para escritura
        """
        # Truncar idea si es muy larga
        idea_summary = idea[:max_idea_length] if idea else "continuar la historia"
        if len(idea) > max_idea_length:
            idea_summary += "..."
        
        return self.get_emergency_prompt(
            "writing_emergency",
            chapter_title=chapter_title or "este capítulo",
            idea_summary=idea_summary
        )
    
    def get_section_regeneration_prompt(
        self,
        context_summary: str = "",
        previous_content: str = "",
        max_context_length: int = 200
    ) -> str:
        """
        Genera prompt de emergencia para regeneración de secciones.
        
        Args:
            context_summary: Resumen del contexto
            previous_content: Contenido previo
            max_context_length: Longitud máxima del contexto
            
        Returns:
            str: Prompt de emergencia para regeneración
        """
        # Truncar contexto si es muy largo
        if len(context_summary) > max_context_length:
            context_summary = context_summary[:max_context_length] + "..."
        
        if len(previous_content) > max_context_length:
            previous_content = previous_content[-max_context_length:]
        
        return self.get_emergency_prompt(
            "section_regeneration",
            context_summary=context_summary or "historia en progreso",
            previous_content=previous_content or "contenido previo"
        )
    
    def get_summary_emergency_prompt(self, content: str = "", max_length: int = 300) -> str:
        """
        Genera prompt de emergencia para creación de resúmenes.
        
        Args:
            content: Contenido a resumir
            max_length: Longitud máxima del contenido
            
        Returns:
            str: Prompt de emergencia para resúmenes
        """
        if len(content) > max_length:
            content = content[:max_length] + "..."
        
        return self.get_emergency_prompt(
            "summary_emergency",
            content=content or "contenido no disponible"
        )

# Instancia global del generador de prompts de emergencia
emergency_prompts = EmergencyPromptGenerator()

# Funciones de conveniencia para compatibilidad con código existente
def get_writing_emergency_prompt(chapter_title: str = "", idea: str = "") -> str:
    """Función de conveniencia para prompts de escritura de emergencia"""
    return emergency_prompts.get_writing_emergency_prompt(chapter_title, idea)

def get_section_regeneration_prompt(context: str = "", previous: str = "") -> str:
    """Función de conveniencia para prompts de regeneración de secciones"""
    return emergency_prompts.get_section_regeneration_prompt(context, previous)

def get_summary_emergency_prompt(content: str = "") -> str:
    """Función de conveniencia para prompts de resúmenes de emergencia"""
    return emergency_prompts.get_summary_emergency_prompt(content)

# Configuración desde variables de entorno
def configure_emergency_prompts_from_env():
    """Configura prompts de emergencia desde variables de entorno si están disponibles"""
    
    # Permitir customización de prompts desde variables de entorno
    env_prefix = "EMERGENCY_PROMPT_"
    
    for key, value in os.environ.items():
        if key.startswith(env_prefix):
            template_name = key[len(env_prefix):].lower()
            emergency_prompts.register_template(template_name, value)

# Configurar automáticamente al importar
configure_emergency_prompts_from_env()