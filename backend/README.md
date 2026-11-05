# D.O.S.Y.S API + Portal clínico

Backend académico con **FastAPI + SQLAlchemy async + Alembic + PostgreSQL** y un
**portal clínico** para el personal médico servido por el mismo backend.
**Todos los datos sembrados son ficticios de demostración.**

## Qué incluye

- JWT de corta duración con roles `patient`, `doctor`, `laboratory` y `reception`.
- Autorización en servidor: el paciente solo consulta su propio perfil, citas y consultas.
- **API REST** para la app Android: login, perfil, citas y consultas del paciente; lista de
  pacientes y registro de consultas para el médico.
- **Portal clínico** (`/portal`) para el personal médico: acceso, listado y búsqueda de
  pacientes, expediente con historial, nueva consulta, alta y edición de pacientes,
  agenda de citas con QR, gestión de usuarios (médicos) y bitácora de actividad.
- **Check-in con QR**: el portal muestra un código por cita y la app del paciente lo
  escanea con la cámara para confirmar su llegada.
- **Registro de cuentas**: el médico da de alta pacientes y médicos; el sistema genera la
  credencial (se muestra una vez, se puede imprimir y se simula su envío por correo).
- **Login seguro**: bloqueo de la cuenta tras 5 intentos fallidos (con desbloqueo desde el
  portal), **segundo factor TOTP** (Google Authenticator y similares) para médicos y
  pacientes, y **códigos de recuperación** de un solo uso.
- **Transferencia de sesión entre dispositivos** para la app del paciente: un solo teléfono
  de confianza, código OTP generado localmente (60 s) y aprobación criptográfica; funciona
  sin Firebase (sondeo) y mejora con FCM.
- PostgreSQL aislado, migraciones Alembic versionadas y bitácora de auditoría de todos
  los accesos, sin guardar tokens ni texto clínico.

## Arranque local

Requisitos: Docker Desktop iniciado y Docker Compose v2.

```powershell
cd backend
Copy-Item .env.example .env
# Edita .env y cambia POSTGRES_PASSWORD y JWT_SECRET_KEY por valores propios.
docker compose up -d --build
```

Comprueba la salud:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Resultado esperado: `status = ok` y `database = ok`.

> Si el puerto 8000 está ocupado, define `API_PORT=8100` antes de `docker compose up`
> y usa esa base en los scripts (`DOSYS_API_URL=http://127.0.0.1:8100`).

Para detener los servicios sin borrar la base local: `docker compose down`.

## Portal clínico

Abre `http://127.0.0.1:8000/portal` e inicia sesión con `medico` / `Medico123!`.

1. **Pacientes**: buscador por nombre o CURP, métricas reales, alta de pacientes con
   credencial de acceso (mostrar una vez, imprimir y envío simulado por correo) y edición
   de sus datos, incluidas **alergias, antecedentes y diagnósticos crónicos**.
2. **Expediente**: datos del paciente, alertas clínicas e historial de consultas en orden
   cronológico. Una consulta ya firmada se puede **corregir** con auditoría.
3. **Nueva consulta**: motivo, diagnóstico, notas, estudios de laboratorio/imagen, receta
   y próxima cita. Los errores se muestran en un resumen al inicio del formulario.
4. **Agendar cita**: fecha, hora, especialidad y consultorio; el sistema genera un código
   de check-in único por cita y rechaza empalmes de paciente, médico o consultorio.
5. **Citas**: solo las citas futuras aparecen como próximas; las pasadas quedan en el
   historial. El QR muestra su ventana de validez (2 h antes a 4 h después).
6. **En espera y laboratorio**: cola de estudios con filtros, inicio, captura de resultado
   y PDF con huella SHA-256.
7. **Usuarios**: alta y edición de médicos, activar/desactivar cuentas y restablecer
   contraseñas (siempre mostrando la credencial una vez).
8. **Actividad**: bitácora con filtros por acción, usuario, entidad, texto y fechas,
   paginación y exportación CSV auditada.

