"""
Archivo de Deprecación - Sistemas de Contexto Antiguos

Este archivo documenta los sistemas de gestión de contexto que han sido
deprecados y reemplazados por el sistema unificado.

ESTADO: NO ELIMINAR ESTOS ARCHIVOS TODAVÍA
Los archivos antiguos se mantienen para referencia pero no deben usarse en nuevo código.

SISTEMAS DEPRECADOS:
--------------------

1. adaptive_context.py
   - Estado: NO FUNCIONAL (marcado explícitamente en comentarios)
   - Motivo: Todos los métodos devuelven el input sin modificar
   - Uso actual: NINGUNO
   - Acción: Mantener como referencia histórica

2. memory_manager.py
   - Estado: SIMPLE SIN RESTRICCIONES
   - Motivo: Sistema básico que no aplica ninguna optimización
   - Uso actual: NINGUNO
   - Acción: Mantener como referencia histórica

3. intelligent_context.py
   - Estado: AVANZADO PERO NO UTILIZADO
   - Motivo: Características útiles (micro-resúmenes, condensación) nunca implementadas
   - Uso actual: NINGUNO
   - Características valiosas: Migradas a UnifiedContextManager
   - Acción: Mantener como referencia histórica

4. ProgressiveContextManager (en chapter_summary.py - DEPRECADO)
   - Estado: EN USO ACTIVO (writing.py)
   - Motivo: Sistema simple que funciona
   - Acción: REEMPLAZADO por UnifiedContextManager con alias de compatibilidad

NUEVO SISTEMA UNIFICADO:
-------------------------

unified_context.py - UnifiedContextManager
   - Combina lo mejor de todos los sistemas anteriores
   - API compatible con ProgressiveContextManager
   - Características avanzadas opcionales de IntelligentContextManager
   - Configurable por variables de entorno
   - Modos: simple, progressive, intelligent

MIGRACIÓN:
----------

El código existente NO necesita cambios:
   from chapter_summary import ProgressiveContextManager
   
Esto automáticamente usa UnifiedContextManager con alias de compatibilidad.

Para usar características avanzadas:
   from unified_context import UnifiedContextManager, ContextMode
   
   # Modo progressive (default, compatible con código antiguo)
   manager = UnifiedContextManager(framework, mode=ContextMode.PROGRESSIVE)
   
   # Modo intelligent (micro-resúmenes automáticos)
   manager = UnifiedContextManager(
       framework, 
       llm=llm,
       mode=ContextMode.INTELLIGENT,
       enable_micro_summaries=True
   )

VARIABLES DE ENTORNO:
---------------------

CONTEXT_MODE=simple|progressive|intelligent
CONTEXT_MAX_SIZE=2000
CONTEXT_ENABLE_MICRO_SUMMARIES=true|false
CONTEXT_MICRO_SUMMARY_INTERVAL=3

CRONOLOGÍA DE CAMBIOS:
----------------------

Fecha: 2025-10-19
- Creado unified_context.py con UnifiedContextManager
- Actualizado chapter_summary.py para usar sistema unificado
- Mantenidos archivos antiguos como referencia histórica
- Establecidos alias de compatibilidad

PRÓXIMOS PASOS:
---------------

1. Validar que todo funciona correctamente con el nuevo sistema
2. Ejecutar tests end-to-end de generación de libros
3. Considerar eliminación de archivos antiguos en futuras versiones
   (después de período de gracia de 3-6 meses)

NOTAS TÉCNICAS:
---------------

Decisiones de diseño del sistema unificado:

1. Compatibilidad retroactiva total
   - Alias ProgressiveContextManager = UnifiedContextManager
   - Misma API pública que el sistema anterior
   - Código existente funciona sin cambios

2. Características opcionales
   - Micro-resúmenes activables con enable_micro_summaries
   - Requiere LLM para características avanzadas
   - Fallback graceful si LLM no está disponible

3. Configuración flexible
   - Variables de entorno para configuración global
   - Parámetros de constructor para configuración específica
   - Modos de operación claramente definidos

4. Optimización de memoria
   - Límite configurable de tamaño de contexto
   - Resúmenes condensados cuando es necesario
   - Priorización inteligente de información reciente

REFERENCIAS:
------------

- Fase 2 del plan de refactorización
- Análisis en docs/FASE_2_ANALISIS.md (si existe)
- Tests en tests/test_unified_context.py
"""

# Este archivo no contiene código ejecutable, solo documentación
pass
