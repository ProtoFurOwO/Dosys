# 🏥 Funcionalidades Nuevas para el Portal Web D.O.S.Y.S

Análisis enfocado **solo en el portal web** (`/portal/*`). Revisé las 2,431 líneas de [routes.py](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/routes.py), las 27 plantillas Jinja2, el admin, los servicios y los modelos.

---

## Lo que ya tiene el portal (para no repetir)

| ✅ Ya existe | Detalle |
|---|---|
| Login + 2FA + recovery codes | Con rate limiting y bloqueo por intentos |
| Sesión renovable (refresh token en cookie) | Rotación automática |
| CRUD de pacientes | Nuevo, editar, buscar por nombre/CURP |
| Expediente completo | Consultas, documentos, estudios, recetas |
| Registrar consulta | Con recetas PDF, solicitar estudios y agendar siguiente cita en un solo flujo |
| Citas + QR check-in | Mostrar QR, asignar consultorio, check-in en vivo |
| Sala de espera | Auto-refresh con polling, botón "Atender" |
| Laboratorio | Cola de órdenes, captura de resultados, PDF con SHA-256 |
| Documentos clínicos | Subida, descarga, verificación de integridad (HMAC) |
| Admin: usuarios + roles + permisos | CRUD completo con credenciales imprimibles |
| Bitácora de auditoría | Filtro por acción y usuario |
| Recuperación de contraseña | Con enlace de un solo uso + email (Resend) |
| Mi seguridad | Cambio de contraseña, correo, activar/desactivar 2FA |

---

## 🆕 Funcionalidades que NO tiene y podríamos añadir

### 📊 1. Dashboard con Estadísticas Reales (Página de inicio mejorada)

**Actualmente:** La página principal (`/portal`) es solo la lista de pacientes con 3 métricas simples (total pacientes, consultas totales, consultas de hoy).

**Propuesta:** Transformarla en un dashboard real con:
- **Gráfica de consultas por día** de la última semana (barras con JS puro o Chart.js)
- **Citas de hoy** con cuenta regresiva y estados (agendada/confirmada/llegó/atendida)
- **Órdenes de lab pendientes** (counter rápido)
- **Últimos 5 movimientos** del log de auditoría
- **Pacientes atendidos hoy vs. ayer** (comparativa)

**Esfuerzo:** ⏱️⏱️ Medio — nuevo template `dashboard.html`, endpoint de datos, algo de JS para gráficas.

---

### 📅 2. Calendario Visual de Citas (Vista semanal/mensual)

**Actualmente:** Las citas se ven como tabla plana buscando por paciente. No hay vista de agenda por día/semana.

**Propuesta:** Agregar `/portal/agenda` con:
- Vista de **semana** con las horas como filas y los consultorios como columnas
- Código de color por estado (agendada = azul, confirmada = verde, cancelada = rojo)
- Click en un slot vacío para agendar cita directamente
- Filtro por médico y por consultorio

**Esfuerzo:** ⏱️⏱️⏱️ Alto — nuevo template, JS para la grilla, lógica de slots disponibles.

---

### 📊 3. Reportes Exportables (PDF/CSV)

**Actualmente:** Solo genera PDFs de recetas y resultados de laboratorio. No hay reportes administrativos.

**Propuesta:** Sección `/portal/reportes` con:
- **Consultas por período** (CSV/PDF con fecha, paciente, médico, diagnóstico)
- **Citas por médico** (cuántas agendó, cuántas atendió, tasa de asistencia)
- **Estudios solicitados** por tipo y por médico
- **Resumen mensual** del hospital (PDF con logo)
- Filtros de fecha de inicio/fin

**Esfuerzo:** ⏱️⏱️ Medio — reutiliza `reportlab` que ya está instalado, nuevos endpoints y un template.

---

### 🔔 4. Sistema de Notificaciones Internas (Alertas en el portal)

**Actualmente:** No hay notificaciones. El médico tiene que revisar manualmente la sala de espera, el laboratorio, etc.

**Propuesta:** Barra de notificaciones en el `panel.html` con:
- "Paciente X llegó al consultorio 3" (cuando hay check-in)
- "Resultado de laboratorio listo para paciente Y" 
- "Cita de Z es en 15 minutos"
- Icono con badge de contador en la barra lateral
- Endpoint JSON `/portal/notificaciones/estado` con polling

**Esfuerzo:** ⏱️⏱️ Medio — modelo `Notification`, lógica en los flujos existentes, JS en el layout.

---

### 💬 5. Notas Internas entre Personal (Chat clínico)

