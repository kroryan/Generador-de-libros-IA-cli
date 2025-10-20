# Sistema de Few-Shot Learning

## Descripción General

El sistema de Few-Shot Learning ha sido implementado para mejorar significativamente la calidad de la generación de libros mediante el uso de ejemplos de alta calidad en los prompts. Este sistema transforma los prompts **zero-shot** originales en prompts **few-shot** que incluyen 1-2 ejemplos relevantes por género/estilo.

## Componentes del Sistema

### 1. ExampleLibrary (`src/example_library.py`)
- **Función**: Biblioteca central que almacena y gestiona ejemplos de secciones de alta calidad
- **Características**:
  - Almacenamiento persistente en JSON
  - Búsqueda por género, estilo y tipo de sección
  - Ejemplos por defecto para géneros populares
  - Sistema de fallback para géneros no encontrados

### 2. ExampleQualityEvaluator (`src/example_quality.py`)
- **Función**: Evalúa la calidad de las secciones generadas usando múltiples criterios
- **Criterios de evaluación** (score 0.0-1.0):
  - Longitud apropiada (200-500 palabras)
  - Riqueza léxica (diversidad de vocabulario)
  - Estructura narrativa (párrafos bien organizados)
  - Elementos narrativos (diálogos, descripciones sensoriales)
  - Ausencia de repeticiones

### 3. SectionQualityMonitor (`src/section_quality_monitor.py`)
- **Función**: Monitorea la generación en tiempo real y guarda automáticamente las mejores secciones
- **Características**:
  - Evaluación automática de cada sección generada
  - Guardado automático cuando se supera el umbral de calidad
  - Estadísticas de sesión en tiempo real
  - Posibilidad de guardado manual forzado

### 4. WriterChain Mejorado (`src/writing.py`)
- **Función**: Integra el sistema few-shot en la generación de contenido
- **Mejoras**:
  - Nuevo template few-shot con sección de ejemplos
  - Inyección automática de ejemplos relevantes
  - Compatibilidad con modo zero-shot para comparación
  - Integración con monitor de calidad

## Configuración

### Variables de Entorno

```bash
# Activar/desactivar few-shot learning
USE_FEW_SHOT_LEARNING=true

# Umbral de calidad para guardar ejemplos (0.0-1.0)
EXAMPLE_QUALITY_THRESHOLD=0.75

# Número máximo de ejemplos por prompt
MAX_EXAMPLES_PER_PROMPT=2

# Ruta de almacenamiento
EXAMPLES_STORAGE_PATH=./data/examples

# Auto-guardado automático
FEW_SHOT_AUTO_SAVE=true
```

### Configuración Centralizada

El sistema utiliza la configuración centralizada en `config/defaults.py`:

```python
from config.defaults import get_config
config = get_config()
few_shot_config = config.few_shot
```

## Flujo de Funcionamiento

### 1. Inicialización
```python
# Cargar configuración
config = get_config()

# Inicializar componentes
quality_monitor = SectionQualityMonitor(
    quality_threshold=config.few_shot.quality_threshold,
    auto_save=config.few_shot.auto_save_examples
)

writer_chain = WriterChain(use_few_shot=config.few_shot.enabled)
```

### 2. Generación de Secciones
```python
# Para cada sección:
1. WriterChain obtiene ejemplos relevantes de ExampleLibrary
2. Inyecta ejemplos en el prompt few-shot
3. Genera contenido usando el LLM
4. SectionQualityMonitor evalúa la calidad
5. Si score >= umbral, se guarda como ejemplo futuro
```

### 3. Estadísticas Finales
Al completar un libro, el sistema muestra:
- Secciones evaluadas
- Secciones guardadas como ejemplos
- Calidad promedio, máxima y mínima
- Tasa de guardado

## Géneros Soportados

### Ejemplos por Defecto Incluidos:
- **Fantasía Épica**: Ambientación medieval, magia, aventuras heroicas
- **Cyberpunk**: Tecnología avanzada, distopía, implantes cibernéticos
- **Ciencia Ficción**: Exploración espacial, dilemas éticos, especulación científica
- **Romance**: Relaciones emotivas, desarrollo de personajes, química
- **Misterio**: Suspense, investigación, revelaciones graduales

