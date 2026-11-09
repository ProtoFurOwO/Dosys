# D.O.S.Y.S en 10 minutos — 6 min de app, 4 min de clínica

**Formato:** 1 laptop + 1 teléfono espejado + 4 perfiles de navegador.
**Regla:** 60% del tiempo es la app del paciente. El portal es el “backstage” que
hace posible lo que el paciente ve.

| Bloque | Tiempo | Porcentaje |
|---|---:|---:|
| Apertura | 0:00–0:30 | 5% |
| **App del paciente** | **0:30–6:30** | **60%** |
| Portal y talacha clínica | 6:30–8:30 | 20% |
| Seguridad, auditoría y dispositivos | 8:30–9:30 | 10% |
| Cierre | 9:30–10:00 | 5% |

---

## 0. Antes de presentar (T-10 minutos)

### 0.1 Preparar el día

```bash
curl -s https://medicos.stolasimp.dev/health
# {"status":"ok","database":"ok"}

sudo docker exec dosys-api python scripts/demo_reset.py --reset --live
sudo docker exec dosys-api python scripts/demo_status.py
```

`demo_status.py` debe mostrar:

- `Dispositivos activos: 0/3`
- cita de hoy `confirmed` con `check-in=ABIERTO`
- solicitud pendiente para mañana
- una orden de laboratorio pendiente

El reset deja además:

- una **consulta SOAP** con signos vitales;
- un **resultado de química sanguínea ya listo** con PDF firmado;
- una **biometría pendiente** para el portal;
- una **nota de consulta firmada**;
- la cuenta `demo.paciente` **sin dispositivos**.

### 0.2 Espejar el teléfono

La app es el 60% de la presentación: el público debe verla. Usa `scrcpy` o la
herramienta de espejo de Android Studio.

```bash
scrcpy --stay-awake --max-size=1024
```

Si no tienes espejo, usa un soporte para el teléfono y proyecta la pantalla con
la cámara del salón; pero `scrcpy` se ve mucho mejor.

### 0.3 Cuentas

| Rol | Usuario | Contraseña | Uso |
|---|---|---|---|
| Paciente (app) | `demo.paciente` | `Paciente123!` | 6 minutos de app |
| Recepción | `demo.recepcion` | `Recepcion123!` | Confirmar solicitud y QR |
| Médico | `demo.medico` | `Medico123!` | SOAP y receta |
| Laboratorio | `laboratorio` | `Lab12345!` | Resultado y PDF |
| Admin | `demo.admin` | `Admin123!` | Bitácora y dispositivos |

`demo.admin` no tiene 2FA. No uses `admin` en vivo si no tienes el autenticador.

### 0.4 Cuatro perfiles de navegador

El portal comparte cookie por navegador. Usa **cuatro perfiles distintos** o
cuatro navegadores:

1. Recepción: `/portal/inicio`
2. Médico: `/portal/inicio`
3. Laboratorio: `/portal/laboratorio`
4. Admin: `/portal/usuarios` y `/portal/actividad`

Abre en Recepción la cita de hoy (`/portal/citas/<id>`) con el QR visible.
No uses varias pestañas del mismo perfil: el login de un rol pisa al otro.

### 0.5 Teléfono

- APK construido desde `master`.
- Cámara, ubicación y notificaciones concedidas.
- Huella/PIN configurados.
- En **No molestar**, cargando.
- Sesión cerrada: el primer login en vivo registra el dispositivo.
- Ten a la mano el **código de respaldo** del QR.

---

## 1. Apertura — 0:00 a 0:30

**Decir:**

> “Voy a ocupar 6 de los 10 minutos en la app del paciente, porque ahí es donde
> se ve si el sistema sirve. El portal es el backstage: recepción, médico y
> laboratorio trabajan sobre el mismo expediente que el paciente ve en su teléfono.
> No son dos sistemas: es el mismo backend y la misma base PostgreSQL.”

**Hacer:** muestra el teléfono espejado y la laptop con Recepción.

---

## 2. App del paciente — 0:30 a 6:30 (60%)

### 2.1 Login y Home — 0:30 a 1:15

**Hacer:**

1. Abre la app.
2. Inicia sesión con `demo.paciente` / `Paciente123!`.
3. Muestra el **Home**:
   - saludo con el nombre;
   - próxima cita;
   - tratamiento activo;
   - accesos: **Expediente, Estudios, Recetas, Documentos, Check-in con QR,
     Mi seguridad**.

