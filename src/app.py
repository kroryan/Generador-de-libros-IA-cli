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
        from model_profiles import model_profile_manager, get_model_context_window
        from utils import update_model_name
        
        # FASE 4: Usar configuración centralizada
        from config.defaults import get_config
        config = get_config()
        gen_config = config.generation

        # Configurar el modelo LLM si se especificó uno
        if model:
            print_step(f"Configurando modelo: {model}")
            update_model_name(model)
            # Establecer MODEL_TYPE en el entorno para casos de fallback
            provider = model.split(':')[0] if ':' in model else 'ollama'
            os.environ["MODEL_TYPE"] = provider
            
            # Usar el nuevo sistema de perfiles para detectar configuración del modelo
            model_name = model.split(':')[1] if ':' in model else model
            profile = model_profile_manager.detect_model_profile(model_name, provider)
            
            if profile:
                print_step(f"Perfil detectado: {profile.display_name} ({profile.size_category})")
                
                # NUEVO: Crear calculador dinámico de contexto
                from dynamic_context import DynamicContextCalculator
                
                context_calc = DynamicContextCalculator(model_name, provider)
                context_profile = context_calc.profile
                
                # Actualizar variables de entorno dinámicamente
                os.environ["CONTEXT_LIMITED_SIZE"] = str(context_profile.section_limit)
                os.environ["CONTEXT_STANDARD_SIZE"] = str(context_profile.chapter_limit)
                os.environ["CONTEXT_MAX_ACCUMULATION"] = str(context_profile.accumulation_threshold)
                os.environ["CONTEXT_GLOBAL_LIMIT"] = str(context_profile.global_limit)
                
                print_step(f"🔧 Contexto dinámico configurado:")
                print_step(f"   Ventana del modelo: {context_profile.context_window} tokens")
                print_step(f"   Límite sección: {context_profile.section_limit} chars")
                print_step(f"   Límite capítulo: {context_profile.chapter_limit} chars")
                print_step(f"   Límite global: {context_profile.global_limit} chars")
                print_step(f"   Umbral acumulación: {context_profile.accumulation_threshold} chars")
                
                # Configurar contexto basado en el perfil del modelo (compatibilidad)
                context_window = profile.context_window
                if context_window < 8192 or profile.size_category == "small":
                    print_step("Configurando modo de contexto limitado basado en perfil del modelo")
                    os.environ["MODEL_CONTEXT_SIZE"] = "limited"
                else:
                    os.environ["MODEL_CONTEXT_SIZE"] = "standard"
                    
                # Configurar parámetros optimizados
                optimal_params = profile.get_optimal_parameters()
                for param, value in optimal_params.items():
                    os.environ[f"MODEL_{param.upper()}"] = str(value)
                    
            else:
                # Fallback para modelos no reconocidos
                print_step("Modelo no reconocido en base de datos, usando detección por nombre")
                
                # NUEVO: Crear calculador dinámico incluso sin perfil detectado
                from dynamic_context import DynamicContextCalculator
                
                context_calc = DynamicContextCalculator(model_name, provider)
                context_profile = context_calc.profile
                
                # Actualizar variables de entorno dinámicamente
                os.environ["CONTEXT_LIMITED_SIZE"] = str(context_profile.section_limit)
                os.environ["CONTEXT_STANDARD_SIZE"] = str(context_profile.chapter_limit)
                os.environ["CONTEXT_MAX_ACCUMULATION"] = str(context_profile.accumulation_threshold)
                os.environ["CONTEXT_GLOBAL_LIMIT"] = str(context_profile.global_limit)
                
                print_step(f"🔧 Contexto dinámico estimado:")
                print_step(f"   Ventana estimada: {context_profile.context_window} tokens")
                print_step(f"   Límite sección: {context_profile.section_limit} chars")
                print_step(f"   Límite capítulo: {context_profile.chapter_limit} chars")
                
                # Configuración de compatibilidad
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

        # FASE 4: Usar valores de configuración como defaults
        subject = gen_config.default_subject
        profile = gen_config.default_profile
        style = gen_config.default_style
        genre = gen_config.default_genre

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
