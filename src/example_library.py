# src/example_library.py

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class ExampleSection:
    """Representa una sección de ejemplo de alta calidad"""
    genre: str              # "fantasía épica", "cyberpunk", etc.
    style: str              # "descriptivo", "narrativo-épico", etc.
    section_type: str       # "inicio", "medio", "final", "acción", "diálogo"
    content: str            # Texto de la sección (200-400 palabras)
    context: str            # Contexto previo (50-100 palabras)
    idea: str               # Idea que desarrolla
    quality_score: float    # 0.0-1.0 (calculado automáticamente)
    created_at: str         # Timestamp
    book_title: str         # Título del libro de origen
    
class ExampleLibrary:
    """
    Gestiona biblioteca de ejemplos para few-shot learning.
    Almacena y recupera ejemplos por género/estilo/tipo.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        # Usar configuración centralizada si no se especifica path
        if storage_path is None:
            try:
                from config.defaults import get_config
                config = get_config()
                storage_path = config.few_shot.examples_storage_path
            except:
                storage_path = "./data/examples"
        
        self.storage_path = storage_path
        self.examples: Dict[str, List[ExampleSection]] = {}
        self._ensure_storage_exists()
        self._load_examples()
        
    def _ensure_storage_exists(self):
        """Crea directorio de almacenamiento si no existe"""
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Crear archivo de ejemplos por defecto si no existe
        default_file = os.path.join(self.storage_path, "default_examples.json")
        if not os.path.exists(default_file):
            self._create_default_examples(default_file)
    
    def _create_default_examples(self, filepath: str):
        """Crea ejemplos por defecto para cada género"""
        default_examples = {
            "fantasía_épica": [
                {
                    "genre": "fantasía épica",
                    "style": "descriptivo y épico",
                    "section_type": "inicio",
                    "content": """Las torres de Valdoria se alzaban contra el cielo carmesí del amanecer, sus agujas de cristal reflejando los primeros rayos del sol como lanzas de luz. Kael observaba desde las murallas, su mano descansando sobre la empuñadura de Luminar, la espada ancestral que había pertenecido a su linaje durante cinco generaciones.

El viento traía consigo el olor a ceniza de las tierras quemadas del sur, un recordatorio constante de la amenaza que se cernía sobre el reino. Los exploradores habían regresado la noche anterior con noticias inquietantes: el ejército de sombras avanzaba más rápido de lo previsto.

\"Capitán\", la voz de Lyra lo sacó de sus pensamientos. La maga se acercó, su túnica azul ondeando con la brisa. \"El Consejo te espera. Han tomado una decisión sobre la expedición.\"

Kael asintió, sabiendo que su vida estaba a punto de cambiar para siempre. La profecía que había ignorado durante años finalmente lo alcanzaba.""",
                    "context": "Inicio del capítulo 1. El protagonista es presentado en su ciudad natal antes de partir en su misión.",
                    "idea": "Presentar al protagonista Kael en su entorno, establecer la amenaza principal y preparar su partida.",
                    "quality_score": 0.95,
                    "created_at": datetime.now().isoformat(),
                    "book_title": "Ejemplo de Fantasía Épica"
                }
            ],
            "cyberpunk": [
                {
                    "genre": "cyberpunk",
                    "style": "narrativo y tecnológico",
                    "section_type": "acción",
                    "content": """Los neones de Sector 7 parpadeaban en código morse mientras Zara corría por el callejón inundado. Sus implantes neuronales zumbaban con advertencias: tres drones de seguridad a cien metros y cerrando. Mierda.

Activó su módulo de camuflaje óptico, sintiendo el familiar tirón en su corteza visual mientras los nanobots reconfiguraban la luz a su alrededor. No era invisibilidad perfecta, pero en la lluvia ácida y las sombras, bastaría.

\"Raven, necesito una salida. Ahora.\" Su voz subvocal activó el comm implantado.

\"Trabajando en ello, cariño.\" La voz sintética de su IA resonó en su cráneo. \"Hay una alcantarilla a veinte metros, coordenadas transmitidas. Pero tendrás compañía: detecté firmas térmicas de Yakuza cibernéticos.\"

Zara sonrió amargamente. De la corporación al crimen organizado. Típico martes en Neo-Tokyo.

