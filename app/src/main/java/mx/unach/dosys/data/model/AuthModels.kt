package mx.unach.dosys.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Credenciales que la app envía al endpoint /auth/login. */
@Serializable
data class LoginRequest(
    @SerialName("username") val username: String,
    @SerialName("password") val password: String,
)

/** Respuesta del backend con los tokens JWT. */
@Serializable
data class LoginResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String? = null,
    @SerialName("token_type") val tokenType: String = "bearer",
)

/** Datos básicos del paciente autenticado (solo lectura). */
@Serializable
data class PatientProfile(
    val id: Int,
    @SerialName("full_name") val fullName: String,
    val curp: String? = null,
    @SerialName("blood_type") val bloodType: String? = null,
)
