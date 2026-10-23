"""Genera los diagramas SVG del documento de diseño D.O.S.Y.S."""

from __future__ import annotations

import base64
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "assets", "diagrams")
LOGOS = os.path.join(ROOT, "assets", "logos")

INK = "#1F2320"
MUTED = "#5B6560"
LINE = "#94A3B8"
GREEN = "#13653F"
GREEN_MID = "#2F7A5A"
GREEN_LIGHT = "#EAF4EF"
BLUE = "#2563EB"
BLUE_LIGHT = "#EFF6FF"
AMBER = "#B45309"
AMBER_LIGHT = "#FFF7ED"
PURPLE = "#6D28D9"
PURPLE_LIGHT = "#F5F3FF"
GRAY_LIGHT = "#F8FAFC"
WHITE = "#FFFFFF"

FONT = "Arial, Helvetica, sans-serif"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def logo_data(name: str) -> str:
    path = os.path.join(LOGOS, name)
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"


def text(x, y, value, size=20, fill=INK, weight="normal", anchor="start", family=FONT, opacity=1):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" opacity="{opacity}">{esc(value)}</text>'
    )


def lines(x, y, values, size=20, fill=INK, weight="normal", anchor="start", lh=24):
    out = []
    for i, value in enumerate(values):
        out.append(text(x, y + i * lh, value, size, fill, weight, anchor))
    return "".join(out)


def rect(x, y, w, h, fill=WHITE, stroke=LINE, rx=14, sw=2, dash=None, opacity=1):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{d}/>'
    )


def line(x1, y1, x2, y2, stroke=LINE, sw=2, dash=None, marker=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#{marker})"' if marker else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{sw}"{d}{m}/>'
    )


def path(d, stroke=LINE, sw=2, fill="none", dash=None, marker=None, opacity=1):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#{marker})"' if marker else ""
    return (
        f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
        f'opacity="{opacity}"{da}{m}/>'
    )


def markers() -> str:
    colors = {"arrow": LINE, "green": GREEN, "blue": BLUE, "amber": AMBER, "purple": PURPLE}
    out = []
    for name, color in colors.items():
        out.append(
            f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    return "<defs>" + "".join(out) + "</defs>"


def actor(x, y, label, color=MUTED):
    return f"""
    <g>
      <circle cx="{x}" cy="{y}" r="17" fill="{WHITE}" stroke="{color}" stroke-width="3"/>
      <line x1="{x}" y1="{y+17}" x2="{x}" y2="{y+72}" stroke="{color}" stroke-width="3"/>
      <line x1="{x-27}" y1="{y+35}" x2="{x+27}" y2="{y+35}" stroke="{color}" stroke-width="3"/>
      <line x1="{x}" y1="{y+72}" x2="{x-24}" y2="{y+108}" stroke="{color}" stroke-width="3"/>
      <line x1="{x}" y1="{y+72}" x2="{x+24}" y2="{y+108}" stroke="{color}" stroke-width="3"/>
      {text(x, y+140, label, 22, INK, "bold", "middle")}
    </g>"""


def header(w, h, title, subtitle=""):
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        markers(),
        f'<rect width="{w}" height="{h}" fill="{WHITE}"/>',
        text(50, 58, title, 32, INK, "bold"),
    ]
    if subtitle:
        out.append(text(50, 90, subtitle, 18, MUTED))
    return "".join(out)


def save(name: str, content: str):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(content + "</svg>")
    print("ok", name)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Casos de uso
