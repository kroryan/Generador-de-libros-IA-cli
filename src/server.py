import sys
import os
import re
import requests

# Add the parent directory to the Python path to resolve the 'src' module issue
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_socketio import SocketIO
import threading
import time
# Corregir importaciones para usar las rutas relativas correctas
from structure import get_structure
from ideas import get_ideas
from writing import write_book
from publishing import DocWriter
from chapter_summary import ChapterSummaryChain
from utils import update_model_name, get_available_models

# Configurar correctamente Flask para servir archivos estáticos desde templates
app = Flask(__name__, 
            template_folder=os.path.join(parent_dir, 'templates'),
            static_folder=os.path.join(parent_dir, 'templates'))

# FASE 4: Usar configuración centralizada para SocketIO
from config.defaults import get_config

config = get_config()
socketio_config = config.socketio

# Utilizar el servidor integrado de werkzeug para evitar problemas de monkey patching
socketio = SocketIO(
    app, 
    cors_allowed_origins=socketio_config.cors_allowed_origins, 
    async_mode=socketio_config.async_mode.value,
    ping_interval=socketio_config.ping_interval,
    ping_timeout=socketio_config.ping_timeout  # CRÍTICO: Cambiado de 72h (259200) a 1h (3600)
)

# FASE 4: Agregar observers al state_manager (necesita estar después de socketio)
# Importar después de socketio para evitar importación circular
from generation_state import SocketIOObserver, LoggingObserver

# Registrar observers
def _init_state_observers():
    """Inicializa observers del estado. Debe llamarse después de definir socketio."""
    from generation_state import state_manager
    state_manager.add_observer(SocketIOObserver(socketio))
    state_manager.add_observer(LoggingObserver())

_init_state_observers()

# Función para limpiar códigos de escape ANSI
def clean_ansi_codes(text):
    """
    Limpia códigos de escape ANSI del texto.
    
    NOTA: Esta función ahora usa el sistema unificado de limpieza de texto.
    Mantenida por compatibilidad con código existente.
    """
    from text_cleaning import clean_ansi_codes as _clean_ansi_codes
    return _clean_ansi_codes(text)

# Clase para capturar la salida y enviarla a través de websockets
class OutputCapture:
    """
    Captura output y lo envía vía websockets.
    
    NOTA: Ahora usa el sistema unificado de limpieza de streaming.
    """
    def __init__(self):
        from streaming_cleaner import OutputCapture as _OutputCapture
        self._capture = _OutputCapture(socketio_emit_func=socketio.emit)
        
    def write(self, data):
        self._capture.write(data)
    
    def flush(self):
        self._capture.flush()
    
    # Propiedades para compatibilidad
    @property
    def in_think_block(self):
        return self._capture.in_think_block
    
    @property
    def buffer(self):
        return self._capture.buffer
    
    @property
    def think_buffer(self):
        return self._capture.think_buffer

