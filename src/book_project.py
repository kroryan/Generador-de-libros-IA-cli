"""Persistent, isolated workspace created before any book-generation call."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from obsidian_vault import slugify


@dataclass(frozen=True)
class BookProjectWorkspace:
    """Owns every durable artifact produced for one generation run."""

    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / ".bookgen" / "project.json"

    @property
    def work_directory(self) -> Path:
        return self.root / "Work"

    @property
    def exports_directory(self) -> Path:
        return self.root / "Exports"

    @classmethod
    def create(cls, output_directory: str | Path, request: dict) -> "BookProjectWorkspace":
        base = Path(output_directory).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        stem = f"pending-book-{now.strftime('%Y%m%d-%H%M%S')}"
        root = base / stem
        suffix = 2
        while root.exists():
            root = base / f"{stem}-{suffix}"
            suffix += 1
        for directory in (root, root / ".bookgen", root / "Work", root / "Exports"):
            directory.mkdir(parents=True, exist_ok=True)

        workspace = cls(root)
        workspace._write_manifest({
            "schema_version": 1,
            "project_id": root.name,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "status": "created",
            "current_stage": "request",
            "title": "",
            "error": None,
            "request": request,
            "paths": {"work": "Work", "exports": "Exports", "vault": "."},
            "stages": [],
        })
        workspace.write_markdown(
            "00 Request.md",
            "# Book Generation Request\n\n"
            f"- Language: {request.get('language', '')}\n"
            f"- Genre: {request.get('genre', '')}\n"
            f"- Style: {request.get('style', '')}\n"
            f"- Output format: {request.get('output_format', '')}\n\n"
            f"## Premise\n\n{request.get('subject', '')}\n\n"
            f"## Reader and constraints\n\n{request.get('profile', '')}\n",
            stage="request",
        )
        return workspace

    def rename_for_title(self, title: str) -> "BookProjectWorkspace":
        """Atomically replace the temporary directory name with the generated title."""
        clean_title = str(title).strip()
        title_slug = slugify(clean_title)[:100]
        manifest = self.read_manifest()
        if (
            manifest.get("title") == clean_title
            and manifest.get("project_id") == self.root.name
            and not self.root.name.startswith("pending-book-")
        ):
            return self

        stem = title_slug or "untitled-book"
        destination = self.root.parent / stem
        suffix = 2
        while destination.exists() and destination != self.root:
            destination = self.root.parent / f"{stem}-{suffix}"
            suffix += 1

        if destination != self.root:
            self.root.rename(destination)
        workspace = type(self)(destination)
        manifest["project_id"] = destination.name
        manifest["title"] = clean_title
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        workspace._write_manifest(manifest)
        workspace._refresh_dashboard()
        return workspace

    def read_manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def update(self, **values) -> None:
        manifest = self.read_manifest()
        manifest.update(values)
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_manifest(manifest)
        self._refresh_dashboard()

    def write_markdown(self, filename: str, content: str, stage: str) -> Path:
        path = self.work_directory / filename
        path.write_text(content.strip() + "\n", encoding="utf-8")
        self._record_stage(stage, path)
        return path

    def write_json(self, filename: str, payload: object, stage: str) -> Path:
        path = self.work_directory / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._record_stage(stage, path)
        return path

    def write_checkpoint(self, filename: str, payload: str | object) -> Path:
        """Persist resumable intermediate data outside the visible canonical vault."""
        directory = self.root / ".bookgen" / "checkpoints"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        if isinstance(payload, str):
            path.write_text(payload.strip() + "\n", encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def mark_failed(self, error: Exception) -> None:
        self.update(status="failed", current_stage="failed", error=str(error))

    def mark_cancelled(self) -> None:
        self.update(status="cancelled", current_stage="cancelled", error=None)

    def mark_complete(self, title: str, output_path: Path) -> None:
        self.update(
            status="complete",
            current_stage="complete",
            title=title,
            error=None,
            published_output=output_path.relative_to(self.root).as_posix(),
        )

    def _record_stage(self, stage: str, path: Path) -> None:
        manifest = self.read_manifest()
        relative = path.relative_to(self.root).as_posix()
        stages = [item for item in manifest.get("stages", []) if item.get("name") != stage]
        stages.append({
            "name": stage,
            "path": relative,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        })
        manifest.update({"status": "running", "current_stage": stage, "stages": stages})
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_manifest(manifest)
        self._refresh_dashboard()

    def _write_manifest(self, manifest: dict) -> None:
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.manifest_path)

    def _refresh_dashboard(self) -> None:
        manifest = self.read_manifest()
        title = manifest.get("title") or "Untitled book project"
        lines = [
            "---",
            "type: book-project",
            f"status: {json.dumps(manifest.get('status', 'created'))}",
            "---",
            "",
            f"# {title}",
            "",
            f"- Project ID: `{manifest['project_id']}`",
            f"- Status: `{manifest.get('status', 'created')}`",
            f"- Current stage: `{manifest.get('current_stage', '')}`",
            "",
            "## Generation Work",
            "",
        ]
        for item in manifest.get("stages", []):
            path = Path(item["path"])
            label = item["name"].replace("_", " ").title()
            if path.suffix.casefold() == ".md":
                lines.append(f"- [[{path.with_suffix('').as_posix()}|{label}]]")
            else:
                lines.append(f"- [{label}]({path.as_posix().replace(' ', '%20')})")
        vault_manifest_path = self.root / ".bookgen" / "manifest.json"
        if vault_manifest_path.exists():
            try:
                vault = json.loads(vault_manifest_path.read_text(encoding="utf-8"))
                lines.extend([
                    "", "## Canonical Vault", "",
                    f"- [[{vault['book_bible']}|Book Bible]]",
                    f"- [[{vault['outline']}|Chapter Index]]",
                    f"- [[{vault['wiki_index']}|Wiki Index]]",
                ])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
        (self.root / "Project Dashboard.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
