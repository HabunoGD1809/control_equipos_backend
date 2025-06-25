import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Boolean
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.db.base import Base

if TYPE_CHECKING:
    from .proveedor import Proveedor
    from .inventario_stock import InventarioStock
    from .inventario_movimiento import InventarioMovimiento


class TipoItemInventario(Base):
    """
    Modelo ORM para la tabla 'tipos_item_inventario'. 
    """
    __tablename__ = "tipos_item_inventario"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categoria: Mapped[str] = mapped_column(String(50), index=True)
    unidad_medida: Mapped[str] = mapped_column(String(50), default='Unidad')
    marca: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    modelo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    codigo_barras: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    modelos_equipo_compatibles: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    proveedor_preferido_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    stock_minimo: Mapped[int] = mapped_column(Integer, default=0)
    perecedero: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    proveedor_preferido: Mapped[Optional["Proveedor"]] = relationship(
        "Proveedor",
        back_populates="items_inventario_preferidos",
        lazy="selectin"
    )
    stock_ubicaciones: Mapped[List["InventarioStock"]] = relationship(
        "InventarioStock",
        back_populates="tipo_item",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    movimientos_inventario: Mapped[List["InventarioMovimiento"]] = relationship(
        "InventarioMovimiento",
        back_populates="tipo_item",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TipoItemInventario(id={self.id}, nombre='{self.nombre}')>"
