# CyberNovelist AI

CyberNovelist AI es un generador de libros largos cuyo origen editable es un vault de
Obsidian. Sirve para ficcion, historia, biografia, no ficcion narrativa, ensayo, manuales
tecnicos y otros formatos extensos. Primero crea una biblia canonica y una wiki enlazada, despues escribe y guarda
cada capitulo con su resumen de continuidad y, finalmente, publica DOCX, PDF, Markdown,
HTML o texto desde ese vault. El idioma predeterminado es ingles, pero ingles y espanol
estan soportados durante todo el flujo.

[English documentation](README.md)

## Flujo de generacion

1. Carpeta aislada, titulo y marco narrativo inicial
2. Seis volumenes extensos de biblia canonica
3. Creacion de la estructura de Obsidian
4. Wiki de personajes, lugares, organizaciones, objetos, conceptos y eventos
5. Fusion de nombres y alias en un registro canonico y validacion del graph
6. Esquema de capitulos creado desde la biblia y la wiki terminadas
7. Briefs de capitulos y planes de escenas o secciones expositivas
8. Escritura con resumenes compactos y agente autor con tools reales
9. Guardado inmediato de capitulos y continuidad
10. Publicacion a partir del vault validado

## Estructura del vault

```text
books/<fecha>-<premisa>/
├── 00 - Inicio/
├── 01 - Nucleo de la obra/       portal y seis volumenes de biblia
├── 02 - Historia y continuidad/
├── 03 - Manuscrito/Libros/
│   └── Libro - <titulo>/          planes, capitulos, escenas y resumenes
├── 04 - Personajes/
├── 05 - Mundo/
├── 06 - Organizaciones/
├── 07 - Objetos y conceptos/
├── 08 - Continuidad/
├── 09 - Investigacion/
├── 10 - Escritura y revision/
├── 11 - Wiki de contexto de libros/  referencias comprimidas, nunca manuscritos completos
├── 90 - Plantillas/
├── 99 - Archivos/
├── Exports/
└── .bookgen/
    ├── manifest.json y project.json
    ├── checkpoints/
    └── agent-traces/
```

La IA proporciona los datos de las entidades, pero los enlaces los crea el programa solo
despues de registrar notas reales. Los enlaces inexistentes se convierten en texto normal,
los resolubles se normalizan y el graph se vuelve a validar antes de publicar.

## Instalacion

```bash
git clone https://github.com/kroryan/Generador-de-libros-IA-cli.git
cd Generador-de-libros-IA-cli
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Linea de comandos

```bash
python src/app.py \
  --model ollama:gpt-oss:20b-cloud \
  --language es \
  --output-format obsidian \
  --subject "Una expedicion descubre una ciudad fuera del tiempo" \
  --profile "Fantasia adulta, misterio causal y final cerrado"
```

Formatos: `obsidian`, `md`, `txt`, `html`, `docx` y `pdf`. La exportacion PDF requiere
LibreOffice. Para iniciar la interfaz web:

```bash
python src/app.py --web
```

Abre `http://localhost:5000`. Al cambiar `BOOK LANGUAGE` tambien cambian los ejemplos de
premisa y perfil, estilos, generos, controles y estados. El prompt de control puede estar
en ingles porque obliga a producir todo el contenido visible en el idioma elegido.

La web separa proveedor y modelo. El gestor permite anadir, probar y borrar endpoints
OpenAI-compatible o Anthropic nativos. Las claves quedan solo en
`.bookgen/providers.json`, con permisos `0600`, y nunca vuelven al navegador. Ollama se
consulta mediante `/api/tags`, se excluyen modelos solo de embeddings y se indica cuales
soportan tools nativas.

El selector de boveda descubre proyectos reales dentro del directorio de salida. Sin
seleccion se crea una boveda nueva. Una boveda elegida puede servir como canon para
continuar la historia, crear un segundo libro relacionado o revisar el libro en un proyecto
nuevo. Nunca se sobrescribe implicitamente el original. Mientras hay una generacion activa
aparecen los botones Pausar/Reanudar y Cancelar; al cancelar se conservan los checkpoints.

Al seleccionar un libro fuente, la nueva boveda mantiene separados los dos tipos de datos.
Los manuscritos completos editables permanecen en `03 - Manuscrito/Libros/Libro - <titulo>/`.
La referencia derivada se guarda en `11 - Wiki de contexto de libros/Libro - <titulo fuente>/`
con portal, dossier comprimido, mapa del manuscrito y procedencia. La planificacion reserva
contexto para ese dossier y el agente puede buscarlo como cualquier otra nota; el manuscrito
fuente completo no se duplica dentro de la wiki.

