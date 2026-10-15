from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Empresa(Base):
    __tablename__ = "configuracion_empresa"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    nombre: Mapped[str] = mapped_column(String(150), default="ControlEquipos")
    identificacion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
