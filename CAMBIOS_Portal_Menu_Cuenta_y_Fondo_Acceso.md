# Portal clínico: menú de cuenta, riel fijo y fondo del acceso

**Fecha:** 5 de noviembre de 2026
**Rama:** `feat/portal-menu-cuenta-riel-fijo`
**Alcance:** solo el portal web (`backend/app/portal`). No se tocaron rutas,
permisos, modelos ni migraciones; la API y la app Android no cambian.

---

## 1. Resumen

1. **Menú de cuenta (engranaje).** «Mi seguridad», «Roles», «Actividad» y
   «Cerrar sesión» salen de la navegación principal y pasan a un menú que se
   abre desde el engranaje, junto al nombre de quien tiene la sesión.
2. **Riel fijo.** El menú lateral ya no se va con el scroll: el logo y la
   navegación se desplazan por dentro, pero el bloque «En sesión» y el
   engranaje quedan siempre a la vista.
3. **Logotipo real.** La marca dibujada con CSS se sustituye por
   `LogoDOSYS.png` en el acceso y en el portal.
4. **Fondo del acceso.** El panel izquierdo del login usa la fotografía de la
   clínica al 75 % de opacidad, con un velo para mantener el contraste.
5. **Acciones de Usuarios.** Los botones de cada fila se agrupan en un menú
   «Más» para que la tabla no se desborde.
6. **Verificación.** `verify_portal.py` comprueba los dos recursos nuevos y la
   estructura del riel.

---

## 2. Archivos modificados

| Archivo | Cambio |
| --- | --- |
| `backend/app/portal/templates/panel.html` | Riel dividido en `.rail-top` (logo + navegación) y `.rail-bottom` (sesión + engranaje). Menú de cuenta con permisos. |
| `backend/app/portal/templates/login.html` | Logotipo como `<img>` en lugar de la marca CSS. |
| `backend/app/portal/templates/users.html` | Menú «Más» por fila; clases `table-users` y `content-wide`. |
| `backend/app/portal/templates/base.html` | `portal.css?v=17`, `portal.js?v=10`. |
| `backend/app/portal/static/portal.css` | Riel sticky, popover del engranaje, menú «Más», fondo del acceso y sus medios `≤920 px`. |
| `backend/app/portal/static/portal.js` | Cierre de los menús emergentes con clic fuera o `Escape`. |
| `backend/app/portal/static/img/LogoDOSYS.png` | **Nuevo** (binario). |
| `backend/app/portal/static/img/FondoLogin.jpg` | **Nuevo** (binario). |
| `backend/scripts/verify_portal.py` | Comprueba `/portal/static/img/FondoLogin.jpg` y `class="rail-top"`. |

---

## 3. Menú de cuenta (engranaje)

- `panel.html` calcula `in_gear` y `can_admin` a partir de
  `request.state.permissions`; no se añadieron permisos nuevos.
- El engranaje es un `<details data-gear>` nativo: funciona sin JavaScript.
  `portal.js` solo añade el cierre al hacer clic fuera y con `Escape`,
  devolviendo el foco al botón.
- «Cerrar sesión» sigue siendo un `POST /portal/salir` con el mismo token CSRF.
- En escritorio el panel se abre **hacia arriba** del engranaje (nunca se sale
  del viewport, verificado a 500 px y 320 px de alto). En móvil se ancla abajo.
- La navegación del riel ya no incluye Mi seguridad, Roles ni Actividad: se
  llega a ellas desde el engranaje.

## 4. Riel fijo

- `.rail` pasa a `position: sticky; top: 0; align-self: start;
  height: 100vh; height: 100dvh; box-sizing: border-box`. Se conserva
  `z-index: 20`.
- El riel **no** tiene `overflow`: así el popover del engranaje puede salir del
  riel sin recortarse. El scroll interno vive en `.rail-top`, con
  `overscroll-behavior: contain` y 6 px de margen/relleno para que el aro de
  foco no se corte.
- `.rail-bottom` es `flex: none` y tiene fondo propio (`--surface`): el pie no
  se desplaza ni se transparenta.
