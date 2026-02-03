#!/usr/bin/env python3
"""
Test para verificar que el buffer de palabras funciona correctamente
y evita la fragmentación de tokens en el streaming.
"""

import os
import sys
import time

# Añadir src al path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from streaming_cleaner import StreamingCleaner, OutputCapture


class TestBuffer:
    """Clase para capturar y analizar el output de streaming."""
    
    def __init__(self):
        self.normal_outputs = []
        self.think_outputs = []
        self.timestamps = []
    
    def on_normal_output(self, text: str):
        """Callback para output normal."""
        self.normal_outputs.append(text)
        self.timestamps.append(time.time())
        print(f"[NORMAL] '{text}'")
    
    def on_think_output(self, text: str, think_type: str):
        """Callback para output de pensamiento."""
        self.think_outputs.append((text, think_type))
        self.timestamps.append(time.time())
        print(f"[THINK-{think_type.upper()}] '{text}'")


def test_word_fragmentation():
    """
    Test principal: simula tokens fragmentados y verifica
    que se envían como palabras completas.
    """
    print("=== TEST: Buffer de Palabras Completas ===")
    print("Simulando tokens fragmentados de LLM...\n")
    
    # Crear el buffer de prueba
    test_buffer = TestBuffer()
    cleaner = StreamingCleaner(
        on_normal_output=test_buffer.on_normal_output,
        on_think_output=test_buffer.on_think_output,
        buffer_threshold=50
    )
    
    # Simular tokens fragmentados como los generaría un LLM
    fragmented_tokens = [
        "El", " artefac", "to", " de", " piedra",
        " respland", "ecía", " bajo", " la", " luz",
        " del", " Crist", "al", " Eter", "no."
    ]
    
    print("Tokens fragmentados simulados:")
    for i, token in enumerate(fragmented_tokens):
        print(f"{i+1:2d}: '{token}'")
    print()
    
    # Procesar tokens uno por uno
    print("Procesando tokens...")
    for token in fragmented_tokens:
        cleaner.process_chunk(token)
        time.sleep(0.01)  # Simular latencia
    
    # Flush final
    cleaner.flush()
    
    print("\n=== RESULTADOS ===")
    print(f"Total de outputs normales: {len(test_buffer.normal_outputs)}")
    
    # Verificar que las palabras no están fragmentadas
    fragmented_words = []
    
    # Palabras válidas cortas en español
    valid_short_words = {
        'a', 'y', 'o', 'u', 'e', 'ni',
        'el', 'la', 'de', 'un', 'en', 'es', 'al', 'se', 'le', 'te',
        'me', 'lo', 'ya', 'si', 'no', 'su', 'tu', 'mi', 'yo', 'he',
        'ha', 'ir', 'va', 've', 'da', 'di', 'do', 'fe', 'pi', 'ti',
        'ay', 'ah', 'eh', 'oh'
    }
    
    for output in test_buffer.normal_outputs:
        words = output.split()
        for word in words:
            # Limpiar puntuación para la verificación
            clean_word = word.strip('.,;:!WARN"\'()[]{}').lower()
            
            # Verificar si es un fragmento obvio
            # (palabra muy corta que no está en la lista de palabras válidas)
            if (len(clean_word) < 3 and clean_word.isalpha() and 
                clean_word not in valid_short_words):
                fragmented_words.append(word)
    
    print(f"Palabras fragmentadas detectadas: {len(fragmented_words)}")
    if fragmented_words:
        print(f"Fragmentos: {fragmented_words}")
        print("FAIL: Se detectaron fragmentos de palabras")
    else:
        print("OK: No se detectaron fragmentos de palabras")
    
    return len(fragmented_words) == 0


def test_think_blocks():
    """Test para verificar que los bloques de pensamiento funcionan con buffer."""
    print("\n=== TEST: Bloques de Pensamiento con Buffer ===")
    
    test_buffer = TestBuffer()
    cleaner = StreamingCleaner(
        on_normal_output=test_buffer.on_normal_output,
        on_think_output=test_buffer.on_think_output,
        buffer_threshold=50
    )
    
    # Simular texto con bloques de pensamiento fragmentados
    tokens_with_think = [
        "El", " protagon", "ista", " camin", "aba",
        " <think>", "Neces", "ito", " describ", "ir",
        " mejor", " el", " ambient", "e</think>",
        " por", " las", " call", "es", " oscur", "as."
    ]
    
    for token in tokens_with_think:
        cleaner.process_chunk(token)
        time.sleep(0.01)
    
    cleaner.flush()
    
    print(f"Outputs normales: {len(test_buffer.normal_outputs)}")
    print(f"Outputs de pensamiento: {len(test_buffer.think_outputs)}")
    
    # Verificar que hay al menos un output de cada tipo
    success = (len(test_buffer.normal_outputs) > 0 and 
               len(test_buffer.think_outputs) > 0)
    
    if success:
        print("OK: Bloques de pensamiento procesados correctamente")
    else:
        print("FAIL: Problemas procesando bloques de pensamiento")
    
    return success


def test_configuration():
    """Test para verificar que la configuración desde .env funciona."""
    print("\n=== TEST: Configuración desde Variables de Entorno ===")
    
    # Configurar variables de entorno temporalmente
    os.environ['STREAMING_WORD_BUFFER_SIZE'] = '100'
    os.environ['STREAMING_WORD_DELIMITERS'] = ' .!?'
    
    test_buffer = TestBuffer()
    cleaner = StreamingCleaner(
        on_normal_output=test_buffer.on_normal_output,
        buffer_threshold=50
    )
    
    # Verificar configuración
    expected_size = 100
    expected_delimiters = [' ', '.', '!', '?']
    
    print(f"Buffer size configurado: {cleaner.word_buffer_size}")
    print(f"Delimitadores configurados: {cleaner.word_delimiters}")
    
    size_ok = cleaner.word_buffer_size == expected_size
    delims_ok = cleaner.word_delimiters == expected_delimiters
    
    if size_ok and delims_ok:
        print("OK: EXITOSO: Configuración desde .env funciona")
        success = True
    else:
        print("FAIL: FALLIDO: Problemas con configuración desde .env")
        success = False
    
    # Limpiar variables de entorno
    del os.environ['STREAMING_WORD_BUFFER_SIZE']
    del os.environ['STREAMING_WORD_DELIMITERS']
    
    return success


def main():
    """Ejecutar todos los tests."""
    print("Iniciando tests del sistema de buffer de palabras...\n")
    
    tests = [
        ("Fragmentación de Palabras", test_word_fragmentation),
        ("Bloques de Pensamiento", test_think_blocks),
        ("Configuración", test_configuration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen final
    print("\n" + "="*50)
    print("RESUMEN DE TESTS")
    print("="*50)
    
    passed = 0
    for test_name, success in results:
        status = "OK" if success else "FAIL"
        print(f"{test_name:<25} {status}")
        if success:
            passed += 1
    
    print(f"\nTests pasados: {passed}/{len(results)}")
    
    if passed == len(results):
        print(" ¡Todos los tests pasaron! El sistema de buffer está funcionando correctamente.")
        return 0
    else:
        print("WARN  Algunos tests fallaron. Revisar la implementación.")
        return 1


if __name__ == "__main__":
    exit(main())
