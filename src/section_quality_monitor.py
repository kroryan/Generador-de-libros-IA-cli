# src/section_quality_monitor.py

from typing import Optional
from example_library import ExampleLibrary, ExampleSection
from example_quality import ExampleQualityEvaluator
from utils import print_progress
from datetime import datetime

class SectionQualityMonitor:
    """
    Monitorea calidad de secciones generadas y almacena las mejores
    como ejemplos para futuras generaciones.
    """
    
    def __init__(
        self, 
        quality_threshold: float = 0.75,
        auto_save: bool = True
    ):
        """
        Args:
            quality_threshold: Score mínimo (0.0-1.0) para guardar como ejemplo
            auto_save: Si True, guarda automáticamente secciones de alta calidad
        """
        self.quality_threshold = quality_threshold
        self.auto_save = auto_save
        self.example_library = ExampleLibrary()
        self.evaluator = ExampleQualityEvaluator()
        
        # Estadísticas de sesión
        self.sections_evaluated = 0
        self.sections_saved = 0
        self.quality_scores = []
    
    def evaluate_and_store(
        self,
        section_content: str,
        genre: str,
        style: str,
        section_position: str,
        context: str,
        idea: str,
        book_title: str,
        language: str = "es",
    ) -> Optional[float]:
        """
        Evalúa una sección y la almacena si supera el umbral de calidad.
        
        Args:
            section_content: Texto de la sección generada
            genre: Género del libro
            style: Estilo de escritura
            section_position: inicio/medio/final
            context: Contexto previo a la sección
            idea: Idea que desarrolla la sección
            book_title: Título del libro
            
        Returns:
            Score de calidad (0.0-1.0) o None si hubo error
        """
        try:
            # Evaluar calidad
            quality_score = self.evaluator.evaluate(
                section_content=section_content,
                context=context,
                idea=idea
            )
            
            self.sections_evaluated += 1
            self.quality_scores.append(quality_score)
            
            # Guardar si supera umbral
            if quality_score >= self.quality_threshold and self.auto_save:
                example = ExampleSection(
                    genre=genre,
                    style=style,
                    section_type=section_position,
                    content=section_content,
                    context=context[:200] if context else "",  # Limitar contexto a 200 chars
                    idea=idea[:150] if idea else "",           # Limitar idea a 150 chars
                    quality_score=quality_score,
                    created_at=datetime.now().isoformat(),
                    book_title=book_title,
                    language=language,
                )
                
                self.example_library.add_example(example)
                self.sections_saved += 1
                
                print_progress(
                    f"✨ Sección de alta calidad guardada como ejemplo "
                    f"(score={quality_score:.2f})"
                )
            
            return quality_score
            
        except Exception as e:
            print_progress(f"⚠️ Error evaluando calidad de sección: {str(e)}")
            return None
    
    def get_session_stats(self) -> dict:
        """Retorna estadísticas de la sesión actual"""
        avg_quality = (
            sum(self.quality_scores) / len(self.quality_scores)
            if self.quality_scores else 0.0
        )
        
        max_quality = max(self.quality_scores) if self.quality_scores else 0.0
        min_quality = min(self.quality_scores) if self.quality_scores else 0.0
        
        return {
            "sections_evaluated": self.sections_evaluated,
            "sections_saved": self.sections_saved,
            "average_quality": avg_quality,
            "max_quality": max_quality,
            "min_quality": min_quality,
            "save_rate": (
                self.sections_saved / self.sections_evaluated
                if self.sections_evaluated > 0 else 0.0
            )
        }
    
    def force_save_section(
        self,
        section_content: str,
        genre: str,
        style: str,
        section_position: str,
        context: str,
        idea: str,
        book_title: str,
        language: str = "es",
    ) -> bool:
        """
        Fuerza el guardado de una sección independientemente del score.
        Útil para guardar manualmente secciones que el usuario considera buenas.
        """
        try:
            quality_score = self.evaluator.evaluate(
                section_content=section_content,
                context=context,
                idea=idea
            )
            
            example = ExampleSection(
                genre=genre,
                style=style,
                section_type=section_position,
                content=section_content,
                context=context[:200] if context else "",
                idea=idea[:150] if idea else "",
                quality_score=quality_score,
                created_at=datetime.now().isoformat(),
                book_title=book_title,
                language=language,
            )
            
            self.example_library.add_example(example)
            print_progress(f"🔖 Sección guardada manualmente (score={quality_score:.2f})")
            return True
            
        except Exception as e:
            print_progress(f"⚠️ Error guardando sección manualmente: {str(e)}")
            return False
    
    def get_quality_breakdown(self, section_content: str, context: str, idea: str) -> dict:
        """Retorna análisis detallado de calidad de una sección"""
        return self.evaluator.get_quality_breakdown(section_content, context, idea)
    
    def adjust_threshold(self, new_threshold: float):
        """Ajusta el umbral de calidad dinámicamente"""
        if 0.0 <= new_threshold <= 1.0:
            self.quality_threshold = new_threshold
            print_progress(f"🎯 Umbral de calidad ajustado a {new_threshold:.2f}")
        else:
            print_progress(f"⚠️ Umbral inválido: {new_threshold}. Debe estar entre 0.0 y 1.0")
    
    def reset_session_stats(self):
        """Reinicia las estadísticas de la sesión actual"""
        self.sections_evaluated = 0
        self.sections_saved = 0
        self.quality_scores = []
        print_progress("📊 Estadísticas de sesión reiniciadas")
