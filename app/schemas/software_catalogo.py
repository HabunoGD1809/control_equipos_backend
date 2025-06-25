import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Listas de valores válidos (deben coincidir con CHECKs DB)
TIPOS_LICENCIA_VALIDOS = [
    'Perpetua', 'Suscripción Anual', 'Suscripción Mensual',
    'OEM', 'Freeware', 'Open Source', 'Otra'
]
METRICAS_LICENCIAMIENTO_VALIDAS = [
    'Por Dispositivo', 'Por Usuario Nominal', 'Por Usuario Concurrente',
    'Por Core', 'Por Servidor', 'Gratuita', 'Otra'
]

# --- Schema Base ---
class SoftwareCatalogoBase(BaseModel):
    nombre: str = Field(..., max_length=255, description="Nombre del producto de software")
    version: Optional[str] = Field(None, max_length=50, description="Versión específica (ej: 2023, 11, CC)")
    fabricante: Optional[str] = Field(None, max_length=100, description="Fabricante del software")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del software")
    categoria: Optional[str] = Field(None, max_length=100, description="Categoría (ej: Ofimática, Diseño, SO)")
    tipo_licencia: str = Field(..., description=f"Tipo de licencia. Válidos: {TIPOS_LICENCIA_VALIDOS}")
    metrica_licenciamiento: str = Field(..., description=f"Métrica de licenciamiento. Válidas: {METRICAS_LICENCIAMIENTO_VALIDAS}")

    # Validadores opcionales para asegurar valores correctos
    @field_validator('tipo_licencia')
    def tipo_licencia_valido(cls, v):
        if v not in TIPOS_LICENCIA_VALIDOS:
            raise ValueError(f"Tipo de licencia inválido. Válidos: {TIPOS_LICENCIA_VALIDOS}")
        return v

    @field_validator('metrica_licenciamiento')
    def metrica_valida(cls, v):
        if v not in METRICAS_LICENCIAMIENTO_VALIDAS:
            raise ValueError(f"Métrica de licenciamiento inválida. Válidas: {METRICAS_LICENCIAMIENTO_VALIDAS}")
        return v

# --- Schema para Creación ---
class SoftwareCatalogoCreate(SoftwareCatalogoBase):
    pass # Coincide con la base

# --- Schema para Actualización ---
class SoftwareCatalogoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=255)
    version: Optional[str] = Field(None, max_length=50)
    fabricante: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    categoria: Optional[str] = Field(None, max_length=100)
    tipo_licencia: Optional[str] = Field(None, description=f"Nuevo Tipo. Válidos: {TIPOS_LICENCIA_VALIDOS}")
    metrica_licenciamiento: Optional[str] = Field(None, description=f"Nueva Métrica. Válidas: {METRICAS_LICENCIAMIENTO_VALIDAS}")

    # Validadores opcionales para actualización
    @field_validator('tipo_licencia', mode='before')
    def check_tipo_licencia_opcional(cls, v):
        if v is not None and v not in TIPOS_LICENCIA_VALIDOS:
            raise ValueError(f"Tipo de licencia inválido. Válidos: {TIPOS_LICENCIA_VALIDOS}")
        return v

    @field_validator('metrica_licenciamiento', mode='before')
    def check_metrica_opcional(cls, v):
        if v is not None and v not in METRICAS_LICENCIAMIENTO_VALIDAS:
            raise ValueError(f"Métrica de licenciamiento inválida. Válidas: {METRICAS_LICENCIAMIENTO_VALIDAS}")
        return v

# --- Schema Interno DB ---
class SoftwareCatalogoInDBBase(SoftwareCatalogoBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class SoftwareCatalogo(SoftwareCatalogoInDBBase):
    # Devuelve todos los campos por defecto
    pass

# --- Schema Simple ---
class SoftwareCatalogoSimple(BaseModel):
    id: uuid.UUID
    nombre: str
    version: Optional[str] = None
    fabricante: Optional[str] = None

    model_config = {
       "from_attributes": True
    }
