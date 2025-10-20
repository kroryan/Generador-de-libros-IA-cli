"""
Sistema de Limpieza para Streaming de Texto con Buffer de Palabras.

Este módulo proporciona limpieza en tiempo real para streams de texto,
manejando casos especiales como tags de pensamiento que pueden aparecer
fragmentados en múltiples chunks, y acumulando tokens hasta formar
palabras completas antes de enviarlas.

Reemplaza la lógica manual de detección de tags en OutputCapture.
"""

import os
import re
from enum import Enum
from typing import Tuple, Optional, Callable, List
from text_cleaning import clean_ansi_codes, clean_think_tags


class StreamState(Enum):
    """Estados del stream durante el procesamiento."""
    NORMAL = "normal"           # Procesando texto normal
    IN_THINK_BLOCK = "in_think" # Dentro de un bloque <think>
    BUFFERING = "buffering"     # Buffering para detectar tags


class StreamingCleaner:
    """
    Limpiador especializado para streaming que mantiene estado
    y puede detectar tags que aparecen fragmentados.
    """
    
    def __init__(
        self,
        on_normal_output: Optional[Callable[[str], None]] = None,
        on_think_output: Optional[Callable[[str, str], None]] = None,
        buffer_threshold: int = 50
    ):
        """
        Inicializa el limpiador de streaming.
        
        Args:
            on_normal_output: Callback para output normal (recibe el texto)
            on_think_output: Callback para output de pensamiento (recibe texto y tipo)
            buffer_threshold: Umbral de caracteres para enviar buffer acumulado
        """
        self.state = StreamState.NORMAL
        self.buffer = ""
        self.think_buffer = ""
        self.partial_buffer = ""  # Para detectar tags fragmentados
        
        # NUEVO: Buffer para acumular palabras completas
        self.word_buffer = ""
        self.think_word_buffer = ""
        
        self.on_normal_output = on_normal_output
        self.on_think_output = on_think_output
        self.buffer_threshold = buffer_threshold
        
        # Configuración del buffer de palabras desde variables de entorno
        self.word_buffer_size = int(os.getenv('STREAMING_WORD_BUFFER_SIZE', '50'))
        word_delims = os.getenv('STREAMING_WORD_DELIMITERS', ' ,.\n\t;:!?"\'()[]{}')
        self.word_delimiters = list(word_delims)
        
        # Patrones de tags a detectar
        self.think_start_tag = "<think>"
        self.think_end_tag = "</think>"
    
    def process_chunk(self, data: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Procesa un chunk de datos del stream.
        
        Args:
            data: Chunk de datos a procesar
            
        Returns:
            Tupla (normal_output, think_output) con el output procesado.
            Cualquiera puede ser None si no hay output en ese tipo.
        """
        if not data:
            return None, None
        
        # Limpiar códigos ANSI del chunk
        data = clean_ansi_codes(data)
        
        normal_out = None
        think_out = None
        
        # Detectar tags de pensamiento
        if self.think_start_tag in data:
            normal_out, think_out = self._handle_think_start(data)
        elif self.think_end_tag in data:
            normal_out, think_out = self._handle_think_end(data)
        else:
            # No hay tags, procesar según estado actual
            if self.state == StreamState.IN_THINK_BLOCK:
                think_out = self._accumulate_think_data(data)
            else:
                normal_out = self._accumulate_normal_data(data)
        
        # Llamar callbacks si están configurados
        if normal_out and self.on_normal_output:
            self.on_normal_output(normal_out)
        
        if think_out and self.on_think_output:
            think_type = self._get_think_output_type()
            self.on_think_output(think_out, think_type)
        
        return normal_out, think_out
    
    def _handle_think_start(self, data: str) -> Tuple[Optional[str], Optional[str]]:
        """Maneja la detección de tag de inicio de pensamiento."""
        normal_out = None
        think_out = None
        
        # Enviar cualquier buffer pendiente como output normal
        if self.buffer.strip():
            normal_out = self.buffer.strip()
            self.buffer = ""
        
        # Cambiar a modo pensamiento
        self.state = StreamState.IN_THINK_BLOCK
        
        # Extraer contenido después del tag
        parts = data.split(self.think_start_tag, 1)
        if len(parts) > 1:
            content_after_tag = parts[1].strip()
            if content_after_tag:
                think_out = content_after_tag
                self.think_buffer = ""
            else:
                self.think_buffer = ""
        
        return normal_out, think_out
    
    def _handle_think_end(self, data: str) -> Tuple[Optional[str], Optional[str]]:
        """Maneja la detección de tag de fin de pensamiento."""
        normal_out = None
        think_out = None
        
        # Cambiar a modo normal
        self.state = StreamState.NORMAL
        
        # Extraer contenido antes del tag
        parts = data.split(self.think_end_tag, 1)
        
        # Agregar contenido antes del tag al buffer de pensamiento
        if parts[0]:
            self.think_buffer += parts[0].strip()
        
        # Enviar el bloque completo de pensamiento si hay algo
        if self.think_buffer.strip():
            think_out = self.think_buffer.strip()
            self.think_buffer = ""
        
        # Si hay contenido después del tag, acumularlo como normal
        if len(parts) > 1 and parts[1].strip():
            self.buffer = parts[1].strip()
        
        return normal_out, think_out
    
    def _accumulate_think_data(self, data: str) -> Optional[str]:
        """Acumula datos en el buffer de pensamiento con buffer de palabras."""
        return self._accumulate_word_data(data, is_think=True)
    
    def _accumulate_normal_data(self, data: str) -> Optional[str]:
        """Acumula datos en el buffer normal con buffer de palabras."""
        return self._accumulate_word_data(data, is_think=False)
    
    def _accumulate_word_data(self, data: str, is_think: bool = False) -> Optional[str]:
        """
        Acumula datos en el buffer de palabras hasta detectar palabra completa.
        
        Args:
            data: Datos a acumular
            is_think: True si es para buffer de pensamiento, False para normal
            
        Returns:
            Palabra completa lista para enviar o None si aún está acumulando
        """
        # Seleccionar el buffer apropiado
        if is_think:
            self.think_word_buffer += data
            current_buffer = self.think_word_buffer
        else:
            self.word_buffer += data
            current_buffer = self.word_buffer
        
        # Buscar delimitadores en el nuevo data que indican fin de palabra
        has_delimiter_in_data = any(delim in data for delim in self.word_delimiters)
        
        # Enviar si:
        # 1. El nuevo chunk contiene delimitador (fin de palabra)
        # 2. Buffer muy largo (evitar bloqueo en palabras muy largas)
        # 3. Hay salto de línea (párrafo completo)
        should_flush = (
            has_delimiter_in_data or 
            len(current_buffer) > self.word_buffer_size or
            '\n' in data
        )
        
        if should_flush and current_buffer.strip():
            # Si hay delimitador, buscar hasta dónde enviar
            if has_delimiter_in_data:
                # Encontrar la posición del último delimitador
                last_delim_pos = -1
                for delim in self.word_delimiters:
                    pos = current_buffer.rfind(delim)
                    if pos > last_delim_pos:
                        last_delim_pos = pos
                
                if last_delim_pos >= 0:
                    # Enviar hasta el delimitador (inclusive)
                    output = current_buffer[:last_delim_pos + 1].strip()
                    # Mantener el resto en el buffer
                    remaining = current_buffer[last_delim_pos + 1:]
                    if is_think:
                        self.think_word_buffer = remaining
                    else:
                        self.word_buffer = remaining
                    
                    if output:
                        return output
            else:
                # No hay delimitador, enviar todo
                output = current_buffer.strip()
                if is_think:
                    self.think_word_buffer = ""
                else:
                    self.word_buffer = ""
                
                if output:
                    return output
        
        return None
    
    def _get_think_output_type(self) -> str:
        """Determina el tipo de output de pensamiento según el estado."""
        if self.state == StreamState.IN_THINK_BLOCK:
            return 'content'
        else:
            return 'end'
    
    def flush(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Flush de todos los buffers pendientes (incluyendo buffers de palabras).
        
        Returns:
            Tupla (normal_output, think_output) con cualquier contenido pendiente.
        """
        normal_out = None
        think_out = None
        
        # Enviar buffer de palabras de pensamiento si estamos en modo pensamiento
        if self.think_word_buffer and self.state == StreamState.IN_THINK_BLOCK:
            if self.think_word_buffer.strip():
                think_out = self.think_word_buffer.strip()
            self.think_word_buffer = ""
        
        # Enviar buffer de palabras normal si hay algo
        if self.word_buffer:
            if self.word_buffer.strip():
                normal_out = self.word_buffer.strip()
            self.word_buffer = ""
        
        # Fallback a buffers originales si los de palabras están vacíos
        if not think_out and self.think_buffer and self.state == StreamState.IN_THINK_BLOCK:
            if self.think_buffer.strip():
                think_out = self.think_buffer.strip()
            self.think_buffer = ""
        
        if not normal_out and self.buffer:
            if self.buffer.strip():
                normal_out = self.buffer.strip()
            self.buffer = ""
        
        # Llamar callbacks si están configurados
        if normal_out and self.on_normal_output:
            self.on_normal_output(normal_out)
        
        if think_out and self.on_think_output:
            self.on_think_output(think_out, 'content')
        
        return normal_out, think_out
    
    def reset(self):
        """Resetea el estado del limpiador."""
        self.state = StreamState.NORMAL
        self.buffer = ""
        self.think_buffer = ""
        self.partial_buffer = ""
        # Limpiar también los buffers de palabras
        self.word_buffer = ""
        self.think_word_buffer = ""


class OutputCapture:
    """
    Clase de compatibilidad que envuelve StreamingCleaner
    para mantener la interfaz existente de OutputCapture en server.py.
    
    Esta versión usa el sistema unificado de limpieza en lugar de
    lógica manual de detección de tags.
    """
    
    def __init__(self, socketio_emit_func=None):
        """
        Inicializa OutputCapture con soporte para emit de socketio.
        
        Args:
            socketio_emit_func: Función para emitir eventos (ej: socketio.emit)
        """
        self.emit_func = socketio_emit_func
        
        # Crear el streaming cleaner con callbacks
        self.cleaner = StreamingCleaner(
            on_normal_output=self._emit_normal,
            on_think_output=self._emit_think,
            buffer_threshold=50
        )
    
    def _emit_normal(self, data: str):
        """Callback para emitir output normal."""
        if self.emit_func and data:
            self.emit_func('result_update', {'data': data})
    
    def _emit_think(self, data: str, think_type: str):
        """Callback para emitir output de pensamiento."""
        if self.emit_func and data:
            self.emit_func('thinking_update', {'data': data, 'type': think_type})
    
    def write(self, data: str):
        """
        Escribe datos al output, procesándolos con el streaming cleaner.
        
        Args:
            data: Datos a escribir
        """
        self.cleaner.process_chunk(data)
    
    def flush(self):
        """Flush de todos los buffers pendientes."""
        self.cleaner.flush()
    
    def reset(self):
        """Resetea el estado del capture."""
        self.cleaner.reset()
    
    # Propiedades para compatibilidad con código existente
    @property
    def in_think_block(self) -> bool:
        """Indica si estamos actualmente en un bloque de pensamiento."""
        return self.cleaner.state == StreamState.IN_THINK_BLOCK
    
    @property
    def buffer(self) -> str:
        """Buffer normal actual (incluye buffer de palabras)."""
        return self.cleaner.buffer + self.cleaner.word_buffer
    
    @property
    def think_buffer(self) -> str:
        """Buffer de pensamiento actual (incluye buffer de palabras)."""
        return self.cleaner.think_buffer + self.cleaner.think_word_buffer
    
    # Propiedades adicionales para inspección del buffer de palabras
    @property
    def word_buffer(self) -> str:
        """Buffer de palabras normal actual."""
        return self.cleaner.word_buffer
    
    @property
    def think_word_buffer(self) -> str:
        """Buffer de palabras de pensamiento actual."""
        return self.cleaner.think_word_buffer
