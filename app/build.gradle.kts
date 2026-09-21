plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Permite compilar apuntando a otro backend sin tocar el código:
//   .\gradlew.bat :app:assembleDebug -PapiBaseUrl=https://medicos.stolasimp.dev/api/v1/
val apiBaseUrlOverride: String? = (project.findProperty("apiBaseUrl") as String?)?.takeIf { it.isNotBlank() }

android {
    namespace = "mx.unach.dosys"
    compileSdk = 35

    defaultConfig {
        applicationId = "mx.unach.dosys"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            // 10.0.2.2 = la PC anfitriona vista desde el emulador de Android
            val defaultUrl = "http://10.0.2.2:8000/api/v1/"
            buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrlOverride ?: defaultUrl}\"")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // Backend real del hospital académico (VPS con HTTPS).
            val defaultUrl = "https://medicos.stolasimp.dev/api/v1/"
            buildConfigField("String", "API_BASE_URL", "\"${apiBaseUrlOverride ?: defaultUrl}\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    // Núcleo / ciclo de vida
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    // Jetpack Compose (BOM controla las versiones)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.navigation.compose)

    // Red: Retrofit + kotlinx.serialization + OkHttp
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp.logging)

    // Almacenamiento local de la sesión (token JWT)
    implementation(libs.androidx.datastore.preferences)

    // Generación del código QR del paciente
    implementation(libs.zxing.core)

    // Escaneo de QR con la cámara (módulo del celular)
    implementation(libs.zxing.android.embedded)

    // Huella dactilar / bloqueo del dispositivo para abrir el expediente
    implementation(libs.androidx.biometric)
    implementation(libs.androidx.fragment.ktx)

    // Mapa del hospital (OpenStreetMap, sin API key)
    implementation(libs.osmdroid.android)

    // Pruebas
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
