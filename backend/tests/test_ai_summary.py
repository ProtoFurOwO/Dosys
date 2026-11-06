"""Pruebas del resumen del expediente con IA.

Sin red y sin llave real: se usa `FakeLlmClient` o un cliente simulado.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "prueba-" + "x" * 40)
os.environ.setdefault("AI_ENABLED", "true")
os.environ.setdefault("AI_PROVIDER", "fake")
os.environ.setdefault("AI_OCR_ENABLED", "false")

import json
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todas las tablas)
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.lab_study import LabStudy
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.prescription import Prescription, PrescriptionItem
from app.models.role import Role
from app.models.study_order import StudyOrder
from app.models.user import User
from app.services import ai_summary
from app.services.llm_client import AiUnavailable, FakeLlmClient
from app.services.local_summary import build_local_summary
from app.services.ocr import extract_document_text
from app.services.reports import build_study_result_pdf

ALL_PERMISSIONS = (
    "portal:access",
    "patients:read",
    "consultations:read",
    "studies:read",
    "prescriptions:read",
    "documents:read",
    "ai:summary",
)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def make_user(db, permissions=ALL_PERMISSIONS, username="medico"):
    items = []
    for code in permissions:
        permission = await db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, area="Prueba", action="lectura", description=code)
            db.add(permission)
        items.append(permission)
    role = Role(code=f"rol-{username}", name="Médico", description=None, is_system=True, permissions=items)
    user = User(username=username, password_hash="x", role=role)
    db.add(user)
    await db.flush()
    return user


async def make_patient(db, *, notes="", with_studies=True, with_recipes=True):
    user = await make_user(db, ["portal:access", "patients:read"], username="paciente_user")
    patient = Patient(
        user_id=user.id,
        full_name="José Antonio Matuz",
        curp="MAAJ010415HCSRRN09",
        email="jose.matuz@correo.com",
        emergency_contact="María Argueta · 961 123 4567",
        blood_type="O+",
        birth_date=date(2001, 4, 15),
    )
    doctor_user = await make_user(db, ALL_PERMISSIONS, username="doctor_base")
    doctor = Doctor(user_id=doctor_user.id, full_name="Dra. López", specialty="Medicina General")
    db.add_all([patient, doctor])
    await db.flush()

    db.add(
        Consultation(
            patient_id=patient.id,
            doctor_id=doctor.id,
            reason="Control de presión",
            diagnosis="Hipertensión en control",
            notes=notes or "Sin notas.",
        )
    )
    if with_studies:
        study = LabStudy(code="biometria", name="Biometría hemática", category="laboratorio")
        db.add(study)
        await db.flush()
        db.add(
            StudyOrder(
                patient_id=patient.id,
                study_id=study.id,
                doctor_id=doctor.id,
                result_text="Hemoglobina 14.2 g/dL.",
                performed_at=datetime(2026, 10, 4, 18, tzinfo=timezone.utc),
            )
        )
    if with_recipes:
        prescription = Prescription(patient_id=patient.id, doctor_id=doctor.id)
        prescription.items = [
            PrescriptionItem(
                medication="Losartán", dose="50 mg", frequency="cada 24 h", duration="30 días"
            )
        ]
        db.add(prescription)
    await db.flush()
    return await make_user(db, ALL_PERMISSIONS, username="doctor_clinico"), patient


@pytest.mark.asyncio
async def test_la_entrada_no_lleva_identificadores_y_depura_textos(db):
    doctor, patient = await make_patient(
        db,
        notes=(
            "Paciente MAAJ010415HCSRRN09, correo jose.matuz@correo.com, "
            "teléfono 961 123 4567. Se cita en control."
        ),
    )
    entry = await ai_summary.build_summary_input(db, patient=patient, user=doctor)
    raw = json.dumps(entry.payload, ensure_ascii=False)

    assert patient.full_name not in raw
    assert patient.curp not in raw
    assert patient.email not in raw
    assert patient.emergency_contact not in raw
    assert "dato omitido" in raw
    assert "José Antonio Matuz" not in ai_summary.sanitize_text("José Antonio Matuz", patient=patient)
    assert entry.payload["paciente"]["edad_anios"] >= 0
    assert "consultas" in entry.payload


@pytest.mark.asyncio
async def test_sin_permisos_no_incluye_estudios_ni_recetas(db):
    _, patient = await make_patient(db)
    limited = await make_user(
        db, ["portal:access", "patients:read", "consultations:read", "ai:summary"], username="limitado"
    )

    entry = await ai_summary.build_summary_input(db, patient=patient, user=limited)

    assert "estudios" not in entry.payload
    assert "recetas" not in entry.payload
    assert "consultas" in entry.payload


def test_descarta_items_con_fuentes_inexistentes():
    raw = json.dumps(
        {
            "resumen": "Resumen de prueba.",
            "padecimientos_registrados": [
                {"texto": "Válido", "fuentes": ["consulta:1"]},
                {"texto": "Inventado", "fuentes": ["consulta:999"]},
            ],
            "puntos_por_confirmar": [],
            "limitaciones": "",
        }
    )

    resumen = ai_summary.parse_summary(raw, {"consulta:1"})

    assert [item.texto for item in resumen.padecimientos_registrados] == ["Válido"]


def test_json_invalido_o_sin_fuentes_validas_es_fallo():
    with pytest.raises(ai_summary.SummaryInvalid):
        ai_summary.parse_summary("esto no es JSON", {"consulta:1"})

    raw = json.dumps(
        {
            "resumen": "Resumen.",
            "padecimientos_registrados": [{"texto": "Inventado", "fuentes": ["consulta:999"]}],
        }
    )
    with pytest.raises(ai_summary.SummaryInvalid):
        ai_summary.parse_summary(raw, {"consulta:1"})


@pytest.mark.asyncio
async def test_reutiliza_el_resumen_si_no_cambia_la_entrada(db, monkeypatch):
    doctor, patient = await make_patient(db)

    class CountingClient:
        def __init__(self):
            self.calls = 0
            self.fake = FakeLlmClient()

        async def complete(self, system, user_json):
            self.calls += 1
            return await self.fake.complete(system, user_json)

    client = CountingClient()
    monkeypatch.setattr(ai_summary, "build_llm_client", lambda: client)

    first = await ai_summary.generate_summary(db, patient=patient, user=doctor)
    assert first.cached is False and client.calls == 1

    second = await ai_summary.generate_summary(db, patient=patient, user=doctor)
    assert second.cached is True and client.calls == 1

    db.add(
        Consultation(
            patient_id=patient.id,
            doctor_id=(await db.scalars(select(Doctor))).first().id,
            reason="Nueva consulta",
            diagnosis="Control",
        )
    )
    await db.flush()

    third = await ai_summary.generate_summary(db, patient=patient, user=doctor)
    assert third.cached is False and client.calls == 2


@pytest.mark.asyncio
async def test_no_deja_de_funcionar_si_el_proveedor_falla(db, monkeypatch):
    doctor, patient = await make_patient(db)

    class FailingClient:
        async def complete(self, system, user_json):
            raise AiUnavailable("sin proveedor")

    monkeypatch.setattr(ai_summary, "build_llm_client", lambda: FailingClient())

    with pytest.raises(AiUnavailable):
        await ai_summary.generate_summary(db, patient=patient, user=doctor)


@pytest.mark.asyncio
async def test_limite_horario_y_bitacora_sin_datos_clinicos(db, monkeypatch):
    doctor, patient = await make_patient(db)
    patient_id = patient.id

    for _ in range(3):
        db.add(
            AuditLog(
                user_id=doctor.id,
                action="portal_ai_summary",
                entity_type="patient",
                entity_id=str(patient_id),
            )
        )
    await db.flush()

    assert await ai_summary.hourly_summaries(db, doctor) == 3

    class CountingClient:
        def __init__(self):
            self.calls = 0
            self.fake = FakeLlmClient()

        async def complete(self, system, user_json):
            self.calls += 1
            return await self.fake.complete(system, user_json)

    client = CountingClient()
    monkeypatch.setattr(ai_summary, "build_llm_client", lambda: client)
    result = await ai_summary.generate_summary(db, patient=patient, user=doctor)

    detail = ai_summary.audit_detail(result)
    assert "modelo=" in detail and "registros=" in detail and "cache=" in detail
    assert "Hipertensión" not in detail
    assert "Matuz" not in detail


def test_solo_el_medico_puede_generar_el_resumen():
    class FakeRole:
        def __init__(self, codes):
            self.permissions = [type("P", (), {"code": code})() for code in codes]

    class FakeUser:
        def __init__(self, codes):
            self.role = FakeRole(codes)

    assert ai_summary.can_use_summary(FakeUser(ALL_PERMISSIONS)) is True
    assert ai_summary.can_use_summary(FakeUser(("portal:access", "patients:read"))) is False


def test_el_resumen_se_muestra_escapado():
    from app.portal.templating import templates

    html = templates.get_template("_ai_summary.html").render(
        patient=type("Paciente", (), {"id": 1})(),
        ai_summary_data={
            "resumen": "<script>alert('x')</script>",
            "padecimientos_registrados": [],
            "antecedentes_y_eventos": [],
            "estudios_relevantes": [],
            "tratamientos_registrados": [],
            "puntos_por_confirmar": [],
            "limitaciones": "",
        },
        ai_refs={},
        ai_generated_at=None,
        ai_records=1,
        ai_outdated=False,
        ai_con_ocr=False,
        ai_ocr_count=0,
        ai_ocr_enabled=False,
        ai_local=True,
        ai_message=None,
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_resumen_local_agrupa_diagnosticos_y_ordena_eventos():
    payload = {
        "paciente": {"edad_anios": 45, "grupo_sanguineo": "O+"},
        "consultas": [
            {
                "ref": "consulta:1",
                "fecha": "2026-09-01",
                "motivo": "Control",
                "diagnostico": "Hipertensión arterial",
                "notas": "Sin cambios.",
            },
            {
                "ref": "consulta:2",
                "fecha": "2026-10-01",
                "motivo": "Cefalea",
                "diagnostico": "Hipertensión arterial",
                "notas": "",
            },
            {
                "ref": "consulta:3",
                "fecha": "2026-10-05",
                "motivo": "Revisión",
                "diagnostico": "Diabetes tipo 2",
                "notas": "",
            },
        ],
    }

    data = build_local_summary(payload)

    diagnoses = [item["texto"] for item in data["padecimientos_registrados"]]
    assert any("2 consultas entre el 1 sep 2026 y el 1 oct 2026" in text for text in diagnoses)
    assert [item["fuentes"][0] for item in data["antecedentes_y_eventos"]] == [
        "consulta:1",
        "consulta:2",
        "consulta:3",
    ]
    assert "45 años" in data["resumen"] and "O+" in data["resumen"]


def test_resumen_local_marca_dosis_distintas_y_lee_pdf():
    payload = {
        "paciente": {"edad_anios": 50, "grupo_sanguineo": "A+"},
        "recetas": [
            {
                "ref": "receta:1",
                "fecha": "2026-09-01",
                "medicamentos": [
                    {"medicamento": "Losartán", "dosis": "50 mg", "frecuencia": "cada 24 h", "duracion": "30 días"}
                ],
            },
            {
                "ref": "receta:2",
                "fecha": "2026-10-01",
                "medicamentos": [
                    {"medicamento": "Losartán", "dosis": "100 mg", "frecuencia": "cada 24 h", "duracion": "30 días"}
                ],
            },
        ],
        "resultados_pdf": [
            {
                "ref": "documento:9",
                "titulo": "Resultado de laboratorio",
                "fecha": "2026-10-02",
                "texto": "Hemoglobina 14.2 g/dL. Sin alteraciones.",
            }
        ],
    }

    data = build_local_summary(payload)

    assert any("dosis distintas" in issue for issue in data["puntos_por_confirmar"])
    assert any("PDF" in item["texto"] for item in data["estudios_relevantes"])
    assert any("Losartán" in item["texto"] for item in data["tratamientos_registrados"])

    validated = ai_summary.parse_summary(
        json.dumps(data), {"receta:1", "receta:2", "documento:9"}
    )
    assert validated.resumen


def test_resumen_local_no_inventa_fuentes_ni_excede_limites():
    data = build_local_summary(
        {
            "paciente": {"edad_anios": 30},
            "consultas": [
                {
                    "ref": f"consulta:{index}",
                    "fecha": f"2026-09-{index:02d}",
                    "motivo": "Control",
                    "diagnostico": "Hipertensión",
                    "notas": "",
                }
                for index in range(1, 4)
            ],
        }
    )

    assert len(data["padecimientos_registrados"]) == 1
    assert all(item["fuentes"] for item in data["padecimientos_registrados"])
    assert len(data["resumen"]) <= 700
    assert len(data["limitaciones"]) <= 300


def test_extrae_el_texto_del_pdf_de_resultados():
    pdf = build_study_result_pdf(
        patient_name="Paciente de Prueba",
        patient_curp="TEST010101HCSRRN09",
        study_name="Biometría hemática",
        doctor_name="Dra. López",
        performer_name="laboratorio",
        result_text="Hemoglobina 14.2 g/dL, sin alteraciones.",
        requested_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        performed_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )

    text, method = extract_document_text(pdf, "application/pdf")

    assert method == "pdf"
    assert "Hemoglobina 14.2" in text