# Función para obtener los modelos disponibles en todas las APIs configuradas
def get_available_models():
    all_models = []
    
    # 1. Detectar modelos de Ollama (siempre escaneados automáticamente)
    try:
        ollama_api_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
        response = requests.get(f"{ollama_api_base}/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            # Convertir los modelos de Ollama en formato estructurado
            for model in models:
                all_models.append({
                    "provider": "ollama",
                    "name": model['name'],
                    "display_name": f"Ollama: {model['name']}",
                    "value": model['name']  # Ollama no necesita prefijo
                })
    except Exception as e:
        print(f"Error al obtener modelos de Ollama: {e}")
    
    # 2. Obtener modelos de Groq (desde las variables de entorno)
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    if groq_api_key and groq_api_key.strip():
        groq_models = os.environ.get("GROQ_AVAILABLE_MODELS", "qwen-qwq-32b,llama3-8b-8192,mixtral-8x7b-32768").split(",")
        for model in groq_models:
            model = model.strip()
            if model:
                all_models.append({
                    "provider": "groq",
                    "name": model,
                    "display_name": f"Groq: {model}",
                    "value": f"groq:{model}"
                })
    
    # 3. Obtener modelos de OpenAI (desde las variables de entorno)
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_api_key and openai_api_key.strip():
        # Si no hay modelos definidos explícitamente, usar una lista predeterminada
        openai_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]
        
        # Si hay una API base personalizada y no es Groq, intentar obtener la lista real
        openai_api_base = os.environ.get("OPENAI_API_BASE", "")
        if openai_api_base and "groq" not in openai_api_base.lower():
            try:
                url = f"{openai_api_base}/models"
                headers = {"Authorization": f"Bearer {openai_api_key}"}
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    models_data = response.json().get('data', [])
                    api_models = [model['id'] for model in models_data if 'id' in model]
                    if api_models:
                        openai_models = api_models
            except Exception as e:
                print(f"Error al obtener lista de modelos de OpenAI: {e}")
        
        # Agregar modelos de OpenAI a la lista
        for model in openai_models:
            model = model.strip()
            if model:
                all_models.append({
                    "provider": "openai",
                    "name": model,
                    "display_name": f"OpenAI: {model}",
                    "value": f"openai:{model}"
                })
    
    # 4. Obtener modelos de DeepSeek (desde las variables de entorno)
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_api_key and deepseek_api_key.strip():
        deepseek_models = os.environ.get("DEEPSEEK_AVAILABLE_MODELS", "deepseek-chat,deepseek-reasoner").split(",")
        if not deepseek_models or not deepseek_models[0]:
            deepseek_models = ["deepseek-chat", "deepseek-reasoner"]
            
        for model in deepseek_models:
            model = model.strip()
            if model:
                all_models.append({
                    "provider": "deepseek",
                    "name": model,
                    "display_name": f"DeepSeek: {model}",
                    "value": f"deepseek:{model}"
                })
    
    # 5. Obtener modelos de Anthropic (desde las variables de entorno)
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_api_key and anthropic_api_key.strip():
        anthropic_models = os.environ.get("ANTHROPIC_AVAILABLE_MODELS", "claude-3-opus,claude-3-sonnet,claude-3-haiku").split(",")
        for model in anthropic_models:
            model = model.strip()
            if model:
                all_models.append({
                    "provider": "anthropic",
                    "name": model,
                    "display_name": f"Anthropic: {model}",
                    "value": f"anthropic:{model}"
                })
    
    # 6. Buscar proveedores personalizados adicionales
    for key in os.environ:
        if key.endswith("_API_KEY") and key not in ["OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY"]:
            provider = key.replace("_API_KEY", "").lower()
            api_key = os.environ.get(key, "")
            
            if api_key and api_key.strip():
                # Obtener los modelos disponibles para este proveedor
                models_env_var = f"{provider.upper()}_AVAILABLE_MODELS"
                default_model_env_var = f"{provider.upper()}_MODEL"
                
                models = os.environ.get(models_env_var, "").split(",")
                default_model = os.environ.get(default_model_env_var, "")
                
                # Si no hay modelos definidos pero hay un modelo predeterminado, usar ese
                if (not models or not models[0]) and default_model:
                    models = [default_model]
                
                # Agregar modelos del proveedor personalizado
                for model in models:
                    model = model.strip()
                    if model:
                        all_models.append({
                            "provider": provider,
                            "name": model,
                            "display_name": f"{provider.capitalize()}: {model}",
                            "value": f"{provider}:{model}"
                        })
    
    # Si no se encontró ningún modelo, añadir uno predeterminado
    if not all_models:
        all_models.append({
            "provider": "ollama",
            "name": "llama2",
            "display_name": "Ollama: llama2 (default)",
            "value": "llama2"
        })
    
    return all_models

# FASE 4: Reemplazar diccionario global con GenerationStateManager
from generation_state import (
    GenerationStateManager,
    GenerationStatus,
    SocketIOObserver,
    LoggingObserver
)

# Crear gestor de estado con observers
state_manager = GenerationStateManager()
# Se agregará el SocketIOObserver después de que socketio esté definido

@app.route('/')
def index():
    # Obtener modelos disponibles para pasar a la plantilla
    models = get_available_models()
    return render_template('index.html', models=models)

@app.route('/models')
def get_models():
    # Endpoint para obtener modelos disponibles mediante AJAX
    models = get_available_models()
    return jsonify({"models": models})

