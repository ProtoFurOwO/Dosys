"""Pruebas de la ruta del resumen con IA (sin red ni llave real)."""

import asyncio
import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "prueba-" + "x" * 40)
os.environ.setdefault("AI_ENABLED", "true")
os.environ.setdefault("AI_PROVIDER", "fake")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registra todas las tablas)
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services import ai_summary as ai_service
from app.services.llm_client import AiUnavailable

PERMISSIONS = (
    "portal:access",
    "patients:read",
    "consultations:read",
    "studies:read",
    "prescriptions:read",
    "documents:read",
    "ai:summary",
)


async def create_data(maker):
    async with maker() as db:
        permissions = {}
        for code in PERMISSIONS:
            permission = Permission(code=code, area="Prueba", action="lectura", description=code)
            db.add(permission)
            permissions[code] = permission

        doctor_role = Role(code="doctor", name="Médico", description=None, is_system=True)
        doctor_role.permissions = list(permissions.values())
        reception_role = Role(code="reception", name="Recepción", description=None, is_system=True)
        reception_role.permissions = [permissions["portal:access"], permissions["patients:read"]]
        db.add_all([doctor_role, reception_role])
        await db.flush()

        doctor_user = User(username="medico", password_hash="x", role_id=doctor_role.id)
        reception_user = User(username="recepcion", password_hash="x", role_id=reception_role.id)
        patient_user = User(username="paciente", password_hash="x", role_id=doctor_role.id)
        db.add_all([doctor_user, reception_user, patient_user])
        await db.flush()

        doctor = Doctor(user_id=doctor_user.id, full_name="Dra. López", specialty="Medicina General")
        patient = Patient(
            user_id=patient_user.id,
            full_name="José Antonio Matuz",
            curp="MAAJ010415HCSRRN09",
            blood_type="O+",
            birth_date=date(2001, 4, 15),
        )
        db.add_all([doctor, patient])
        await db.flush()
        db.add(
            Consultation(
                patient_id=patient.id,
                doctor_id=doctor.id,
                reason="Control de presión",
                diagnosis="Hipertensión en control",
            )
        )
        await db.commit()

        doctor_token, _ = create_access_token(
            doctor_user.id, doctor_role.code, sorted(PERMISSIONS)
        )
        reception_token, _ = create_access_token(
            reception_user.id, reception_role.code, ["portal:access", "patients:read"]
        )
        return {
            "patient_id": patient.id,
            "doctor_token": doctor_token,
            "reception_token": reception_token,
        }


@pytest.fixture()
def scenario(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dosys.db'}")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return await create_data(maker)

    data = asyncio.run(prepare())

    async def override_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, data
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def login_as(client, token):
    client.cookies.set("dosys_portal", token, path="/portal")


def test_404_si_la_ia_esta_desactivada(scenario, monkeypatch):
    client, data = scenario
    patient_id = data["patient_id"]
    login_as(client, data["doctor_token"])
    monkeypatch.setattr(settings, "ai_enabled", False)

    page = client.get(f"/portal/pacientes/{patient_id}")
    assert page.status_code == 200
    assert 'id="resumen-ia"' not in page.text

    blocked = client.post(
        f"/portal/pacientes/{patient_id}/resumen-ia",
        follow_redirects=False,
    )
    assert blocked.status_code == 404


def test_medico_genera_resumen_y_se_reutiliza(scenario):
    client, data = scenario
    patient_id = data["patient_id"]
    login_as(client, data["doctor_token"])

    page = client.get(f"/portal/pacientes/{patient_id}")
    assert page.status_code == 200
    assert 'id="resumen-ia"' in page.text
    assert "No es un diagnóstico" in page.text
    assert "modo local" in page.text

    generated = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert generated.status_code == 200
    assert "Resumen del expediente" in generated.text
    assert "Hipertensión en control" in generated.text

    repeated = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert "Sin cambios desde el último resumen" in repeated.text


def test_recepcion_no_ve_la_tarjeta_ni_puede_generarla(scenario):
    client, data = scenario
    patient_id = data["patient_id"]
    login_as(client, data["reception_token"])

    page = client.get(f"/portal/pacientes/{patient_id}")
    assert page.status_code == 200
    assert 'id="resumen-ia"' not in page.text

    denied = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert denied.status_code == 403


def test_limite_horario_no_llama_al_modelo(scenario, monkeypatch):
    client, data = scenario
    patient_id = data["patient_id"]
    login_as(client, data["doctor_token"])
    monkeypatch.setattr(settings, "ai_max_requests_per_user_hour", 1)

    first = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert "Resumen del expediente" in first.text

    second = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert "límite de resúmenes por hora" in second.text


def test_falla_del_proveedor_no_rompe_la_ficha(scenario, monkeypatch):
    client, data = scenario
    patient_id = data["patient_id"]
    login_as(client, data["doctor_token"])

    class FailingClient:
        async def complete(self, system, user_json):
            raise AiUnavailable("sin proveedor")

    monkeypatch.setattr(ai_service, "build_llm_client", lambda: FailingClient())

    response = client.post(f"/portal/pacientes/{patient_id}/resumen-ia")
    assert response.status_code == 200
    assert "No se pudo generar el resumen ahora" in response.text
    assert "No es un diagnóstico" in response.text