**Decir:**

> “La app no es un visor de PDFs. Es el expediente del paciente en el bolsillo:
> cita, receta, estudios, documentos y seguridad. Este primer login registra el
> teléfono como dispositivo de confianza.”

**No te detengas aquí:** 45 segundos máximo.

---

### 2.2 Mi expediente + huella — 1:15 a 2:05

**Hacer:**

1. Toca **Expediente**.
2. Pide **huella**.
3. Muestra:
   - datos del paciente;
   - alergias en rojo;
   - antecedentes y diagnósticos crónicos;
   - historial de consultas con motivo y diagnóstico.

**Decir:**

> “El paciente no puede editar nada: solo leer. La huella protege el acceso local.
> Las alergias y los crónicos vienen del expediente real que capturó el hospital,
> no de un formulario de la app.”

---

### 2.3 Mis citas y solicitud — 2:05 a 3:05

**Hacer:**

1. Regresa y abre **Mis citas**.
2. Muestra la cita de hoy **confirmada** y la solicitud de mañana en estado
   **Solicitada**.
3. Explica el flujo: el paciente solicita, recepción confirma, hasta entonces no
   hay QR.
4. Si el tiempo alcanza, toca **Solicitar cita** y muestra los pasos:
   médico → fecha → horario → motivo → **Enviar solicitud**.

**Decir:**

> “La cita no nace confirmada: nace como solicitud. Eso evita que el paciente
> invente horarios o bloquee la agenda. Recepción conserva el control; el paciente
> ve el estado en tiempo real.”

**Si vas retrasado:** no envíes una solicitud nueva; solo muestra la que ya está
en estado `Solicitada`.

---

### 2.4 Check-in con QR — 3:05 a 3:55

**Hacer:**

1. Abre **Check-in con QR**.
2. La laptop debe tener visible el QR de la cita de hoy.
3. Toca **Abrir cámara** y escanea.
4. Muestra la confirmación en la app.
5. Muestra que la cita cambia a **Check-in confirmado**.

**Decir:**

> “El QR es de la cita, no del paciente. Es de un solo uso y solo funciona dentro
> de la ventana: 2 horas antes y 4 horas después. El servidor valida la hora y el
> código; la app no decide si puede entrar.”

**Plan B:** si la cámara falla, escribe el **código de respaldo** en el campo y
pulsa **Confirmar con el código**.

---

### 2.5 Recetas y estudios — 3:55 a 4:55

**Hacer:**

1. Abre **Recetas**. Muestra la receta de la consulta y abre el **PDF**.
2. Regresa y abre **Estudios**.
3. Muestra:
   - **Química sanguínea** con resultado listo y **Ver resultado (PDF)**;
   - **Biometría** pendiente.

**Decir:**

> “La receta y el resultado no los inventa la app: los firma el servidor. El
> paciente ve el mismo PDF que ve el médico y el laboratorio. La biometría sigue
> pendiente porque el laboratorio todavía no la captura.”

---

### 2.6 Documentos e integridad — 4:55 a 5:50

**Hacer:**

1. Abre **Documentos**.
2. Entra a la **Nota de consulta** o al **Resultado de química**.
3. Pulsa **Verificar firma**.
4. Muestra el mensaje de firma válida y la huella.

**Decir:**

> “Cada documento lleva una huella SHA-256 y un sello del servidor. Si alguien
> cambia un solo byte, la verificación falla. No es una firma legal con e.firma,
> pero sí demuestra integridad y autoría interna.”

---

### 2.7 Dispositivos de confianza — 5:50 a 6:30

**Hacer:**

1. Regresa y abre **Mi seguridad**.
2. Entra a **Administrar dispositivos**.
3. Muestra el teléfono actual como **Este dispositivo**.
4. Lee el texto: hasta 3 teléfonos, todos con acceso completo, cualquiera puede
   autorizar uno nuevo, los demás siguen activos.
5. Muestra **Revocar** (sin usarlo todavía).

**Decir:**

> “La clínica real no cabe en un solo teléfono. Hasta 3 dispositivos, todos con
> acceso completo. Cualquiera puede aprobar un alta; el cuarto se rechaza con 409.
> Revocar uno no cierra los demás.”

**Cierre del bloque app:**

> “Eso es la app: expediente, citas, check-in, recetas, estudios, documentos
> firmados y dispositivos. Ahora veamos quién hace posible esa información.”

