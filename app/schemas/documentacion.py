import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator, ConfigDict

from .enums import EstadoDocumentoEnum
from .tipo_documento import TipoDocumento
from .usuario import UsuarioSimple
from .equipo import EquipoSimple
from .mantenimiento import MantenimientoSimple
from .licencia_software import LicenciaSoftwareSimple


# --- Schema Base (SIN validador de asociación para no romper serialización) ---
class DocumentacionBase(BaseModel):
    """Campos base que definen un registro de documentación."""
    titulo: str = Field(..., max_length=255, description="Título descriptivo del documento")
    descripcion: Optional[str] = Field(None, description="Descripción adicional del contenido")
    tipo_documento_id: uuid.UUID = Field(..., description="ID del Tipo de Documento")
    equipo_id: Optional[uuid.UUID] = Field(None, description="ID del Equipo asociado (opcional)")
    mantenimiento_id: Optional[uuid.UUID] = Field(None, description="ID del Mantenimiento asociado (opcional)")
    licencia_id: Optional[uuid.UUID] = Field(None, description="ID de la Licencia asociada (opcional)")


# --- Mixin reutilizable con la validación de asociación ---
class _AssociationValidatorMixin(BaseModel):
    """
    Mixin que valida que el documento esté asociado al menos a
    un Equipo, Mantenimiento o Licencia. Solo se aplica a schemas
    de entrada (Create), nunca a schemas de respuesta/DB.
    """
    @model_validator(mode='after')
    def check_association(self) -> '_AssociationValidatorMixin':
        if (
            getattr(self, 'equipo_id', None) is None
            and getattr(self, 'mantenimiento_id', None) is None
            and getattr(self, 'licencia_id', None) is None
        ):
            raise ValueError(
                "El documento debe estar asociado al menos a un Equipo, Mantenimiento o Licencia."
            )
        return self


# --- Schema para Creación INTERNA (con validación de asociación) ---
class DocumentacionCreateInternal(_AssociationValidatorMixin, DocumentacionBase):
    """
    Schema interno usado por el servicio tras guardar el archivo.
    Incluye la validación de asociación porque es un schema de entrada.
    """
    enlace: str
    nombre_archivo: Optional[str] = None
    mime_type: Optional[str] = None
    tamano_bytes: Optional[int] = None
    subido_por: Optional[uuid.UUID] = None


# --- Schema para Actualización ---
class DocumentacionUpdate(BaseModel):
    """Schema para actualizar metadatos de un documento."""
    titulo: Optional[str] = Field(None, max_length=255)
    descripcion: Optional[str] = None
    tipo_documento_id: Optional[uuid.UUID] = None


# --- Schema específico para la acción de Verificar/Rechazar ---
class DocumentacionVerify(BaseModel):
    """Schema para verificar o rechazar un documento."""
    estado: EstadoDocumentoEnum = Field(
        ...,
        description="Nuevo estado. Solo 'Verificado' o 'Rechazado' son válidos para esta acción."
    )
    notas_verificacion: Optional[str] = Field(
        None,
        description="Notas o motivo de la verificación/rechazo"
    )

    @model_validator(mode='after')
    def estado_valido_para_accion(self) -> 'DocumentacionVerify':
        if self.estado not in [EstadoDocumentoEnum.VERIFICADO, EstadoDocumentoEnum.RECHAZADO]:
            raise ValueError("Para esta acción, el estado debe ser 'Verificado' o 'Rechazado'.")
        return self


# --- Schema Interno DB (SIN validación de asociación — solo lectura desde BD) ---
class DocumentacionInDBBase(DocumentacionBase):
    """
    Schema que refleja el modelo completo de la BD.
    No hereda el mixin de validación para no fallar al serializar
    documentos que puedan tener IDs nulos (por datos históricos, etc.).
    """
    id: uuid.UUID
    enlace: str
    nombre_archivo: Optional[str] = None
    mime_type: Optional[str] = None
    tamano_bytes: Optional[int] = None
    fecha_subida: datetime
    subido_por: Optional[uuid.UUID] = None
    estado: EstadoDocumentoEnum
    verificado_por: Optional[uuid.UUID] = None
    fecha_verificacion: Optional[datetime] = None
    notas_verificacion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Schema para Respuesta API ---
class Documentacion(DocumentacionInDBBase):
    """Schema de respuesta completo que anida información de relaciones."""
    tipo_documento: TipoDocumento
    subido_por_usuario: Optional[UsuarioSimple] = None
    verificado_por_usuario: Optional[UsuarioSimple] = None
    equipo: Optional[EquipoSimple] = None
    mantenimiento: Optional[MantenimientoSimple] = None
    licencia: Optional[LicenciaSoftwareSimple] = None


# --- Schema Simple ---
class DocumentacionSimple(BaseModel):
    """Schema simplificado para referencias en otros objetos."""
    id: uuid.UUID
    titulo: str
    nombre_archivo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
