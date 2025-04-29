from docx import Document
import os
import sys
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import subprocess


def print_progress(message):
    print(f"\n> {message}")
    sys.stdout.flush()


class DocWriter:
    def __init__(self) -> None:
        self.doc = Document()
        # Configurar estilo del documento
        self.doc.styles['Normal'].font.name = 'Times New Roman'
        self.doc.styles['Normal'].font.size = Pt(12)

    def write_doc(self, book, chapter_dict, title):
        try:
            print_progress("Iniciando creación del documento...")
            
            # Crear directorio docs si no existe
            os.makedirs("docs", exist_ok=True)
            
            # Título principal
            title_paragraph = self.doc.add_heading(title, 0)
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Agregar salto de página después del título
            self.doc.add_page_break()

            # Escribir cada capítulo
            for chapter, paragraphs_list in book.items():
                print_progress(f"Escribiendo capítulo: {chapter}")
                
                description = chapter_dict[chapter]
                chapter_name = f"{chapter}: {description.strip()}"
                
                # Título del capítulo
                chapter_heading = self.doc.add_heading(chapter_name, 1)
                chapter_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # Contenido del capítulo
                for paragraph_text in paragraphs_list:
                    if paragraph_text and paragraph_text.strip():
                        paragraph = self.doc.add_paragraph(paragraph_text.strip())
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

                # Agregar salto de página entre capítulos
                if chapter != list(book.keys())[-1]:  # No añadir salto después del último
                    self.doc.add_page_break()

            # Guardar el documento
            docx_path = "./docs/book_1.docx"
            self.doc.save(docx_path)
            print_progress(f"Documento guardado como: {docx_path}")

            # Convertir a PDF usando LibreOffice si está disponible
            try:
                pdf_path = docx_path.replace('.docx', '.pdf')
                print_progress("Intentando convertir a PDF...")
                
                # Intentar usar LibreOffice para la conversión
                soffice_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                ]
                
                converted = False
                for soffice_path in soffice_paths:
                    if os.path.exists(soffice_path):
                        try:
                            subprocess.run([
                                soffice_path,
                                '--headless',
                                '--convert-to',
                                'pdf',
                                '--outdir',
                                'docs',
                                docx_path
                            ], check=True, capture_output=True)
                            converted = True
                            print_progress(f"PDF generado exitosamente: {pdf_path}")
                            break
                        except subprocess.CalledProcessError:
                            continue
                
                if not converted:
                    print_progress("No se pudo convertir a PDF. El archivo está disponible en formato DOCX.")
                
            except Exception as e:
                print_progress(f"Error en la conversión a PDF: {str(e)}")
                print_progress("El archivo está disponible en formato DOCX.")

        except Exception as e:
            print_progress(f"Error guardando el documento: {str(e)}")
            raise
