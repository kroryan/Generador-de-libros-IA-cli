from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response, BaseChain
from chapter_summary import ChapterSummaryChain, ProgressiveContextManager
from emergency_prompts import emergency_prompts
from example_library import ExampleLibrary
from section_quality_monitor import SectionQualityMonitor
from time import sleep
import re
import time  # Importación añadida para usar time.sleep()
import os    # Importación añadida para variables de entorno

# FASE 4: Importar configuración centralizada
from config.defaults import get_config

# Obtener configuración
_config = get_config()
_context_config = _config.context
_rate_limit_config = _config.rate_limit

class WriterChain(BaseEventChain):
    # Template zero-shot original
    ZERO_SHOT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### INFORMACIÓN ESENCIAL:
    - Título: "{title}"
    - Estilo: {style}
    - Capítulo actual: {chapter_title} (Capítulo {current_chapter} de {total_chapters})
    - Posición: {section_position} del capítulo
    
    ### CONTEXTO RESUMIDO:
    {summary}
    
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
    - Solo genera el texto que formaría parte del libro final
    
    Escribe directamente el contenido narrativo:"""

    # Nuevo template few-shot con ejemplos
    FEW_SHOT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### INFORMACIÓN ESENCIAL:
    - Título: "{title}"
    - Estilo: {style}
    - Capítulo actual: {chapter_title} (Capítulo {current_chapter} de {total_chapters})
    - Posición: {section_position} del capítulo
    
    ### EJEMPLOS DE REFERENCIA:
    
    A continuación se muestran ejemplos de secciones bien escritas en este género/estilo:
    
    {examples}
    
    ### CONTEXTO RESUMIDO:
    {summary}
    
    ### PÁRRAFOS RECIENTES:
    {previous_paragraphs}
    
    ### IDEA A DESARROLLAR AHORA:
    {current_idea}
    
    <think>
    Analizaré los ejemplos para capturar:
    1. Tono y ritmo narrativo característico del género
    2. Nivel de detalle descriptivo apropiado
    3. Balance entre acción, diálogo y descripción
    4. Técnicas de transición entre escenas
    
    Luego desarrollaré la idea actual manteniendo:
    - Conexión directa con el contenido reciente
    - Desarrollo coherente de personajes y situaciones
    - Avance natural de la historia
    - Calidad similar a los ejemplos mostrados
    </think>
    
    IMPORTANTE: 
    - Escribe EXCLUSIVAMENTE texto narrativo en español
    - Mantén el nivel de calidad de los ejemplos mostrados
    - NO incluyas notas, comentarios ni explicaciones
    - Solo genera el texto que formaría parte del libro final
    
    Escribe directamente el contenido narrativo:"""
    
    def __init__(self, use_few_shot: bool = True):
        """
        Args:
            use_few_shot: Si True, usa prompts con ejemplos. Si False, usa zero-shot.
        """
        super().__init__()
        
        # NUEVO: Configurar few-shot learning
        self.use_few_shot = use_few_shot
        if self.use_few_shot:
            self.example_library = ExampleLibrary()
            self.PROMPT_TEMPLATE = self.FEW_SHOT_TEMPLATE
        else:
            self.PROMPT_TEMPLATE = self.ZERO_SHOT_TEMPLATE

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
            # Limpiar todas las entradas de posibles cadenas de pensamiento
            summary_clean = clean_think_tags(summary)
            previous_paragraphs_clean = clean_think_tags(previous_paragraphs)
            current_idea_clean = clean_think_tags(current_idea)
            
            # FASE 4: Usar configuración en lugar de valores mágicos
            # Optimizar longitud del contexto para evitar sobrecarga
            if len(previous_paragraphs_clean) > _context_config.limited_context_size:
                previous_paragraphs_clean = previous_paragraphs_clean[-_context_config.limited_context_size:] 
            
            # NUEVO: Obtener ejemplos relevantes si few-shot está activado
            examples_text = ""
            if self.use_few_shot:
                examples_text = self._get_formatted_examples(
                    genre=genre,
                    style=style,
                    section_position=section_position
                )
            
            # Invocar con o sin ejemplos según configuración
            invoke_params = {
                'genre': clean_think_tags(genre),
                'style': clean_think_tags(style),
                'title': clean_think_tags(title),
                'chapter_title': clean_think_tags(chapter_title),
                'summary': summary_clean,
                'previous_paragraphs': previous_paragraphs_clean,
                'current_idea': current_idea_clean,
                'current_chapter': current_chapter,
                'total_chapters': total_chapters,
                'section_position': section_position,
                'section_number': section_number,
                'total_sections': total_sections
            }
            
            # Solo añadir ejemplos si estamos usando few-shot
            if self.use_few_shot:
                invoke_params['examples'] = examples_text
            
            result = self.invoke(**invoke_params)
            
            # El resultado ya viene limpio por el invoke() de BaseChain
            print_progress(f"Sección completada: {len(result)} caracteres")
            return result

        except Exception as e:
            print_progress(f"Error generando contenido: {str(e)}")
            raise
    
    def _get_formatted_examples(
        self, 
        genre: str, 
        style: str, 
        section_position: str
    ) -> str:
        """
        Recupera y formatea ejemplos relevantes para el prompt.
        
        Args:
            genre: Género del libro
            style: Estilo de escritura
            section_position: inicio/medio/final
            
        Returns:
            String formateado con 1-2 ejemplos
        """
        try:
            # Obtener número máximo de ejemplos desde configuración
            max_examples = _config.few_shot.max_examples_per_prompt
            
            # Obtener ejemplos de la biblioteca
            examples = self.example_library.get_examples(
                genre=genre,
                style=style,
                section_type=section_position,
                max_examples=max_examples
            )
            
            if not examples:
                # Fallback: buscar sin filtro de tipo
                examples = self.example_library.get_examples(
                    genre=genre,
                    style=style,
                    max_examples=max_examples
                )
            
            if not examples:
                return "[No hay ejemplos disponibles para este género/estilo]"
            
            # Formatear ejemplos para el prompt
            formatted = []
            for i, ex in enumerate(examples, 1):
                formatted.append(f"""
**EJEMPLO {i}:**

Contexto previo:
{ex.context}

Idea desarrollada:
{ex.idea}

Texto generado:
{ex.content}

---
""")
            
            return "\n".join(formatted)
            
        except Exception as e:
            print_progress(f"⚠️ Error obteniendo ejemplos: {str(e)}")
            return "[Error cargando ejemplos]"

