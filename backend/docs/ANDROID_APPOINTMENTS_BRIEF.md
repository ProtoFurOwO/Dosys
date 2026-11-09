# Brief Android — solicitud de citas desde la app

No se actualizó la app en el VPS. Este documento es para que OpenCode local
implemente la pantalla y el consumo de los endpoints nuevos.

## Contexto

El backend ahora permite que el paciente **solicite** una cita. No reserva
directo: la cita queda `requested` y recepción la confirma. Hasta que se
confirme, no hay QR ni check-in.

Endpoints (la app ya usa base `.../api/v1/`):

```text
GET  appointments/doctors
GET  appointments/availability?doctor_id=3&date=2026-11-10
POST appointments/requests
GET  patients/me/appointments
```

### `GET appointments/doctors`

```json
[
  {"id": 3, "full_name": "Dr. Demo Médico", "specialty": "Medicina General"}
]
```

### `GET appointments/availability`

```json
{
  "doctor_id": 3,
  "date": "2026-11-10",
  "slots": [
    {"time": "08:00", "scheduled_at": "2026-11-10T14:00:00Z", "available": true},
    {"time": "08:30", "scheduled_at": "2026-11-10T14:30:00Z", "available": false}
  ]
}
```

### `POST appointments/requests`

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

Errores esperados:

- `409`: el paciente o el médico ya tienen otra cita en ese horario.
- `422`: fecha/hora inválida, domingo, fuera de 30 días o fuera de 08:00–19:00.
- `429`: demasiadas solicitudes; esperar un minuto.
- `404`: médico inactivo o inexistente.

## Prompt para OpenCode local

```text
Estoy en el repo Dosys, rama feat/clinical-ux-portal (o la rama que incluya los endpoints de citas).

Lee backend/docs/ANDROID_APPOINTMENTS_BRIEF.md e implementa la solicitud de citas desde la app.

Requisitos:
- No toques backend ni migraciones.
- Agrega modelos DTO: DoctorOption, AppointmentAvailabilitySlot, AppointmentAvailabilityResponse, AppointmentRequest.
- Extiende ApiService con:
  GET appointments/doctors
  GET appointments/availability?doctor_id=&date=
  POST appointments/requests
- Agrega un botón "Solicitar cita" en la pantalla de Citas.
- Flujo: elegir médico → elegir fecha → cargar horarios → elegir slot disponible → motivo → enviar.
- Muestra loading, error y confirmación. Maneja 409, 422 y 429 con mensajes claros.
- Después de enviar, refresca "Mis citas" y muestra la cita como "Solicitada".
- Agrega el estado REQUESTED al enum/mapeo de estados: Solicitada, Agendada, Confirmada, Atendida, Cancelada.
- Para status requested: no mostrar botón de QR/check-in; mostrar "Pendiente de confirmación por recepción".
- Cuando el backend devuelva confirmed, habilitar el QR/check-in existente.
- Mantén el diseño Compose actual.
- Agrega tests de mapeo de estados y de parseo de slots.
- Compila con ./gradlew :app:assembleDebug.
- Prueba con demo.paciente / Paciente123! contra el VPS.
```

## Flujo visual recomendado

### Pantalla Citas

- Header: “Mis citas” + botón **Solicitar cita**.
- Secciones:
  - Próximas: muestra `requested` como “Solicitada” con chip ámbar.
  - Confirmadas: chip verde, botón QR/check-in.
  - Historial.
- Empty state: “No tienes citas. Solicita una para comenzar.”

### Bottom sheet / wizard

1. **Médico**: lista de doctores activos con especialidad.
2. **Fecha**: date picker; deshabilitar domingos y fechas >30 días.
3. **Horario**: chips de 30 min; deshabilitar `available=false`.
4. **Motivo**: textarea opcional, máximo 300 caracteres.
5. **Confirmar solicitud**:
   - Muestra resumen: médico, fecha, hora, motivo.
   - Al enviar: spinner y bloqueo de doble envío.
   - Éxito: “Solicitud enviada. Recepción la confirmará.”
   - Error 409: “Ese horario acaba de ocuparse. Elige otro.”
   - Error 422: mensaje del servidor.
   - Error 429: “Espera un minuto antes de intentar de nuevo.”

## Seguridad que NO debes romper

- El paciente solo solicita para su propia cuenta; no envíes `patient_id`.
- No permitas escoger médicos inactivos.
- No inventes horarios: usa los slots del servidor.
- No habilites check-in para `requested`.
- Mantén el token en el almacenamiento seguro actual.
- No loguees tokens ni datos clínicos.
- No agregues lógica de reserva local/offline.

## Prueba de aceptación

1. Login `demo.paciente` / `Paciente123!`.
2. Solicitar cita con `Dr. Demo Médico`, fecha hábil, 09:30.
3. La app muestra “Solicitada”.
4. En portal, `demo.recepcion` ve la solicitud en Inicio/Agenda y confirma.
5. En la app, refrescar: la cita pasa a “Confirmada”.
6. El check-in/QR sigue bloqueado hasta que esté dentro de la ventana.