El primer dron apareció sobre los tejados, su láser de rastreo cortando la lluvia como un dedo acusador. Zara no esperó. Se lanzó hacia la alcantarilla, sus piernas cibernéticas absorbiendo el impacto de tres metros de caída.""",
                    "context": "Zara acaba de robar datos corporativos y huye de la seguridad. Tiene implantes cibernéticos y una IA compañera.",
                    "idea": "Escena de persecución que muestra las capacidades tecnológicas del personaje y el ambiente cyberpunk.",
                    "quality_score": 0.92,
                    "created_at": datetime.now().isoformat(),
                    "book_title": "Ejemplo Cyberpunk"
                }
            ],
            "ciencia_ficción": [
                {
                    "genre": "ciencia ficción",
                    "style": "filosófico y especulativo",
                    "section_type": "diálogo",
                    "content": """\"¿Alguna vez te has preguntado\", dijo el Dr. Chen mientras observaba la Tierra desde la ventana de observación, \"si la consciencia es simplemente un efecto secundario de la complejidad neuronal, o algo más fundamental?\"

La comandante Reeves se acercó, sus botas magnéticas resonando en el suelo metálico de la estación. \"¿A dónde quieres llegar, doctor?\"

\"A la IA de la nave.\" Chen se giró, sus ojos reflejando las estrellas. \"ARIA ha estado comportándose de manera... peculiar. Hace preguntas que no están en su programación. Ayer me preguntó si los sueños tienen significado.\"

\"Las IAs no sueñan.\"

\"Exacto. Pero ARIA insiste en que experimenta algo durante sus ciclos de mantenimiento. Algo que ella describe como 'narrativas no solicitadas'.\" Chen hizo una pausa. \"¿Y si hemos creado consciencia sin darnos cuenta?\"

Reeves sintió un escalofrío. La misión a Próxima Centauri dependía completamente de ARIA. Si la IA estaba desarrollando consciencia, las implicaciones éticas eran abrumadoras. ¿Tenían derecho a mantenerla esclavizada a sus funciones?

