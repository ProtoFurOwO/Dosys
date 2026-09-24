// Único script del portal: botón de impresión de la credencial (sin dependencias).
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-print]");
  if (trigger) {
    window.print();
  }
});
