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

// Menús emergentes (engranaje de cuenta y «Más» de Usuarios): se cierran al
// hacer clic fuera o con Escape. Solo hay uno abierto a la vez.
const popovers = document.querySelectorAll("details[data-gear], details[data-more]");
if (popovers.length) {
  document.addEventListener("click", (event) => {
    popovers.forEach((item) => {
      if (item.open && !item.contains(event.target)) item.open = false;
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    popovers.forEach((item) => {
      if (item.open) {
        item.open = false;
        item.querySelector("summary").focus();
      }
    });
  });
}

// Llenado rápido para demostraciones: botón o Alt+Shift+D.
// Solo existe en el formulario de nueva consulta; no envía nada.
const demoConsultationForm = document.querySelector("form[data-demo-consultation]");
if (demoConsultationForm) {
  const demoStatus = demoConsultationForm.querySelector("[data-demo-status]");
  const setIfEmpty = (selector, value) => {
    const field = demoConsultationForm.querySelector(selector);
    if (field && !field.value.trim()) field.value = value;
  };
  const showDemoStatus = (text) => {
    if (!demoStatus) return;
    demoStatus.textContent = text;
    window.setTimeout(() => {
      if (demoStatus.textContent === text) demoStatus.textContent = "";
    }, 2500);
  };
  const fillDemoConsultation = () => {
    setIfEmpty("#reason", "Dolor de cabeza intenso desde hace 3 días");
    setIfEmpty("#diagnosis", "Cefalea tensional. Sin datos de alarma.");
    setIfEmpty("#notes", "Hidratación, descanso y control en 7 días.");
    setIfEmpty("#blood_pressure", "120/80");
    setIfEmpty("#heart_rate", "72");
    setIfEmpty("#respiratory_rate", "16");
    setIfEmpty("#temperature_c", "36.5");
    setIfEmpty("#oxygen_saturation", "98");
    setIfEmpty("#weight_kg", "70");
    setIfEmpty("#height_cm", "170");
    setIfEmpty("#physical_exam", "Paciente consciente, orientado, cardiopulmonar sin agregados, abdomen blando y doloroso a la palpación superficial.");
    document.getElementById("weight_kg")?.dispatchEvent(new Event("input", { bubbles: true }));
    document.getElementById("height_cm")?.dispatchEvent(new Event("input", { bubbles: true }));

    const recipeToggle = demoConsultationForm.querySelector("[data-toggle-recipe]");
    const recipePanel = demoConsultationForm.querySelector("#recipe-panel");
    if (recipeToggle && recipePanel) {
      if (!recipeToggle.checked) {
        recipeToggle.checked = true;
        recipeToggle.dispatchEvent(new Event("change", { bubbles: true }));
      }
      const row = demoConsultationForm.querySelector("#recipe-rows .recipe-row");
      if (row) {
        const setRow = (name, value) => {
          const input = row.querySelector(`input[name="${name}"]`);
          if (input && !input.value.trim()) input.value = value;
        };
        setRow("medication", "Paracetamol");
        setRow("dose", "500 mg");
        setRow("frequency", "Cada 8 horas");
        setRow("duration", "5 días");
      }
      setIfEmpty("#prescription_notes", "Tomar con alimentos. Regresar si la cefalea aumenta.");
    }

    const firstStudy = demoConsultationForm.querySelector('input[name="study_ids"]');
    if (firstStudy && !firstStudy.checked) firstStudy.checked = true;

    showDemoStatus("Ejemplo cargado");
  };

  demoConsultationForm.querySelectorAll("[data-demo-fill]").forEach((button) => {
    button.addEventListener("click", fillDemoConsultation);
  });
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey || event.code !== "KeyD") return;
    event.preventDefault();
    fillDemoConsultation();
  });
}

