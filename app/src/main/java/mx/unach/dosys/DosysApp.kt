package mx.unach.dosys

import android.app.Application
import mx.unach.dosys.core.di.ServiceLocator

/**
 * Punto de entrada de la aplicación.
 * Aquí se inicializa el contenedor de dependencias (ServiceLocator).
 */
class DosysApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ServiceLocator.init(this)
    }
}
