# Guion de presentación — un día de clínica en D.O.S.Y.S

Este guion no recorre menús: cuenta **un día de trabajo real** en la clínica.
La misma base de datos atiende el portal y la app del paciente.

- **Duración:** 12–15 minutos.
- **Escenario:** 1 laptop con 4 perfiles de navegador + 1 teléfono.
- **Idea central:** recepción registra y agenda; el médico documenta; laboratorio
  firma; el paciente consulta. Todo queda auditado.

---

## 0. Antes de presentar (T-10 minutos)

### 0.1 Verificar el servidor

```bash
curl -s https://medicos.stolasimp.dev/health
# {"status":"ok","database":"ok"}
```

### 0.2 Preparar el día (borra solo datos del paciente demo)

```bash
sudo docker exec dosys-api python scripts/demo_reset.py --reset --live
```

Debe imprimir algo como:

```text
Demo recreada:
  Modo: día en vivo
  Paciente: Paciente Demo (id 7)
  Cita de hoy: 2026-11-09T03:10-06:00 (confirmed) · /portal/citas/23
  Solicitud pendiente: 2026-11-10T12:30-06:00
  Consulta SOAP: id 11
  Documento firmado: Nota de consulta demo
```

Ese comando deja:

- Una **cita confirmada para hoy**, 20 minutos adelante, con QR y check-in abierto.
- Una **solicitud de cita para mañana** enviada desde la app, pendiente de confirmar.
- Una consulta SOAP de ejemplo, una orden de laboratorio pendiente y una nota firmada.
- La cuenta `demo.paciente` **sin dispositivos**, para que el primer login en el
  teléfono sea limpio.

Verifica el estado sin SQL:

```bash
sudo docker exec dosys-api python scripts/demo_status.py
```

Debe mostrar `Dispositivos activos: 0/3`, la cita de hoy con
`check-in=ABIERTO` y una orden de laboratorio pendiente.

Si quieres respaldar antes (opcional):

```bash
sudo docker exec dosys-db pg_dump -U dosys -d dosys -Fc \
  > /tmp/dosys-demo-$(date +%F-%H%M).dump
```

### 0.3 Abrir cuatro ventanas/perfiles distintos

El portal usa **una cookie de sesión por navegador**. Si abres dos roles en el
mismo perfil, el segundo login pisa al primero. Usa:

1. **Recepción:** `https://medicos.stolasimp.dev/portal/inicio`
2. **Médico:** `https://medicos.stolasimp.dev/portal/inicio`
3. **Laboratorio:** `https://medicos.stolasimp.dev/portal/laboratorio`
4. **Administración:** `https://medicos.stolasimp.dev/portal/usuarios`

No uses varias pestañas del mismo perfil ni varias ventanas de incógnito del
mismo navegador: comparten cookies. Usa cuatro **perfiles** de Chrome/Edge
(Persona 1, Persona 2…) o cuatro navegadores distintos.

### 0.4 Cuentas

| Rol | Usuario | Contraseña | Notas |
|---|---|---|---|
| Recepción | `demo.recepcion` | `Recepcion123!` | Dashboard, pacientes, citas |
| Médico | `demo.medico` | `Medico123!` | Dr. Demo Médico · Medicina General |
| Laboratorio | `laboratorio` | `Lab12345!` | Laboratorio Central |
| Administración | `demo.admin` | `Admin123!` | Sin 2FA; ideal para la demo |
| Paciente (app) | `demo.paciente` | `Paciente123!` | Sin 2FA |

No uses `admin` en vivo si no tienes a mano el autenticador: esa cuenta sí tiene
2FA. `demo.admin` entra directo.

### 0.5 Teléfono

- Instala el APK construido desde `master` (incluye citas, documentos y
  dispositivos de confianza).
- Concede **cámara**, **ubicación** y **notificaciones**.
- Configura **huella/PIN**; la app lo pide para el expediente y para aprobar
  dispositivos.
- Déjalo cargando y en modo **No molestar**.
- No inicies sesión todavía: el primer login en vivo registra el dispositivo.
- Ten el código de respaldo del QR a la vista por si la cámara falla.

