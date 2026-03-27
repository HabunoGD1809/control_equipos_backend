import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo
    from .software_catalogo import SoftwareCatalogo
    from .tipo_item_inventario import TipoItemInventario


class Marca(Base):
    """Modelo ORM para el catálogo de Marcas y Fabricantes."""
    __tablename__ = "marcas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    equipos: Mapped[List["Equipo"]] = relationship("Equipo", back_populates="marca_rel", lazy="selectin")
    software: Mapped[List["SoftwareCatalogo"]] = relationship("SoftwareCatalogo", back_populates="marca_rel", lazy="selectin")
    items_inventario: Mapped[List["TipoItemInventario"]] = relationship("TipoItemInventario", back_populates="marca_rel", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Marca(id={self.id}, nombre='{self.nombre}')>"
