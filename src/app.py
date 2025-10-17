from dotenv import load_dotenv
import sys
import os

load_dotenv()

def print_step(message):
    print(f"\n=== {message} ===")
    sys.stdout.flush()

def run_cli_generation(model=None):
    try:
        from structure import get_structure
        from ideas import get_ideas
        from writing import write_book
        from publishing import DocWriter
        from utils import update_model_name

        # Configurar el modelo LLM si se especificó uno
        if model:
            print_step(f"Configurando modelo: {model}")
            update_model_name(model)
            # Establecer MODEL_TYPE en el entorno para casos de fallback
            provider = model.split(':')[0] if ':' in model else 'ollama'
            os.environ["MODEL_TYPE"] = provider
            
            # Detectar modelos con contexto limitado
            model_name = model.split(':')[1] if ':' in model else model
            if 'deepseek' in model_name.lower():
                print_step("Detectado modelo Deepseek: configurando modo de contexto limitado")
                os.environ["MODEL_CONTEXT_SIZE"] = "limited"
            elif any(small in model_name.lower() for small in ['7b', '8b', '9b']):
                print_step("Detectado modelo de tamaño pequeño: configurando modo de contexto limitado")
                os.environ["MODEL_CONTEXT_SIZE"] = "limited"
            else:
                os.environ["MODEL_CONTEXT_SIZE"] = "standard"
        else:
            # Utilizar el MODEL_TYPE del .env si existe
            model_type = os.environ.get("MODEL_TYPE", "").strip()
            if model_type:
                print_step(f"Usando tipo de modelo del archivo .env: {model_type}")
            else:
                print_step("No se especificó modelo, se usará el configurado en .env o el predeterminado")

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
        book = write_book(genre, style, profile, title, framework, summaries_dict, idea_dict, chapter_summaries={})
        print("\nContenido del libro generado")

        print_step("Guardando el documento final")
        output_path = doc_writer.write_doc(book, chapter_dict, title)
        print("\n¡Libro completado con éxito!")
        print(f"\nPuedes encontrar tu libro en: {output_path}")

    except Exception as e:
        print(f"\nError durante la generación: {str(e)}")
        sys.exit(1)

def list_available_models():
    """Lista todos los modelos disponibles en los proveedores configurados"""
    from utils import get_available_models
    
    print_step("Modelos disponibles")
    models = get_available_models()
    
    # Agrupar modelos por proveedor
    providers = {}
    for model in models:
        provider = model["provider"]
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(model)
    
    # Mostrar modelos agrupados por proveedor
    for provider, provider_models in providers.items():
        print(f"\n{provider.upper()}:")
        for model in provider_models:
            print(f"  - {model['name']} (usar como: {model['value']})")
    
    print("\nEjemplos de uso:")
    print("  python app.py --model groq:llama3-8b-8192")
    print("  python app.py --model openai:gpt-4o")
    print("  python app.py --model anthropic:claude-3-opus")
    print("  python app.py --model ollama:llama3")

def run_web_interface():
    # Importar desde el directorio actual, no desde 'src'
    from server import app, socketio

    # Crear directorio para los documentos si no existe
    os.makedirs("docs", exist_ok=True)
    
    print_step("Iniciando la interfaz web")
    print("\nNavega a http://localhost:5000/ para acceder a la interfaz web")
    
    # Iniciar el servidor web usando el modo threading (sin gevent)
    # Escuchar en 0.0.0.0:5000 para ser accesible desde Docker
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generador de libros con LLMs")
    parser.add_argument("--web", action="store_true", help="Iniciar la interfaz web")
    parser.add_argument("--model", type=str, help="Modelo a utilizar (ej: groq:llama3-8b-8192, openai:gpt-4)")
    parser.add_argument("--list-models", action="store_true", help="Listar todos los modelos disponibles")
    
    args = parser.parse_args()
    
    if args.list_models:
        list_available_models()
    elif args.web:
        if args.model:
            # Configurar el modelo por defecto antes de iniciar la interfaz web
            from utils import update_model_name
            update_model_name(args.model)
            # Establecer MODEL_TYPE en el entorno
            provider = args.model.split(':')[0] if ':' in args.model else 'ollama'
            os.environ["MODEL_TYPE"] = provider
        run_web_interface()
    else:
        run_cli_generation(args.model)
