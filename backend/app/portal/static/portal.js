// Único script del portal: impresión de credenciales y copiado del secreto 2FA.
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-print]");
  if (trigger) {
    window.print();
    return;
  }

  const copy = event.target.closest("[data-copy]");
  if (copy) {
    const value = copy.getAttribute("data-copy") || "";
    const done = () => {
      const original = copy.textContent;
      copy.textContent = "Copiado";
      window.setTimeout(() => {
        copy.textContent = original;
      }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(done).catch(() => {});
    } else {
      const field = document.createElement("textarea");
      field.value = value;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      try {
        document.execCommand("copy");
        done();
      } finally {
        document.body.removeChild(field);
      }
    }
  }
});

// Check-in en vivo: la pantalla del QR se actualiza sola cuando el paciente
// confirma su llegada desde la app. Deja de consultar al recibir la respuesta.
const watch = document.querySelector("[data-checkin-watch]");
if (watch) {
  const endpoint = watch.getAttribute("data-checkin-watch");
  const chip = document.getElementById("cita-chip");
  const estado = document.getElementById("checkin-estado");
  const aviso = document.getElementById("checkin-aviso");

  const timer = window.setInterval(async () => {
    try {
      const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      if (data.checked_in) {
        window.clearInterval(timer);
        if (chip) {
          chip.textContent = "Llegó";
        }
        if (estado && data.checked_in_label) {
          estado.textContent = "Llegada confirmada a las " + data.checked_in_label + ".";
        }
        if (aviso && data.checked_in_label) {
          aviso.innerHTML =
            '<div class="note note-ok" role="status"><p>Este paciente ya confirmó su llegada a las ' +
            data.checked_in_label +
            ".</p></div>";
        }
      }
    } catch (error) {
      // Sin conexión momentánea: se reintenta en el siguiente ciclo.
    }
  }, 4000);
}
