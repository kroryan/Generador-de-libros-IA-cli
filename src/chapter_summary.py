from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response

class ChapterSummaryChain(BaseEventChain):
    """Genera resúmenes de capítulos para mantener la coherencia narrativa entre ellos."""
    
    PROMPT_TEMPLATE = """
    Como editor profesional, crea un resumen conciso pero completo del siguiente capítulo.
    El resumen debe capturar los elementos esenciales para que otros capítulos mantengan coherencia con este.
    
    IMPORTANTE: El resumen debe estar EXCLUSIVAMENTE en español.
    
    Título del libro: {title}
    Número del capítulo: {chapter_num}
    Capítulo: {chapter_title}
    Total de capítulos: {total_chapters}
    
    Contenido del capítulo:
    {chapter_content}
    
    <think>
    Voy a identificar los elementos narrativos más importantes:
    1. Eventos principales y su orden cronológico
    2. Desarrollo de personajes clave y sus motivaciones
    3. Revelaciones importantes o giros en la trama
    4. Cambios en conflictos o situaciones centrales
    5. Elementos que necesitarán continuidad en capítulos posteriores
    
    Mantendré el resumen conciso (máximo 200 palabras) pero incluiré todos los detalles críticos.
    </think>
    
    Genera un resumen detallado que sirva como referencia para mantener la coherencia narrativa:"""

    def run(self, title, chapter_num, chapter_title, chapter_content, total_chapters):
        """Genera un resumen del capítulo para mantener coherencia narrativa."""
        print_progress(f"Generando resumen del capítulo {chapter_num}: {chapter_title}")
        
        try:
            # Acortar el contenido si es muy largo para evitar sobrecargar el modelo
            if len(chapter_content) > 10000:
                summarized_content = chapter_content[:4000] + "\n...\n" + chapter_content[-4000:]
            else:
                summarized_content = chapter_content
                
            result = self.invoke(
                title=clean_think_tags(title),
                chapter_num=chapter_num,
                chapter_title=clean_think_tags(chapter_title),
                chapter_content=clean_think_tags(summarized_content),
                total_chapters=total_chapters
            )
            
            if not result:
                raise ValueError("No se generó contenido válido para el resumen")
                
            print_progress(f"Resumen del capítulo {chapter_num} completado")
            return result
            
        except Exception as e:
            print_progress(f"Error generando resumen para el capítulo {chapter_num}: {str(e)}")
            return f"Resumen no disponible para el capítulo {chapter_num}: {chapter_title}"