def regenerate_problematic_section(writer_chain, context_manager, section_params, max_attempts=3):
    """
    Intenta regenerar una sección que ha mostrado problemas o señales de colapso.
    Ahora usa el sistema centralizado de prompts de emergencia.
    """
    print_progress("🔄 Intentando regenerar sección problemática...")
    
    # Extractores de parámetros clave
    chapter_key = section_params.get('chapter_key', 'capítulo actual')
    chapter_title = section_params.get('chapter_title', 'este capítulo')
    current_idea = section_params.get('current_idea', '')
    
    try:
        # Usar prompt de emergencia centralizado en lugar de lógica de reintentos manual
        emergency_prompt = emergency_prompts.get_section_regeneration_prompt(
            context_summary=f"Capítulo: {chapter_title}",
            previous_content=section_params.get('previous_paragraphs', '')[:200]
        )
        
        # Ejecutar con el sistema de reintentos integrado en BaseChain
        response = writer_chain.llm.invoke(emergency_prompt)
        content = clean_think_tags(extract_content_from_llm_response(response))
        
        if content and len(content.strip()) > 50:
            print_progress("✅ Regeneración exitosa usando prompt de emergencia")
            return content
            
    except Exception as e:
        print_progress(f"Error en regeneración con prompt de emergencia: {str(e)}")
    
    # Si todo falla, usar texto de contingencia
    print_progress("⚠️ Usando texto de contingencia tras fallo de regeneración")
    return f"La escena continuó desarrollándose. Los personajes avanzaron en su objetivo mientras exploraban {chapter_title}."

