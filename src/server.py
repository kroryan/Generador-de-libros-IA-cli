import sys
import os
import re
import requests

# Add the parent directory to the Python path to resolve the 'src' module issue
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_socketio import SocketIO
import threading
import time
from src.structure import get_structure
from src.ideas import get_ideas
from src.writing import write_book
from src.publishing import DocWriter

# Configurar correctamente Flask para servir archivos estáticos desde templates
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../templates')
socketio = SocketIO(app, cors_allowed_origins="*")

# Función para obtener los modelos disponibles en Ollama
def get_available_models():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get('models', [])
            # Ordenar modelos por nombre
            return sorted([model['name'] for model in models])
        else:
            return ["hf.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF:Q4_K_M"]  # Modelo por defecto
    except Exception as e:
        print(f"Error al obtener los modelos: {e}")
        return ["hf.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF:Q4_K_M"]  # Modelo por defecto en caso de error

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
        self.current_text = ""
        self.buffer = ""
        self.collect_after_think = False
        self.result_buffer = ""
        
    def write(self, data):
        # Limpiar códigos de escape ANSI y otros prefijos
        data = clean_ansi_codes(data)
        
        # Detectar inicio y fin de bloques de pensamiento
        if "<think>" in data:
            # Si estábamos recolectando texto después de un </think>, 
            # enviar lo acumulado como un mensaje de resultado
            if self.collect_after_think and self.result_buffer.strip():
                socketio.emit('result_update', {'data': self.result_buffer.strip()})
                self.result_buffer = ""
            
            self.in_think_block = True
            # Eliminar la etiqueta <think> del mensaje
            cleaned_data = data.replace("<think>", "")
            socketio.emit('thinking_update', {'data': self.buffer + cleaned_data, 'type': 'start'})
            self.buffer = ""
            self.collect_after_think = False
            return
        elif "</think>" in data:
            self.in_think_block = False
            # Eliminar la etiqueta </think> del mensaje
            cleaned_data = data.replace("</think>", "")
            socketio.emit('thinking_update', {'data': self.buffer + cleaned_data, 'type': 'end'})
            self.buffer = ""
            # Activar la recolección de texto después de un bloque de pensamiento
            self.collect_after_think = True
            return
            
        # Acumular datos en el buffer
        if self.in_think_block:
            self.buffer += data
            
            # Emitir cuando hay un salto de línea o un bloque grande
            if '\n' in data or len(self.buffer) > 80:
                cleaned_buffer = self.buffer.strip()
                if cleaned_buffer:  # Solo enviar si hay contenido después de limpiar
                    socketio.emit('thinking_update', {'data': cleaned_buffer, 'type': 'content'})
                self.buffer = ""
        else:
            # Si estamos después de un bloque </think>, acumular en result_buffer
            if self.collect_after_think:
                self.result_buffer += data
                
                # Emitir cuando hay un salto de línea o un bloque grande
                if '\n' in data or len(self.result_buffer) > 80:
                    cleaned_buffer = self.result_buffer.strip()
                    if cleaned_buffer:  # Solo enviar si hay contenido después de limpiar
                        socketio.emit('result_update', {'data': cleaned_buffer})
                    self.result_buffer = ""
            else:
                # Comportamiento normal para texto fuera de bloques de pensamiento
                self.buffer += data
                
                # Emitir cuando hay un salto de línea o un bloque grande
                if '\n' in data or len(self.buffer) > 80:
                    cleaned_buffer = self.buffer.strip()
                    if cleaned_buffer:  # Solo enviar si hay contenido después de limpiar
                        socketio.emit('result_update', {'data': cleaned_buffer})
                    self.buffer = ""
            
    def flush(self):
        # Enviar cualquier texto pendiente en los buffers
        if self.buffer and self.in_think_block:
            cleaned_buffer = self.buffer.strip()
            if cleaned_buffer:
                socketio.emit('thinking_update', {'data': cleaned_buffer, 'type': 'content'})
            self.buffer = ""
        elif self.collect_after_think and self.result_buffer:
            cleaned_buffer = self.result_buffer.strip()
            if cleaned_buffer:
                socketio.emit('result_update', {'data': cleaned_buffer})
            self.result_buffer = ""
        elif self.buffer:
            cleaned_buffer = self.buffer.strip()
            if cleaned_buffer:
                socketio.emit('result_update', {'data': cleaned_buffer})
            self.buffer = ""

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
    model = data.get('model', 'hf.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF:Q4_K_M')
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
        from src.utils import update_model_name
        update_model_name(model)
        
        # Paso 2: Generación de estructura (25%)
        update_generation_state('generating_structure', 'Generando estructura básica...', 5)
        socketio.emit('status_update', generation_state)
        
        title, framework, chapter_dict = get_structure(subject, genre, style, profile)
        generation_state['title'] = title
        generation_state['chapter_count'] = len(chapter_dict)
        update_generation_state('structure_complete', f'Estructura generada: {title}', 25)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 3: Generación de ideas (50%)
        update_generation_state('generating_ideas', 'Generando ideas para cada capítulo...', 30)
        socketio.emit('status_update', generation_state)
        
        summaries_dict, idea_dict = get_ideas(subject, genre, style, profile, title, framework, chapter_dict)
        update_generation_state('ideas_complete', f'Ideas generadas para {len(idea_dict)} capítulos', 50)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 4: Escritura del libro (90%)
        update_generation_state('writing_book', 'Escribiendo el libro...', 55)
        socketio.emit('status_update', generation_state)
        
        book = write_book(genre, style, profile, title, framework, summaries_dict, idea_dict)
        update_generation_state('writing_complete', 'Contenido del libro generado', 90)
        socketio.emit('status_update', generation_state)
        time.sleep(0.5)  # Pequeña pausa para la UI
        
        # Paso 5: Guardado del documento (100%)
        update_generation_state('saving_document', f'Guardando documento en formato {output_format.upper()}...', 95)
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
    # Determinar el directorio base buscando el archivo directamente
    if os.path.exists(os.path.join('../docs', filename)):
        return send_from_directory('../docs', filename)
    elif os.path.exists(os.path.join('docs', filename)):
        return send_from_directory('docs', filename)
    elif os.path.exists(filename):
        directory = os.path.dirname(filename)
        base_filename = os.path.basename(filename)
        if directory:
            return send_from_directory(directory, base_filename)
    
    # Si no encuentra el archivo
    return "Archivo no encontrado", 404

@app.route('/templates/<path:filename>')
def templates(filename):
    return send_from_directory('../templates', filename)

@socketio.on('connect')
def handle_connect():
    # Enviar el estado actual al cliente cuando se conecta
    socketio.emit('status_update', generation_state)

if __name__ == '__main__':
    os.makedirs('../docs', exist_ok=True)
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)