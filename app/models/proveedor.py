import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo # noqa: F401
    from .tipo_item_inventario import TipoItemInventario # noqa: F401
    from .mantenimiento import Mantenimiento # noqa: F401
    from .licencia_software import LicenciaSoftware # noqa: F401


class Proveedor(Base):
    """
    Modelo ORM para la tabla 'proveedores'. 
    """
    __tablename__ = "proveedores"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contacto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sitio_web: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rnc: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relaciones mapeadas ---
    equipos_suministrados: Mapped[List["Equipo"]] = relationship(
        "Equipo",
        back_populates="proveedor",
        lazy="selectin"
    )
    items_inventario_preferidos: Mapped[List["TipoItemInventario"]] = relationship(
        "TipoItemInventario",
        back_populates="proveedor_preferido",
        lazy="selectin"
    )
    mantenimientos_realizados: Mapped[List["Mantenimiento"]] = relationship(
        "Mantenimiento",
        back_populates="proveedor_servicio",
        lazy="selectin"
    )
    licencias_adquiridas: Mapped[List["LicenciaSoftware"]] = relationship(
        "LicenciaSoftware",
        back_populates="proveedor",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Proveedor(id={self.id}, nombre='{self.nombre}')>"
