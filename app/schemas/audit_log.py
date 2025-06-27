import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

# from .usuario import UsuarioSimple

# ===============================================================
# Schema Base
# ===============================================================
class AuditLogBase(BaseModel):
    """Campos base que definen un registro de auditoría."""
    table_name: str = Field(..., description="Nombre de la tabla que fue afectada por la operación")
    operation: str = Field(..., description="Operación realizada (INSERT, UPDATE, DELETE)")
    old_data: Optional[Dict[str, Any]] = Field(None, description="Valores del registro antes del cambio (para UPDATE y DELETE)")
    new_data: Optional[Dict[str, Any]] = Field(None, description="Valores del registro después del cambio (para INSERT y UPDATE)")
    username: Optional[str] = Field(None, description="Usuario de la base de datos que ejecutó la acción")
    app_user_id: Optional[uuid.UUID] = Field(None, description="ID del usuario de la aplicación que inició la acción (si se pudo registrar)")

# ===============================================================
# Schema Interno DB
# ===============================================================
class AuditLogInDBBase(AuditLogBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    audit_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class AuditLog(AuditLogInDBBase):
    """
    Schema para devolver al cliente. Expone todos los campos del log.
    Opcionalmente, podría anidar la información del usuario si se implementa en el servicio.
    """
    # app_usuario: Optional[UsuarioSimple] = None
    pass
