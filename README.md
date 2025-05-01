

<p align="center">
  <img src="images/sample.png" alt="Generador de Novelas de Fantasía con LLMs" width="800">
  <h1 align="center">📚 Generador de Novelas de Fantasía con LLMs</h1>
</p>

![GitHub last commit]([https://img.shields.io/github/last-commit/tu_usuario/tu_repositorio](https://github.com/kroryan/Generador-de-libros-IA-cli)?style=flat-square)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)

## ✨ Introducción

Este proyecto utiliza Large Language Models (LLMs) para generar novelas de fantasía completas con transparencia del proceso creativo.

> **⚠️ AVISO**: Proyecto en fase temprana de desarrollo. Pueden existir bugs y limitaciones.

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

| Proveedor       | Modelos Ejemplo         | Requisitos         |
|-----------------|-------------------------|--------------------|
| Ollama (Local)  | llama3, mistral         | Servidor Ollama    |
| OpenAIcompatible| GPT-4, GPT-3.5          | API Key            |
| Groq            | Mixtral-8x7b            | API Key            |
| Anthropic       | Claude-3                | API Key + librería |

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

---
