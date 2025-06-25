import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Numeric
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .tipo_item_inventario import TipoItemInventario
    from .equipo import Equipo
    from .mantenimiento import Mantenimiento
    from .usuario import Usuario


class InventarioMovimiento(Base):
    """
    Modelo ORM para la tabla 'inventario_movimientos'. 
    """
    __tablename__ = "inventario_movimientos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tipos_item_inventario.id", ondelete="RESTRICT"), index=True)
    tipo_movimiento: Mapped[str] = mapped_column(String(50), index=True)
    cantidad: Mapped[int] = mapped_column(Integer)
    ubicacion_origen: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    ubicacion_destino: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    lote_origen: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    lote_destino: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    equipo_asociado_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="SET NULL"), nullable=True, index=True)
    mantenimiento_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("mantenimiento.id", ondelete="SET NULL"), nullable=True, index=True)
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    costo_unitario: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    motivo_ajuste: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referencia_externa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referencia_transferencia: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tipo_item: Mapped["TipoItemInventario"] = relationship(
        "TipoItemInventario",
        back_populates="movimientos_inventario",
        lazy="joined"
    )
    equipo_asociado: Mapped[Optional["Equipo"]] = relationship(
        "Equipo",
        back_populates="movimientos_inventario_asociados",
        lazy="selectin"
    )
    mantenimiento_asociado: Mapped[Optional["Mantenimiento"]] = relationship(
        "Mantenimiento",
        back_populates="items_usados",
        lazy="selectin"
    )
    usuario_registrador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[usuario_id], # Especificar aquí si hay ambigüedad
        back_populates="movimientos_inventario_registrados",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<InventarioMovimiento(id={self.id}, tipo='{self.tipo_movimiento}', item_id={self.tipo_item_id}, cantidad={self.cantidad})>"