Cada cita agendada desde el portal aparece también en la app del paciente, y cada paciente
registrado puede iniciar sesión de inmediato en la app con la credencial que se genera.

Credenciales exclusivamente locales/de demostración:

| Rol | Usuario | Contraseña |
|---|---|---|
| Paciente (app) | `paciente` | `Paciente123!` |
| Médico (portal) | `medico` | `Medico123!` |
| Administrador | `admin` | `Admin123!` |
| Laboratorio | `laboratorio` | `Lab12345!` |
| Recepción | `recepcion` | `Recepcion123!` |

## Expediente clínico, check-in y laboratorio

### Datos clínicos del paciente

La migración `20261105_0012_clinical_record.py` agrega a `patients`:

- `allergies` (texto libre)
- `medical_history` (antecedentes)
- `chronic_conditions` (diagnósticos crónicos)

Se capturan al crear o editar al paciente y se muestran en el expediente y en la app. El
endpoint `GET /api/v1/patients/me` los devuelve. La edición requiere `patients:write` y
registra en la bitácora **solo los nombres de los campos modificados**, nunca el contenido
clínico.

### Corrección de consultas

`GET/POST /portal/pacientes/{id}/consulta/{consulta_id}/editar` permite a un médico con
ficha corregir motivo, diagnóstico y notas. La consulta conserva `created_at`, se marca
`updated_at` y la bitácora registra `portal_update_consultation` con
`campos=reason,diagnosis,...`. No se borra ni se sobrescribe el registro original sin
dejar rastro.

### Check-in con ventana y un solo uso

- El check-in abre **2 horas antes** y cierra **4 horas después** de la cita
  (`CHECKIN_WINDOW_BEFORE_MINUTES` y `CHECKIN_WINDOW_AFTER_MINUTES`).
- `GET /api/v1/patients/me/appointments` incluye `is_upcoming`, `checkin_available`,
  `checkin_opens_at`, `checkin_closes_at` y `checkin_reason`.
- `POST /api/v1/patients/me/check-in` acepta solo el código y busca la cita vigente del
  paciente. El endpoint anterior con `appointment_id` se conserva.
- Un código incorrecto responde **400**; una cita cancelada, atendida o fuera de ventana
  responde **409** con el motivo. La operación es idempotente.
- Límite de **10 intentos por minuto por IP** (`429`).
- Portal: el QR muestra la ventana, se actualiza solo y permite **reabrir el check-in** si
  recepción se equivocó (auditado).

### Laboratorio

- `POST /portal/pacientes/{id}/estudio-demo` crea una **orden real** sin consulta previa,
  pensada para demostrar la cola en clase. Requiere ficha de médico y `studies:request`.
- La cola tiene filtros por paciente/CURP/estudio y por estado; `Iniciar` pasa a
  `in_progress`; `Capturar resultado` genera el PDF con SHA-256.
- Todo queda auditado: `portal_create_demo_study_order`, `portal_start_study_order`,
  `portal_complete_study_order` y `portal_cancel_study_order`.

### Bitácora

`/portal/actividad` filtra por acción, usuario, entidad, texto libre y rango de fechas,
pagina de 50 en 50 y exporta CSV. La exportación también se audita
(`portal_export_activity`). Los identificadores y detalles se muestran con etiquetas
legibles; las contraseñas, tokens y contenido clínico nunca se guardan.

## Transferencia de sesión entre dispositivos (app del paciente)

Un paciente tiene **un solo dispositivo de confianza**. Si intenta entrar desde otro
teléfono, el servidor **no emite tokens**: crea una solicitud y avisa al dispositivo activo
(notificación FCM o sondeo en primer plano). El dispositivo activo muestra un código de
6 dígitos generado con `SecureRandom`, que vive **60 segundos y solo en memoria**; el
dispositivo nuevo lo escribe y el servidor guarda solo su **hash SHA-256** para
reenviarlo al activo, que compara el hash con el de su código local. **El servidor
nunca genera, compara ni conoce el código en claro.**

### Flujo

