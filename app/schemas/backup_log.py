import uuid
from typing import Optional
from datetime import datetime, timedelta

from pydantic import BaseModel, Field, ConfigDict

# ===============================================================
# Schema Base
# ===============================================================
class BackupLogBase(BaseModel):
    """Campos base que definen un registro de log de backup."""
    backup_status: Optional[str] = Field(None, description="Estado del backup (iniciado, completado, fallido)")
    backup_type: Optional[str] = Field(None, description="Tipo de backup realizado (ej: full, incremental, BBDD)")
    duration: Optional[timedelta] = Field(None, description="Duración total de la operación de backup")
    file_path: Optional[str] = Field(None, description="Ruta del archivo de backup generado (si aplica)")
    error_message: Optional[str] = Field(None, description="Mensaje de error detallado en caso de fallo")
    notes: Optional[str] = Field(None, description="Observaciones o comentarios adicionales sobre el proceso")

# ===============================================================
# Schema Interno DB
# ===============================================================
class BackupLogInDBBase(BackupLogBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    backup_timestamp: datetime = Field(..., description="Timestamp de cuando se registró el evento de log")

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class BackupLog(BackupLogInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass
