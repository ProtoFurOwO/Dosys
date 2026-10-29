"""Prueba de aceptación de la Agenda del portal.

Requiere el stack local levantado (`docker compose up -d --build`).
Verifica filtros por URL, las tres vistas, el modal, el cambio de estado,
la conservación de un consultorio fuera de 1–4 y la ausencia de "None" en
los atributos del modal.

Todos los datos son ficticios.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

BASE_URL = os.getenv("DOSYS_API_URL", "http://127.0.0.1:8000").rstrip("/")
USER_AGENT = "D.O.S.Y.S/1.0 (verificacion agenda)"
DOCTOR = {"username": "medico", "password": "Medico123!"}
BACKEND = Path(__file__).resolve().parents[1]


def main() -> None:
    # El template no debe volver a usar handlers inline bloqueados por CSP.
    template = (BACKEND / "app/portal/templates/agenda.html").read_text(encoding="utf-8")
    portal_js = (BACKEND / "app/portal/static/portal.js").read_text(encoding="utf-8")
    assert "onchange=" not in template, "agenda.html no debe usar onchange inline"
    assert 'id="agenda-date-form"' in template, "Falta el formulario de fecha"
    assert "agenda-date-form" in portal_js, "Falta el listener del selector de fecha"
    assert ".grid-apt-card" in portal_js, "Falta el listener de tarjetas de matriz/semana"
    assert "{{ apt.checked_in_label or '' }}" in template, "Falta el fallback de checked_in_label"

    with httpx.Client(
        base_url=BASE_URL,
        follow_redirects=True,
        timeout=30.0,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = client.post("/portal/login", data=DOCTOR)
        assert response.status_code == 200 and "Pacientes" in response.text, "El médico debe iniciar sesión"

        response = client.get("/portal")
        patient_id = None
        for row in response.text.split("<tr>"):
            if "Matuz" in row:
                match = re.search(r"/portal/pacientes/(\d+)", row)
                if match:
                    patient_id = int(match.group(1))
                    break
        assert patient_id, "No se encontró el paciente sembrado"

        marker = f"AGENDA-{datetime.now():%Y%m%d%H%M%S}"
        target_date = (datetime.now() + timedelta(days=8)).date()
        date_str = target_date.isoformat()
        response = client.post(
            f"/portal/pacientes/{patient_id}/cita",
            data={
                "specialty": "Cardiología",
                "fecha": date_str,
                "hora": "15:00",
                "location": "Consultorio 7",
                "notes": marker,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303, "No se pudo crear la cita de prueba"
        location = response.headers.get("location", "")
        match = re.search(r"creada=(\d+)", location)
        assert match, "No se encontró el id de la cita creada"
        appointment_id = int(match.group(1))
        response = client.get(location)
        assert response.status_code == 200 and "Cita agendada" in response.text, (
            "La cita creada no aparece en la lista"
        )

        response = client.get(f"/portal/agenda?vista=tablero&fecha={date_str}")
        tablero = response.text
        assert response.status_code == 200 and "modal-detalle" in tablero, "La agenda no abrió"
        assert "agenda-filters" in tablero and "agenda-date-form" in tablero
        assert marker in tablero, "La cita creada no aparece en la agenda"
        assert "Consultorio 7" in tablero, "La agenda perdió el Consultorio 7"
        assert 'data-checked-in="None"' not in tablero, "El modal todavía renderiza None"
        assert re.search(r"Consultorio 7.{0,5000}" + re.escape(marker), tablero, re.S), (
            "La cita no está en la columna Consultorio 7"
        )

        for view in ("cuadricula", "semana"):
            response = client.get(f"/portal/agenda?vista={view}&fecha={date_str}")
            assert response.status_code == 200 and marker in response.text, (
                f"La vista {view} no muestra la cita"
            )
            assert "grid-apt-card" in response.text, f"La vista {view} no tiene tarjetas clicables"

        response = client.get(
            f"/portal/agenda?vista=tablero&fecha={date_str}&consultorio=Consultorio%207"
        )
        assert response.status_code == 200 and marker in response.text, (
            "El filtro por Consultorio 7 no devuelve la cita"
        )
        response = client.get(
            f"/portal/agenda?vista=tablero&fecha={date_str}&consultorio=Consultorio%201"
        )
        assert response.status_code == 200 and marker not in response.text, (
            "El filtro por Consultorio 1 no debe incluir la cita"
        )

        response = client.post(
            f"/portal/agenda/citas/{appointment_id}/estado",
            data={
                "nuevo_estado": "confirmed",
                "nuevo_consultorio": "Consultorio 7",
                "fecha": date_str,
                "vista": "tablero",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303 and "aviso=Cita+actualizada" in response.headers.get("location", ""), (
            "No se pudo actualizar la cita"
        )
        response = client.get(f"/portal/agenda?vista=tablero&fecha={date_str}")
        assert response.status_code == 200 and marker in response.text and "Consultorio 7" in response.text, (
            "Guardar el estado perdió el Consultorio 7"
        )

        response = client.post(
            f"/portal/agenda/citas/{appointment_id}/estado",
            data={
                "nuevo_estado": "confirmed",
                "nuevo_consultorio": "Consultorio 99",
                "fecha": date_str,
                "vista": "tablero",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303 and "error=Consultorio+no" in response.headers.get("location", ""), (
            "Se aceptó un consultorio inexistente"
        )
        response = client.get(f"/portal/agenda?vista=tablero&fecha={date_str}")
        assert response.status_code == 200 and marker in response.text and "Consultorio 7" in response.text, (
            "El rechazo de consultorio alteró la cita"
        )

        response = client.get("/portal/actividad")
        assert response.status_code == 200 and (
            "portal_read_agenda" in response.text or "Agenda" in response.text
        ), "La bitácora no registra la agenda"

    print(json.dumps({
        "agenda": "ok",
        "appointment_id": appointment_id,
        "date": date_str,
        "consultorio": "Consultorio 7",
        "views": ["tablero", "cuadricula", "semana"],
        "filters_url": True,
        "modal_none_fixed": True,
        "status_update": True,
        "invalid_room_rejected": True,
        "audit": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
