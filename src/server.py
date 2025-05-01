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

# Utilizar el servidor integrado de werkzeug para evitar problemas de monkey patching
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_interval=25,        # Latido cada 25 segundos para mantener la conexión viva
    ping_timeout=259200      # Timeout de 72 horas (en segundos)
)

# Función para limpiar códigos de escape ANSI
def clean_ansi_codes(text):
    # Patrón para capturar códigos de escape ANSI
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    # También limpiar patrones como [97m, [0m, [1m, etc.
    ansi_simple = re.compile(r'\[\d+m')
    
    # Primero eliminamos códigos de escape complejos
    text = ansi_escape.sub('', text)
    # Luego los códigos simples
    text = ansi_simple.sub('', text)
    return text

# Clase para capturar la salida y enviarla a través de websockets
class OutputCapture:
    def __init__(self):
        self.in_think_block = False
        self.buffer = ""
        self.think_buffer = ""
        self.result_buffer = ""
        
    def write(self, data):
        # Limpiar códigos de escape ANSI y otros prefijos
        data = clean_ansi_codes(data)
        
        # Detectar inicio y fin de bloques de pensamiento
        if "<think>" in data:
            # Enviar cualquier texto pendiente antes de entrar en modo pensamiento
            if self.buffer.strip():
                socketio.emit('result_update', {'data': self.buffer.strip()})
                self.buffer = ""
            
            self.in_think_block = True
            # Eliminar la etiqueta <think> del mensaje
            data = data.replace("<think>", "")
            self.think_buffer = data.strip()
            
            # Si hay contenido después de quitar <think>, emitirlo inmediatamente
            if self.think_buffer:
                socketio.emit('thinking_update', {'data': self.think_buffer, 'type': 'start'})
                self.think_buffer = ""
            return
        elif "</think>" in data:
            self.in_think_block = False
            # Eliminar la etiqueta </think> del mensaje
            data = data.replace("</think>", "")
            # Agregar cualquier texto final al buffer de pensamiento
            self.think_buffer += data.strip()
            
            # Enviar el bloque completo de pensamiento si hay algo
            if self.think_buffer.strip():
                socketio.emit('thinking_update', {
                    'data': self.think_buffer.strip(), 
                    'type': 'end'
                })
            
            self.think_buffer = ""
            return
            
        # Acumular datos según el modo actual
        if self.in_think_block:
            self.think_buffer += data
            
            # Solo enviar cuando hay suficiente texto acumulado o hay un salto de línea
            if len(self.think_buffer) > 50 or '\n' in data:
                if self.think_buffer.strip():
                    socketio.emit('thinking_update', {
                        'data': self.think_buffer.strip(), 
                        'type': 'content'
                    })
                self.think_buffer = ""
        else:
            self.buffer += data
            
            # Solo enviar cuando hay suficiente texto acumulado o hay un salto de línea
            if len(self.buffer) > 50 or '\n' in data:
                if self.buffer.strip():
                    socketio.emit('result_update', {'data': self.buffer.strip()})
                self.buffer = ""
    
    def flush(self):
        # Enviar cualquier texto pendiente en los buffers
        if self.think_buffer and self.in_think_block:
            if self.think_buffer.strip():
                socketio.emit('thinking_update', {
                    'data': self.think_buffer.strip(),
                    'type': 'content'
                })
            self.think_buffer = ""
        
        if self.buffer:
            if self.buffer.strip():
                socketio.emit('result_update', {'data': self.buffer.strip()})
            self.buffer = ""

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

# Estado global para seguimiento del progreso
generation_state = {
    'status': 'idle',
    'title': '',
    'current_step': '',
    'progress': 0,
    'chapter_count': 0,
    'current_chapter': 0,
    'error': None,
    'book_ready': False,
    'file_path': '',
    'output_format': 'docx'
}

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
    # Reiniciar el estado de generación
    global generation_state
    generation_state = {
        'status': 'starting',
        'title': '',
        'current_step': 'Iniciando generación...',
        'progress': 0,
        'chapter_count': 0,
        'current_chapter': 0,
        'error': None,
        'book_ready': False,
        'file_path': '',
        'output_format': 'docx'
    }
    socketio.emit('status_update', generation_state)
    
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
    generation_state['output_format'] = output_format

    # Iniciar el proceso en un hilo separado
    thread = threading.Thread(
        target=generate_book, 
        args=(subject, profile, style, genre, model, output_format, output_path)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"status": "Generation started", "outputFormat": output_format})

