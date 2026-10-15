from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmpresaUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    nombre: str = Field(min_length=1, max_length=150)
    identificacion: Optional[str] = Field(default=None, max_length=50)
    direccion: Optional[str] = Field(default=None, max_length=500)
    telefono: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = Field(default=None, max_length=254)


class EmpresaRead(EmpresaUpdate):
    logo_url: Optional[str] = None
    updated_at: Optional[datetime] = None


class EmpresaPublica(BaseModel):
    nombre: str
    logo_url: Optional[str] = None