@app.route('/generate', methods=['POST'])
def generate():
    # FASE 4: Usar state_manager en lugar de diccionario global
    state_manager.reset()
    state_manager.update_state(
        status=GenerationStatus.STARTING,
        current_step='Iniciando generación...',
        progress=0
    )
    
    data = request.json
    subject = data.get('subject', 'Aventuras en un mundo cyberpunk')
    profile = data.get('profile', 'Protagonista rebelde en un entorno distópico')
    style = data.get('style', 'Narrativo-Épico-Imaginativo')
    genre = data.get('genre', 'Cyberpunk')
    model = data.get('model', 'llama2')
    output_format = data.get('outputFormat', 'docx')
    output_path = data.get('outputPath', './docs')
    
    # Normalizar la ruta de salida
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), output_path.lstrip('./\\'))
    
    # Actualizar el formato de salida en el estado
    state_manager.update_state(output_format=output_format)

    # Iniciar el proceso en un hilo separado
    thread = threading.Thread(
        target=generate_book, 
        args=(subject, profile, style, genre, model, output_format, output_path)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"status": "Generation started", "outputFormat": output_format})

def generate_book(subject, profile, style, genre, model, output_format, output_path):
    """
    Genera el libro completo. FASE 4: Usa GenerationStateManager inmutable.
    """
    # Redireccionar la salida estándar para capturarla
    old_stdout = sys.stdout
    sys.stdout = OutputCapture()
    
    try:
        # FASE 4: Obtener configuración de rate limiting
        rate_limit_config = config.rate_limit
        
        # Paso 1: Configurar el modelo
        state_manager.update_state(
            status=GenerationStatus.CONFIGURING_MODEL,
            current_step=f'Configurando modelo: {model}',
            progress=2
        )
        time.sleep(rate_limit_config.default_delay)
        
        # Actualizar el modelo seleccionado en utils.py
        print(f"Modelo seleccionado: {model}")
        update_model_name(model)
        
        # Paso 2: Generación de estructura (20%)
        state_manager.update_state(
            status=GenerationStatus.GENERATING_STRUCTURE,
            current_step='Generando estructura básica...',
            progress=5
        )
        
        title, framework, chapter_dict = get_structure(subject, genre, style, profile)
        
        state_manager.update_state(
            status=GenerationStatus.STRUCTURE_COMPLETE,
            title=title,
            chapter_count=len(chapter_dict),
            current_step=f'Estructura generada: {title}',
            progress=20
        )
        time.sleep(rate_limit_config.default_delay)
        
        # Paso 3: Generación de ideas (40%)
        state_manager.update_state(
            status=GenerationStatus.GENERATING_IDEAS,
            current_step='Generando ideas para cada capítulo...',
            progress=25
        )
        
        summaries_dict, idea_dict = get_ideas(subject, genre, style, profile, title, framework, chapter_dict)
        
        state_manager.update_state(
            status=GenerationStatus.IDEAS_COMPLETE,
            current_step=f'Ideas generadas para {len(idea_dict)} capítulos',
            progress=40
        )
        time.sleep(rate_limit_config.default_delay)
        
        # Paso 4: Escritura del libro y generación de resúmenes (85%)
        state_manager.update_state(
            status=GenerationStatus.WRITING_BOOK,
            current_step='Escribiendo el libro...',
            progress=45
        )
        
        # Inicializar el diccionario de resúmenes de capítulos
        chapter_summaries = {}
        chapter_summary_chain = ChapterSummaryChain()
        
        # Escribir el libro capítulo a capítulo, generando resúmenes a medida que avanzamos
        book = {}
        total_chapters = len(idea_dict)
        progress_per_chapter = 40 / total_chapters  # 40% del progreso total distribuido entre capítulos
        
        for i, (chapter, idea_list) in enumerate(idea_dict.items(), 1):
            state_manager.update_state(
                status=GenerationStatus.WRITING_BOOK,
                current_chapter=i,
                current_step=f'Escribiendo capítulo {i}/{total_chapters}: {chapter}',
                progress=int(45 + (i-1) * progress_per_chapter)
            )
            
            # Escribir un solo capítulo a la vez
            chapter_title = summaries_dict[chapter].split('\n')[0] if '\n' in summaries_dict[chapter] else chapter
            chapter_book = write_book(
                genre, style, profile, title, framework, 
                {chapter: summaries_dict[chapter]}, 
                {chapter: idea_list},
                chapter_summaries
            )
            
            # Combinar con el libro principal
            book.update(chapter_book)
            
            # Generar resumen para este capítulo completo para usar en los siguientes
            chapter_content = "\n\n".join(chapter_book[chapter])
            chapter_summaries[chapter] = chapter_summary_chain.run(
                title=title,
                chapter_num=i,
                chapter_title=chapter_title,
                chapter_content=chapter_content,
                total_chapters=total_chapters
            )
            
            state_manager.update_state(
                status=GenerationStatus.CHAPTER_COMPLETE,
                current_step=f'Capítulo {i}/{total_chapters} completado',
                progress=int(45 + i * progress_per_chapter)
            )
            
        state_manager.update_state(
            status=GenerationStatus.WRITING_COMPLETE,
            current_step='Contenido del libro generado',
            progress=85
        )
        time.sleep(rate_limit_config.default_delay)
        
        # Paso 5: Guardado del documento (100%)
        state_manager.update_state(
            status=GenerationStatus.SAVING_DOCUMENT,
            current_step=f'Guardando documento en formato {output_format.upper()}...',
            progress=90
        )
        
        doc_writer = DocWriter()
        file_path = doc_writer.write_doc(
            book, 
            chapter_dict, 
            title, 
            output_format=output_format, 
            output_path=output_path
        )
        
        # Verificar que el archivo se guardó correctamente
        if os.path.exists(file_path):
            # Generar una URL relativa para la descarga
            relative_path = os.path.relpath(file_path, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            download_path = relative_path.replace('\\', '/')
            
            # Extraer solo el nombre del archivo
            filename = os.path.basename(file_path)
            
            # Generación completada con éxito
            state_manager.update_state(
                status=GenerationStatus.COMPLETE,
                current_step=f'Libro "{title}" completado con éxito y guardado como {filename}',
                progress=100,
                book_ready=True,
                file_path=download_path
            )
        else:
            # Hubo un error al guardar
            state_manager.update_state(
                status=GenerationStatus.ERROR,
                current_step='Error al guardar el libro. Generación completada pero el archivo no se encuentra.',
                progress=95,
                error='Archivo no encontrado'
            )
        
    except Exception as e:
        # Manejar errores
        error_msg = str(e)
        current_progress = state_manager.get_state().progress
        state_manager.update_state(
            status=GenerationStatus.ERROR,
            current_step=f'Error: {error_msg}',
            progress=current_progress,
            error=error_msg
        )
    finally:
        # Restaurar la salida estándar
        sys.stdout.flush()
        sys.stdout = old_stdout

# FASE 4: Función eliminada - usar state_manager.update_state() directamente
# def update_generation_state(status, step, progress):
#     Esta función ha sido eliminada. Usar state_manager.update_state() en su lugar.

@app.route('/download/<path:filename>')
def download(filename):
    # Determinar el directorio base para la descarga
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Primero intentar con la ruta exacta proporcionada
    if os.path.exists(os.path.join(root_dir, filename)):
        directory = os.path.dirname(os.path.join(root_dir, filename))
        base_filename = os.path.basename(filename)
        return send_from_directory(directory, base_filename)
    
    # Luego probar con la carpeta docs
    if os.path.exists(os.path.join(root_dir, 'docs', os.path.basename(filename))):
        return send_from_directory(os.path.join(root_dir, 'docs'), os.path.basename(filename))
    
    # Si ninguna encuentra el archivo
    return "Archivo no encontrado", 404

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, '..', 'templates'), 'favicon.ico')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.root_path, '..', 'templates'), filename)

@socketio.on('connect')
def handle_connect():
    # FASE 4: Enviar el estado actual al cliente cuando se conecta
    socketio.emit('status_update', state_manager.get_state().to_dict())

if __name__ == '__main__':
    # Asegurarse de que exista el directorio docs
    os.makedirs(os.path.join(parent_dir, 'docs'), exist_ok=True)
    
    # Iniciar el servidor web
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)