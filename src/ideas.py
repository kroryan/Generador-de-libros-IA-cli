from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response

class ChapterFrameworkChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Como escritor profesional, genera el marco detallado para este capítulo.
    Sé específico y conciso. El marco debe incluir:
    - Posición del capítulo en la narrativa general ({chapter_num} de {total_chapters})
    - Eventos principales
    - Desarrollo de personajes
    - Elementos mágicos/tecnológicos relevantes
    - Conflictos y resoluciones
    - Conexiones con capítulos anteriores (si aplica)
    - Preparación para capítulos posteriores

    IMPORTANTE: Todo el contenido del marco debe estar EXCLUSIVAMENTE en español. Todos los nombres, lugares, 
    elementos mágicos, tecnológicos y conceptos deben estar en español. No utilices ningún término en otro idioma.

    Elementos narrativos a considerar:
    {features}

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título del libro: {title}
    Perfil: {profile}
    Marco general: {framework}

    Capítulos anteriores:
    {outline}

    Marcos previos:
    {summaries}

    Marco para {chapter} (Capítulo {chapter_num} de {total_chapters}):"""

    def run(
        self,
        subject,
        genre,
        style,
        profile,
        title,
        framework,
        summaries_dict,
        chapter_dict,
        chapter,
        chapter_num,
        total_chapters
    ):
        print_progress(f"Generando marco para: {chapter} (Capítulo {chapter_num} de {total_chapters})")
        
        try:
            # Generar features usando el mismo modelo y limpiar resultado
            # Usar la función para extraer el contenido de AIMessage de manera segura
            try:
                features_response = self.llm.invoke("Genera una lista breve de elementos narrativos clave para una historia de fantasía y ciencia ficción. IMPORTANTE: Todos los elementos deben estar EXCLUSIVAMENTE en español.")
                features = clean_think_tags(extract_content_from_llm_response(features_response))
            except Exception as e:
                print_progress(f"Error al generar features: {str(e)}. Usando features genéricas.")
                features = "Personajes, lugares, elementos mágicos, tecnología, conflictos, resoluciones."
            
            # Limpiar todas las entradas de forma segura
            try:
                outline = "\n".join(
                    [f"{ch}: {clean_think_tags(str(desc))}" for ch, desc in chapter_dict.items()]
                )
            except Exception as e:
                print_progress(f"Error al procesar outline: {str(e)}. Usando versión simplificada.")
                outline = "Estructura de capítulos no disponible en detalle."

            try:
                summaries = "\n\n".join(
                    [f"{ch}:\n{clean_think_tags(str(summary))}" for ch, summary in summaries_dict.items()]
                )
            except Exception as e:
                print_progress(f"Error al procesar summaries: {str(e)}. Usando versión simplificada.")
                summaries = "Resúmenes de capítulos anteriores no disponibles en detalle."

            # Asegurar que todos los parámetros sean strings válidos
            safe_params = {
                "subject": clean_think_tags(str(subject) if subject is not None else ""),
                "genre": clean_think_tags(str(genre) if genre is not None else ""),
                "style": clean_think_tags(str(style) if style is not None else ""),
                "profile": clean_think_tags(str(profile) if profile is not None else ""),
                "title": clean_think_tags(str(title) if title is not None else ""),
                "framework": clean_think_tags(str(framework) if framework is not None else ""),
                "features": features,
                "outline": outline,
                "summaries": summaries,
                "chapter": str(chapter),
                "chapter_num": chapter_num,
                "total_chapters": total_chapters
            }

            result = self.invoke(**safe_params)

            # Verificar el resultado y procesarlo de manera segura
            if not result or not isinstance(result, str):
                print_progress("Advertencia: Formato de respuesta inesperado. Intentando recuperar contenido...")
                result = extract_content_from_llm_response(result)

            if not result:
                raise ValueError("No se generó contenido válido")

            return result

        except Exception as e:
            print_progress(f"Error generando marco para {chapter}: {str(e)}")
            # En caso de error fatal, devolver un marco básico para poder continuar
            return f"Marco para el capítulo {chapter_num} de {total_chapters}. Este capítulo avanza la trama principal y prepara eventos para el siguiente capítulo."

class IdeasChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Como escritor de fantasía y ciencia ficción, genera 3-5 ideas clave para este capítulo.
    Cada idea debe ser clara y específica, enfocándose en:
    - Desarrollo de la trama
    - Elementos mágicos/tecnológicos
    - Desarrollo de personajes
    - Conexiones con la historia general
    - Transiciones fluidas entre secciones

    IMPORTANTE: Todas las ideas deben estar EXCLUSIVAMENTE en español. Todos los nombres, lugares, elementos 
    mágicos, tecnológicos y conceptos deben estar en español. No utilices ningún término en otro idioma.

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título: {title}
    Perfil: {profile}
    Marco general: {framework}
    Posición: Capítulo {chapter_num} de {total_chapters}

    Ideas de capítulos previos: {previous_ideas}

    Marco del capítulo:
    {summary}

    <think>
    Voy a generar ideas que:
    1. Sean coherentes con el marco del capítulo
    2. Sigan una progresión narrativa lógica
    3. Mantengan continuidad con capítulos anteriores
    4. Preparen elementos para capítulos posteriores
    5. Tengan un flujo natural entre sí
    </think>

    Lista de ideas ordenadas para asegurar progresión narrativa fluida (una por línea):"""

    def run(self, subject, genre, style, profile, title, framework, summary, idea_dict, chapter_num, total_chapters):
        print_progress(f"Generando ideas para el capítulo {chapter_num}")
        
        try:
            # Limpiar las ideas previas de forma segura
            previous_ideas = ""
            try:
                previous_ideas = "\n".join(
                    [f"{ch}:\n" + "\n".join(f"- {clean_think_tags(idea)}" for idea in ideas)
                     for ch, ideas in idea_dict.items()]
                )
            except Exception as e:
                print_progress(f"Advertencia al procesar ideas previas: {str(e)}")
                # Crear una versión más simple si hay problemas
                previous_ideas = "Ideas de capítulos anteriores no disponibles."

            # Asegurar que todos los parámetros sean strings válidos
            safe_params = {
                "subject": clean_think_tags(str(subject) if subject is not None else ""),
                "genre": clean_think_tags(str(genre) if genre is not None else ""),
                "style": clean_think_tags(str(style) if style is not None else ""),
                "profile": clean_think_tags(str(profile) if profile is not None else ""),
                "title": clean_think_tags(str(title) if title is not None else ""),
                "framework": clean_think_tags(str(framework) if framework is not None else ""),
                "summary": clean_think_tags(str(summary) if summary is not None else ""),
                "previous_ideas": previous_ideas,
                "chapter_num": chapter_num,
                "total_chapters": total_chapters
            }

            result = self.invoke(**safe_params)

            # Si el resultado no es del tipo esperado, intentar procesar de manera segura
            if not result or not isinstance(result, str):
                print_progress("Advertencia: Resultado de ideas con formato inesperado. Intentando recuperar contenido...")
                result = extract_content_from_llm_response(result)
                if not result:
                    raise ValueError("No se pudo extraer contenido válido de la respuesta del modelo")

            return self.parse(result)
            
        except Exception as e:
            print_progress(f"Error generando ideas: {str(e)}")
            # En caso de error, devolver al menos una idea genérica para no interrumpir el proceso
            return [f"Avanzar la trama principal en el capítulo {chapter_num} de {total_chapters}"]

    def parse(self, response):
        if not response:
            raise ValueError("Respuesta vacía del modelo")
        
        # Limpiar cada idea individualmente
        ideas = [clean_think_tags(idea.strip()) for idea in response.split('\n') if idea.strip()]
        if not ideas:
            raise ValueError("No se generaron ideas válidas")
        return ideas

