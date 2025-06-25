import uuid
from typing import Any, Optional, List
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

# Importar schemas relacionados
from .software_catalogo import SoftwareCatalogoSimple
from .proveedor import ProveedorSimple
# Importar schema simple de Asignacion si se necesita anidar info básica
# from .asignacion_licencia import AsignacionLicenciaSimple

# --- Schema Base ---
class LicenciaSoftwareBase(BaseModel):
    software_catalogo_id: uuid.UUID = Field(..., description="ID del Software del catálogo asociado")
    clave_producto: Optional[str] = Field(None, description="Clave de activación/producto (si aplica)")
    fecha_adquisicion: date = Field(..., description="Fecha de compra de la licencia")
    fecha_expiracion: Optional[date] = Field(None, description="Fecha de expiración (para suscripciones)")
    proveedor_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor donde se adquirió")
    costo_adquisicion: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Costo de la licencia")
    numero_orden_compra: Optional[str] = Field(None, max_length=100, description="Nº de Orden de Compra asociada")
    cantidad_total: int = Field(default=1, gt=0, description="Número total de activaciones/usuarios cubiertos por esta licencia (>0)")
    # cantidad_disponible no se incluye aquí, se calcula/gestiona internamente
    notas: Optional[str] = Field(None, description="Observaciones sobre la licencia")

    @model_validator(mode='after')
    def check_fechas_logicas(self) -> 'LicenciaSoftwareBase':
        # 'self' aquí es la instancia del modelo validado
        adquisicion = self.fecha_adquisicion
        expiracion = self.fecha_expiracion
        if adquisicion and expiracion and expiracion <= adquisicion:
            raise ValueError("La fecha de expiración debe ser posterior a la fecha de adquisición")
        return self

# --- Schema para Creación ---
class LicenciaSoftwareCreate(LicenciaSoftwareBase):
    cantidad_disponible: Optional[int] = Field(None, description="Cantidad disponible inicial (opcional, por defecto igual a cantidad_total)")

    # Usamos 'before' para modificar los datos *antes* de la validación principal del modelo
    @model_validator(mode='before')
    @classmethod
    def set_default_disponible(cls, data: Any) -> Any:
        if isinstance(data, dict): # Asegurar que es un diccionario
             # Si cantidad_disponible no viene o es None, la igualamos a cantidad_total
            if data.get("cantidad_disponible") is None:
                data["cantidad_disponible"] = data.get("cantidad_total", 1)
            # Validar que disponible no sea mayor que total o negativo
            total = data.get("cantidad_total", 1)
            disponible = data.get("cantidad_disponible", total) # Usar total si aún es None
            if disponible > total:
                raise ValueError("La cantidad disponible no puede ser mayor que la cantidad total")
            if disponible < 0:
                 raise ValueError("La cantidad disponible no puede ser negativa")
        return data
    # --- FIN CORRECCIÓN ---


# --- Schema para Actualización ---
class LicenciaSoftwareUpdate(BaseModel):
    clave_producto: Optional[str] = None
    fecha_adquisicion: Optional[date] = None
    fecha_expiracion: Optional[date] = None
    proveedor_id: Optional[uuid.UUID] = None
    costo_adquisicion: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    numero_orden_compra: Optional[str] = Field(None, max_length=100)
    notas: Optional[str] = None
    # Quitamos validación de fechas aquí, es mejor en el servicio para updates parciales

# --- Schema Interno DB ---
class LicenciaSoftwareInDBBase(LicenciaSoftwareBase):
    id: uuid.UUID
    cantidad_disponible: int # Incluir el campo real de la DB
    created_at: datetime
    updated_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class LicenciaSoftware(LicenciaSoftwareInDBBase):
    software_info: SoftwareCatalogoSimple
    proveedor: Optional[ProveedorSimple] = None

# --- Schema Simple ---
class LicenciaSoftwareSimple(BaseModel):
    id: uuid.UUID
    software_nombre: Optional[str] = Field(None, validation_alias='software_info__nombre')
    software_version: Optional[str] = Field(None, validation_alias='software_info__version')
    clave_producto: Optional[str] = None
    fecha_expiracion: Optional[date] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True, # Necesario para que funcione validation_alias
    }
