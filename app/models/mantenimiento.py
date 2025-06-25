import uuid
from typing import TYPE_CHECKING, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR

from sqlalchemy.orm import relationship, Mapped, mapped_column
# from sqlalchemy.types import Text as TextType

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo
    from .tipo_mantenimiento import TipoMantenimiento
    from .proveedor import Proveedor
    from .documentacion import Documentacion
    from .inventario_movimiento import InventarioMovimiento


class Mantenimiento(Base):
    """
    Modelo ORM para la tabla 'mantenimiento'.
    """
    __tablename__ = "mantenimiento"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), index=True)
    tipo_mantenimiento_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tipos_mantenimiento.id", ondelete="RESTRICT"), index=True)
    fecha_programada: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fecha_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fecha_finalizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fecha_proximo_mantenimiento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    costo_estimado: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    costo_real: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    tecnico_responsable: Mapped[str] = mapped_column(Text) # Usar Text de SQLAlchemy directamente
    proveedor_servicio_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    estado: Mapped[str] = mapped_column(String(50), default='Programado', index=True)
    prioridad: Mapped[int] = mapped_column(Integer, default=0, index=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Usar Text de SQLAlchemy
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- CORRECCIÓN: Mapear texto_busqueda como TSVECTOR y indicar que es manejado por DB ---
    # Usar deferred=True para que no se cargue por defecto, y nullable=True
    texto_busqueda: Mapped[Optional[Any]] = mapped_column(TSVECTOR, nullable=True, deferred=True)
    # Nota: El tipo Any se usa porque la representación directa de TSVECTOR puede variar.
    # No se incluirá en schemas de entrada/actualización.
    # --------------------------------------------------------------------------------------

    equipo: Mapped["Equipo"] = relationship(
        "Equipo",
        back_populates="mantenimientos",
        lazy="selectin"
    )
    tipo_mantenimiento: Mapped["TipoMantenimiento"] = relationship(
        "TipoMantenimiento",
        back_populates="mantenimientos",
        lazy="joined"
    )
    proveedor_servicio: Mapped[Optional["Proveedor"]] = relationship(
        "Proveedor",
        back_populates="mantenimientos_realizados",
        lazy="selectin"
    )
    documentos: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        foreign_keys="Documentacion.mantenimiento_id",
        back_populates="mantenimiento",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    items_usados: Mapped[List["InventarioMovimiento"]] = relationship(
        "InventarioMovimiento",
        back_populates="mantenimiento_asociado",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Mantenimiento(id={self.id}, equipo_id={self.equipo_id}, tipo_id={self.tipo_mantenimiento_id})>"
