from utils import BaseStructureChain, print_progress, clean_think_tags

class TitleChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
    Genera un título atractivo y original para esta novela de fantasía y ciencia ficción.
    El título debe capturar la esencia de la historia y ser memorable.
    Devuelve solo el título, sin explicaciones adicionales.
    IMPORTANTE: El título debe estar EXCLUSIVAMENTE en español. No uses palabras en otros idiomas.

    Tema del libro: {subject}
    Género del libro: {genre}
    Estilo: {style}
    Perfil del libro: {profile}

    Título:"""

    def run(self, subject, genre, style, profile):
        print_progress("Generando título...")
        return self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            profile=clean_think_tags(profile)
        )

class FrameworkChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
    Genera el marco narrativo para esta novela de fantasía y ciencia ficción.
    El marco debe ser claro y específico, incluyendo:
    1. El conflicto principal de la historia
    2. Los elementos mágicos y tecnológicos más importantes
    3. Los personajes principales y sus motivaciones
    4. La estructura general de la trama
    5. Los temas principales a explorar
    IMPORTANTE: Todo el contenido debe estar EXCLUSIVAMENTE en español. Todos los nombres de personajes, 
    lugares, elementos mágicos y tecnológicos deben estar en español o ser adaptados al español.

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título: {title}
    Perfil del libro: {profile}

    Marco narrativo:"""

    def run(self, subject, genre, style, profile, title):
        print_progress("Generando marco narrativo...")
        return self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            profile=clean_think_tags(profile),
            title=clean_think_tags(title)
        )

class ChaptersChain(BaseStructureChain):
    PROMPT_TEMPLATE = """
    Genera una lista de capítulos para esta novela.
    La lista debe incluir un prólogo, 7-9 capítulos numerados y un epílogo.
    Usa exactamente este formato:
    Prólogo: [breve descripción]
    Capítulo 1: [breve descripción]
    ...
    Epílogo: [breve descripción]
    IMPORTANTE: Los títulos y descripciones de TODOS los capítulos deben estar EXCLUSIVAMENTE en español. 
    Todos los nombres, lugares y conceptos mencionados deben estar en español.

    Tema: {subject}
    Género: {genre}
    Estilo: {style}
    Título: {title}
    Perfil: {profile}
    Marco: {framework}

    Lista de capítulos:"""

    def run(self, subject, genre, style, title, profile, framework):
        print_progress("Generando lista de capítulos...")
        response = self.invoke(
            subject=clean_think_tags(subject),
            genre=clean_think_tags(genre),
            style=clean_think_tags(style),
            title=clean_think_tags(title),
            profile=clean_think_tags(profile),
            framework=clean_think_tags(framework)
        )
        return self.parse(response)

    def parse(self, response):
        if not response:
            raise ValueError("No se generó contenido para los capítulos")
            
        # Asegurar que el response sea una cadena de texto
        if not isinstance(response, str):
            response = extract_content_from_llm_response(response)
            if not response:
                raise ValueError("No se pudo extraer contenido válido de la respuesta del modelo")
                
        # El response ya viene limpio de clean_think_tags por el invoke()
        try:
            chapter_list = [line.strip() for line in response.split('\n') if ':' in line]
            if not chapter_list:
                raise ValueError("No se generaron capítulos válidos")
                
            chapter_dict = {}
            for chapter in chapter_list:
                name, description = chapter.split(':', 1)
                chapter_dict[name.strip()] = description.strip()
            return chapter_dict
            
        except Exception as e:
            print_progress(f"Error al procesar los capítulos: {str(e)}")
            print_progress("Intentando recuperar estructura básica...")
            
            # Intentar recuperar al menos algunos capítulos en caso de error
            chapter_dict = {}
            try:
                # Buscar cualquier línea que pueda contener un capítulo
                lines = response.split('\n')
                chapter_count = 1
                
                for line in lines:
                    line = line.strip()
                    if line and (':' in line or 'capítulo' in line.lower() or 'prólogo' in line.lower() or 'epílogo' in line.lower()):
                        if ':' in line:
                            name, desc = line.split(':', 1)
                            chapter_dict[name.strip()] = desc.strip()
                        else:
                            chapter_dict[line] = "Desarrollo de la trama principal."
                    
                # Si aún no se han recuperado capítulos, crear estructura mínima
                if not chapter_dict:
                    chapter_dict["Prólogo"] = "Introducción a la historia y personajes principales."
                    for i in range(1, 6):
                        chapter_dict[f"Capítulo {i}"] = f"Desarrollo de la trama principal - parte {i}."
                    chapter_dict["Epílogo"] = "Conclusión de la historia."
                    
                return chapter_dict
                
            except Exception as nested_e:
                print_progress(f"Error en la recuperación de emergencia: {str(nested_e)}")
                # Estructura mínima en caso de error total
                return {
                    "Prólogo": "Introducción a la historia.",
                    "Capítulo 1": "Desarrollo inicial.",
                    "Capítulo 2": "Desarrollo medio.",
                    "Capítulo 3": "Clímax.",
                    "Epílogo": "Conclusión."
                }

def get_structure(subject, genre, style, profile):
    print_progress("Iniciando generación de estructura...")
    
    try:
        # Limpiar las entradas iniciales
        subject = clean_think_tags(subject)
        genre = clean_think_tags(genre)
        style = clean_think_tags(style)
        profile = clean_think_tags(profile)
        
        # Generar título
        title_chain = TitleChain()
        title = title_chain.run(subject, genre, style, profile)
        print_progress(f"Título generado: {title}")
        
        # Generar marco
        framework_chain = FrameworkChain()
        framework = framework_chain.run(subject, genre, style, profile, title)
        print_progress("Marco narrativo generado")
        
        # Generar capítulos
        chapters_chain = ChaptersChain()
        chapter_dict = chapters_chain.run(subject, genre, style, profile, title, framework)
        print_progress(f"Lista de {len(chapter_dict)} capítulos generada")
        
        return title, framework, chapter_dict
        
    except Exception as e:
        print_progress(f"Error en la generación de la estructura: {str(e)}")
        raise