**Actualmente:** No hay comunicación entre el personal dentro del sistema.

**Propuesta:** Sección `/portal/mensajes` con:
- Mensajes internos entre usuarios del portal (médico → recepción, laboratorio → médico)
- Opcionalmente vinculados a un paciente o cita específica
- Historial de conversación tipo chat
- Indicador de "no leído" en la navegación

**Esfuerzo:** ⏱️⏱️⏱️ Alto — modelo `Message`, nuevo template, polling para nuevos mensajes.

---

### 🔍 6. Historial de Signos Vitales del Paciente

**Actualmente:** La consulta solo tiene motivo, diagnóstico y notas. No se registran signos vitales.

**Propuesta:** Agregar campos al formulario de consulta:
- Peso (kg), Talla (cm), IMC (calculado)
- Presión arterial (sistólica/diastólica)
- Temperatura (°C)
- Frecuencia cardíaca (bpm)
- Saturación de oxígeno (%)
- Tabla de historial en el expediente con tendencia

**Archivos afectados:** modelo `Consultation` (migración Alembic), [consultation_form.html](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/templates/consultation_form.html), [patient_detail.html](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/templates/patient_detail.html), [routes.py](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/routes.py) en la sección de consultas.

**Esfuerzo:** ⏱️⏱️ Medio — campos nuevos en modelo y formulario, tabla en expediente.

---

### 📋 7. Historial de Alergias y Antecedentes

**Actualmente:** El modelo `Patient` solo tiene datos demográficos (nombre, CURP, sangre, contacto, correo). No hay antecedentes médicos.

**Propuesta:** Agregar al expediente del paciente:
- Alergias (lista editable: medicamento + severidad)
- Antecedentes personales (diabetes, hipertensión, cirugías previas)
- Antecedentes familiares
- **Badge de alerta** en la parte superior del expediente si tiene alergias activas

**Esfuerzo:** ⏱️⏱️ Medio — modelo `PatientAllergy`, sección nueva en patient_detail.

---

### 🖨️ 8. Credencial Imprimible del Paciente con QR

**Actualmente:** Existe [credential.html](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/templates/credential.html) pero solo muestra usuario y contraseña al crear la cuenta. No es una credencial de identificación permanente.

**Propuesta:** Credencial tipo tarjeta con:
- Nombre completo, CURP, tipo de sangre
- QR con el ID del paciente (para escaneo rápido en recepción)
- Logo de D.O.S.Y.S
- Botón "Imprimir credencial" en el expediente del paciente
- CSS de impresión con tamaño tarjeta de crédito

**Esfuerzo:** ⏱️ Bajo — template nuevo + CSS `@media print`, reutiliza `qr_svg()`.

---

### ⏰ 9. Cancelación y Reagendamiento de Citas

**Actualmente:** Las citas se crean y se confirman con check-in, pero **no se pueden cancelar ni reagendar** desde el portal.

**Propuesta:** En la vista del QR de la cita (`/portal/citas/{id}`):
- Botón "Cancelar cita" con confirmación
- Botón "Reagendar" que lleva a un formulario con la nueva fecha/hora
- Historial de cambios de la cita (original → reagendada → cancelada)

**Archivos afectados:** [appointment_qr.html](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/templates/appointment_qr.html), nuevas rutas POST en routes.py.

**Esfuerzo:** ⏱️ Bajo — son 2-3 nuevas rutas y botones en el template existente.

---

### 🔎 10. Búsqueda Global (Pacientes + Citas + Estudios)

**Actualmente:** Cada sección tiene su propia búsqueda local (pacientes por nombre/CURP, citas por paciente).

**Propuesta:** Barra de búsqueda en la navegación (`panel.html`) que busque en:
- Pacientes (por nombre o CURP)
- Citas (por paciente o fecha)
- Estudios (por nombre del estudio o paciente)
- Resultados agrupados por categoría

**Esfuerzo:** ⏱️⏱️ Medio — endpoint `/portal/buscar`, template de resultados, query combinada.

---

### 👨‍⚕️ 11. Perfil del Médico (Mi perfil)

**Actualmente:** El médico solo tiene "Mi seguridad" (contraseña + 2FA). No puede ver ni editar su nombre, especialidad ni foto.

**Propuesta:** Sección `/portal/perfil` con:
- Ver y editar: nombre completo, especialidad, cédula profesional
- Resumen de actividad: consultas realizadas este mes, pacientes atendidos
- Último acceso registrado

**Esfuerzo:** ⏱️ Bajo — template nuevo, route nueva, datos ya existen en modelo `Doctor`.

---