- El divisor pasó de `border-right` en `.rail` a `border-left` en `.main`,
  para que llegue hasta el final de la página.
- `@media (max-width: 920px)`: `.rail` vuelve a `position: static`,
  `height: auto`; `.rail-top` sin scroll y `.main` sin borde. En móvil el menú
  se comporta como antes.

## 5. Fondo del acceso

- `.login-intro` es `position: relative; isolation: isolate; overflow: hidden`.
- `::before` pinta `url("img/FondoLogin.jpg") center / cover no-repeat` con
  **`opacity: 0.75`**. El fondo base sigue siendo `var(--canvas)`.
- `::after` añade el velo de legibilidad, porque la foto tiene sillones y
  puertas oscuras justo detrás del texto (sin velo el contraste medido era
  **1.0:1**):
  - Escritorio: `rgba(243,245,243,.84)` → `.80` al 70 % → `.45` al 100 %.
  - `≤920 px`: velo vertical casi uniforme `.88 → .84`, para que el texto —que
    ocupa casi todo el ancho— no caiga sobre una zona clara.
- `.login-intro .login-caption` sube de `--ink-muted` a `--ink-soft`: ni con el
  velo llegaba a 4.5:1 (y sobre el fondo liso ya estaba en 4.2:1).
- Contraste medido sobre los píxeles reales de la foto compuestos con el velo:

| Pantalla | Título | Párrafo | Nota inferior |
| --- | --- | --- | --- |
| 1366 × 900 | 12.5:1 | 5.99:1 | 5.92:1 |
| 1200 × 760 | 12.4:1 | 5.99:1 | 5.97:1 |
| 768 × 900 | 12.5:1 | 5.97:1 | 6.49:1 |
| 400 × 850 | 12.5:1 | 5.93:1 | 5.89:1 |

- `login.html`, `two_factor.html`, `forgot.html`, `reset.html` y
  `email_reset.html` comparten `.login-intro`, así que todas reciben el fondo.
- Sin `<style>`, sin `style=""` y sin scripts en línea: la CSP estricta del
  portal sigue igual (`default-src 'self'; img-src 'self' data:;
  style-src 'self'`).

## 6. Logotipo e imágenes versionadas

El HTML y el CSS referencian dos binarios:

| Archivo | Ruta en el repo | Dimensiones | Peso | SHA-256 (prefijo) |
| --- | --- | --- | --- | --- |
| Logotipo | `backend/app/portal/static/img/LogoDOSYS.png` | 3664 × 1092 (RGBA) | 2 449 936 B (2.34 MB) | `f9fc978facc0412b` |
| Fondo | `backend/app/portal/static/img/FondoLogin.jpg` | 5707 × 3805 (RGB) | 1 787 893 B (1.71 MB) | `9c1000f8cc6ef4ef` |

Referencias exactas:

```text
backend/app/portal/templates/panel.html:11   <img ... src="/portal/static/img/LogoDOSYS.png?v=1">
backend/app/portal/templates/login.html:8    <img ... src="/portal/static/img/LogoDOSYS.png?v=1">
backend/app/portal/static/portal.css:1106    background: url("img/FondoLogin.jpg") center / cover no-repeat;
```

**Los dos PNG/JPG van dentro del commit.** Si solo se suben las plantillas y el
CSS, el VPS hace `git pull`, el HTML pide `/portal/static/img/LogoDOSYS.png`,
el archivo no existe y el menú queda con la imagen rota; lo mismo con el fondo
del acceso.

Comprobar que viajaron antes de empujar:

```bash
git ls-files backend/app/portal/static/img
# backend/app/portal/static/img/FondoLogin.jpg
# backend/app/portal/static/img/LogoDOSYS.png

git cat-file -s $(git rev-parse HEAD:backend/app/portal/static/img/LogoDOSYS.png)   # 2449936
git cat-file -s $(git rev-parse HEAD:backend/app/portal/static/img/FondoLogin.jpg)  # 1787893
```

## 7. Despliegue en el VPS

El `Dockerfile` hace `COPY app ./app`: los estáticos quedan **horneados en la
imagen** y no hay bind mount de código. Por eso `git pull` no basta y hay que
reconstruir:

