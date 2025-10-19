"""
Sistema de gestión de estado inmutable para la generación de libros.

FASE 4: Reemplaza el diccionario global mutable con un sistema
thread-safe basado en dataclasses inmutables y el patrón Observer.
"""

from dataclasses import dataclass, field, replace
from typing import Optional, List, Callable
from enum import Enum
from threading import Lock
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GenerationStatus(Enum):
    """Estados válidos del proceso de generación."""
    IDLE = "idle"
    STARTING = "starting"
    CONFIGURING_MODEL = "configuring_model"
    GENERATING_STRUCTURE = "generating_structure"
    STRUCTURE_COMPLETE = "structure_complete"
    GENERATING_IDEAS = "generating_ideas"
    IDEAS_COMPLETE = "ideas_complete"
    WRITING_BOOK = "writing_book"
    CHAPTER_COMPLETE = "chapter_complete"
    WRITING_COMPLETE = "writing_complete"
    SAVING_DOCUMENT = "saving_document"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass(frozen=True)
class GenerationState:
    """
    Estado inmutable de generación.
    
    Usa frozen=True para garantizar inmutabilidad. Los cambios se realizan
    mediante el método update() que retorna un nuevo estado.
    """
    status: GenerationStatus = GenerationStatus.IDLE
    title: str = ''
    current_step: str = ''
    progress: int = 0
    chapter_count: int = 0
    current_chapter: int = 0
    error: Optional[str] = None
    book_ready: bool = False
    file_path: str = ''
    output_format: str = 'docx'
    timestamp: datetime = field(default_factory=datetime.now)
    
    def update(self, **kwargs) -> 'GenerationState':
        """
        Crea un nuevo estado con los cambios especificados.
        
        Args:
            **kwargs: Campos a actualizar
            
        Returns:
            GenerationState: Nuevo estado inmutable con cambios aplicados
        """
        return replace(self, timestamp=datetime.now(), **kwargs)
    
    def to_dict(self) -> dict:
        """
        Convierte a diccionario para serialización (SocketIO).
        
        Returns:
            dict: Representación serializable del estado
        """
        return {
            'status': self.status.value,
            'title': self.title,
            'current_step': self.current_step,
            'progress': self.progress,
            'chapter_count': self.chapter_count,
            'current_chapter': self.current_chapter,
            'error': self.error,
            'book_ready': self.book_ready,
            'file_path': self.file_path,
            'output_format': self.output_format
        }
    
    def can_transition_to(self, new_status: GenerationStatus) -> bool:
        """
        Valida si la transición de estado es válida.
        
        Implementa una máquina de estados finita para prevenir
        transiciones inválidas.
        
        Args:
            new_status: Estado destino
            
        Returns:
            bool: True si la transición es válida
        """
        valid_transitions = {
            GenerationStatus.IDLE: [
                GenerationStatus.STARTING
            ],
            GenerationStatus.STARTING: [
                GenerationStatus.CONFIGURING_MODEL,
                GenerationStatus.ERROR
            ],
            GenerationStatus.CONFIGURING_MODEL: [
                GenerationStatus.GENERATING_STRUCTURE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.GENERATING_STRUCTURE: [
                GenerationStatus.STRUCTURE_COMPLETE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.STRUCTURE_COMPLETE: [
                GenerationStatus.GENERATING_IDEAS,
                GenerationStatus.ERROR
            ],
            GenerationStatus.GENERATING_IDEAS: [
                GenerationStatus.IDEAS_COMPLETE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.IDEAS_COMPLETE: [
                GenerationStatus.WRITING_BOOK,
                GenerationStatus.ERROR
            ],
            GenerationStatus.WRITING_BOOK: [
                GenerationStatus.CHAPTER_COMPLETE,
                GenerationStatus.WRITING_COMPLETE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.CHAPTER_COMPLETE: [
                GenerationStatus.WRITING_BOOK,
                GenerationStatus.WRITING_COMPLETE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.WRITING_COMPLETE: [
                GenerationStatus.SAVING_DOCUMENT,
                GenerationStatus.ERROR
            ],
            GenerationStatus.SAVING_DOCUMENT: [
                GenerationStatus.COMPLETE,
                GenerationStatus.ERROR
            ],
            GenerationStatus.COMPLETE: [
                GenerationStatus.IDLE
            ],
            GenerationStatus.ERROR: [
                GenerationStatus.IDLE
            ]
        }
        
        return new_status in valid_transitions.get(self.status, [])


class StateObserver:
    """
    Interfaz para observadores de cambios de estado.
    
    Implementa el patrón Observer para notificar cambios
    sin acoplamiento directo.
    """
    
    def on_state_changed(self, old_state: GenerationState, new_state: GenerationState):
        """
        Callback invocado cuando el estado cambia.
        
        Args:
            old_state: Estado anterior
            new_state: Estado nuevo
        """
        pass


class SocketIOObserver(StateObserver):
    """Observer que emite eventos SocketIO."""
    
    def __init__(self, socketio_instance):
        """
        Inicializa el observer de SocketIO.
        
        Args:
            socketio_instance: Instancia de SocketIO para emitir eventos
        """
        self.socketio = socketio_instance
    
    def on_state_changed(self, old_state: GenerationState, new_state: GenerationState):
        """Emite evento de actualización de estado vía SocketIO."""
        try:
            self.socketio.emit('status_update', new_state.to_dict())
            logger.debug(f"Estado emitido vía SocketIO: {new_state.status.value}")
        except Exception as e:
            logger.error(f"Error emitiendo estado vía SocketIO: {e}")


class LoggingObserver(StateObserver):
    """Observer que registra cambios en logs."""
    
    def on_state_changed(self, old_state: GenerationState, new_state: GenerationState):
        """Registra transición de estado en logs."""
        logger.info(
            f"State transition: {old_state.status.value} -> {new_state.status.value} "
            f"(progress: {new_state.progress}%)"
        )
        if new_state.error:
            logger.error(f"Error en estado: {new_state.error}")


class GenerationStateManager:
    """
    Gestor thread-safe del estado de generación.
    
    Proporciona acceso sincronizado al estado mediante Lock,
    mantiene historial de cambios, y notifica a observers.
    """
    
    def __init__(self, initial_state: Optional[GenerationState] = None):
        """
        Inicializa el gestor de estado.
        
        Args:
            initial_state: Estado inicial (default: IDLE)
        """
        self._state = initial_state or GenerationState()
        self._lock = Lock()
        self._observers: List[StateObserver] = []
        self._history: List[GenerationState] = [self._state]
        logger.info("GenerationStateManager inicializado")
    
    def get_state(self) -> GenerationState:
        """
        Obtiene el estado actual (thread-safe).
        
        Returns:
            GenerationState: Copia del estado actual
        """
        with self._lock:
            return self._state
    
    def update_state(self, **kwargs) -> GenerationState:
        """
        Actualiza el estado y notifica a observers (thread-safe).
        
        Args:
            **kwargs: Campos a actualizar
            
        Returns:
            GenerationState: Nuevo estado
            
        Raises:
            ValueError: Si la transición de estado es inválida
        """
        with self._lock:
            old_state = self._state
            new_state = old_state.update(**kwargs)
            
            # Validar transición si hay cambio de status
            if 'status' in kwargs:
                new_status = kwargs['status']
                if isinstance(new_status, str):
                    new_status = GenerationStatus(new_status)
                if not old_state.can_transition_to(new_status):
                    error_msg = (
                        f"Invalid state transition: "
                        f"{old_state.status.value} -> {new_status.value}"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            self._state = new_state
            self._history.append(new_state)
            
            # Copiar lista de observers para liberar el lock antes de notificar
            observers = self._observers.copy()
        
        # Notificar sin lock para evitar deadlocks
        for observer in observers:
            try:
                observer.on_state_changed(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in observer {observer.__class__.__name__}: {e}")
        
        return new_state
    
    def reset(self) -> GenerationState:
        """
        Resetea el estado a IDLE.
        No valida transiciones para permitir reset desde cualquier estado.
        
        Returns:
            GenerationState: Estado reseteado
        """
        with self._lock:
            old_state = self._state
            
            # Crear nuevo estado IDLE sin validar transición
            new_state = GenerationState(
                status=GenerationStatus.IDLE,
                title='',
                current_step='',
                progress=0,
                chapter_count=0,
                current_chapter=0,
                error=None,
                book_ready=False,
                file_path='',
                output_format='docx'
            )
            
            self._state = new_state
            self._history.append(new_state)
            
            # Notificar a observers fuera del lock
            observers = self._observers.copy()
        
        logger.info(f"Estado reseteado: {old_state.status.value} -> IDLE")
        
        # Notificar sin lock para evitar deadlocks
        for observer in observers:
            try:
                observer.on_state_changed(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in observer {observer.__class__.__name__}: {e}")
        
        return new_state
    
    def add_observer(self, observer: StateObserver):
        """
        Agrega un observer.
        
        Args:
            observer: Observer a agregar
        """
        with self._lock:
            self._observers.append(observer)
            logger.info(f"Observer agregado: {observer.__class__.__name__}")
    
    def remove_observer(self, observer: StateObserver):
        """
        Remueve un observer.
        
        Args:
            observer: Observer a remover
        """
        with self._lock:
            self._observers.remove(observer)
            logger.info(f"Observer removido: {observer.__class__.__name__}")
    
    def get_history(self) -> List[GenerationState]:
        """
        Obtiene el historial de estados.
        
        Returns:
            List[GenerationState]: Copia del historial
        """
        with self._lock:
            return self._history.copy()
    
    def get_current_status(self) -> GenerationStatus:
        """
        Obtiene solo el status actual.
        
        Returns:
            GenerationStatus: Status actual
        """
        with self._lock:
            return self._state.status


# ============================================================
# INSTANCIA GLOBAL DEL STATE MANAGER
# ============================================================

# Crear instancia global del gestor de estado
state_manager = GenerationStateManager()

# Exportar para uso en otros módulos
__all__ = [
    'GenerationStatus',
    'GenerationState',
    'StateObserver',
    'SocketIOObserver',
    'LoggingObserver',
    'GenerationStateManager',
    'state_manager'  # ← Instancia global
]
