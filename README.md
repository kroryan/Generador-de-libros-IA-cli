# CyberNovelist AI 
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/kroryan/CyberNovelist-AI)

CyberNovelist AI is an Obsidian-first long-form book generator. It builds a canonical
book bible and linked planning wiki before drafting prose, saves every chapter and
continuity summary back into the vault, and publishes reader-facing files from that
vault. It supports fiction, history, biography, narrative nonfiction, essays, technical
books, and other long-form genres. English is the default; English and Spanish books are
fully supported.

[Documentacion en espanol](README.es.md)

## Why Obsidian first?

The editable vault is the source of truth. DOCX, PDF, Markdown, HTML, and plain-text
outputs are derived artifacts. This makes the plan inspectable, reduces context waste,
and prevents later exports from drifting away from the chapter files.

The generation sequence is:

1. Create an isolated project, generate the title, and semantically audit the foundational framework against the exact user request
2. Materialize the visible Obsidian vault with the generated framework, without empty notes
3. Build, audit, repair, and visibly save six substantial canonical bible volumes one by one
4. Extract, audit, and repair characters, locations, organizations, objects, concepts, and events
5. Merge names and aliases into one canonical entity registry and validate every graph link
6. Plan the chapter outline from the completed bible and wiki
7. Generate detailed chapter briefs and ordered scene or expository-section plans
8. Draft chapters with compact savepoints and a tool-using author agent
9. Persist every chapter and continuity summary immediately
10. Publish from the validated vault

## Vault layout

```text
books/<generated-title>/
├── 00 - Start/                 portal, master index, wiki index, project control
├── 01 - Story Core/            bible portal and six canonical volumes
├── 02 - Story and Continuity/  events and story architecture
├── 03 - Manuscript/Books/
│   └── Book - <title>/         chapter index, plans, chapters, scenes, summaries
├── 04 - Characters/
├── 05 - World/
├── 06 - Organizations/
├── 07 - Objects and Concepts/
├── 08 - Continuity/
├── 09 - Research/
├── 10 - Writing and Revision/
├── 11 - Book Context Wiki/     compressed prior-book references, never full manuscripts
├── 90 - Templates/
├── 99 - Archive/
├── Exports/
└── .bookgen/
    ├── manifest.json, project.json, link-repairs.json
    ├── checkpoints/
    └── agent-traces/
```

The model supplies canonical entity data, but application code creates wikilinks only
after registering real notes. Before each export, missing links are converted back to
plain visible text, resolvable links are normalized, and the graph is validated again.
Every bible volume and wiki domain must pass deterministic checks plus an independent LLM
continuity/taxonomy audit. Deterministic scope blockers trigger repair before another audit call,
so obvious failures do not waste context on a contradictory verdict. Failed candidates are saved in `.bookgen/checkpoints/`, repaired up
to the configured limit, and never become canon while critical issues remain.
High-confidence checks also reject wrong-language labels, policy-negating instructions, misplaced
encyclopedia material, unsupported precision, and ambiguous relationship claims observed during
live generation audits.

## Installation

Python 3.11 is recommended.

```bash
git clone https://github.com/kroryan/CyberNovelist-AI.git
cd CyberNovelist-AI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure at least one provider in `.env`. Ollama can run without an API key when its
local server is available.

## CLI

Generate an English DOCX with the configured default model:

```bash
python src/app.py --language en --output-format docx
```

Generate a Spanish Obsidian vault archive with a selected model:

```bash
python src/app.py \
  --model ollama:gpt-oss:20b-cloud \
  --language es \
  --output-format obsidian \
  --subject "Una expedicion descubre una ciudad fuera del tiempo" \
  --profile "Fantasia adulta, misterio causal y final cerrado"
```

Useful options:

```text
--web
--list-models
--model PROVIDER:MODEL
--language {en,es}
--output-format {obsidian,md,txt,html,docx,pdf}
--output-path DIRECTORY
--subject TEXT
--profile TEXT
--style TEXT
--genre TEXT
--source-vault DIRECTORY
--source-book BOOK_ID
--vault-mode {new,continue,related,revise}
--web-search
--no-agent-tools
```

PDF publication requires `libreoffice` or `soffice` in `PATH`.

## Web interface

```bash
python src/app.py --web
```

Open `http://localhost:5000`. The UI defaults to English and includes an explicit book
language selector for English and Spanish. Changing it also localizes the premise/profile
examples, styles, genres, controls, and status text. The choice is persisted in the browser,
restored into both the visible control and generation payload, and never inferred from stale
visual form state. Only one generation runs at a time.

The progress history is a bounded, four-column activity table with its own scroll. Long model
responses are collapsed per event and can be expanded in place; wrapped text remains inside the
message column, and new events do not force the view to the bottom while the user is reading older rows.

The provider and model selectors are independent. The provider manager can add, test, and
remove OpenAI-compatible or native Anthropic API endpoints. API keys are stored locally in
`.bookgen/providers.json` with `0600` permissions and are never returned to the browser.
Ollama models are discovered from `/api/tags`; embedding-only models are excluded and native
tool support is shown next to the model.

The source-vault selector discovers BookGen vaults under the output directory. With no
selection, generation creates a new independent vault. A selected vault can provide canon
for a continuation, a related second book, or a revision. All three create a separate
project, so an existing manuscript is never overwritten implicitly. Pause/resume and cancel
controls appear under the Generate button while work is active; cancellation retains every
completed checkpoint.

