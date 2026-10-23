"""Ensambla el documento, lo exporta a PDF y agrega índice, encabezado y pie de página."""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
OUT_HTML = os.path.join(ROOT, "index.html")
OUT_PDF = os.path.join(ROOT, "UNACH_Diseño_Equipo5.pdf")
ROOT_PDF = os.path.abspath(os.path.join(ROOT, "..", "..", "UNACH_Diseño_Equipo5.pdf"))
TMP = os.path.join(os.environ.get("TEMP", "."), "dosys-doc")
os.makedirs(TMP, exist_ok=True)

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

FRAGMENTS = [
    "00_cover_toc.html",
    "01_e1.html",
    "02_e2.html",
    "03_e3.html",
    "04_e4.html",
    "05_e5_close.html",
]

# clave del índice -> texto que se busca en el PDF
TOC_KEYS = {
    "sec1": "1. Análisis del problema y requisitos",
    "s11": "1.1 Ficha del proyecto",
    "s12": "1.2 Problemática y justificación",
    "s13": "1.3 Objetivos",
    "s14": "1.4 Perfiles de usuario",
    "s15": "1.5 Requisitos funcionales",
    "s16": "1.6 Requisitos no funcionales",
    "s17": "1.7 Historias de usuario",
    "s18": "1.8 Trazabilidad y alcance",
    "sec2": "2. Casos de uso y flujo de navegación",
    "s21": "2.1 Actores y alcance",
    "s22": "2.2 Diagrama de casos de uso",
    "s23": "2.3 Descripción de casos principales",
    "s24": "2.4 Mapa de navegación",
    "s25": "2.5 Inventario de pantallas",
    "sec3": "3. Wireframes y mockups",
    "s31": "3.1 Sistema de diseño",
    "s32": "3.2 Wireframes de baja fidelidad",
    "s33": "3.3 Mockups de alta fidelidad",
    "s34": "3.4 Prototipo navegable",
    "s35": "3.5 Coherencia entre mockups y app",
    "sec4": "4. Arquitectura y modelo de datos",
    "s41": "4.1 Arquitectura MVVM",
    "s42": "4.2 Arquitectura de datos y stack",
    "s43": "4.3 Flujo de datos del check-in",
    "s44": "4.4 Modelo de datos de la app",
    "s45": "4.5 Data classes de Kotlin",
    "s46": "4.6 Diccionario de datos",
    "sec5": "5. Prototipo, coherencia y evidencias",
    "s51": "5.1 Estado del prototipo",
    "s52": "5.2 Coherencia diseño",
    "s53": "5.3 Diferencias respecto del alcance",
    "s54": "5.4 Pruebas y evidencias",
    "sec6": "6. Conclusiones, referencias",
    "anexo": "Modelo entidad-relación del backend",
}


def build_html() -> str:
    with open(os.path.join(SRC, "style.css"), encoding="utf-8") as fh:
        css = fh.read()
    body = []
    for name in FRAGMENTS:
        with open(os.path.join(SRC, name), encoding="utf-8") as fh:
            body.append(fh.read())
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UNACH · Diseño de app Android · D.O.S.Y.S</title>
<style>{css}</style>
</head>
<body>
{''.join(body)}
</body>
</html>"""
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("HTML:", len(html), "bytes")
    return html


def render_pdf(path: str):
    url = "file:///" + OUT_HTML.replace("\\", "/")
    cmd = [
        EDGE,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--virtual-time-budget=30000",
        "--print-to-pdf=" + path,
        url,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not os.path.exists(path):
        raise RuntimeError("Edge no generó el PDF")
    print("PDF:", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


def find_pages(pdf_path: str) -> dict[str, int]:
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    found = {}
    for key, phrase in TOC_KEYS.items():
        for idx in range(3, len(texts)):  # saltar portada y las dos páginas del índice
            if phrase in texts[idx]:
                found[key] = idx + 1
                break
        else:
            # intento con las primeras 28 letras, por si el texto se parte
            short = phrase[:28]
            for idx in range(3, len(texts)):
                if short in texts[idx]:
                    found[key] = idx + 1
                    break
        if key not in found:
            print("  aviso: no se encontró", key, repr(phrase))
    return found


def fill_toc(pages: dict[str, int]):
    with open(OUT_HTML, encoding="utf-8") as fh:
        html = fh.read()
    for key, page in pages.items():
        html = re.sub(
            rf'(data-toc="{re.escape(key)}">)—(</span>)',
            rf"\g<1>{page}\g<2>",
            html,
        )
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("índice actualizado:", pages)


def register_fonts():
    regular = r"C:\Windows\Fonts\arial.ttf"
    bold = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("DocArial", regular))
        pdfmetrics.registerFont(TTFont("DocArialBold", bold if os.path.exists(bold) else regular))
        return "DocArial", "DocArialBold"
    return "Helvetica", "Helvetica-Bold"


def add_header_footer(src: str, dst: str):
    regular, bold = register_fonts()
    reader = PdfReader(src)
    total = len(reader.pages)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i > 0:
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=letter)
            w, h = letter
            c.setStrokeColor(HexColor("#C9DED4"))
            c.setLineWidth(0.5)
            c.line(2.5 * 28.35, h - 1.55 * 28.35, w - 2.5 * 28.35, h - 1.55 * 28.35)
            c.setFont(regular, 7.5)
            c.setFillColor(HexColor("#5B6560"))
            c.drawString(2.5 * 28.35, h - 1.35 * 28.35, "UNACH · Diseño y prototipado de app Android")
            c.drawRightString(w - 2.5 * 28.35, h - 1.35 * 28.35, "Equipo 5 · D.O.S.Y.S")
            c.line(2.5 * 28.35, 1.65 * 28.35, w - 2.5 * 28.35, 1.65 * 28.35)
            c.setFont(regular, 7.5)
            c.drawString(2.5 * 28.35, 1.0 * 28.35, "Documento de diseño · E1–E4")
            c.setFont(bold, 8)
            c.setFillColor(HexColor("#13653F"))
            c.drawRightString(w - 2.5 * 28.35, 1.0 * 28.35, f"Página {i + 1} de {total}")
            c.save()
            overlay = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
            page.merge_page(overlay)
        writer.add_page(page)
    with open(dst, "wb") as fh:
        writer.write(fh)
    print("PDF final:", dst, round(os.path.getsize(dst) / 1024 / 1024, 2), "MB")


def previews(pdf_path: str, pages: list[int]):
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        print("sin previews:", exc)
        return
    pdf = pdfium.PdfDocument(pdf_path)
    for p in pages:
        if 0 <= p < len(pdf):
            img = pdf[p].render(scale=1.1).to_pil()
            out = os.path.join(TMP, f"docpage-{p+1}.png")
            img.save(out)
            print("preview:", out)


def main():
    build_html()
    temp_pdf = os.path.join(TMP, "doc-pass1.pdf")
    render_pdf(temp_pdf)
    pages = find_pages(temp_pdf)
    fill_toc(pages)
    render_pdf(temp_pdf)
    add_header_footer(temp_pdf, OUT_PDF)
    shutil.copy2(OUT_PDF, ROOT_PDF)
    print("copia en raíz:", ROOT_PDF)
    previews(OUT_PDF, [0, 1, 2, 3, 6, 8, 10, 12, 14, 18, 22, 26, 30, 34])
    reader = PdfReader(OUT_PDF)
    box = reader.pages[0].mediabox
    print("páginas:", len(reader.pages), "| tamaño:", round(float(box.width), 1), "x", round(float(box.height), 1), "pt")


if __name__ == "__main__":
    main()
