"""
Sistema de Contexto Progresivo Inteligente para el Generador de Libros IA.

Este módulo implementa un sistema avanzado de gestión de contexto que utiliza
la propia IA para crear resúmenes inteligentes y mantener la coherencia narrativa
sin sobrecargar los LLMs locales.
"""

from utils import BaseEventChain, print_progress, clean_think_tags, extract_content_from_llm_response
import time

class IntelligentContextManager:
    """
    Gestor de contexto inteligente que usa la IA para resumir automáticamente
    y mantener solo la información esencial entre capítulos.
    """
    
    def __init__(self, llm, max_context_size=2000):
        self.llm = llm
        self.max_context_size = max_context_size
        self.book_memory = {
            "global_summary": "",
            "characters": {},
            "plot_threads": [],
            "world_building": {},
            "chapter_summaries": {}
        }
        self.current_chapter_content = []
        self.section_count = 0
        
    def add_section_to_chapter(self, section_content, chapter_key):
        """Añade una nueva sección al capítulo actual"""
        self.current_chapter_content.append(section_content)
        self.section_count += 1
        
        # Cada 3-4 secciones, crear un micro-resumen para evitar acumulación
        if self.section_count % 3 == 0:
            self._create_micro_summary(chapter_key)
    
    def _create_micro_summary(self, chapter_key):
        """Crea un micro-resumen de las últimas secciones para optimizar memoria"""
        if len(self.current_chapter_content) < 3:
            return
            
        print_progress("🔄 Creando micro-resumen para optimizar contexto...")
        
        # Tomar las últimas 3 secciones para resumir
        recent_sections = self.current_chapter_content[-3:]
        combined_text = "\n\n".join(recent_sections)
        
        # Crear prompt para micro-resumen
        prompt = f"""
        Resume las siguientes secciones del capítulo actual manteniendo SOLO los elementos narrativos esenciales.
        Máximo 100 palabras, enfócate en:
        - Eventos clave que afectan la trama
        - Desarrollo de personajes importantes
        - Información que será relevante para continuar la historia
        
        IMPORTANTE: Responde SOLO en español, máximo 100 palabras.
        
        Secciones a resumir:
        {combined_text[:1500]}
        
        Resumen esencial:
        """
        
        try:
            response = self.llm.invoke(prompt)
            micro_summary = clean_think_tags(extract_content_from_llm_response(response))
            
            # Reemplazar las secciones resumidas con el micro-resumen
            if len(micro_summary) > 20:
                # Mantener solo la última sección completa + el micro-resumen
                self.current_chapter_content = [
                    f"[Resumen de secciones anteriores: {micro_summary}]",
                    self.current_chapter_content[-1]  # Última sección completa
                ]
                print_progress("✓ Micro-resumen creado, contexto optimizado")
            
        except Exception as e:
            print_progress(f"⚠️ Error en micro-resumen: {str(e)}, continuando...")
    
    def finalize_chapter(self, chapter_key, chapter_title, chapter_number, total_chapters):
        """
        Finaliza un capítulo creando un resumen completo y transfiriendo
        solo la información esencial al contexto global.
        """
        print_progress(f"📝 Finalizando capítulo {chapter_number}: {chapter_title}")
        
        if not self.current_chapter_content:
            return self._create_fallback_summary(chapter_title, chapter_number)
        
        # Combinar todo el contenido del capítulo
        full_chapter = "\n\n".join(self.current_chapter_content)
        
        # Crear resumen inteligente del capítulo completo
        chapter_summary = self._create_intelligent_chapter_summary(
            full_chapter, chapter_title, chapter_number, total_chapters
        )
        
        # Actualizar memoria global
        self._update_global_memory(chapter_summary, chapter_key, chapter_title)
        
        # Limpiar contenido del capítulo actual
        self.current_chapter_content = []
        self.section_count = 0
        
        return chapter_summary
    
    def _create_intelligent_chapter_summary(self, chapter_content, chapter_title, chapter_number, total_chapters):
        """Crea un resumen inteligente del capítulo usando IA"""
        
        # Optimizar longitud del contenido si es muy largo
        if len(chapter_content) > 3000:
            # Tomar inicio, medio y final del capítulo
            start = chapter_content[:1000]
            middle_pos = len(chapter_content) // 2
            middle = chapter_content[middle_pos-500:middle_pos+500]
            end = chapter_content[-1000:]
            
            optimized_content = f"{start}\n\n[...SECCIÓN MEDIA...]\n\n{middle}\n\n[...SECCIÓN FINAL...]\n\n{end}"
        else:
            optimized_content = chapter_content
        
        prompt = f"""
        Como editor profesional, crea un resumen estratégico del capítulo que será usado para mantener 
        coherencia narrativa en los siguientes capítulos.
        
        IMPORTANTE: 
        - Máximo 200 palabras en español
        - Enfócate en elementos que afectarán capítulos futuros
        - Incluye personajes, eventos clave, y elementos de trama
        - NO incluyas detalles descriptivos innecesarios
        
        Título del libro: [Generación en curso]
        Capítulo: {chapter_title} (Capítulo {chapter_number} de {total_chapters})
        
        Contenido del capítulo:
        {optimized_content}
        
        Resumen estratégico para continuidad narrativa:
        """
        
        try:
            response = self.llm.invoke(prompt)
            summary = clean_think_tags(extract_content_from_llm_response(response))
            
            # Validar y limitar longitud
            if len(summary) > 500:
                summary = summary[:500] + "..."
            
            if len(summary) < 30:
                return self._create_fallback_summary(chapter_title, chapter_number)
                
            print_progress(f"✓ Resumen inteligente del capítulo {chapter_number} creado ({len(summary)} caracteres)")
            return summary
            
        except Exception as e:
            print_progress(f"⚠️ Error en resumen inteligente: {str(e)}")
            return self._create_fallback_summary(chapter_title, chapter_number)
    
    def _create_fallback_summary(self, chapter_title, chapter_number):
        """Crea un resumen básico en caso de error"""
        return f"Capítulo {chapter_number} ({chapter_title}): La historia continúa desarrollándose."
    
    def _update_global_memory(self, chapter_summary, chapter_key, chapter_title):
        """Actualiza la memoria global del libro con información del nuevo capítulo"""
        self.book_memory["chapter_summaries"][chapter_key] = {
            "title": chapter_title,
            "summary": chapter_summary,
            "key_elements": self._extract_key_elements(chapter_summary)
        }
        
        # Actualizar resumen global si hay múltiples capítulos
        if len(self.book_memory["chapter_summaries"]) > 1:
            self._update_global_summary()
    
    def _extract_key_elements(self, chapter_summary):
        """Extrae elementos clave del resumen (personajes, lugares, eventos)"""
        # Implementación básica - puede mejorarse con NLP más avanzado
        key_elements = {
            "characters": [],
            "locations": [],
            "events": []
        }
        
        # Análisis simple basado en patrones comunes
        words = chapter_summary.split()
        for i, word in enumerate(words):
            # Buscar nombres propios (palabras que empiezan con mayúscula)
            if word[0].isupper() and len(word) > 2 and word not in ["El", "La", "Los", "Las", "En", "Con", "Por"]:
                key_elements["characters"].append(word)
        
        return key_elements
    
    def _update_global_summary(self):
        """Actualiza el resumen global del libro basado en todos los capítulos"""
        if len(self.book_memory["chapter_summaries"]) < 2:
            return
            
        # Crear resumen global combinando resúmenes de capítulos
        chapter_summaries = []
        for key, data in self.book_memory["chapter_summaries"].items():
            chapter_summaries.append(f"{data['title']}: {data['summary'][:100]}...")
        
        combined = " | ".join(chapter_summaries)
        
        # Si el resumen global es muy largo, usar IA para condensarlo
        if len(combined) > 800:
            self._condense_global_summary(combined)
        else:
            self.book_memory["global_summary"] = combined
    
    def _condense_global_summary(self, long_summary):
        """Condensa el resumen global usando IA"""
        prompt = f"""
        Condensa el siguiente resumen de la historia manteniendo SOLO los elementos más importantes
        para la coherencia narrativa general. Máximo 300 palabras en español.
        
        Resumen actual:
        {long_summary}
        
        Resumen condensado:
        """
        
        try:
            response = self.llm.invoke(prompt)
            condensed = clean_think_tags(extract_content_from_llm_response(response))
            
            if len(condensed) > 50:
                self.book_memory["global_summary"] = condensed[:400]
                print_progress("✓ Resumen global condensado")
            
        except Exception as e:
            print_progress(f"⚠️ Error condensando resumen global: {str(e)}")
    
    def get_context_for_next_chapter(self, next_chapter_number):
        """
        Obtiene el contexto optimizado para el siguiente capítulo.
        Devuelve solo la información esencial sin sobrecargar el LLM.
        """
        context = {
            "global_summary": self.book_memory.get("global_summary", ""),
            "previous_chapter": "",
            "key_characters": [],
            "plot_continuity": ""
        }
        
        # Obtener resumen del capítulo anterior
        if len(self.book_memory["chapter_summaries"]) > 0:
            last_chapter = list(self.book_memory["chapter_summaries"].values())[-1]
            context["previous_chapter"] = f"{last_chapter['title']}: {last_chapter['summary']}"
        
        # Limitar el contexto total
        total_context = f"{context['global_summary']} {context['previous_chapter']}"
        if len(total_context) > self.max_context_size:
            # Dar prioridad al capítulo anterior sobre el resumen global
            context["global_summary"] = context["global_summary"][:500] + "..."
        
        return context
    
    def get_current_chapter_context(self):
        """Obtiene el contexto del capítulo actual para la siguiente sección"""
        if not self.current_chapter_content:
            return ""
        
        # Devolver las últimas 1-2 secciones como contexto
        recent_sections = self.current_chapter_content[-2:] if len(self.current_chapter_content) > 2 else self.current_chapter_content
        context = "\n\n".join(recent_sections)
        
        # Limitar longitud
        if len(context) > 800:
            context = context[-800:]
        
        return context


