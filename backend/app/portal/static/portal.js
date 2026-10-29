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

// Agenda: abrir los detalles de la cita desde el botón de cada tarjeta.
const appointmentModal = document.getElementById("modal-detalle");
if (appointmentModal) {
  const cleanValue = (raw) => {
    const text = (raw || "").trim();
    return text.toLowerCase() === "none" ? "" : text;
  };
  const openAppointmentModal = (card) => {
    const value = (name) => cleanValue(card.getAttribute("data-" + name));
    const patientName = value("patient-name");
    const setText = (id, text) => {
      const element = document.getElementById(id);
      if (element) element.textContent = text;
      return element;
    };

    setText("detalle-avatar", patientName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("") || "P");
    setText("detalle-paciente", patientName || "Paciente sin nombre");
    setText("detalle-curp", "CURP: " + (value("patient-curp") || "No registrada"));
    setText("detalle-medico", value("doctor-name") || "Sin médico asignado");
    setText("detalle-especialidad", value("specialty") || "Sin especialidad");
    setText("detalle-horario", value("time") + " h");
    setText("detalle-fecha", value("date"));
    setText("detalle-consultorio", value("room") || "Sin consultorio");
    setText("detalle-checkin-code", value("checkin-code") || "N/A");
    setText("detalle-notas", value("notes") || "Sin notas adicionales registradas.");

    const badge = setText("detalle-status-badge", value("status-label"));
    if (badge) badge.className = "modern-status-pill status-pill-" + value("status");

    const checkedIn = value("checked-in");
    const arrival = setText("detalle-llegada-aviso", checkedIn ? "Llegó " + checkedIn : "Pendiente de escaneo QR");
    if (arrival) {
      arrival.style.color = checkedIn ? "#047857" : "var(--ink-muted)";
      arrival.style.fontWeight = checkedIn ? "600" : "normal";
    }

    const qrLink = document.getElementById("btn-ver-qr");
    if (qrLink) qrLink.href = "/portal/citas/" + value("apt-id");
    const patientLink = document.getElementById("btn-ver-expediente");
    if (patientLink) patientLink.href = "/portal/pacientes/" + value("patient-id");

    const changeForm = document.getElementById("form-cambiar-estado");
    if (changeForm) {
      changeForm.action = "/portal/agenda/citas/" + value("apt-id") + "/estado";
      const stateSelect = document.getElementById("cambio-estado");
      if (stateSelect) stateSelect.value = value("status");
      const roomSelect = document.getElementById("cambio-consultorio");
      if (roomSelect && value("room")) roomSelect.value = value("room");
    }

    appointmentModal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  const closeAppointmentModal = () => {
    appointmentModal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  document.querySelectorAll(".card-detail-button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const card = button.closest(".modern-card-item");
      if (card) openAppointmentModal(card);
    });
  });

  // Las tarjetas de la matriz horaria y de la vista semanal también abren el detalle.
  document.querySelectorAll(".grid-apt-card").forEach((card) => {
    const open = (event) => {
      if (event) event.preventDefault();
      openAppointmentModal(card);
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open(event);
      }
    });
  });

  appointmentModal.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", closeAppointmentModal);
  });
  appointmentModal.addEventListener("click", (event) => {
    if (event.target === appointmentModal) closeAppointmentModal();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && appointmentModal.getAttribute("aria-hidden") === "false") {
      closeAppointmentModal();
    }
  });
}

// Agenda: los filtros y el selector de fecha envían el formulario sin depender
// de handlers inline, que el CSP del portal bloquea.
const agendaFilters = document.getElementById("agenda-filters");
if (agendaFilters) {
  agendaFilters.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", () => agendaFilters.submit());
  });
}
const agendaDateForm = document.getElementById("agenda-date-form");
if (agendaDateForm) {
  const agendaDateInput = document.getElementById("agenda-date-input");
  if (agendaDateInput) {
    agendaDateInput.addEventListener("change", () => agendaDateForm.submit());
  }
}

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
