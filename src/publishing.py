"""Publish canonical Obsidian vault content to reader-facing formats."""

from __future__ import annotations

from html import escape
import os
from pathlib import Path
import re
import shutil
import subprocess

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from obsidian_vault import VaultProject, slugify
from text_cleaning import clean_content


SUPPORTED_OUTPUT_FORMATS = ("obsidian", "md", "txt", "html", "docx", "pdf")


def print_progress(message):
    print(f"\n> {message}", flush=True)


def _narrative_text(value: str) -> str:
    return clean_content(value or "", aggressive=True).strip()


class DocxWriter:
    def write(self, title: str, book: dict[str, list[str]], destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        document = Document()
        normal = document.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(12)
        for section in document.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        heading = document.add_heading(title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        document.add_page_break()
        for index, (chapter, sections) in enumerate(book.items()):
            document.add_heading(chapter, level=1)
            content = _narrative_text("\n\n".join(sections))
            for paragraph in re.split(r"\n\s*\n", content):
                if paragraph.strip():
                    document.add_paragraph(paragraph.strip())
            if index < len(book) - 1:
                document.add_page_break()
        document.save(destination)
        return destination


class VaultPublisher:
    def publish(self, project: VaultProject, output_format="docx", output_path=None) -> Path:
        output_format = output_format.lower().strip()
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format '{output_format}'")
        project.repair_and_validate_graph()
        title, book, _ = project.read_book()
        if not book:
            raise ValueError("The vault has no drafted chapters to publish")

        destination_dir = Path(output_path or project.root.parent).expanduser().resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        stem = slugify(title)
        if output_format == "obsidian":
            return project.archive(destination_dir / f"{stem}-obsidian.zip")

        markdown = project.compile_markdown()
        if output_format == "md":
            destination = destination_dir / f"{stem}.md"
            destination.write_text(markdown, encoding="utf-8")
            return destination
        if output_format == "txt":
            destination = destination_dir / f"{stem}.txt"
            plain = re.sub(r"(?m)^#+\s*", "", markdown)
            destination.write_text(plain, encoding="utf-8")
            return destination
        if output_format == "html":
            destination = destination_dir / f"{stem}.html"
            chunks = []
            for line in markdown.splitlines():
                if line.startswith("# "):
                    chunks.append(f"<h1>{escape(line[2:])}</h1>")
                elif line.strip():
                    chunks.append(f"<p>{escape(line)}</p>")
            destination.write_text(
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                f"<title>{escape(title)}</title><style>body{{max-width:48rem;margin:3rem auto;"
                "font:18px/1.65 Georgia,serif;padding:0 1rem}}h1{page-break-before:always}</style>"
                f"</head><body>{''.join(chunks)}</body></html>",
                encoding="utf-8",
            )
            return destination

        docx_path = DocxWriter().write(title, book, destination_dir / f"{stem}.docx")
        if output_format == "docx":
            return docx_path

        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            raise RuntimeError("PDF export requires LibreOffice (libreoffice or soffice in PATH)")
        result = subprocess.run(
            [libreoffice, "--headless", "--convert-to", "pdf", "--outdir", str(destination_dir), str(docx_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        pdf_path = destination_dir / f"{stem}.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(f"LibreOffice PDF conversion failed: {result.stderr.strip()}")
        return pdf_path


class DocWriter:
    """Compatibility adapter for callers that still provide an in-memory book."""

    def clean_content(self, text):
        return _narrative_text(text)

    def extract_clean_title(self, chapter_title):
        return str(chapter_title).split(":", 1)[0].strip()

    def write_doc(self, book, chapter_dict, title, output_format="docx", output_path="./books"):
        output_format = output_format.lower()
        if output_format not in ("docx", "pdf"):
            raise ValueError("Legacy DocWriter supports docx/pdf; use VaultPublisher for other formats")
        destination_dir = Path(output_path).expanduser().resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        docx_path = DocxWriter().write(title, book, destination_dir / f"{slugify(title)}.docx")
        if output_format == "docx":
            return str(docx_path)
        libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice:
            raise RuntimeError("PDF export requires LibreOffice")
        subprocess.run(
            [libreoffice, "--headless", "--convert-to", "pdf", "--outdir", str(destination_dir), str(docx_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return str(destination_dir / f"{slugify(title)}.pdf")
