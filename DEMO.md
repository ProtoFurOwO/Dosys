# Guía de demostración — D.O.S.Y.S

Demostración de 7 a 10 minutos con dos dispositivos: **laptop** (portal clínico) y
**celular** (app del paciente). Todo el flujo es real: portal → PostgreSQL → app.

## Antes de presentar (2 minutos de preparación)

1. **Backend en el VPS** (desde tu PC):

   ```powershell
   curl -s https://medicos.stolasimp.dev/health
   ```

   Debe responder `{"status":"ok","database":"ok"}`.

2. **Laptop**: abre `https://medicos.stolasimp.dev/portal` e inicia sesión con
   `medico` / `Medico123!`. Deja la ventana maximizada.

3. **Celular**: instala `dosys-demo-vps.apk` (ya apunta al VPS), inicia sesión con
   `paciente` / `Paciente123!` **una vez** para comprobar que todo carga, y sal de la
   sesión. Deja el celular en la pantalla de acceso con datos móviles o wifi.
   Concede el permiso de ubicación y ten la huella configurada.

4. **Citas de reserva**: en el portal, agenda 2 citas (por si el primer escaneo no lee).
   Cada cita genera su propio QR y código.

## Guion sugerido

### 1. Presentación (30 s)

> "D.O.S.Y.S es un sistema hospitalario con dos partes: una **app nativa del paciente**
> (Kotlin + Compose) y un **portal clínico web** para el personal médico. Los dos usan el
> mismo backend en FastAPI + PostgreSQL, desplegado con HTTPS en un VPS."

### 2. El portal y el expediente (1 min)

- Muestra **Pacientes**: buscador real, métricas (pacientes, consultas, consultas de hoy).
- Entra al expediente de José Antonio Matuz: datos, historial de consultas en orden
  cronológico, correo y contacto de emergencia.

> "Cada consulta que se registra aquí aparece automáticamente en la app del paciente."

### 3. Registrar un paciente en vivo (1 min)

- **Nuevo paciente** → llena nombre, CURP, correo y usuario (por ejemplo
  `invitado.hoy` / `Acceso2026`).
- Al guardar sale la **credencial**: usuario + contraseña temporal.
- Pulsa **Imprimir credencial** (papel de verdad o vista de impresión).
- Pulsa **Enviar por correo**: sale la **vista previa del correo** y se registra en la
  bitácora. Aclara:

> "El envío es simulado para la entrega; en producción se conecta el proveedor de correo
> del hospital. La credencial se muestra una sola vez."

### 4. Agendar la cita con QR (30 s)

- En el expediente o en **Citas**: **Agendar cita** (Cardiología, mañana 11:30).
- Al guardar, el portal muestra la cita con **su QR de check-in** y el código de respaldo.

### 5. La app con la cuenta recién creada (1 min)

- En el celular, inicia sesión con **el paciente que acabas de registrar**.
- La app saluda con su nombre, le muestra "No tienes citas próximas" y el check-in listo.

> "La cuenta nació hace un minuto en el portal y ya funciona en la app: es la misma base
> de datos y el mismo servidor."

### 6. Check-in con la cámara (1 min)

- En la app: **Check-in con QR → Abrir cámara**, apunta al QR de la laptop.
- La app confirma: "Llegada confirmada".
- Recarga **Citas** en la laptop: aparece la etiqueta **"Llegó (hora)"**.

> "La cámara del celular del paciente es el módulo del dispositivo; el hospital solo
> muestra el código, no necesita cámara ni permisos del navegador."

### 7. Huella y GPS (1 min)

- Abre **Mi expediente**: pide **huella** antes de mostrar información clínica.
- En el check-in, la tarjeta **Cómo llegar al hospital** muestra el **mapa real**
  (OpenStreetMap, sin API key), el pin del sanatorio, tu ubicación y la distancia.

### 8. Usuarios y auditoría (1 min)

- **Usuarios → Nuevo médico**: crea una cuenta de prueba, sale su credencial.
- **Restablecer** y **Desactivar**: intenta iniciar sesión con esa cuenta (falla);
  reactívala y vuelve a entrar.

> "Desactivar bloquea el acceso al instante porque la validación es en el servidor."

- Abre **Actividad**: ahí está todo lo que acabas de hacer (registro, desactivación,
  contraseña restablecida, llegada con QR, accesos).

### 9. Cierre (30 s)

- Arquitectura: app nativa ↔ API REST ↔ PostgreSQL, portal con el mismo backend, HTTPS y
  bitácora de todo.
- Seguridad ya cubierta: JWT corto, Argon2, roles en servidor, cookie HttpOnly, CSP,
  Swagger apagado en producción, base sin puertos públicos.
- Lo que sigue: rol administrador, MFA, cambio obligatorio de contraseña, envío real de
  correo, respaldos y monitoreo (está en el README del backend).

## Frases que ayudan a explicar

- **"Solo lectura para el paciente"**: la app nunca modifica datos clínicos; las únicas
  escrituras son su login y su check-in.
- **"La seguridad se valida en el servidor"**: el rol no se decide en la app; cada petición
  comprueba el token y el rol, y queda en la bitácora.
- **"El QR es de la cita, no del paciente"**: cada cita genera un código único; el código
  de respaldo permite continuar si la cámara falla.
- **"Sin servicios de pago"**: el mapa usa OpenStreetMap (sin API key) y el escaneo es
  nativo con ZXing.

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué no un portal en React? | El portal es HTML del propio backend; menos piezas que mantener y el mismo despliegue. Un portal React queda como siguiente iteración si crece el equipo. |
| ¿Dónde se guardan las contraseñas? | En PostgreSQL con hash **Argon2**; nadie puede verlas, solo restablecerlas. |
| ¿Qué pasa si pierdo el celular? | La sesión JWT caduca en 30 minutos y el expediente pide huella; el token cifrado con Keystore y la revocación están en la lista de pendientes. |
| ¿Aguanta datos reales? | La base técnica está, pero antes se requiere MFA, respaldos, cifrado en reposo, aviso de privacidad y revisión NOM-024. |
| ¿Cómo lo despliegan? | Docker Compose en el VPS detrás de Nginx Proxy Manager con Let's Encrypt; la base nunca publica puertos. |
| ¿Se conecta con otros sistemas? | Sí: la API REST con OpenAPI permite integrar laboratorio y recepción; hoy el rol y las tablas ya los contemplan. |

## Plan B (si algo falla en vivo)

- Si el escaneo no lee: usa el **código de respaldo** que aparece bajo el QR.
- Si el celular no conecta: abre `https://medicos.stolasimp.dev/portal` en el navegador del
  celular (mismo backend, misma demo) o continúa con el emulador.
- Si el GPS no fija: la tarjeta avisa "sin señal" y la demo sigue; el mapa del hospital
  igual se muestra.
- Si la cita ya está "Llegó": agenda una nueva desde el portal en 10 segundos.