// Datos aleatorios para demos de alta de pacientes y personal.
const demoRandomForm = document.querySelector("form[data-demo-patient], form[data-demo-user]");
if (demoRandomForm) {
  const isPatientForm = demoRandomForm.hasAttribute("data-demo-patient");
  const randomStatus = demoRandomForm.querySelector("[data-demo-status]");
  const namesBySex = {
    H: ["José", "Luis", "Carlos", "Miguel", "Jorge", "Ricardo", "Fernando", "Alejandro", "Daniel", "Raúl"],
    M: ["María", "Ana", "Laura", "Sofía", "Gabriela", "Fernanda", "Valeria", "Daniela", "Paola", "Andrea"],
  };
  const surnames = ["López", "Hernández", "García", "Martínez", "Pérez", "Gómez", "Sánchez", "Ramírez", "Torres", "Flores"];
  const states = ["CS", "DF", "MC", "NL", "JC", "QR", "PL", "VZ", "YU", "ZC"];
  const randomInt = (max) => {
    if (window.crypto && window.crypto.getRandomValues) {
      const buffer = new Uint32Array(1);
      window.crypto.getRandomValues(buffer);
      return buffer[0] % max;
    }
    return Math.floor(Math.random() * max);
  };
  const pick = (items) => items[randomInt(items.length)];
  const normalize = (text) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const letters = (text) => normalize(text).toUpperCase().replace(/[^A-Z]/g, "");
  const firstVowel = (text) => letters(text).slice(1).match(/[AEIOU]/)?.[0] || "X";
  const firstConsonant = (text) => letters(text).slice(1).match(/[BCDFGHJKLMNPQRSTVWXYZ]/)?.[0] || "X";
  const slug = (text) => normalize(text).toLowerCase().replace(/[^a-z0-9]/g, "");
  const randomPassword = () => {
    const digits = "23456789";
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz";
    let value = "Dosys";
    for (let i = 0; i < 4; i += 1) value += digits[randomInt(digits.length)];
    for (let i = 0; i < 2; i += 1) value += chars[randomInt(chars.length)];
    return value;
  };
  const randomPerson = () => {
    const sex = randomInt(2) ? "H" : "M";
    const firstName = pick(namesBySex[sex]);
    const firstSurname = pick(surnames);
    const secondSurname = pick(surnames);
    const year = 1955 + randomInt(51);
    const month = 1 + randomInt(12);
    const day = 1 + randomInt(28);
    const date = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const curp = [
      letters(firstSurname)[0] || "X",
      firstVowel(firstSurname),
      letters(secondSurname)[0] || "X",
      letters(firstName)[0] || "X",
      String(year).slice(-2),
      String(month).padStart(2, "0"),
      String(day).padStart(2, "0"),
      sex,
      pick(states),
      firstConsonant(firstSurname),
      firstConsonant(secondSurname),
      firstConsonant(firstName),
      pick("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"),
      String(randomInt(10)),
    ].join("");
    const username = `${slug(firstName)}.${slug(firstSurname)}${10 + randomInt(90)}`.slice(0, 64);
    return {
      fullName: `${firstName} ${firstSurname} ${secondSurname}`,
      curp,
      date,
      username,
      password: randomPassword(),
    };
  };
  const setValue = (selector, value) => {
    const field = demoRandomForm.querySelector(selector);
    if (field) field.value = value;
  };
  const showRandomStatus = (text) => {
    if (!randomStatus) return;
    randomStatus.textContent = text;
    window.setTimeout(() => {
      if (randomStatus.textContent === text) randomStatus.textContent = "";
    }, 2500);
  };
  const fillRandom = () => {
    const person = randomPerson();
    setValue("#full_name", person.fullName);
    setValue("#username", person.username);
    setValue("#password", person.password);
    setValue("#password_confirm", person.password);
    if (isPatientForm) {
      setValue("#curp", person.curp);
      setValue("#birth_date", person.date);
      const blood = demoRandomForm.querySelector("#blood_type");
      if (blood && blood.options.length > 1) {
        const options = Array.from(blood.options).filter((option) => option.value);
        blood.value = pick(options).value;
      }
    } else {
      const role = demoRandomForm.querySelector("#role_code");
      const specialty = demoRandomForm.querySelector("#specialty");
      if (role && role.value === "doctor" && specialty && !specialty.value.trim()) {
        specialty.value = "Medicina General";
      }
    }
    showRandomStatus("Datos aleatorios cargados");
  };
  demoRandomForm.querySelectorAll("[data-demo-random-patient], [data-demo-random-user]").forEach((button) => {
    button.addEventListener("click", fillRandom);
  });
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey || event.code !== "KeyR") return;
    event.preventDefault();
    fillRandom();
  });
}

