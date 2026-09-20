# D.O.S.Y.S — App Android (paciente)

Aplicación móvil **nativa** del paciente (Kotlin + Jetpack Compose). Permite consultar
información clínica en **modo solo lectura**, dar seguimiento a tratamientos y mostrar el
código QR para el check-in en el hospital.

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

### Opción C — Terminal

```powershell
cd "C:\Users\josea\OneDrive\Documents\Septimo Semestre\Desarrolloweb\Proyecto\android"
.\gradlew.bat :app:installDebug
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am start -n mx.unach.dosys/.MainActivity
```

El emulador debe estar encendido (Android Studio o `emulator -avd DosysPhone`).

## Recorrido de la demo

| Desde Home | Qué ves |
|---|---|
| Próxima cita | Lista de citas (agendada / confirmada / atendida) |
| Tratamiento activo / Recetas | Receta del médico + botón **Ya la tomé** |
| Expediente | CURP, alergias, crónicas, consultas |
| Estudios | Flujo Solicitado → En proceso → Listo (toca uno para el resultado) |
| Mi QR | QR que expira en 3 min + código de respaldo `A7K9M2` |

## Estructura

```
app/src/main/java/mx/unach/dosys/
├─ DosysApp.kt · MainActivity.kt
├─ core/auth · core/di
├─ data/model · data/remote · data/repository · data/mock
└─ ui/
   ├─ login · home
   ├─ record · studies · prescriptions · appointments · qr
   ├─ navigation · theme · components
```

## Backend local (FastAPI)

La app ya usa el backend real para inicio de sesión, perfil, citas y consultas.
El tutorial completo está en [`backend/README.md`](backend/README.md).

En el emulador, `10.0.2.2` apunta a tu computadora (`API_BASE_URL` en `app/build.gradle.kts`).
Primero levanta `backend/` y verifica `http://127.0.0.1:8000/health`.

Los módulos de estudios, recetas y QR siguen mostrando datos demo hasta que se agreguen sus endpoints.

### Si el emulador no tiene red

Comprueba dentro del emulador: `adb shell ping -c 1 10.0.2.2`. Si falla, reinicia el AVD con
**Cold Boot Now** desde el Device Manager o ejecuta `emulator -avd DosysPhone -no-snapshot`.

## Notas de seguridad

- Solo `MainActivity` está exportada (requisito del launcher).
- El token de sesión **no** se incluye en respaldos.
- Cleartext solo hacia `10.0.2.2` y `localhost`.
- `SessionManager` pendiente de endurecer con Android Keystore.