1. `POST /api/v1/auth/login` exige `device_id` para pacientes (UUID aleatorio que
   genera la app; el servidor guarda solo su hash SHA-256). `device_name` es opcional.
2. Si la cuenta no tiene dispositivo activo y no tiene 2FA, el login es normal y el
   `device_id` queda registrado. Si tiene 2FA, el dispositivo se registra **después**
   de verificar el segundo factor. Si el `device_id` coincide con el activo, el login
   es normal. Si es distinto, la respuesta es `DeviceTransferChallengeResponse` con
   `transfer_id`, `challenge_token` y `expires_in`; nunca incluye tokens. Si el
   paciente omite `device_id`, se rechaza con **400**: no se emiten tokens sin
   dispositivo.
3. El dispositivo activo consulta `GET /devices/transfers/pending`, pide huella, genera el
   código local y sondea cada 2 s. El nuevo propone el código con
   `POST /auth/device-transfer/{id}/code` (máximo una propuesta pendiente y 3 por solicitud).
4. El activo compara en local. Si coincide, llama `POST /devices/transfers/{id}/approve`
   con el `approval_token`; si no, `reject` con `mismatch`; el botón **“No fui yo”** usa
   `not_me` y termina la solicitud.
5. Tras aprobar, el dispositivo nuevo obtiene sus tokens **una sola vez** al sondear
   `POST /auth/device-transfer/{id}/status`, pasa a ser el activo y las sesiones del
   anterior quedan revocadas. Su access token responde **401 de inmediato** porque lleva el
   claim `did` (hash del dispositivo) y `get_current_user` lo compara con el activo.

> Los tokens de paciente sin `did` se rechazan (obliga a re-login tras actualizar).
> `users.device_epoch` invalida cualquier challenge 2FA emitido antes de una
> transferencia, logout o liberación desde el portal: un challenge viejo no puede
> reactivar el teléfono anterior. La aprobación exige biometría/PIN; si el teléfono
> no tiene bloqueo de pantalla, la app no permite continuar.

### Endpoints nuevos

| Método y ruta | Quién | Uso |
|---|---|---|
| `POST /auth/login` | público | `device_id` obligatorio para pacientes; puede devolver el desafío de transferencia |
| `POST /auth/device-transfer/{id}/code` | dispositivo nuevo | Propone el código (202) |
| `POST /auth/device-transfer/{id}/status` | dispositivo nuevo | Estado; entrega `tokens` una sola vez |
| `POST /auth/device-transfer/{id}/cancel` | dispositivo nuevo | Cancela la solicitud |
| `POST /auth/device-transfer/{id}/fallback` | dispositivo nuevo | 2FA si el paciente perdió el teléfono anterior; 409 si no tiene 2FA |
| `PUT /devices/me` | dispositivo activo | Registra el dispositivo y su token FCM |
| `GET /devices/transfers/pending` | dispositivo activo | Solicitud pendiente + `approval_token` + código propuesto |
| `POST /devices/transfers/{id}/approve` | dispositivo activo | Aprueba y cierra la sesión anterior |
| `POST /devices/transfers/{id}/reject` | dispositivo activo | `not_me`, `mismatch` o `expired` |

### Límites y alternativas

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `DEVICE_TRANSFER_TTL_SECONDS` | `120` | Vida total de la solicitud (cubre push + huella) |
| `DEVICE_TRANSFER_MAX_CODE_SUBMISSIONS` | `3` | Propuestas por transferencia, impuestas por el servidor |
| `DEVICE_TRANSFER_MAX_PER_HOUR` | `5` | Solicitudes por usuario y hora (429 al exceder) |
| `FCM_CREDENTIALS_FILE` | vacío | Cuenta de servicio; sin archivo el envío es simulado |

- Una solicitud nueva sustituye a la pendiente anterior (la anterior queda `expired`).
- **Restablecer la contraseña** libera el dispositivo de confianza, además de revocar
  sesiones. En el portal, **Usuarios → Restablecer dispositivo de confianza** hace lo mismo
  (permiso `users:manage`, auditado). **Cerrar sesión** en la app también lo libera.
