import os
import json
from typing import List, Union, Optional, Dict, Any
from pydantic import AnyHttpUrl, field_validator, PostgresDsn, ValidationInfo
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """
    Configuraciones de la aplicación, leídas desde variables de entorno.
    """
    # --- Configuración General del Proyecto ---
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Control de Equipos API")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    SECRET_KEY: str = str(os.getenv("SECRET_KEY"))
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_SECRET_KEY: str = str(os.getenv("REFRESH_TOKEN_SECRET_KEY"))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))
    
    # --- Configuración de Base de Datos ---
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5433")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "control_equipos_dbv1")

    # Configuración de la conexión a la base de datos
    DATABASE_URI: Optional[PostgresDsn] = None
    DATABASE_DRIVER: str = os.getenv("DATABASE_DRIVER", "psycopg")

    @field_validator("DATABASE_URI", mode='before')
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v
        
        driver = info.data.get("DATABASE_DRIVER", "psycopg")
        scheme = f"postgresql+{driver}"

        return PostgresDsn.build(
            scheme=scheme,
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_SERVER"),
            port=int(info.data.get("POSTGRES_PORT", 5433)),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    # --- Configuración de CORS ---
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and v:
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    # --- Configuración de Celery ---
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # --- Configuración de Almacenamiento ---
    UPLOADS_DIRECTORY: str = os.getenv("UPLOADS_DIRECTORY", "./uploads")
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024)) # 10 MB
    
    # --- Otras Configuraciones ---
    MAX_FAILED_ATTEMPTS_BEFORE_LOCK: int = int(os.getenv("MAX_FAILED_ATTEMPTS_BEFORE_LOCK", "5"))
    
    # --- Credenciales para pruebas ---
    TEST_USER_REGULAR_PASSWORD: str = str(os.getenv("TEST_USER_REGULAR_PASSWORD"))
    TEST_ADMIN_PASSWORD: str = str(os.getenv("TEST_ADMIN_PASSWORD"))
    TEST_SUPERVISOR_PASSWORD: str = str(os.getenv("TEST_SUPERVISOR_PASSWORD"))
    TEST_TECNICO_PASSWORD: str = str(os.getenv("TEST_TECNICO_PASSWORD"))
    TEST_AUDITOR_PASSWORD: str = str(os.getenv("TEST_AUDITOR_PASSWORD"))
    TEST_TESTER_PASSWORD: str = str(os.getenv("TEST_TESTER_PASSWORD"))
    
    # --- Credenciales para el Superusuario Inicial ---
    SUPERUSER_EMAIL: str = str(os.getenv("SUPERUSER_EMAIL"))
    SUPERUSER_PASSWORD: str = str(os.getenv("SUPERUSER_PASSWORD"))
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
