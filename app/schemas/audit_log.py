import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field

# Importar schema simple de Usuario
from .usuario import UsuarioSimple

# --- Schema Base (para lectura) ---
class AuditLogBase(BaseModel):
    table_name: str = Field(..., description="Nombre de la tabla afectada")
    operation: str = Field(..., description="Operación realizada (INSERT, UPDATE, DELETE)")
    old_data: Optional[Dict[str, Any]] = Field(None, description="Valores anteriores (para UPDATE/DELETE)")
    new_data: Optional[Dict[str, Any]] = Field(None, description="Valores nuevos (para INSERT/UPDATE)")
    username: Optional[str] = Field(None, description="Usuario de la base de datos que ejecutó la acción")
    app_user_id: Optional[uuid.UUID] = Field(None, description="ID del usuario de la aplicación que inició la acción (si se registró)")

# --- Schema Interno DB ---
class AuditLogInDBBase(AuditLogBase):
    # La PK compuesta (ts, id) no se mapea directamente como un solo campo
    audit_timestamp: datetime
    id: uuid.UUID

    model_config = {
        "from_attributes": True
    }

# --- Schema para Respuesta API ---
# Devuelve la información del log de auditoría
class AuditLog(AuditLogInDBBase):
    # Opcionalmente, podríamos añadir lógica en el servicio para buscar y anidar
    # el UsuarioSimple basado en app_user_id, pero por ahora solo devolvemos el ID.
    # app_usuario: Optional[UsuarioSimple] = None
    pass
