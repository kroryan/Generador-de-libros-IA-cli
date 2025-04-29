from utils import BaseEventChain, print_progress, clean_think_tags

class WriterChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Como escritor de fantasía y ciencia ficción, genera el contenido para esta sección del capítulo.
    El contenido debe ser detallado, inmersivo y coherente con el resto de la historia.

    Escribe varios párrafos que:
    - Desarrollen la idea principal de manera detallada
    - Integren elementos de fantasía y tecnología
    - Mantengan un ritmo narrativo fluido
    - Sean coherentes con el estilo y tono del libro

    Género: {genre}
    Estilo: {style}
    Perfil del libro: {profile}
    Título: {title}
    Marco del libro: {framework}

    Ideas previas desarrolladas: {previous_ideas}
    Marco del capítulo actual: {summary}
    Contenido previo del capítulo: {previous_paragraphs}

    Nueva idea a desarrollar: {current_idea}

    Genera el contenido narrativo para esta sección:"""

    def run(
        self,
        genre,
        style,
        profile,
        title,
        framework,
        previous_ideas,
        summary,
        previous_paragraphs,
        current_idea,
    ):
        print_progress(f"Escribiendo sección sobre: {current_idea[:100]}...")
        
        try:
            # Limpiar todas las entradas de posibles cadenas de pensamiento
            previous_ideas_cleaned = "\n".join([clean_think_tags(idea) for idea in previous_ideas])
            previous_paragraphs_cleaned = clean_think_tags(previous_paragraphs)
            
            result = self.invoke(
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                title=clean_think_tags(title),
                profile=clean_think_tags(profile),
                framework=clean_think_tags(framework),
                previous_ideas=previous_ideas_cleaned,
                summary=clean_think_tags(summary),
                previous_paragraphs=previous_paragraphs_cleaned,
                current_idea=clean_think_tags(current_idea)
            )
            
            # El resultado ya viene limpio por el invoke() de BaseChain
            print_progress(f"Sección completada: {len(result)} caracteres")
            return result

        except Exception as e:
            print_progress(f"Error generando contenido: {str(e)}")
            raise

def write_book(genre, style, profile, title, framework, summaries_dict, idea_dict):
    print_progress("Iniciando escritura del libro...")
    writer_chain = WriterChain()
    previous_ideas = []
    book = {}
    paragraphs = ""

    try:
        total_chapters = len(idea_dict)
        for i, (chapter, idea_list) in enumerate(idea_dict.items(), 1):
            print_progress(f"Escribiendo capítulo {i}/{total_chapters}: {chapter}")
            book[chapter] = []
            ideas_total = len(idea_list)
            chapter_content = []

            for j, idea in enumerate(idea_list, 1):
                try:
                    print_progress(f"Progreso del capítulo: {j}/{ideas_total} ideas")
                    
                    # Generar y limpiar el contenido
                    paragraphs = writer_chain.run(
                        genre=genre,
                        style=style,
                        profile=profile,
                        title=title,
                        framework=framework,
                        previous_ideas=previous_ideas,
                        summary=summaries_dict[chapter],
                        previous_paragraphs=paragraphs,
                        current_idea=idea,
                    )

                    # La idea ya viene limpia del proceso anterior
                    previous_ideas.append(idea)
                    chapter_content.append(paragraphs)

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
