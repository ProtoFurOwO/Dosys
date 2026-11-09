package mx.unach.dosys.ui.record

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ClinicalMetricsTest {

    @Test
    fun `calcula el IMC del ejemplo clinico`() {
        val result = ClinicalMetrics.bmi(weightKg = 68.5, heightCm = 168.0)

        assertEquals("24.3", result?.formatted)
        assertEquals(BmiCategory.NORMAL, result?.category)
    }

    @Test
    fun `clasifica bajo peso`() {
        val result = ClinicalMetrics.bmi(weightKg = 50.0, heightCm = 170.0)

        assertEquals("17.3", result?.formatted)
        assertEquals(BmiCategory.UNDERWEIGHT, result?.category)
    }

    @Test
    fun `clasifica sobrepeso`() {
        val result = ClinicalMetrics.bmi(weightKg = 80.0, heightCm = 170.0)

        assertEquals("27.7", result?.formatted)
        assertEquals(BmiCategory.OVERWEIGHT, result?.category)
    }

    @Test
    fun `clasifica obesidad`() {
        val result = ClinicalMetrics.bmi(weightKg = 100.0, heightCm = 170.0)

        assertEquals("34.6", result?.formatted)
        assertEquals(BmiCategory.OBESITY, result?.category)
    }

    @Test
    fun `respeta los limites de las categorias`() {
        assertEquals(BmiCategory.NORMAL, ClinicalMetrics.bmi(53.5, 170.0)?.category)
        assertEquals(BmiCategory.OVERWEIGHT, ClinicalMetrics.bmi(72.3, 170.0)?.category)
        assertEquals(BmiCategory.OBESITY, ClinicalMetrics.bmi(86.8, 170.0)?.category)
    }

    @Test
    fun `sin peso o talla no calcula IMC`() {
        assertNull(ClinicalMetrics.bmi(null, 168.0))
        assertNull(ClinicalMetrics.bmi(68.5, null))
        assertNull(ClinicalMetrics.bmi(null, null))
    }

    @Test
    fun `rechaza talla o peso invalidos`() {
        assertNull(ClinicalMetrics.bmi(68.5, 0.0))
        assertNull(ClinicalMetrics.bmi(68.5, -168.0))
        assertNull(ClinicalMetrics.bmi(0.0, 168.0))
        assertNull(ClinicalMetrics.bmi(Double.NaN, 168.0))
        assertNull(ClinicalMetrics.bmi(68.5, Double.POSITIVE_INFINITY))
    }
}
