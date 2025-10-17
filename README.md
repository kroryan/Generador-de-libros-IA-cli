<p align="center">
  <img src="images/sample.png" alt="Generador de Novelas de Fantasía con LLMs" width="800">
  <h1 align="center">📚 Generador de Novelas de Fantasía con LLMs</h1>
</p>

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)

## ✨ Introducción

Este proyecto utiliza Large Language Models (LLMs) para generar novelas de fantasía completas con transparencia del proceso creativo.

> **⚠️ AVISO**: Proyecto en fase temprana de desarrollo. Pueden existir bugs y limitaciones.

---

## 🆕 Actualizaciones recientes (Octubre 2025)

- 🌟 **Streaming en tiempo real mejorado**: Ahora el texto se transmite directamente sin fragmentación ni modificaciones.
- 🎨 **Separación visual de pensamientos y respuestas**: Los pensamientos del modelo se muestran en magenta y las respuestas en cian.
- 🛠️ **Lógica simplificada**: Eliminación de procesamiento innecesario para garantizar una experiencia más fluida.
- 🚀 **Optimización de la interfaz web**: Mejoras en el diseño para una experiencia de usuario más intuitiva.


## 🆕 Actualizaciones recientes (Mayo 2025)

- 💾 **Sistema de puntos de guardado (savepoints)**: Implementación robusta que evita pérdidas de contexto durante la generación de textos largos
- 🧠 **Gestión de contexto mejorada**: Optimización automática del contexto para mantener coherencia en historias extensas
- 💻 **Modo comando mejorado**: Ahora puedes seleccionar modelos directamente con `--model` y listar los disponibles con `--list-models`
- 📝 **Sistema de resúmenes entre capítulos** para mejorar la coherencia narrativa
- 🔄 **Flujo narrativo mejorado** con contexto enriquecido para continuidad entre secciones
- 📊 **Formateo profesional de documentos** con metadatos, márgenes y estilos optimizados
- 📑 **Mejor organización textual** con procesamiento semántico de párrafos
- 🧠 **Sistema de detección de modelos multi-API**: Detecta automáticamente modelos disponibles en Ollama, OpenAI, DeepSeek, Groq y proveedores personalizados
- 🔧 **Configuración flexible mediante archivo .env**: Personaliza completamente todos los proveedores y modelos sin tocar el código
- 🎨 **Visualización mejorada de pensamientos**: Los pensamientos del modelo ahora se muestran correctamente en amarillo y cambian a azul al terminar
- 🖥️ **Interfaz web cyberpunk** completamente rediseñada

---

## 🚀 Características Principales

- 🧠 Soporte multi-API (Ollama, OpenAI, DeepSeek, Groq, Anthropic)
- 📖 Generación completa de estructuras narrativas y personajes
- 💾 Sistema de puntos de guardado para evitar pérdida de contexto
- 🔄 Recuperación automática ante fallos del modelo
- 📝 Sistema de resúmenes para coherencia narrativa
- 🎨 Interfaz cyberpunk con visualización en tiempo real
- 📤 Exportación a PDF/DOCX con formato profesional
- ⚙️ Configuración flexible mediante archivo `.env`
- 🔍 Transparencia del proceso con pensamientos del modelo

---

## 🖥️ Demo Interactiva

![Interfaz del Generador](images/sample.png)

---

## ⚙️ Configuración Rápida

```bash
git clone https://github.com/kroryan/Generador-de-libros-IA-cli.git
cd Generador-de-libros-IA-cli
pip install -r requirements.txt

# Modo web (interfaz gráfica)
python src/app.py --web  

# Modo consola (recomendado para mejor rendimiento)
python src/app.py
```

Para el modo web, visita `http://localhost:5000` en tu navegador.

---

## 💻 Uso en Línea de Comandos

El programa ofrece una interfaz de línea de comandos potente con selección explícita de modelos:

### 📋 Opciones disponibles

- **Listar modelos disponibles**:
  ```bash
  python src/app.py --list-models
  ```

- **Generar libro con un modelo específico**:
  ```bash
  python src/app.py --model groq:llama3-8b-8192
  ```

