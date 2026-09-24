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
```

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

**Ya implementado:** JWT de corta duración, contraseñas con Argon2, RBAC validado en
servidor, bitácora de auditoría visible desde el portal, HTTPS en producción, cookie del
portal `HttpOnly` y `SameSite=Lax`, cabeceras de seguridad (CSP, X-Frame-Options), Swagger
apagado en producción, PostgreSQL sin puertos públicos, alta de cuentas con contraseña
temporal mostrada una sola vez y gestión de usuarios restringida al rol médico.

**Falta antes de usar datos reales:**

1. **Acceso**
   - Rol `admin` dedicado para la gestión de usuarios (hoy lo hace cualquier médico).
   - Cambio obligatorio de contraseña en el primer inicio de sesión.
   - Refresh tokens con revocación y cierre de sesión por inactividad.
   - Recuperación de contraseña y bloqueo por intentos fallidos.
   - Segundo factor (MFA) para el personal médico.
   - Restringir el portal a red interna o VPN, como pide el análisis inicial.
   - Relación médico-paciente: hoy el médico ve a todos los pacientes del hospital.
2. **Protección de datos**
   - Guardar el token en el celular con Android Keystore (hoy va en DataStore).
   - Cifrado en reposo de PostgreSQL y de los respaldos.
   - Envío real de credenciales por correo (hoy es una simulación con vista previa).
   - Límite de peticiones (rate limiting) contra fuerza bruta en login y portal.
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
