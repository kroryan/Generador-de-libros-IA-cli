from dotenv import load_dotenv
import sys
import os

load_dotenv()

def print_step(message):
    print(f"\n=== {message} ===")
    sys.stdout.flush()

def run_cli_generation():
    try:
        from structure import get_structure
        from ideas import get_ideas
        from writing import write_book
        from publishing import DocWriter

        subject = """
        El tema del libro es una aventura épica que combina fantasía y ciencia ficción. 
        La historia se desarrolla en un universo donde la magia compleja coexiste con la tecnología avanzada,
        permitiendo viajes espaciales en naves impulsadas tanto por energía mágica como por tecnología futurista.
        Los personajes exploran mundos misteriosos, enfrentando desafíos que requieren tanto el dominio de
        antiguos hechizos como la comprensión de avanzados sistemas tecnológicos.
        """

        profile = """
        Esta novela fusiona elementos de fantasía épica y ciencia ficción espacial, creando un universo único
        donde la magia ancestral y la tecnología avanzada se entrelazan de formas sorprendentes. La historia
        está dirigida a lectores que disfrutan de mundos complejos donde los límites entre la magia y la ciencia
        se desdibujan. A través de una narrativa inmersiva, la obra explora temas como el poder, la aventura,
        el descubrimiento y la coexistencia de diferentes formas de conocimiento.

        La historia integra sistemas mágicos complejos y detallados con conceptos de ciencia ficción como
        viajes espaciales, civilizaciones alienígenas y tecnología avanzada. Los personajes deben navegar
        por este mundo dual, donde los hechizos más poderosos pueden amplificar las capacidades de las naves
        espaciales, y donde antiguas profecías se entrelazan con descubrimientos científicos.
        """

        style = "Narrativo-Épico-Imaginativo"
        genre = "Fantasía y Ciencia Ficción"

        print_step("Iniciando generación del libro")
        doc_writer = DocWriter()

        print_step("Generando estructura básica")
        title, framework, chapter_dict = get_structure(subject, genre, style, profile)
        print(f"\nTítulo generado: {title}")
        print(f"\nMarco generado. Número de capítulos: {len(chapter_dict)}")

        print_step("Generando ideas para cada capítulo")
        summaries_dict, idea_dict = get_ideas(
            subject, genre, style, profile, title, framework, chapter_dict
        )
        print(f"\nIdeas generadas para {len(idea_dict)} capítulos")

        print_step("Escribiendo el libro")
        book = write_book(genre, style, profile, title, framework, summaries_dict, idea_dict)
        print("\nContenido del libro generado")

        print_step("Guardando el documento final")
        output_path = doc_writer.write_doc(book, chapter_dict, title)
        print("\n¡Libro completado con éxito!")
        print(f"\nPuedes encontrar tu libro en: {output_path}")

    except Exception as e:
        print(f"\nError durante la generación: {str(e)}")
        sys.exit(1)

def run_web_interface():
    # Importar desde el directorio actual, no desde 'src'
    from server import app, socketio

    # Crear directorio para los documentos si no existe
    os.makedirs("docs", exist_ok=True)
    
    print_step("Iniciando la interfaz web")
    print("\nNavega a http://localhost:5000/ para acceder a la interfaz web")
    
    # Iniciar el servidor web usando el modo threading (sin gevent)
    # Eliminamos los parámetros host y port para usar los valores por defecto que son seguros
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generador de libros con LLMs")
    parser.add_argument("--web", action="store_true", help="Iniciar la interfaz web")
    
    args = parser.parse_args()
    
    if args.web:
        run_web_interface()
    else:
        run_cli_generation()
