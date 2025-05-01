<p align="center">
  <img src="images/sample.png" alt="Generador de Novelas de Fantasía con LLMs" width="800">
  <h1 align="center">📚 Generador de Novelas de Fantasía con LLMs</h1>
</p>

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)

## ✨ Introducción

Este proyecto utiliza Large Language Models (LLMs) para generar novelas de fantasía completas con transparencia del proceso creativo.

> **⚠️ AVISO**: Proyecto en fase temprana de desarrollo. Pueden existir bugs y limitaciones.

> **⚠️ AVISO SOBRE CONTEXTO**: Se recomienda utilizar modelos con capacidad de 128.000 tokens de contexto hasta que los problemas actuales de manejo de contexto sean solucionados. Modelos con menor capacidad pueden experimentar pérdida de coherencia narrativa entre capítulos.

---

## 🆕 Actualizaciones recientes (Mayo 2025)

- 💻 **Modo comando mejorado**: Ahora puedes seleccionar modelos directamente con `--model` y listar los disponibles con `--list-models`
- 📝 **Nuevo sistema de resúmenes entre capítulos** para mejorar la coherencia narrativa
- 🔄 **Flujo narrativo mejorado** con contexto enriquecido para continuidad entre secciones
- 📊 **Formateo profesional de documentos** con metadatos, márgenes y estilos optimizados
- 📑 **Mejor organización textual** con procesamiento semántico de párrafos
- 🧠 **Sistema de detección de modelos multi-API**: Detecta automáticamente modelos disponibles en Ollama, OpenAI, DeepSeek, Groq y proveedores personalizados
- 🔧 **Configuración flexible mediante archivo .env**: Personaliza completamente todos los proveedores y modelos sin tocar el código
- 🎨 **Visualización mejorada de pensamientos**: Los pensamientos del modelo ahora se muestran correctamente en amarillo y cambian a azul al terminar
- 🖥️ Interfaz web cyberpunk completamente rediseñada
- 📝 Visualización en tiempo real del proceso de generación, separando pensamientos y resultados finales
- 📊 Barra de progreso visual para seguimiento detallado
- 📋 Organización clara del contenido generado
- 🎨 Efectos visuales mejorados para una experiencia más inmersiva
- 📲 Diseño responsivo adaptado a diferentes dispositivos

---

## 🚀 Características Principales

- 🧠 Soporte multi-API (Ollama, OpenAI, DeepSeek, Groq, Anthropic)
- 📖 Generación completa de estructuras narrativas y personajes
- 🎨 Interfaz cyberpunk con visualización en tiempo real
- 📝 Sistema de resúmenes para coherencia narrativa
- 📤 Exportación a PDF/DOCX con formato profesional
- ⚙️ Configuración flexible mediante archivo `.env`
- 🔍 Transparencia del proceso con pensamientos del modelo

---

## 🖥️ Demo Interactiva

![Interfaz del Generador](images/sample.png)

---

## ⚙️ Configuración Rápida

git clone [https://github.com/kroryan/Generador-de-libros-IA-cli](https://github.com/kroryan/Generador-de-libros-IA-cli).git
cd Generador-de-libros-IA-cli
pip install -r requirements.txt
python src/app.py --web  #se iniciara el modo web, este modo no es recomendado ya que la web aun no esta muy pulida tambien puedes usar 
Visita `http://localhost:5000`

o tambien para la consola:

 python src/app.py 

---

## 💻 Uso en Línea de Comandos

El programa ahora ofrece una interfaz de línea de comandos mejorada con selección explícita de modelos:

### 📋 Opciones disponibles

- **Listar modelos disponibles**:
  ```bash
  python app.py --list-models
  ```

- **Generar libro con un modelo específico**:
  ```bash
  python app.py --model groq:llama3-8b-8192
  ```

- **Iniciar interfaz web con un modelo preseleccionado**:
  ```bash
  python app.py --web --model openai:gpt-4
  ```

  ```bash
  python app.py --web --model groq:qwen-qwq-32b
  ```

### 🔧 Interacción con el archivo .env

- Si no especificas un modelo con `--model`, el programa usará el valor de `MODEL_TYPE` del archivo `.env`
- Puedes configurar tu archivo `.env` para establecer un modelo predeterminado:
  ```
  MODEL_TYPE=groq
  GROQ_MODEL=llama3-8b-8192
  GROQ_API_KEY=tu_clave_api
  ```

- La prioridad de selección de modelos es:
  1. Modelo especificado con `--model`
  2. Valor de `MODEL_TYPE` en `.env`
  3. Fallback a otros proveedores configurados

---

## 🛠️ Guía de Prompts

### 🔍 Ubicación de los Prompts

| Archivo               | Clase                 | Propósito |
|-----------------------|-----------------------|-----------|
| `structure.py`        | `TitleChain`          | Título del libro |
| `structure.py`        | `FrameworkChain`      | Marco narrativo |
| `ideas.py`            | `IdeasChain`          | Desarrollo de ideas |
| `writing.py`          | `WriterChain`         | Escritura narrativa |

### 📝 Personalización de Prompts

1. Edite el archivo correspondiente
2. Busque `PROMPT_TEMPLATE`
3. Modifique manteniendo los marcadores `{variables}`

**Ejemplo para estilo poético** (`writing.py`):
```python
PROMPT_TEMPLATE = """
Eres un poeta y escritor de fantasía en español.
Utiliza lenguaje metafórico y descripciones vívidas.
...
"""
```

---

## 🌐 Proveedores Compatibles

| Proveedor       | Modelos Ejemplo         | Requisitos         | Contexto Recomendado |
|-----------------|-------------------------|--------------------|----------------------|
| Ollama (Local)  | llama3, mistral         | Servidor Ollama    | 8K-32K tokens        |
| OpenAIcompatible| GPT-4, GPT-3.5          | API Key            | 8K-128K tokens       |
| Groq            | Mixtral-8x7b            | API Key            | 32K tokens           |
| Anthropic       | Claude-3                | API Key + librería | 100K+ tokens         |

> **💡 Nota sobre contexto**: Para una generación óptima, se recomienda usar modelos con al menos 128K tokens de contexto. Modelos con menor capacidad pueden requerir configuraciones adicionales o experimentar limitaciones en la coherencia narrativa.

---

## ⚙️ Configuración .env

```env
# Ollama
OLLAMA_MODEL=llama3
OLLAMA_API_BASE=http://localhost:11434

# OpenAI
OPENAI_API_KEY=tu_clave
OPENAI_MODEL=gpt-4
```

---

## 🚧 Proceso de Generación

1. **Estructura (20%)**: Título y marco narrativo
2. **Ideas (40%)**: Desarrollo de capítulos
3. **Escritura (85%)**: Narrativa detallada
4. **Publicación (100%)**: Exportación a PDF/DOCX

---

## 🚧 Desarrollo Futuro

- ✅ Soporte para parámetros avanzados
- ✅ Integración con más proveedores
- ✅ Generación de imágenes
- ⏳ Optimización avanzada del manejo de contexto para modelos con ventanas más pequeñas
- ⏳ Implementación de memoria persistente para mejorar la coherencia en libros largos

---

Si por alguna razon quereis contactarme podeis hacerlo entrando a este discord, mi nombre es allen en el discord; https://discord.gg/TTmrXaeXM8