### 📄 12. Plantillas de Consulta Predefinidas

**Actualmente:** Cada consulta se llena desde cero (motivo, diagnóstico, notas, receta).

**Propuesta:** Permitir guardar "plantillas" de consulta reutilizables:
- "Consulta de control de diabetes" → prellenar motivo, diagnóstico y receta frecuente
- El médico las guarda desde una consulta exitosa
- Selector de plantilla al iniciar una nueva consulta
- Cada médico tiene sus propias plantillas

**Esfuerzo:** ⏱️⏱️ Medio — modelo `ConsultationTemplate`, select en consultation_form.html, endpoint CRUD.

---

### 🏷️ 13. Etiquetas/Tags para Pacientes

**Actualmente:** Los pacientes no tienen categorización más allá de los datos demográficos.

**Propuesta:** Sistema de etiquetas por paciente:
- "Embarazo de alto riesgo", "Diabetes controlada", "Seguimiento postquirúrgico"
- Filtro por etiqueta en la lista de pacientes
- Chips de colores visibles en el expediente
- El médico puede crear etiquetas nuevas

**Esfuerzo:** ⏱️⏱️ Medio — modelo `Tag` + `PatientTag`, filtro en la lista, chips en el detalle.

---

### 🌙 14. Tema Oscuro para el Portal

**Actualmente:** [portal.css](file:///c:/Users/Angel-PC/Downloads/Dosys/backend/app/portal/static/portal.css) usa un solo tema claro (27 KB de CSS bien organizado).

**Propuesta:** 
- Variables CSS con `prefers-color-scheme: dark`
- Toggle manual en la barra lateral con persistencia en cookie
- Colores oscuros que reduzcan fatiga visual en turnos nocturnos

**Esfuerzo:** ⏱️ Bajo — solo CSS con variables + un pequeño JS para el toggle.

---

### 📱 15. Vista Responsiva Mejorada (Tablet/Móvil)

**Actualmente:** El portal tiene `.hide-sm` para ocultar columnas, pero no está optimizado para tablets ni celulares del personal médico.

**Propuesta:**
- Sidebar colapsable en pantallas pequeñas (hamburger menu)
- Formulario de consulta en una sola columna en tablets
- Tablas con scroll horizontal en móviles
- Mapa de la sala de espera optimizado para tablet en recepción

**Esfuerzo:** ⏱️⏱️ Medio — media queries en portal.css, JS para toggle del sidebar.

---

## 📊 Resumen Rápido

| # | Funcionalidad | Impacto | Esfuerzo | Quick Win? |
|---|---|---|---|---|
| 1 | Dashboard con estadísticas | 🔴 Alto | ⏱️⏱️ | |
| 2 | Calendario de citas | 🔴 Alto | ⏱️⏱️⏱️ | |
| 3 | Reportes exportables | 🟠 Medio | ⏱️⏱️ | |
| 4 | Notificaciones internas | 🟠 Medio | ⏱️⏱️ | |
| 5 | Chat entre personal | 🟡 Bajo | ⏱️⏱️⏱️ | |
| 6 | Signos vitales | 🔴 Alto | ⏱️⏱️ | |
| 7 | Alergias y antecedentes | 🔴 Alto | ⏱️⏱️ | |
| 8 | Credencial con QR | 🟡 Bajo | ⏱️ | ✅ |
| 9 | Cancelar/reagendar citas | 🟠 Medio | ⏱️ | ✅ |
| 10 | Búsqueda global | 🟡 Bajo | ⏱️⏱️ | |
| 11 | Perfil del médico | 🟡 Bajo | ⏱️ | ✅ |
| 12 | Plantillas de consulta | 🟠 Medio | ⏱️⏱️ | |
| 13 | Etiquetas de pacientes | 🟡 Bajo | ⏱️⏱️ | |
| 14 | Tema oscuro | 🟡 Bajo | ⏱️ | ✅ |
| 15 | Responsivo mejorado | 🟠 Medio | ⏱️⏱️ | |

---

> [!TIP]
> **Mi recomendación de orden:**
> 1. **Cancelar/reagendar citas** (9) — falta obvia, fácil, útil para la demo
> 2. **Signos vitales** (6) — da mucho peso clínico al proyecto
> 3. **Dashboard** (1) — causa impacto visual inmediato al abrir el portal
> 4. **Credencial con QR** (8) — quick win que luce en la presentación
> 5. **Tema oscuro** (14) — otro quick win visual

> [!NOTE]
> Dime cuáles quieres implementar y las hacemos juntos. Puedo empezar con varias a la vez si son independientes.
