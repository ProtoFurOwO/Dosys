# Portal clínico D.O.S.Y.S — flujo profesional y decisiones de UX

Fecha: 2026-11-09
Alcance: portal web del personal (recepción, médico, laboratorio, administración).

## 1. Objetivo

Que el portal se comporte como una clínica real, no como un CRUD académico:

1. Cada rol entra y ve primero lo que necesita resolver.
2. El paciente sigue un recorrido claro: registro → cita → llegada → consulta → estudios/receta → resultados → seguimiento.
3. La nota clínica sigue una estructura profesional (SOAP) con signos vitales.
4. Cada acción tiene feedback, validación y trazabilidad.
5. La interfaz reduce carga cognitiva: jerarquía, estados visibles y menos clics.

## 2. Investigación

### 2.1 Flujo clínico y carga de documentación

La revisión de usabilidad de EHR de PMC concluye que los sistemas fallan cuando
no se alinean con el trabajo real: obligan a copiar información, fragmentan la
consulta y generan alertas excesivas. Recomienda análisis de tareas, módulos
integrados (agenda, notas, resultados) y alertas contextuales.

- Fuente: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12206486/>
- Aplicado: agenda, espera, consulta, estudios y resultados viven en el mismo
  portal; el dashboard muestra solo lo urgente del día.

### 2.2 Planificación previa y comunicación con el paciente

AMA recomienda planificación previa, liberación de resultados normales y
resúmenes después de la visita para reducir carga administrativa y mejorar la
experiencia del paciente.

- Fuente: <https://edhub.ama-assn.org/steps-forward/module/2821565>
- Aplicado: el paciente ve consultas, recetas y resultados en la app; el portal
  conserva la receta PDF y el resultado firmado.

### 2.3 Nota clínica SOAP

La nota SOAP separa Subjetivo (lo que reporta el paciente), Objetivo (signos
vitales y exploración), Análisis (impresión/diagnóstico) y Plan (indicaciones,
estudios, receta y seguimiento). Reduce omisiones y facilita auditoría.

- Fuente: <https://www.ncbi.nlm.nih.gov/books/NBK482263/>
- Fuente: <https://tandemhealth.ai/resources/knowledge/soap-format-clinical-documentation-practical-guide>
- Aplicado: formulario de consulta con bloques S/O/A/P, signos vitales, IMC
  calculado, exploración física, diagnóstico y plan.

### 2.4 UI/UX para salud

Buenas prácticas recurrentes:

- Vistas por rol y jerarquía clara; no dar el mismo peso a todo.
- Accesibilidad WCAG AA, contraste y navegación por teclado.
- Mostrar primero lo urgente: espera, estudios pendientes, citas del día.
- Evitar sobrecarga visual; tarjetas pequeñas, listas escaneables y acciones
  contextuales.
- Feedback inmediato y prevención de dobles envíos.

Fuentes:

- <https://fuselabcreative.com/healthcare-ux-design-best-practices-guide/>
- <https://www.thinkitive.com/blog/best-practices-in-healthcare-dashboard-design/>
- <https://www.aufaitux.com/blog/healthcare-dashboard-ui-ux-design-best-practices/>

## 3. Flujo implementado

### Recepción

1. Login.
2. Dashboard: citas de hoy, sala de espera, accesos rápidos.
3. Alta de paciente con credencial de una sola vez.
4. Agenda de cita; QR de check-in.
5. Confirmación de llegada, asignación de consultorio.
6. No ve notas clínicas ni alertas clínicas; sí identificación, contacto y
   agenda.

### Médico

1. Login.
2. Dashboard: agenda del día, pacientes en espera, estudios pendientes,
   consultas recientes y actividad.
3. Abre expediente: alertas, línea de tiempo, consultas, estudios, documentos.
4. Nueva consulta SOAP:
   - S: motivo.
   - O: presión, FC, FR, temperatura, SpO₂, peso, talla, IMC y exploración.
   - A: diagnóstico.
   - P: plan, estudios, receta, próxima cita.
5. Guarda; se actualiza expediente, se genera receta PDF y orden de laboratorio.
6. Corrige consultas con auditoría de campos.

### Laboratorio

1. Login.
2. Dashboard: estudios pendientes.
3. Cola de laboratorio: iniciar, capturar resultado, PDF firmado.
4. El paciente ve el resultado en la app.

### Administración / auditoría

1. Dashboard con usuarios y actividad.
2. Usuarios, roles y permisos dinámicos.
3. Bitácora de solo lectura con IP real, acción y entidad.

### Paciente (app)

1. Login con dispositivo de confianza.
2. Inicio, expediente, consultas, estudios, recetas, citas, documentos y QR.
3. Solo lectura; no puede modificar información clínica.

## 4. Decisiones de diseño

- **Dashboard separado** (`/portal/inicio`) para no convertir la lista de
  pacientes en el home.
- **Navegación por rol**: Inicio, Pacientes, Citas, Agenda, En espera,
  Laboratorio; administración en engranaje.
- **SOAP visual** con letras S/O/A/P y bloques separados.
- **Signos vitales opcionales** para no bloquear consultas rápidas, pero con
  validación de rangos y formato de presión.
- **IMC en vivo** con clasificación simple.
- **Línea de tiempo clínica** que une consultas, estudios, recetas y documentos.
- **Stepper de cita**: Agendada → Confirmada → En espera → Atendida.
- **Feedback**: validación inline, resumen de errores, botón “Guardando…” y
  bloqueo de doble envío.
- **Accesibilidad**: foco visible, etiquetas, `aria-live` para estado, contraste
  y adaptación a móvil.

## 5. Pendientes / siguiente iteración

- Rol de enfermería/triage para capturar signos vitales antes del médico.
- Reglas de alerta clínica configurables (alergias, interacciones, signos fuera
  de rango).
- Nota de consulta imprimible/PDF además de la receta.
- Recordatorios de cita y resultados por correo/push.
- Adjuntar resultados de imagen y visor DICOM (fuera del alcance académico).
- Android: mostrar bloques SOAP, signos vitales y línea de tiempo (ver
  `ANDROID_UPDATE_BRIEF.md`).
- Revisión de privacidad: separar documentos clínicos de documentos
  administrativos para recepción.
