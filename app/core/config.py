import json
from typing import List, Union, Any, Optional

from pydantic import field_validator, PostgresDsn, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Configuraciones de la aplicación, leídas automáticamente desde .env y el entorno.
    """
    # --- Configuración General del Proyecto ---
    PROJECT_NAME: str = "Control de Equipos API"
    API_V1_STR: str = "/api/v1"
    ALGORITHM: str = "HS256"

    # --- Claves y Tiempos de Expiración ---
    SECRET_KEY: str
    REFRESH_TOKEN_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    # --- Configuración de Base de Datos ---
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "control_equipos_dbv1"
    DATABASE_DRIVER: str = "psycopg"
    DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URI", mode='before')
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str):
            return v
        return str(PostgresDsn.build(
            scheme=f"postgresql+{info.data.get('DATABASE_DRIVER')}",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_SERVER"),
            port=info.data.get("POSTGRES_PORT"),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        ))

    # --- Configuración de CORS ---
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        elif isinstance(v, str):
            return json.loads(v)
        return v

    # --- Configuración de Almacenamiento ---
    UPLOADS_DIRECTORY: str = "./uploads"
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # --- Otras Configuraciones ---
    MAX_FAILED_ATTEMPTS_BEFORE_LOCK: int = 5

    # --- Credenciales para pruebas ---
    TEST_USER_REGULAR_PASSWORD: str
    TEST_ADMIN_PASSWORD: str
    TEST_SUPERVISOR_PASSWORD: str
    TEST_TECNICO_PASSWORD: str
    TEST_AUDITOR_PASSWORD: str
    TEST_TESTER_PASSWORD: str

    # --- Credenciales para el Superusuario Inicial ---
    SUPERUSER_EMAIL: str
    SUPERUSER_PASSWORD: str

    # --- Configuración moderna de Pydantic ---
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings() # type: ignore