def get_ideas(subject, genre, style, profile, title, framework, chapter_dict):
    print_progress("Iniciando generación de ideas para capítulos...")
    chapter_framework_chain = ChapterFrameworkChain()
    ideas_chain = IdeasChain()
    summaries_dict = {}
    idea_dict = {}

    try:
        total_chapters = len(chapter_dict)
        for i, (chapter, description) in enumerate(chapter_dict.items(), 1):
            print_progress(f"Procesando capítulo {i}/{total_chapters}: {chapter}")
            
            try:
                # Determinar el número correcto del capítulo para el prompt
                chapter_num = i
                if "prólogo" in chapter.lower():
                    chapter_num = 0
                elif "epílogo" in chapter.lower():
                    chapter_num = total_chapters
                
                # Generar marco del capítulo con información de posición
                summaries_dict[chapter] = chapter_framework_chain.run(
                    subject=subject,
                    genre=genre,
                    style=style,
                    profile=profile,
                    title=title,
                    framework=framework,
                    summaries_dict=summaries_dict,
                    chapter_dict=chapter_dict,
                    chapter=chapter,
                    chapter_num=chapter_num,
                    total_chapters=total_chapters
                )
                print_progress(f"Marco generado para: {chapter}")

                # Generar ideas para el capítulo con información de posición
                idea_dict[chapter] = ideas_chain.run(
                    subject=subject,
                    genre=genre,
                    style=style,
                    profile=profile,
                    title=title,
                    framework=framework,
                    summary=summaries_dict[chapter],
                    idea_dict=idea_dict,
                    chapter_num=chapter_num,
                    total_chapters=total_chapters
                )
                
                print_progress(f"Completado: {chapter} - {len(idea_dict[chapter])} ideas generadas")
                
            except Exception as e:
                print_progress(f"Error en capítulo {chapter}: {str(e)}")
                print_progress("Intentando continuar con el siguiente capítulo...")
                summaries_dict[chapter] = f"Error en la generación del marco para el capítulo {i} de {total_chapters}"
                idea_dict[chapter] = [f"Error en la generación de ideas para el capítulo {i} de {total_chapters}"]
                continue

        return summaries_dict, idea_dict
        
    except Exception as e:
        print_progress(f"Error general en la generación de ideas: {str(e)}")
        raise
