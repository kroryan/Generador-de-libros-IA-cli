from utils import BaseEventChain, print_progress, clean_think_tags

class WriterChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### CONTEXTO NARRATIVO:
    - Título del libro: "{title}"
    - Estilo narrativo: {style}
    - Perfil general: {profile}
    - Número total de capítulos: {total_chapters}
    - Capítulo actual: {current_chapter} de {total_chapters}
    
    ### MARCO GENERAL DEL LIBRO:
    {framework}
    
    ### RESUMEN DE CAPÍTULOS ANTERIORES:
    {previous_chapters_summary}
    
    ### CONTEXTO DEL CAPÍTULO ACTUAL:
    - Título del capítulo: "{chapter_title}"
    - Marco del capítulo: {summary}
    - Posición: {section_position} ({section_number} de {total_sections})
    
    ### CONTENIDO PREVIO DEL CAPÍTULO:
    {previous_paragraphs}
    
    ### NUEVA IDEA A DESARROLLAR:
    {current_idea}
    
    <think>
    Analicemos cómo desarrollar esta idea para que fluya naturalmente con el contenido previo:
    
    1. Conexión con párrafos anteriores: identificaré elementos clave para retomar.
    2. Desarrollo coherente: expandiré la idea manteniendo el tono y estilo.
    3. Progresión narrativa: avanzaré la historia sin saltos lógicos.
    4. Elementos de continuidad: mantendré la coherencia de personajes y situaciones.
    
    Si estoy al inicio del capítulo, estableceré la conexión con capítulos anteriores.
    Si estoy en medio del capítulo, aseguraré la fluidez con los párrafos previos.
    Si estoy al final del capítulo, prepararé el terreno para el siguiente capítulo.
    </think>
    
    IMPORTANTE: Todo el contenido narrativo debe estar EXCLUSIVAMENTE en español. 
    Todo el texto, diálogos, nombres de personajes, lugares, objetos, términos técnicos 
    o mágicos y cualquier otro elemento narrativo DEBE estar en español. 
    NO uses términos, expresiones o nombres en otros idiomas bajo ninguna circunstancia.
    
    Genera el contenido narrativo para esta sección, asegurándote de que fluya naturalmente con el contenido previo:"""

    def run(
        self,
        genre,
        style,
        profile,
        title,
        framework,
        previous_chapters_summary,
        chapter_title,
        summary,
        previous_paragraphs,
        current_idea,
        current_chapter,
        total_chapters,
        section_position,
        section_number,
        total_sections
    ):
        print_progress(f"Escribiendo sección {section_number}/{total_sections} del capítulo {current_chapter}: {current_idea[:100]}...")
        
        try:
            # Limpiar todas las entradas de posibles cadenas de pensamiento
            previous_chapters_summary_cleaned = clean_think_tags(previous_chapters_summary)
            previous_paragraphs_cleaned = clean_think_tags(previous_paragraphs)
            
            # Limitar el tamaño del contexto previo para no sobrecargar el modelo
            if len(previous_paragraphs_cleaned) > 2000:
                previous_paragraphs_cleaned = "... [texto previo omitido] ...\n\n" + previous_paragraphs_cleaned[-2000:]
            
            result = self.invoke(
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                title=clean_think_tags(title),
                profile=clean_think_tags(profile),
                framework=clean_think_tags(framework),
                previous_chapters_summary=previous_chapters_summary_cleaned,
                chapter_title=clean_think_tags(chapter_title),
                summary=clean_think_tags(summary),
                previous_paragraphs=previous_paragraphs_cleaned,
                current_idea=clean_think_tags(current_idea),
                current_chapter=current_chapter,
                total_chapters=total_chapters,
                section_position=section_position,
                section_number=section_number,
                total_sections=total_sections
            )
            
            # El resultado ya viene limpio por el invoke() de BaseChain
            print_progress(f"Sección completada: {len(result)} caracteres")
            return result

        except Exception as e:
            print_progress(f"Error generando contenido: {str(e)}")
            raise

def write_book(genre, style, profile, title, framework, summaries_dict, idea_dict, chapter_summaries=None):
    print_progress("Iniciando escritura del libro...")
    writer_chain = WriterChain()
    book = {}
    
    # Si no hay resúmenes de capítulos, crear un diccionario vacío
    if chapter_summaries is None:
        chapter_summaries = {}

    try:
        total_chapters = len(idea_dict)
        for i, (chapter, idea_list) in enumerate(idea_dict.items(), 1):
            print_progress(f"Escribiendo capítulo {i}/{total_chapters}: {chapter}")
            book[chapter] = []
            ideas_total = len(idea_list)
            chapter_content = []
            chapter_paragraphs = ""
            
            # Preparar resumen de capítulos anteriores
            previous_chapters_summary = ""
            if i > 1:
                previous_chapters_summary = "Resumen de capítulos anteriores:\n\n"
                for j in range(1, i):
                    chapter_key = list(idea_dict.keys())[j-1]
                    if chapter_key in chapter_summaries:
                        previous_chapters_summary += f"Capítulo {j} ({chapter_key}):\n{chapter_summaries[chapter_key]}\n\n"
            
            # Procesar el título del capítulo
            chapter_title = summaries_dict[chapter].split('\n')[0] if '\n' in summaries_dict[chapter] else chapter

            for j, idea in enumerate(idea_list, 1):
                try:
                    # Determinar posición en el capítulo (inicio/medio/final)
                    if j == 1:
                        section_position = "inicio"
                    elif j == ideas_total:
                        section_position = "final"
                    else:
                        section_position = "medio"
                    
                    print_progress(f"Progreso del capítulo: {j}/{ideas_total} ideas")
                    
                    # Generar y limpiar el contenido con contexto mejorado
                    section_content = writer_chain.run(
                        genre=genre,
                        style=style,
                        profile=profile,
                        title=title,
                        framework=framework,
                        previous_chapters_summary=previous_chapters_summary,
                        chapter_title=chapter_title,
                        summary=summaries_dict[chapter],
                        previous_paragraphs=chapter_paragraphs,
                        current_idea=idea,
                        current_chapter=i,
                        total_chapters=total_chapters,
                        section_position=section_position,
                        section_number=j,
                        total_sections=ideas_total
                    )

                    chapter_content.append(section_content)
                    chapter_paragraphs = section_content if j == 1 else chapter_paragraphs + "\n\n" + section_content

                except Exception as e:
                    print_progress(f"Error generando contenido para idea {j}: {str(e)}")
                    print_progress("Intentando continuar con la siguiente idea...")
                    continue

            book[chapter] = chapter_content
            print_progress(f"Capítulo {chapter} completado")

        print_progress("Escritura del libro finalizada")
        return book

    except Exception as e:
        print_progress(f"Error general en la escritura del libro: {str(e)}")
        raise
