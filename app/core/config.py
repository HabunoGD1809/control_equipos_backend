import json
from typing import List, Union, Any, Optional, Literal

from pydantic import field_validator, PostgresDsn, ValidationInfo, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Configuraciones de la aplicación, leídas automáticamente desde .env y el entorno.
    """
    # --- Configuración General del Proyecto ---
    PROJECT_NAME: str = "Control de Equipos API"
    API_V1_STR: str = "/api/v1"
    ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"

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
        
    # --- Configuración de Celery ---
    REPORT_EXECUTION_MODE: Literal["background", "celery"] = "background"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/0"

    # --- Configuración de Almacenamiento Local (Fallback) ---
    UPLOADS_DIRECTORY: str = "./uploads"
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # --- Configuración de Almacenamiento Cloud (S3 / MinIO) ---
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = "us-east-1"
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_ENDPOINT_URL: Optional[str] = None

    # --- Otras Configuraciones ---
    MAX_FAILED_ATTEMPTS_BEFORE_LOCK: int = 5
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_STARTTLS: bool = True
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[EmailStr] = None

    # --- Credenciales para pruebas ---
    TEST_USER_REGULAR_PASSWORD: Optional[str] = None
    TEST_ADMIN_PASSWORD: Optional[str] = None
    TEST_SUPERVISOR_PASSWORD: Optional[str] = None
    TEST_TECNICO_PASSWORD: Optional[str] = None
    TEST_AUDITOR_PASSWORD: Optional[str] = None
    TEST_TESTER_PASSWORD: Optional[str] = None

    # --- Credenciales para el Superusuario Inicial ---
    SUPERUSER_EMAIL: EmailStr
    SUPERUSER_PASSWORD: str
    SUPERUSER_USERNAME: str

    # --- Configuración moderna de Pydantic ---
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

settings = Settings() # type: ignore
