"""Obsidian-compatible canonical vault and manuscript storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

from chapter_ordering import sort_chapters_intelligently


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    return re.sub(r"[-\s]+", "-", value) or "untitled-book"


def _yaml_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "-", value).strip().strip(".")
    return cleaned[:100] or "Untitled"


def _entity_key(value: str) -> str:
    return re.sub(r"[^\w]+", "", str(value), flags=re.UNICODE).casefold()


def _extract_section(markdown: str, heading: str) -> str:
    pattern = rf"(?ms)^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown)
    return match.group(1).strip() if match else ""


def _labels(language: str) -> dict[str, str]:
    if language == "es":
        return {
            "start": "00 - Inicio", "core": "01 - Nucleo de la obra",
            "story": "02 - Historia y continuidad", "manuscript": "03 - Manuscrito",
            "characters": "04 - Personajes", "world": "05 - Mundo",
            "organizations": "06 - Organizaciones", "objects": "07 - Objetos y conceptos",
            "continuity": "08 - Continuidad", "research": "09 - Investigacion",
            "writing": "10 - Escritura y revision", "source_books": "11 - Wiki de contexto de libros",
            "templates": "90 - Plantillas",
            "archive": "99 - Archivos", "portal": "00 - Portal del libro",
            "master_index": "02 - Indice maestro", "bible": "Biblia del libro",
            "wiki": "Indice de la wiki", "outline": "Indice de capitulos",
            "status": "Estado del proyecto", "questions": "Preguntas abiertas",
            "continuity_index": "Centro de continuidad", "style": "Guia de escritura",
            "plans": "Planes", "chapters": "Capitulos", "scenes": "Escenas",
            "summaries": "Resumenes", "agent_notes": "Notas del agente",
            "books": "Libros", "book_prefix": "Libro",
        }
    return {
        "start": "00 - Start", "core": "01 - Story Core",
        "story": "02 - Story and Continuity", "manuscript": "03 - Manuscript",
        "characters": "04 - Characters", "world": "05 - World",
        "organizations": "06 - Organizations", "objects": "07 - Objects and Concepts",
        "continuity": "08 - Continuity", "research": "09 - Research",
        "writing": "10 - Writing and Revision", "source_books": "11 - Book Context Wiki",
        "templates": "90 - Templates",
        "archive": "99 - Archive", "portal": "00 - Book Portal",
        "master_index": "02 - Master Index", "bible": "Book Bible",
        "wiki": "Wiki Index", "outline": "Chapter Index", "status": "Project Status",
        "questions": "Open Questions", "continuity_index": "Continuity Hub",
        "style": "Writing Guide", "plans": "Plans", "chapters": "Chapters",
        "scenes": "Scenes", "summaries": "Summaries", "agent_notes": "Agent Notes",
        "books": "Books", "book_prefix": "Book",
    }


def _terms(language: str) -> dict[str, str]:
    if language == "es":
        return {
            "bible": "Biblia", "wiki": "Wiki", "summary": "Resumen", "related": "Relacionado",
            "none": "Ninguno registrado.", "chapter_brief": "Brief del capitulo",
            "section_plan": "Plan de secciones", "entities": "Entidades canonicas",
            "continuity_notes": "Notas de continuidad", "review": "Revisar despues de escribir.",
            "outline_description": "Descripcion del esquema", "outline": "Indice", "plan": "Plan",
            "chapter": "Capitulo", "book_bible": "Biblia del libro", "books": "Libros",
            "active_chapters": "Capitulos activos", "project_status": "Estado del proyecto",
            "questions": "Preguntas abiertas", "continuity": "Continuidad",
            "canonical_bible": "Biblia canonica", "world_wiki": "Wiki del libro",
            "manuscript": "Estructura del manuscrito", "writing_guide": "Guia de escritura",
            "previous_book": "Contexto del libro anterior",
        }
    return {
        "bible": "Bible", "wiki": "Wiki", "summary": "Summary", "related": "Related",
        "none": "None recorded.", "chapter_brief": "Chapter brief", "section_plan": "Section plan",
        "entities": "Canonical entities", "continuity_notes": "Continuity notes",
        "review": "Review after drafting.", "outline_description": "Outline description",
        "outline": "Outline", "plan": "Plan", "chapter": "Chapter", "book_bible": "Book Bible",
        "books": "Books", "active_chapters": "Active Chapters", "project_status": "Project Status",
        "questions": "Open Questions", "continuity": "Continuity", "canonical_bible": "Canonical Bible",
        "world_wiki": "Book Wiki", "manuscript": "Manuscript Structure", "writing_guide": "Writing Guide",
        "previous_book": "Previous Book Context",
    }


VOLUME_NAMES = {
    "en": ("Creative and Editorial Foundation", "People Actors and Relationships", "World and Domain Encyclopedia",
           "Content and Story Architecture", "Organizations Objects and Concepts", "Continuity Research and Writing Control"),
    "es": ("Fundamentos creativos y editoriales", "Personas actores y relaciones", "Enciclopedia del mundo y del tema",
           "Arquitectura del contenido y la historia", "Organizaciones objetos y conceptos", "Continuidad investigacion y control de escritura"),
}


def _split_bible(book_bible: str) -> list[str]:
    parts = re.split(r"(?m)^# Volume \d+: .*?\s*$", str(book_bible))
    volumes = [part.strip() for part in parts[1:] if part.strip()]
    if volumes:
        return volumes
    return [str(book_bible).strip()]


def _balanced_excerpt(parts: list[str], limit: int) -> str:
    if not parts:
        return ""
    if sum(len(part) for part in parts) <= limit:
        return "\n\n".join(parts)
    allowance = max(500, limit // len(parts))
    return "\n\n".join(part[:allowance] for part in parts)


@dataclass(frozen=True)
class VaultProject:
    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / ".bookgen" / "manifest.json"

    def read_manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.manifest_path)

    def read_bible(self) -> str:
        manifest = self.read_manifest()
        paths = manifest.get("book_bible_volumes") or [manifest["book_bible"]]
        return "\n\n".join((self.root / path).read_text(encoding="utf-8") for path in paths)

    def planning_context(self, max_chars: int = 60000) -> str:
        manifest = self.read_manifest()
        entities = []
        for entity in manifest.get("entities", []):
            aliases = ", ".join(entity.get("aliases", []))
            entities.append(
                f"## {entity['name']} ({entity['category']})\n"
                f"Aliases: {aliases or 'none'}\n{entity.get('summary', '')}"
            )
        manifest = self.read_manifest()
        bible_parts = [
            (self.root / path).read_text(encoding="utf-8")
            for path in manifest.get("book_bible_volumes", [])
        ] or [self.read_bible()]
        source_path = str(manifest.get("source_context_path", ""))
        source_file = self.root / f"{source_path}.md" if source_path else None
        if source_file and source_file.is_file():
            bible = _balanced_excerpt(bible_parts, int(max_chars * 0.60))
            registry = _balanced_excerpt(entities, int(max_chars * 0.20))
            source = source_file.read_text(encoding="utf-8")[:int(max_chars * 0.20)]
            return (
                bible + "\n\n# Canonical entity registry\n\n" + registry
                + "\n\n# Previous-book context\n\n" + source
            )
        bible = _balanced_excerpt(bible_parts, int(max_chars * 0.75))
        registry = _balanced_excerpt(entities, int(max_chars * 0.25))
        return bible + "\n\n# Canonical entity registry\n\n" + registry

    def write_source_book_context(
        self, title: str, dossier: str, source_vault: str, source_book_id: str,
        mode: str, chapters: list[dict] | None = None,
    ) -> None:
        """Store a compressed prior-book reference outside the full-manuscript tree."""
        manifest = self.read_manifest()
        root = manifest["paths"]["source_books"]
        prefix = "Libro" if manifest["language"] == "es" else "Book"
        folder = f"{root}/{prefix} - {_safe_filename(title)}"
        portal = f"{folder}/00 - {'Portal del libro fuente' if manifest['language'] == 'es' else 'Source Book Portal'}"
        context = f"{folder}/01 - {'Contexto comprimido' if manifest['language'] == 'es' else 'Compressed Context'}"
        chapter_map = f"{folder}/02 - {'Mapa del manuscrito' if manifest['language'] == 'es' else 'Manuscript Map'}"
        provenance = f"{folder}/03 - {'Procedencia' if manifest['language'] == 'es' else 'Provenance'}"
        (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / f"{portal}.md").write_text(
            f"# {title}\n\n"
            f"- [[{context}|{'Contexto comprimido' if manifest['language'] == 'es' else 'Compressed context'}]]\n"
            f"- [[{chapter_map}|{'Mapa del manuscrito' if manifest['language'] == 'es' else 'Manuscript map'}]]\n"
            f"- [[{provenance}|{'Procedencia' if manifest['language'] == 'es' else 'Provenance'}]]\n",
            encoding="utf-8",
        )
        reference_notice = (
            "> Esta nota es contexto derivado. El manuscrito completo editable permanece en su boveda de origen."
            if manifest["language"] == "es" else
            "> This note is a derived context reference. The full editable manuscript remains in its source vault."
        )
        (self.root / f"{context}.md").write_text(
            "---\ntype: source-book-context\nstatus: derived-reference\n---\n\n"
            f"# {title} - {'Contexto comprimido' if manifest['language'] == 'es' else 'Compressed Context'}\n\n"
            f"{reference_notice}\n\n"
            + str(dossier).strip() + "\n",
            encoding="utf-8",
        )
        records = sorted(chapters or [], key=lambda item: item.get("order", 0))
        lines = [f"# {title} - {'Mapa del manuscrito' if manifest['language'] == 'es' else 'Manuscript Map'}", ""]
        for item in records:
            lines.append(
                f"- {item.get('order', '?')}. {item.get('name', 'Untitled')} "
                f"[{item.get('status', 'unknown')}] - {item.get('description', '')}"
            )
        if not records:
            lines.append(
                "- No habia registros de capitulos en el manifiesto de origen."
                if manifest["language"] == "es" else
                "- No chapter records were available in the source manifest."
            )
        (self.root / f"{chapter_map}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        provenance_labels = (
            ("Boveda de origen", "ID del libro fuente", "Modo de trabajo", "Material: solo contexto comprimido; no es un duplicado del manuscrito.")
            if manifest["language"] == "es" else
            ("Source vault", "Source book ID", "Workflow mode", "Material: compressed context only; not a manuscript duplicate.")
        )
        (self.root / f"{provenance}.md").write_text(
            "---\ntype: source-provenance\n---\n\n"
            f"# {'Procedencia' if manifest['language'] == 'es' else 'Provenance'}\n\n"
            f"- {provenance_labels[0]}: `{source_vault}`\n- {provenance_labels[1]}: `{source_book_id}`\n"
            f"- {provenance_labels[2]}: `{mode}`\n- {provenance_labels[3]}\n",
            encoding="utf-8",
        )
        manifest["source_context_path"] = context
        manifest.setdefault("source_books", []).append({
            "id": source_book_id, "title": title, "path": folder, "portal": portal,
            "context": context, "source_vault": source_vault,
        })
        self.write_manifest(manifest)
        self._refresh_portals()
        self.refresh_entity_indexes()

    def manuscript_context(self, book_id: str = "", max_chars: int = 30000) -> str:
        """Return balanced plans, summaries, and prose for one selected manuscript."""
        manifest = self.read_manifest()
        books = manifest.get("books", [])
        selected = next((item for item in books if item.get("id") == book_id), None)
        if selected is None and books:
            selected = books[0]
        chapters = selected.get("chapters", []) if selected else manifest.get("chapters", [])
        parts = []
        for entry in sorted(chapters, key=lambda item: item.get("order", 0)):
            chapter_parts = [f"# {entry.get('name', 'Chapter')}"]
            for key in ("plan_path", "summary_path", "draft_path"):
                path = self.root / str(entry.get(key, ""))
                if path.is_file():
                    chapter_parts.append(path.read_text(encoding="utf-8"))
            parts.append("\n\n".join(chapter_parts))
        return _balanced_excerpt(parts, max_chars)

    def load_generation_inputs(self) -> tuple[str, dict[str, str], dict[str, list[str]]]:
        manifest = self.read_manifest()
        terms = _terms(manifest.get("language", "en"))
        summaries: dict[str, str] = {}
        ideas: dict[str, list[str]] = {}
        for chapter in manifest.get("chapters", []):
            text = (self.root / chapter["plan_path"]).read_text(encoding="utf-8")
            summaries[chapter["name"]] = (
                _extract_section(text, terms["chapter_brief"]) or _extract_section(text, "Chapter brief")
            )
            scene_plan = (
                _extract_section(text, terms["section_plan"])
                or _extract_section(text, "Section plan") or _extract_section(text, "Scene plan")
            )
            ideas[chapter["name"]] = [
                re.sub(r"^[-*+]\s+", "", line).strip()
                for line in scene_plan.splitlines() if re.match(r"^\s*[-*+]\s+\S", line)
            ]
        return self.read_bible(), summaries, ideas

    def write_wiki(self, wiki_data: dict) -> None:
        manifest = self.read_manifest()
        terms = _terms(manifest.get("language", "en"))
        paths = manifest["paths"]
        category_folders = {
            "characters": paths["characters"], "locations": paths["world"],
            "organizations": paths["organizations"], "objects": paths["objects"],
            "concepts": paths["objects"], "events": paths["story"],
        }
        entities: list[dict] = []
        aliases: dict[str, dict] = {}
        used_targets: set[str] = set()
        for category, folder in category_folders.items():
            for raw in wiki_data.get(category, []):
                name = str(raw.get("name", "")).strip()
                if not name:
                    continue
                keys = [_entity_key(name), *[_entity_key(value) for value in raw.get("aliases", [])]]
                duplicate = next((aliases[key] for key in keys if key and key in aliases), None)
                if duplicate:
                    duplicate["aliases"] = list(dict.fromkeys([
                        *duplicate.get("aliases", []), name, *raw.get("aliases", [])
                    ]))
                    duplicate["relationships"] = list(dict.fromkeys([
                        *duplicate.get("relationships", []), *raw.get("relationships", [])
                    ]))
                    details = str(raw.get("details", "")).strip()
                    if details and details not in duplicate.get("details", ""):
                        duplicate["details"] = (duplicate.get("details", "").rstrip() + "\n\n" + details).strip()
                    for value in [name, *raw.get("aliases", [])]:
                        if _entity_key(value):
                            aliases[_entity_key(value)] = duplicate
                    continue
                filename = _safe_filename(name)
                target = f"{folder}/{filename}"
                if target.casefold() in used_targets:
                    target = f"{folder}/{filename} - {category.rstrip('s').title()}"
                used_targets.add(target.casefold())
                entity = {
                    "name": name, "aliases": list(dict.fromkeys(raw.get("aliases", []))),
                    "category": category, "subtype": str(raw.get("subtype", "")),
                    "summary": str(raw.get("summary", "")).strip(),
                    "details": str(raw.get("details", "")).strip(),
                    "relationships": list(dict.fromkeys(raw.get("relationships", []))), "path": target,
                }
                entities.append(entity)
                for key in keys:
                    if key:
                        aliases[key] = entity

        for entity in entities:
            related = []
            for value in entity["relationships"]:
                target = aliases.get(_entity_key(value))
                if target and target is not entity:
                    related.append(target)
            details = self._link_registered_names(entity["details"], entity, entities)
            unique_related = {item["path"]: item for item in related}.values()
            relation_lines = "\n".join(
                f"- [[{item['path']}|{item['name']}]]" for item in unique_related
            ) or f"- {terms['none']}"
            alias_yaml = json.dumps(entity["aliases"], ensure_ascii=False)
            note = (
                "---\ntype: wiki-entity\n"
                f"category: {_yaml_string(entity['category'])}\nsubtype: {_yaml_string(entity['subtype'])}\n"
                f"aliases: {alias_yaml}\nstatus: canonical\n---\n\n# {entity['name']}\n\n"
                f"[[{manifest['wiki_index']}|{terms['wiki']}]] | [[{manifest['book_bible']}|{terms['bible']}]]\n\n"
                f"## {terms['summary']}\n\n{entity['summary']}\n\n{details}\n\n## {terms['related']}\n\n{relation_lines}\n"
            )
            path = self.root / f"{entity['path']}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(note, encoding="utf-8")

        grouped: dict[str, list[dict]] = {key: [] for key in category_folders}
        for entity in entities:
            grouped[entity["category"]].append(entity)
        index_targets = []
        for category, folder in category_folders.items():
            category_labels = {
                "characters": "Personajes" if manifest["language"] == "es" else "People and Characters",
                "locations": "Lugares" if manifest["language"] == "es" else "Locations",
                "organizations": "Organizaciones" if manifest["language"] == "es" else "Organizations",
                "objects": "Objetos" if manifest["language"] == "es" else "Objects",
                "concepts": "Conceptos" if manifest["language"] == "es" else "Concepts",
                "events": "Eventos" if manifest["language"] == "es" else "Events",
            }
            label = category_labels[category]
            index_path = f"{folder}/Index - {label}"
            if index_path in index_targets:
                continue
            index_targets.append(index_path)
            category_entities = [item for item in entities if item["path"].startswith(folder + "/")]
            lines = [f"# {label}", "", f"[[{manifest['wiki_index']}|{terms['wiki']}]]", ""]
            lines.extend(f"- [[{item['path']}|{item['name']}]] - {item['summary']}" for item in category_entities)
            (self.root / f"{index_path}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

        wiki_lines = [f"# {Path(manifest['wiki_index']).stem}", "", f"[[{manifest['book_bible']}|{terms['bible']}]]", ""]
        for index_path in index_targets:
            wiki_lines.append(f"- [[{index_path}|{Path(index_path).name.removeprefix('Index - ')}]]")
        for source_book in manifest.get("source_books", []):
            wiki_lines.append(f"- [[{source_book['portal']}|{terms['previous_book']}: {source_book['title']}]]")
        (self.root / f"{manifest['wiki_index']}.md").write_text("\n".join(wiki_lines).strip() + "\n", encoding="utf-8")
        manifest["entities"] = [{key: value for key, value in item.items() if key != "details"} for item in entities]
        self.write_manifest(manifest)
        self._refresh_portals()
        self.repair_and_validate_graph()

    def refresh_entity_indexes(self) -> None:
        """Rebuild derived wiki indexes after guarded/manual entity additions."""
        manifest = self.read_manifest()
        paths = manifest["paths"]
        terms = _terms(manifest.get("language", "en"))
        category_folders = {
            "characters": paths["characters"], "locations": paths["world"],
            "organizations": paths["organizations"], "objects": paths["objects"],
            "concepts": paths["objects"], "events": paths["story"],
        }
        index_targets = []
        for category, folder in category_folders.items():
            labels = {
                "characters": "Personajes" if manifest["language"] == "es" else "People and Characters",
                "locations": "Lugares" if manifest["language"] == "es" else "Locations",
                "organizations": "Organizaciones" if manifest["language"] == "es" else "Organizations",
                "objects": "Objetos" if manifest["language"] == "es" else "Objects",
                "concepts": "Conceptos" if manifest["language"] == "es" else "Concepts",
                "events": "Eventos" if manifest["language"] == "es" else "Events",
            }
            label = labels[category]
            index_path = f"{folder}/Index - {label}"
            index_targets.append(index_path)
            items = [item for item in manifest.get("entities", []) if item.get("category") == category]
            lines = [f"# {label}", "", f"[[{manifest['wiki_index']}|{terms['wiki']}]]", ""]
            lines.extend(f"- [[{item['path']}|{item['name']}]] - {item.get('summary', '')}" for item in items)
            (self.root / f"{index_path}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        wiki_lines = [f"# {Path(manifest['wiki_index']).stem}", "", f"[[{manifest['book_bible']}|{terms['bible']}]]", ""]
        wiki_lines.extend(f"- [[{target}|{Path(target).name.removeprefix('Index - ')}]]" for target in index_targets)
        wiki_lines.extend(
            f"- [[{item['portal']}|{terms['previous_book']}: {item['title']}]]"
            for item in manifest.get("source_books", [])
        )
        (self.root / f"{manifest['wiki_index']}.md").write_text("\n".join(wiki_lines).strip() + "\n", encoding="utf-8")
        self.repair_and_validate_graph()

    @staticmethod
    def _link_registered_names(text: str, owner: dict, entities: list[dict]) -> str:
        linked = str(text)
        for entity in sorted(entities, key=lambda item: len(item["name"]), reverse=True):
            if entity is owner:
                continue
            names = [entity["name"], *entity.get("aliases", [])]
            for name in sorted(names, key=len, reverse=True):
                if len(name) < 3:
                    continue
                pattern = rf"(?<![\w\[])({re.escape(name)})(?![\w\]])"
                replacement = rf"[[{entity['path']}|\1]]"
                linked, count = re.subn(pattern, replacement, linked, count=1, flags=re.IGNORECASE)
                if count:
                    break
        return linked

    def write_plans(self, chapter_dict: dict[str, str], summaries: dict[str, str], ideas: dict[str, list[str]]) -> None:
        manifest = self.read_manifest()
        paths = manifest["paths"]
        terms = _terms(manifest.get("language", "en"))
        ordered = sort_chapters_intelligently(chapter_dict)
        entries = []
        outline_lines = [f"# {Path(manifest['outline']).stem}", "", f"[[{manifest['book_bible']}|{terms['bible']}]]", ""]
        entities = manifest.get("entities", [])
        for index, chapter in enumerate(ordered, 1):
            safe = _safe_filename(chapter)
            plan_path = Path(paths["plans"]) / f"{index:03d} {safe} - Plan.md"
            draft_path = Path(paths["chapters"]) / f"{index:03d} {safe}.md"
            summary_path = Path(paths["summaries"]) / f"{index:03d} {safe} - Summary.md"
            description = chapter_dict.get(chapter, "")
            beats = ideas.get(chapter, [])
            searchable = "\n".join([description, summaries.get(chapter, ""), *beats]).casefold()
            relevant = [item for item in entities if item["name"].casefold() in searchable]
            entity_links = "\n".join(f"- [[{item['path']}|{item['name']}]]" for item in relevant) or f"- {terms['none']}"
            content = (
                "---\ntype: chapter-plan\n" f"order: {index}\nchapter: {_yaml_string(chapter)}\n"
                f"language: {_yaml_string(manifest['language'])}\nstatus: planned\n---\n\n"
                f"# {chapter} - {terms['plan']}\n\n[[{manifest['book_bible']}|{terms['bible']}]] | [[{manifest['outline']}|{terms['outline']}]]\n\n"
                f"## {terms['outline_description']}\n\n{description}\n\n## {terms['chapter_brief']}\n\n{summaries.get(chapter, '').strip()}\n\n"
                f"## {terms['section_plan']}\n\n" + "\n".join(f"- {beat}" for beat in beats)
                + f"\n\n## {terms['entities']}\n\n{entity_links}\n\n## {terms['continuity_notes']}\n\n- {terms['review']}\n"
            )
            (self.root / plan_path).write_text(content, encoding="utf-8")
            outline_lines.append(f"{index}. [[{plan_path.with_suffix('').as_posix()}|{chapter}]] - {description}")
            entries.append({"order": index, "name": chapter, "description": description,
                            "plan_path": plan_path.as_posix(), "draft_path": draft_path.as_posix(),
                            "summary_path": summary_path.as_posix(), "status": "planned"})
        (self.root / f"{manifest['outline']}.md").write_text("\n".join(outline_lines).strip() + "\n", encoding="utf-8")
        manifest["chapters"] = entries
        if manifest.get("books"):
            manifest["books"][0]["chapters"] = entries
        self.write_manifest(manifest)
        self._refresh_portals()
        self.repair_and_validate_graph()

    def write_chapter(self, chapter_name: str, sections: list[str], summary: str) -> None:
        manifest = self.read_manifest()
        terms = _terms(manifest.get("language", "en"))
        entry = next(item for item in manifest["chapters"] if item["name"] == chapter_name)
        chapter_path, summary_path = self.root / entry["draft_path"], self.root / entry["summary_path"]
        chapter_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n\n".join(section.strip() for section in sections if section and section.strip())
        chapter_path.write_text(
            "---\ntype: chapter\n" f"order: {entry['order']}\nlanguage: {_yaml_string(manifest['language'])}\nstatus: drafted\n---\n\n"
            f"# {chapter_name}\n\n[[{manifest['book_bible']}|{terms['bible']}]] | [[{Path(entry['plan_path']).with_suffix('').as_posix()}|{terms['plan']}]]\n\n{body}\n",
            encoding="utf-8",
        )
        summary_path.write_text(
            "---\ntype: chapter-summary\n" f"chapter: {_yaml_string(chapter_name)}\norder: {entry['order']}\n---\n\n"
            f"# {chapter_name} - {terms['summary']}\n\n[[{Path(entry['draft_path']).with_suffix('').as_posix()}|{terms['chapter']}]]\n\n{summary.strip()}\n",
            encoding="utf-8",
        )
        entry["status"] = "drafted"
        for book in manifest.get("books", []):
            for book_entry in book.get("chapters", []):
                if book_entry.get("name") == chapter_name:
                    book_entry["status"] = "drafted"
        self.write_manifest(manifest)

    def _refresh_portals(self) -> None:
        manifest = self.read_manifest()
        paths = manifest["paths"]
        terms = _terms(manifest.get("language", "en"))
        portal = self.root / f"{paths['portal']}.md"
        master = self.root / f"{paths['master_index']}.md"
        portal.write_text(
            f"# {manifest['title']}\n\n"
            f"- [[{manifest['book_bible']}|{terms['book_bible']}]]\n- [[{manifest['wiki_index']}|{terms['wiki']}]]\n"
            f"- [[{paths.get('books_index', manifest['outline'])}|{terms['books']}]]\n- [[{manifest['outline']}|{terms['active_chapters']}]]\n"
            f"- [[{paths['status']}|{terms['project_status']}]]\n"
            f"- [[{paths['questions']}|{terms['questions']}]]\n- [[{paths['continuity_index']}|{terms['continuity']}]]\n",
            encoding="utf-8",
        )
        if manifest.get("source_books"):
            with portal.open("a", encoding="utf-8") as handle:
                handle.write(f"- [[{manifest['source_books'][0]['portal']}|{terms['previous_book']}]]\n")
        master.write_text(
            f"# {master.stem}\n\n[[{paths['portal']}|Portal]]\n\n"
            f"- [[{manifest['book_bible']}|{terms['canonical_bible']}]]\n- [[{manifest['wiki_index']}|{terms['world_wiki']}]]\n"
            f"- [[{manifest['outline']}|{terms['manuscript']}]]\n- [[{paths['style']}|{terms['writing_guide']}]]\n",
            encoding="utf-8",
        )
        if manifest.get("source_books"):
            with master.open("a", encoding="utf-8") as handle:
                handle.write(f"- [[{manifest['source_books'][0]['portal']}|{terms['previous_book']}]]\n")
        books_index = paths.get("books_index")
        if books_index:
            book_lines = [f"# {Path(books_index).name}", ""]
            for book in manifest.get("books", []):
                book_lines.append(f"- [[{book.get('outline', manifest['outline'])}|{book.get('title', 'Untitled')}]]")
            (self.root / f"{books_index}.md").write_text("\n".join(book_lines).strip() + "\n", encoding="utf-8")

    def validate_links(self) -> list[str]:
        markdown_files = list(self.root.rglob("*.md"))
        by_stem: dict[str, list[Path]] = {}
        by_relative = set()
        for path in markdown_files:
            relative = path.relative_to(self.root).with_suffix("").as_posix()
            by_relative.add(relative.casefold())
            by_stem.setdefault(path.stem.casefold(), []).append(path)
        errors = []
        pattern = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
        for source in markdown_files:
            for target in pattern.findall(source.read_text(encoding="utf-8")):
                key = target.strip().replace("\\", "/").casefold().removesuffix(".md")
                if "/" in key and key not in by_relative:
                    errors.append(f"{source.relative_to(self.root)} -> missing [[{target}]]")
                elif "/" not in key:
                    matches = by_stem.get(Path(key).name, [])
                    if not matches:
                        errors.append(f"{source.relative_to(self.root)} -> missing [[{target}]]")
                    elif len(matches) > 1:
                        errors.append(f"{source.relative_to(self.root)} -> ambiguous [[{target}]]")
        return errors

    def repair_links(self) -> list[dict]:
        markdown_files = list(self.root.rglob("*.md"))
        by_stem: dict[str, list[Path]] = {}
        by_relative: dict[str, Path] = {}
        for path in markdown_files:
            relative = path.relative_to(self.root).with_suffix("").as_posix()
            by_relative[relative.casefold()] = path
            by_stem.setdefault(path.stem.casefold(), []).append(path)
        repairs = []
        pattern = re.compile(r"\[\[([^\]|#]+)(#[^\]|]+)?(?:\|([^\]]+))?\]\]")
        for source in markdown_files:
            original = source.read_text(encoding="utf-8")
            def replace(match: re.Match) -> str:
                raw, anchor, alias = match.group(1).strip(), match.group(2) or "", match.group(3)
                visible = (alias or raw).strip()
                key = raw.replace("\\", "/").casefold().removesuffix(".md")
                if key in by_relative:
                    return match.group(0)
                matches = by_stem.get(Path(key).name, [])
                if len(matches) == 1:
                    target = matches[0].relative_to(self.root).with_suffix("").as_posix()
                    replacement = f"[[{target}{anchor}|{visible}]]"
                    repairs.append({"file": str(source.relative_to(self.root)), "from": match.group(0), "to": replacement, "reason": "normalized"})
                    return replacement
                repairs.append({"file": str(source.relative_to(self.root)), "from": match.group(0), "to": visible, "reason": "ambiguous" if matches else "missing"})
                return visible
            updated = pattern.sub(replace, original)
            if updated != original:
                source.write_text(updated, encoding="utf-8")
        report = self.root / ".bookgen" / "link-repairs.json"
        history = []
        if report.exists():
            try:
                history = json.loads(report.read_text(encoding="utf-8"))
            except (TypeError, json.JSONDecodeError):
                history = []
        known = {(item.get("file"), item.get("from"), item.get("to"), item.get("reason")) for item in history}
        history.extend(item for item in repairs if (
            item.get("file"), item.get("from"), item.get("to"), item.get("reason")
        ) not in known)
        report.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return repairs

    def assert_valid_graph(self) -> None:
        errors = self.validate_links()
        if errors:
            raise ValueError("Obsidian graph validation failed:\n" + "\n".join(f"- {value}" for value in errors[:20]))

    def repair_and_validate_graph(self) -> list[dict]:
        repairs = self.repair_links()
        self.assert_valid_graph()
        return repairs

    def read_book(self) -> tuple[str, dict[str, list[str]], dict[str, str]]:
        manifest = self.read_manifest()
        book, chapter_dict = {}, {}
        for entry in sorted(manifest.get("chapters", []), key=lambda item: item["order"]):
            path = self.root / entry["draft_path"]
            if not path.exists():
                continue
            markdown = re.sub(r"(?s)^---\n.*?\n---\n", "", path.read_text(encoding="utf-8"), count=1).strip()
            lines = markdown.splitlines()[1:]
            while lines and (not lines[0].strip() or lines[0].strip().startswith("[[")):
                lines.pop(0)
            book[entry["name"]] = ["\n".join(lines).strip()]
            chapter_dict[entry["name"]] = entry.get("description", "")
        return manifest["title"], book, chapter_dict

    def compile_markdown(self) -> str:
        title, book, _ = self.read_book()
        return "\n\n".join([f"# {title}", *[f"# {name}\n\n" + "\n\n".join(parts) for name, parts in book.items()]]).strip() + "\n"

    def archive(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            for path in sorted(self.root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(self.root.parent))
        return destination


class ObsidianVaultWriter:
    def create(self, output_directory: str | Path, title: str, language: str, metadata: dict,
               framework: str, chapter_dict: dict[str, str] | None = None,
               summaries_dict: dict[str, str] | None = None, idea_dict: dict[str, list[str]] | None = None,
               book_bible: str = "", wiki_data: dict | None = None,
               vault_root: str | Path | None = None) -> VaultProject:
        base = Path(output_directory).expanduser().resolve()
        root = Path(vault_root).expanduser().resolve() if vault_root else base / f"{slugify(title)}-vault"
        root.mkdir(parents=True, exist_ok=True)
        labels = _labels(language)
        terms = _terms(language)
        paths = {
            **{key: labels[key] for key in ("start", "core", "story", "manuscript", "characters", "world", "organizations", "objects", "continuity", "research", "writing", "source_books", "templates", "archive")},
            "portal": f"{labels['start']}/{labels['portal']}",
            "master_index": f"{labels['start']}/{labels['master_index']}",
            "status": f"{labels['start']}/{labels['status']}",
            "questions": f"{labels['start']}/{labels['questions']}",
            "books": f"{labels['manuscript']}/{labels['books']}",
            "books_index": f"{labels['manuscript']}/{labels['books']}/Index - {labels['books']}",
            "continuity_index": f"{labels['continuity']}/{labels['continuity_index']}",
            "style": f"{labels['writing']}/{labels['style']}",
            "agent_notes": f"{labels['writing']}/{labels['agent_notes']}",
        }
        book_id = slugify(title)
        active_book = f"{paths['books']}/{labels['book_prefix']} - {_safe_filename(title)}"
        paths.update({
            "active_book": active_book,
            "plans": f"{active_book}/{labels['plans']}",
            "chapters": f"{active_book}/{labels['chapters']}",
            "scenes": f"{active_book}/{labels['scenes']}",
            "summaries": f"{active_book}/{labels['summaries']}",
        })
        directories = {
            labels[key] for key in (
                "start", "core", "story", "manuscript", "characters", "world",
                "organizations", "objects", "continuity", "research", "writing", "source_books",
                "templates", "archive",
            )
        }
        directories.update(paths[key] for key in ("plans", "chapters", "scenes", "summaries", "agent_notes"))
        for directory in directories:
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / ".bookgen").mkdir(exist_ok=True)

        volumes = _split_bible(book_bible)
        volume_names = VOLUME_NAMES.get(language, VOLUME_NAMES["en"])
        volume_paths = []
        for index, body in enumerate(volumes, 1):
            name = volume_names[index - 1] if index <= len(volume_names) else f"Volume {index}"
            path = Path(labels["core"]) / f"{index:02d} - {name}.md"
            (root / path).write_text(
                "---\ntype: book-bible-volume\n" f"volume: {index}\nstatus: canonical\n---\n\n# {name}\n\n{body.strip()}\n",
                encoding="utf-8",
            )
            volume_paths.append(path.as_posix())
        bible_path = f"{labels['core']}/{labels['bible']}"
        (root / f"{bible_path}.md").write_text(
            f"# {title} - {labels['bible']}\n\n" + "\n".join(
                f"- [[{path.with_suffix('').as_posix()}|{path.stem}]]" for path in map(Path, volume_paths)
            ) + "\n",
            encoding="utf-8",
        )
        wiki_index = f"{labels['start']}/{labels['wiki']}"
        outline = f"{active_book}/{labels['outline']}"
        for target, heading in ((wiki_index, labels["wiki"]), (outline, labels["outline"]),
                                (paths["status"], labels["status"]), (paths["questions"], labels["questions"]),
                                (paths["continuity_index"], labels["continuity_index"]), (paths["style"], labels["style"])):
            (root / f"{target}.md").write_text(f"# {heading}\n\n[[{bible_path}|{terms['bible']}]]\n", encoding="utf-8")
        if metadata.get("vault_mode") == "revise":
            revision_name = "Brief de revision" if language == "es" else "Revision Brief"
            revision_path = f"{labels['writing']}/{revision_name}"
            paths["revision_brief"] = revision_path
            revision_title = "Brief de revision" if language == "es" else "Revision Brief"
            instruction_title = "Instrucciones de edicion vinculantes" if language == "es" else "Binding editing instructions"
            source_title = "Origen" if language == "es" else "Source"
            (root / f"{revision_path}.md").write_text(
                f"---\ntype: revision-brief\nstatus: active\n---\n\n# {revision_title}\n\n"
                f"## {instruction_title}\n\n{metadata.get('subject', '')}\n\n"
                f"## {source_title}\n\n- Vault: `{metadata.get('source_vault_path', '')}`\n"
                f"- Book ID: `{metadata.get('source_book_id', '')}`\n",
                encoding="utf-8",
            )
        self._write_templates(root, labels)
        project = VaultProject(root)
        project.write_manifest({
            "schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
            "title": title, "language": language, "metadata": metadata, "framework": framework,
            "book_bible": bible_path, "book_bible_volumes": volume_paths,
            "outline": outline, "wiki_index": wiki_index, "paths": paths, "entities": [], "chapters": [],
            "active_book_id": book_id,
            "books": [{"id": book_id, "title": title, "path": active_book, "outline": outline, "chapters": []}],
        })
        project._refresh_portals()
        if wiki_data:
            project.write_wiki(wiki_data)
        if chapter_dict:
            project.write_plans(chapter_dict, summaries_dict or {}, idea_dict or {})
        project.repair_and_validate_graph()
        return project

    @staticmethod
    def _write_templates(root: Path, labels: dict[str, str]) -> None:
        spanish = labels["templates"] == "90 - Plantillas"
        if spanish:
            templates = {
                "Persona o personaje": "# <Nombre>\n\n## Resumen\n\n## Funcion en el libro\n\n## Objetivos posicion o conflicto\n\n## Relaciones\n\n## Evidencia y continuidad\n",
                "Lugar": "# <Nombre del lugar>\n\n## Resumen\n\n## Aspecto y atmosfera\n\n## Historia\n\n## Funcion en el libro\n\n## Evidencia y continuidad\n",
                "Organizacion": "# <Nombre de la organizacion>\n\n## Proposito\n\n## Estructura\n\n## Recursos y limites\n\n## Relaciones\n",
                "Capitulo": "# <Numero y titulo>\n\n## Objetivo\n\n## Pregunta o estado inicial\n\n## Progresion narrativa o expositiva\n\n## Plan de secciones\n\n## Cambio o conclusion\n\n## Continuidad y fuentes\n",
                "Escena o seccion": "# <Numero y titulo>\n\n## Proposito\n\n## Punto de vista o enfoque\n\n## Desarrollo\n\n## Pruebas o elementos canonicos\n\n## Resultado\n",
                "Fuente de investigacion": "# <Titulo de la fuente>\n\n## Referencia y URL\n\n## Afirmaciones respaldadas\n\n## Fiabilidad y limites\n\n## Notas\n",
                "Afirmacion y verificacion": "# <Afirmacion>\n\n## Estado\n\n## Pruebas favorables\n\n## Pruebas contrarias\n\n## Conclusion provisional\n",
            }
        else:
            templates = {
                "Person or Character": "# <Name>\n\n## Summary\n\n## Function in the book\n\n## Goals position or conflict\n\n## Relationships\n\n## Evidence and continuity\n",
                "Location": "# <Location name>\n\n## Summary\n\n## Appearance and atmosphere\n\n## History\n\n## Function in the book\n\n## Evidence and continuity\n",
                "Organization": "# <Organization name>\n\n## Purpose\n\n## Structure\n\n## Resources and limits\n\n## Relationships\n",
                "Chapter": "# <Number and title>\n\n## Objective\n\n## Opening question or state\n\n## Narrative or expository progression\n\n## Section plan\n\n## Change or conclusion\n\n## Continuity and sources\n",
                "Scene or Section": "# <Number and title>\n\n## Purpose\n\n## Point of view or focus\n\n## Development\n\n## Evidence or canonical elements\n\n## Result\n",
                "Research Source": "# <Source title>\n\n## Citation and URL\n\n## Claims supported\n\n## Reliability and limits\n\n## Notes\n",
                "Claim and Fact Check": "# <Claim>\n\n## Status\n\n## Supporting evidence\n\n## Contrary evidence\n\n## Provisional conclusion\n",
            }
        for name, body in templates.items():
            (root / labels["templates"] / f"Template - {name}.md").write_text(
                "---\ntype: template\n---\n\n" + body, encoding="utf-8"
            )
