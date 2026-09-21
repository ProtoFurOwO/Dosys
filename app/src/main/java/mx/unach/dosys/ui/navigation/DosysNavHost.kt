package mx.unach.dosys.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import mx.unach.dosys.ui.appointments.AppointmentsScreen
import mx.unach.dosys.ui.checkin.CheckInScreen
import mx.unach.dosys.ui.home.HomeScreen
import mx.unach.dosys.ui.login.LoginScreen
import mx.unach.dosys.ui.prescriptions.PrescriptionsScreen
import mx.unach.dosys.ui.qr.QrScreen
import mx.unach.dosys.ui.record.RecordScreen
import mx.unach.dosys.ui.studies.StudiesScreen
import mx.unach.dosys.ui.studies.StudyDetailScreen

/**
 * Grafo de navegación de la app.
 * Al iniciar sesión se limpia el backstack para que "atrás" no regrese al login.
 */
@Composable
fun DosysNavHost() {
    val navController = rememberNavController()

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
                onOpenQr = { navController.navigate(Routes.QR) },
                onOpenAppointments = { navController.navigate(Routes.APPOINTMENTS) },
                onOpenCheckIn = { navController.navigate(Routes.CHECKIN) },
            )
        }
        composable(Routes.RECORD) {
            RecordScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.STUDIES) {
            StudiesScreen(
                onBack = { navController.popBackStack() },
                onOpenStudy = { id -> navController.navigate(Routes.studyDetail(id)) },
            )
        }
        composable(
            route = Routes.STUDY_DETAIL,
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            val id = entry.arguments?.getInt("id") ?: return@composable
            StudyDetailScreen(studyId = id, onBack = { navController.popBackStack() })
        }
        composable(Routes.PRESCRIPTIONS) {
            PrescriptionsScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.QR) {
            QrScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.APPOINTMENTS) {
            AppointmentsScreen(
                onBack = { navController.popBackStack() },
                onOpenCheckIn = { navController.navigate(Routes.CHECKIN) },
            )
        }
        composable(Routes.CHECKIN) {
            CheckInScreen(onBack = { navController.popBackStack() })
        }
    }
}