```bash
cd ~/Dosys/backend          # ruta del clon en el VPS
git pull
sudo docker compose -f compose.production.yaml up -d --build
```

No hace falta `--no-cache` (el contexto cambia al cambiar `app/`, así que la
capa `COPY app ./app` se invalida sola). Tampoco hay que reiniciar PostgreSQL:
el volumen `postgres_data` no se toca.

Verificar después del despliegue:

```bash
# 1. ¿La imagen trae los archivos?
sudo docker compose -f compose.production.yaml exec api \
  ls -l /app/app/portal/static/img/LogoDOSYS.png /app/app/portal/static/img/FondoLogin.jpg

# 2. ¿El portal los sirve con el tipo correcto?
curl -sI https://<tu-dominio>/portal/static/img/LogoDOSYS.png  | head -n 3
curl -sI https://<tu-dominio>/portal/static/img/FondoLogin.jpg | head -n 3
# HTTP/... 200 + Content-Type: image/png / image/jpeg

# 3. Caché: el HTML debe pedir las versiones nuevas
curl -s https://<tu-dominio>/portal/login | grep -o 'portal\.\(css\|js\)?v=[0-9]*'
# portal.css?v=17 y portal.js?v=10
```

Notas:

- **Caché del navegador.** Al cambiar un CSS o JS hay que subir su número en
  `base.html` (`?v=17`, `?v=10`). Los logotipos llevan `?v=1`; si algún día se
  reemplaza el archivo, hay que subir ese número o el navegador seguirá con el
  anterior.
- **Peso.** El logotipo (2.34 MB) y el fondo (1.71 MB) están muy por encima de
  lo recomendado (~1600 px de ancho y <400 KB). Funcionan, pero el primer
  pintado del acceso y del menú es más lento. Si se optimizan, hay que
  reemplazar el archivo y subir su `?v=`.
- **Git LFS.** El repositorio no lo usa: los dos archivos pesan menos de 3 MB y
  entran como binarios normales. Si en el futuro crecen, conviene mover
  `backend/app/portal/static/img/` a LFS.
- **Nginx Proxy Manager** no necesita configuración extra: son archivos
  estáticos servidos por la API, no subidas de usuario.

## 8. Verificación ejecutada

- `python scripts/verify_portal.py` → terminó con su resumen final
  `{"portal": "ok", ...}`, incluida la comprobación nueva del fondo
  (`200`, `image/jpeg`) y la de `class="rail-top"` en el panel.
- Navegador real (Chrome headless por CDP), `/portal/actividad` con 5 652 px de
  página: con el scroll al final el riel sigue en 0–800 y el pie en 724–778; el
  engranaje se abre completo (531–777). Ventana de 500 px: pie en 424–478.
  Ventana de 320 px: el pie queda en 244–298 y **solo** `.rail-top` se
  desplaza (354 px de contenido en 210 visibles).
- Acceso a 1366 × 900 y 400 × 850: opacidad `0.75`, `background-image`
  apuntando a `FondoLogin.jpg`, panel cubierto en ambos tamaños.
- Consola del navegador sin errores y sin avisos de CSP; cero `style=` en las
  plantillas del portal.
- `/portal`, `/portal/roles`, `/portal/pacientes` sin desbordes horizontales a
  1366 px.

## 9. Pendientes y limitaciones conocidas

1. **`/portal/usuarios` a 1366 px desborda 30 px** (tabla de 1 107 px en un
   documento de 1 396). Es anterior a este cambio; el riel mide 248 px igual
   que antes. Queda fuera del alcance de este commit.
2. **Peso de las imágenes** (ver §7): conviene optimizarlas antes de abrir el
   portal a usuarios finales.
3. La nota del acceso usa `--ink-soft` por contraste; si se rediseña la paleta,
   revisar esa excepción.

## 10. Cómo revertir

```bash
git revert <sha-del-commit>
cd backend && sudo docker compose -f compose.production.yaml up -d --build
```

Al revertir, el fondo y el logotipo desaparecen junto con las plantillas, así
que el portal vuelve a la marca dibujada con CSS y al acceso sin fotografía.
