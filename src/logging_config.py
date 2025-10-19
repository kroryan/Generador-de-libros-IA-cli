"""
Configuración de logging estructurado para el proyecto.
Reemplaza los print_progress() dispersos con logging profesional.
"""

import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

class StructuredFormatter(logging.Formatter):
    """
    Formatter que produce logs estructurados en JSON para producción
    o formato pretty para desarrollo.
    """
    
    def __init__(self, use_json: bool = True):
        super().__init__()
        self.use_json = use_json
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_json:
            return self._format_json(record)
        else:
            return self._format_pretty(record)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """Formato JSON estructurado"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Agregar campos adicionales si existen
        if hasattr(record, 'provider'):
            log_entry['provider'] = record.provider
        if hasattr(record, 'attempt'):
            log_entry['attempt'] = record.attempt
        if hasattr(record, 'circuit_breaker'):
            log_entry['circuit_breaker'] = record.circuit_breaker
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        
        # Agregar excepción si existe
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)
    
    def _format_pretty(self, record: logging.LogRecord) -> str:
        """Formato pretty para desarrollo"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Colores ANSI para diferentes niveles
        colors = {
            'DEBUG': '\033[36m',     # Cyan
            'INFO': '\033[32m',      # Green
            'WARNING': '\033[33m',   # Yellow
            'ERROR': '\033[31m',     # Red
            'CRITICAL': '\033[35m'   # Magenta
        }
        reset = '\033[0m'
        
        color = colors.get(record.levelname, '')
        
        # Información contextual
        context_parts = []
        if hasattr(record, 'provider'):
            context_parts.append(f"provider={record.provider}")
        if hasattr(record, 'attempt'):
            context_parts.append(f"attempt={record.attempt}")
        if hasattr(record, 'operation'):
            context_parts.append(f"op={record.operation}")
        
        context = f" [{', '.join(context_parts)}]" if context_parts else ""
        
        formatted = f"{color}[{timestamp}] {record.levelname:8} {record.name:20}{context} | {record.getMessage()}{reset}"
        
        # Agregar excepción si existe
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted

class ContextLogger:
    """
    Logger con contexto automático para operaciones específicas.
    Permite agregar información contextual automáticamente.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Establece contexto para todos los logs subsecuentes"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Limpia el contexto"""
        self.context.clear()
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log con contexto automático"""
        # Combinar contexto global con kwargs específicos
        extra = {**self.context, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def progress(self, message: str, **kwargs):
        """Método especial para logs de progreso (reemplaza print_progress)"""
        self.info(f"🔄 {message}", operation="progress", **kwargs)

class LoggingConfig:
    """Configuración centralizada de logging"""
    
    @staticmethod
    def setup_logging():
        """Configura el sistema de logging basado en variables de entorno"""
        
        # Configuración desde variables de entorno
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_format = os.environ.get("LOG_FORMAT", "pretty").lower()  # json o pretty
        log_file_path = os.environ.get("LOG_FILE_PATH", "./logs/app.log")
        log_rotation_size = os.environ.get("LOG_ROTATION_SIZE", "10MB")
        
        # Crear directorio de logs si no existe
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Limpiar handlers existentes
        root_logger.handlers.clear()
        
        # Determinar si usar formato JSON
        use_json = log_format == "json"
        formatter = StructuredFormatter(use_json=use_json)
        
        # Handler para consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level, logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Handler para archivo con rotación
        try:
            # Convertir tamaño de string a bytes
            size_str = log_rotation_size.upper()
            if size_str.endswith('MB'):
                max_bytes = int(size_str[:-2]) * 1024 * 1024
            elif size_str.endswith('KB'):
                max_bytes = int(size_str[:-2]) * 1024
            else:
                max_bytes = int(size_str)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # Archivo siempre guarda todo
            
            # Para archivos, usar siempre formato JSON para facilitar parsing
            json_formatter = StructuredFormatter(use_json=True)
            file_handler.setFormatter(json_formatter)
            root_logger.addHandler(file_handler)
            
        except Exception as e:
            # Si falla la configuración de archivo, continuar sin él
            logging.warning(f"No se pudo configurar logging a archivo: {e}")
        
        # Configurar loggers específicos
        LoggingConfig._configure_specific_loggers()
        
        # Log inicial
        logging.info("Sistema de logging configurado", extra={
            "log_level": log_level,
            "log_format": log_format,
            "log_file": log_file_path
        })
    
    @staticmethod
    def _configure_specific_loggers():
        """Configura loggers específicos para diferentes módulos"""
        
        # Reducir verbosidad de librerías externas
        external_loggers = [
            'urllib3',
            'requests',
            'langchain',
            'openai',
            'httpx'
        ]
        
        for logger_name in external_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
        
        # Configurar loggers internos
        internal_loggers = [
            'provider_registry',
            'provider_chain',
            'retry_strategy',
            'circuit_breaker',
            'writing',
            'utils'
        ]
        
        for logger_name in internal_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.INFO)

# Funciones de conveniencia para mantener compatibilidad
def get_logger(name: str) -> ContextLogger:
    """Obtiene un logger con contexto para un módulo específico"""
    return ContextLogger(name)

def print_progress(message: str, **kwargs):
    """
    Función de compatibilidad para reemplazar print_progress existente.
    Migra gradualmente a logging estructurado.
    """
    logger = get_logger("progress")
    logger.progress(message, **kwargs)

# Configurar logging automáticamente al importar
LoggingConfig.setup_logging()

# Loggers comunes para usar en el proyecto
app_logger = get_logger("app")
provider_logger = get_logger("provider")
writing_logger = get_logger("writing")
utils_logger = get_logger("utils")