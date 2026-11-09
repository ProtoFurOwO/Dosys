# Flujo de citas y agenda — decisión de producto

Fecha: 2026-11-09

## Problema encontrado

1. Recepción podía abrir el formulario de cita, pero el `POST` exigía que la
   cuenta tuviera ficha de médico (`isinstance(doctor, Doctor)`). Por eso
   recepción recibía 403 al guardar.
2. El formulario no permitía elegir médico; usaba siempre al usuario logueado.
3. El paciente no tenía forma de solicitar una cita desde la app.
4. No existía un estado “solicitada”: cualquier cita nacía agendada, sin control
   de recepción.

## Referencias

- Autoservicio de pacientes y ventajas operativas:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC8790681/>
- Buenas prácticas de agenda, buffers y autoservicio:
  <https://www.phreesia.com/blog-patient-scheduling-10-best-practices-for-peak-efficiency/>
- Autoservicio vs solicitud y requisitos de privacidad:
  <https://doctorconnect.net/self-scheduling-vs-request-based-choosing-the-right-strategy>
- Seguridad/HIPAA en agenda:
  <https://www.accountablehq.com/post/hipaa-compliant-appointment-scheduling-requirements-best-practices-and-tools>
- Check-in y flujo de recepción:
  <https://harriscaretracker.com/front-desk-efficiency-tips-to-streamline-check-in-and-scheduling/>
- Innovación en scheduling y reducción de tiempos:
  <https://nam.edu/perspectives/innovation-and-best-practices-in-health-care-scheduling/>

## Decisión

Se implementó un modelo **request-based** (solicitud + confirmación), no
reserva directa. Es más seguro para una clínica:

- El paciente elige médico, fecha, horario disponible y motivo.
- El servidor crea una cita en estado `requested`.
- Recepción revisa y confirma; hasta entonces no hay QR ni check-in.
- El paciente ve el estado en la app.

Ventajas:

- Evita que un paciente invente horarios o bloquee la agenda.
- Recepción conserva el control de consultorios y excepciones.
- Deja trazabilidad de quién solicitó, quién confirmó y cuándo.
- Permite crecer después a reserva inmediata si la clínica lo decide.

## Flujo operativo

### Recepción

1. `Pacientes` → paciente → `Agendar cita`.
2. Elige **médico** (ahora sí), especialidad, fecha, hora y consultorio.
3. El servidor valida empalmes de médico, paciente y consultorio.
4. La cita nace `scheduled`.
5. En `Citas`/`Agenda` puede confirmar, asignar consultorio y abrir el QR.
6. Las solicitudes de la app aparecen en `Inicio` → **Solicitudes de cita** y
   en `Agenda` con filtro `Solicitadas`.
7. Abre la solicitud → `Confirmar cita` → se habilita el check-in.

### Médico

1. Ve su agenda y sala de espera.
2. Puede agendar para un paciente eligiendo médico (por defecto él mismo).
3. Confirma o atiende; el flujo de consulta no cambia.

### Paciente (app)

1. `Solicitar cita`.
2. Elige médico de la lista de médicos activos.
3. Consulta horarios disponibles (08:00–19:00, intervalos de 30 min).
4. Envía fecha, hora y motivo.
5. La cita queda `requested` y sin QR.
6. Cuando recepción confirma, la app la muestra como `confirmed` y habilita el
   check-in dentro de la ventana.

## Reglas de seguridad y negocio

- Solo el paciente autenticado puede solicitar para su propio expediente.
- Solo médicos activos (`users.is_active`) aparecen y aceptan solicitudes.
- Fecha entre hoy y 30 días; domingos cerrados.
- Horario 08:00–19:00, intervalos de 30 minutos.
- No se permiten empalmes de médico, paciente ni consultorio.
- La especialidad se toma del perfil del médico; el cliente no puede inventarla.
- Rate limit por IP en solicitudes.
- Auditoría: `patient_request_appointment`, `portal_confirm_appointment`.
- La solicitud no genera QR ni permite check-in (`checkin_reason=requested`).
- El paciente no puede ver citas de otros pacientes ni la agenda completa.

## Endpoints nuevos

```text
GET  /api/v1/appointments/doctors
GET  /api/v1/appointments/availability?doctor_id=3&date=YYYY-MM-DD
POST /api/v1/appointments/requests
```

### Solicitud

```json
{
  "doctor_id": 3,
  "specialty": "Medicina General",
  "date": "2026-11-10",
  "time": "09:30",
  "reason": "Dolor lumbar de una semana"
}
```

Respuesta `201`:

```json
{
  "id": 10,
  "status": "requested",
  "is_upcoming": true,
  "checkin_available": false,
  "checkin_reason": "requested"
}
```

## Pendientes / siguiente iteración

- Cancelación/reprogramación desde la app.
- Recordatorios 24/48 h por correo/push.
- Lista de espera y reasignación automática.
- Política de no-show.
- Bloqueos de agenda por vacaciones o cirugías.
- Duración de cita configurable por especialidad (hoy 30 min fijos).
- Android: pantalla de solicitud y manejo del estado `requested`
  (ver `ANDROID_APPOINTMENTS_BRIEF.md`).
