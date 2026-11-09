#!/usr/bin/env bash
# Despliegue seguro en el VPS.
#
# Nunca copies la carpeta backend encima de la instalación sin conservar el
# .env: ese archivo contiene la contraseña de la base y la clave que firma los
# documentos. Cambiarlos rompe la conexión o invalida los sellos existentes.
#
# Uso:
#   cd /ruta/al/backend
#   bash scripts/deploy_vps.sh

set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f compose.production.yaml)

fail() {
  echo
  echo "ERROR: $*" >&2
  echo
  exit 1
}

echo "== D.O.S.Y.S · despliegue de producción =="

if [[ ! -f .env ]]; then
  fail "falta backend/.env. Recupéralo antes de continuar (ver RECUPERAR_VPS.md)."
fi

for key in POSTGRES_PASSWORD JWT_SECRET_KEY; do
  if ! grep -qE "^${key}=.+" .env; then
    fail "falta ${key} en .env"
  fi
done

# Si la base ya existe, la contraseña del .env debe ser la misma que se usó al
# crear el volumen. Cambiarla aquí no cambia la contraseña real de PostgreSQL.
if docker inspect dosys-db >/dev/null 2>&1; then
  DB_PASSWORD="$(
    docker inspect dosys-db --format '{{range .Config.Env}}{{println .}}{{end}}' \
      | sed -n 's/^POSTGRES_PASSWORD=//p' | head -1
  )"
  ENV_PASSWORD="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | head -1)"
  if [[ -n "${DB_PASSWORD}" && "${DB_PASSWORD}" != "${ENV_PASSWORD}" ]]; then
    fail "POSTGRES_PASSWORD de .env no coincide con la base existente.
Usa exactamente esta línea en .env:
POSTGRES_PASSWORD=${DB_PASSWORD}"
  fi
fi

echo "== Construyendo y levantando contenedores =="
"${COMPOSE[@]}" up -d --build

echo "== Esperando a que la API responda =="
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS http://127.0.0.1:8000/health; then
  echo
  "${COMPOSE[@]}" ps || true
  "${COMPOSE[@]}" logs --tail=120 api || true
  fail "la API no respondió. Revisa los logs de arriba."
fi

echo
echo "== Comprobando el portal =="
curl -fsS http://127.0.0.1:8000/portal/login >/dev/null
echo "Portal OK."
"${COMPOSE[@]}" ps
