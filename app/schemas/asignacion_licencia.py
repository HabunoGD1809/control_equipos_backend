import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

# Importar schemas simples para referencias
from .licencia_software import LicenciaSoftwareSimple
from .equipo import EquipoSimple
from .usuario import UsuarioSimple

# --- Schema Base ---
class AsignacionLicenciaBase(BaseModel):
    licencia_id: uuid.UUID = Field(..., description="ID de la LicenciaSoftware a asignar")
    equipo_id: Optional[uuid.UUID] = Field(None, description="ID del Equipo al que se asigna (si aplica)")
    usuario_id: Optional[uuid.UUID] = Field(None, description="ID del Usuario al que se asigna (si aplica)")
    instalado: bool = Field(True, description="Indica si el software asociado está instalado")
    notas: Optional[str] = Field(None, description="Observaciones sobre la asignación")

    @model_validator(mode='after')
    def check_target_exclusive(self) -> 'AsignacionLicenciaBase':
        # 'self' es la instancia del modelo validado
        equipo_id = self.equipo_id
        usuario_id = self.usuario_id

        if equipo_id is not None and usuario_id is not None:
            raise ValueError("La licencia no puede asignarse simultáneamente a un equipo y a un usuario.")
        if equipo_id is None and usuario_id is None:
             raise ValueError("La licencia debe asignarse a un equipo o a un usuario.")
        return self

# --- Schema para Creación ---
class AsignacionLicenciaCreate(AsignacionLicenciaBase):
    pass

# --- Schema para Actualización ---
class AsignacionLicenciaUpdate(BaseModel):
    instalado: Optional[bool] = None
    notas: Optional[str] = None

# --- Schema Interno DB ---
class AsignacionLicenciaInDBBase(AsignacionLicenciaBase):
    id: uuid.UUID
    fecha_asignacion: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class AsignacionLicencia(AsignacionLicenciaInDBBase):
    licencia: LicenciaSoftwareSimple
    equipo: Optional[EquipoSimple] = None
    usuario: Optional[UsuarioSimple] = None
