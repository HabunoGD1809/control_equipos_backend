import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator, ConfigDict

from .licencia_software import LicenciaSoftwareSimple
from .equipo import EquipoSimple
from .usuario import UsuarioSimple

# ===============================================================
# Schema Base
# ===============================================================
class AsignacionLicenciaBase(BaseModel):
    """Campos base que definen una asignación de licencia."""
    licencia_id: uuid.UUID = Field(..., description="ID de la LicenciaSoftware que se está asignando")
    equipo_id: Optional[uuid.UUID] = Field(None, description="ID del Equipo al que se asigna (si aplica)")
    usuario_id: Optional[uuid.UUID] = Field(None, description="ID del Usuario al que se asigna (si aplica)")
    instalado: bool = Field(True, description="Indica si el software asociado a la licencia ya está instalado")
    notas: Optional[str] = Field(None, description="Observaciones o comentarios sobre la asignación")

    @model_validator(mode='after')
    def check_target_exclusive(self) -> 'AsignacionLicenciaBase':
        """
        Valida que la asignación tenga exactamente un objetivo: un equipo o un usuario,
        pero no ambos ni ninguno.
        """
        if self.equipo_id and self.usuario_id:
            raise ValueError("La licencia no puede asignarse simultáneamente a un equipo y a un usuario.")
        if not self.equipo_id and not self.usuario_id:
            raise ValueError("La licencia debe asignarse a un equipo o a un usuario.")
        return self

# ===============================================================
# Schema para Creación
# ===============================================================
class AsignacionLicenciaCreate(AsignacionLicenciaBase):
    """Schema utilizado para crear una nueva asignación de licencia."""
    pass

# ===============================================================
# Schema para Actualización
# ===============================================================
class AsignacionLicenciaUpdate(BaseModel):
    """Schema para actualizar una asignación existente. Usualmente solo se modifican notas o el estado de instalación."""
    instalado: Optional[bool] = None
    notas: Optional[str] = None

# ===============================================================
# Schema Interno DB
# ===============================================================
class AsignacionLicenciaInDBBase(AsignacionLicenciaBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    fecha_asignacion: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class AsignacionLicencia(AsignacionLicenciaInDBBase):
    """
    Schema para devolver al cliente. Incluye objetos anidados para una respuesta rica.
    """
    licencia: LicenciaSoftwareSimple
    equipo: Optional[EquipoSimple] = None
    usuario: Optional[UsuarioSimple] = None
