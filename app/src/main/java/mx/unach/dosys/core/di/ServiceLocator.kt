package mx.unach.dosys.core.di

import android.content.Context
import mx.unach.dosys.core.auth.SessionManager
import mx.unach.dosys.core.device.DeviceIdentity
import mx.unach.dosys.data.repository.AuthRepository
import mx.unach.dosys.data.repository.DeviceRepository
import mx.unach.dosys.data.repository.PatientRepository
import mx.unach.dosys.data.repository.RemoteAuthRepository
import mx.unach.dosys.data.repository.RemoteDeviceRepository
import mx.unach.dosys.data.repository.RemotePatientRepository
import mx.unach.dosys.data.repository.RemoteSecurityRepository
import mx.unach.dosys.data.repository.SecurityRepository
import mx.unach.dosys.data.remote.NetworkModule
import mx.unach.dosys.data.remote.TokenRefresher

/**
 * Contenedor de dependencias sencillo (service locator).
 * Para el MVP es suficiente; si el proyecto crece se puede migrar a Hilt.
 */
object ServiceLocator {

    lateinit var sessionManager: SessionManager
        private set

    lateinit var authRepository: AuthRepository
        private set

    lateinit var patientRepository: PatientRepository
        private set

    lateinit var securityRepository: SecurityRepository
        private set

    lateinit var deviceIdentity: DeviceIdentity
        private set

    lateinit var deviceRepository: DeviceRepository
        private set

    fun init(context: Context) {
        val application = context.applicationContext
        sessionManager = SessionManager(application)
        deviceIdentity = DeviceIdentity(application)
        val api = NetworkModule.create()
        val refresher = TokenRefresher(api, sessionManager)
        authRepository = RemoteAuthRepository(api, sessionManager, deviceIdentity)
        patientRepository = RemotePatientRepository(api, sessionManager, refresher)
        securityRepository = RemoteSecurityRepository(api, sessionManager, refresher)
        deviceRepository = RemoteDeviceRepository(api, sessionManager, refresher, deviceIdentity)
    }
}
