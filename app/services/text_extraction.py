import io

import pypdf
from docx import Document as DocxDocument

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_CONTENT_TYPE = "text/plain"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type ==  PDF_CONTENT_TYPE:
        return _extract_pdf(file_bytes)
    if content_type == DOCX_CONTENT_TYPE:
        return _extract_docx(file_bytes)
    if content_type == TXT_CONTENT_TYPE:
        return file_bytes.decode("utf-8", errors='ignore')

    raise ValueError(f"Unsupported content type for text extraction: {content_type}")

def _extract_pdf(file_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    page_text = [page.extract_text() or "" for page in reader.pages]
    return '\n'.join(page_text)

def _extract_docx(file_bytes: bytes) -> str:
    document = DocxDocument(io.BytesIO(file_bytes))
    return  '\n'.join(paragraph.text for paragraph in document.paragraphs)

def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_lenght = len(text)

    while start < text_lenght:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks