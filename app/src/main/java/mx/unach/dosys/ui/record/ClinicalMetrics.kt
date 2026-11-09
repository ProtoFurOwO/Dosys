package mx.unach.dosys.ui.record

import java.util.Locale

enum class BmiCategory(val label: String) {
    UNDERWEIGHT("Bajo peso"),
    NORMAL("Normal"),
    OVERWEIGHT("Sobrepeso"),
    OBESITY("Obesidad"),
}

data class BmiResult(
    val value: Double,
    val category: BmiCategory,
) {
    /** Un decimal con punto, como en el ejemplo clínico (24.3). */
    val formatted: String = String.format(Locale.US, "%.1f", value)
}

/** Cálculos clínicos que no dependen de Android, para poder probarlos. */
object ClinicalMetrics {

    /**
     * IMC = peso / (talla en metros)^2.
     * Devuelve null si falta algún dato o si la talla/peso no son válidos.
     */
    fun bmi(weightKg: Double?, heightCm: Double?): BmiResult? {
        if (weightKg == null || heightCm == null) return null
        if (!weightKg.isFinite() || !heightCm.isFinite()) return null
        if (weightKg <= 0.0 || heightCm <= 0.0) return null

        val heightMeters = heightCm / 100.0
        val value = weightKg / (heightMeters * heightMeters)
        val category = when {
            value < 18.5 -> BmiCategory.UNDERWEIGHT
            value < 25.0 -> BmiCategory.NORMAL
            value < 30.0 -> BmiCategory.OVERWEIGHT
            else -> BmiCategory.OBESITY
        }
        return BmiResult(value = value, category = category)
    }
}
