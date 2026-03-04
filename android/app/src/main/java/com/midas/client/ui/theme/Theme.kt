package com.midas.client.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val MidasPalette = darkColorScheme(
    primary = Color(0xFF63BCFF),
    onPrimary = Color(0xFFEAF6FF),
    primaryContainer = Color(0xFF164B73),
    onPrimaryContainer = Color(0xFFD7ECFF),
    secondary = Color(0xFF71D6C2),
    onSecondary = Color(0xFFE7FFF9),
    secondaryContainer = Color(0xFF0F4E45),
    onSecondaryContainer = Color(0xFFD1F4EC),
    tertiary = Color(0xFFF1C488),
    onTertiary = Color(0xFFFFF7EC),
    background = Color(0xFF0B1526),
    onBackground = Color(0xFFE7F1FF),
    surface = Color(0xFF11233A),
    onSurface = Color(0xFFE7F1FF),
    surfaceVariant = Color(0xFF16304D),
    onSurfaceVariant = Color(0xFFABC4E3),
    outline = Color(0xFF345675),
    error = Color(0xFFFF8A80),
    onError = Color(0xFF2A0001),
)

private val LightColors = lightColorScheme(
    primary = MidasPalette.primary,
    onPrimary = MidasPalette.onPrimary,
    primaryContainer = MidasPalette.primaryContainer,
    onPrimaryContainer = MidasPalette.onPrimaryContainer,
    secondary = MidasPalette.secondary,
    onSecondary = MidasPalette.onSecondary,
    secondaryContainer = MidasPalette.secondaryContainer,
    onSecondaryContainer = MidasPalette.onSecondaryContainer,
    tertiary = MidasPalette.tertiary,
    onTertiary = MidasPalette.onTertiary,
    background = MidasPalette.background,
    onBackground = MidasPalette.onBackground,
    surface = MidasPalette.surface,
    onSurface = MidasPalette.onSurface,
    surfaceVariant = MidasPalette.surfaceVariant,
    onSurfaceVariant = MidasPalette.onSurfaceVariant,
    outline = MidasPalette.outline,
    error = MidasPalette.error,
    onError = MidasPalette.onError,
)

private val DarkColors = MidasPalette

@Composable
fun MidasTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        content = content,
    )
}
