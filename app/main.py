import logging
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from contextlib import asynccontextmanager

from app.core.config import settings
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

    yield # La aplicación se ejecuta

    # Código de apagado
    logger.info("*"*50)
    logger.info(f"Deteniendo Aplicación: {settings.PROJECT_NAME}")
    logger.info("*"*50)

# --- Crear Instancia de FastAPI ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para el Sistema de Control y Gestión de Equipos Físicos, Inventario, Licencias y Reservas.",
    version="1.1.0",
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

# --- Montar directorio estático para uploads ---
uploads_path = Path(settings.UPLOADS_DIRECTORY)
uploads_path.mkdir(parents=True, exist_ok=True)
static_route_prefix = f"/static/{uploads_path.name}"
try:
    # --- 2. LÓGICA DE COMPROBACIÓN CORREGIDA ---
    # Se verifica si alguna de las rutas es una instancia de Mount y su path coincide.
    is_mounted = any(
        isinstance(route, Mount) and route.path == static_route_prefix
        for route in app.routes
    )

    if not is_mounted:
         app.mount(static_route_prefix, StaticFiles(directory=uploads_path), name="uploads")
         logger.info(f"Sirviendo archivos estáticos desde '{uploads_path}' en ruta '{static_route_prefix}'")
    else:
        logger.debug(f"Ruta estática en '{static_route_prefix}' ya parece estar montada.")
except Exception as e:
     logger.error(f"Error inesperado al montar directorio estático: {e}", exc_info=True)


# --- Incluir Routers de la API ---
app.include_router(api_router, prefix=settings.API_V1_STR)
logger.info(f"Routers de API incluidos bajo el prefijo: {settings.API_V1_STR}")

# --- Endpoint Raíz Básico ---
@app.get("/", tags=["Root"], include_in_schema=False)
def read_root() -> dict:
    return {"status": "ok", "message": f"Bienvenido a {settings.PROJECT_NAME}"}
