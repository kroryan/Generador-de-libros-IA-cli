from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response
from config.defaults import get_config
from retry_strategy import RetryableException
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Importar el sistema unificado de contexto
from unified_context import UnifiedContextManager, ContextMode

# Alias para compatibilidad con código existente
ProgressiveContextManager = UnifiedContextManager

_summary_config = get_config().summary

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

    def extract_key_segments(self, text, max_segments=None, segment_length=None):
        """
        Extrae segmentos clave del texto usando sistema adaptativo.
        
        MIGRADO: Ahora usa text_segment_extractor.py para lógica adaptativa.
        """
        if max_segments is None:
            max_segments = _summary_config.chapter_summary_max_segments
        if segment_length is None:
            segment_length = _summary_config.chapter_summary_segment_length
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
            section_limit = _summary_config.savepoint_section_max_chars
            if len(new_section) > section_limit:
                # Tomar solo inicio y final (donde suele estar la información clave)
                head_len = section_limit // 2
                tail_len = section_limit - head_len
                summary_section = new_section[:head_len] + "\n\n[...]\n\n" + new_section[-tail_len:]
            else:
                summary_section = new_section

            prompt = PromptTemplate(
                template=self.PROGRESSIVE_SUMMARY_TEMPLATE,
                input_variables=["title", "chapter_num", "chapter_title", "current_summary", "new_section"]
            )
            chain = LLMChain(llm=self.llm, prompt=prompt, verbose=True)

            def _execute():
                result = chain({
                    "title": clean_think_tags(title),
                    "chapter_num": chapter_num,
                    "chapter_title": clean_think_tags(chapter_title),
                    "current_summary": clean_think_tags(current_summary),
                    "new_section": clean_think_tags(summary_section)
                })

                text_result = extract_content_from_llm_response(result)
                cleaned = clean_think_tags(text_result)
                if not cleaned or len(cleaned.strip()) < _summary_config.savepoint_summary_min_chars:
                    raise RetryableException("Resumen incremental vacio o muy corto")
                return cleaned

            result = self.retry_strategy.execute(_execute)

            # Limitar longitud del resumen incremental para evitar crecimiento excesivo
            if len(result) > _summary_config.savepoint_summary_max_chars:
                print_progress("Resumen demasiado largo, truncando...")
                result = result[:_summary_config.savepoint_summary_max_chars] + "..."
                
            return result
            
        except Exception as e:
            print_progress(f"Error actualizando resumen incremental: {str(e)}")
            return current_summary  # Devolver el resumen anterior sin cambios
    
    def run(self, title, chapter_num, chapter_title, chapter_content, total_chapters):
        """Genera un resumen final conciso del capítulo"""
        print_progress(f"Generando resumen final del capítulo {chapter_num}: {chapter_title}")
        
        try:
            # Preparar el contenido de manera más eficiente
            summarized_content = self.extract_key_segments(
                chapter_content,
                max_segments=_summary_config.chapter_summary_max_segments,
                segment_length=_summary_config.chapter_summary_segment_length
            )
            
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
            if len(result) > _summary_config.chapter_summary_max_chars:
                print_progress("Resumen final demasiado largo, truncando...")
                result = result[:_summary_config.chapter_summary_max_chars] + "..."
            
            print_progress(f"Resumen final del capítulo {chapter_num} completado")
            return result
            
        except Exception as e:
            print_progress(f"Error generando resumen para el capítulo {chapter_num}: {str(e)}")
            return f"Capítulo {chapter_num}: Continúa la historia."