---

## 3. Portal y talacha clínica — 6:30 a 8:30

### 3.1 Recepción confirma la solicitud — 6:30 a 7:10

**Hacer:**

1. En Recepción, abre **Inicio → Solicitudes de cita**.
2. Abre la solicitud de `Paciente Demo` para mañana.
3. Pulsa **Confirmar cita**.
4. Abre **En espera**: el check-in de la app ya aparece reflejado.
5. Muestra la cita de hoy con **Check-in** y **Consultorio 3**.

**Decir:**

> “Lo que el paciente solicitó desde la app aparece aquí. Recepción confirma y
> recién ahí se habilita el QR. El check-in que hizo el paciente hace un minuto
> ya está en la sala de espera.”

---

### 3.2 Médico: SOAP, receta y orden — 7:10 a 8:10

**Hacer:**

1. En Médico, abre **Inicio**. Muestra la sala de espera.
2. Entra al expediente de `Paciente Demo`.
3. Abre la **consulta** que ya está registrada.
4. Muestra:
   - S: motivo;
   - O: presión, FC, FR, temperatura, SpO₂, peso/talla e IMC;
   - A: diagnóstico;
   - P: plan, receta y estudio.
5. Abre la **receta PDF** y la **orden de laboratorio**.

**Decir:**

> “El médico documenta una sola vez y salen tres cosas: la nota en el expediente,
> la receta y la orden de laboratorio. Los signos vitales y el IMC se calculan en
> el servidor. Si corrige, la bitácora guarda qué cambió, no el contenido clínico.”

**Si te sobra tiempo:** muestra el botón **Llenar ejemplo** (`Alt+Shift+D`) y
menciona que el formulario también se puede capturar a mano.

---

### 3.3 Laboratorio y resultado — 8:10 a 8:30

**Hacer:**

1. En Laboratorio, muestra la **Biometría pendiente**.
2. Abre el **Resultado PDF** de la química ya completada.
3. Señala la huella y la firma.

**Decir:**

> “El laboratorio ve la orden que pidió el médico. Al capturar el resultado se
> genera un PDF firmado. El paciente ya lo tiene en la app: no hay que mandarlo
> por WhatsApp ni imprimirlo.”

---

## 4. Seguridad, auditoría y dispositivos — 8:30 a 9:30

### 4.1 Auditoría — 8:30 a 9:00

**Hacer:**

1. En Admin, abre **Actividad**.
2. Filtra por `consultation`, `study_order` o `appointment`.
3. Muestra las acciones de la demo: alta de paciente, cita confirmada, check-in,
   consulta y resultado.
4. Descarga el **CSV**.

**Decir:**

> “Cada acción queda con usuario, IP real, entidad y detalle. El rol no se decide
> en la pantalla: el servidor lo valida en cada petición.”

---

### 4.2 Dispositivos y permisos — 9:00 a 9:30

**Hacer:**

1. En Admin, abre **Usuarios → Paciente Demo → Dispositivos de confianza**.
2. Muestra el teléfono actual.
3. Muestra **Revocar** y **Restablecer todos los dispositivos**.
4. Menciona los roles: recepción no ve notas clínicas; médico no ve usuarios;
   laboratorio no ve la agenda completa.

**Decir:**

> “Máximo 3 dispositivos, todos con acceso completo, cualquiera puede aprobar.
> Revocar uno invalida su token al instante y los demás siguen. Los permisos se
> validan en el servidor, no en la interfaz.”

---

## 5. Cierre — 9:30 a 10:00

**Decir:**

> “D.O.S.Y.S es una app nativa para el paciente y un portal clínico para el
> hospital, sobre el mismo backend FastAPI y PostgreSQL. La app no es un adorno:
> es donde el paciente ve su expediente, su receta, su resultado y su cita.
> El portal es donde recepción, médico y laboratorio hacen la talacha, con roles,
> auditoría y documentos firmados. Todo corre en Docker con HTTPS. Lo que sigue
> es endurecerlo para producción: correo real, FCM, respaldos, monitoreo y
> revisión NOM-024.”

**Cierre corto:**

> “Una sola verdad clínica, dos experiencias: el paciente en su teléfono y el
> hospital en el portal.”

---

## 6. Si el tiempo se acorta

Recorta en este orden:

