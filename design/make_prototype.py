"""Genera el prototipo navegable autocontenido (HTML + imágenes en base64)."""

from __future__ import annotations

import base64
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "assets", "app")
OUT = os.path.join(ROOT, "prototipo")
os.makedirs(OUT, exist_ok=True)


def b64(name: str) -> str:
    with open(os.path.join(APP, name), "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")


SCREENS = {
    "login": {
        "img": "login.png",
        "title": "Inicio de sesión",
        "hint": "Escribe tus credenciales o toca “¿Olvidaste tu contraseña?”.",
        "hotspots": [
            {"x": 6, "y": 59.5, "w": 88, "h": 6.2, "to": "home", "label": "Iniciar sesión"},
            {"x": 22, "y": 69.0, "w": 56, "h": 3.4, "to": "recovery", "label": "Recuperar contraseña"},
        ],
    },
    "recovery": {
        "img": "recovery.png",
        "title": "Recuperar contraseña",
        "hint": "Diálogo modal: si la cuenta existe, se envía un enlace de un solo uso.",
        "hotspots": [
            {"x": 28, "y": 65.0, "w": 20, "h": 4.0, "to": "login", "label": "Cancelar"},
            {"x": 52, "y": 65.0, "w": 24, "h": 4.0, "to": "login", "label": "Enviar enlace"},
        ],
    },
    "home": {
        "img": "home.png",
        "title": "Inicio",
        "hint": "Resumen de la próxima cita, tratamiento activo y accesos rápidos.",
        "hotspots": [
            {"x": 4, "y": 12.6, "w": 92, "h": 15.2, "to": "checkin", "label": "Próxima cita → Citas / Check-in"},
            {"x": 4, "y": 30.5, "w": 92, "h": 17.5, "toast": "La pantalla de Recetas se documenta en el mapa de navegación y los wireframes.", "label": "Tratamiento activo"},
            {"x": 4, "y": 55.2, "w": 42, "h": 8.8, "to": "record", "label": "Expediente"},
            {"x": 52, "y": 55.2, "w": 44, "h": 8.8, "toast": "La pantalla de Estudios se documenta en el mapa de navegación y los wireframes.", "label": "Estudios"},
            {"x": 4, "y": 65.2, "w": 42, "h": 8.8, "toast": "La pantalla de Recetas se documenta en el mapa de navegación y los wireframes.", "label": "Recetas"},
            {"x": 52, "y": 65.2, "w": 44, "h": 8.8, "toast": "La pantalla Mi QR se documenta en el mapa de navegación y los wireframes.", "label": "Mi QR"},
            {"x": 4, "y": 75.2, "w": 42, "h": 8.8, "to": "checkin", "label": "Check-in con QR"},
            {"x": 52, "y": 75.2, "w": 44, "h": 8.8, "to": "security", "label": "Mi seguridad"},
            {"x": 4, "y": 85.2, "w": 92, "h": 8.4, "toast": "La pantalla de Documentos se documenta en el mapa de navegación y los wireframes.", "label": "Mis documentos"},
            {"x": 88, "y": 7.0, "w": 8, "h": 4.5, "to": "login", "label": "Cerrar sesión"},
        ],
    },
    "record": {
        "img": "record.png",
        "title": "Mi expediente",
        "hint": "Datos del paciente e historial de consultas; se abre después de validar la huella.",
        "hotspots": [
            {"x": 4, "y": 6.5, "w": 10, "h": 4.5, "to": "home", "label": "Regresar"},
        ],
    },
    "biometric": {
        "img": "biometric.png",
        "title": "Bloqueo por huella",
        "hint": "BiometricPrompt protege el expediente antes de mostrar datos clínicos.",
        "hotspots": [
            {"x": 6, "y": 61.5, "w": 88, "h": 5.5, "to": "record", "label": "Continuar"},
        ],
    },
    "checkin": {
        "img": "checkin.png",
        "title": "Check-in con QR",
        "hint": "La cámara lee el QR de la cita; si falla, existe un código de respaldo. El mapa usa GPS y OpenStreetMap.",
        "hotspots": [
            {"x": 4, "y": 6.5, "w": 10, "h": 4.5, "to": "home", "label": "Regresar"},
            {"x": 7, "y": 25.0, "w": 86, "h": 5.0, "toast": "Demo: se abriría la cámara y el escáner ZXing.", "label": "Abrir cámara"},
            {"x": 7, "y": 34.5, "w": 86, "h": 4.5, "toast": "Demo: valida el código de respaldo contra la API.", "label": "Confirmar con el código"},
            {"x": 7, "y": 48.0, "w": 45, "h": 5.0, "to": "map", "label": "Ver mapa GPS"},
        ],
    },
    "map": {
        "img": "map.png",
        "title": "Mapa y GPS",
        "hint": "OpenStreetMap muestra el hospital, la ubicación del paciente y la distancia en metros.",
        "hotspots": [
            {"x": 4, "y": 6.5, "w": 10, "h": 4.5, "to": "checkin", "label": "Regresar"},
        ],
    },
    "security": {
        "img": "security.png",
        "title": "Mi seguridad",
        "hint": "Activa el segundo factor, cambia la contraseña y consulta los códigos de recuperación.",
        "hotspots": [
            {"x": 4, "y": 6.5, "w": 10, "h": 4.5, "to": "home", "label": "Regresar"},
            {"x": 4, "y": 17.0, "w": 92, "h": 5.5, "to": "twofactor", "label": "Activar segundo factor"},
        ],
    },
    "twofactor": {
        "img": "twofactor.png",
        "title": "Verificación 2FA",
        "hint": "Al iniciar sesión, la app pide el código TOTP de Google/Microsoft Authenticator.",
        "hotspots": [
            {"x": 6, "y": 63.0, "w": 88, "h": 5.0, "toast": "Demo: el código se valida contra la API (TOTP).", "label": "Verificar"},
            {"x": 25, "y": 76.5, "w": 50, "h": 3.6, "to": "login", "label": "Volver al login"},
        ],
    },
}


