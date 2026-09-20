package mx.unach.dosys.ui.format

import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private val spanishMexico = Locale("es", "MX")
private val dateFormatter = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy", spanishMexico)
private val dateTimeFormatter = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy · HH:mm 'h'", spanishMexico)

fun formatClinicalDate(value: String?): String = runCatching {
    LocalDate.parse(value).format(dateFormatter)
}.getOrDefault("No registrado")

fun formatClinicalDateTime(value: String): String = runCatching {
    OffsetDateTime.parse(value).format(dateTimeFormatter)
}.getOrElse {
    value
}