- Si el paciente ya no tiene el teléfono anterior y tiene 2FA, `fallback` devuelve el
  desafío TOTP existente (acepta código o de recuperación); al verificarlo se libera el
  dispositivo anterior. Si no tiene 2FA, responde 409 invitando a recuperar la contraseña.
- El portal web y los roles distintos de `patient` no cambian.

### Auditoría

Cada evento queda en la bitácora con etiqueta en español: `device_registered`,
`device_transfer_requested`, `device_transfer_code_submitted`, `device_transfer_approved`,
`device_transfer_rejected`, `device_transfer_failed`, `device_transfer_expired`,
`device_transfer_fallback` y `device_released`. **Nunca se registra el código ni ningún
 token.**

### Firebase Cloud Messaging (opcional)

1. Crea el proyecto en Firebase y registra la app Android `mx.unach.dosys` con el SHA-1 de
   debug. Descarga `google-services.json` en `app/` (está en `.gitignore`).
2. Genera una cuenta de servicio y colócala **solo en el servidor** como
   `backend/secrets/fcm.json`. Compose monta esa carpeta en `/run/secrets` (solo lectura);
   nunca va dentro de la imagen ni del repositorio.
3. Apunta `FCM_CREDENTIALS_FILE=/run/secrets/fcm.json` en el `.env` (ya es el valor por
   defecto de Compose). Sin archivo, `services/push.py` registra el envío como simulado y
   todo funciona con el sondeo de la app.

## Pruebas de aceptación repetibles

Con los contenedores levantados (instala una vez `py -3.12 -m pip install -r requirements-dev.txt`):

```powershell
py -3.12 scripts\verify_vertical_slice.py   # API: médico crea, paciente lee, RBAC 401/403
py -3.12 scripts\verify_portal.py           # Portal: pacientes, consultas, citas, usuarios, credenciales y bitácora
py -3.12 scripts\verify_checkin.py          # Check-in: ventana, código incorrecto 400, correcto 200 e idempotente
py -3.12 scripts\verify_clinical_flow.py     # Expediente: alergias, edición, consulta con estudio, corrección, laboratorio y CSV
py -3.12 scripts\verify_agenda.py           # Agenda: vistas, filtros por URL, modal, estado y consultorio dinámico
py -3.12 scripts\verify_login_security.py   # Login: bloqueo 429, desbloqueo, 2FA y códigos de recuperación
py -3.12 scripts\verify_account_security.py # Cuentas: cambio y recuperación de contraseña, refresh con rotación, rate limit y API admin
py -3.12 scripts\verify_device_transfer.py  # Transferencia: desafío, aprobación, 401 inmediato, límites, 2FA y portal
py -3.12 scripts\demo_api_seguridad.py     # Demostración guiada para la presentación: 401, JWT con permisos, 403 por rol, firma y rotación
```

Para pruebas manuales del segundo factor está `scripts\totp_code.py <secreto>`: genera el
código de 6 dígitos a partir del secreto (útil si el teléfono no está a mano).

Los tres scripts aceptan `DOSYS_API_URL` para apuntar a otro entorno (por ejemplo el VPS).

## Android y backend local

La variante `debug` usa por defecto `http://10.0.2.2:8000/api/v1/` (emulador → PC) y la
variante `release` el dominio HTTPS. Los endpoints del paciente son:

- `POST /api/v1/auth/login` (con `device_id`/`device_name`)
- `PUT /api/v1/devices/me`
- `GET /api/v1/devices/transfers/pending`
- `POST /api/v1/devices/transfers/{id}/approve` · `/reject`
- `POST /api/v1/auth/device-transfer/{id}/code` · `/status` · `/cancel` · `/fallback`
- `GET /api/v1/patients/me`
- `GET /api/v1/patients/me/appointments`
- `GET /api/v1/patients/me/consultations`
- `POST /api/v1/patients/me/appointments/{id}/check-in`