class ProgressiveWriterChain(BaseEventChain):
    """
    Cadena de escritura que utiliza el contexto progresivo inteligente
    """
    
    PROMPT_TEMPLATE = """
    Eres un escritor profesional de {genre} en español.
    
    ### INFORMACIÓN ESENCIAL:
    - Título: "{title}"
    - Estilo: {style}
    - Capítulo actual: {chapter_title} (Capítulo {current_chapter} de {total_chapters})
    - Sección: {section_number} de {total_sections}
    
    ### CONTEXTO DE LA HISTORIA:
    {story_context}
    
    ### CONTENIDO RECIENTE DEL CAPÍTULO:
    {recent_content}
    
    ### IDEA A DESARROLLAR:
    {current_idea}
    
    IMPORTANTE: 
    - Escribe EXCLUSIVAMENTE texto narrativo en español
    - NO incluyas notas, comentarios ni explicaciones
    - Mantén la coherencia con el contexto previo
    - Desarrolla la idea de forma natural y envolvente
    
    Texto narrativo:"""

    def run(self, context_manager, genre, style, title, chapter_title, current_idea, 
            current_chapter, total_chapters, section_number, total_sections):
        
        print_progress(f"📝 Escribiendo sección {section_number}/{total_sections} (contexto inteligente)")
        
        try:
            # Obtener contexto optimizado
            story_context = context_manager.get_context_for_next_chapter(current_chapter)
            recent_content = context_manager.get_current_chapter_context()
            
            # Crear contexto narrativo condensado
            context_text = ""
            if story_context.get("global_summary"):
                context_text += f"Historia hasta ahora: {story_context['global_summary'][:300]}\n\n"
            if story_context.get("previous_chapter"):
                context_text += f"Capítulo anterior: {story_context['previous_chapter'][:200]}"
            
            # Generar contenido
            result = self.invoke(
                genre=clean_think_tags(genre),
                style=clean_think_tags(style),
                title=clean_think_tags(title),
                chapter_title=clean_think_tags(chapter_title),
                story_context=clean_think_tags(context_text),
                recent_content=clean_think_tags(recent_content),
                current_idea=clean_think_tags(current_idea),
                current_chapter=current_chapter,
                total_chapters=total_chapters,
                section_number=section_number,
                total_sections=total_sections
            )
            
            print_progress(f"✓ Sección {section_number} completada ({len(result)} caracteres)")
            return result

        except Exception as e:
            print_progress(f"❌ Error generando sección {section_number}: {str(e)}")
            # Fallback simple
            return f"La historia continuó desarrollándose en este punto del capítulo {chapter_title}."