1. La solicitud de cita nueva en la app (deja solo la que ya está pendiente).
2. La sección de dispositivos en la app (menciónala en seguridad).
3. El laboratorio en el portal (el resultado ya se mostró en la app).
4. La descarga del CSV.

**No recortes:** login/Home, expediente con huella, check-in, recetas/estudios,
documentos, SOAP del portal y cierre.

---

## 7. Comandos de preparación

```bash
# Día en vivo: cita de hoy confirmada, resultado listo y orden pendiente
sudo docker exec dosys-api python scripts/demo_reset.py --reset --live

# Estado sin SQL
sudo docker exec dosys-api python scripts/demo_status.py

# Modo histórico: cita para mañana
sudo docker exec dosys-api python scripts/demo_reset.py --reset

# Ver cita, código y ventana
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

# Ver dispositivos
sudo docker exec dosys-db psql -U dosys -d dosys -c "
select d.id, d.name, d.is_active, d.last_seen_at
from user_devices d
join users u on u.id = d.user_id
where u.username = 'demo.paciente'
order by d.id;"
```

Limpiar dispositivos si la app se queda en “autoriza este dispositivo”:

```bash
sudo docker exec dosys-db psql -U dosys -d dosys -c "
update user_devices set is_active = false
where user_id = (select id from users where username = 'demo.paciente');
update refresh_tokens set revoked_at = now()
where user_id = (select id from users where username = 'demo.paciente')
  and revoked_at is null;"
```

Verificaciones de aceptación (antes de la demo, no durante):

```bash
sudo docker exec dosys-api python scripts/verify_checkin.py
sudo docker exec dosys-api python scripts/verify_clinical_flow.py
sudo docker exec dosys-api bash scripts/demo_integrity.sh
```

---

## 8. Plan B

| Falla | Plan B |
|---|---|
| La cámara no lee el QR | Escribe el **código de respaldo** y confirma |
| El teléfono no conecta | Otro teléfono/emulador; el login es el mismo |
| La app no abre | Sigue con el portal; el resultado ya está en la laptop |
| El check-in no avanza | Marca la cita como **Atendida** en Agenda y sigue |
| La cita ya pasó | `demo_reset.py --reset --live` y re-login |
| Laboratorio no carga | Muestra el PDF ya completado de la química |
| Se cae internet | Hotspot o video de respaldo |
| Un rol perdió sesión | Vuelve a entrar; credenciales en la tabla |

Modo bombero para check-in (solo si el teléfono murió):

```bash
# Reemplaza <ID> por la cita de hoy
sudo docker exec dosys-db psql -U dosys -d dosys -c "
update appointments
set checked_in_at = now(), status = 'confirmed'
where id = <ID>;"
```

Recarga **En espera** y continúa. No lo uses en la narrativa.

---

## 9. Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿La app puede editar el expediente? | No. Solo lee; escribe login, check-in y solicitudes de cita. |
| ¿Cuántos dispositivos? | Hasta 3 activos, todos con acceso completo; cualquiera aprueba; el cuarto se rechaza. |
| ¿Qué pasa si pierdo el teléfono? | Se revoca desde el portal o desde otro dispositivo; el token deja de servir al instante. |
| ¿El QR se reutiliza? | No. Es de un solo uso y solo dentro de la ventana. |
| ¿El resultado es alterable? | Lleva SHA-256 y sello HMAC; si cambia un byte, la verificación falla. |
| ¿Es firma legal? | No. Es firma electrónica del servidor para integridad académica. |
| ¿Por qué no React? | El portal es HTML del backend; menos piezas y el mismo despliegue. |
| ¿Funciona sin Firebase? | Sí. Sin credenciales, la notificación queda simulada y la app usa sondeo. |
| ¿Aguanta datos reales? | Falta endurecer: MFA, respaldos, cifrado en reposo, aviso de privacidad y NOM-024. |

---

## 10. Checklist final

- [ ] Health en `ok`.
- [ ] `demo_reset.py --reset --live` corrió.
- [ ] `demo_status.py` muestra cita de hoy, QR abierto y laboratorio pendiente.
- [ ] Teléfono espejado con `scrcpy`.
- [ ] Cuatro perfiles de navegador abiertos.
- [ ] QR de la cita de hoy visible en Recepción.
- [ ] `demo.paciente` sin sesión iniciada.
- [ ] Credenciales a la mano.
- [ ] Notificaciones en silencio.
- [ ] Plan B localizado.
