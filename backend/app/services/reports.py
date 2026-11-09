"""PDFs que el sistema genera: resultados de laboratorio y recetas médicas.

Son documentos de demostración académica; se guardan en el expediente como
cualquier otro documento y reciben la misma huella SHA-256 y sello del servidor.
"""

import textwrap
from datetime import datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

CLINIC_TIMEZONE = ZoneInfo("America/Mexico_City")
GREEN = colors.HexColor("#1F5C3A")
GRAY = colors.HexColor("#666666")


def _local(moment: datetime | None) -> str:
    if moment is None:
        return "Sin registro"
    value = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return value.astimezone(CLINIC_TIMEZONE).strftime("%d/%m/%Y a las %H:%M h")


def _header(pdf: canvas.Canvas, title: str) -> float:
    width, height = letter
    pdf.setFillColor(GREEN)
    pdf.rect(0, height - 3.0 * cm, width, 3.0 * cm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 21)
    pdf.drawString(1.5 * cm, height - 1.35 * cm, "D.O.S.Y.S")
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(1.5 * cm, height - 1.95 * cm, "Sistema hospitalario · Documento de demostración académica")
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(1.5 * cm, height - 4.15 * cm, title)
    pdf.setFillColor(colors.black)
    return height - 4.8 * cm


def _field(pdf: canvas.Canvas, y: float, label: str, value: str) -> float:
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1.5 * cm, y, f"{label}:")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(6.3 * cm, y, value[:96])
    return y - 0.58 * cm


def _paragraph(pdf: canvas.Canvas, y: float, text: str, width: int = 92) -> float:
    pdf.setFont("Helvetica", 10)
    for line in textwrap.wrap(text, width) or [""]:
        pdf.drawString(1.5 * cm, y, line)
        y -= 0.5 * cm
    return y


def _footer(pdf: canvas.Canvas) -> None:
    pdf.setFont("Helvetica-Oblique", 7.8)
    pdf.setFillColor(GRAY)
    pdf.drawString(
        1.5 * cm,
        1.35 * cm,
        "Documento generado por D.O.S.Y.S con datos ficticios de demostración académica.",
    )
    pdf.drawString(
        1.5 * cm,
        0.95 * cm,
        "El archivo quedó protegido con huella SHA-256 y sello del servidor; puede verificarse en el expediente.",
    )
    pdf.setFillColor(colors.black)


