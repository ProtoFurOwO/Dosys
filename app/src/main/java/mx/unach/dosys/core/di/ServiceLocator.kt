package mx.unach.dosys.core.di

import android.content.Context
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.data.repository.AuthRepository
import mx.unach.dosys.data.repository.FakeAuthRepository

/**
 * Contenedor de dependencias sencillo (service locator).
 * Para el MVP es suficiente; si el proyecto crece se puede migrar a Hilt.
 */
object ServiceLocator {

    lateinit var sessionManager: SessionManager
        private set

    lateinit var authRepository: AuthRepository
        private set

    fun init(context: Context) {
        sessionManager = SessionManager(context.applicationContext)

        // Mientras el backend FastAPI no esté desplegado se usa la versión simulada.
        // Para conectar la API real, cambiar por:
        //   RemoteAuthRepository(NetworkModule.create(), sessionManager)
        authRepository = FakeAuthRepository(sessionManager)
    }
}
