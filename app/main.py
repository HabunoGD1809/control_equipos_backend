import logging
from pathlib import Path
import os
import asyncio
from contextlib import suppress
from app.core.maintenance import maintenance_loop

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.event_broker import broker
from app.api.routes import api_router
from app.core.logging_config import setup_logging
from app.core.error_handlers import register_error_handlers

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código de inicio
    logger.info("*"*50)
    logger.info(f"Iniciando Aplicación: {settings.PROJECT_NAME}")
    logger.info("*"*50)

    # --- Añadir logs para URLs de documentación ---
    PORT = os.getenv("PORT", "8086")
    BASE_URL = f"http://127.0.0.1:{PORT}"
    DOCS_URL = f"{BASE_URL}{settings.API_V1_STR}/docs"
    REDOC_URL = f"{BASE_URL}{settings.API_V1_STR}/redoc"

    logger.info(f"API Docs (Swagger UI): {DOCS_URL}")
    logger.info(f"API Docs (ReDoc):      {REDOC_URL}")
    logger.info("*"*50)
    # --- Fin de logs añadidos ---

    await broker.start()
    maintenance = asyncio.create_task(maintenance_loop()) if settings.REPORT_EXECUTION_MODE == "background" else None
    try:
        yield
    finally:
        if maintenance:
            maintenance.cancel()
            with suppress(asyncio.CancelledError):
                await maintenance
        await broker.stop()

    # Código de apagado
    logger.info("*"*50)
    logger.info(f"Deteniendo Aplicación: {settings.PROJECT_NAME}")
    logger.info("*"*50)

# --- Crear Instancia de FastAPI ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para el Sistema de Control y Gestión de Equipos Físicos, Inventario, Licencias y Reservas.",
    version="1.3.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# --- Configurar CORS ---
if settings.BACKEND_CORS_ORIGINS:
    logger.info(f"Configurando CORS para los orígenes: {settings.BACKEND_CORS_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("CORS no configurado (BACKEND_CORS_ORIGINS no definido en .env)")

# --- Registrar Manejadores de Errores ---
register_error_handlers(app)

# Las fotos de perfil se sirven por la ruta autenticada /usuarios/avatar/{filename}.

# --- Incluir Routers de la API ---
app.include_router(api_router, prefix=settings.API_V1_STR)
logger.info(f"Routers de API incluidos bajo el prefijo: {settings.API_V1_STR}")

# --- Endpoint Raíz Básico ---
@app.get("/", tags=["Root"], include_in_schema=False)
def read_root() -> dict:
    return {"status": "ok", "message": f"Bienvenido a {settings.PROJECT_NAME}"}

@app.get("/health", include_in_schema=False)
def health():
    from fastapi.responses import JSONResponse
    from app.db.session import SessionLocal
    from sqlalchemy import text
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            actual_database = db.scalar(text("SELECT current_database()"))
        payload = {"status": "ok"}
        if "_test" in actual_database:
            payload["test_database"] = actual_database
        return payload
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