## Tipos de Sección
- **inicio**: Presentación, establecimiento de ambiente
- **medio**: Desarrollo, acción, conflictos
- **final**: Resolución, clímax, desenlace
- **acción**: Secuencias dinámicas, persecuciones
- **diálogo**: Conversaciones, desarrollo de relaciones

## Métricas de Calidad

### Criterios de Evaluación:
1. **Longitud** (15% del score): 200-500 palabras óptimo
2. **Riqueza Léxica** (25%): Diversidad de vocabulario
3. **Estructura** (20%): Párrafos bien organizados
4. **Elementos Narrativos** (15%): Diálogos, descripciones sensoriales
5. **Anti-repetición** (25%): Variedad en inicios de oraciones

### Rangos de Score:
- **0.90-1.00**: Excelente calidad
- **0.75-0.89**: Alta calidad (se guarda como ejemplo)
- **0.60-0.74**: Calidad aceptable
- **0.00-0.59**: Calidad baja

## Uso del Sistema

### Activación Automática
El sistema se activa automáticamente al generar libros si `USE_FEW_SHOT_LEARNING=true`.

### Monitoreo en Tiempo Real
Durante la generación, verás mensajes como:
```
📊 Calidad de sección: 0.82
✨ Sección de alta calidad guardada como ejemplo (score=0.82)
```

### Estadísticas Finales
```
📈 ESTADÍSTICAS DE FEW-SHOT LEARNING:
  Secciones evaluadas: 45
  Secciones guardadas como ejemplos: 12
  Calidad promedio: 0.73
  Calidad máxima: 0.92
  Calidad mínima: 0.52
  Tasa de guardado: 26.7%
```

## Archivos del Sistema

### Estructura de Directorios:
```
data/
└── examples/
    ├── default_examples.json    # Ejemplos por defecto
    └── user_examples.json       # Ejemplos generados por el usuario
```

### Archivos de Código:
```
src/
├── example_library.py           # Biblioteca de ejemplos
├── example_quality.py           # Evaluador de calidad
├── section_quality_monitor.py   # Monitor en tiempo real
└── writing.py                   # WriterChain mejorado
```

## Testing

Ejecutar tests del sistema:
```bash
python tests/test_few_shot_system.py
```

## Beneficios

### 1. Mejora de Calidad
- Los ejemplos guían al LLM hacia mejores patrones narrativos
- Consistencia en el tono y estilo del género
- Reducción de contenido genérico o repetitivo

### 2. Aprendizaje Continuo
- El sistema mejora automáticamente con cada libro generado
- Las mejores secciones se convierten en ejemplos futuros
- Adaptación al estilo preferido del usuario

### 3. Flexibilidad
- Soporte para múltiples géneros y estilos
- Configuración granular mediante variables de entorno
- Posibilidad de desactivar para comparar con zero-shot

### 4. Transparencia
- Métricas de calidad en tiempo real
- Estadísticas detalladas al final
- Posibilidad de revisar ejemplos almacenados

## Troubleshooting

### Problema: No se guardan ejemplos
- Verificar que `FEW_SHOT_AUTO_SAVE=true`
- Revisar que el umbral `EXAMPLE_QUALITY_THRESHOLD` no sea demasiado alto
- Comprobar permisos de escritura en `EXAMPLES_STORAGE_PATH`

### Problema: Calidad baja constante
- Revisar la configuración del LLM (temperatura, parámetros)
- Verificar que hay ejemplos apropiados para el género
- Considerar ajustar el umbral de calidad

### Problema: Errores de carga de ejemplos
- Verificar que el directorio `data/examples` existe
- Comprobar que los archivos JSON no están corruptos
- Revisar logs para errores específicos

## Roadmap Futuro

### Mejoras Planificadas:
1. **Análisis Semántico**: Mejorar la búsqueda de ejemplos por similitud semántica
2. **Templates Dinámicos**: Adaptar el formato de ejemplos según el contexto
3. **Métricas Avanzadas**: Incluir análisis de coherencia narrativa
4. **Interfaz Web**: Panel para gestionar ejemplos manualmente
5. **Exportación**: Capacidad de exportar/importar bibliotecas de ejemplos