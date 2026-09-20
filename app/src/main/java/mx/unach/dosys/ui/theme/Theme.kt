package mx.unach.dosys.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = GreenDeep,
    onPrimary = Color.White,
    primaryContainer = GreenLight,
    onPrimaryContainer = GreenDeep,
    secondary = GreenMid,
    onSecondary = Color.White,
    background = SurfaceLight,
    onBackground = TextDark,
    surface = Color.White,
    onSurface = TextDark,
    surfaceVariant = GreenLight,
    onSurfaceVariant = GrayText,
    error = ErrorRed,
)

private val DarkColors = darkColorScheme(
    primary = GreenMid,
    onPrimary = Color(0xFF06231A),
    primaryContainer = GreenDeep,
    onPrimaryContainer = GreenLight,
    background = SurfaceDark,
    onBackground = TextLight,
    surface = CardDark,
    onSurface = TextLight,
    error = ErrorRed,
)

/** Tema único de la aplicación (claro/oscuro según el sistema). */
@Composable
fun DosysTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = DosysTypography,
        content = content,
    )
}
