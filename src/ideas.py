from utils import BaseEventChain, print_progress, clean_think_tags

class ChapterFrameworkChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Como escritor, genera el marco detallado para este capítulo.
    Sé específico y conciso. El marco debe incluir:
    - Eventos principales
    - Desarrollo de personajes
    - Elementos mágicos/tecnológicos relevantes
    - Conflictos y resoluciones

    Elementos narrativos a considerar:
    {features}

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título: {title}
    Perfil: {profile}
    Marco general: {framework}

    Capítulos anteriores:
    {outline}

    Marcos previos:
    {summaries}

    Marco para {chapter}:"""

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
    ):
        print_progress(f"Generando marco para: {chapter}")
        
        try:
            # Generar features usando el mismo modelo y limpiar resultado
            features = clean_think_tags(self.llm.invoke("Genera una lista breve de elementos narrativos clave para una historia de fantasía y ciencia ficción."))
            
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
                chapter=chapter
            )

            if not result:
                raise ValueError("No se generó contenido válido")

            return result

        except Exception as e:
            print_progress(f"Error generando marco para {chapter}: {str(e)}")
            raise

class IdeasChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Como escritor de fantasía y ciencia ficción, genera 3-4 ideas clave para este capítulo.
    Cada idea debe ser clara y específica, enfocándose en:
    - Desarrollo de la trama
    - Elementos mágicos/tecnológicos
    - Desarrollo de personajes
    - Conexiones con la historia general

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título: {title}
    Perfil: {profile}
    Marco: {framework}

    Ideas previas: {previous_ideas}

    Marco del capítulo:
    {summary}

    Lista de ideas (una por línea):"""

    def run(self, subject, genre, style, profile, title, framework, summary, idea_dict):
        print_progress("Generando ideas para el capítulo")
        
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
                previous_ideas=previous_ideas
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
                # Generar marco del capítulo
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
                )
                print_progress(f"Marco generado para: {chapter}")

                # Generar ideas para el capítulo
                idea_dict[chapter] = ideas_chain.run(
                    subject=subject,
                    genre=genre,
                    style=style,
                    profile=profile,
                    title=title,
                    framework=framework,
                    summary=summaries_dict[chapter],
                    idea_dict=idea_dict,
                )
                
                print_progress(f"Completado: {chapter} - {len(idea_dict[chapter])} ideas generadas")
                
            except Exception as e:
                print_progress(f"Error en capítulo {chapter}: {str(e)}")
                print_progress("Intentando continuar con el siguiente capítulo...")
                summaries_dict[chapter] = "Error en la generación del marco"
                idea_dict[chapter] = ["Error en la generación de ideas"]
                continue

        if not any(ideas != ["Error en la generación de ideas"] for ideas in idea_dict.values()):
            raise Exception("No se pudo generar ninguna idea válida para ningún capítulo")

        return summaries_dict, idea_dict
        
    except Exception as e:
        print_progress(f"Error general en la generación de ideas: {str(e)}")
        raise
