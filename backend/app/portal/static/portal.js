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

// Receta: mostrar el panel y agregar o quitar medicamentos.
const recipeToggle = document.querySelector("[data-toggle-recipe]");
const recipePanel = document.getElementById("recipe-panel");
if (recipeToggle && recipePanel) {
  recipeToggle.addEventListener("change", () => {
    recipePanel.hidden = !recipeToggle.checked;
  });
}

document.addEventListener("click", (event) => {
  const recipeRows = document.getElementById("recipe-rows");
  if (!recipeRows) {
    return;
  }
  const addButton = event.target.closest("[data-add-row]");
  if (addButton) {
    const rows = recipeRows.querySelectorAll(".recipe-row");
    if (rows.length >= 8) {
      return;
    }
    const clone = rows[rows.length - 1].cloneNode(true);
    clone.querySelectorAll("input").forEach((input) => {
      input.value = "";
    });
    recipeRows.appendChild(clone);
    return;
  }
  const removeButton = event.target.closest("[data-remove-row]");
  if (removeButton) {
    const row = removeButton.closest(".recipe-row");
    const rows = recipeRows.querySelectorAll(".recipe-row");
    if (row && rows.length > 1) {
      row.remove();
    } else if (row) {
      row.querySelectorAll("input").forEach((input) => {
        input.value = "";
      });
    }
  }
});

// Próxima cita: mostrar u ocultar el panel.
const nextToggle = document.querySelector("[data-toggle-next]");
const nextPanel = document.getElementById("next-panel");
if (nextToggle && nextPanel) {
  nextToggle.addEventListener("change", () => {
    nextPanel.hidden = !nextToggle.checked;
  });
}

// Sala de espera: si cambia la lista (llegadas o consultorios), la página se recarga.
const waitingWatch = document.querySelector("[data-waiting-watch]");
if (waitingWatch) {
  const endpoint = waitingWatch.getAttribute("data-waiting-watch");
  window.setInterval(async () => {
    try {
      const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      const list = data.waiting || [];
      const fresh = list.map((item) => item.appointment_id + ":" + item.room).join(";") + (list.length ? ";" : "");
      const current = waitingWatch.getAttribute("data-waiting-signature") || "";
      if (fresh !== current) {
        window.location.reload();
      }
    } catch (error) {
      // Sin conexión momentánea: se reintenta en el siguiente ciclo.
    }
  }, 5000);
}
