import uuid
from typing import Optional
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

# --- Schema Base (para lectura) ---
class BackupLogBase(BaseModel):
    backup_status: Optional[str] = Field(None, description="Estado del backup (iniciado, completado, fallido)")
    backup_type: Optional[str] = Field(None, description="Tipo de backup (full, incremental)")
    duration: Optional[timedelta] = Field(None, description="Duración de la operación de backup")
    file_path: Optional[str] = Field(None, description="Ruta del archivo de backup (si aplica)")
    error_message: Optional[str] = Field(None, description="Mensaje de error (si falló)")
    notes: Optional[str] = Field(None, description="Observaciones adicionales")

# --- Schema Interno DB ---
class BackupLogInDBBase(BackupLogBase):
    id: uuid.UUID
    backup_timestamp: datetime # Timestamp de inicio/fin según la lógica de registro

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
# Devuelve la información del log de backup
class BackupLog(BackupLogInDBBase):
    pass
