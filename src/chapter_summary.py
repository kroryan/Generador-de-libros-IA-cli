from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response

# Importar el sistema unificado de contexto
from unified_context import UnifiedContextManager, ContextMode

# Alias para compatibilidad con código existente
ProgressiveContextManager = UnifiedContextManager

class ChapterSummaryChain(BaseEventChain):
    """Genera resúmenes de capítulos para mantener la coherencia narrativa entre ellos."""
    
    PROMPT_TEMPLATE = """
    Como editor profesional, crea un resumen breve y esencial del siguiente capítulo.
    El resumen debe capturar SOLO los elementos más importantes para mantener coherencia.
    
    IMPORTANTE: El resumen debe estar en español y ser muy conciso (máximo 150 palabras).
    
    Título del libro: {title}
    Capítulo: {chapter_title} (Capítulo {chapter_num} de {total_chapters})
    
    Contenido del capítulo:
    {chapter_content}
    
    <think>
    Identificaré solo los elementos narrativos cruciales:
    1. Eventos principales que afectan la trama general
    2. Desarrollo significativo de personajes principales
    3. Revelaciones importantes o giros en la trama
    4. Elementos específicos que necesitarán continuidad
    
    Seré extremadamente conciso y preciso, enfocándome solo en lo esencial.
    </think>
    
    Genera un resumen breve y esencial:"""

    # Prompt para resumir incremental por secciones
    PROGRESSIVE_SUMMARY_TEMPLATE = """
    Actualiza el resumen existente para incorporar solo los elementos esenciales 
    de la nueva sección. Mantén el resumen muy breve y centrado solo en lo crucial.
    
    IMPORTANTE: Máximo 150 palabras, solo en español.
    
    Título: {title}
    Capítulo: {chapter_title} (Capítulo {chapter_num})
    
    Resumen actual:
    {current_summary}
    
    Nueva sección:
    {new_section}
    
    <think>
    Analizaré qué elementos nuevos son verdaderamente importantes:
    - ¿Introduce algún evento crítico para la trama?
    - ¿Revela información esencial sobre personajes principales?
    - ¿Presenta un giro o cambio significativo?
    
    Incorporaré solo lo verdaderamente relevante, manteniendo el resumen muy conciso.
    </think>
    
    Resumen actualizado:"""

    def extract_key_segments(self, text, max_segments=3, segment_length=1000):
        """
        Extrae segmentos clave del texto usando sistema adaptativo.
        
        MIGRADO: Ahora usa text_segment_extractor.py para lógica adaptativa.
        """
        from text_segment_extractor import extract_key_segments as extract_adaptive
        return extract_adaptive(text, max_segments, segment_length)

    def update_summary_incrementally(self, title, chapter_num, chapter_title, current_summary, new_section, total_chapters=None):
        """Actualiza un resumen existente incorporando nueva información esencial"""
        print_progress(f"Actualizando resumen incremental del capítulo {chapter_num}...")
        
        # Si no hay resumen actual, crear uno básico
        if not current_summary or current_summary.strip() == "":
            current_summary = f"Inicio del capítulo {chapter_num} ({chapter_title})."
        
        try:
            # Extraer solo fragmentos clave de la nueva sección
            if len(new_section) > 1500:
                # Tomar solo inicio y final (donde suele estar la información clave)
                summary_section = new_section[:750] + "\n\n[...]\n\n" + new_section[-750:]
            else:
                summary_section = new_section
                
            # Si total_chapters no se proporciona, usar un valor predeterminado
            if total_chapters is None:
                total_chapters = 10  # Valor predeterminado razonable
                
            # El parámetro chapter_content es diferente de new_section
            # new_section es el texto nuevo a incorporar en el resumen
            # chapter_content es necesario para el template base, pero no para el incremental
            
            # Usar el template PROGRESSIVE_SUMMARY_TEMPLATE con los parámetros correctos
            result = self.invoke(
                title=clean_think_tags(title),
                chapter_num=chapter_num,
                chapter_title=clean_think_tags(chapter_title),
                current_summary=clean_think_tags(current_summary),
                new_section=clean_think_tags(summary_section)
            )
            
            if not result:
                raise ValueError("No se generó contenido válido para el resumen")
                
            # Limitar longitud del resumen incremental para evitar crecimiento excesivo
            if len(result) > 500:
                print_progress("Resumen demasiado largo, truncando...")
                result = result[:500] + "..."
                
            return result
            
        except Exception as e:
            print_progress(f"Error actualizando resumen incremental: {str(e)}")
            return current_summary  # Devolver el resumen anterior sin cambios
    
    def run(self, title, chapter_num, chapter_title, chapter_content, total_chapters):
        """Genera un resumen final conciso del capítulo"""
        print_progress(f"Generando resumen final del capítulo {chapter_num}: {chapter_title}")
        
        try:
            # Preparar el contenido de manera más eficiente
            summarized_content = self.extract_key_segments(chapter_content, 
                                                         max_segments=3, 
                                                         segment_length=1000)
            
            # Corrección: Añadir explícitamente el parámetro template con el valor PROMPT_TEMPLATE
            result = self.invoke(
                template=self.PROMPT_TEMPLATE,
                title=clean_think_tags(title),
                chapter_num=chapter_num,
                chapter_title=clean_think_tags(chapter_title),
                chapter_content=clean_think_tags(summarized_content),
                total_chapters=total_chapters
            )
            
            if not result:
                raise ValueError("No se generó contenido válido para el resumen")
            
            # Limitar longitud del resumen final para no sobrecargar el contexto
            if len(result) > 300:
                print_progress("Resumen final demasiado largo, truncando...")
                result = result[:300] + "..."
            
            print_progress(f"Resumen final del capítulo {chapter_num} completado")
            return result
            
        except Exception as e:
            print_progress(f"Error generando resumen para el capítulo {chapter_num}: {str(e)}")
            return f"Capítulo {chapter_num}: Continúa la historia."
