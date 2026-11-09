# Recuperar el VPS después de copiar `backend/` sin `.env`

## Qué pasó

`compose.production.yaml` necesita un archivo `backend/.env`. Sin él:

- `docker compose` falla porque `POSTGRES_PASSWORD` es obligatorio.
- Si además se levantó el `compose.yaml` local, Docker crea **otro proyecto**
  (`dosys-local`) y **otro volumen** de PostgreSQL, no el de producción.
- Si se puso una `POSTGRES_PASSWORD` nueva, la API no puede entrar al volumen
  existente: PostgreSQL conserva la contraseña con la que se creó la primera vez.

**No ejecutes `docker compose down -v`**: borra el volumen de la base y los
documentos. Úsalo solo si aceptas perder los datos de demostración.

## 1. Ver qué contenedores y volúmenes existen

```bash
sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
sudo docker volume ls | grep -i dosys
```

Lo normal en producción es ver `dosys-db` y `dosys-api`. Si ves
`dosys-db-local` / `dosys-api-local`, se levantó el compose equivocado.

## 2. Recuperar la contraseña original de PostgreSQL

Si el contenedor `dosys-db` sigue existiendo:

```bash
sudo docker inspect dosys-db \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E 'POSTGRES_(DB|USER|PASSWORD)'
```

Si ya no existe, revisa el volumen:

```bash
sudo docker volume ls | grep -i postgres
```

No hay forma de leer la contraseña desde el volumen; si se perdió, hay que
restablecerla dentro de PostgreSQL o recrear la base (esto último borra datos).

## 3. Recrear `backend/.env`

Crea el archivo con los valores **originales** del VPS. Ejemplo:

```dotenv
APP_ENV=production
DOCS_ENABLED=false

POSTGRES_DB=dosys
POSTGRES_USER=dosys
POSTGRES_PASSWORD=LA_CONTRASENA_ORIGINAL_DEL_VPS

JWT_SECRET_KEY=EL_SECRETO_ORIGINAL_DEL_VPS
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=https://medicos.stolasimp.dev
PUBLIC_BASE_URL=https://medicos.stolasimp.dev

DEVICE_TRANSFER_TTL_SECONDS=120
DEVICE_TRANSFER_MAX_CODE_SUBMISSIONS=3
DEVICE_TRANSFER_MAX_PER_HOUR=5
FCM_CREDENTIALS_FILE=/run/secrets/fcm.json

DOCUMENTS_MAX_MB=10
# DOCUMENTS_SIGNING_KEY=
```

Reglas importantes:

- `POSTGRES_PASSWORD` **debe ser la misma** con la que se creó el volumen.
  Cambiarla en `.env` no cambia la contraseña real de PostgreSQL.
- `DOCS_ENABLED=false` en producción. El código además oculta `/docs` y
  `/openapi.json` cuando `APP_ENV=production`, pero conviene dejarlo explícito.
- Conserva `JWT_SECRET_KEY` y `DOCUMENTS_SIGNING_KEY`: si cambian, las sesiones
  actuales se invalidan y los documentos existentes fallan la verificación de
  integridad.
- No copies el `.env` de tu laptop: casi seguro tiene otra contraseña.

## 4. Levantar con el compose correcto

```bash
cd /ruta/al/backend
sudo docker compose -f compose.production.yaml up -d --build
```

o, mejor, usa el script que valida el `.env` antes de tocar nada:

```bash
bash scripts/deploy_vps.sh
```

El script:

- exige `.env` y las variables mínimas;
- compara la contraseña del `.env` con la del contenedor `dosys-db`;
- construye y levanta;
- espera `/health`;
- imprime logs si algo falla.

## 5. Si sigue el 500

```bash
sudo docker compose -f compose.production.yaml logs --tail=200 api
```

Busca la causa real:

| Log | Causa probable | Solución |
|---|---|---|
| `password authentication failed` | `.env` no coincide con la base | Usa la contraseña original del paso 2 |
| `relation "..." does not exist` / `UndefinedColumn` | Migraciones no corrieron o apunta a otra base | Revisa `DATABASE_URL` y ejecuta `alembic upgrade head` |
| `connection refused` a `db` | La base no está sana | `docker compose -f compose.production.yaml ps` y logs de `db` |
| `Falta POSTGRES_PASSWORD` | No hay `.env` | Créalo en el paso 3 |
| `port is already allocated` | Hay otro contenedor usando 8000 | Detén el stack viejo o usa el puerto correcto |

Para ver la base que está usando la API:

```bash
sudo docker exec dosys-api env | grep DATABASE_URL
```

## 6. Actualizar código sin volver a perder `.env`

Antes de copiar una versión nueva:

```bash
cd /ruta/al/backend
cp .env .env.backup
cp -a secrets secrets.backup 2>/dev/null || true
```

Luego copia el código **sin** `.env` ni `secrets`, o mejor usa Git:

```bash
git fetch origin
git checkout feat/backend-vertical-slice
git pull
bash scripts/deploy_vps.sh
```

Si usas `rsync`:

```bash
rsync -av --exclude '.env' --exclude 'secrets/' \
  ./backend/ usuario@vps:/ruta/al/backend/
```

## 7. Verificación final

```bash
curl -s https://medicos.stolasimp.dev/health
curl -s -o /dev/null -w '%{http_code}\n' https://medicos.stolasimp.dev/portal/login
```

Debe responder:

```json
{"status":"ok","database":"ok"}
```

y `200` en el login. Después entra al portal con `medico / Medico123!` y abre
**Actividad** para confirmar que la base es la correcta.

## Si perdiste el volumen y aceptas reiniciar la demo

Solo en un entorno de demostración, sin datos reales:

```bash
sudo docker compose -f compose.production.yaml down -v
sudo docker compose -f compose.production.yaml up -d --build
```

Al arrancar, las migraciones y el `seed` crean de nuevo las cuentas demo. **Esto
borra pacientes, consultas, documentos y auditoría anteriores.**