# ─────────────────────────────────────────────────────────────────────────────
def use_cases():
    w, h = 1850, 1500
    out = [header(w, h, "Diagrama de casos de uso · App del paciente", "Actores, casos principales y relaciones «include» / «extend»")]

    # Frontera del sistema
    bx, by, bw, bh = 340, 120, 1120, 1320
    out.append(rect(bx, by, bw, bh, "#FBFDFC", GREEN_MID, 22, 2.5))
    out.append(text(bx + 28, by + 40, "D.O.S.Y.S · aplicación Android del paciente", 22, GREEN, "bold"))

    # Actor principal
    out.append(actor(140, 640, "Paciente"))

    # Bus del actor
    out.append(line(210, 640, 270, 640, MUTED, 2.5))
    out.append(line(270, 210, 270, 1270, MUTED, 2.5))

    cases = [
        ("CU-01", "Iniciar sesión y verificar 2FA", 210),
        ("CU-02", "Recuperar contraseña", 320),
        ("CU-03", "Consultar expediente clínico", 430),
        ("CU-04", "Ver citas y estados", 540),
        ("CU-05", "Hacer check-in con QR", 650),
        ("CU-06", "Consultar estudios y resultados", 760),
        ("CU-07", "Ver recetas y tratamiento", 870),
        ("CU-08", "Ver documentos del expediente", 980),
        ("CU-09", "Mostrar mi QR", 1090),
        ("CU-10", "Gestionar mi seguridad", 1200),
        ("CU-11", "Cerrar sesión", 1310),
    ]
    for code, label, cy in cases:
        out.append(line(270, cy, 470, cy, MUTED, 2))
        out.append(f'<ellipse cx="760" cy="{cy}" rx="290" ry="46" fill="{GREEN_LIGHT}" stroke="{GREEN_MID}" stroke-width="2.2"/>')
        out.append(text(760, cy - 6, label, 19, INK, "bold", "middle"))
        out.append(text(760, cy + 20, code, 15, GREEN, "bold", "middle"))

    # Relaciones include / extend
    inc = [
        ("Verificar código TOTP", 210, "include"),
        ("Validar huella dactilar", 430, "include"),
        ("Escanear QR con la cámara", 650, "include"),
        ("Usar código de respaldo", 760, "extend"),
        ("Descargar PDF firmado", 980, "include"),
    ]
    for label, cy, kind in inc:
        out.append(rect(1290, cy - 34, 250, 68, WHITE, GREEN_MID, 12, 1.8, "5,4"))
        out.append(text(1415, cy - 2, label, 15, INK, "bold", "middle"))
        out.append(text(1415, cy + 20, f"«{kind}»", 13, GREEN, "normal", "middle"))
        # flecha desde el caso principal al caso incluido
        if kind == "include":
            out.append(line(1050, cy, 1290, cy, GREEN, 2, "6,4", "green"))
        else:
            out.append(path(f"M 1290 {cy} L 1060 {cy - 95}", GREEN, 2, dash="6,4", marker="green"))

    # Actores secundarios
    out.append(actor(1720, 650, "Recepción"))
    out.append(line(1720, 650, 1540, 650, MUTED, 2, "6,4"))
    out.append(text(1630, 690, "QR de la cita", 13, MUTED, "normal", "middle"))

    out.append(actor(1720, 250, "App autenticadora"))
    out.append(line(1720, 250, 1540, 210, MUTED, 2, "6,4"))
    out.append(text(1630, 295, "código TOTP", 13, MUTED, "normal", "middle"))

    # Nota
    out.append(rect(60, 1385, 1730, 70, "#F8FAFC", "#E2E8F0", 12, 1.5))
    out.append(text(85, 1428, "El paciente es el actor principal; Recepción y la app autenticadora participan como actores secundarios en el check-in y el segundo factor.", 17, MUTED))
    save("use-cases.svg", "".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mapa de navegación
# ─────────────────────────────────────────────────────────────────────────────
def navigation():
    w, h = 1750, 1320
    out = [header(w, h, "Mapa de navegación · 11 rutas + 2 estados", "Rutas reales del NavHost de la app (Kotlin + Navigation Compose)")]

    def node(x, y, nw, nh, title, route, fill, stroke, dash=None, sub=None):
        out.append(rect(x, y, nw, nh, fill, stroke, 16, 2.4, dash))
        out.append(text(x + nw / 2, y + 32, title, 20, INK, "bold", "middle"))
        out.append(text(x + nw / 2, y + 56, route, 13, stroke, "normal", "middle", "Consolas, monospace"))
        if sub:
            out.append(text(x + nw / 2, y + 78, sub, 13, MUTED, "normal", "middle"))

    # Fila 1
    node(720, 120, 300, 78, "Login", "Routes.LOGIN", GREEN_LIGHT, GREEN)
    node(300, 120, 260, 78, "Verificación 2FA", "estado de Login", WHITE, GREEN, "6,4")
    node(1190, 120, 280, 78, "Recuperar contraseña", "diálogo modal", WHITE, GREEN, "6,4")

    # Home
    node(690, 300, 360, 90, "Inicio", "Routes.HOME", GREEN_LIGHT, GREEN, sub="próxima cita · tratamiento · accesos")

    # Fila 2
    row2 = [
        (90, "Expediente", "Routes.RECORD", BLUE_LIGHT, BLUE, "huella"),
        (470, "Citas", "Routes.APPOINTMENTS", BLUE_LIGHT, BLUE, None),
        (850, "Check-in", "Routes.CHECKIN", AMBER_LIGHT, AMBER, "QR + GPS"),
        (1230, "Estudios", "Routes.STUDIES", BLUE_LIGHT, BLUE, None),
    ]
    for x, title, route, fill, stroke, sub in row2:
        node(x, 500, 300, 80, title, route, fill, stroke, sub=sub)

    # Fila 3
    row3 = [
        (90, "Recetas", "Routes.PRESCRIPTIONS", BLUE_LIGHT, BLUE, None),
        (470, "Documentos", "Routes.DOCUMENTS", BLUE_LIGHT, BLUE, None),
        (850, "Mi QR", "Routes.QR", BLUE_LIGHT, BLUE, None),
        (1230, "Mi seguridad", "Routes.SECURITY", PURPLE_LIGHT, PURPLE, "2FA"),
    ]
    for x, title, route, fill, stroke, sub in row3:
        node(x, 730, 300, 80, title, route, fill, stroke, sub=sub)

    # Detalle de estudio
    node(1230, 960, 300, 78, "Detalle de estudio", "Routes.STUDY_DETAIL", BLUE_LIGHT, BLUE, sub="resultado + PDF")

    # Flechas Login/2FA/Recuperación
    out.append(line(720, 198, 720, 300, GREEN, 2.6, None, "green"))
    out.append(text(735, 255, "credenciales válidas", 14, MUTED))
    out.append(path("M 560 160 L 720 160", GREEN, 2.2, dash="6,4", marker="green"))
    out.append(path("M 1190 160 L 1020 160", GREEN, 2.2, dash="6,4", marker="green"))
    out.append(text(590, 145, "si la cuenta tiene 2FA", 13, MUTED, "normal", "middle"))
    out.append(text(1105, 145, "enlace de un solo uso", 13, MUTED, "normal", "middle"))

    # Home → fila 2 (bus vertical)
    out.append(line(870, 390, 870, 440, GREEN, 2.6))
    out.append(line(240, 440, 1380, 440, GREEN, 2.6))
    for x in (240, 620, 1000, 1380):
        out.append(line(x, 440, x, 500, GREEN, 2.2, None, "green"))

    # Home → fila 3 (bus por el costado derecho, sin cruzar la fila 2)
    out.append(path("M 1050 360 L 1650 360 L 1650 670 L 240 670", GREEN, 2.2))
    for x in (240, 620, 1000, 1380):
        out.append(line(x, 670, x, 730, GREEN, 2.2, None, "green"))

    # Estudios → detalle (rodea Mi seguridad por la derecha)
    out.append(path("M 1380 580 L 1380 620 L 1680 620 L 1680 999 L 1530 999", BLUE, 2.4, marker="blue"))
    out.append(text(1400, 900, "toca un estudio", 14, MUTED))

    # Regreso
    out.append(path("M 90 810 L 40 810 L 40 345 L 690 345", MUTED, 2, dash="6,5", marker="arrow"))

    # Logout
    out.append(path("M 1050 345 L 1560 345 L 1560 198 L 1470 198", MUTED, 2, dash="6,5", marker="arrow"))
    out.append(text(1305, 330, "cerrar sesión · popUpTo(0)", 14, MUTED, "normal", "middle"))

    # Nota de regreso
    out.append(text(90, 1085, "← atrás: todas las pantallas internas vuelven al inicio con popBackStack(); la huella y la cámara son compuertas locales.", 15, MUTED))

    # Leyenda
    out.append(rect(90, 1150, 1570, 110, "#F8FAFC", "#E2E8F0", 14, 1.5))
    out.append(text(115, 1187, "Leyenda", 17, INK, "bold"))
    out.append(line(250, 1180, 310, 1180, GREEN, 3, None, "green"))
    out.append(text(325, 1186, "navegación principal", 15, MUTED))
    out.append(line(520, 1180, 580, 1180, MUTED, 2, "6,4", "arrow"))
    out.append(text(595, 1186, "regreso / cierre de sesión", 15, MUTED))
    out.append(rect(830, 1166, 34, 28, WHITE, GREEN, 6, 1.5, "5,4"))
    out.append(text(875, 1186, "estado o diálogo (no es una ruta del NavHost)", 15, MUTED))
    out.append(text(115, 1230, "Login limpia el backstack al entrar; el logout lo limpia por completo. La huella y la cámara son compuertas locales, no pantallas nuevas.", 15, MUTED))

    save("navigation.svg", "".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# 3. MVVM
# ─────────────────────────────────────────────────────────────────────────────
def mvvm():
    w, h = 1750, 1270
    out = [header(w, h, "Arquitectura MVVM · D.O.S.Y.S", "Flujo unidireccional de datos y responsabilidad de cada capa")]

    # UI
    y = 120
    out.append(rect(60, y, 1630, 220, "#FBFDFC", GREEN_MID, 18, 2.2))
    out.append(text(90, y + 38, "UI · Jetpack Compose + Material 3", 22, GREEN, "bold"))
    out.append(text(90, y + 64, "Renderiza el estado, captura eventos y aplica accesibilidad. No contiene reglas de negocio.", 16, MUTED))
    for i, name in enumerate(["LoginScreen", "HomeScreen", "RecordScreen", "CheckInScreen", "SecurityScreen"]):
        x = 90 + i * 315
        out.append(rect(x, y + 90, 285, 100, WHITE, "#C9DED4", 12, 1.8))
        out.append(text(x + 142, y + 130, name, 18, INK, "bold", "middle"))
        out.append(text(x + 142, y + 158, "Compose · M3", 14, GREEN, "normal", "middle"))

    # VM
    y = 400
    out.append(rect(60, y, 1630, 200, "#F5F9FF", BLUE, 18, 2.2))
    out.append(text(90, y + 38, "ViewModel · estado y lógica de presentación", 22, BLUE, "bold"))
    out.append(text(90, y + 64, "Expone StateFlow<UiState>, valida entradas, orquesta casos y sobrevive a cambios de configuración.", 16, MUTED))
    for i, name in enumerate(["LoginViewModel", "HomeViewModel", "RecordViewModel", "CheckInViewModel", "SecurityViewModel"]):
        x = 90 + i * 315
        out.append(rect(x, y + 90, 285, 82, WHITE, "#BFDBFE", 12, 1.8))
        out.append(text(x + 142, y + 126, name, 18, INK, "bold", "middle"))
        out.append(text(x + 142, y + 150, "StateFlow + eventos", 13, BLUE, "normal", "middle"))

    # Repo
    y = 660
    out.append(rect(60, y, 1630, 190, "#FFFBF5", AMBER, 18, 2.2))
    out.append(text(90, y + 38, "Repository · única fuente de verdad", 22, AMBER, "bold"))
    out.append(text(90, y + 64, "Mapea DTO → modelo de dominio, centraliza el acceso a datos y decide qué hacer ante errores.", 16, MUTED))
    for i, name in enumerate(["AuthRepository", "PatientRepository", "SecurityRepository"]):
        x = 90 + i * 525
        out.append(rect(x, y + 90, 480, 72, WHITE, "#FED7AA", 12, 1.8))
        out.append(text(x + 240, y + 125, name, 19, INK, "bold", "middle"))
        out.append(text(x + 240, y + 148, "perfil · citas · consultas · documentos", 13, AMBER, "normal", "middle"))

    # Data
    y = 910
    out.append(rect(60, y, 1630, 190, "#F8FAFC", "#64748B", 18, 2.2))
    out.append(text(90, y + 38, "Data · red y sesión", 22, "#334155", "bold"))
    out.append(text(90, y + 64, "Retrofit + OkHttp, kotlinx.serialization, DataStore para el token y refresco automático en 401.", 16, MUTED))
    for i, (name, sub) in enumerate([
        ("ApiService", "Retrofit · endpoints"),
        ("SessionManager", "DataStore · tokens"),
        ("TokenRefresher", "401 · rotación"),
        ("MockData", "datos de ejemplo"),
    ]):
        x = 90 + i * 390
        out.append(rect(x, y + 90, 350, 72, WHITE, "#CBD5E1", 12, 1.8))
        out.append(text(x + 175, y + 122, name, 18, INK, "bold", "middle"))
        out.append(text(x + 175, y + 146, sub, 13, MUTED, "normal", "middle"))

    # Backend
    y = 1160
    out.append(rect(60, y, 1630, 72, "#F1F5F9", "#64748B", 14, 2, "8,5"))
    out.append(text(875, y + 30, "Frontera del sistema · API REST FastAPI + PostgreSQL (HTTPS)", 20, "#334155", "bold", "middle"))
    out.append(text(875, y + 54, "JWT 30 min · refresh 7 días · RBAC · Argon2 · auditoría", 15, MUTED, "normal", "middle"))

    # Arrows between layers
    out.append(line(800, 340, 800, 400, GREEN, 3, None, "green"))
    out.append(text(815, 375, "eventos del usuario", 14, MUTED))
    out.append(line(970, 400, 970, 340, GREEN, 3, None, "green"))
    out.append(text(985, 375, "StateFlow<UiState>", 14, MUTED))

    out.append(line(800, 600, 800, 660, BLUE, 3, None, "blue"))
    out.append(text(815, 635, "solicita datos", 14, MUTED))
    out.append(line(970, 660, 970, 600, BLUE, 3, None, "blue"))
    out.append(text(985, 635, "resultado / error", 14, MUTED))

    out.append(line(800, 850, 800, 910, AMBER, 3, None, "amber"))
    out.append(text(815, 885, "DTO / modelo", 14, MUTED))
    out.append(line(970, 910, 970, 850, AMBER, 3, None, "amber"))
    out.append(text(985, 885, "modelo de dominio", 14, MUTED))

    out.append(line(875, 1100, 875, 1160, "#64748B", 3, None, "arrow"))
    out.append(text(895, 1135, "HTTPS / JSON", 14, MUTED))

    # Transversal
    out.append(text(875, 1248, "Transversal: ServiceLocator (DI manual) · BiometricPrompt · ZXing · OSMDroid · DataStore", 15, MUTED, "normal", "middle"))

    save("mvvm.svg", "".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Arquitectura de datos / stack con logos
# ─────────────────────────────────────────────────────────────────────────────
def logo_card(x, y, w, h, logo, name, sub="", color=INK):
    out = [rect(x, y, w, h, WHITE, "#D8E5DF", 12, 1.5)]
    if logo:
        out.append(f'<image href="{logo_data(logo)}" x="{x + 14}" y="{y + 14}" width="34" height="34"/>')
        out.append(text(x + 58, y + 30, name, 15, color, "bold"))
        if sub:
            out.append(text(x + 58, y + 50, sub, 11, MUTED))
    else:
        out.append(text(x + 14, y + 30, name, 15, color, "bold"))
        if sub:
            out.append(text(x + 14, y + 50, sub, 11, MUTED))
    return "".join(out)


def data_architecture():
    w, h = 1850, 1320
    out = [header(w, h, "Arquitectura de datos y stack tecnológico", "Logos de las herramientas y flujo real de los datos entre cliente, borde, servidor y almacenamiento")]

    # Zonas
    zones = [
        (50, 120, 420, 740, "1 · Clientes", GREEN_LIGHT, GREEN),
        (500, 120, 300, 740, "2 · Borde", "#F8FAFC", "#64748B"),
        (830, 120, 470, 740, "3 · Servidor y build", BLUE_LIGHT, BLUE),
        (1330, 120, 470, 740, "4 · Datos, servicios y herramientas", AMBER_LIGHT, AMBER),
    ]
    for x, y, zw, zh, title, fill, stroke in zones:
        out.append(rect(x, y, zw, zh, fill, stroke, 18, 2.2))
        out.append(text(x + 22, y + 38, title, 20, stroke, "bold"))

    # Cliente Android
    cx, cy = 70, 180
    out.append(logo_card(cx, cy, 180, 68, "android.svg", "Android", "API 26+"))
    out.append(logo_card(cx + 200, cy, 180, 68, "kotlin.svg", "Kotlin", "2.x"))
    out.append(logo_card(cx, cy + 88, 180, 68, "jetpackcompose.svg", "Compose", "UI declarativa"))
    out.append(logo_card(cx + 200, cy + 88, 180, 68, "materialdesign.svg", "Material 3", "diseño"))
    out.append(logo_card(cx, cy + 176, 180, 68, None, "Retrofit", "REST + OkHttp"))
    out.append(logo_card(cx + 200, cy + 176, 180, 68, None, "ZXing", "cámara / QR"))
    out.append(logo_card(cx, cy + 264, 180, 68, "openstreetmap.svg", "OSM", "mapa / GPS"))
    out.append(logo_card(cx + 200, cy + 264, 180, 68, None, "Biometric", "huella"))
    out.append(logo_card(cx, cy + 352, 180, 68, "figma.svg", "Figma", "diseño UI"))
    out.append(logo_card(cx + 200, cy + 352, 180, 68, "androidstudio.svg", "Android Studio", "IDE"))

    # Portal (cliente web)
    out.append(rect(cx, cy + 450, 380, 170, WHITE, "#D8E5DF", 14, 1.6, "6,4"))
    out.append(text(cx + 20, cy + 482, "Portal clínico (web)", 17, GREEN, "bold"))
    out.append(text(cx + 20, cy + 508, "HTML + Jinja2 servido por FastAPI", 13, MUTED))
    for i, item in enumerate(["Recepción · QR de la cita", "Médico · consulta y recetas", "Laboratorio · resultados"]):
        out.append(text(cx + 20, cy + 536 + i * 24, "• " + item, 13, MUTED))
    out.append(text(cx + 20, cy + 610, "misma API · mismos permisos", 12, GREEN, "bold"))

    # Borde
    bx = 520
    out.append(logo_card(bx, 180, 260, 72, "cloudflare.svg", "Cloudflare", "DNS + TLS"))
    out.append(line(780, 216, 810, 216, "#64748B", 2, None, "arrow"))
    out.append(logo_card(bx, 280, 260, 72, "nginx.svg", "Nginx Proxy", "Manager"))
    out.append(line(780, 316, 810, 316, "#64748B", 2, None, "arrow"))
    out.append(logo_card(bx, 380, 260, 72, "letsencrypt.svg", "Let's Encrypt", "HTTPS"))
    out.append(text(650, 490, "TLS · HSTS", 14, MUTED, "normal", "middle"))
    out.append(text(650, 515, "candado en el navegador", 12, MUTED, "normal", "middle"))
    out.append(text(650, 585, "Proxy inverso", 13, GREEN, "bold", "middle"))
    out.append(text(650, 610, "fuerza HTTPS y", 12, MUTED, "normal", "middle"))
    out.append(text(650, 630, "detecta la IP real", 12, MUTED, "normal", "middle"))

    # Servidor
    sx = 850
    out.append(logo_card(sx, 180, 205, 68, "ubuntu.svg", "Ubuntu", "VPS"))
    out.append(logo_card(sx + 225, 180, 205, 68, "docker.svg", "Docker", "Compose"))
    out.append(logo_card(sx, 268, 205, 68, "fastapi.svg", "FastAPI", "API REST"))
    out.append(logo_card(sx + 225, 268, 205, 68, "python.svg", "Python", "3.12"))
    out.append(logo_card(sx, 356, 205, 68, "pydantic.svg", "Pydantic", "validación"))
    out.append(logo_card(sx + 225, 356, 205, 68, "sqlalchemy.svg", "SQLAlchemy", "ORM async"))
    out.append(logo_card(sx, 444, 205, 68, "jinja.svg", "Jinja2", "portal"))
    out.append(logo_card(sx + 225, 444, 205, 68, None, "ReportLab", "PDF + hash"))
    out.append(logo_card(sx, 532, 205, 68, "jsonwebtokens.svg", "JWT", "HS256"))
    out.append(logo_card(sx + 225, 532, 205, 68, None, "Argon2 / TOTP", "contraseñas + 2FA"))
    out.append(logo_card(sx, 620, 205, 68, "gradle.svg", "Gradle", "build Android"))
    out.append(logo_card(sx + 225, 620, 205, 68, "git.svg", "Git", "versiones"))
    out.append(text(sx + 235, 735, "Uvicorn · Alembic · PyJWT · qrcode", 12, MUTED, "normal", "middle"))

    # Datos
    dx = 1350
    out.append(logo_card(dx, 180, 420, 74, "postgresql.svg", "PostgreSQL", "datos clínicos · 13 tablas · 3FN"))
    out.append(logo_card(dx, 276, 420, 74, None, "Volumen Docker", "PDFs · documentos · resultados"))
    out.append(logo_card(dx, 372, 420, 74, "resend.svg", "Resend", "correo de recuperación"))
    out.append(logo_card(dx, 468, 420, 74, "openstreetmap.svg", "OpenStreetMap", "tiles del mapa · sin API key · HTTPS"))
    out.append(logo_card(dx, 564, 420, 74, "github.svg", "GitHub", "repositorio · README · demo"))
    out.append(logo_card(dx, 660, 420, 74, "figma.svg", "Figma", "mockups y prototipo"))

    # Líneas entre zonas
    out.append(line(470, 420, 500, 420, GREEN, 3, None, "green"))
    out.append(text(485, 400, "HTTPS/REST", 12, MUTED, "normal", "middle"))
    out.append(line(800, 420, 830, 420, "#64748B", 3, None, "arrow"))
    out.append(text(815, 400, "proxy", 12, MUTED, "normal", "middle"))
    out.append(line(1300, 420, 1330, 420, BLUE, 3, None, "blue"))
    out.append(text(1315, 400, "SQL", 12, MUTED, "normal", "middle"))
    out.append(line(1300, 500, 1330, 500, BLUE, 2, "5,4", "blue"))
    out.append(text(1315, 484, "PDF", 12, MUTED, "normal", "middle"))

    # Banda de seguridad
    out.append(rect(50, 890, 1750, 120, "#F5F3FF", PURPLE, 16, 2))
    out.append(text(75, 925, "Seguridad transversal", 19, PURPLE, "bold"))
    pills = ["JWT HS256 · 30 min", "Refresh 7 días + rotación", "Argon2", "RBAC por permisos", "SHA-256 + sello HMAC", "Bitácora de auditoría", "Rate limiting"]
    for i, pill in enumerate(pills):
        x = 75 + i * 238
        out.append(rect(x, 945, 225, 42, WHITE, "#C4B5FD", 21, 1.2))
        out.append(text(x + 112, 971, pill, 12, PURPLE, "bold", "middle"))

    # Nota de capas
    out.append(rect(50, 1040, 1750, 130, "#F8FAFC", "#E2E8F0", 14, 1.5))
    out.append(text(75, 1075, "Lectura del diagrama", 17, INK, "bold"))
    out.append(text(75, 1105, "La app y el portal consumen la misma API. Cloudflare termina TLS, Nginx Proxy Manager enruta y FastAPI valida JWT/permisos antes de tocar PostgreSQL.", 15, MUTED))
    out.append(text(75, 1132, "PostgreSQL vive en una red Docker interna sin puertos publicados. Los PDFs se guardan en un volumen y se registran con SHA-256 + sello HMAC.", 15, MUTED))
    out.append(text(75, 1159, "El mapa usa OpenStreetMap (sin API key) y el correo real es opcional vía Resend; sin clave se usa la vista previa simulada.", 15, MUTED))

    # Leyenda
    out.append(line(75, 1210, 135, 1210, GREEN, 3, None, "green"))
    out.append(text(145, 1216, "petición / respuesta", 13, MUTED))
    out.append(line(340, 1210, 400, 1210, BLUE, 2, "5,4", "blue"))
    out.append(text(410, 1216, "datos / archivos", 13, MUTED))
    out.append(line(580, 1210, 640, 1210, AMBER, 2, "6,4", "amber"))
    out.append(text(650, 1216, "servicio externo", 13, MUTED))

    save("data-architecture.svg", "".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Modelo de clases Kotlin
# ─────────────────────────────────────────────────────────────────────────────
def class_diagram():
    w, h = 1850, 1420
    out = [header(w, h, "Modelo de datos · data classes de Kotlin", "Proyección de solo lectura que consume la app; los IDs referencian entidades del backend")]

    def cls(x, y, cw, title, attrs, fill=WHITE, stroke=BLUE, ch=44):
        head = ch + 12 + len(attrs) * 22
        out.append(rect(x, y, cw, head, fill, stroke, 10, 2))
        out.append(rect(x, y, cw, ch, fill, stroke, 10, 2))
        out.append(text(x + cw / 2, y + 29, title, 17, INK, "bold", "middle"))
        for i, attr in enumerate(attrs):
            out.append(text(x + 12, y + ch + 20 + i * 22, attr, 13, MUTED))
        return ""

    # Centro: perfil
    out.append(cls(690, 150, 390, "PatientProfile", [
        "id: Int",
        "fullName: String",
        "curp: String?",
        "bloodType: String?",
        "birthDate: String?",
        "emergencyContact: String?",
    ], GREEN_LIGHT, GREEN, 48))

    # Alrededor
    out.append(cls(90, 380, 390, "PatientAppointment", [
        "id: Int",
        "specialty: String",
        "doctorName: String?",
        "scheduledAt: String",
        "location: String",
        "status: AppointmentStatus",
        "notes: String?",
        "checkedInAt: String?",
    ], BLUE_LIGHT, BLUE))

    out.append(cls(690, 380, 390, "PatientConsultation", [
        "id: Int",
        "patientId: Int",
        "doctorName: String",
        "specialty: String",
        "reason: String",
        "diagnosis: String",
        "notes: String?",
        "createdAt: String",
    ], BLUE_LIGHT, BLUE))

    out.append(cls(1290, 380, 430, "PatientDocument", [
        "id: Int",
        "title: String",
        "category: String",
        "originalName: String",
        "contentType: String",
        "sizeBytes: Long",
        "sha256: String",
        "createdAt: String",
    ], AMBER_LIGHT, AMBER))

    out.append(cls(90, 720, 390, "PatientStudy", [
        "id: Int",
        "studyName: String",
        "category: String",
        "status: String",
        "requestedAt: String",
        "performedAt: String?",
        "documentId: Int?",
    ], BLUE_LIGHT, BLUE))

    out.append(cls(690, 720, 390, "PatientPrescription", [
        "id: Int",
        "createdAt: String",
        "notes: String?",
        "documentId: Int?",
        "items: List<PatientPrescriptionItem>",
    ], BLUE_LIGHT, BLUE))

    out.append(cls(1290, 720, 430, "PatientPrescriptionItem", [
        "medication: String",
        "dose: String",
        "frequency: String",
        "duration: String?",
    ], BLUE_LIGHT, BLUE))

    # Seguridad / sesión
    out.append(rect(90, 1020, 750, 300, "#F5F3FF", PURPLE, 16, 2))
    out.append(text(115, 1055, "Sesión y seguridad (data classes de apoyo)", 18, PURPLE, "bold"))
    sec = [
        ("LoginResponse", "accessToken · refreshToken · requires2fa · challengeToken"),
        ("TwoFactorStatus", "enabled · recoveryCodesRemaining"),
        ("TwoFactorSetup", "secret · otpauthUri · issuer"),
        ("ChangePasswordRequest", "currentPassword · newPassword · newPasswordConfirm"),
        ("PasswordForgotRequest", "identifier"),
    ]
    for i, (name, attrs) in enumerate(sec):
        out.append(text(115, 1092 + i * 42, name, 15, INK, "bold"))
        out.append(text(380, 1092 + i * 42, attrs, 13, MUTED))

    # Relaciones
    out.append(line(885, 300, 885, 380, GREEN, 2.4, None, "green"))
    out.append(text(900, 345, "1", 16, GREEN, "bold"))
    out.append(text(900, 370, "0..*", 14, GREEN))

    out.append(path("M 690 240 L 285 240 L 285 380", GREEN, 2.2, marker="green"))
    out.append(text(300, 230, "1  →  0..*", 14, GREEN))
    out.append(path("M 1080 240 L 1660 240 L 1660 380", GREEN, 2.2, marker="green"))
    out.append(text(1450, 230, "1  →  0..*", 14, GREEN))

    out.append(path("M 690 300 L 600 300 L 600 690 L 300 690 L 300 720", GREEN, 2.2, marker="green"))
    out.append(text(610, 500, "1 → 0..*", 14, GREEN))

    out.append(path("M 1080 340 L 1200 340 L 1200 720", GREEN, 2.2, marker="green"))
    out.append(text(1215, 500, "1 → 0..*", 14, GREEN))

    # Study -> Document (rodea por el espacio entre Consultation y Prescription)
    out.append(path("M 480 780 L 560 780 L 560 660 L 1500 660 L 1500 612", AMBER, 2, dash="6,4", marker="amber"))
    out.append(text(1010, 650, "documentId  0..1  →  0..1", 13, AMBER, "normal", "middle"))

    # Prescription -> Item
    out.append(line(1080, 800, 1290, 800, BLUE, 2.4, None, "blue"))
    out.append(text(1185, 790, "1  →  1..*", 13, BLUE, "normal", "middle"))

    # Prescription -> Document (paralela a la de Study)
    out.append(path("M 1080 780 L 1150 780 L 1150 680 L 1540 680 L 1540 612", AMBER, 2, dash="6,4", marker="amber"))
    out.append(text(1260, 700, "documentId 0..1", 13, AMBER))

    # Nota
    out.append(rect(900, 1120, 860, 200, "#F8FAFC", "#E2E8F0", 14, 1.5))
    out.append(text(925, 1155, "Cómo leerlo", 17, INK, "bold"))
    out.append(text(925, 1185, "• PatientProfile es la raíz de la proyección del paciente autenticado.", 14, MUTED))
    out.append(text(925, 1212, "• Cada colección se obtiene de un endpoint distinto y se combina en la UI.", 14, MUTED))
    out.append(text(925, 1239, "• PatientDocument se reutiliza para resultados de estudio y recetas en PDF.", 14, MUTED))
    out.append(text(925, 1266, "• Los campos DateTime viajan como String ISO-8601 y se formatean en la capa UI.", 14, MUTED))
    out.append(text(925, 1293, "• El backend mantiene 13 tablas normalizadas en 3FN (ver anexo ER).", 14, MUTED))

    save("class-diagram.svg", "".join(out))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Secuencia de check-in
# ─────────────────────────────────────────────────────────────────────────────
def sequence():
    w, h = 1750, 980
    out = [header(w, h, "Flujo de datos · check-in con QR", "Secuencia real entre la app, el portal, la API y PostgreSQL")]

    xs = {"app": 170, "portal": 560, "api": 980, "db": 1420}
    labels = {"app": "App Android", "portal": "Portal / Recepción", "api": "API FastAPI", "db": "PostgreSQL"}
    for key, x in xs.items():
        out.append(rect(x - 110, 130, 220, 58, GREEN_LIGHT, GREEN, 12, 2))
        out.append(text(x, 166, labels[key], 17, GREEN, "bold", "middle"))
        out.append(line(x, 188, x, 860, "#CBD5E1", 2, "7,6"))

    steps = [
        ("app", "portal", 250, "1. El paciente llega y recepción abre la cita"),
        ("portal", "app", 300, "2. El portal muestra el QR de la cita (o el código de respaldo)"),
        ("app", "app", 350, "3. Escanea el QR con ZXing y obtiene el código"),
        ("app", "api", 410, "4. POST /patients/me/appointments/{id}/check-in + JWT"),
        ("api", "db", 470, "5. Valida propiedad, código, estado y ventana; actualiza checked_in_at"),
        ("db", "api", 530, "6. OK + registro en audit_log"),
        ("api", "app", 590, "7. 200 · llegada confirmada"),
        ("api", "portal", 650, "8. La sala de espera del portal refleja la llegada"),
        ("app", "app", 710, "9. La app muestra especialidad, consultorio y hora"),
    ]
    for src, dst, y, label in steps:
        if src == dst:
            x = xs[src]
            out.append(path(f"M {x + 90} {y} C {x + 155} {y - 10}, {x + 155} {y + 28}, {x + 90} {y + 35}", BLUE, 2, marker="blue"))
            out.append(text(x + 175, y + 18, label, 14, MUTED))
        else:
            out.append(line(xs[src], y, xs[dst], y, BLUE if "API" in label or "POST" in label else GREEN, 2.2, None, "blue" if "API" in label or "POST" in label else "green"))
            out.append(text((xs[src] + xs[dst]) / 2, y - 10, label, 13, MUTED, "normal", "middle"))

    # Caja de error
    out.append(rect(760, 770, 630, 110, "#FEF2F2", "#DC2626", 12, 2))
    out.append(text(785, 805, "Camino alterno", 16, "#B91C1C", "bold"))
    out.append(text(785, 833, "Código inválido, cita ya usada o fuera de ventana → 400/409, mensaje claro", 13, MUTED))
    out.append(text(785, 858, "y opción de escribir el código de respaldo sin salir de la pantalla.", 13, MUTED))

    out.append(text(75, 925, "El check-in es idempotente: repetir la llamada no duplica la llegada. La app nunca escribe datos clínicos; solo confirma la llegada.", 15, MUTED))

    save("sequence-checkin.svg", "".join(out))


if __name__ == "__main__":
    use_cases()
    navigation()
    mvvm()
    data_architecture()
    class_diagram()
    sequence()
    print("diagramas listos")
