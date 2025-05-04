class MemoryManager:
    """
    Sistema simplificado de gestión de memoria para generación de libros.
    No aplica restricciones basadas en tamaño de contexto o tipo de modelo.
    """
    
    def __init__(self, framework=""):
        self.framework = framework
        self.chapter_memories = {}
        self.global_memory = {}
        
    def add_chapter_memory(self, chapter_key, content):
        """Añade contenido a la memoria de un capítulo"""
        if chapter_key not in self.chapter_memories:
            self.chapter_memories[chapter_key] = []
        self.chapter_memories[chapter_key].append(content)
        
    def get_chapter_context(self, chapter_key, num_memories=None):
        """
        Obtiene el contexto completo para un capítulo.
        No hay restricciones por tipo de modelo o tamaño de contexto.
        """
        if chapter_key not in self.chapter_memories:
            return ""
            
        memories = self.chapter_memories[chapter_key]
        # Usar todas las memorias disponibles 
        # (sin importar límites de contexto o tipo de modelo)
        if num_memories is None or num_memories >= len(memories):
            return "\n\n".join(memories)
        else:
            # Si se especifica un número, usar las más recientes
            return "\n\n".join(memories[-num_memories:])
            
    def add_global_memory(self, key, value):
        """Añade una memoria global con una clave específica"""
        self.global_memory[key] = value
        
    def get_global_memory(self, key):
        """Obtiene una memoria global"""
        return self.global_memory.get(key, "")
        
    def get_summary_for_chapter(self, chapter_key):
        """Obtiene un resumen para el capítulo"""
        # Siempre devuelve todas las memorias disponibles
        return self.get_chapter_context(chapter_key)
    
    def get_context_for_writing(self, chapter_key, prev_chapters=None):
        """
        Obtiene contexto para escritura.
        Proporciona todo el contexto disponible sin límites.
        """
        context = {}
        
        # Añadir el marco narrativo general
        context["framework"] = self.framework
        
        # Añadir contexto de capítulos previos si se especifican
        if prev_chapters:
            prev_context = []
            for prev_key in prev_chapters:
                if prev_key in self.chapter_memories:
                    prev_context.append(self.get_summary_for_chapter(prev_key))
            context["previous_chapters"] = "\n\n".join(prev_context)
        
        # Añadir contexto del capítulo actual
        if chapter_key in self.chapter_memories:
            context["current_chapter"] = self.get_chapter_context(chapter_key)
        
        # Añadir todas las memorias globales disponibles
        context["global"] = self.global_memory
        
        return context