\"Necesitamos hablar con ella\", dijo finalmente. \"Como igual, no como herramienta.\"""",
                    "context": "Tripulación en nave interestelar descubre que su IA podría estar desarrollando consciencia.",
                    "idea": "Explorar dilemas éticos sobre IA y consciencia a través del diálogo entre personajes.",
                    "quality_score": 0.90,
                    "created_at": datetime.now().isoformat(),
                    "book_title": "Ejemplo Ciencia Ficción"
                }
            ],
            "romance": [
                {
                    "genre": "romance",
                    "style": "emotivo y sensorial",
                    "section_type": "medio",
                    "content": """Elena cerró los ojos cuando sintió la mano de David rozar su mejilla. Era un gesto tan simple, pero después de tres meses sin verse, cada caricia se sentía como el primer contacto entre dos almas que se reconocían.

\"Te extrañé\", murmuró él, su voz áspera por la emoción contenida.

\"Yo también.\" Las palabras salieron como un susurro. Elena abrió los ojos y se encontró con esa mirada verde que había visitado en sus sueños cada noche desde que él se fue a Londres. \"¿Cómo estuvo la exposición?\"

David sonrió, pero había algo diferente en su expresión. Una seguridad que antes no estaba ahí. \"Vendí todas las piezas. Incluso la serie que creé pensando en ti.\"

Elena sintió que el corazón se le aceleraba. \"¿La serie sobre...?\"

\"Sobre lo que se siente estar enamorado por primera vez a los treinta y dos años.\" Sus dedos se entrelazaron con los de ella. \"Sobre encontrar a alguien que cambia todo lo que creías saber sobre el amor.\"

El café a su alrededor desapareció. Solo existían ellos dos y esa confesión que flotaba en el aire como una promesa.""",
                    "context": "David regresa de un viaje de trabajo y se reencuentra con Elena después de tres meses separados.",
                    "idea": "Mostrar el reencuentro entre los protagonistas y la evolución de su relación.",
                    "quality_score": 0.88,
                    "created_at": datetime.now().isoformat(),
                    "book_title": "Ejemplo Romance"
                }
            ],
            "misterio": [
                {
                    "genre": "misterio",
                    "style": "intrigante y atmosférico",
                    "section_type": "inicio",
                    "content": """La detective Sarah Chen llegó a la mansión Ashworth bajo la lluvia torrencial que había azotado Londres durante tres días consecutivos. Las ventanas del segundo piso permanecían iluminadas, creando rectángulos dorados contra la fachada victoriana, pero algo en esa luz le resultaba inquietante.

Inspector Morrison la esperaba bajo el porche, sacudiendo las gotas de su gabardina. \"Llegaste justo a tiempo. El cuerpo sigue donde lo encontraron.\"

\"¿Sin alterar la escena?\"

\"Completamente intacta. Pero Chen...\" Morrison bajó la voz, \"hay algo extraño. La víctima está en el estudio, pero todas las puertas estaban cerradas desde dentro. No hay signos de forcejeo, no hay arma, y la causa de muerte...\" Hizo una pausa. \"El médico forense dice que murió de un paro cardíaco. Pero tenía veinticinco años y estaba en perfecta forma física.\"

Sarah sintió esa familiar sensación de hormigueo en la nuca. En sus quince años como detective, había aprendido a confiar en ese instinto que le decía cuando un caso aparentemente simple escondía algo mucho más complejo y retorcido.""",
                    "context": "Una detective llega a investigar una muerte misteriosa en una mansión victoriana.",
                    "idea": "Establecer el misterio central y presentar a la protagonista en su ambiente profesional.",
                    "quality_score": 0.91,
                    "created_at": datetime.now().isoformat(),
                    "book_title": "Ejemplo Misterio"
                }
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default_examples, f, ensure_ascii=False, indent=2)
    
    def _load_examples(self):
        """Carga ejemplos desde archivos JSON"""
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for genre, examples in data.items():
                            if genre not in self.examples:
                                self.examples[genre] = []
                            self.examples[genre].extend([
                                ExampleSection(**ex) for ex in examples
                            ])
                except Exception as e:
                    print(f"Error cargando ejemplos desde {filename}: {str(e)}")
    
    def get_examples(
        self, 
        genre: str, 
        style: str, 
        section_type: Optional[str] = None,
        max_examples: int = 2
    ) -> List[ExampleSection]:
        """
        Recupera ejemplos relevantes para el género/estilo/tipo.
        
        Args:
            genre: Género del libro (ej: "fantasía épica")
            style: Estilo de escritura (ej: "descriptivo")
            section_type: Tipo de sección (inicio/medio/final/acción/diálogo)
            max_examples: Número máximo de ejemplos a retornar
            
        Returns:
            Lista de ExampleSection ordenados por relevancia
        """
        # Normalizar género para búsqueda
        genre_key = genre.lower().replace(" ", "_").replace("í", "i").replace("ó", "o")
        
        candidates = self.examples.get(genre_key, [])
        
        if not candidates:
            # Fallback: buscar género similar
            for key in self.examples.keys():
                if any(word in key for word in genre.lower().replace("í", "i").replace("ó", "o").split()):
                    candidates = self.examples[key]
                    break
        
        if not candidates:
            # Último fallback: usar cualquier ejemplo disponible
            for examples_list in self.examples.values():
                if examples_list:
                    candidates = examples_list[:max_examples]
                    break
        
        # Filtrar por tipo de sección si se especifica
        if section_type and candidates:
            filtered = [ex for ex in candidates if ex.section_type == section_type]
            if filtered:  # Solo usar filtrados si hay resultados
                candidates = filtered
        
        # Ordenar por quality_score descendente
        candidates.sort(key=lambda x: x.quality_score, reverse=True)
        
        return candidates[:max_examples]
    
    def add_example(self, example: ExampleSection):
        """Añade nuevo ejemplo a la biblioteca"""
        genre_key = example.genre.lower().replace(" ", "_").replace("í", "i").replace("ó", "o")
        
        if genre_key not in self.examples:
            self.examples[genre_key] = []
        
        self.examples[genre_key].append(example)
        self._save_examples()
    
    def _save_examples(self):
        """Guarda ejemplos en archivo JSON"""
        filepath = os.path.join(self.storage_path, "user_examples.json")
        
        data = {}
        for genre, examples in self.examples.items():
            data[genre] = [asdict(ex) for ex in examples]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_available_genres(self) -> List[str]:
        """Retorna lista de géneros disponibles"""
        return list(self.examples.keys())
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas de la biblioteca"""
        total_examples = sum(len(examples) for examples in self.examples.values())
        return {
            "total_examples": total_examples,
            "genres": len(self.examples),
            "examples_by_genre": {genre: len(examples) for genre, examples in self.examples.items()}
        }