def build():
    data = {key: {**value, "img": b64(value["img"])} for key, value in SCREENS.items()}
    screens_json = json.dumps(data, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>D.O.S.Y.S · Prototipo navegable</title>
<style>
  :root {{
    --ink: #14201A;
    --muted: #64746B;
    --green: #13653F;
    --green-2: #1E7A4E;
    --cream: #F7F4EC;
    --line: rgba(19,101,63,.18);
    --card: rgba(255,255,255,.88);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin:0; padding:0; min-height:100%; }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1200px 700px at 15% 0%, #1d6a47 0%, transparent 55%),
      radial-gradient(900px 600px at 100% 100%, #0d2c20 0%, transparent 60%),
      #0b1f16;
    min-height: 100vh;
  }}
  .app {{
    max-width: 1380px; margin: 0 auto; padding: 28px 26px 40px;
    display: grid; grid-template-columns: 320px 1fr; gap: 28px;
  }}
  header.top {{
    grid-column: 1 / -1; display:flex; align-items:center; justify-content:space-between;
    gap: 20px; padding: 4px 2px 6px;
  }}
  .brand {{ display:flex; align-items:center; gap:14px; }}
  .mark {{
    width: 46px; height: 46px; border-radius: 13px; background: #fff; color: var(--green);
    display:flex; align-items:center; justify-content:center; font-weight: 900; font-size: 27px;
    box-shadow: 0 8px 22px rgba(0,0,0,.25);
  }}
  .brand h1 {{ margin:0; color:#fff; font-size: 22px; letter-spacing:.2px; }}
  .brand p {{ margin:3px 0 0; color:rgba(255,255,255,.72); font-size: 12.5px; }}
  .top-actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
  .ghost {{
    appearance:none; border:1px solid rgba(255,255,255,.22); background:rgba(255,255,255,.06);
    color:#fff; border-radius: 999px; padding: 10px 15px; font-size: 12.5px; cursor:pointer;
    transition:.18s ease;
  }}
  .ghost:hover {{ background:rgba(255,255,255,.14); }}
  .ghost.primary {{ background:#fff; color:var(--green); border-color:#fff; font-weight:700; }}

  aside.panel {{
    background: var(--card); border:1px solid rgba(255,255,255,.5); border-radius: 22px;
    padding: 20px 18px; align-self:start; backdrop-filter: blur(10px);
    box-shadow: 0 20px 60px rgba(0,0,0,.18);
  }}
  .panel h2 {{ margin:0 0 4px; font-size: 13px; letter-spacing:.14em; text-transform:uppercase; color:var(--green); }}
  .panel .sub {{ margin:0 0 14px; color:var(--muted); font-size:12.5px; line-height:1.45; }}
  .screen-list {{ display:flex; flex-direction:column; gap:6px; margin: 10px 0 18px; }}
  .screen-btn {{
    display:flex; align-items:center; gap:10px; width:100%; text-align:left;
    border:1px solid transparent; background:transparent; border-radius: 12px;
    padding: 8px 10px; font-size: 13.5px; color:#23372C; cursor:pointer;
  }}
  .screen-btn:hover {{ background:#EAF4EF; }}
  .screen-btn.active {{ background: var(--green); color:#fff; }}
  .screen-btn .num {{
    width: 24px; height: 24px; border-radius: 8px; background:#EAF4EF; color:var(--green);
    display:flex; align-items:center; justify-content:center; font-size: 11px; font-weight:800; flex:0 0 auto;
  }}
  .screen-btn.active .num {{ background:rgba(255,255,255,.2); color:#fff; }}
  .divider {{ height:1px; background:var(--line); margin: 14px 0; }}
  .panel .label {{ font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin: 0 0 8px; }}
  .state-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
  .state-btn {{
    border:1px solid var(--line); background:#fff; border-radius: 10px; padding: 8px 9px;
    font-size: 12px; color:#23372C; cursor:pointer; text-align:left;
  }}
  .state-btn:hover {{ border-color:var(--green); }}
  .tip {{
    margin-top: 16px; background:#F1F7F3; border-left: 3px solid var(--green);
    padding: 10px 12px; border-radius: 0 10px 10px 0; color:#335243; font-size:12px; line-height:1.45;
  }}

  main.stage {{
    display:flex; flex-direction:column; align-items:center; justify-content:flex-start;
    gap: 14px; padding-top: 4px;
  }}
  .crumbs {{ display:flex; align-items:center; gap:8px; color:rgba(255,255,255,.78); font-size:12.5px; }}
  .crumbs b {{ color:#fff; }}
  .phone-wrap {{ position:relative; filter: drop-shadow(0 40px 70px rgba(0,0,0,.4)); }}
  .phone {{
    position:relative; width: 360px; height: 800px; background:#0b0f0d; border-radius: 46px;
    padding: 11px; box-shadow: inset 0 0 0 2px rgba(255,255,255,.08), inset 0 0 0 7px #050706;
  }}
  .phone:before {{
    content:""; position:absolute; left:-3px; top:150px; width:3px; height:64px; border-radius:3px;
    background:#1b211d;
  }}
  .phone:after {{
    content:""; position:absolute; right:-3px; top:180px; width:3px; height:92px; border-radius:3px;
    background:#1b211d;
  }}
  .screen {{
    position:relative; width:100%; height:100%; border-radius: 36px; overflow:hidden; background:#fff;
  }}
  .screen img {{ width:100%; height:100%; object-fit:cover; display:block; }}
  .island {{
    position:absolute; top:10px; left:50%; transform:translateX(-50%); width: 104px; height: 26px;
    background:#050706; border-radius: 18px; z-index:5;
  }}
  .hotspot {{
    position:absolute; border: 0; background: transparent; cursor:pointer; border-radius: 12px;
    z-index:4; transition: background .15s ease, box-shadow .15s ease;
  }}
  .hotspot:before {{
    content:""; position:absolute; inset:0; border:2px dashed rgba(19,101,63,.95);
    border-radius:12px; opacity:0; transition:.15s ease;
    box-shadow: 0 0 0 3px rgba(19,101,63,.12);
  }}
  .hotspot:after {{
    content:attr(data-label); position:absolute; left:50%; top:-34px; transform:translateX(-50%);
    background:#0e2b1f; color:#fff; font-size:10.5px; line-height:1.2; padding:5px 8px;
    border-radius:7px; white-space:nowrap; opacity:0; pointer-events:none; transition:.15s ease;
    max-width: 260px; overflow:hidden; text-overflow:ellipsis;
  }}
  .show-hotspots .hotspot:before {{ opacity:1; }}
  .hotspot:hover {{ background: rgba(19,101,63,.12); }}
  .hotspot:hover:before {{ background:rgba(19,101,63,.10); border-style:solid; }}
  .hotspot:hover:after {{ opacity:1; }}
  .phone-foot {{
    margin-top: 2px; display:flex; align-items:center; justify-content:space-between;
    width: 360px; color:rgba(255,255,255,.62); font-size:11.5px;
  }}
  .hint {{ color:rgba(255,255,255,.78); font-size:13px; text-align:center; max-width: 520px; line-height:1.5; }}
  .toast {{
    position:absolute; left:50%; bottom:26px; transform:translateX(-50%) translateY(20px);
    background:#0e2b1f; color:#fff; font-size:12px; line-height:1.4; padding:10px 14px;
    border-radius:12px; max-width: 300px; text-align:center; opacity:0; pointer-events:none;
    transition:.22s ease; z-index:9; box-shadow:0 12px 30px rgba(0,0,0,.3);
  }}
  .toast.show {{ opacity:1; transform:translateX(-50%) translateY(0); }}
  .controls {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:center; }}
  .controls button {{
    border:1px solid rgba(255,255,255,.22); background:rgba(255,255,255,.08); color:#fff;
    border-radius:999px; padding:9px 14px; font-size:12.5px; cursor:pointer;
  }}
  .controls button:hover {{ background:rgba(255,255,255,.16); }}
  .footer-note {{ color:rgba(255,255,255,.45); font-size:11.5px; text-align:center; margin-top: 8px; }}
  @media (max-width: 980px) {{
    .app {{ grid-template-columns:1fr; }}
    aside.panel {{ order:2; }}
    main.stage {{ order:1; }}
    .phone {{ width: 320px; height: 711px; }}
    .phone-foot {{ width:320px; }}
  }}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <div class="mark">+</div>
      <div>
        <h1>D.O.S.Y.S · Prototipo navegable</h1>
        <p>5 pantallas + estados · Material 3 · datos de demostración</p>
      </div>
    </div>
    <div class="top-actions">
      <button class="ghost" onclick="toggleHotspots()">Mostrar / ocultar zonas</button>
      <button class="ghost" onclick="reset()">Reiniciar</button>
      <button class="ghost primary" onclick="fullscreen()">Pantalla completa</button>
    </div>
  </header>

  <aside class="panel">
    <h2>Recorrido</h2>
    <p class="sub">Haz clic en los elementos resaltados del teléfono o salta a una pantalla desde aquí.</p>
    <div class="screen-list" id="screenList"></div>
    <div class="divider"></div>
    <p class="label">Estados y módulos</p>
    <div class="state-grid">
      <button class="state-btn" onclick="go('recovery')">Recuperar contraseña</button>
      <button class="state-btn" onclick="go('biometric')">Bloqueo por huella</button>
      <button class="state-btn" onclick="go('map')">Mapa GPS</button>
      <button class="state-btn" onclick="go('twofactor')">Verificación 2FA</button>
    </div>
    <div class="tip">
      <b>Para el profe:</b> este prototipo usa las capturas reales de la app. Los botones
      resaltados reproducen el flujo real: login → inicio → expediente / check-in / seguridad.
    </div>
  </aside>

  <main class="stage">
    <div class="crumbs"><span>Prototipo</span><span>›</span><b id="crumb">Inicio de sesión</b></div>
    <div class="phone-wrap">
      <div class="phone">
        <div class="island"></div>
        <div class="screen" id="screen">
          <img id="shot" alt="Pantalla del prototipo">
          <div id="hotspots"></div>
          <div class="toast" id="toast"></div>
        </div>
      </div>
    </div>
    <div class="phone-foot"><span>D.O.S.Y.S · demo</span><span id="counter">1 / 9</span></div>
    <p class="hint" id="hint">Escribe tus credenciales o toca “¿Olvidaste tu contraseña?”.</p>
    <div class="controls">
      <button onclick="back()">← Atrás</button>
      <button onclick="go('login')">Inicio del flujo</button>
      <button onclick="window.open('../UNACH_Diseño_Equipo5.pdf','_blank')">Ver documento PDF</button>
    </div>
    <p class="footer-note">Prototipo autocontenido · funciona sin internet · las capturas son del sistema real de demostración.</p>
  </main>
</div>

<script>
const SCREENS = {screens_json};
const MAIN = ['login','home','record','checkin','security'];
let current = 'login';
let stack = [];
let show = true;

const shot = document.getElementById('shot');
const hotspots = document.getElementById('hotspots');
const toast = document.getElementById('toast');
const crumb = document.getElementById('crumb');
const hint = document.getElementById('hint');
const counter = document.getElementById('counter');

function renderList() {{
  const list = document.getElementById('screenList');
  list.innerHTML = '';
  MAIN.forEach((id, i) => {{
    const s = SCREENS[id];
    const b = document.createElement('button');
    b.className = 'screen-btn' + (id === current ? ' active' : '');
    b.innerHTML = `<span class="num">${{i+1}}</span><span>${{s.title}}</span>`;
    b.onclick = () => go(id);
    list.appendChild(b);
  }});
}}

function render() {{
  const s = SCREENS[current];
  shot.src = s.img;
  shot.alt = s.title;
  crumb.textContent = s.title;
  hint.textContent = s.hint;
  hotspots.innerHTML = '';
  s.hotspots.forEach(h => {{
    const el = document.createElement('button');
    el.className = 'hotspot';
    el.style.left = h.x + '%';
    el.style.top = h.y + '%';
    el.style.width = h.w + '%';
    el.style.height = h.h + '%';
    el.dataset.label = h.label || '';
    el.setAttribute('aria-label', h.label || 'Zona interactiva');
    el.onclick = (e) => {{
      e.stopPropagation();
      if (h.toast) {{ showToast(h.toast); return; }}
      if (h.to) go(h.to);
    }};
    hotspots.appendChild(el);
  }});
  const total = Object.keys(SCREENS).length;
  const idx = Object.keys(SCREENS).indexOf(current) + 1;
  counter.textContent = `${{idx}} / ${{total}}`;
  renderList();
}}

function go(id, push = true) {{
  if (!SCREENS[id]) return;
  if (push && id !== current) stack.push(current);
  current = id;
  render();
}}

function back() {{
  if (stack.length) {{ current = stack.pop(); render(); }}
  else go('home', false);
}}

function reset() {{
  stack = [];
  current = 'login';
  render();
}}

function showToast(msg) {{
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(window.__toast);
  window.__toast = setTimeout(() => toast.classList.remove('show'), 2600);
}}

function toggleHotspots() {{
  show = !show;
  document.querySelector('.screen').classList.toggle('show-hotspots', show);
}}

function fullscreen() {{
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
}}

document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') back();
  if (e.key === 'ArrowLeft') back();
}});

document.querySelector('.screen').classList.add('show-hotspots');
render();
</script>
</body>
</html>"""
    path = os.path.join(OUT, "Prototipo_DOSYS.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("ok", path, round(os.path.getsize(path) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    build()