def create_savepoint_summary(llm, title, chapter_num, chapter_title, current_summary, new_section, total_chapters=None):
    """
    Sistema simplificado y autónomo para crear resúmenes incrementales como puntos de guardado.
    No depende de ChapterSummaryChain, evitando así los errores de parámetros faltantes.
    """
    print_progress(f"Actualizando resumen del capítulo {chapter_num} para savepoint...")
    
    try:
        # Si no hay resumen previo, crear uno básico
        if not current_summary or current_summary.strip() == "":
            current_summary = f"Inicio del capítulo {chapter_num}: {chapter_title}"
        
        # Si la nueva sección es muy larga, limitarla para el análisis
        if len(new_section) > 1500:
            summary_section = new_section[:750] + "\n\n[...]\n\n" + new_section[-750:]
        else:
            summary_section = new_section
            
        # Prompt directo y simple para generar el resumen
        prompt = f"""
        Actualiza el resumen existente para incorporar solo los elementos esenciales 
        de la nueva sección. Mantén el resumen muy breve y centrado solo en lo crucial.
        
        IMPORTANTE: Máximo 150 palabras, solo en español.
        
        Título: {clean_think_tags(title)}
        Capítulo: {clean_think_tags(chapter_title)} (Capítulo {chapter_num})
        
        Resumen actual:
        {clean_think_tags(current_summary)}
        
        Nueva sección:
        {clean_think_tags(summary_section)}
        
        Resumen actualizado:
        """
        
        # Usar directamente el LLM para evitar problemas con las clases de resumen
        # BaseChain ahora maneja los reintentos automáticamente, eliminamos lógica manual
        try:
            # Invocar directamente al modelo - los reintentos están en BaseChain
            result = llm.invoke(prompt)
            # Extraer y limpiar la respuesta
            text_result = extract_content_from_llm_response(result)
            updated_summary = clean_think_tags(text_result)
            
            # Verificar si el resultado es válido
            if updated_summary and len(updated_summary) > 20:
                # Limitar la longitud para evitar resúmenes excesivamente largos
                if len(updated_summary) > 500:
                    updated_summary = updated_summary[:500] + "..."
                return updated_summary
            else:
                # Si no hay resultado válido, usar prompt de emergencia
                emergency_prompt = emergency_prompts.get_summary_emergency_prompt(new_section[:300])
                emergency_result = llm.invoke(emergency_prompt)
                return clean_think_tags(extract_content_from_llm_response(emergency_result))
                    
        except Exception as e:
            print_progress(f"Error creando resumen: {str(e)}")
            # Usar prompt de emergencia como fallback
            try:
                emergency_prompt = emergency_prompts.get_summary_emergency_prompt(new_section[:300])
                emergency_result = llm.invoke(emergency_prompt)
                return clean_think_tags(extract_content_from_llm_response(emergency_result))
            except:
                # Si todo falla, devolver el resumen actual sin cambios
                print_progress("No se pudo generar un nuevo resumen, manteniendo el actual")
                return current_summary
        
        # Si todos los intentos fallan, devolver el resumen actual sin cambios
        print_progress("No se pudo generar un nuevo resumen, manteniendo el actual")
        return current_summary
        
    except Exception as e:
        print_progress(f"Error creando savepoint: {str(e)}")
        return current_summary  # En caso de error, devolver el resumen anterior

