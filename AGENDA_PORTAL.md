# Agenda y citas del portal

## Propósito

La Agenda sirve para consultar y administrar citas ya registradas. El agendamiento se inicia desde el expediente o desde la fila del paciente en **Citas**, no desde un espacio libre del calendario.

## Vistas y navegación

La página `/portal/agenda` ofrece tres formas de revisar las citas:

- **Por consultorios**: organiza las citas del día en tarjetas por consultorio. Cada tarjeta muestra paciente, horario, médico, especialidad y estado de check-in.
- **Matriz horaria**: distribuye las citas del día por horario y consultorio.
- **Vista semanal**: muestra las citas de lunes a domingo.

Las vistas comparten navegación por fecha y filtros de médico, consultorio y estado. La ruta GET `/portal/agenda` consulta las citas de la semana de la fecha seleccionada y prepara los datos para `agenda.html`. Requiere el permiso `appointments:read`.

## Detalle de una cita

En las tarjetas de la vista por consultorios, **Ver detalle** abre el modal `#modal-detalle`, definido en `backend/app/portal/templates/agenda.html`. El modal presenta datos del paciente y de la cita, el código de check-in, el estado de llegada y accesos al QR y al expediente. Incluye una **X** para cerrarlo.

El botón y los datos de la tarjeta se conectan en `backend/app/portal/static/portal.js`:

1. La plantilla expone los datos de la cita en atributos `data-*` y renderiza el botón `card-detail-button`.
2. Al pulsar el botón, JavaScript copia esos valores al modal, actualiza sus enlaces y prepara la acción del formulario de estado.
3. El modal se hace visible cambiando `aria-hidden` a `false`; al abrirse se evita el desplazamiento del contenido del fondo.
4. Se cierra con la X, al pulsar el fondo fuera del diálogo o con la tecla Escape.

El aspecto y los estados visible/oculto del modal están definidos en `backend/app/portal/static/portal.css`. El controlador está en el archivo JavaScript externo porque la política de seguridad del portal bloquea scripts integrados en las plantillas. `base.html` carga ese archivo y su versión de caché.

## Acciones y permisos

El formulario del modal permite cambiar estado y reasignar consultorio. Envía un POST a `/portal/agenda/citas/{appointment_id}/estado`, que requiere `appointments:write`; el servidor valida el estado, guarda los cambios, registra el evento de auditoría y vuelve a Agenda con un mensaje.

La agenda no ofrece un formulario para crear una cita desde una celda o espacio libre. Para agendar, se utiliza el enlace asociado al paciente y las rutas:

- GET `/portal/pacientes/{patient_id}/cita`: muestra el formulario del paciente.
- POST `/portal/pacientes/{patient_id}/cita`: valida y registra la cita.

Esos enlaces se ofrecen desde el detalle del paciente y desde la lista de Citas cuando el paciente no tiene cita pendiente y el usuario cuenta con permiso de escritura. La lista de Citas también permite buscar por nombre o CURP y abrir el QR de una cita pendiente.

## Archivos relacionados

- `backend/app/portal/templates/agenda.html`: vistas del calendario, tarjetas, botón y estructura del modal.
- `backend/app/portal/static/portal.js`: apertura y cierre del modal, además de las interacciones compartidas del portal.
- `backend/app/portal/static/portal.css`: estilos del botón y modal.
- `backend/app/portal/templates/appointments.html`: búsqueda y acciones por paciente en la lista de Citas.
- `backend/app/portal/templates/patient_detail.html`: acceso al agendamiento desde el expediente.
- `backend/app/portal/templates/base.html`: carga los recursos CSS y JavaScript del portal.
- `backend/app/portal/routes.py`: lectura de Agenda, actualización de estado y rutas de agendamiento.