When a source book is selected, the new vault keeps the two kinds of book data separate.
Complete editable manuscripts stay under `03 - Manuscript/Books/Book - <title>/`. A derived
reference is written under `11 - Book Context Wiki/Book - <source title>/` with its own
portal, compressed dossier, manuscript map, and provenance. Planning reserves context for
this dossier, and the agent can search it like any other vault note; the full source
manuscript is not duplicated into the wiki.

The progress panel also accepts live instructions while a project is being built or edited.
Instructions are injected into subsequent model and agent calls and persisted in
`.bookgen/guidance.jsonl`. A nearby checkbox enables bounded DuckDuckGo web search for the
author agent. Web access is off by default, except that selecting `History` in the UI checks
it automatically; the user can still turn it off. Search results are source leads with URLs,
not proof by themselves, so consequential historical claims must be corroborated.

Genre policy is explicit. `History` uses factual chronology, provenance, competing
interpretations, and verification requirements. `Historical fiction` may research its real
setting but retains freedom to invent characters, scenes, dialogue, and deliberate departures
without turning the manuscript into documentary exposition.

Two subscription-backed adapters are detected automatically:

- [`Codex CLI (ChatGPT subscription)`](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan): run `codex login` and choose ChatGPT sign-in.
- [`Claude Code (Pro/Max subscription)`](https://docs.anthropic.com/en/docs/claude-code/getting-started): run `claude`, then `/login` and select the Claude subscription.

They invoke the vendors' official non-interactive CLIs and never extract OAuth credentials.
CLI calls are intentionally tool-restricted; the author agent uses its own audited vault
tools through ReAct. API subscriptions/billing remain separate from consumer subscriptions.

## Docker

```bash
docker compose up --build
```

The service listens on port `5000`, reads `.env` as a mounted file, and writes vaults and
published output inside its isolated project under `books/`.

## Project workspace

Every generation creates a neutral `pending-book-*` project directory before the first model
call. As soon as the AI chooses the title, that directory is atomically renamed from the title;
the user prompt is never used as a directory name, and collisions receive a numeric suffix. The
directory itself is an Obsidian vault and contains all durable work for that book:

```text
books/<timestamp>-<premise>/
  Project Dashboard.md
  Work/                 original request only
  00 - Start/ ... 99 - Archive/   canonical Obsidian vault
  Exports/              DOCX, PDF, Markdown, HTML, TXT, or vault ZIP
  .bookgen/              manifests, hidden checkpoints, graph repairs, and agent traces
```

Each model result is checkpointed immediately under `.bookgen/checkpoints/`. The visible vault
exists as soon as the framework is ready, initially containing the actual generated framework rather
than empty wiki/control notes. Every accepted bible volume is written at once to
`01 - Story Core/`; users can inspect partial canonical work before the remaining volumes finish.
Appending a later volume does not rewrite an existing volume note, so direct user edits remain intact.
Wiki category indexes and manuscript indexes are created only when their first real entity or plan
exists; ungenerated sections remain absent instead of appearing as empty files.
Bible text exists once in its six canonical volume notes; portals and indices link to it rather
than copying it. A later provider or server failure therefore does not discard completed work.
Codex and Claude Code are launched with this project as their working directory.

## Context strategy

The full bible remains available in the vault. Each prose request receives a compact,
relevance-ranked bible excerpt, the current chapter brief or savepoint, the previous
chapter continuity state, the current scene or section objective, and only recent prose. This preserves
canonical facts without repeatedly spending the entire context window.

For continuation and revision, source compression is adaptive and hierarchical. Markdown
volumes and chapter boundaries are packed into bounded maps, oversized sections receive a
small overlap, every source section is covered, and a final synthesis reconciles the maps.
The complete selected source remains in a hidden checkpoint and is retrievable on demand by
the author agent, so compression is not the only access path.

Editable vaults use `.bookgen/context-index.json` as an incremental cache. Each relevant
Markdown file has a content hash, provenance, and reusable summary. Normal edits only
re-index changed/new files and patch the canonical dossier; deleted files are removed. A
full rebuild occurs only when the cache is absent or a large share of the vault changed.

Before and after each chapter, the model runs as a bounded author agent with a real
observe-and-act loop. It can search and read the vault, inspect backlinks and summaries,
validate the graph, maintain agent notes, and append verified continuity or entity updates.
When enabled, it can also search DuckDuckGo and retains source URLs in its audited trace.
Ollama uses native `/api/chat` tool calls; compatible hosted/local wrappers use native
`bind_tools`; other models use a ReAct fallback over the same real tools. Every write passes
through graph repair and validation, and traces are stored in `.bookgen/agent-traces`.
Use `--no-agent-tools` when minimizing model calls matters more than autonomous retrieval.
Revision mode additionally exposes read-only source-manuscript retrieval plus guarded
canonical note creation/editing with exact-match patches, backups, a revision ledger, and
graph validation. The same guarded canonical tools can incorporate necessary live guidance
during new-world construction without granting unrestricted filesystem writes.

Configuration options and provider variables are documented in [`.env.example`](.env.example).

## Tests

```bash
python -m pytest -q
python -m pyflakes src
```

The static check catches undefined names and invalid imports before a generation reaches
an incremental callback. The graph/storage tests can also run directly:

```bash
python tests/test_obsidian_pipeline.py
```

## Supported providers

- Ollama with live model/capability discovery
- OpenAI and OpenAI-compatible APIs
- Native Anthropic Messages API
- Groq and DeepSeek through their OpenAI-compatible endpoints
- Codex CLI authenticated with ChatGPT
- Claude Code authenticated with Claude Pro/Max
- Web-created custom providers and providers declared through environment variables

Never commit API keys. Keep secrets in `.env` or the ignored `.bookgen/providers.json`.
