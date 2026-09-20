# D.O.S.Y.S API

Backend académico con **FastAPI + SQLAlchemy async + Alembic + PostgreSQL**.
El corte vertical permite que un médico registre una consulta desde Swagger y que el paciente la consulte desde la API y la app Android. **Todos los datos sembrados son ficticios.**

## Qué incluye este corte

- JWT de corta duración con roles `patient`, `doctor`, `laboratory` y `reception`.
- Autorización en servidor: el paciente solo puede consultar su propio perfil, citas y consultas; no puede acceder a endpoints médicos.
- Persistencia PostgreSQL aislada de la red del host.
- Migración Alembic versionada y bitácora de accesos/operaciones, sin tokens ni texto clínico en la bitácora.
- Swagger local para el médico de demostración: `http://127.0.0.1:8000/docs`.

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

Para detener los servicios sin borrar la base local:

```powershell
docker compose down
```

> No uses `docker compose down -v` si deseas conservar la información de la demostración.

## Demostración desde Swagger

1. Abre `http://127.0.0.1:8000/docs`.
2. Ejecuta `POST /api/v1/auth/login` con `medico` / `Medico123!`.
3. Copia **solo** `access_token`; presiona **Authorize** y escribe `Bearer <access_token>`.
4. Consulta `GET /api/v1/doctor/patients` para obtener el `id` del paciente ficticio.
5. Envía `POST /api/v1/doctor/consultations` con ese `patient_id`.
6. En la app Android inicia sesión con `paciente` / `Paciente123!`; abre **Mi expediente**. La consulta creada debe aparecer.

Credenciales exclusivamente locales/de demostración:

| Rol | Usuario | Contraseña |
|---|---|---|
| Paciente | `paciente` | `Paciente123!` |
| Médico | `medico` | `Medico123!` |

## Prueba repetible de aceptación

Con los contenedores levantados:

```powershell
py -3.12 scripts\verify_vertical_slice.py
```

La prueba crea una consulta ficticia, confirma que el paciente autenticado puede leerla y comprueba los rechazos `403` (paciente contra endpoint médico) y `401` (sin token).

## Android y backend local

La variante `debug` usa `http://10.0.2.2:8000/api/v1/`, que apunta desde el emulador Android a esta computadora. La variante `release` sigue reservada para el dominio HTTPS final.

La aplicación conectada consume:

- `POST /api/v1/auth/login`
- `GET /api/v1/patients/me`
- `GET /api/v1/patients/me/appointments`
- `GET /api/v1/patients/me/consultations`

## Despliegue posterior en VPS con Nginx Proxy Manager

No ejecutes esta sección hasta validar el flujo local.

1. Copia `backend/` al VPS y crea un `.env` de producción con secretos nuevos, por ejemplo:

   ```dotenv
   APP_ENV=production
   DOCS_ENABLED=false
   POSTGRES_DB=dosys
   POSTGRES_USER=dosys
   POSTGRES_PASSWORD=<contraseña-larga-y-única>
   JWT_SECRET_KEY=<secreto-aleatorio-de-64-o-más-caracteres>
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   CORS_ORIGINS=https://app.tudominio.mx
   NPM_NETWORK=<red-docker-de-nginx-proxy-manager>
   ```

2. Averigua la red de Nginx Proxy Manager (`docker network ls`) y asígnala a `NPM_NETWORK`.
3. Ejecuta `docker compose -f compose.production.yaml up -d --build`.
4. En Nginx Proxy Manager crea un **Proxy Host**: `api.tudominio.mx` → host `dosys-api` → puerto `8000`; activa certificado Let's Encrypt, **Force SSL** y HTTP/2.
5. Publica la app Android únicamente con `https://api.tudominio.mx/api/v1/` y elimina cualquier permiso de HTTP de la variante release.

PostgreSQL no publica puertos al VPS. Swagger queda desactivado por `DOCS_ENABLED=false`; si se habilita para soporte, protégelo mediante red interna/VPN o una ACL de Nginx Proxy Manager.

## Límites conocidos antes de producción

- Falta asociar médico-paciente para limitar la lista clínica a pacientes bajo su atención.
- Faltan refresh tokens, revocación, recuperación de cuenta, cifrado con Android Keystore y un portal interno real.
- Estudios, recetas y QR de la app permanecen como interfaz demo; no se escriben en este backend todavía.
- Antes de usar datos reales se requiere revisión de seguridad, privacidad, retención, respaldos, monitoreo y normatividad aplicable.