## Despliegue en el VPS con Nginx Proxy Manager

1. Copia `backend/` al VPS y crea el `.env` de producción:

   ```dotenv
   APP_ENV=production
   DOCS_ENABLED=false
   POSTGRES_DB=dosys
   POSTGRES_USER=dosys
   POSTGRES_PASSWORD=<contraseña-larga-y-única>
   JWT_SECRET_KEY=<secreto-aleatorio-de-64-o-más-caracteres>
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   CORS_ORIGINS=https://medicos.tudominio.dev
   PUBLIC_BASE_URL=https://medicos.tudominio.dev
   # Correo real (opcional): sin clave se usa la vista previa simulada del portal.
   RESEND_API_KEY=
   EMAIL_FROM=D.O.S.Y.S <no-reply@tudominio.dev>
   # Transferencia de sesión y notificaciones (opcional).
   DEVICE_TRANSFER_TTL_SECONDS=120
   DEVICE_TRANSFER_MAX_CODE_SUBMISSIONS=3
   DEVICE_TRANSFER_MAX_PER_HOUR=5
   FCM_CREDENTIALS_FILE=/run/secrets/fcm.json
   ```

2. Levanta el stack con el daemon donde vive Nginx Proxy Manager:

   ```bash
   sudo docker compose -f compose.production.yaml up -d --build
   ```

   La API queda publicada en `127.0.0.1:8000` y `172.17.0.1:8000` (nunca expuesta a internet).

3. En Nginx Proxy Manager crea un **Proxy Host**:
   - Domain: `medicos.tudominio.dev`
   - Scheme: `http`, Forward Hostname: `172.17.0.1`, Forward Port: `8000`
   - SSL: Let's Encrypt, **Force SSL** y HTTP/2.

4. Verifica desde fuera: `curl -s https://medicos.tudominio.dev/health`.

Swagger queda desactivado en producción (`DOCS_ENABLED=false`); el personal usa el portal.

## Seguridad: estado y pendientes

**Ya implementado:** JWT de corta duración (30 min) firmado y con `purpose`, **sesión renovable
con refresh tokens de 7 días, rotación y revocación** (API y portal), contraseñas con
Argon2, **cambio de contraseña propio** y **recuperación con token de un solo uso**, RBAC
validado en servidor, bitácora de auditoría visible desde el portal,
**bloqueo por intentos fallidos** con desbloqueo, **límite de peticiones por IP** en los
accesos sensibles, **segundo factor TOTP** con códigos de recuperación, **transferencia de
sesión entre dispositivos** con código local y aprobación criptográfica, cierre inmediato
del dispositivo anterior por el claim `did`, HTTPS en producción +
HSTS, cookie del portal `HttpOnly` y `SameSite=Lax`, cabeceras de seguridad (CSP,
X-Frame-Options), Swagger apagado en producción, PostgreSQL sin puertos públicos, alta de
cuentas con contraseña temporal mostrada una sola vez, **API de administración con verbos
GET/PUT/DELETE** y gestión de usuarios restringida al rol médico.

**Falta antes de usar datos reales:**

1. **Acceso**
   - Rol `admin` dedicado para la gestión de usuarios (hoy lo hace cualquier médico).
   - Cambio obligatorio de contraseña en el primer inicio de sesión.
   - Cierre de sesión por inactividad en la app.
   - Envío real de correo con un proveedor (Resend) y bloqueo distribuido entre instancias.
   - Restringir el portal a red interna o VPN, como pide el análisis inicial.
   - Relación médico-paciente: hoy el médico ve a todos los pacientes del hospital.
2. **Protección de datos**
   - Guardar el token en el celular con Android Keystore (hoy va en DataStore).
   - Cifrado en reposo de PostgreSQL y de los respaldos.
   - Límite de peticiones distribuido (hoy es en memoria, por instancia).
   - Token CSRF formal en el portal (hoy la cookie `SameSite=Lax` cubre lo básico).
   - Gestión de secretos con Vault/Doppler en lugar de archivos `.env`.
   - Escaneo de dependencias (`pip-audit`) y de la imagen (`trivy`) en cada versión.
