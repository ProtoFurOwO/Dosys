from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.portal.routes import router as portal_router
from app.schemas.health import HealthResponse
from app.services.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Las migraciones se ejecutan antes, desde Docker Compose. Luego sembramos
    # datos ficticios solo para que la demo sea funcional desde el primer arranque.
    await seed_demo_data()
    yield
    await engine.dispose()


app = FastAPI(
    title="D.O.S.Y.S API",
    description=(
        "API del sistema hospitalario académico D.O.S.Y.S. "
        "Contiene solamente datos ficticios de demostración."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(portal_router)
app.mount(
    "/portal/static",
    StaticFiles(directory=str(Path(__file__).parent / "portal" / "static")),
    name="portal-static",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Cabeceras mínimas de seguridad para el HTML del personal médico."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.url.path.startswith("/portal"):
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; form-action 'self'; frame-ancestors 'none'",
        )
    return response


@app.get("/health", response_model=HealthResponse, tags=["Infraestructura"])
async def health_check() -> HealthResponse:
    """Comprueba que la API y PostgreSQL estén disponibles."""
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        # No exponer la configuración de base de datos al cliente.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible",
        ) from exc
    return HealthResponse(status="ok", database="ok")