El panel de progreso permite enviar ordenes mientras se construye o edita el proyecto. Las
ordenes se aplican en las siguientes llamadas del modelo y del agente, y quedan registradas
en `.bookgen/guidance.jsonl`. Junto al campo existe una casilla para permitir busquedas
limitadas con DuckDuckGo. Esta desactivada por defecto; al escoger `Historia` la web la marca
automaticamente, aunque el usuario puede volver a desactivarla. Los resultados y sus URL son
pistas de investigacion, no pruebas definitivas, por lo que los hechos importantes deben
corroborarse.

La politica editorial distingue generos. `Historia` exige cronologia factual, procedencia,
interpretaciones rivales y verificacion. `Ficcion historica` puede investigar el periodo real,
pero conserva libertad para inventar personajes, escenas, dialogo y desviaciones deliberadas
sin convertirse en un tratado documental.

Tambien se detectan dos proveedores basados en suscripcion:

- [`Codex CLI (suscripcion de ChatGPT)`](https://help.openai.com/es-419/articles/11369540-uso-de-codex-con-tu-plan-de-chatgpt): ejecuta `codex login` e inicia sesion con ChatGPT.
- [`Claude Code (suscripcion Pro/Max)`](https://docs.anthropic.com/en/docs/claude-code/getting-started): ejecuta `claude`, usa `/login` y elige la suscripcion.

Se usan exclusivamente los modos no interactivos oficiales, sin extraer tokens OAuth. Las
suscripciones de API y las de consumidor siguen siendo sistemas de facturacion distintos.

## Estrategia de contexto

La biblia completa permanece en Obsidian. Cada peticion de prosa recibe solo los apartados
mas relevantes de la biblia, el brief del capitulo, el resumen incremental, la continuidad
del capitulo anterior, el objetivo de escena o seccion actual y la prosa reciente. Esto mejora la coherencia sin
reenviar todo el libro en cada llamada.

Para continuaciones y revisiones, la compresion es adaptativa y jerarquica: respeta limites
de volumen y capitulo, crea varios mapas con pequeno solape para secciones grandes y realiza
una sintesis final que reconcilia todos los mapas. El original completo queda en un
checkpoint oculto que el agente puede consultar bajo demanda.

Las bovedas editables usan `.bookgen/context-index.json` como cache incremental. Cada nota
relevante guarda hash, procedencia y resumen reutilizable. Una edicion normal solo vuelve a
indexar archivos nuevos o modificados y actualiza el dossier mediante un delta; solo se
reconstruye todo si falta la cache o cambia una parte grande de la boveda.

Antes y despues de cada capitulo, el modelo ejecuta un bucle real de observar y actuar:
puede buscar y leer el vault, consultar backlinks y resumenes, validar el graph y actualizar
notas de trabajo, continuidad o entidades mediante escrituras controladas. Ollama usa tools
nativas de `/api/chat`; otros wrappers compatibles usan `bind_tools`; el resto usa ReAct
sobre las mismas herramientas reales. Todas las escrituras reparan y validan el graph y las
trazas quedan en `.bookgen/agent-traces`. Con `--web-search`, el agente tambien puede buscar
en DuckDuckGo y conserva las URL en la traza. `--no-agent-tools` desactiva el bucle.
En revision, el agente tambien puede consultar el manuscrito fuente real y crear o editar
notas canonicas con reemplazo exacto, copia de seguridad, registro de decisiones y validacion
del graph. Esas herramientas canonicas controladas tambien permiten incorporar las ordenes
necesarias durante la construccion de una boveda nueva.

## Carpeta de proyecto

Cada generacion crea una carpeta neutra `pending-book-*` en `books/` antes de llamar al modelo.
En cuanto la IA elige el titulo, la carpeta se renombra atomicamente a partir de ese titulo; el
prompt del usuario nunca se usa como nombre de directorio y las colisiones reciben un sufijo
numerico. Esa carpeta es directamente un vault de Obsidian. Los resultados intermedios se guardan en
`.bookgen/checkpoints/`; los seis volumenes visibles son la unica copia canonica de la
biblia y los portales solo los enlazan. Un fallo posterior no pierde el trabajo completado.
Codex y Claude Code trabajan con esa carpeta como directorio.

## Pruebas

```bash
python -m pytest -q
python -m pyflakes src
```

La comprobacion estatica detecta nombres indefinidos e imports invalidos antes de que una
generacion llegue a un callback incremental.

Consulta [`.env.example`](.env.example) para la
configuracion completa. No guardes claves API en el repositorio.
