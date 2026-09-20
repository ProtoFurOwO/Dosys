from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal, engine
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
