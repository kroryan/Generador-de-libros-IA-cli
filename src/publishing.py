from docx import Document
import os
import sys
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import subprocess
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def print_progress(message):
    print(f"\n> {message}")
    sys.stdout.flush()


class DocWriter:
    def __init__(self) -> None:
        self.doc = Document()
        # Configurar estilo del documento
        self.doc.styles['Normal'].font.name = 'Times New Roman'
        self.doc.styles['Normal'].font.size = Pt(12)

    def write_doc(self, book, chapter_dict, title, output_format='docx', output_path='./docs'):
        try:
            print_progress("Iniciando creación del documento...")
            
            # Normalizar la ruta de salida
            if not os.path.isabs(output_path):
                output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), output_path.lstrip('./\\'))
            
            # Crear directorio de salida si no existe
            os.makedirs(output_path, exist_ok=True)
            
            # Añadir metadatos para mejor indexación
            core_properties = self.doc.core_properties
            core_properties.author = "AI Book Generator"
            core_properties.title = title
            core_properties.subject = "Novela generada con IA"
            core_properties.category = "Ficción"
            
            # Configurar márgenes para mejor legibilidad
            section = self.doc.sections[0]
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            
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

                # Contenido del capítulo - procesar como bloques semánticos
                for paragraph_text in paragraphs_list:
                    if paragraph_text and paragraph_text.strip():
                        # Dividir en párrafos lógicos si hay múltiples saltos de línea
                        inner_paragraphs = paragraph_text.strip().split('\n\n')
                        for inner_para in inner_paragraphs:
                            if inner_para.strip():
                                paragraph = self.doc.add_paragraph(inner_para.strip())
                                paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                                paragraph.paragraph_format.first_line_indent = Inches(0.25)
                                paragraph.paragraph_format.space_after = Pt(12)

                # Agregar salto de página entre capítulos
                if chapter != list(book.keys())[-1]:  # No añadir salto después del último
                    self.doc.add_page_break()

            # Generar un nombre de archivo único basado en el título
            safe_title = "".join([c if c.isalnum() else "_" for c in title]).lower()
            file_id = 1
            base_filename = f"book_{safe_title[:30]}_{file_id}"
            
            # Guardar el documento DOCX
            docx_path = os.path.join(output_path, f"{base_filename}.docx")
            self.doc.save(docx_path)
            print_progress(f"Documento guardado como: {docx_path}")
            
            final_path = docx_path
            
            # Convertir a PDF si se solicita ese formato
            if output_format.lower() == 'pdf':
                pdf_path = os.path.join(output_path, f"{base_filename}.pdf")
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
                                output_path,
                                docx_path
                            ], check=True, capture_output=True)
                            converted = True
                            print_progress(f"PDF generado exitosamente: {pdf_path}")
                            final_path = pdf_path
                            break
                        except subprocess.CalledProcessError:
                            continue
                
                if not converted:
                    print_progress("No se pudo convertir a PDF. El archivo está disponible en formato DOCX.")
            
            return final_path

        except Exception as e:
            print_progress(f"Error guardando el documento: {str(e)}")
            raise