3. **Infraestructura**
   - Respaldos automáticos de la base y prueba de restauración.
   - Monitoreo, alertas y rotación de logs del contenedor.
   - Firewall del VPS (`ufw`) y `fail2ban` para SSH.
   - Límites de CPU/memoria y filesystem de solo lectura en los contenedores.
4. **Cumplimiento**
   - Aviso de privacidad, consentimiento informado y política de retención de datos.
   - Revisión contra NOM-024 y la normatividad aplicable antes de datos reales.
   - Procedimiento de respuesta a incidentes y contacto de seguridad.

## Límites conocidos de esta entrega

- Estudios, recetas y recordatorios siguen como interfaz demo en la app.
- El GPS solo muestra la distancia informativa al hospital; no bloquea el check-in.
- La huella protege el expediente en pantalla, pero no cifra los datos locales.

## Cumplimiento del caso práctico (Seguridad en Cómputo)

| Requisito | Estado |
|---|---|
| Registro de usuarios (nombre, correo, contraseña) | ✅ alta de pacientes y personal con credencial |
| Inicio de sesión | ✅ con bloqueo y segundo factor |
| Cambio de contraseña propio y recuperación | ✅ API y portal; recuperación con token de un solo uso (15 min) y correo simulado con proveedor opcional |
| Roles predeterminados (administrador / editor / usuario regular) | ✅ en base de datos: Administrador, Médico (editor), Laboratorio, Recepción y Paciente (lectura) |
| Permisos por acción (lectura, escritura, eliminación) | ✅ catálogo con área, acción y descripción |
| Asignar permisos a los roles dinámicamente | ✅ panel de Roles |
| Control de acceso por permisos | ✅ el servidor valida rol y permisos en cada petición |
| Historial de acceso | ✅ bitácora con usuario, fecha, IP y acción |
| Dashboard: usuarios, asignar/revocar roles, crear roles, auditoría | ✅ |
| Frontend web + API REST | ✅ portal web; la API REST la consume la app Android y queda documentada en OpenAPI |
| JWT: firma, expiración y datos (rol y permisos) | ✅ 30 min, HS256, claims `role`, `permissions`, `purpose` |
| Refresh tokens | ✅ 7 días con rotación y revocación; la app renueva sola al recibir 401 y el portal renueva su cookie |
| Contraseñas con hash seguro (salt) | ✅ Argon2 |
| HTTPS/TLS | ✅ producción con Let's Encrypt |
| Cookie HttpOnly, Secure y SameSite | ✅ portal |
| Validación y sanitización de entradas | ✅ Pydantic + ORM (sin SQL crudo) + autoescape de plantillas |
| Fuerza bruta: bloqueo temporal | ✅ 5 intentos → 15 minutos, con desbloqueo desde el portal |
| Rate limiting | ✅ ventana deslizante por IP en login, 2FA, recuperación y refresh (en memoria, por instancia) |
| Auditoría inmutable desde la aplicación | ✅ la bitácora es de solo lectura |
| CORS restringido a orígenes autorizados | ✅ |
| Principio de mínimo privilegio | ✅ permisos por rol; el paciente solo ve sus propios datos |
| Errores sin fuga de información | ✅ mensajes genéricos, sin trazas ni detalles internos |
| Documentos clínicos íntegros | ✅ huella SHA-256 + sello HMAC y verificación en el portal |

## Documentos clínicos

- El médico sube PDF o imágenes (≤10 MB) al expediente desde el portal; el paciente los
  consulta y descarga desde la app.
- Cada archivo se guarda en un volumen Docker y se registra con su **huella SHA-256** y un
  **sello HMAC** del servidor.
- La pantalla **Verificar** recalcula la huella y valida el sello: si el contenido cambió,
  lo advierte en lugar de mostrarlo como válido.
- Toda subida, descarga, verificación y eliminación queda en la bitácora.
