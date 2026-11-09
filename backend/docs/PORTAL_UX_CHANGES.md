# Cambios de flujo clínico y UX — 2026-11-09

## Backup / rollback

Carpeta:

```text
/home/ubuntu/Dosys/backups/rollback-20261109-040825/
```

Contiene:

- `dosys-backend-code.tar.gz` — código previo al rediseño.
- `dosys-db.dump` — PostgreSQL custom dump previo a la migración 0013.
- `.env.backup` — variables de producción (modo 600).
- `README.md` — comandos de restauración.
- `alembic-version.txt` — `20261105_0012`.
- `health.json`, `image-id.txt`.

Restauración probada: el dump se restauró en `dosys_restore_test` y coincidió
en usuarios, pacientes, consultas y citas con el estado del respaldo.

## Implementado

### 1. Dashboard por rol (`/portal/inicio`)

- Recepción: citas de hoy, sala de espera, pacientes.
- Médico: agenda, espera, consultas recientes, estudios pendientes, actividad.
- Laboratorio: estudios pendientes y pacientes.
- Administración: pacientes, usuarios, actividad.
- Login y 2FA redirigen al dashboard.
- Navegación con “Inicio” y rol visible en la barra lateral.

### 2. Consulta SOAP + signos vitales

Migración `20261109_0013` agregada a `consultations`:

- `blood_pressure`, `heart_rate`, `respiratory_rate`, `temperature_c`,
  `oxygen_saturation`, `weight_kg`, `height_cm`, `physical_exam`.

Formulario:

- S · Subjetivo: motivo.
- O · Objetivo: signos vitales, IMC en vivo y exploración física.
- A · Análisis: diagnóstico.
- P · Plan: indicaciones, estudios, receta y próxima cita.
- Validación de rangos y formato de presión.
- Corrección de consultas con los mismos campos.

### 3. Línea de tiempo clínica

En el expediente, para roles con `consultations:read`:

- Consultas, estudios, recetas y documentos, ordenados por fecha.
- Recepción/laboratorio no ven el historial ni las alertas clínicas.

### 4. Flujo visual de cita

- Agendada → Confirmada → En espera → Atendida.
- Estado actual y pasos completados en `/portal/citas/{id}`.

### 5. Nota de consulta PDF

- `GET /portal/pacientes/{id}/consulta/{cid}/pdf`.
- Solo roles con `consultations:read`.
- Incluye SOAP, signos vitales, IMC y firma del médico.
- Descarga auditada.

### 6. UX / accesibilidad

- Botones con estado “Guardando…” para evitar dobles envíos.
- Foco visible, `aria-live`, etiquetas y ayuda contextual.
- Responsive para dashboard, vitales, timeline y flujo de cita.
- Estilos de impresión.

## Verificación ejecutada

| Prueba | Resultado |
|---|---|
| `/health` | 200, DB ok |
| Migración | `20261109_0013` aplicada |
| Login portal | 303 → `/portal/inicio` |
| Dashboards recepción/médico/lab/admin | 200 |
| Consulta POST con vitales | 303, fila en DB |
| Detalle médico | muestra SOAP, vitales, timeline |
| Detalle recepción | oculta datos clínicos |
| Recepción PDF de nota | 403 |
| Médico PDF de nota | 200 `application/pdf` |
| API app `/me/consultations` | 200 con campos nuevos |
| QR de cita | stepper visible |
| Laboratorio | cola y botones visibles |
| Errores 500 recientes | ninguno |

## Archivos principales

- `app/portal/routes.py`
- `app/portal/templates/dashboard.html`
- `app/portal/templates/consultation_form.html`
- `app/portal/templates/consultation_edit.html`
- `app/portal/templates/patient_detail.html`
- `app/portal/templates/appointment_qr.html`
- `app/portal/static/portal.css`
- `app/portal/static/portal.js`
- `app/models/consultation.py`
- `app/services/consultations.py`
- `app/services/reports.py`
- `app/api/routes/patients.py`
- `app/schemas/consultation.py`
- `alembic/versions/20261109_0013_consultation_vitals.py`
- `docs/PORTAL_CLINICAL_UX.md`
- `docs/ANDROID_UPDATE_BRIEF.md`

## Android

No se modificó en el VPS. Brief para OpenCode local:

```text
docs/ANDROID_UPDATE_BRIEF.md
```

El backend es compatible: los campos nuevos son opcionales y la app anterior
sigue funcionando.
