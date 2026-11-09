# Integridad y firma electrónica de documentos

Fecha: 2026-11-09

## 1. Qué significa aquí “firma electrónica”

En la interfaz el documento muestra **Firma electrónica** en lugar de “SHA-256”.
Técnicamente el sistema usa dos controles:

1. **SHA-256** del contenido: si cambia un solo byte, la huella cambia.
2. **Sello HMAC del servidor** sobre `documento + paciente + huella`: impide que
   alguien edite la base de datos y ponga una huella nueva sin la clave del
   servidor.

Es una firma electrónica **del servidor** (simétrica), suficiente para
demostrar integridad y autoría interna en esta práctica. No es una e.firma
legal con certificado del SAT ni una firma asimétrica con clave privada del
médico. Para producción regulada habría que evolucionar a firma asimétrica,
sellado de tiempo y almacenamiento WORM.

## 2. Investigación

- Integridad, firma y sellado de tiempo en salud:
  <https://smartadmissions.ai/articles/electronic-signature-healthcare>
- Hashing y detección de alteraciones:
  <https://wesignature.com/blog/document-hashing-prevents-digital-tampering/>
- Versionado y auditoría en expedientes:
  <https://www.censinet.com/perspectives/version-control-best-practices-healthcare-audits>
- HMAC vs firma digital; cuándo usar cada uno:
  <https://www.encryptionconsulting.com/hmac-vs-digital-signatures-understanding-the-right-tool-for-the-right-job/>
- Integridad documental y detección de cambios:
  <https://nhimg.org/glossary/document-integrity/>
- Firmas electrónicas y auditoría:
  <https://www.blueink.com/blog/audit-trail-esignature>
- Guía FDA de registros electrónicos y audit trail:
  <https://www.fda.gov/media/166215/download>

## 3. Flujo implementado

### Subir

- El médico sube PDF/JPG/PNG/WEBP (≤10 MB).
- El servidor calcula la firma y el sello.
- El documento aparece en el expediente con la columna **Firma electrónica**.

### Verificar

- Botón **Verificar** en el expediente o en la pantalla de firma.
- La pantalla compara:
  - firma registrada
  - firma calculada del archivo actual
- Resultado:
  - **Firma válida** si coinciden y el sello HMAC es correcto.
  - **Documento alterado** si cambió el contenido o el sello no valida.

### Demostrar una alteración real

Importante: si editas un archivo y lo **subes como nuevo**, el sistema lo firma
de nuevo y dirá “válido”. Eso es una versión nueva, no una alteración.

Para demostrar que el sistema detecta cambios hay que modificar el archivo
**guardado en el volumen** sin actualizar la base:

```bash
cd /home/ubuntu/Dosys/dosys-backend
./scripts/demo_integrity.sh <document_id> status
./scripts/demo_integrity.sh <document_id> tamper
```

Luego abre:

```text
https://medicos.stolasimp.dev/portal/documentos/<document_id>/verificar
```

Debe mostrar **Documento alterado**, con dos firmas diferentes.

Para restaurar:

```bash
./scripts/demo_integrity.sh <document_id> restore
```

Y verificar de nuevo: **Firma válida**.

### Corregir / reemplazar

En la pantalla de verificación:

- **Reemplazar archivo**: sube la versión correcta.
- El servidor elimina el archivo anterior del volumen.
- Recalcula SHA-256 + HMAC.
- La bitácora guarda `old_sha256`, `new_sha256`, usuario y fecha.
- Al volver a verificar, la nueva firma es válida.

### Eliminar

- **Eliminar documento** borra el archivo y el registro; queda auditado.
- Solo roles con `documents:delete` (médico/admin).

## 4. App del paciente

Endpoint nuevo:

```text
GET /api/v1/patients/me/documents/{id}/verify
```

Respuesta:

```json
{
  "id": 3,
  "intact": true,
  "registered_signature": "…",
  "current_signature": "…",
  "message": "Firma electrónica válida. El archivo no ha cambiado."
}
```

La app debe mostrar “Firma electrónica” y **no** “SHA-256”. Puede tener un botón
**Verificar firma** que llame a este endpoint.

## 5. Límites honestos

- HMAC usa una clave simétrica del servidor; no sustituye una e.firma legal.
- No hay versionado completo: al reemplazar se conserva el registro de la firma
  anterior en la bitácora, no el archivo anterior.
- El volumen Docker no es WORM; un administrador con root podría alterar el
  archivo, pero la verificación lo detecta.
- Para datos reales: firma asimétrica, timestamp authority, object storage con
  retención/WORM, respaldos inmutables y control de acceso más estricto.