### 0.6 Pestañas que conviene dejar preabiertas

- Recepción: `Inicio`.
- Médico: `Inicio`.
- Laboratorio: `Laboratorio`.
- Admin: `Usuarios` y `Actividad`.
- Portal: la cita de hoy de `demo.paciente` (`/portal/citas/<id>`), con el QR.

Para obtener el ID de la cita de hoy:

```bash
sudo docker exec dosys-db psql -U dosys -d dosys -c "
select a.id, a.scheduled_at, a.status, a.checkin_code
from appointments a
join patients p on p.id = a.patient_id
join users u on u.id = p.user_id
where u.username = 'demo.paciente'
order by a.scheduled_at desc
limit 5;"
```

---

## 1. La “talacha” que vas a contar

| Momento | Quién | Acción real | Lo que demuestra |
|---|---|---|---|
| 08:00 | Recepción | Abre el día y ve pendientes | Dashboard operativo por rol |
| 08:05 | Recepción | Registra paciente sin cita | Alta + credencial de una sola vez |
| 08:10 | Recepción | Confirma solicitud de la app | Agenda request-based |
| 08:20 | Paciente | Escanea QR en recepción | Check-in único y ventana horaria |
| 08:25 | Médico | Ve sala de espera y abre consulta | Continuidad recepción → médico |
| 08:35 | Médico | Llena SOAP, receta y estudio | Nota clínica completa y auditada |
| 08:45 | Laboratorio | Inicia y captura resultado | PDF firmado con huella |
| 09:00 | Paciente | Ve receta, estudio y expediente | Misma verdad en la app |
| 09:10 | Admin | Revisa bitácora y dispositivos | Trazabilidad y control de acceso |

No tienes que hacer las nueve escenas: si el tiempo aprieta, recorta la alta de
paciente o la demo de dispositivos. Nunca recortes check-in, SOAP y laboratorio:
son el corazón de la talacha.

---

## 2. Guion minuto a minuto

### 2.1 Apertura (30 s)

**Decir:**

> “Esto no es un CRUD con pantallas bonitas. Es la operación de una clínica:
> recepción, médico, laboratorio y paciente trabajando sobre el mismo expediente.
> La app no es un adorno: es el canal del paciente. Todo lo que vean está en la
> misma base PostgreSQL y pasa por el mismo backend.”

**Hacer:** mostrar la laptop con Recepción y el teléfono al lado.

---

### 2.2 Recepción: empieza el día (2 min)

**Hacer:**

1. Entra como `demo.recepcion` → **Inicio**.
2. Señala las tarjetas: **Citas de hoy**, **En espera**, **Solicitudes**,
   **Pacientes**.
3. Ve a **Pacientes → Nuevo paciente**.
4. Pulsa **Llenar aleatorio** (`Alt+Shift+R`) y guarda.
5. Se muestra la **credencial**: usuario y contraseña temporal. Pulsa
   **Imprimir credencial** o **Enviar por correo** para mostrar la vista previa.
6. Vuelve a **Inicio → Solicitudes de cita**. Abre la solicitud de
   `Paciente Demo` para mañana y pulsa **Confirmar cita**.
7. Entra a **Citas** o **Agenda** y muestra la cita confirmada de hoy.

**Decir:**

> “Recepción no ve notas clínicas, solo identidad, contacto y agenda. La
> credencial se muestra una sola vez; el correo está simulado para la demo.
> La cita que acabo de confirmar nació desde la app: el paciente solicita,
> recepción conserva el control y hasta que se confirma no hay QR.”

**Debe verse:** credencial generada, solicitud confirmada y cita de hoy en la
agenda.

---

### 2.3 Llega el paciente: check-in con QR (1.5 min)

**Hacer:**

1. Abre en la laptop la cita de hoy: `/portal/citas/<id>`.
2. Muestra el **QR**, el **código de respaldo** y la **ventana de check-in**
   (abre 2 h antes, cierra 4 h después).
