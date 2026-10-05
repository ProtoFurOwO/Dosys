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
   de sus datos.
2. **Expediente**: datos del paciente e historial de consultas en orden cronológico.
3. **Nueva consulta**: motivo, diagnóstico y notas; al guardar aparece en el expediente y
   en la app del paciente.
4. **Agendar cita**: fecha, hora, especialidad y consultorio; el sistema genera un código
   de check-in único por cita.
5. **Citas**: agenda con el QR de check-in y su código de respaldo.
6. **Usuarios**: alta y edición de médicos, activar/desactivar cuentas y restablecer
   contraseñas (siempre mostrando la credencial una vez).
7. **Actividad**: bitácora en solo lectura con filtros por acción y usuario.

Cada cita agendada desde el portal aparece también en la app del paciente, y cada paciente
registrado puede iniciar sesión de inmediato en la app con la credencial que se genera.

Credenciales exclusivamente locales/de demostración:

| Rol | Usuario | Contraseña |
|---|---|---|
| Paciente (app) | `paciente` | `Paciente123!` |
| Médico (portal) | `medico` | `Medico123!` |

## Pruebas de aceptación repetibles

Con los contenedores levantados:

```powershell
py -3.12 scripts\verify_vertical_slice.py   # API: médico crea, paciente lee, RBAC 401/403
py -3.12 scripts\verify_portal.py           # Portal: pacientes, consultas, citas, usuarios, credenciales y bitácora
py -3.12 scripts\verify_checkin.py          # Check-in: código incorrecto 400, correcto 200 e idempotente
py -3.12 scripts\verify_login_security.py   # Login: bloqueo 423, desbloqueo, 2FA y códigos de recuperación
py -3.12 scripts\verify_account_security.py # Cuentas: cambio y recuperación de contraseña, refresh con rotación, rate limit y API admin
py -3.12 scripts\demo_api_seguridad.py     # Demostración guiada para la presentación: 401, JWT con permisos, 403 por rol, firma y rotación
```

Para pruebas manuales del segundo factor está `scripts\totp_code.py <secreto>`: genera el
código de 6 dígitos a partir del secreto (útil si el teléfono no está a mano).

Los tres scripts aceptan `DOSYS_API_URL` para apuntar a otro entorno (por ejemplo el VPS).

## Android y backend local

La variante `debug` usa por defecto `http://10.0.2.2:8000/api/v1/` (emulador → PC) y la
variante `release` el dominio HTTPS. Los endpoints del paciente son:

- `POST /api/v1/auth/login`
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
accesos sensibles, **segundo factor TOTP** con códigos de recuperación, HTTPS en producción +
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