def build_study_result_pdf(
    *,
    patient_name: str,
    patient_curp: str,
    study_name: str,
    doctor_name: str,
    performer_name: str,
    result_text: str,
    requested_at: datetime | None,
    performed_at: datetime | None,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = _header(pdf, "Resultado de estudio")
    y = _field(pdf, y, "Paciente", patient_name)
    y = _field(pdf, y, "CURP", patient_curp or "No registrada")
    y = _field(pdf, y, "Estudio", study_name)
    y = _field(pdf, y, "Solicitado", _local(requested_at))
    y = _field(pdf, y, "Realizado", _local(performed_at))
    y = _field(pdf, y, "Médico solicitante", doctor_name)
    y = _field(pdf, y, "Personal que realizó", performer_name)

    y -= 0.35 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "Conclusión")
    y -= 0.7 * cm
    y = _paragraph(pdf, y, result_text)

    y -= 0.35 * cm
    pdf.setFillColor(colors.HexColor("#F2F6F3"))
    pdf.rect(1.5 * cm, y - 1.25 * cm, 16.0 * cm, 1.5 * cm, stroke=0, fill=1)
    pdf.setFillColor(colors.HexColor("#1F5C3A"))
    pdf.setFont("Helvetica-Bold", 9.5)
    pdf.drawString(1.9 * cm, y - 0.45 * cm, "Estudio realizado con control de calidad interno.")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.black)
    pdf.drawString(1.9 * cm, y - 0.95 * cm, "Conserve este documento; puede verificarse su integridad en el portal clínico.")
    _footer(pdf)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_consultation_pdf(
    *,
    patient_name: str,
    patient_curp: str,
    doctor_name: str,
    specialty: str,
    created_at: datetime | None,
    reason: str,
    diagnosis: str,
    notes: str | None,
    blood_pressure: str | None,
    heart_rate: int | None,
    respiratory_rate: int | None,
    temperature_c: float | None,
    oxygen_saturation: int | None,
    weight_kg: float | None,
    height_cm: float | None,
    physical_exam: str | None,
) -> bytes:
    """Nota clínica SOAP imprimible, con signos vitales y plan."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = _header(pdf, "Nota de consulta")
    y = _field(pdf, y, "Paciente", patient_name)
    y = _field(pdf, y, "CURP", patient_curp or "No registrada")
    y = _field(pdf, y, "Médico", f"{doctor_name} · {specialty}")
    y = _field(pdf, y, "Fecha", _local(created_at))

    vitals = []
    if blood_pressure:
        vitals.append(f"TA {blood_pressure} mmHg")
    if heart_rate:
        vitals.append(f"FC {heart_rate} lpm")
    if respiratory_rate:
        vitals.append(f"FR {respiratory_rate} rpm")
    if temperature_c:
        vitals.append(f"T {temperature_c} °C")
    if oxygen_saturation:
        vitals.append(f"SpO2 {oxygen_saturation}%")
    if weight_kg:
        vitals.append(f"Peso {weight_kg} kg")
    if height_cm:
        vitals.append(f"Talla {height_cm} cm")
    if weight_kg and height_cm:
        bmi = weight_kg / ((height_cm / 100) ** 2)
        vitals.append(f"IMC {bmi:.1f}")

    y -= 0.2 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "S · Subjetivo")
    y -= 0.55 * cm
    y = _paragraph(pdf, y, reason)

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "O · Objetivo")
    y -= 0.55 * cm
    y = _paragraph(pdf, y, " · ".join(vitals) if vitals else "Signos vitales no registrados.")
    if physical_exam:
        y = _paragraph(pdf, y, f"Exploración física: {physical_exam}")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "A · Análisis")
    y -= 0.55 * cm
    y = _paragraph(pdf, y, diagnosis)

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "P · Plan")
    y -= 0.55 * cm
    y = _paragraph(pdf, y, notes or "Sin indicaciones adicionales.")

    if y < 4 * cm:
        pdf.showPage()
        y = _header(pdf, "Nota de consulta (continuación)")

    y -= 1.2 * cm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(1.5 * cm, y, "_______________________________")
    pdf.drawString(1.5 * cm, y - 0.45 * cm, doctor_name)
    _footer(pdf)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_prescription_pdf(
    *,
    patient_name: str,
    patient_curp: str,
    doctor_name: str,
    notes: str | None,
    items: list[dict],
    created_at: datetime | None = None,
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = _header(pdf, "Receta médica")
    y = _field(pdf, y, "Paciente", patient_name)
    y = _field(pdf, y, "CURP", patient_curp or "No registrada")
    y = _field(pdf, y, "Médico", doctor_name)
    y = _field(pdf, y, "Fecha", _local(created_at or datetime.now(timezone.utc)))

    y -= 0.35 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, y, "Medicamentos")
    y -= 0.75 * cm
    for index, item in enumerate(items, start=1):
        pdf.setFont("Helvetica-Bold", 10.5)
        pdf.drawString(1.5 * cm, y, f"{index}. {item['medication']}")
        y -= 0.5 * cm
        pdf.setFont("Helvetica", 9.5)
        detalle = f"{item['dose']} · {item['frequency']}"
        if item.get("duration"):
            detalle += f" · {item['duration']}"
        pdf.drawString(2.1 * cm, y, detalle)
        y -= 0.75 * cm

    if notes:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(1.5 * cm, y, "Indicaciones")
        y -= 0.6 * cm
        y = _paragraph(pdf, y, notes, width=90)

    y -= 0.4 * cm
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColor(GRAY)
    pdf.drawString(1.5 * cm, y, "Receta válida por 30 días naturales.")
    pdf.setFillColor(colors.black)
    y -= 1.4 * cm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(1.5 * cm, y, "_______________________________")
    pdf.drawString(1.5 * cm, y - 0.45 * cm, doctor_name)
    _footer(pdf)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