3. En el teléfono, inicia sesión con `demo.paciente` / `Paciente123!`.
4. Abre **Check-in con QR** y escanea la pantalla.
5. Vuelve a la laptop: la cita debe mostrar **Llegada confirmada** y el paciente
   debe aparecer en **En espera** con **Consultorio 3**.
6. Si quieres, cambia el consultorio y pulsa **Guardar consultorio**.

**Decir:**

> “El QR es de la cita, no del paciente. Es de un solo uso y solo funciona dentro
> de la ventana. El servidor valida la hora, la cita y el código; la app no decide
> si puede entrar.”

**Plan B:** si la cámara falla, escribe el **código de respaldo** en el campo
“Código de respaldo” de la app. Si el teléfono falla por completo, usa el modo
bombero de la sección 6.

---

### 2.4 Médico: consulta SOAP (3 min)

**Hacer:**

1. Entra como `demo.medico` → **Inicio**.
2. Muestra **Sala de espera**: ahí está `Paciente Demo` con el consultorio.
3. Pulsa **Iniciar consulta**.
4. Recorre el expediente: alergias, antecedentes, crónicos y consultas previas.
5. Pulsa **Llenar ejemplo** (`Alt+Shift+D`).
6. Señala el SOAP:
   - **S:** motivo.
   - **O:** presión, FC, FR, temperatura, SpO₂, peso/talla e **IMC calculado**.
   - **A:** diagnóstico.
   - **P:** plan, receta y estudio.
7. Cambia una palabra del diagnóstico para mostrar que es editable. Guarda con
   **Guardar consulta**.
8. Muestra el resultado: consulta en la línea de tiempo, **receta PDF** y
   **orden de laboratorio**.

**Decir:**

> “Una sola nota genera tres cosas: la consulta en el expediente, la receta en PDF
> y la orden de laboratorio. El médico no captura lo mismo en tres sistemas. Si
> corrige después, la bitácora guarda qué cambió, no el contenido clínico.”

**Debe verse:** “Consulta registrada”, receta y estudio pendiente.

---

### 2.5 Laboratorio: resultado firmado (1.5 min)

**Hacer:**

1. Entra como `laboratorio` / `Lab12345!`.
2. Abre **Laboratorio**. Muestra los contadores: solicitados, en proceso, listos.
3. Busca a `Paciente Demo`.
4. Pulsa **Iniciar** y luego **Capturar resultado**.
5. Pulsa **Llenar ejemplo** (`Alt+Shift+L`) y **Guardar y generar PDF**.
6. Abre el **Resultado PDF** y muestra la huella SHA-256 y la firma electrónica
   del servidor.

**Decir:**

> “El resultado no es un texto suelto: es un PDF con huella y sello del servidor.
> Si alguien cambia un byte, la verificación lo detecta. El laboratorio no puede
> inventar un resultado sin que quede auditado.”

**Opcional:** abre el expediente → **Documentos** → **Verificar** para mostrar
“El archivo coincide con la huella registrada”.

---

### 2.6 Paciente: la misma verdad en el celular (1.5 min)

**Hacer:**

1. En el teléfono, vuelve a **Inicio** y actualiza.
2. Muestra la próxima cita, la consulta reciente y el estudio.
3. Abre **Estudios**: el resultado ya está listo.
4. Abre **Recetas**: el PDF de la receta.
5. Abre **Mi expediente**: pide huella y muestra alergias, antecedentes y
   diagnósticos crónicos.

**Decir:**

> “El paciente no captura datos clínicos: solo lee. No hay una ‘app paralela’ con
> datos inventados; es la misma consulta que acaba de firmar el médico y el mismo
> resultado que acaba de subir laboratorio.”

---

### 2.7 Administración y auditoría (1 min)

**Hacer:**

1. Entra como `demo.admin` / `Admin123!`.
2. Abre **Usuarios**: muestra roles y permisos.
3. Abre **Actividad**. Filtra por entidad `consultation`, `study_order` o
   `appointment`.
4. Muestra las acciones de la demo: alta de paciente, cita confirmada, check-in,
   consulta, resultado, etc.
5. Descarga el **CSV**.