def generate_book(subject, profile, style, genre, model, output_format, output_path):
    # Redireccionar la salida estándar para capturarla
    old_stdout = sys.stdout
    sys.stdout = OutputCapture()
    
    try:
        # Paso 1: Configurar el modelo
        update_generation_state('configuring_model', f'Configurando modelo: {model}', 2)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Actualizar el modelo seleccionado en utils.py
        print(f"Modelo seleccionado: {model}")
        update_model_name(model)
        
        # Paso 2: Generación de estructura (20%)
        update_generation_state('generating_structure', 'Generando estructura básica...', 5)
        socketio.emit('status_update', generation_state)
        
        title, framework, chapter_dict = get_structure(subject, genre, style, profile)
        generation_state['title'] = title
        generation_state['chapter_count'] = len(chapter_dict)
        update_generation_state('structure_complete', f'Estructura generada: {title}', 20)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 3: Generación de ideas (40%)
        update_generation_state('generating_ideas', 'Generando ideas para cada capítulo...', 25)
        socketio.emit('status_update', generation_state)
        
        summaries_dict, idea_dict = get_ideas(subject, genre, style, profile, title, framework, chapter_dict)
        update_generation_state('ideas_complete', f'Ideas generadas para {len(idea_dict)} capítulos', 40)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 4: Escritura del libro y generación de resúmenes (85%)
        update_generation_state('writing_book', 'Escribiendo el libro...', 45)
        socketio.emit('status_update', generation_state)
        
        # Inicializar el diccionario de resúmenes de capítulos
        chapter_summaries = {}
        chapter_summary_chain = ChapterSummaryChain()
        
        # Escribir el libro capítulo a capítulo, generando resúmenes a medida que avanzamos
        book = {}
        total_chapters = len(idea_dict)
        progress_per_chapter = 40 / total_chapters  # 40% del progreso total distribuido entre capítulos
        
        for i, (chapter, idea_list) in enumerate(idea_dict.items(), 1):
            generation_state['current_chapter'] = i
            update_generation_state(
                'writing_chapter', 
                f'Escribiendo capítulo {i}/{total_chapters}: {chapter}', 
                45 + (i-1) * progress_per_chapter
            )
            socketio.emit('status_update', generation_state)
            
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
            
            update_generation_state(
                'chapter_complete', 
                f'Capítulo {i}/{total_chapters} completado', 
                45 + i * progress_per_chapter
            )
            socketio.emit('status_update', generation_state)
            
        update_generation_state('writing_complete', 'Contenido del libro generado', 85)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 5: Guardado del documento (100%)
        update_generation_state('saving_document', f'Guardando documento en formato {output_format.upper()}...', 90)
        socketio.emit('status_update', generation_state)
        
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
            update_generation_state(
                'complete', 
                f'Libro "{title}" completado con éxito y guardado como {filename}', 
                100
            )
            generation_state['book_ready'] = True
            generation_state['file_path'] = download_path
        else:
            # Hubo un error al guardar
            update_generation_state('error', 'Error al guardar el libro. Generación completada pero el archivo no se encuentra.', 95)
            generation_state['error'] = 'Archivo no encontrado'
        
        socketio.emit('status_update', generation_state)
        
    except Exception as e:
        # Manejar errores
        error_msg = str(e)
        update_generation_state('error', f'Error: {error_msg}', generation_state['progress'])
        generation_state['error'] = error_msg
        socketio.emit('status_update', generation_state)
    finally:
        # Restaurar la salida estándar
        sys.stdout.flush()
        sys.stdout = old_stdout

def update_generation_state(status, step, progress):
    generation_state['status'] = status
    generation_state['current_step'] = step
    generation_state['progress'] = progress

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
    # Enviar el estado actual al cliente cuando se conecta
    socketio.emit('status_update', generation_state)

if __name__ == '__main__':
    # Asegurarse de que exista el directorio docs
    os.makedirs(os.path.join(parent_dir, 'docs'), exist_ok=True)
    
    # Iniciar el servidor web
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)