def write_book(genre, style, profile, title, framework, summaries_dict, idea_dict, chapter_summaries=None):
    print_progress("Iniciando escritura del libro...")
    
    # NUEVO: Usar configuración centralizada para few-shot learning
    config = _config
    few_shot_config = config.few_shot
    
    # Inicializar monitor de calidad con configuración
    quality_monitor = SectionQualityMonitor(
        quality_threshold=few_shot_config.quality_threshold,
        auto_save=few_shot_config.auto_save_examples
    )
    
    # Inicializar WriterChain con configuración few-shot
    writer_chain = WriterChain(use_few_shot=few_shot_config.enabled)
    book = {}
    
    # Si no hay resúmenes de capítulos, crear un diccionario vacío
    if chapter_summaries is None:
        chapter_summaries = {}

    # NUEVO: Inicializar el gestor de contexto con sistema dinámico
    try:
        from dynamic_context import DynamicContextCalculator, ModelContextProfile
        
        # Intentar detectar el modelo desde variables de entorno
        model_type = os.environ.get("MODEL_TYPE", "ollama")
        model_name = "unknown"
        
        # Crear calculador dinámico
        context_calc = DynamicContextCalculator(model_name, model_type)
        
        # Inicializar contexto manager con perfil dinámico y LLM
        context_manager = ProgressiveContextManager(
            framework=framework,
            llm=writer_chain.llm,  # Pasar LLM para micro-resúmenes
            enable_micro_summaries=True,  # Activar micro-resúmenes
            micro_summary_interval=3,     # Cada 3 secciones
            model_profile=context_calc.profile
        )
        
        print_progress("🧠 Sistema de contexto dinámico inicializado")
        
    except Exception as e:
        print_progress(f"⚠️ Error inicializando contexto dinámico: {e}")
        print_progress("🔄 Usando sistema de contexto tradicional")
        context_manager = ProgressiveContextManager(framework)
    
    summary_chain = ChapterSummaryChain()

    try:
        total_chapters = len(idea_dict)
        
        # Usar sistema inteligente de ordenamiento O(n log n)
        from chapter_ordering import sort_chapters_intelligently
        ordered_chapters = sort_chapters_intelligently(idea_dict)
        
        # Procesar capítulos en el orden establecido
        for i, chapter in enumerate(ordered_chapters, 1):
            idea_list = idea_dict[chapter]
            
            print_progress(f"======================================")
            print_progress(f"CAPÍTULO {i}/{total_chapters}: {chapter}")
            print_progress(f"======================================")
            
            book[chapter] = []
            ideas_total = len(idea_list)
            chapter_content = []
            
            # Obtener resumen del capítulo
            chapter_summary = summaries_dict.get(chapter, "")
            
            # Registrar el capítulo en el gestor de contexto
            context_manager.register_chapter(chapter, chapter, chapter_summary)
            
            # Acumular texto para contexto
            paragraphs_context = ""
            
            # Crear un resumen incremental que se actualizará durante la escritura
            savepoint_summary = f"Inicio del capítulo {i}: {chapter}"
            
            # Definir intervalo para puntos de guardado (cada cuántas ideas se crea un savepoint)
            savepoint_interval = max(1, min(3, ideas_total // 3))  # Al menos 3 savepoints por capítulo
            
            for j, idea in enumerate(idea_list, 1):
                # Determinar posición en el capítulo
                section_position = "medio"
                if j == 1:
                    section_position = "inicio"
                elif j == ideas_total:
                    section_position = "final"
                
                # Mostrar parte de la idea en la consola
                idea_preview = idea[:40] + "..." if len(idea) > 40 else idea
                print_progress(f">> Idea {j}/{ideas_total}: {idea_preview}")
                
                # SISTEMA DE SAVEPOINTS: Verificar si toca crear un punto de guardado
                is_savepoint = (j == 1 or j == ideas_total or j % savepoint_interval == 0)
                
                if is_savepoint and paragraphs_context:
                    try:
                        print_progress("📌 Creando punto de guardado (savepoint)...")
                        # Usar nuestra nueva función independiente que no requiere de ChapterSummaryChain
                        savepoint_summary = create_savepoint_summary(
                            llm=writer_chain.llm,
                            title=title,
                            chapter_num=i,
                            chapter_title=chapter,
                            current_summary=savepoint_summary,
                            new_section=paragraphs_context[-1500:] if len(paragraphs_context) > 1500 else paragraphs_context,
                            total_chapters=total_chapters
                        )
                        print_progress("✓ Punto de guardado creado")
                        
                        # Cada ciertos savepoints (2-3), limpiar el contexto acumulado para evitar sobrecarga
                        if j > savepoint_interval * 2:
                            # Mantener solo las últimas 2-3 secciones y reemplazar el resto con el resumen
                            recent_sections = chapter_content[-2:] if len(chapter_content) > 2 else chapter_content
                            paragraphs_context = f"[Resumen hasta ahora: {savepoint_summary}]\n\n" + "\n\n".join(recent_sections)
                            print_progress("🧹 Contexto optimizado para continuar")
                    except Exception as e:
                        print_progress(f"⚠️ Error creando savepoint: {str(e)}")
                        # Si ocurre un error al crear el savepoint, seguir adelante con el resumen actual
                        # Esto garantiza que un error en el resumen no interrumpa la generación del libro
                
                # Preparar los parámetros para la generación de contenido
                section_params = {
                    'genre': genre,
                    'style': style,
                    'title': title,
                    'context_manager': context_manager,
                    'chapter_title': chapter,
                    'summary': chapter_summary if j == 1 else savepoint_summary,  # Usar resumen incremental
                    # FASE 4: Usar configuración en lugar de valor mágico 800
                    'previous_paragraphs': paragraphs_context[-_context_config.limited_context_size:] if paragraphs_context else "",
                    'current_idea': idea,
                    'current_chapter': i,
                    'total_chapters': total_chapters,
                    'section_position': section_position,
                    'section_number': j,
                    'total_sections': ideas_total,
                    'chapter_key': chapter
                }
                
                # Usar un sistema simplificado sin reintentos manuales
                try:
                    # Usar BaseChain que ya tiene reintentos integrados
                    section_content = writer_chain.run(**section_params)
                    
                    # Verificar si el contenido es válido
                    if section_content and len(section_content.strip()) >= 50:
                        pass  # Contenido válido, continuar
                    else:
                        # Si el contenido no es válido, usar prompt de emergencia
                        emergency_prompt = emergency_prompts.get_writing_emergency_prompt(
                            chapter_title=chapter,
                            idea=idea[:100]
                        )
                        raw_response = writer_chain.llm.invoke(emergency_prompt)
                        section_content = clean_think_tags(extract_content_from_llm_response(raw_response))
                
                except Exception as e:
                    print_progress(f"Error en generación: {str(e)}")
                    # Usar prompt de emergencia como fallback
                    emergency_prompt = emergency_prompts.get_writing_emergency_prompt(
                        chapter_title=chapter,
                        idea=idea[:100]
                    )
                    try:
                        raw_response = writer_chain.llm.invoke(emergency_prompt)
                        section_content = clean_think_tags(extract_content_from_llm_response(raw_response))
                    except:
                        # Último recurso: texto de respaldo
                        section_content = f"La historia continuó desarrollándose en {chapter}. Los personajes avanzaron en su objetivo mientras enfrentaban nuevos desafíos."
                
                # Si después de todos los intentos no hay contenido válido, usar texto de respaldo
                if not section_content or len(section_content.strip()) < 50:
                    print_progress("⚠️ Usando texto de respaldo tras múltiples fallos")
                    section_content = f"La historia continuó desarrollándose en {chapter}. Los personajes avanzaron en su objetivo mientras enfrentaban nuevos desafíos."
                
                # NUEVO: Evaluar y potencialmente guardar como ejemplo
                quality_score = quality_monitor.evaluate_and_store(
                    section_content=section_content,
                    genre=genre,
                    style=style,
                    section_position=section_position,
                    context=paragraphs_context[-200:] if paragraphs_context else "",
                    idea=idea,
                    book_title=title
                )
                
                if quality_score:
                    print_progress(f"📊 Calidad de sección: {quality_score:.2f}")
                
                # Actualizar contexto en el gestor y guardar el contenido
                context_manager.update_chapter_content(chapter, section_content)
                
                # FASE 4: Usar configuración en lugar de valores mágicos 5000/3000
                # Actualizar contexto acumulado (limitar para evitar sobrecarga)
                if len(paragraphs_context) > _context_config.max_context_accumulation:
                    # Mantener solo la parte más reciente
                    paragraphs_context = paragraphs_context[-_context_config.standard_context_size:]
                    
                # Añadir nuevo contenido al contexto
                paragraphs_context += "\n\n" + section_content
                
                # Guardar el contenido generado
                chapter_content.append(section_content)
                book[chapter].append(section_content)
                
                # FASE 4: Usar rate limiting de configuración
                # Pequeña pausa entre secciones para evitar problemas con APIs
                time.sleep(_rate_limit_config.default_delay)
            
            # Al finalizar el capítulo, generar un resumen completo para usar en el siguiente capítulo
            try:
                chapter_complete_text = "\n\n".join(chapter_content)
                chapter_summaries[chapter] = summary_chain.run(
                    title=title,
                    chapter_num=i,
                    chapter_title=chapter,
                    chapter_content=chapter_complete_text,
                    total_chapters=total_chapters
                )
                print_progress(f"✓ Resumen final del capítulo {i} generado")
            except Exception as e:
                print_progress(f"⚠️ Error generando resumen final: {str(e)}")
                chapter_summaries[chapter] = savepoint_summary
            
            # NUEVO: Mostrar reporte dinámico al finalizar el capítulo
            try:
                if hasattr(context_manager, 'get_dynamic_status'):
                    dynamic_status = context_manager.get_dynamic_status()
                    if dynamic_status.get('dynamic_enabled', False):
                        complexity_report = dynamic_status.get('complexity_report', {})
                        quality_report = dynamic_status.get('quality_report', {})
                        
                        print_progress("📊 REPORTE DINÁMICO DEL CAPÍTULO:")
                        if complexity_report.get('overall_complexity'):
                            print_progress(f"   Complejidad narrativa: {complexity_report['complexity_category']} "
                                         f"({complexity_report['overall_complexity']:.2f})")
                            entities = complexity_report.get('entities', {})
                            print_progress(f"   Personajes detectados: {entities.get('character_count', 0)}")
                            print_progress(f"   Ubicaciones detectadas: {entities.get('location_count', 0)}")
                        
                        if quality_report.get('average_quality'):
                            print_progress(f"   Calidad de resúmenes: {quality_report['quality_category']} "
                                         f"({quality_report['average_quality']:.2f})")
                            print_progress(f"   Factor de agresividad: {quality_report['aggressiveness_factor']:.1f}x")
                        
                        current_limits = dynamic_status.get('current_limits', {})
                        if current_limits:
                            print_progress(f"   Límites dinámicos actuales:")
                            print_progress(f"     - Sección: {current_limits.get('max_section_context', 'N/A')} chars")
                            print_progress(f"     - Capítulo: {current_limits.get('max_chapter_context', 'N/A')} chars")
            except Exception as e:
                print_progress(f"⚠️ Error mostrando reporte dinámico: {e}")
            
            print_progress(f"✓ Capítulo {chapter} completado: {len(chapter_content)} secciones")

        # Al final de la generación, mostrar estadísticas de calidad
        stats = quality_monitor.get_session_stats()
        print_progress("\n" + "="*50)
        print_progress("📈 ESTADÍSTICAS DE FEW-SHOT LEARNING:")
        print_progress(f"  Secciones evaluadas: {stats['sections_evaluated']}")
        print_progress(f"  Secciones guardadas como ejemplos: {stats['sections_saved']}")
        print_progress(f"  Calidad promedio: {stats['average_quality']:.2f}")
        print_progress(f"  Calidad máxima: {stats['max_quality']:.2f}")
        print_progress(f"  Calidad mínima: {stats['min_quality']:.2f}")
        print_progress(f"  Tasa de guardado: {stats['save_rate']:.1%}")
        print_progress("="*50 + "\n")
        
        print_progress("======================================")
        print_progress("ESCRITURA DEL LIBRO FINALIZADA")
        print_progress("======================================")
        return book

    except Exception as e:
        print_progress(f"Error general en la escritura del libro: {str(e)}")
        raise  # Propagar el error para detener la ejecución

def optimize_prompt_for_limited_context(prompt, max_length=None, preserve_instructions=True):
    """
    Versión simplificada que no modifica los prompts.
    Todos los modelos reciben el prompt completo sin optimizaciones.
    """
    # Devolver el prompt original sin modificaciones
    return prompt

def extract_first_sentence(text):
    """Extrae la primera frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[0] if sentences else ""

def extract_last_sentence(text):
    """Extrae la última frase de un texto"""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[-1] if sentences else ""
