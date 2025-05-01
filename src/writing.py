from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response
from chapter_summary import ChapterSummaryChain, ProgressiveContextManager
from time import sleep
import re
import time  # Importación añadida para usar time.sleep()

class WriterChain(BaseEventChain):
    PROMPT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### INFORMACIÓN ESENCIAL:
    - Título: "{title}"
    - Estilo: {style}
    - Capítulo actual: {current_chapter} de {total_chapters}
    - Posición: {section_position} del capítulo
    
    ### MARCO NARRATIVO RESUMIDO:
    {framework_summary}
    
    ### CONTEXTO ANTERIOR COMPACTO:
    {minimal_context}
    
    ### CONTEXTO INMEDIATO:
    - Título del capítulo: "{chapter_title}"
    - Sección: {section_number} de {total_sections}
    
    ### PÁRRAFOS RECIENTES:
    {previous_paragraphs}
    
    ### IDEA A DESARROLLAR AHORA:
    {current_idea}
    
    <think>
    Desarrollaré esta idea enfocándome solo en:
    1. Conexión directa con el contenido reciente
    2. Desarrollo coherente de personajes y situaciones
    3. Avance natural de la historia
    
    Mantendré el foco narrativo sin divagar ni resumir.
    </think>
    
    IMPORTANTE: 
    - Escribe EXCLUSIVAMENTE texto narrativo en español
    - NO incluyas notas, comentarios ni explicaciones
    - NO hagas resúmenes ni menciones de la estructura
    - Solo genera el texto que formaría parte del libro final
    
    Escribe directamente el contenido narrativo:"""

    def run(
        self,
        genre,
        style,
        title,
        context_manager,
        chapter_title,
        summary,
        previous_paragraphs,
        current_idea,
        current_chapter,
        total_chapters,
        section_position,
        section_number,
        total_sections,
        chapter_key
    ):
        print_progress(f"Escribiendo sección {section_number}/{total_sections} del capítulo {current_chapter}")
        
        try:
            # Obtener contexto mínimo optimizado
            context_data = context_manager.get_context_for_section(current_chapter, section_position, chapter_key)
            
            # Crear un contexto mucho más compacto
            minimal_context = self._create_minimal_context(
                context_data, 
                current_chapter, 
                section_position
            )
            
            # Extraer solo lo esencial del marco narrativo
            framework_summary = self._extract_framework_essence(context_data["framework"])
            
            # Limpiar y reducir las entradas para minimizar tokens
            previous_paragraphs_cleaned = self._optimize_previous_paragraphs(previous_paragraphs)
            chapter_summary_short = self._optimize_summary(summary)
            idea_to_develop = self._optimize_idea(current_idea)
            
            # Título del capítulo simplificado (solo el nombre principal)
            simple_chapter_title = self._simplify_chapter_title(chapter_title)
            
            result = self.invoke(
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                title=clean_think_tags(title),
                framework_summary=framework_summary,
                minimal_context=minimal_context,
                chapter_title=simple_chapter_title,
                previous_paragraphs=previous_paragraphs_cleaned,
                current_idea=clean_think_tags(idea_to_develop),
                current_chapter=current_chapter,
                total_chapters=total_chapters,
                section_position=section_position,
                section_number=section_number,
                total_sections=total_sections
            )
            
            # Eliminar posibles metadatos que el modelo haya incluido
            clean_result = self._clean_result(result)
            
            print_progress(f"Sección completada: {len(clean_result)} caracteres")
            return clean_result

        except Exception as e:
            print_progress(f"Error generando contenido: {str(e)}")
            raise
    
    def _create_minimal_context(self, context_data, current_chapter, position):
        """Crea un contexto mínimo y óptimo basado en la posición en el capítulo"""
        context_parts = []
        
        # Para inicio de capítulo: contexto de capítulos anteriores
        if position == "inicio" and current_chapter > 1:
            # Reducir drásticamente el contexto previo
            prev_chapters = context_data.get("previous_chapters_summary", "")
            if prev_chapters:
                context_parts.append(f"Capítulos anteriores: {prev_chapters[:300]}...")
        
        # Para medio y final: resumen incremental del mismo capítulo
        if position in ["medio", "final"]:
            current_context = context_data.get("current_chapter_summary", "")
            if current_context:
                context_parts.append(f"Desarrollo previo: {current_context[:250]}...")
        
        return "\n".join(context_parts)
    
    def _extract_framework_essence(self, framework):
        """Extrae solo los elementos esenciales del marco narrativo"""
        if not framework:
            return ""
        
        # Limitar a 150 caracteres
        if len(framework) > 150:
            return framework[:150] + "..."
        return framework
    
    def _optimize_previous_paragraphs(self, text):
        """Optimiza los párrafos previos para mantener solo lo más reciente y relevante"""
        if not text:
            return ""
            
        # Limpiar etiquetas y metadata
        cleaned = clean_think_tags(text)
        
        # Reducir drásticamente - solo mantener los últimos 2-3 párrafos
        paragraphs = cleaned.split('\n\n')
        if len(paragraphs) > 3:
            return "...\n\n" + "\n\n".join(paragraphs[-3:])
        return cleaned
    
    def _optimize_summary(self, summary):
        """Reduce el resumen a lo esencial"""
        if not summary:
            return ""
            
        cleaned = clean_think_tags(summary)
        if len(cleaned) > 200:
            return cleaned[:200] + "..."
        return cleaned
    
    def _optimize_idea(self, idea):
        """Optimiza la idea a desarrollar"""
        if not idea:
            return ""
            
        cleaned = clean_think_tags(idea)
        if len(cleaned) > 150:
            return cleaned[:150] + "..."
        return cleaned
    
    def _simplify_chapter_title(self, title):
        """Simplifica el título del capítulo a su esencia"""
        if not title:
            return ""
            
        # Eliminar descripciones extensas después de dos puntos
        if ':' in title:
            return title.split(':', 1)[0].strip()
        return title
    
    def _clean_result(self, text):
        """Elimina posibles metadatos del resultado generado"""
        if not text:
            return ""
            
        # Eliminar patrones comunes que no pertenecen a la narrativa
        import re
        patterns = [
            r'^Capítulo \d+:.*?\n',
            r'^CAPÍTULO \d+:.*?\n',
            r'^Sección \d+:.*?\n',
            r'^\[Continúa.*?\].*?\n',
            r'^\[Desarrollo.*?\].*?\n',
            r'^\[.*?\].*?\n',
            r'^\*\*\*.*?\*\*\*\n',
            r'^---.*?---\n'
        ]
        
        result = text
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.MULTILINE)
            
        return result.strip()

def regenerate_problematic_section(writer_chain, context_manager, section_params, max_attempts=3):
    """
    Intenta regenerar una sección que ha mostrado problemas o señales de colapso.
    Usa estrategias progresivamente más agresivas para recuperar la generación.
    
    Args:
        writer_chain: Instancia de WriterChain para generar contenido
        context_manager: Gestor de contexto progresivo
        section_params: Parámetros de la sección a regenerar
        max_attempts: Número máximo de intentos antes de usar fallback
        
    Returns:
        str: Contenido regenerado
    """
    from utils import print_progress
    
    print_progress("🔄 Intentando regenerar sección problemática...")
    
    # Extractores de parámetros clave
    chapter_key = section_params.get('chapter_key', 'capítulo actual')
    chapter_title = section_params.get('chapter_title', 'este capítulo')
    current_chapter = section_params.get('current_chapter', 1)
    section_position = section_params.get('section_position', 'medio')
    
    # Guardar capacidad original del modelo
    original_capacity = context_manager.model_capacity
    
    for attempt in range(max_attempts):
        try:
            print_progress(f"Intento {attempt+1}/{max_attempts} de regeneración")
            
            # Estrategias progresivamente más agresivas
            if attempt == 0:
                # Primer intento: reducir ligeramente el contexto
                if original_capacity != "limited":
                    context_manager.set_model_capacity("limited")
            elif attempt == 1:
                # Segundo intento: aplicar compresión de emergencia
                section_params['previous_paragraphs'] = section_params.get('previous_paragraphs', '')[:200]
                section_params['current_idea'] = section_params.get('current_idea', '')[:100]
            else:
                # Último intento: contexto ultra minimalista
                minimal_context = context_manager.get_minimal_context()
                # Usar solo la primera línea de la idea actual
                current_idea = section_params.get('current_idea', '')
                idea_first_line = current_idea.split('\n')[0] if current_idea else ''
                
                # Crear un prompt con instrucciones absolutamente claras
                from utils import clean_think_tags, extract_content_from_llm_response
                
                emergency_prompt = f'''
                Escribe un párrafo narrativo para continuar esta historia.
                
                Capítulo: {chapter_title}
                Contexto mínimo: {minimal_context.get("framework", "")}
                Idea a desarrollar: {idea_first_line}
                
                IMPORTANTE: Escribe SOLO texto narrativo en español, sin encabezados ni metadata.
                '''
                
                response = writer_chain.llm.invoke(emergency_prompt)
                return clean_think_tags(extract_content_from_llm_response(response))
            
            # Intentar la generación con los parámetros actuales
            content = writer_chain.run(**section_params)
            
            # Verificar si la regeneración fue exitosa
            is_collapsed, message = context_manager.detect_collapse_risk(content)
            if not is_collapsed:
                # Restaurar capacidad del modelo
                context_manager.set_model_capacity(original_capacity)
                print_progress("✅ Regeneración exitosa")
                return content
                
        except Exception as e:
            print_progress(f"Error en intento {attempt+1}: {str(e)}")
    
    # Si todos los intentos fallan, usar un texto de contingencia
    context_manager.set_model_capacity(original_capacity)
    print_progress("⚠️ Usando texto de contingencia tras múltiples fallos")
    
    return f"La escena continuó desarrollándose. Los personajes avanzaron en su objetivo mientras exploraban {chapter_title}."

def write_book(genre, style, profile, title, framework, summaries_dict, idea_dict, chapter_summaries=None):
    print_progress("Iniciando escritura del libro...")
    writer_chain = WriterChain()
    summary_chain = ChapterSummaryChain()
    book = {}
    
    # Si no hay resúmenes de capítulos, crear un diccionario vacío
    if chapter_summaries is None:
        chapter_summaries = {}
        
    # Inicializar el nuevo sistema de contexto adaptativo
    from adaptive_context import AdaptiveContextSystem
    from utils import detect_model_size
    from content_analyzer import ContentAnalyzer
    
    # Detectar automáticamente el tamaño del modelo
    model_size = detect_model_size(writer_chain.llm)
    
    # Configurar el sistema adaptativo de contexto
    context_system = AdaptiveContextSystem(title, framework, len(idea_dict), model_size)
    content_analyzer = ContentAnalyzer()  # Analizador de calidad y colapsos
    
    # Simplificar el perfil para reducir contexto
    profile_short = profile[:150] + "..." if len(profile) > 150 else profile
    
    # Contador para chequeos periódicos de salud
    health_check_counter = 0 
    health_check_interval = 5  # Cada cuántas secciones hacer un chequeo

    try:
        total_chapters = len(idea_dict)
        for i, (chapter, idea_list) in enumerate(idea_dict.items(), 1):
            print_progress(f"======================================")
            print_progress(f"CAPÍTULO {i}/{total_chapters}: {chapter}")
            print_progress(f"======================================")
            
            book[chapter] = []
            ideas_total = len(idea_list)
            chapter_content = []
            
            # Simplificar el título del capítulo
            chapter_title = chapter.split(':', 1)[0] if ':' in chapter else chapter
            
            # Obtener o crear resumen del capítulo
            chapter_summary = summaries_dict.get(chapter, "")
            
            # Inicializar contexto para este capítulo usando el nuevo sistema adaptativo
            chapter_info = context_system.start_chapter(
                chapter_num=i,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary
            )

            for j, idea in enumerate(idea_list, 1):
                # Realizar chequeo periódico de salud del modelo
                health_check_counter += 1
                if health_check_counter >= health_check_interval:
                    health_check_counter = 0
                    is_healthy = context_system.health_check(writer_chain.llm)
                    if not is_healthy:
                        print_progress("⏳ Pausando brevemente para recuperar estabilidad...")
                        # Una pausa breve puede ayudar a "resetear" el contexto interno del modelo
                        time.sleep(2)
                
                try:
                    # Determinar posición en el capítulo
                    if j == 1:
                        section_position = "inicio"
                    elif j == ideas_total:
                        section_position = "final"
                    else:
                        section_position = "medio"
                    
                    # Mostrar solo parte de la idea para no llenar la consola
                    idea_preview = idea[:40] + "..." if len(idea) > 40 else idea
                    print_progress(f">> Idea {j}/{ideas_total}: {idea_preview}")
                    
                    # Obtener contexto adaptativo para esta sección específica
                    chapter_paragraphs = "\n\n".join(chapter_content[-3:]) if chapter_content else ""
                    
                    adaptive_context = context_system.get_context_for_section(
                        section_position=section_position,
                        idea=idea,
                        previous_content=chapter_paragraphs,
                        section_number=j,
                        total_sections=ideas_total
                    )
                    
                    # NUEVO: Verificar y ajustar el tamaño del contexto para no exceder el límite universal
                    adaptive_context, size_info = context_system.check_context_size(
                        adaptive_context, 
                        context_system.generation_state["model_size"]
                    )
                    
                    # Mostrar información del contexto si fue comprimido
                    if size_info["compressed"]:
                        print_progress(f"📊 Contexto: {size_info['estimated_tokens']} tokens ({size_info['usage_percentage']}% del límite)")
                        if size_info["emergency_compressed"]:
                            print_progress("⚠️ Se aplicó compresión de emergencia para evitar exceder el límite")
                    
                    # Generar contenido usando WriterChain con el contexto adaptativo
                    prompt = f"""
                    Eres un escritor profesional de {genre} en español.
                    
                    ### INFORMACIÓN ESENCIAL:
                    - Título: "{title}"
                    - Estilo: {style}
                    - Capítulo actual: {i} de {total_chapters}
                    - Posición: {section_position} del capítulo
                    
                    ### MARCO NARRATIVO:
                    {adaptive_context.get('core_narrative', '')}
                    
                    ### CONTEXTO RECIENTE:
                    {adaptive_context.get('recent_paragraphs', '')}
                    
                    ### PERSONAJES ACTIVOS:
                    {adaptive_context.get('active_entities', '')}
                    
                    ### GUÍA DE POSICIÓN:
                    {adaptive_context.get('position_guidance', '')}
                    
                    ### IDEA A DESARROLLAR AHORA:
                    {adaptive_context.get('current_idea', '')}
                    
                    <think>
                    Desarrollaré esta idea enfocándome solo en:
                    1. Conexión directa con el contenido reciente
                    2. Desarrollo coherente de personajes y situaciones
                    3. Avance natural de la historia
                    
                    Mantendré el foco narrativo sin divagar ni resumir.
                    </think>
                    
                    IMPORTANTE: 
                    - Escribe EXCLUSIVAMENTE texto narrativo en español
                    - NO incluyas notas, comentarios ni explicaciones
                    - NO hagas resúmenes ni menciones de la estructura
                    - Solo genera el texto que formaría parte del libro final
                    
                    Escribe directamente el contenido narrativo:
                    """
                    
                    # Generar contenido de sección
                    try:
                        response = writer_chain.llm(prompt)
                        section_content = clean_think_tags(extract_content_from_llm_response(response))
                    except Exception as e:
                        # Capturar específicamente errores de exceso de contexto/tokens
                        error_str = str(e).lower()
                        if any(keyword in error_str for keyword in ["token", "context length", "maximum context", "too many tokens"]):
                            print_progress("🚨 Error de límite de tokens detectado, reiniciando contexto...")
                            
                            # Usar el nuevo sistema de manejo de overflow de tokens
                            if chapter_content:
                                # Si ya tenemos contenido previo, intentar continuar desde allí
                                recovered_content, success = context_system.manage_token_overflow(
                                    llm=writer_chain.llm,
                                    content_so_far="\n\n".join(chapter_content),
                                    idea_current=idea,
                                    section_position=section_position
                                )
                                
                                if success:
                                    # Extraer solo la parte nueva (lo que se acaba de generar)
                                    existing_content = "\n\n".join(chapter_content)
                                    if recovered_content.startswith(existing_content):
                                        # Si la recuperación incluye todo el contenido anterior,
                                        # extraer solo la parte nueva
                                        section_content = recovered_content[len(existing_content):].strip()
                                        # Asegurar un separador limpio
                                        if section_content and not section_content.startswith("\n"):
                                            section_content = "\n\n" + section_content
                                    else:
                                        # Si no podemos identificar claramente la parte nueva,
                                        # usar solo los últimos párrafos como contenido de sección
                                        paragraphs = recovered_content.split('\n\n')
                                        if len(paragraphs) > 3:
                                            section_content = '\n\n'.join(paragraphs[-3:])
                                        else:
                                            section_content = recovered_content
                                else:
                                    # Si no tuvimos éxito, usar texto de fallback
                                    section_content = f"La narrativa continuó desarrollándose mientras los personajes exploraban los eventos relacionados con {idea[:30]}..."
                            else:
                                # Si no hay contenido previo, generar algo mínimo
                                emergency_prompt = f"""
                                Escribe un párrafo corto para abrir este capítulo.
                                Título: "{chapter_title}"
                                Idea: {idea[:100]}
                                """
                                try:
                                    response = writer_chain.llm(emergency_prompt, temperature=0.7)
                                    section_content = clean_think_tags(extract_content_from_llm_response(response))
                                except:
                                    section_content = f"El capítulo comenzó explorando {idea[:30]}..."
                        else:
                            # Otros tipos de errores, reenviar la excepción
                            raise
                    
                    # Procesar el contenido generado con el nuevo sistema
                    processed_content, analysis, is_collapsed = context_system.process_generated_content(
                        content=section_content,
                        section_position=section_position,
                        idea=idea
                    )
                    
                    # Si se detecta riesgo de colapso, regenerar la sección
                    if is_collapsed:
                        print_progress(f"⚠️ Regenerando sección con problemas: {analysis.get('analysis', {}).get('potential_issues', [])}")
                        
                        # Intentar regenerar la sección de forma segura
                        section_content = context_system.regenerate_section_safely(
                            llm=writer_chain.llm,
                            idea=idea,
                            section_position=section_position,
                            chapter_info=chapter_info
                        )
                    
                    # Añadir contenido a las acumulaciones
                    chapter_content.append(section_content)
                    book[chapter].append(section_content)

                except Exception as e:
                    print_progress(f"Error generando contenido para idea {j}: {str(e)}")
                    print_progress("Intentando recuperar la generación...")
                    
                    # Usar función de recuperación de emergencia
                    from utils import recover_from_model_collapse
                    
                    chapter_details = {
                        'title': chapter_title,
                        'summary': chapter_summary,
                        'idea': idea
                    }
                    
                    fallback_content = recover_from_model_collapse(
                        writer_chain.llm, 
                        chapter_details, 
                        context_system, 
                        section_position
                    )
                    
                    print_progress("Recuperación con contenido alternativo")
                    chapter_content.append(fallback_content)
                    book[chapter].append(fallback_content)
                    continue
            
            # Al final de cada capítulo, generar resumen usando el nuevo sistema
            if len(chapter_content) > 0:
                # Generar resumen optimizado para mantener coherencia entre capítulos
                chapter_summary_final = context_system.create_chapter_summary(
                    llm=summary_chain.llm,
                    chapter_content=chapter_content,
                    chapter_info=chapter_info
                )
                
                # Guardar el resumen
                chapter_summaries[chapter] = chapter_summary_final
            
            print_progress(f"✓ Capítulo {i} completado: {len(chapter_content)} secciones")
            
            # Resetear el contador de chequeos al cambiar de capítulo
            health_check_counter = 0

        print_progress("======================================")
        print_progress("ESCRITURA DEL LIBRO FINALIZADA")
        print_progress("======================================")
        return book

    except Exception as e:
        print_progress(f"Error general en la escritura del libro: {str(e)}")
        raise

def generate_chapter_content_for_limited_context(llm, chapter_details, context_manager, max_chunk_size=700):
    """
    Genera el contenido de un capítulo para modelos con contexto limitado como Gemma 9B
    utilizando una técnica de generación en bloques pequeños con planificación coherente.
    
    Args:
        llm: Modelo de lenguaje a utilizar
        chapter_details: Detalles del capítulo a generar
        context_manager: Gestor de contexto progresivo
        max_chunk_size: Tamaño máximo de cada bloque en palabras
        
    Returns:
        str: Contenido completo del capítulo
    """
    from time import sleep
    import re
    
    # 1. Crear un plan de alto nivel para el capítulo
    plan_prompt = f"""
    Crea un plan detallado para el capítulo '{chapter_details['title']}' de nuestro libro.
    
    Contexto del libro: {context_manager.get_minimal_context()}
    
    El plan debe incluir:
    1. 5-7 secciones clave con subtítulos
    2. Para cada sección, 2-3 puntos principales a desarrollar
    3. Conexiones lógicas entre secciones
    
    Formato simple:
    SECCIÓN 1: [Título]
    - Punto clave 1
    - Punto clave 2
    
    SECCIÓN 2: [Título]
    ...
    """
    
    print("Creando plan de capítulo...")
    chapter_plan = llm(plan_prompt, temperature=0.7)
    
    # 2. Extraer secciones del plan
    sections = []
    current_section = None
    
    for line in chapter_plan.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('SECCIÓN') or re.match(r'^\d+\.', line):
            # Extraer título de sección
            if ':' in line:
                section_title = line.split(':', 1)[1].strip()
            else:
                section_title = line
                
            current_section = {'title': section_title, 'points': []}
            sections.append(current_section)
        elif line.startswith('-') and current_section:
            # Añadir punto clave a la sección actual
            current_section['points'].append(line[1:].strip())
    
    # 3. Generar contenido sección por sección
    full_content = []
    previous_content = ""
    
    for i, section in enumerate(sections):
        print(f"Generando sección {i+1}/{len(sections)}: {section['title']}")
        
        # Contexto para continuidad entre secciones
        continuity_context = ""
        if i > 0:
            # Usar últimas frases de la sección anterior
            words = previous_content.split()
            if words:
                last_words = ' '.join(words[-min(50, len(words)):])
                continuity_context = f"La sección anterior terminó así: '{last_words}'"
        
        # Prompt para generar la sección
        section_prompt = f"""
        Escribe la sección '{section['title']}' del capítulo '{chapter_details['title']}' siguiendo estos puntos clave:
        
        {chr(10).join(['- ' + point for point in section['points']])}
        
        {continuity_context}
        
        Contexto del libro: {context_manager.get_minimal_context()}
        
        La sección debe:
        - Tener aproximadamente {max_chunk_size} palabras
        - Mantener un tono consistente con el resto del libro
        - Fluir naturalmente desde la sección anterior
        - No repetir información ya proporcionada
        """
        
        # Generar contenido de la sección
        section_content = llm(section_prompt, temperature=0.7)
        full_content.append(section_content)
        previous_content = section_content
        
        # Pequeña pausa para evitar sobrecarga y permitir mejor planificación
        sleep(1)
    
    # 4. Generar transiciones suaves entre secciones
    final_content = []
    
    for i, content in enumerate(full_content):
        final_content.append(content)
        
        # Generar transición si no es la última sección
        if i < len(full_content) - 1:
            # Extraer última frase de la sección actual
            current_last_sentence = extract_last_sentence(content)
            
            # Extraer primera frase de la siguiente sección
            next_first_sentence = extract_first_sentence(full_content[i+1])
            
            # Generar transición coherente
            transition_prompt = f"""
            Crea una transición suave de 1-2 frases entre estas ideas:
            
            Idea actual: "{current_last_sentence}"
            
            Siguiente idea: "{next_first_sentence}"
            """
            
            transition = llm(transition_prompt, temperature=0.7)
            final_content.append(transition)
    
    # 5. Unir todo el contenido
    complete_chapter = '\n\n'.join(final_content)
    
    # 6. Revisión final de coherencia (opcional para modelos muy limitados)
    if context_manager.model_capacity != "limited":
        coherence_prompt = f"""
        Revisa este contenido para asegurar coherencia y fluidez. Corrige solo problemas graves de
        continuidad o contradicciones. No cambies el estilo ni la sustancia.
        
        {complete_chapter[:1000]}
        ...
        {complete_chapter[-1000:]}
        """
        
        complete_chapter = llm(coherence_prompt, temperature=0.2)
    
    return complete_chapter

def extract_first_sentence(text):
    """Extrae la primera frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[0] if sentences else ""

