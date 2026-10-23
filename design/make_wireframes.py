"""Genera los wireframes de baja fidelidad (5 pantallas) como HTML y PNG."""

from __future__ import annotations

import os
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "assets", "wireframes")
os.makedirs(OUT, exist_ok=True)

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; width: 1080px; height: 2400px; background: #fff; }
body { font-family: Arial, Helvetica, sans-serif; color: #333; }
.status { height: 64px; display: flex; align-items: center; justify-content: space-between; padding: 0 42px; color: #777; font-size: 26px; }
.status .right { letter-spacing: 6px; }
.appbar { height: 128px; background: #ededed; display: flex; align-items: center; padding: 0 36px; gap: 28px; border-bottom: 1px solid #d5d5d5; }
.back { font-size: 54px; color: #555; line-height: 1; }
.appbar h1 { font-size: 40px; font-weight: 700; margin: 0; color: #333; }
.appbar .action { margin-left: auto; width: 54px; height: 54px; border: 2px dashed #aaa; border-radius: 10px; }
.content { padding: 30px 32px 40px; display: flex; flex-direction: column; gap: 24px; }
.card { border: 3px dashed #a8a8a8; border-radius: 22px; background: #f4f4f4; padding: 26px 28px; position: relative; }
.card.solid { border-style: solid; border-color: #cfcfcf; background: #fafafa; }
.card h2 { font-size: 32px; margin: 0 0 10px; font-weight: 700; color: #333; }
.card h3 { font-size: 28px; margin: 0 0 8px; font-weight: 700; color: #333; }
.card p, .muted { font-size: 24px; line-height: 1.45; color: #666; margin: 0; }
.bar { height: 16px; border-radius: 8px; background: #cfcfcf; margin: 10px 0; }
.bar.w90 { width: 90%; } .bar.w75 { width: 75%; } .bar.w60 { width: 60%; } .bar.w45 { width: 45%; }
.btn { height: 92px; border-radius: 46px; background: #4a4a4a; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 700; margin-top: 16px; }
.btn.outline { background: #fff; color: #444; border: 3px dashed #999; }
.field { border: 3px dashed #9a9a9a; border-radius: 16px; height: 108px; display: flex; align-items: center; gap: 18px; padding: 0 24px; margin-top: 14px; background: #fff; }
.field .icon { width: 34px; height: 34px; border: 3px dashed #999; border-radius: 8px; }
.field .label { font-size: 24px; color: #666; }
.link { text-align: center; font-size: 26px; color: #444; text-decoration: underline; margin-top: 8px; }
.small { font-size: 22px; color: #777; line-height: 1.4; }
.badge { position: absolute; top: -18px; right: -12px; width: 44px; height: 44px; border-radius: 50%; background: #222; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.tile { border: 3px dashed #a8a8a8; border-radius: 18px; background: #f4f4f4; height: 190px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }
.tile .icon { width: 54px; height: 54px; border: 3px dashed #999; border-radius: 12px; }
.tile span { font-size: 24px; color: #555; font-weight: 700; }
.section { font-size: 30px; font-weight: 700; color: #444; margin: 4px 0 -4px; }
.map { height: 280px; border: 3px dashed #999; border-radius: 16px; background: #e9e9e9; position: relative; overflow: hidden; }
.map:before, .map:after { content: ""; position: absolute; background: #cfcfcf; }
.map:before { width: 140%; height: 46px; left: -20%; top: 40%; transform: rotate(-12deg); }
.map:after { width: 46px; height: 140%; left: 55%; top: -20%; transform: rotate(18deg); }
.pin { position: absolute; width: 46px; height: 46px; border: 5px solid #555; border-radius: 50%; left: 48%; top: 38%; background: #fff; }
.pin:after { content: ""; position: absolute; width: 5px; height: 55px; background: #555; left: 16px; top: 40px; }
.row { display: flex; gap: 18px; align-items: center; }
.dot { width: 44px; height: 44px; border: 3px dashed #999; border-radius: 50%; flex: 0 0 auto; }
.progress { height: 14px; background: #d0d0d0; border-radius: 7px; margin: 12px 0 4px; overflow: hidden; }
.progress div { height: 100%; width: 62%; background: #777; }
.note { margin-top: auto; padding: 22px 8px 0; font-size: 21px; color: #777; text-align: center; }
.overlay { position: absolute; left: 26px; right: 26px; top: 22px; border: 4px dashed #555; background: rgba(255,255,255,.92); border-radius: 20px; padding: 22px 24px; }
.overlay h3 { font-size: 28px; margin: 0 0 6px; }
"""


def shell(title, content, back=True, action=False, show_appbar=True):
    back_html = '<div class="back">←</div>' if back else '<div style="width:54px"></div>'
    action_html = '<div class="action"></div>' if action else ""
    appbar = ""
    if show_appbar:
        appbar = f'<div class="appbar">{back_html}<h1>{title}</h1>{action_html}</div>'
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
  <div class="status"><span>9:41</span><span class="right">▮▮▮ ᯤ ▰</span></div>
  {appbar}
  <div class="content">{content}</div>
</body></html>"""


def badge(n):
    return f'<div class="badge">{n}</div>'


def wire_login():
    content = f"""
    <div style="height:60px"></div>
    <div style="display:flex;flex-direction:column;align-items:center;gap:18px">
      <div style="width:150px;height:150px;border:4px dashed #777;border-radius:28px;display:flex;align-items:center;justify-content:center;font-size:32px;color:#777">LOGO</div>
      <div style="font-size:62px;font-weight:800;letter-spacing:2px;color:#444">D.O.S.Y.S</div>
      <div class="muted" style="text-align:center">Tu expediente clínico, en tus manos</div>
    </div>
    <div style="height:40px"></div>
    <div class="card">{badge(1)}
      <div class="field"><div class="icon"></div><div class="label">Usuario o CURP</div></div>
      <div class="field"><div class="icon"></div><div class="label">Contraseña</div></div>
      <div class="btn">Iniciar sesión</div>
      <div class="link">¿Olvidaste tu contraseña?</div>
    </div>
    <div class="small" style="text-align:center;padding:0 12px">
      <div style="height:12px"></div>
      Aviso de demostración y ayuda para el primer acceso.
    </div>
    """
    return shell("", content, back=False, show_appbar=False)


def wire_home():
    content = f"""
    <div class="card">{badge(1)}
      <div class="row"><div class="dot"></div><h2>Próxima cita</h2></div>
      <div class="bar w60"></div>
      <div class="bar w75"></div>
      <div class="bar w45"></div>
      <div class="small" style="margin-top:14px">Toca para ver todas tus citas</div>
    </div>
    <div class="card">{badge(2)}
      <h2>Tratamiento activo</h2>
      <div class="bar w60"></div>
      <div class="progress"><div></div></div>
      <div class="small">2 de 5 tomas</div>
      <div class="bar w45" style="margin-top:18px"></div>
      <div class="progress"><div style="width:35%"></div></div>
      <div class="small">1 de 3 tomas</div>
    </div>
    <div class="section">Mi información</div>
    <div class="grid">
      <div class="tile"><div class="icon"></div><span>Expediente</span></div>
      <div class="tile"><div class="icon"></div><span>Estudios</span></div>
      <div class="tile"><div class="icon"></div><span>Recetas</span></div>
      <div class="tile"><div class="icon"></div><span>Mi QR</span></div>
      <div class="tile"><div class="icon"></div><span>Check-in</span></div>
      <div class="tile"><div class="icon"></div><span>Mi seguridad</span></div>
    </div>
    <div class="tile" style="height:130px;flex-direction:row;gap:24px"><div class="icon"></div><span>Mis documentos</span></div>
    <div class="small" style="text-align:center">Solo lectura: la información clínica la modifica tu médico.</div>
    """
    return shell("Hola, [nombre]", content, action=True)


def wire_record():
    content = f"""
    <div class="card" style="position:relative">{badge(1)}
      <div class="overlay">
        <h3>Desbloquea tu expediente</h3>
        <div class="small">Usa tu huella o el bloqueo del teléfono para ver tu información clínica.</div>
        <div class="btn outline" style="height:76px;margin-top:14px">Continuar</div>
      </div>
      <div style="height:210px"></div>
    </div>
    <div class="card">{badge(2)}
      <h2>Datos del paciente</h2>
      <div class="small">Nombre · CURP · Nacimiento · Tipo de sangre · Contacto de emergencia</div>
      <div class="bar w90"></div><div class="bar w75"></div><div class="bar w60"></div>
    </div>
    <div class="card">
      <h3>Alergias, antecedentes y diagnósticos crónicos</h3>
      <div class="bar w90"></div><div class="bar w60"></div>
    </div>
    <div class="section">Historial de consultas</div>
    <div class="card">
      <div class="small">Fecha · Especialidad · Médico</div>
      <div class="bar w60"></div><div class="bar w90"></div><div class="bar w75"></div>
    </div>
    <div class="card">
      <div class="small">Fecha · Especialidad · Médico</div>
      <div class="bar w45"></div><div class="bar w90"></div><div class="bar w60"></div>
    </div>
    <div class="small" style="text-align:center">Solo lectura. Si detectas un dato incorrecto, comunícalo en tu próxima consulta.</div>
    """
    return shell("Mi expediente", content)


def wire_checkin():
    content = f"""
    <div class="card">{badge(1)}
      <h2>Confirma tu llegada</h2>
      <p>Escanea el código QR que recepción muestra en pantalla. Si no puedes escanear, escribe el código de respaldo.</p>
      <div class="btn">▣ &nbsp; Abrir cámara</div>
      <div class="field"><div class="label">Código de respaldo</div></div>
      <div class="btn outline">Confirmar con el código</div>
    </div>
    <div class="card">{badge(2)}
      <div class="row"><div class="dot"></div><h2>Ubicación del hospital</h2></div>
      <div class="map"><div class="pin"></div></div>
      <div class="small" style="margin-top:12px">Estás a 697 m del hospital · Abrir en la app de mapas</div>
    </div>
    <div class="card solid">
      <h3>Llegada confirmada</h3>
      <div class="small">Especialidad · Consultorio · Fecha y hora</div>
    </div>
    <div class="section">Mis citas</div>
    <div class="card">
      <div class="bar w45"></div><div class="bar w60"></div>
      <div class="row" style="margin-top:14px"><div style="border:2px solid #999;border-radius:20px;padding:8px 18px;font-size:20px">Confirmada</div><div style="border:2px solid #999;border-radius:20px;padding:8px 18px;font-size:20px">Llegaste</div></div>
    </div>
    """
    return shell("Check-in", content)


def wire_security():
    content = f"""
    <div class="card">{badge(1)}
      <div class="row"><div class="dot"></div><div><h2>Segundo factor inactivo</h2><div class="small">Protege tu cuenta: además de la contraseña se pedirá un código temporal.</div></div></div>
      <div class="btn">Activar segundo factor</div>
    </div>
    <div class="card">{badge(2)}
      <h2>Cambiar contraseña</h2>
      <div class="small">Se cerrarán las demás sesiones abiertas por seguridad.</div>
      <div class="field"><div class="label">Contraseña actual</div></div>
      <div class="field"><div class="label">Contraseña nueva</div></div>
      <div class="small" style="margin-top:10px">Mínimo 8 caracteres, con letras y números</div>
      <div class="field"><div class="label">Repite la contraseña nueva</div></div>
      <div class="row" style="margin-top:18px"><div style="width:38px;height:38px;border:3px solid #888;border-radius:4px"></div><div class="small">Mostrar contraseñas</div></div>
      <div class="btn outline" style="margin-top:18px">Cambiar contraseña</div>
    </div>
    <div class="small" style="text-align:center">También puedes usar códigos de recuperación de un solo uso.</div>
    """
    return shell("Mi seguridad", content)


def render(name, html):
    path = os.path.join(OUT, name + ".html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    url = "file:///" + path.replace("\\", "/")
    png = os.path.join(OUT, name + ".png")
    cmd = [
        EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--default-background-color=FFFFFFFF",
        "--virtual-time-budget=1200", f"--screenshot={png}", "--window-size=1080,2400", url,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print("ok", name, os.path.getsize(png))


if __name__ == "__main__":
    render("01-login", wire_login())
    render("02-home", wire_home())
    render("03-record", wire_record())
    render("04-checkin", wire_checkin())
    render("05-security", wire_security())
    print("wireframes listos")
