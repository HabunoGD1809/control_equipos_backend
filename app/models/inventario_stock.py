import uuid
from typing import TYPE_CHECKING, Optional
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Date, Numeric,
    UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .tipo_item_inventario import TipoItemInventario


class InventarioStock(Base):
    """
    Modelo ORM para la tabla 'inventario_stock'. 
    """
    __tablename__ = "inventario_stock"
    __table_args__ = (
        UniqueConstraint('tipo_item_id', 'ubicacion', 'lote', name='uq_item_ubicacion_lote'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tipos_item_inventario.id", ondelete="CASCADE"), index=True)
    ubicacion: Mapped[str] = mapped_column(String(255), default='Almacén Principal', index=True)
    lote: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    fecha_caducidad: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    cantidad_actual: Mapped[int] = mapped_column(Integer, default=0)
    costo_promedio_ponderado: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    ultima_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tipo_item: Mapped["TipoItemInventario"] = relationship(
        "TipoItemInventario",
        back_populates="stock_ubicaciones",
        lazy="joined"
    )

    def __repr__(self) -> str:
        lote_str = f", lote='{self.lote}'" if self.lote else ""
        return f"<InventarioStock(item_id={self.tipo_item_id}, ubicacion='{self.ubicacion}'{lote_str}, cantidad={self.cantidad_actual})>"
