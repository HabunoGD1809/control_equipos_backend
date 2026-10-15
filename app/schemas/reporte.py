from typing import Literal, Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, model_validator

class ReporteRequest(BaseModel):
    tipo_reporte: Literal["equipos", "mantenimientos", "kardex", "movimientos", "auditoria", "inventario", "licencias"] = Field(
        ..., 
        description="Módulo a exportar según el frontend"
    )
    formato: Literal["csv", "pdf", "excel"] = Field(...)
    fecha_inicio: date = Field(...)
    fecha_fin: date = Field(...)

    @model_validator(mode="after")
    def validate_period(self):
        if self.fecha_inicio > self.fecha_fin:
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
        return self

class ReporteResponse(BaseModel):
    id: UUID
    tipo_reporte: str
    formato: str
    parametros: Optional[Dict[str, Any]] = None
    estado: str
    archivo_size_bytes: Optional[int] = None
    error_msg: Optional[str] = None
    fecha_solicitud: datetime
    fecha_completado: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