- **Iniciar interfaz web con un modelo preseleccionado**:
  ```bash
  python src/app.py --web 

  ```bash
  python src/app.py --web 
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

## 🧠 Sistema de Puntos de Guardado (Savepoints)

El generador ahora incluye un robusto sistema de puntos de guardado que:

- 💾 **Crea resúmenes periódicos** durante la generación del contenido 
- 🔄 **Mantiene la coherencia narrativa** incluso en textos muy extensos
- 🛡️ **Previene la pérdida de contexto** que suele ocurrir en modelos LLM
- 🚀 **Permite generar libros completos** sin interrupciones por límites de contexto
- 🔍 **Optimiza automáticamente el contexto** para evitar sobrecarga del modelo

Este sistema funciona creando "savepoints" estratégicos durante la escritura, especialmente después de secciones largas, permitiendo al modelo "recordar" efectivamente lo que sucedió antes sin tener que mantener todo el texto en el contexto.

---

## 🛠️ Guía de Prompts

### 🔍 Ubicación de los Prompts

| Archivo               | Clase                 | Propósito |
|-----------------------|-----------------------|-----------|
| `structure.py`        | `TitleChain`          | Título del libro |
| `structure.py`        | `FrameworkChain`      | Marco narrativo |
| `structure.py`        | `ChaptersChain`       | Estructura de capítulos |
| `ideas.py`            | `IdeasChain`          | Desarrollo de ideas |
| `writing.py`          | `WriterChain`         | Escritura narrativa |
| `chapter_summary.py`  | `ChapterSummaryChain` | Resúmenes de capítulos |

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

| Proveedor       | Modelos Ejemplo         | Requisitos         |
|-----------------|-------------------------|--------------------|
| Ollama (Local)  | llama3, mistral, phi3   | Servidor Ollama    |
| OpenAI          | GPT-4, GPT-3.5          | API Key            |
| Groq            | Llama3, Mixtral-8x7b    | API Key            |
| DeepSeek        | DeepSeek-Chat           | API Key            |
| Anthropic       | Claude-3                | API Key + librería |
| Custom          | Cualquier API OpenAI compatible | Config. en .env |

---

## ⚙️ Configuración .env Completa

```env
# Configuración de modelo predeterminado
MODEL_TYPE=ollama
SELECTED_MODEL=ollama:llama3

# Ollama (local)
OLLAMA_MODEL=llama3
OLLAMA_API_BASE=http://localhost:11434

# OpenAI
OPENAI_API_KEY=tu_clave_aqui
OPENAI_MODEL=gpt-4
OPENAI_API_BASE=  # Opcional, para APIs compatibles

# Groq
GROQ_API_KEY=tu_clave_aqui
GROQ_MODEL=llama3-8b-8192
GROQ_API_BASE=https://api.groq.com/openai/v1

# DeepSeek
DEEPSEEK_API_KEY=tu_clave_aqui
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_BASE=https://api.deepseek.com

# Anthropic
ANTHROPIC_API_KEY=tu_clave_aqui
ANTHROPIC_MODEL=claude-3-opus

# Proveedores personalizados (compatible con OpenAI)
CUSTOM_API_KEY=tu_clave_aqui
CUSTOM_API_BASE=https://tu-api-personalizada.com/v1
CUSTOM_MODEL=tu-modelo-personalizado
```

---

## 🚧 Proceso de Generación

1. **Estructura (20%)**: Título y marco narrativo
2. **Ideas (40%)**: Desarrollo de capítulos y tramas
3. **Escritura (85%)**: Narrativa detallada con gestión de savepoints
4. **Publicación (100%)**: Exportación a PDF/DOCX con formato profesional

---

## 🚧 Desarrollo Futuro

- ✅ Sistema de puntos de guardado
- ✅ Soporte para parámetros avanzados
- ✅ Integración con más proveedores
- ⏳ Generación de imágenes para ilustrar escenas
- ⏳ Ajustes de personalidad avanzados
- ⏳ Implementación de memoria persistente

---

## 📱 Contacto

Si por alguna razón quieres contactarme, puedes hacerlo entrando a este [Discord](https://discord.gg/TTmrXaeXM8) - mi nombre en el servidor es Allen.