**Decir:**

> “Cada acción queda con usuario, IP real, entidad y detalle. El rol no se decide
> en la pantalla: el servidor lo valida en cada petición. Si alguien intenta abrir
> una sección que no le toca, recibe ‘Sin permiso’ y queda registrado.”

---

### 2.8 Dispositivos de confianza (1.5 min, opcional)

**Hacer (con un solo teléfono):**

1. En administración: **Usuarios → Paciente Demo → Dispositivos de confianza**.
2. Muestra el teléfono actual como **Autorizado**.
3. Explica que puede haber hasta 3, todos con acceso completo.
4. Muestra el botón **Revocar** y el de **Restablecer todos los dispositivos**.

**Hacer (con dos teléfonos):**

1. En el teléfono B, inicia sesión con `demo.paciente`.
2. Aparece “Autoriza este dispositivo”.
3. En A llega la notificación o la pantalla de aprobación; usa la huella.
4. Escribe el código en B. B entra.
5. Vuelve a A: **sigue funcionando**. Abre **Dispositivos de confianza** y muestra
   ambos.
6. En el portal, revoca B. B recibe 401; A sigue dentro.

**Decir:**

> “Ya no es una transferencia que expulsa al anterior: es un alta de dispositivo
> con límite. Cualquier dispositivo activo puede aprobar; el cuarto se rechaza
> con 409. El portal puede revocar uno sin cerrar los demás.”

---

### 2.9 Cierre (30 s)

**Decir:**

> “La talacha real no se pierde: recepción, médico, laboratorio y paciente ven la
> misma verdad, y cada paso queda auditado. La app es nativa, el portal es del
> mismo backend, la base está en PostgreSQL y todo corre en Docker con HTTPS.
> Lo que sigue es endurecerlo para producción: correo real, FCM, respaldos,
> monitoreo y revisión NOM-024.”

---

## 3. Comandos de apoyo

### 3.1 Preparar el día en vivo

```bash
sudo docker exec dosys-api python scripts/demo_reset.py --reset --live
```

### 3.2 Preparar el modo histórico (cita para mañana)

```bash
sudo docker exec dosys-api python scripts/demo_reset.py --reset
```

### 3.3 Ver el estado del día

```bash
sudo docker exec dosys-api python scripts/demo_status.py
```

### 3.4 Ver la cita, el código y la ventana

```bash
sudo docker exec dosys-db psql -U dosys -d dosys -c "
select a.id, a.scheduled_at, a.status, a.checkin_code,
       a.scheduled_at - interval '2 hours' as abre_checkin,
       a.scheduled_at + interval '4 hours' as cierra_checkin
from appointments a
join patients p on p.id = a.patient_id
join users u on u.id = p.user_id
where u.username = 'demo.paciente'
order by a.scheduled_at desc
limit 5;"
```

### 3.5 Ver dispositivos del paciente demo

```bash
sudo docker exec dosys-db psql -U dosys -d dosys -c "
select d.id, d.name, d.is_active, d.last_seen_at
from user_devices d
join users u on u.id = d.user_id
where u.username = 'demo.paciente'
order by d.id;"
```

### 3.6 Limpiar dispositivos si la app se quedó en “autoriza este dispositivo”

Desde el portal: **Usuarios → Paciente Demo → Restablecer todos los dispositivos**.

O por SQL (solo demo):

```bash
sudo docker exec dosys-db psql -U dosys -d dosys -c "
update user_devices set is_active = false
where user_id = (select id from users where username = 'demo.paciente');
update refresh_tokens set revoked_at = now()
where user_id = (select id from users where username = 'demo.paciente')
  and revoked_at is null;"
```

### 3.7 Verificar el flujo completo antes de presentar

Estos scripts crean datos de prueba; córrelos **antes** de la demo, no durante:

```bash
sudo docker exec dosys-api python scripts/verify_checkin.py
sudo docker exec dosys-api python scripts/verify_clinical_flow.py
sudo docker exec dosys-api bash scripts/demo_integrity.sh
```

---

## 4. Plan B (si algo falla en vivo)

