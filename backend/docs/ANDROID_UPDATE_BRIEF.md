# Brief para actualizar la app Android en OpenCode local

La app **no se actualizó en el VPS**. El backend ya expone los campos nuevos y
mantiene compatibilidad: si la app ignora los campos, sigue funcionando.

## 1. Cambios de API ya desplegados

`GET /api/v1/patients/me/consultations` ahora devuelve, además de los campos
actuales, estos campos opcionales:

```json
{
  "id": 4,
  "reason": "Dolor abdominal...",
  "diagnosis": "Gastroenteritis aguda...",
  "notes": "Hidratación...",
  "blood_pressure": "118/76",
  "heart_rate": 88,
  "respiratory_rate": 18,
  "temperature_c": 38.1,
  "oxygen_saturation": 97,
  "weight_kg": 68.5,
  "height_cm": 168,
  "physical_exam": "Paciente consciente...",
  "created_at": "...",
  "updated_at": null
}
```

`POST /api/v1/auth/login` para pacientes sigue requiriendo `device_id` y
`device_name`; no cambiar ese flujo.

## 2. Prompt para pegar en OpenCode local

> Actualiza la app Android de D.O.S.Y.S para mostrar la consulta clínica con
> estructura SOAP y signos vitales. No cambies autenticación, check-in, QR,
> documentos ni transferencia de sesión.
>
> Contexto:
> - El endpoint `GET /api/v1/patients/me/consultations` ahora incluye campos
>   opcionales: `blood_pressure`, `heart_rate`, `respiratory_rate`,
>   `temperature_c`, `oxygen_saturation`, `weight_kg`, `height_cm`,
>   `physical_exam`.
> - Son opcionales; la app debe tolerar `null` y respuestas antiguas.
>
> Cambios:
> 1. En `data/model/ClinicalModels.kt` (o el modelo de consultas existente),
>    agrega esos campos nullable con los tipos correctos.
> 2. En la pantalla de detalle de consulta, muestra:
>    - Bloque **S — Subjetivo**: motivo.
>    - Bloque **O — Objetivo**: grid de signos vitales con unidades (mmHg, lpm,
>      rpm, °C, %, kg, cm) y exploración física.
>    - Bloque **A — Análisis**: diagnóstico.
>    - Bloque **P — Plan**: notas/indicaciones.
>    - IMC calculado si hay peso y talla (peso / (talla/100)^2), con etiqueta
>      Bajo peso / Normal / Sobrepeso / Obesidad.
> 3. Si un bloque no tiene datos, no muestres una tarjeta vacía; muestra un
>    estado compacto “Sin registrar” solo dentro del detalle.
> 4. Mantén el diseño actual (Compose, tarjetas, tipografía y colores del
>    proyecto). No agregues dependencias nuevas si no hacen falta.
> 5. Agrega pruebas unitarias del cálculo de IMC y de parseo de `null`.
> 6. Compila con `./gradlew :app:assembleDebug` y prueba login con
>    `demo.paciente` / `Paciente123!`.
>
> Restricciones:
> - No toques backend ni migraciones.
> - No cambies la URL base.
> - No rompas el flujo de dispositivo de confianza ni el check-in QR.
> - Si el emulador falla, usa `adb reverse` y documenta el comando.

## 3. Verificación esperada

- La app compila.
- `demo.paciente` inicia sesión sin 2FA.
- La consulta “Gastroenteritis aguda” muestra TA 118/76, FC 88, FR 18, T 38.1,
  SpO₂ 97%, peso 68.5, talla 168 y exploración física.
- El IMC debe mostrar ~24.3 · Normal.
- Las consultas viejas sin signos vitales siguen abriendo sin crash.

## 4. Nota de dispositivo

El paciente `demo.paciente` fue limpiado de dispositivos de prueba en el VPS.
El primer login desde el teléfono registrará ese equipo como confiable. Si ya
había un dispositivo activo, la app puede pedir aprobación desde el anterior o
desde el portal (Usuarios → restablecer dispositivo).
