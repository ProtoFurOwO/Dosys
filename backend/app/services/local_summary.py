"""Resumen local del expediente, sin red ni proveedor externo.

Agrupa diagnósticos y tratamientos repetidos, ordena los eventos, incorpora el
texto de los PDF de resultados y marca inconsistencias con reglas explícitas.
Es apoyo documental: no interpreta datos que no estén escritos ni sustituye el
criterio médico.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
MAX_ITEMS = 12
MAX_ITEM_TEXT = 300
MAX_SUMMARY = 700
MAX_ISSUES = 8

ESTADOS = {
    "requested": "solicitado",
    "in_progress": "en proceso",
    "completed": "listo sin resultado",
    "cancelled": "cancelado",
}

SUSPENSION_WORDS = ("suspender", "suspension", "suspendio", "se suspende", "suspenda")
NO_TREATMENT_WORDS = ("sin tratamiento", "no requiere tratamiento", "sin medicacion")
NORMAL_WORDS = ("sin alteraciones", "normal", "negativo")
ALTERED_WORDS = ("alterad", "elevad", "positivo", "anormal")


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").lower())
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).split())


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _date_label(value: str | None) -> str:
    if not value:
        return "fecha no registrada"
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.day} {MESES[parsed.month - 1]} {parsed.year}"


def _truncate(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].strip()
    return (cut or text[: limit - 1]).rstrip(".,;:") + "…"


def _item(text: str, refs: list[str]) -> dict[str, Any] | None:
    refs = [ref for ref in dict.fromkeys(refs) if ref]
    text = _truncate(_clean(text), MAX_ITEM_TEXT)
    if not text or not refs:
        return None
    return {"texto": text, "fuentes": refs[:6]}


def _source_refs(refs: list[str]) -> list[str]:
    unique = [ref for ref in dict.fromkeys(refs) if ref]
    if len(unique) <= 6:
        return unique
    return unique[:3] + unique[-3:]


def _diagnoses(consultas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for consulta in consultas:
        label = _clean(consulta.get("diagnostico"))
        if not label:
            continue
        entry = groups.setdefault(_norm(label), {"label": label, "refs": [], "dates": []})
        entry["refs"].append(consulta.get("ref"))
        entry["dates"].append(consulta.get("fecha") or "")

    items = []
    for entry in sorted(groups.values(), key=lambda item: min(item["dates"] or [""])):
        dates = sorted(value for value in entry["dates"] if value)
        count = len(entry["refs"])
        if count == 1:
            text = f"{entry['label']} (consulta del {_date_label(dates[0] if dates else '')})."
        else:
            text = (
                f"{entry['label']}: {count} consultas entre el "
                f"{_date_label(dates[0] if dates else '')} y el {_date_label(dates[-1] if dates else '')}."
            )
        item = _item(text, _source_refs(entry["refs"]))
        if item:
            items.append(item)
    return items[:MAX_ITEMS]


def _events(consultas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(consultas, key=lambda consulta: consulta.get("fecha") or "")
    items = []
    for consulta in ordered[-MAX_ITEMS:]:
        parts = []
        motivo = _clean(consulta.get("motivo"))
        diagnostico = _clean(consulta.get("diagnostico"))
        notas = _clean(consulta.get("notas"))
        if motivo:
            parts.append(f"Motivo: {motivo}")
        if diagnostico:
            parts.append(f"Diagnóstico: {diagnostico}")
        if notas and len(notas) <= 100:
            parts.append(f"Notas: {notas}")
        body = ". ".join(parts) or "Consulta registrada sin detalle."
        item = _item(f"{_date_label(consulta.get('fecha'))} · {body}.", [consulta.get("ref")])
        if item:
            items.append(item)
    return items


def _studies(estudios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for estudio in estudios:
        label = _clean(estudio.get("estudio")) or "Estudio"
        entry = groups.setdefault(
            _norm(label),
            {"label": label, "refs": [], "result": "", "result_date": "", "last_date": "", "estado": ""},
        )
        entry["refs"].append(estudio.get("ref"))
        fecha = estudio.get("fecha") or ""
        result = _clean(estudio.get("resultado"))
        if result and (not entry["result_date"] or fecha >= entry["result_date"]):
            entry["result"] = result
            entry["result_date"] = fecha
        if fecha >= (entry["last_date"] or ""):
            entry["last_date"] = fecha
            entry["estado"] = estudio.get("estado") or ""

    items = []
    for entry in groups.values():
        if entry["result"]:
            text = (
                f"{entry['label']} ({_date_label(entry['result_date'] or entry['last_date'])}): "
                f"{entry['result'][:220]}"
            )
        else:
            estado = ESTADOS.get(entry["estado"], entry["estado"] or "sin resultado")
            text = f"{entry['label']} ({_date_label(entry['last_date'])}): {estado}."
        item = _item(text, _source_refs(entry["refs"]))
        if item:
            items.append(item)
    return items[:MAX_ITEMS]


def _pdf_items(resultados_pdf: list[dict[str, Any]], estudios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    already = [
        _norm(estudio.get("resultado"))
        for estudio in estudios
        if len(_norm(estudio.get("resultado"))) >= 20
    ]
    items = []
    seen: set[str] = set()
    for documento in resultados_pdf:
        text = _clean(documento.get("texto"))
        if not text:
            continue
        normalized = _norm(text)
        # Si el PDF corresponde a un resultado ya resumido, no se repite.
        if any(result in normalized for result in already):
            continue
        key = normalized[:120]
        if key in seen:
            continue
        seen.add(key)
        titulo = _clean(documento.get("titulo")) or "resultado"
        item = _item(
            f"PDF «{titulo}» ({_date_label(documento.get('fecha'))}): {text[:200]}",
            [documento.get("ref")],
        )
        if item:
            items.append(item)
    return items


def _treatments(recetas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for receta in recetas:
        fecha = receta.get("fecha") or ""
        for medicamento in receta.get("medicamentos") or []:
            name = _clean(medicamento.get("medicamento"))
            if not name:
                continue
            entry = groups.setdefault(
                (_norm(name), _norm(medicamento.get("dosis"))),
                {"label": name, "dose": _clean(medicamento.get("dosis")), "freqs": [], "refs": [], "dates": []},
            )
            freq = _clean(medicamento.get("frecuencia"))
            if freq and _norm(freq) not in {_norm(value) for value in entry["freqs"]}:
                entry["freqs"].append(freq)
            entry["refs"].append(receta.get("ref"))
            entry["dates"].append(fecha)

    items = []
    for entry in groups.values():
        dates = sorted(value for value in entry["dates"] if value)
        detail = f"{entry['label']} {entry['dose']}".strip()
        if entry["freqs"]:
            detail += f", {', '.join(entry['freqs'][:2])}"
        total = len({ref for ref in entry["refs"] if ref})
        if dates:
            span = (
                _date_label(dates[0])
                if len(dates) == 1
                else f"{_date_label(dates[0])} – {_date_label(dates[-1])}"
            )
            detail += f" ({total} receta(s), {span})"
        else:
            detail += f" ({total} receta(s))"
        item = _item(detail + ".", _source_refs(entry["refs"]))
        if item:
            items.append(item)
    return items[:MAX_ITEMS]


def _issues(payload: dict[str, Any]) -> list[str]:
    consultas = payload.get("consultas") or []
    estudios = payload.get("estudios") or []
    recetas = payload.get("recetas") or []
    patient = payload.get("paciente") or {}
    issues: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        if text in seen or len(issues) >= MAX_ISSUES:
            return
        seen.add(text)
        issues.append(text)

    # Mismo medicamento con dosis o frecuencia distintas.
    by_med: dict[str, dict[str, Any]] = {}
    for receta in recetas:
        for medicamento in receta.get("medicamentos") or []:
            name = _clean(medicamento.get("medicamento"))
            if not name:
                continue
            entry = by_med.setdefault(_norm(name), {"label": name, "doses": [], "freqs": []})
            for field, values in (("dosis", "doses"), ("frecuencia", "freqs")):
                value = _clean(medicamento.get(field))
                if value and _norm(value) not in {_norm(item) for item in entry[values]}:
                    entry[values].append(value)
    for entry in by_med.values():
        if len(entry["doses"]) > 1:
            add(
                f"«{entry['label']}» aparece con dosis distintas: "
                f"{', '.join(entry['doses'][:4])}. Verifica la indicación vigente."
            )
        if len(entry["freqs"]) > 1:
            add(
                f"«{entry['label']}» aparece con frecuencias distintas: "
                f"{', '.join(entry['freqs'][:4])}. Verifica la indicación vigente."
            )

    # Notas que niegan tratamiento o mencionan suspenderlo, con receta posterior.
    for receta in recetas:
        if not receta.get("medicamentos"):
            continue
        fecha = receta.get("fecha") or ""
        for consulta in consultas:
            notes = _norm(consulta.get("notas"))
            if any(word in notes for word in NO_TREATMENT_WORDS) and (consulta.get("fecha") or "") <= fecha:
                add(
                    f"Una nota del {_date_label(consulta.get('fecha'))} indica que no hay tratamiento, "
                    f"pero existe una receta del {_date_label(fecha)}."
                )
                break
        for medicamento in receta.get("medicamentos") or []:
            name = _clean(medicamento.get("medicamento"))
            key = _norm(name)
            if len(key) < 4:
                continue
            for consulta in consultas:
                notes = _norm(consulta.get("notas"))
                if (
                    key in notes
                    and any(word in notes for word in SUSPENSION_WORDS)
                    and (consulta.get("fecha") or "") <= fecha
                ):
                    add(
                        f"Las notas del {_date_label(consulta.get('fecha'))} mencionan suspender «{name}», "
                        f"pero hay una receta del {_date_label(fecha)} que lo incluye."
                    )
                    break

    for estudio in estudios:
        name = _clean(estudio.get("estudio")) or "Estudio"
        result = _norm(estudio.get("resultado"))
        if estudio.get("estado") == "completed" and not result:
            add(f"El estudio «{name}» figura listo pero sin resultado registrado.")
        if result and any(word in result for word in NORMAL_WORDS) and any(
            word in result for word in ALTERED_WORDS
        ):
            add(
                f"El resultado de «{name}» mezcla frases de normalidad y de alteración; "
                "conviene confirmarlo en el expediente."
            )

    if not patient.get("grupo_sanguineo"):
        add("No consta el grupo sanguíneo del paciente.")
    if patient.get("edad_anios") is None:
        add("No consta la fecha de nacimiento del paciente.")
    sin_notas = sum(1 for consulta in consultas if not _clean(consulta.get("notas")))
    if sin_notas:
        add(f"{sin_notas} consulta(s) no tienen notas registradas.")
    sin_resultado = sum(1 for estudio in estudios if not _clean(estudio.get("resultado")))
    if sin_resultado:
        add(f"{sin_resultado} estudio(s) no tienen resultado registrado.")
    if not consultas:
        add("No hay consultas registradas en el expediente.")

    return issues[:MAX_ISSUES]


def _summary(payload: dict[str, Any], pdf_items: list[dict[str, Any]]) -> str:
    consultas = payload.get("consultas") or []
    estudios = payload.get("estudios") or []
    recetas = payload.get("recetas") or []
    patient = payload.get("paciente") or {}
    parts: list[str] = []

    age = patient.get("edad_anios")
    blood = _clean(patient.get("grupo_sanguineo"))
    if age is not None:
        head = f"Paciente de {age} años"
        if blood:
            head += f", grupo sanguíneo {blood}"
        parts.append(head + ".")
    elif blood:
        parts.append(f"Grupo sanguíneo {blood}.")

    if consultas:
        dates = sorted(consulta.get("fecha") for consulta in consultas if consulta.get("fecha"))
        span = ""
        if dates:
            span = (
                f" del {_date_label(dates[0])}"
                if len(dates) == 1
                else f" entre el {_date_label(dates[0])} y el {_date_label(dates[-1])}"
            )
        sentence = f"Constan {len(consultas)} consultas{span}"
        last_motive = _clean(consultas[-1].get("motivo"))
        if last_motive:
            sentence += f"; el último motivo registrado fue «{last_motive}»"
        parts.append(sentence + ".")
    else:
        parts.append("No constan consultas registradas.")

    labels: list[str] = []
    for consulta in consultas:
        label = _clean(consulta.get("diagnostico"))
        if label and _norm(label) not in {_norm(item) for item in labels}:
            labels.append(label)
    if labels:
        parts.append("Diagnósticos registrados: " + "; ".join(labels[:3]) + ".")

    counts = []
    if estudios:
        counts.append(f"{len(estudios)} estudios")
    if recetas:
        counts.append(f"{len(recetas)} recetas")
    if counts:
        sentence = "Se registran " + " y ".join(counts)
        if pdf_items:
            sentence += f"; además, {len(pdf_items)} PDF de resultados del expediente"
        parts.append(sentence + ".")
    elif pdf_items:
        parts.append(f"Se leyó {len(pdf_items)} PDF de resultados del expediente.")

    parts.append("Resumen generado en el servidor con reglas locales; verifica cada dato en el expediente.")
    return _truncate(" ".join(parts), MAX_SUMMARY)


def build_local_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Devuelve un resumen conforme al esquema, sin llamar a ningún modelo."""
    consultas = payload.get("consultas") or []
    estudios = payload.get("estudios") or []
    recetas = payload.get("recetas") or []
    resultados_pdf = payload.get("resultados_pdf") or []

    diagnoses = _diagnoses(consultas)
    events = _events(consultas)
    pdf_items = _pdf_items(resultados_pdf, estudios)
    studies = (_studies(estudios) + pdf_items)[:MAX_ITEMS]
    treatments = _treatments(recetas)

    return {
        "resumen": _summary(payload, pdf_items),
        "padecimientos_registrados": diagnoses,
        "antecedentes_y_eventos": events,
        "estudios_relevantes": studies,
        "tratamientos_registrados": treatments,
        "puntos_por_confirmar": _issues(payload),
        "limitaciones": _truncate(
            "Resumen local por reglas: agrupa lo registrado y marca inconsistencias, "
            "pero no interpreta datos que no consten por escrito ni sustituye el criterio médico.",
            300,
        ),
    }
