"""Genera el QR del check-in como SVG en línea, sin dependencias de imagen."""

import io

import qrcode
import qrcode.image.svg


def qr_svg(data: str) -> str:
    """SVG listo para insertar dentro del HTML del portal.

    Se usa SvgPathImage porque produce un <svg> real (con viewBox); la variante
    "fragment" genera etiquetas con prefijo que el navegador ignora en HTML.
    """
    image = qrcode.make(
        data,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    buffer = io.BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode("utf-8")

    # El prólogo <?xml ...?> no es válido al insertar el SVG dentro del HTML.
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    return svg
