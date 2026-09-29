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
