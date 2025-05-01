import re
import string
from collections import Counter

class EntityExtractor:
    """
    Sistema para extraer automáticamente personajes, lugares y conceptos clave
    de un texto narrativo, manteniendo un seguimiento de qué entidades están 
    actualmente activas en cada escena.
    """
    
    def __init__(self):
        self.known_entities = {
            "characters": set(),  # Personajes conocidos
            "locations": set(),   # Lugares
            "objects": set(),     # Objetos importantes
            "concepts": set()     # Conceptos abstractos clave
        }
        
        # Perfil y estado de entidades
        self.entity_profiles = {}
        
        # Registro histórico de entidades por capítulo
        self.chapter_entities = {}
        
        # Filtros para eliminar falsos positivos comunes
        self.common_words = {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", 
            "a", "ante", "bajo", "con", "contra", "de", "desde", "en", "entre",
            "hacia", "hasta", "para", "por", "según", "sin", "sobre", "tras"
        }
    
    def extract_entities_from_text(self, text, chapter_num=None, is_new_character=False):
        """
        Extrae entidades de un fragmento de texto narrativo.
        
        Args:
            text: Texto a analizar
            chapter_num: Número de capítulo (opcional)
            is_new_character: Si debemos buscar agresivamente nuevos personajes
        
        Returns:
            dict: Entidades extraídas por categoría
        """
        if not text:
            return {"characters": [], "locations": [], "objects": [], "concepts": []}
        
        # 1. Extraer posibles nombres propios (primera letra mayúscula)
        words = text.split()
        proper_nouns = []
        
        for i, word in enumerate(words):
            word_clean = word.strip(string.punctuation)
            
            # Para evitar incluir palabras con mayúscula al inicio de frase
            is_sentence_start = i == 0 or words[i-1][-1] in ".!?"
            
            if (word_clean and word_clean[0].isupper() and not is_sentence_start and 
                len(word_clean) > 2 and word_clean.lower() not in self.common_words):
                # Capturar nombres compuestos
                if i < len(words) - 1 and words[i+1][0].isupper():
                    proper_nouns.append(f"{word_clean} {words[i+1].strip(string.punctuation)}")
                else:
                    proper_nouns.append(word_clean)
        
        # 2. Detectar personajes por patrones contextuales
        characters = self._extract_characters(text, proper_nouns, is_new_character)
        
        # 3. Detectar lugares
        locations = self._extract_locations(text, proper_nouns)
        
        # 4. Detectar objetos importantes
        objects = self._extract_objects(text)
        
        # 5. Detectar conceptos abstractos clave
        concepts = self._extract_concepts(text)
        
        # Actualizar entidades conocidas
        self.known_entities["characters"].update(characters)
        self.known_entities["locations"].update(locations)
        self.known_entities["objects"].update(objects)
        self.known_entities["concepts"].update(concepts)
        
        # Registrar entidades de este capítulo
        if chapter_num is not None:
            if chapter_num not in self.chapter_entities:
                self.chapter_entities[chapter_num] = {
                    "characters": set(),
                    "locations": set(),
                    "objects": set(),
                    "concepts": set()
                }
            
            self.chapter_entities[chapter_num]["characters"].update(characters)
            self.chapter_entities[chapter_num]["locations"].update(locations)
            self.chapter_entities[chapter_num]["objects"].update(objects)
            self.chapter_entities[chapter_num]["concepts"].update(concepts)
        
        return {
            "characters": list(characters),
            "locations": list(locations),
            "objects": list(objects),
            "concepts": list(concepts)
        }
    
    def _extract_characters(self, text, proper_nouns, is_new_character):
        """Extrae personajes del texto usando análisis contextual"""
        characters = set()
        
        # 1. Revisar nombres propios ya conocidos
        for char in self.known_entities["characters"]:
            if char in text:
                characters.add(char)
        
        # 2. Buscar patrones que sugieran nuevos personajes
        character_indicators = [
            r'([A-Z][a-zá-úñ]+) dijo', r'([A-Z][a-zá-úñ]+) respondió',
            r'([A-Z][a-zá-úñ]+) preguntó', r'([A-Z][a-zá-úñ]+) exclamó',
            r'([A-Z][a-zá-úñ]+) pensó', r'respondió ([A-Z][a-zá-úñ]+)',
            r'preguntó ([A-Z][a-zá-úñ]+)', r'miró a ([A-Z][a-zá-úñ]+)',
        ]
        
        for pattern in character_indicators:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and match.lower() not in self.common_words:
                    characters.add(match)
        
        # 3. Para presentación de nuevos personajes, ser más agresivo
        if is_new_character:
            # Usar todos los nombres propios que no sean lugares conocidos
            for noun in proper_nouns:
                if noun not in self.known_entities["locations"] and noun.lower() not in self.common_words:
                    characters.add(noun)
        
        return characters
    
    def _extract_locations(self, text, proper_nouns):
        """Extrae lugares del texto"""
        locations = set()
        
        # 1. Revisar lugares ya conocidos
        for loc in self.known_entities["locations"]:
            if loc in text:
                locations.add(loc)
        
        # 2. Buscar patrones que sugieran nuevos lugares
        location_indicators = [
            r'en ([A-Z][a-zá-úñ]+)', r'a ([A-Z][a-zá-úñ]+)', 
            r'de ([A-Z][a-zá-úñ]+)', r'desde ([A-Z][a-zá-úñ]+)',
            r'hacia ([A-Z][a-zá-úñ]+)', r'El ([A-Z][a-zá-úñ]+)',
            r'La ([A-Z][a-zá-úñ]+)', r'el ([A-Z][a-zá-úñ]+) donde',
            r'la ([A-Z][a-zá-úñ]+) donde'
        ]
        
        for pattern in location_indicators:
            matches = re.findall(pattern, text)
            for match in matches:
                # Verificar que no sea un personaje conocido
                if (match and match not in self.known_entities["characters"] and 
                    match.lower() not in self.common_words):
                    locations.add(match)
        
        return locations
    
    def _extract_objects(self, text):
        """Extrae objetos importantes del texto"""
        objects = set()
        
        # 1. Revisar objetos ya conocidos
        for obj in self.known_entities["objects"]:
            if obj in text:
                objects.add(obj)
        
        # 2. Buscar patrones que sugieran objetos importantes
        object_patterns = [
            r'la ([a-zá-úñ]+) mágica', r'el ([a-zá-úñ]+) mágico',
            r'su ([a-zá-úñ]+)', r'un ([a-zá-úñ]+) único',
            r'una ([a-zá-úñ]+) única', r'el legendario ([a-zá-úñ]+)',
            r'la legendaria ([a-zá-úñ]+)', r'el antiguo ([a-zá-úñ]+)',
            r'la antigua ([a-zá-úñ]+)', r'el poderoso ([a-zá-úñ]+)',
            r'la poderosa ([a-zá-úñ]+)'
        ]
        
        for pattern in object_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and len(match) > 3 and match.lower() not in self.common_words:
                    objects.add(match)
        
        return objects
    
    def _extract_concepts(self, text):
        """Extrae conceptos abstractos clave del texto"""
        concepts = set()
        
        # 1. Revisar conceptos ya conocidos
        for concept in self.known_entities["concepts"]:
            if concept in text:
                concepts.add(concept)
        
        # 2. Buscar patrones que sugieran conceptos importantes
        concept_patterns = [
            r'la ([a-zá-úñ]+) de los', r'el ([a-zá-úñ]+) de los',
            r'la ([a-zá-úñ]+) antigua', r'el ([a-zá-úñ]+) antiguo',
            r'la ([a-zá-úñ]+) mística', r'el ([a-zá-úñ]+) místico',
            r'la ([a-zá-úñ]+) eterna', r'el ([a-zá-úñ]+) eterno'
        ]
        
        abstract_concepts = [
            "magia", "poder", "destino", "tiempo", "espacio", "energía",
            "sabiduría", "conocimiento", "eternidad", "oscuridad", "luz",
            "alma", "espíritu", "vida", "muerte", "guerra", "paz", "verdad"
        ]
        
        # Buscar conceptos abstractos comunes
        for concept in abstract_concepts:
            if concept in text.lower():
                concepts.add(concept)
        
        # Buscar patrones específicos
        for pattern in concept_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and len(match) > 3 and match.lower() not in self.common_words:
                    concepts.add(match)
        
        return concepts
    
    def get_active_entities(self, text, chapter_num=None):
        """
        Determina qué entidades están activas en un fragmento de texto,
        priorizando personajes y otros elementos relevantes para la escena actual.
        
        Args:
            text: Texto de la escena actual
            chapter_num: Número de capítulo actual
            
        Returns:
            list: Lista de entidades activas en esta escena
        """
        # Extraer todas las entidades del texto
        all_entities = self.extract_entities_from_text(text, chapter_num)
        
        # Priorizar personajes y lugares activos
        active_entities = all_entities["characters"].copy()
        
        # Añadir lugares solo si son relevantes para la escena actual
        for location in all_entities["locations"]:
            # Verificar que el lugar se menciona explícitamente en este fragmento
            if location in text:
                active_entities.append(location)
        
        # Añadir objetos importantes si están en uso en la escena
        for obj in all_entities["objects"]:
            if obj in text:
                active_entities.append(obj)
        
        # Ordenar por importancia (frecuencia de mención)
        entity_counts = Counter()
        for entity in active_entities:
            entity_counts[entity] = text.count(entity)
        
        # Devolver las 5-7 entidades más relevantes 
        return [entity for entity, _ in entity_counts.most_common(7)]
    
    def update_entity_profile(self, entity_name, entity_type, profile_info):
        """
        Actualiza el perfil de una entidad con nueva información
        
        Args:
            entity_name: Nombre de la entidad
            entity_type: Tipo de entidad (character, location, etc.)
            profile_info: Diccionario con información a añadir/actualizar
        """
        if entity_name not in self.entity_profiles:
            self.entity_profiles[entity_name] = {
                "type": entity_type,
                "name": entity_name,
                "mentions": 0,
                "first_chapter": None,
                "last_chapter": None
            }
        
        # Actualizar perfil con nueva información
        self.entity_profiles[entity_name].update(profile_info)
        
        # Incrementar contador de menciones
        self.entity_profiles[entity_name]["mentions"] += 1
        
        # Añadir a entidades conocidas
        self.known_entities[f"{entity_type}s"].add(entity_name)
    
    def get_entity_profile(self, entity_name):
        """Obtiene el perfil completo de una entidad"""
        return self.entity_profiles.get(entity_name, {"name": entity_name, "type": "unknown"})
    
    def get_chapter_entities(self, chapter_num):
        """Obtiene todas las entidades mencionadas en un capítulo específico"""
        return self.chapter_entities.get(chapter_num, {
            "characters": [], 
            "locations": [], 
            "objects": [], 
            "concepts": []
        })
        
    def get_most_relevant_entities(self, current_chapter=None, top_n=5):
        """
        Obtiene las entidades más relevantes para el contexto actual,
        basado en frecuencia de mención y aparición reciente.
        
        Args:
            current_chapter: Capítulo actual (opcional)
            top_n: Número de entidades a devolver por tipo
            
        Returns:
            dict: Entidades más relevantes por tipo
        """
        # Ordenar personajes por número de menciones
        sorted_characters = sorted(
            [(name, profile) for name, profile in self.entity_profiles.items() 
             if profile.get("type") == "character"],
            key=lambda x: x[1]["mentions"],
            reverse=True
        )
        
        # Ordenar lugares por número de menciones
        sorted_locations = sorted(
            [(name, profile) for name, profile in self.entity_profiles.items() 
             if profile.get("type") == "location"],
            key=lambda x: x[1]["mentions"],
            reverse=True
        )
        
        # Si tenemos un capítulo actual, dar más relevancia a entidades recientes
        if current_chapter:
            # Priorizar personajes del capítulo actual o anterior
            chapter_characters = []
            if current_chapter in self.chapter_entities:
                chapter_characters = list(self.chapter_entities[current_chapter]["characters"])
                
            if current_chapter > 1 and current_chapter - 1 in self.chapter_entities:
                chapter_characters.extend(list(self.chapter_entities[current_chapter - 1]["characters"]))
                
            # Combinar con personajes más mencionados
            relevant_characters = []
            added_characters = set()
            
            # Primero añadir personajes del capítulo actual
            for character in chapter_characters:
                if character not in added_characters and len(relevant_characters) < top_n:
                    relevant_characters.append(character)
                    added_characters.add(character)
            
            # Luego completar con personajes más mencionados
            for character, _ in sorted_characters:
                if character not in added_characters and len(relevant_characters) < top_n:
                    relevant_characters.append(character)
                    added_characters.add(character)
        else:
            # Sin capítulo específico, usar solo frecuencia
            relevant_characters = [name for name, _ in sorted_characters[:top_n]]
        
        # Para lugares, similar pero más simple
        relevant_locations = [name for name, _ in sorted_locations[:top_n]]
        
        return {
            "characters": relevant_characters,
            "locations": relevant_locations
        }