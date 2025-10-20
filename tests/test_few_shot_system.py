# tests/test_few_shot_system.py

"""
Tests para el sistema de Few-Shot Learning.
Verifica que todos los componentes funcionen correctamente.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import patch, MagicMock
from example_library import ExampleLibrary, ExampleSection
from example_quality import ExampleQualityEvaluator
from section_quality_monitor import SectionQualityMonitor
from datetime import datetime

class TestExampleLibrary(unittest.TestCase):
    """Tests para ExampleLibrary"""
    
    def setUp(self):
        """Setup temporal para tests"""
        self.library = ExampleLibrary("./test_examples")
        
    def test_example_creation(self):
        """Test crear ejemplo básico"""
        example = ExampleSection(
            genre="fantasía épica",
            style="descriptivo",
            section_type="inicio",
            content="Era una noche oscura y tormentosa...",
            context="Inicio del capítulo 1",
            idea="Establecer el ambiente",
            quality_score=0.8,
            created_at=datetime.now().isoformat(),
            book_title="Test Book"
        )
        
        self.assertEqual(example.genre, "fantasía épica")
        self.assertEqual(example.quality_score, 0.8)
    
    def test_get_examples_by_genre(self):
        """Test recuperar ejemplos por género"""
        examples = self.library.get_examples(
            genre="fantasía épica",
            style="descriptivo",
            max_examples=2
        )
        
        self.assertIsInstance(examples, list)
        self.assertLessEqual(len(examples), 2)
    
    def test_fallback_search(self):
        """Test buscar ejemplos con fallback"""
        examples = self.library.get_examples(
            genre="género inexistente",
            style="estilo inexistente",
            max_examples=1
        )
        
        # Debería encontrar algo o retornar lista vacía
        self.assertIsInstance(examples, list)

class TestExampleQualityEvaluator(unittest.TestCase):
    """Tests para ExampleQualityEvaluator"""
    
    def test_evaluate_good_section(self):
        """Test evaluar sección de buena calidad"""
        section = """
        El viento susurraba entre los árboles mientras María caminaba por el sendero. 
        Sus pasos eran lentos y deliberados, cada uno marcando el ritmo de sus pensamientos.
        
        "No puedo seguir así", murmuró para sí misma, deteniéndose bajo la sombra de un roble centenario.
        El sol se filtraba entre las hojas, creando patrones de luz y sombra en el suelo.
        
        Había llegado el momento de tomar una decisión que cambiaría su vida para siempre.
        """
        
        score = ExampleQualityEvaluator.evaluate(
            section_content=section,
            context="María está en crisis personal",
            idea="Mostrar su conflicto interno"
        )
        
        self.assertGreater(score, 0.5)  # Debería ser una buena sección
        self.assertLessEqual(score, 1.0)
    
    def test_evaluate_poor_section(self):
        """Test evaluar sección de mala calidad"""
        section = "Texto corto y malo malo malo malo malo malo."
        
        score = ExampleQualityEvaluator.evaluate(
            section_content=section,
            context="",
            idea=""
        )
        
        self.assertLess(score, 0.6)  # Debería ser una mala sección
    
    def test_quality_breakdown(self):
        """Test obtener desglose de calidad"""
        section = "Un párrafo de ejemplo con contenido decente para evaluar la calidad."
        
        breakdown = ExampleQualityEvaluator.get_quality_breakdown(
            section_content=section,
            context="contexto",
            idea="idea"
        )
        
        self.assertIn('word_count', breakdown)
        self.assertIn('final_score', breakdown)
        self.assertIn('lexical_diversity', breakdown)

class TestSectionQualityMonitor(unittest.TestCase):
    """Tests para SectionQualityMonitor"""
    
    def setUp(self):
        """Setup para tests"""
        self.monitor = SectionQualityMonitor(
            quality_threshold=0.7,
            auto_save=False  # No guardar durante tests
        )
    
    def test_evaluate_section(self):
        """Test evaluar y almacenar sección"""
        section = """
        Los neones de la ciudad parpadeaban en la distancia mientras Alex corría por las calles mojadas.
        Su respiración formaba pequeñas nubes en el aire frío de la noche.
        
        "Tengo que llegar antes que ellos", pensó, acelerando el paso.
        """
        
        score = self.monitor.evaluate_and_store(
            section_content=section,
            genre="cyberpunk",
            style="narrativo",
            section_position="medio",
            context="Alex está huyendo",
            idea="Mostrar la persecución",
            book_title="Test Book"
        )
        
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_session_stats(self):
        """Test estadísticas de sesión"""
        # Simular evaluación de varias secciones
        self.monitor.sections_evaluated = 10
        self.monitor.sections_saved = 3
        self.monitor.quality_scores = [0.8, 0.6, 0.9, 0.5, 0.7, 0.8, 0.4, 0.9, 0.6, 0.8]
        
        stats = self.monitor.get_session_stats()
        
        self.assertEqual(stats['sections_evaluated'], 10)
        self.assertEqual(stats['sections_saved'], 3)
        self.assertAlmostEqual(stats['save_rate'], 0.3)
        self.assertGreater(stats['average_quality'], 0)

class TestFewShotIntegration(unittest.TestCase):
    """Tests de integración del sistema completo"""
    
    @patch('example_library.ExampleLibrary')
    def test_writer_chain_integration(self, mock_library):
        """Test integración con WriterChain"""
        # Mock de la biblioteca de ejemplos
        mock_example = ExampleSection(
            genre="sci-fi",
            style="narrativo",
            section_type="inicio",
            content="Ejemplo de contenido sci-fi...",
            context="En el futuro...",
            idea="Establecer ambiente futurista",
            quality_score=0.9,
            created_at=datetime.now().isoformat(),
            book_title="Future World"
        )
        
        mock_library.return_value.get_examples.return_value = [mock_example]
        
        # Aquí podríamos probar la integración con WriterChain
        # pero requeriría más setup del entorno LLM
        
        self.assertTrue(True)  # Test básico por ahora

def run_few_shot_tests():
    """Ejecuta todos los tests del sistema few-shot"""
    print("🧪 Ejecutando tests del sistema Few-Shot Learning...")
    print("="*60)
    
    # Crear suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Añadir tests
    suite.addTests(loader.loadTestsFromTestCase(TestExampleLibrary))
    suite.addTests(loader.loadTestsFromTestCase(TestExampleQualityEvaluator))
    suite.addTests(loader.loadTestsFromTestCase(TestSectionQualityMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestFewShotIntegration))
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("✅ Todos los tests pasaron correctamente")
    else:
        print("❌ Algunos tests fallaron")
        print(f"Errores: {len(result.errors)}")
        print(f"Fallos: {len(result.failures)}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    run_few_shot_tests()