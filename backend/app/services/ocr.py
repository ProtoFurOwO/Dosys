"""Lectura de documentos de resultados: capa de texto del PDF y OCR.

El sistema genera los PDF de resultados con reportlab, así que ya traen texto
seleccionable; para PDF escaneados o imágenes se usa OCR con Tesseract. Todo
ocurre en el servidor: el archivo nunca sale de la máquina.

Las dependencias son opcionales en tiempo de ejecución: si faltan, se lanza
`OcrUnavailable` y el resumen sigue funcionando sin el texto del PDF.
"""

from __future__ import annotations

import io
from functools import lru_cache

from app.core.config import settings

MIN_TEXT_CHARS = 40
MAX_PAGES = 3
RENDER_SCALE = 2.0


class OcrUnavailable(RuntimeError):
    """No hay forma de extraer texto del documento en este servidor."""


def _pdf_text_layer(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OcrUnavailable("La lectura de PDF no está instalada.") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:MAX_PAGES]
        return "\n".join((page.extract_text() or "") for page in pages)
    except Exception as exc:  # archivo corrupto o protegido
        raise OcrUnavailable("No se pudo leer el PDF.") from exc


def _tesseract():
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OcrUnavailable("El OCR no está instalado en el servidor.") from exc

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:  # binario ausente
        raise OcrUnavailable("El OCR no está disponible en el servidor.") from exc
    return pytesseract


def _ocr_pdf(data: bytes) -> str:
    tesseract = _tesseract()
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OcrUnavailable("La conversión de PDF a imagen no está instalada.") from exc

    try:
        pdf = pdfium.PdfDocument(data)
        texts = []
        for index in range(min(len(pdf), MAX_PAGES)):
            bitmap = pdf[index].render(scale=RENDER_SCALE)
            texts.append(tesseract.image_to_string(bitmap.to_pil(), lang=settings.ai_ocr_language))
        return "\n".join(texts)
    except OcrUnavailable:
        raise
    except Exception as exc:
        raise OcrUnavailable("El OCR no pudo procesar el PDF.") from exc


def _ocr_image(data: bytes) -> str:
    tesseract = _tesseract()
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OcrUnavailable("La lectura de imágenes no está instalada.") from exc

    try:
        with Image.open(io.BytesIO(data)) as image:
            return tesseract.image_to_string(image.convert("RGB"), lang=settings.ai_ocr_language)
    except OcrUnavailable:
        raise
    except Exception as exc:
        raise OcrUnavailable("El OCR no pudo procesar la imagen.") from exc


def extract_document_text(data: bytes, content_type: str) -> tuple[str, str]:
    """Devuelve (texto, método) con método `pdf`, `ocr` o `sin_texto`."""
    if not data:
        raise OcrUnavailable("El archivo está vacío.")

    if content_type == "application/pdf":
        try:
            text = _pdf_text_layer(data)
        except OcrUnavailable:
            text = ""
        if len(" ".join(text.split())) >= MIN_TEXT_CHARS:
            return text, "pdf"
        text = _ocr_pdf(data)
    elif content_type.startswith("image/"):
        text = _ocr_image(data)
    else:
        raise OcrUnavailable("Tipo de archivo no soportado para OCR.")

    text = text.strip()
    return (text, "ocr") if text else ("", "sin_texto")


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """Comprueba una sola vez si Tesseract está instalado en el servidor."""
    try:
        _tesseract()
    except OcrUnavailable:
        return False
    return True