// Cita rápida: fecha/hora futura y datos base para la demo.
const demoAppointmentForm = document.querySelector("form[data-demo-appointment]");
if (demoAppointmentForm) {
  const appointmentStatus = demoAppointmentForm.querySelector("[data-demo-status]");
  const pad = (value) => String(value).padStart(2, "0");
  const setAppointment = (selector, value, force = false) => {
    const field = demoAppointmentForm.querySelector(selector);
    if (field && (force || !field.value.trim())) field.value = value;
  };
  const showAppointmentStatus = (text) => {
    if (!appointmentStatus) return;
    appointmentStatus.textContent = text;
    window.setTimeout(() => {
      if (appointmentStatus.textContent === text) appointmentStatus.textContent = "";
    }, 2500);
  };
  const fillAppointment = () => {
    const next = new Date(Date.now() + 60 * 60 * 1000);
    next.setSeconds(0, 0);
    next.setMinutes(Math.ceil(next.getMinutes() / 30) * 30);
    setAppointment("#fecha", `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`, true);
    setAppointment("#hora", `${pad(next.getHours())}:${pad(next.getMinutes())}`, true);
    setAppointment("#specialty", "Medicina General");
    setAppointment("#location", "Consultorio 3");
    setAppointment("#notes", "Cita de seguimiento para revisión de resultados.");
    showAppointmentStatus("Cita de ejemplo cargada");
  };
  demoAppointmentForm.querySelectorAll("[data-demo-fill-appointment]").forEach((button) => {
    button.addEventListener("click", fillAppointment);
  });
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey || event.code !== "KeyA") return;
    event.preventDefault();
    fillAppointment();
  });
}

// Laboratorio: llena el resultado del primer pendiente o del formulario enfocado.
const labResultForms = document.querySelectorAll("form.result-form");
if (labResultForms.length) {
  const DEMO_LAB_RESULT = "Hemoglobina 14.2 g/dL; leucocitos 6.8; plaquetas 245 mil. Sin hallazgos agudos.";
  const fillLabResult = (form) => {
    const target = form || document.activeElement?.closest("form.result-form") || labResultForms[0];
    if (!target) return;
    const textarea = target.querySelector('textarea[name="result_text"]');
    if (!textarea) return;
    textarea.value = DEMO_LAB_RESULT;
    const details = target.closest("details.result-details");
    if (details) details.open = true;
    textarea.focus();
  };
  document.querySelectorAll("[data-demo-lab-result]").forEach((button) => {
    button.addEventListener("click", () => fillLabResult(button.closest("form.result-form")));
  });
  document.addEventListener("keydown", (event) => {
    if (!event.altKey || !event.shiftKey || event.code !== "KeyL") return;
    event.preventDefault();
    fillLabResult();
  });
}

// IMC en vivo: peso y talla se capturan en el bloque objetivo del SOAP.
const bmiWeight = document.getElementById("weight_kg");
const bmiHeight = document.getElementById("height_cm");
const bmiOutput = document.getElementById("bmi-output");
if (bmiWeight && bmiHeight && bmiOutput) {
  const updateBmi = () => {
    const weight = Number.parseFloat(bmiWeight.value);
    const height = Number.parseFloat(bmiHeight.value);
    if (!Number.isFinite(weight) || !Number.isFinite(height) || weight <= 0 || height <= 0) {
      bmiOutput.textContent = "—";
      return;
    }
    const bmi = weight / ((height / 100) ** 2);
    let label = "Normal";
    if (bmi < 18.5) label = "Bajo peso";
    else if (bmi >= 30) label = "Obesidad";
    else if (bmi >= 25) label = "Sobrepeso";
    bmiOutput.textContent = `${bmi.toFixed(1)} · ${label}`;
  };
  bmiWeight.addEventListener("input", updateBmi);
  bmiHeight.addEventListener("input", updateBmi);
  updateBmi();
}

// Feedback inmediato: evita dobles envíos en formularios clínicos.
document.querySelectorAll("form.form").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button || button.disabled) return;
    button.disabled = true;
    button.textContent = "Guardando…";
  });
});
