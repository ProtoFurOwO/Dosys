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
6. En el login usa cualquier usuario y una contraseña de **4 caracteres o más** (demo). Ejemplo: `paciente` / `1234`.

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

## Conectar el backend (FastAPI)

Mientras el backend no exista, la app usa `FakeAuthRepository`.

Para conectar la API real, en `core/di/ServiceLocator.kt`:

```kotlin
authRepository = RemoteAuthRepository(NetworkModule.create(), sessionManager)
```

En el emulador, `10.0.2.2` apunta a tu computadora (`API_BASE_URL` en `app/build.gradle.kts`).

## Notas de seguridad

- Solo `MainActivity` está exportada (requisito del launcher).
- El token de sesión **no** se incluye en respaldos.
- Cleartext solo hacia `10.0.2.2` y `localhost`.
- `SessionManager` pendiente de endurecer con Android Keystore.
