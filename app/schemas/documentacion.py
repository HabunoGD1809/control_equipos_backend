import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, AnyHttpUrl, model_validator

# Importar schemas relacionados para anidamiento/referencias
from .tipo_documento import TipoDocumento
from .usuario import UsuarioSimple
# Importar schemas simples de los objetos a los que se puede asociar
from .equipo import EquipoSimple
from .mantenimiento import MantenimientoSimple # Asegúrate que este schema simple exista
from .licencia_software import LicenciaSoftwareSimple # Asegúrate que este schema simple exista

ESTADOS_DOCUMENTO_VALIDOS = ['Pendiente', 'Verificado', 'Rechazado']

# --- Schema Base ---
class DocumentacionBase(BaseModel):
    titulo: str = Field(..., max_length=255, description="Título descriptivo del documento")
    descripcion: Optional[str] = Field(None, description="Descripción adicional del contenido")
    tipo_documento_id: uuid.UUID = Field(..., description="ID del Tipo de Documento")
    equipo_id: Optional[uuid.UUID] = Field(None, description="ID del Equipo asociado (opcional)")
    mantenimiento_id: Optional[uuid.UUID] = Field(None, description="ID del Mantenimiento asociado (opcional)")
    licencia_id: Optional[uuid.UUID] = Field(None, description="ID de la Licencia asociada (opcional)")

    # ===== INICIO DE LA CORRECCIÓN =====
    @model_validator(mode='after')
    def check_association(self) -> 'DocumentacionBase':
        if self.equipo_id is None and self.mantenimiento_id is None and self.licencia_id is None:
            raise ValueError("El documento debe estar asociado al menos a un Equipo, Mantenimiento o Licencia.")
        return self
    # ===== FIN DE LA CORRECCIÓN =====

# --- Schema para Creación (INTERNA) ---
class DocumentacionCreateInternal(DocumentacionBase):
    enlace: str
    nombre_archivo: Optional[str] = None
    mime_type: Optional[str] = None
    tamano_bytes: Optional[int] = None
    subido_por: Optional[uuid.UUID] = None

# --- Schema para Actualización ---
class DocumentacionUpdate(BaseModel):
    titulo: Optional[str] = Field(None, max_length=255)
    descripcion: Optional[str] = None
    tipo_documento_id: Optional[uuid.UUID] = None

# --- Schema específico para la acción de Verificar/Rechazar ---
class DocumentacionVerify(BaseModel):
    estado: str = Field(..., description=f"Nuevo estado: 'Verificado' o 'Rechazado'")
    notas_verificacion: Optional[str] = Field(None, description="Notas o motivo de la verificación/rechazo")

    @field_validator('estado')
    def estado_valido(cls, v):
        if v not in ['Verificado', 'Rechazado']:
            raise ValueError("El estado debe ser 'Verificado' o 'Rechazado'")
        return v

# --- Schema Interno DB ---
class DocumentacionInDBBase(DocumentacionBase):
    id: uuid.UUID
    enlace: str
    nombre_archivo: Optional[str]
    mime_type: Optional[str]
    tamano_bytes: Optional[int]
    fecha_subida: datetime
    subido_por: Optional[uuid.UUID]
    estado: str
    verificado_por: Optional[uuid.UUID]
    fecha_verificacion: Optional[datetime]
    notas_verificacion: Optional[str]

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API (MODIFICADO) ---
# Lo que se devuelve al usuario cuando consulta sus notificaciones
class Documentacion(DocumentacionInDBBase):
    tipo_documento: TipoDocumento
    subido_por_usuario: Optional[UsuarioSimple] = None
    verificado_por_usuario: Optional[UsuarioSimple] = None
    equipo: Optional[EquipoSimple] = None
    mantenimiento: Optional[MantenimientoSimple] = None
    licencia: Optional[LicenciaSoftwareSimple] = None

# --- Schema Simple ---
class DocumentacionSimple(BaseModel):
    id: uuid.UUID
    titulo: str
    nombre_archivo: Optional[str] = None

    model_config = {
       "from_attributes": True
    }
