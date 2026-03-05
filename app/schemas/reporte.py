from typing import Literal
from datetime import date
from pydantic import BaseModel, Field

class ReporteRequest(BaseModel):
    tipo_reporte: Literal["equipos", "mantenimientos", "kardex", "movimientos", "auditoria"] = Field(
        ..., 
        description="Módulo a exportar según el frontend"
    )
    formato: Literal["csv", "pdf", "excel"] = Field(...)
    fecha_inicio: date = Field(...)
    fecha_fin: date = Field(...)
