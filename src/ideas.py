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
            # Usar la función para extraer el contenido de AIMessage
            features_response = self.llm.invoke("Genera una lista breve de elementos narrativos clave para una historia de fantasía y ciencia ficción. IMPORTANTE: Todos los elementos deben estar EXCLUSIVAMENTE en español.")
            features = clean_think_tags(extract_content_from_llm_response(features_response))
            
            # Limpiar todas las entradas
            outline = "\n".join(
                [f"{ch}: {clean_think_tags(desc)}" for ch, desc in chapter_dict.items()]
            )

            summaries = "\n\n".join(
                [f"{ch}:\n{clean_think_tags(summary)}" for ch, summary in summaries_dict.items()]
            )

            result = self.invoke(
                subject=clean_think_tags(subject),
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                profile=clean_think_tags(profile),
                title=clean_think_tags(title),
                framework=clean_think_tags(framework),
                features=features,
                outline=outline,
                summaries=summaries,
                chapter=chapter,
                chapter_num=chapter_num,
                total_chapters=total_chapters
            )

            if not result:
                raise ValueError("No se generó contenido válido")

            return result

        except Exception as e:
            print_progress(f"Error generando marco para {chapter}: {str(e)}")
            raise

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
            # Limpiar las ideas previas
            previous_ideas = "\n".join(
                [f"{ch}:\n" + "\n".join(f"- {clean_think_tags(idea)}" for idea in ideas)
                 for ch, ideas in idea_dict.items()]
            )

            result = self.invoke(
                subject=clean_think_tags(subject),
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                profile=clean_think_tags(profile),
                title=clean_think_tags(title),
                framework=clean_think_tags(framework),
                summary=clean_think_tags(summary),
                previous_ideas=previous_ideas,
                chapter_num=chapter_num,
                total_chapters=total_chapters
            )

            return self.parse(result)
            
        except Exception as e:
            print_progress(f"Error generando ideas: {str(e)}")
            raise

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
        for i, (chapter, _) in enumerate(chapter_dict.items(), 1):
            print_progress(f"Procesando capítulo {i}/{total_chapters}: {chapter}")
            
            try:
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
                    chapter_num=i,
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
                    chapter_num=i,
                    total_chapters=total_chapters
                )
                
                print_progress(f"Completado: {chapter} - {len(idea_dict[chapter])} ideas generadas")
                
            except Exception as e:
                print_progress(f"Error en capítulo {chapter}: {str(e)}")
                print_progress("Intentando continuar con el siguiente capítulo...")
                summaries_dict[chapter] = f"Error en la generación del marco para el capítulo {i} de {total_chapters}"
                idea_dict[chapter] = [f"Error en la generación de ideas para el capítulo {i} de {total_chapters}"]
                continue

        if not any(ideas != [f"Error en la generación de ideas para el capítulo {i+1} de {total_chapters}"] for i, ideas in enumerate(idea_dict.values())):
            raise Exception("No se pudo generar ninguna idea válida para ningún capítulo")

        return summaries_dict, idea_dict
        
    except Exception as e:
        print_progress(f"Error general en la generación de ideas: {str(e)}")
        raise
