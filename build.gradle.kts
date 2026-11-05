// Build script raíz: solo declara los plugins, sin aplicarlos aquí.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    // Solo se aplica en :app si existe app/google-services.json (Firebase opcional).
    alias(libs.plugins.google.services) apply false
}
