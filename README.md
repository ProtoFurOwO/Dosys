# D.O.S.Y.S — App Android (paciente)

Aplicación móvil **nativa** del paciente (Kotlin + Jetpack Compose). Consulta información
clínica en **modo solo lectura**, da seguimiento a tratamientos, confirma la llegada con
**cámara** (check-in QR) y protege el expediente con **huella**.

## Requisitos

- Android Studio (Ladybug o superior)
- JDK 17 o superior (se probó con JDK 21)
- Android SDK con la plataforma **android-35**

## Cómo ejecutarla (sin ayuda)

### Opción A — Android Studio (la más fácil)

1. Abre **Android Studio**.
2. **File → Open** y selecciona esta carpeta: `android/` (no la carpeta del proyecto web, sino `android`).
3. Espera a que termine de sincronizar Gradle (barra inferior).
4. Arriba, en el selector de dispositivos, elige **DosysPhone** (o crea un emulador Pixel).
5. Pulsa el botón verde **▶ Run**.
6. Primero inicia el backend local (`backend/README.md`); en el login usa `paciente` / `Paciente123!`.

Si el emulador no aparece: **Device Manager** (icono de celular con una lupa) → el AVD `DosysPhone` ya está creado. Púlsalo ▶.

### Opción B — Teléfono físico

1. En el teléfono: **Ajustes → Acerca del teléfono → toca 7 veces el número de compilación** (activa opciones de desarrollador).
2. **Opciones de desarrollador → Depuración USB** → ON.
3. Conecta el cable. Acepta “¿Permitir depuración USB?”.
4. En Android Studio el teléfono aparece en el selector. ▶ Run.

### Opción C — APK de demostración (la que usarás con el profe)

El APK ya viene compilado apuntando al backend real (`https://medicos.stolasimp.dev/api/v1/`):

```
Proyecto/dosys-demo-vps.apk
```

Cópialo al teléfono (cable, Drive o WhatsApp) e instálalo. Android pedirá permitir
“instalar apps de origen desconocido” la primera vez. No necesita estar en la misma red:
funciona con datos móviles porque todo va por HTTPS.

### Opción D — Terminal

```powershell
cd android
.\gradlew.bat :app:installDebug
# APK apuntando a otro backend:
.\gradlew.bat :app:assembleDebug -PapiBaseUrl=https://medicos.stolasimp.dev/api/v1/
```

El emulador debe estar encendido (Android Studio o `emulator -avd DosysPhone`).

## Módulos del celular (requisito de la materia)

| Módulo | Dónde | Cómo se demuestra |
|---|---|---|
| **Cámara** | Check-in con QR | Recepción muestra el QR en el portal; el paciente lo escanea y confirma su llegada al backend |
| **Huella** | Mi expediente | `BiometricPrompt` pide huella (o bloqueo del teléfono) antes de mostrar datos clínicos |
| **GPS** | Check-in | Mapa real (OpenStreetMap) con el pin del hospital, tu ubicación y la distancia en metros |

El mapa usa **OSMDroid + OpenStreetMap**: no necesita API key ni cuenta de Google.
Las coordenadas del hospital de demostración son `16.755731, -93.136586` (Sanatorio en Tuxtla Gutiérrez).

La cámara está en el **celular del paciente** (que es la app del proyecto). El hospital solo
**muestra** el QR en pantalla desde el portal; no necesita cámara ni permisos del navegador.

## Recorrido de la demo

| Desde Home | Qué ves |
|---|---|
| Próxima cita | Lista de citas (agendada / confirmada / atendida) |
| Tratamiento activo / Recetas | Receta del médico + botón **Ya la tomé** |
| Expediente | **Pide huella** y luego muestra CURP, consultas reales del backend |
| Estudios | Flujo Solicitado → En proceso → Listo (toca uno para el resultado) |
| Mi QR | QR que expira en 3 min + código de respaldo `A7K9M2` |
| **Check-in con QR** | **Abre la cámara**, escanea el QR de recepción y confirma la llegada |

### Guion para la demo (dos dispositivos)

1. En la laptop, portal → **Citas** → muestra el QR de la cita del paciente.
2. En el celular: **Check-in con QR → Abrir cámara** → apunta al QR de la laptop.
3. La app responde “Llegada confirmada”; el portal, al recargar, muestra “Llegó 16:32”.
4. Extra: abre **Mi expediente** y desbloquea con la huella.

## Estructura

```
app/src/main/java/mx/unach/dosys/
├─ DosysApp.kt · MainActivity.kt
├─ core/auth · core/di
├─ data/model · data/remote · data/repository · data/mock
└─ ui/
   ├─ login · home · checkin
   ├─ record · studies · prescriptions · appointments · qr
   ├─ navigation · theme · components
```

## Backend (FastAPI)

La app usa el backend real para inicio de sesión, perfil, citas, consultas y check-in.
El tutorial completo está en [`backend/README.md`](backend/README.md).

- Emulador: `http://10.0.2.2:8000/api/v1/` (apunta a tu PC).
- Producción: `https://medicos.stolasimp.dev/api/v1/`.

### Si el emulador no tiene red

Comprueba dentro del emulador: `adb shell ping -c 1 10.0.2.2`. Si falla, reinicia el AVD con
**Cold Boot Now** desde el Device Manager o ejecuta `emulator -avd DosysPhone -no-snapshot`.

## Notas de seguridad

- Solo `MainActivity` está exportada (requisito del launcher).
- El token de sesión **no** se incluye en respaldos.
- El expediente se protege con huella; si el teléfono no tiene biometría, se avisa y se deja continuar (decisión de demostración).
- `SessionManager` pendiente de endurecer con Android Keystore.
