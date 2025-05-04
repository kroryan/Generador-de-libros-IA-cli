from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response

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
        Extrae segmentos clave del texto (inicio, medio y final) de manera más eficiente
        con segmentos más pequeños.
        """
        if len(text) <= segment_length * max_segments:
            return text
            
        segments = []
        
        # Incluir inicio (establece personajes y escenario)
        segments.append(text[:segment_length])
        
        # Si hay espacio para más de 2 segmentos, incluir segmento del medio
        if max_segments > 2:
            # Extraer una sección del medio
            middle_pos = len(text) // 2
            middle_start = max(middle_pos - segment_length // 2, segment_length)
            middle_end = min(middle_start + segment_length, len(text) - segment_length)
            segments.append(text[middle_start:middle_end])
        
        # Incluir final (resoluciones, giros finales)
        segments.append(text[-segment_length:])
        
        # Unir los segmentos con indicadores claros
        result = "INICIO DEL CAPÍTULO:\n" + segments[0]
        
        for i in range(1, len(segments) - 1):
            result += f"\n\n[...PARTE MEDIA DEL CAPÍTULO...]\n\n{segments[i]}"
            
        result += f"\n\n[...FINAL DEL CAPÍTULO...]\n\n{segments[-1]}"
            
        return result

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

class ProgressiveContextManager:
    """
    Sistema simplificado para gestionar el contexto de manera progresiva
    durante la generación del libro.
    Versión modificada para permitir generación continua sin restricciones.
    """
    def __init__(self, framework=""):
        self.framework = framework
        self.book_context = {}
        self.chapter_contexts = {}
        self.global_entities = {}
        self.current_sections = {}
        
    def register_chapter(self, chapter_key, title, summary):
        """Registra información básica de un capítulo"""
        self.chapter_contexts[chapter_key] = {
            "title": title,
            "summary": summary,
            "content": [],
            "entities": {}
        }
    
    def update_chapter_content(self, chapter_key, section_content):
        """Actualiza el contenido de un capítulo con una nueva sección"""
        if chapter_key not in self.chapter_contexts:
            self.register_chapter(chapter_key, f"Capítulo {chapter_key}", "")
            
        if "content" not in self.chapter_contexts[chapter_key]:
            self.chapter_contexts[chapter_key]["content"] = []
            
        self.chapter_contexts[chapter_key]["content"].append(section_content)
    
    def get_context_for_section(self, chapter_number, position, chapter_key):
        """
        Obtiene contexto para una sección específica de un capítulo.
        Versión simplificada que solo devuelve información básica.
        """
        # Si no hay información de capítulo, devolver contexto vacío
        if chapter_key not in self.chapter_contexts:
            return {
                "framework": self.framework,
                "previous_chapters_summary": "",
                "current_chapter_summary": "",
                "key_entities": {}
            }
            
        # Resumen de capítulos anteriores
        previous_chapters = []
        for i in range(1, chapter_number):
            for key, ctx in self.chapter_contexts.items():
                # Buscar capítulos con número menor al actual
                if str(i) in key:
                    title = ctx.get("title", f"Capítulo {key}")
                    summary = ctx.get("summary", "")
                    if summary:
                        previous_chapters.append(f"{title}: {summary}")
        
        # Contenido acumulado del capítulo actual 
        current_content = self.chapter_contexts[chapter_key].get("content", [])
        current_summary = ""
        
        if current_content:
            # Usar el contenido acumulado como contexto
            paragraphs = current_content[-3:] if len(current_content) > 3 else current_content
            current_summary = "\n\n".join(paragraphs)
            
        # Devolver contexto simpificado
        return {
            "framework": self.framework,
            "previous_chapters_summary": " ".join(previous_chapters),
            "current_chapter_summary": current_summary,
            "key_entities": {}
        }