| Falla | Plan B |
|---|---|
| La cámara no lee el QR | Escribe el **código de respaldo** en la app. |
| El teléfono no conecta | Usa otro teléfono/emulador; el login es el mismo. |
| La app no abre | Enseña el flujo con el portal y el código; o usa el modo bombero de abajo. |
| El check-in no avanza | Marca la cita como **Atendida** desde **Agenda** (equivale a llegada) y sigue con la consulta. |
| La cita ya pasó | Vuelve a correr `demo_reset.py --reset --live`; tendrás una cita nueva. |
| Laboratorio no carga | Muestra el resultado ya completado del historial o el PDF firmado de la nota. |
| Se cae el internet | Usa hotspot; si no, muestra el video/grabación de respaldo y explica la arquitectura. |
| Un rol se quedó sin sesión | Vuelve a entrar; las cuentas están en la tabla de arriba. |

**Modo bombero para check-in (solo si el teléfono murió):**

```bash
# Reemplaza <ID> por el id de la cita de hoy
sudo docker exec dosys-db psql -U dosys -d dosys -c "
update appointments
set checked_in_at = now(), status = 'confirmed'
where id = <ID>;"
```

Después recarga **En espera** en el portal. No lo uses en la narrativa: es solo
para no detener la presentación.

---

## 5. Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué no React? | El portal es HTML del propio backend: menos piezas y el mismo despliegue. React queda para cuando crezca el equipo. |
| ¿Dónde están las contraseñas? | Hash **Argon2** en PostgreSQL; nadie puede verlas, solo restablecerlas. |
| ¿El paciente puede modificar su expediente? | No. La app es de solo lectura clínica; solo escribe login, check-in y solicitudes de cita. |
| ¿Qué pasa si pierdo el celular? | Se revoca desde el portal o desde otro dispositivo; el token deja de servir al instante. |
| ¿Cuántos dispositivos puede tener? | Hasta 3 activos; todos con acceso completo; cualquiera aprueba; el cuarto se rechaza. |
| ¿El QR se puede reutilizar? | No. Es de un solo uso y solo dentro de la ventana de la cita. |
| ¿El resultado del laboratorio es alterable? | El PDF lleva SHA-256 y sello HMAC del servidor; si cambia un byte, la verificación falla. |
| ¿Es una firma legal? | No. Es firma electrónica del servidor para integridad académica; una e.firma legal requiere certificado y sellado de tiempo. |
| ¿Aguanta datos reales? | La base técnica está; antes se requiere MFA, respaldos, cifrado en reposo, aviso de privacidad y revisión NOM-024. |
| ¿Se integra con otros sistemas? | Sí, por API REST/OpenAPI; hoy ya existen roles y tablas para laboratorio y recepción. |
| ¿Funciona sin Firebase? | Sí. Sin credenciales, las notificaciones quedan simuladas y la app usa sondeo cada 5 s. |

---

## 6. Frases que ayudan

- “Recepción no ve notas clínicas; el médico no ve la facturación; cada rol ve lo
  que necesita resolver.”
- “El QR es de la cita, no del paciente.”
- “El servidor no confía en la app: valida rol, dispositivo, hora y código.”
- “Una nota, tres salidas: expediente, receta y orden de laboratorio.”
- “El paciente no captura datos clínicos; solo lee la misma verdad.”
- “Nada se borra: se corrige y queda en la bitácora.”
- “Tres dispositivos, no uno: la clínica real no cabe en un solo teléfono.”

---

## 7. Checklist final (30 segundos antes de entrar)

- [ ] `curl` al health devuelve `ok`.
- [ ] `demo_reset.py --reset --live` corrió y dio cita de hoy.
- [ ] Cuatro perfiles abiertos con sus roles.
- [ ] Teléfono cargando, con cámara, ubicación, notificaciones y huella.
- [ ] QR de la cita de hoy abierto en la laptop.
- [ ] Credenciales a la mano (tabla de la sección 0.4).
- [ ] Notificaciones del sistema en silencio.
- [ ] Plan B impreso o en el teléfono.
