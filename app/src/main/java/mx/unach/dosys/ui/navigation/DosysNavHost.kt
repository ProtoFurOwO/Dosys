package mx.unach.dosys.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import mx.unach.dosys.core.di.ServiceLocator
import mx.unach.dosys.data.repository.DeviceResult
import mx.unach.dosys.ui.appointments.AppointmentRequestScreen
import mx.unach.dosys.ui.appointments.AppointmentsScreen
import mx.unach.dosys.ui.checkin.CheckInScreen
import mx.unach.dosys.ui.documents.DocumentDetailScreen
import mx.unach.dosys.ui.documents.DocumentsScreen
import mx.unach.dosys.ui.home.HomeScreen
import mx.unach.dosys.ui.login.LoginScreen
import mx.unach.dosys.ui.prescriptions.PrescriptionsScreen
import mx.unach.dosys.ui.record.RecordScreen
import mx.unach.dosys.ui.security.SecurityScreen
import mx.unach.dosys.ui.studies.StudiesScreen
import mx.unach.dosys.ui.transfer.TransferApprovalScreen

/**
 * Grafo de navegación de la app.
 * Al iniciar sesión se limpia el backstack para que "atrás" no regrese al login.
 *
 * Además, con la app en primer plano se sondea cada 5 s si este teléfono tiene
 * una solicitud de transferencia pendiente (cubre FCM retrasado o sin Firebase).
 */
@Composable
fun DosysNavHost(openTransferApproval: Boolean = false) {
    val navController = rememberNavController()
    val lifecycleOwner = LocalLifecycleOwner.current

    LaunchedEffect(openTransferApproval) {
        if (openTransferApproval) {
            navController.navigate(Routes.TRANSFER_APPROVAL) { launchSingleTop = true }
        }
    }

    LaunchedEffect(lifecycleOwner, navController) {
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (isActive) {
                val route = navController.currentDestination?.route
                val hasSession = ServiceLocator.sessionManager.currentToken() != null
                if (hasSession && route != Routes.TRANSFER_APPROVAL) {
                    when (val pending = ServiceLocator.deviceRepository.pendingTransfer()) {
                        is DeviceResult.Success -> {
                            if (pending.value != null) {
                                navController.navigate(Routes.TRANSFER_APPROVAL) {
                                    launchSingleTop = true
                                }
                            }
                        }
                        is DeviceResult.Error -> Unit
                    }
                }
                delay(5_000)
            }
        }
    }

    NavHost(navController = navController, startDestination = Routes.LOGIN) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoggedIn = {
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.LOGIN_TRANSFERRED) {
            LoginScreen(
                notice = "Tu sesión se transfirió al nuevo dispositivo. Este teléfono ya no tiene acceso.",
                onLoggedIn = {
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.LOGIN_TRANSFERRED) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.TRANSFER_APPROVAL) {
            TransferApprovalScreen(
                onBack = { navController.popBackStack() },
                onSessionTransferred = {
                    navController.navigate(Routes.LOGIN_TRANSFERRED) {
                        popUpTo(0) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.HOME) {
            HomeScreen(
                onLogout = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onOpenRecord = { navController.navigate(Routes.RECORD) },
                onOpenStudies = { navController.navigate(Routes.STUDIES) },
                onOpenPrescriptions = { navController.navigate(Routes.PRESCRIPTIONS) },
                onOpenAppointments = { navController.navigate(Routes.APPOINTMENTS) },
                onOpenCheckIn = { navController.navigate(Routes.CHECKIN) },
                onOpenSecurity = { navController.navigate(Routes.SECURITY) },
                onOpenDocuments = { navController.navigate(Routes.DOCUMENTS) },
            )
        }
        composable(Routes.RECORD) {
            RecordScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.STUDIES) {
            StudiesScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.PRESCRIPTIONS) {
            PrescriptionsScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.APPOINTMENTS) {
            AppointmentsScreen(
                onBack = { navController.popBackStack() },
                onRequestAppointment = { navController.navigate(Routes.APPOINTMENT_REQUEST) },
                onOpenCheckIn = { navController.navigate(Routes.CHECKIN) },
            )
        }
        composable(Routes.APPOINTMENT_REQUEST) {
            AppointmentRequestScreen(
                onBack = { navController.popBackStack() },
                onDone = { navController.popBackStack() },
            )
        }
        composable(Routes.CHECKIN) {
            CheckInScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.SECURITY) {
            SecurityScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.DOCUMENTS) {
            DocumentsScreen(
                onBack = { navController.popBackStack() },
                onOpenDocument = { id -> navController.navigate(Routes.document(id)) },
            )
        }
        composable(
            route = Routes.DOCUMENT_DETAIL,
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            DocumentDetailScreen(
                documentId = entry.arguments?.getInt("id") ?: 0,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
