package mx.unach.dosys.data.remote

import kotlinx.serialization.json.Json
import mx.unach.dosys.BuildConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Construye el cliente HTTP (Retrofit + OkHttp + kotlinx.serialization)
 * que consume la API del hospital.
 */
object NetworkModule {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    private val logging = HttpLoggingInterceptor().apply {
        // En producción NO se registra nada: los logs podrían exponer datos clínicos.
        level = if (BuildConfig.DEBUG) {
            HttpLoggingInterceptor.Level.BASIC
        } else {
            HttpLoggingInterceptor.Level.NONE
        }
    }

    private val client = OkHttpClient.Builder()
        .addInterceptor(logging)
        // Próximamente: AuthInterceptor que agrega "Authorization: Bearer <token>"
        .build()

    /** Crea una instancia del servicio listo para usarse. */
    fun create(): ApiService = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(ApiService::class.java)
}
