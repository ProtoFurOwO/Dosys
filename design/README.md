# D.O.S.Y.S · Documento de diseño (E1–E4)

Este directorio contiene el documento de diseño de la app Android y el prototipo navegable que lo acompaña.

## Entregables

| Archivo | Qué es |
|---|---|
| `UNACH_Diseño_Equipo5.pdf` | Documento de diseño E1–E4 (41 páginas, Carta, Arial 11 pt, márgenes 2.5 cm). |
| `prototipo/Prototipo_DOSYS.html` | Prototipo navegable autocontenido; se abre en cualquier navegador sin internet. |
| `index.html` | Fuente HTML del documento (CSS y secciones en `src/`). |
| `Tablero_Mockups_DOSYS.png` | Tablero con las 5 pantallas principales para compartir o imprimir. |

## Cómo se regenera

```powershell
cd android/design
py -3.12 make_diagrams.py      # diagramas SVG (casos de uso, navegación, MVVM, stack, clases, secuencia)
py -3.12 make_wireframes.py    # wireframes de baja fidelidad (PNG)
py -3.12 make_prototype.py     # prototipo HTML autocontenido
py -3.12 build_doc.py          # documento PDF + índice + encabezados/pies
```

Requiere Python 3.12, Pillow, pypdf, reportlab y qrcode; Edge/Chromium para exportar el PDF.

## Estructura

```
design/
├─ assets/
│  ├─ app/           capturas reales del prototipo
│  ├─ brand/         escudo UNACH y QR del prototipo
│  ├─ diagrams/      SVG de los diagramas
│  ├─ logos/         logos de Simple Icons (CC0)
│  └─ wireframes/    wireframes en PNG
├─ prototipo/        Prototipo_DOSYS.html
├─ src/              secciones HTML + style.css
├─ make_*.py         generadores
├─ build_doc.py      ensamblado y exportación
└─ UNACH_Diseño_Equipo5.pdf
```

## Enlaces

- Repositorio: <https://github.com/ProtoFurOwO/Dosys>
- Prototipo en línea: <https://raw.githack.com/ProtoFurOwO/Dosys/master/design/prototipo/Prototipo_DOSYS.html>
- Sistema en vivo: <https://medicos.stolasimp.dev>

> Las capturas y datos son ficticios de demostración académica. No contienen información clínica real.
