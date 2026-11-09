#!/usr/bin/env bash
# Demostración de integridad de documentos (solo datos ficticios).
# Uso:
#   ./scripts/demo_integrity.sh <document_id> status
#   ./scripts/demo_integrity.sh <document_id> tamper
#   ./scripts/demo_integrity.sh <document_id> restore
set -euo pipefail

DOC_ID="${1:-}"
MODE="${2:-status}"
API_CONTAINER="${DOSYS_API_CONTAINER:-dosys-api}"
DB_CONTAINER="${DOSYS_DB_CONTAINER:-dosys-db}"
DOCS_DIR="/data/documents"

if [[ -z "$DOC_ID" || ! "$DOC_ID" =~ ^[0-9]+$ ]]; then
  echo "Uso: $0 <document_id> [status|tamper|restore]"
  exit 2
fi

ROW=$(docker exec "$DB_CONTAINER" psql -U dosys -d dosys -t -A -F'|' \
  -c "SELECT stored_name, patient_id, title, sha256 FROM documents WHERE id=$DOC_ID;")
if [[ -z "$ROW" ]]; then
  echo "No existe el documento $DOC_ID"
  exit 1
fi

IFS='|' read -r STORED PATIENT TITLE REGISTERED <<< "$ROW"
BACKUP="/tmp/dosys-integrity-${DOC_ID}.bak"
URL="https://medicos.stolasimp.dev/portal/documentos/${DOC_ID}/verificar"

current_hash() {
  docker exec "$API_CONTAINER" sha256sum "${DOCS_DIR}/${STORED}" 2>/dev/null | awk '{print $1}'
}

echo "Documento: $DOC_ID · $TITLE · paciente $PATIENT"
echo "Firma registrada: $REGISTERED"
echo "URL de verificación: $URL"

case "$MODE" in
  status)
    CURRENT=$(current_hash || true)
    echo "Firma actual:     ${CURRENT:-archivo no disponible}"
    if [[ "$CURRENT" == "$REGISTERED" ]]; then
      echo "Estado: INTACTO"
    else
      echo "Estado: ALTERADO"
    fi
    ;;
  tamper)
    docker exec "$API_CONTAINER" sh -c "cat '${DOCS_DIR}/${STORED}'" > "$BACKUP"
    docker exec "$API_CONTAINER" sh -c "printf '\nDEMO-TAMPER-%s' '$(date +%s)' >> '${DOCS_DIR}/${STORED}'"
    CURRENT=$(current_hash || true)
    echo "Respaldo: $BACKUP"
    echo "Firma actual: ${CURRENT:-archivo no disponible}"
    echo "Archivo alterado. Abre la URL y pulsa Verificar: debe decir ALTERADO."
    echo "Para devolverlo: $0 $DOC_ID restore"
    ;;
  restore)
    if [[ ! -f "$BACKUP" ]]; then
      echo "No existe respaldo en $BACKUP"
      exit 1
    fi
    docker exec -i "$API_CONTAINER" sh -c "cat > '${DOCS_DIR}/${STORED}'" < "$BACKUP"
    CURRENT=$(current_hash || true)
    echo "Archivo restaurado desde $BACKUP"
    echo "Firma actual: ${CURRENT:-archivo no disponible}"
    echo "Abre la URL y pulsa Verificar: debe decir VÁLIDO."
    ;;
  *)
    echo "Modo inválido: $MODE"
    exit 2
    ;;
esac