def extract_last_sentence(text):
    """Extrae la última frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[-1] if sentences else ""

def optimize_prompt_for_limited_context(prompt, max_length=800, preserve_instructions=True):
    """
    Optimiza un prompt para modelos con contexto limitado como Gemma 9B
    
    Args:
        prompt: El prompt original
        max_length: Longitud máxima deseada en caracteres
        preserve_instructions: Si se deben preservar las instrucciones completas
        
    Returns:
        str: Prompt optimizado
    """
    if len(prompt) <= max_length:
        return prompt
        
    # Dividir en componentes
    parts = prompt.split('\n\n')
    
    # Identificar instrucciones (generalmente al inicio del prompt)
    instructions = parts[0] if parts else ""
    content_parts = parts[1:] if parts else []
    
    # Preservar instrucciones completas si es necesario
    if preserve_instructions:
        optimized_parts = [instructions]
    else:
        # Resumir instrucciones si son muy largas
        if len(instructions) > max_length // 3:
            # Tomar solo primeras líneas de instrucciones
            instruction_lines = instructions.split('\n')
            optimized_parts = ['\n'.join(instruction_lines[:3])]
        else:
            optimized_parts = [instructions]
    
    # Calcular espacio disponible para contenido
    used_length = sum(len(part) for part in optimized_parts)
    available_length = max_length - used_length
    
    # Estrategia: preservar partes más informativas
    # Normalmente las primeras y últimas partes contienen información crítica
    if content_parts and available_length > 0:
        # Siempre incluir primera parte (contexto/tarea principal)
        first_part = content_parts[0]
        if len(first_part) <= available_length * 0.5:
            optimized_parts.append(first_part)
            available_length -= len(first_part)
            content_parts.pop(0)
        else:
            # Truncar primera parte si es necesario
            optimized_parts.append(first_part[:int(available_length * 0.5)])
            available_length -= int(available_length * 0.5)
        
        # Intentar incluir última parte (suele contener el formato deseado)
        if content_parts and available_length > 0:
            last_part = content_parts[-1]
            if len(last_part) <= available_length:
                optimized_parts.append(last_part)
                available_length -= len(last_part)
                content_parts.pop()
            else:
                # Truncar última parte si es necesario
                optimized_parts.append(last_part[-int(available_length):])
                available_length = 0
    
    # Unir partes optimizadas
    optimized_prompt = '\n\n'.join(optimized_parts)
    
    return optimized_prompt
