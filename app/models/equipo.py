import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Date, Numeric, Index
)
# Importar TSVECTOR si decides mapearlo explícitamente
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship, Mapped, mapped_column, column_property
from sqlalchemy.types import Text as TextType

from app.db.base import Base
if TYPE_CHECKING:
    from .estado_equipo import EstadoEquipo
    from .proveedor import Proveedor
    from .movimiento import Movimiento
    from .documentacion import Documentacion
    from .mantenimiento import Mantenimiento
    from .equipo_componente import EquipoComponente
    from .asignacion_licencia import AsignacionLicencia
    from .reserva_equipo import ReservaEquipo
    from .inventario_movimiento import InventarioMovimiento


class Equipo(Base):
    """
    Modelo ORM para la tabla 'equipos'. (Actualizado para SQLAlchemy 2.0 Mapped)
    """
    __tablename__ = "equipos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255), index=True)
    numero_serie: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    codigo_interno: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    estado_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("estados_equipo.id"), index=True)
    ubicacion_actual: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marca: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    modelo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    fecha_adquisicion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_puesta_marcha: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_garantia_expiracion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valor_adquisicion: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    proveedor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    centro_costo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- texto_busqueda: Gestionado por trigger en DB, no mapear directamente para escritura ---
    # Opción 1: Quitar el Mapped completamente si no lo lees/usas en la app.
    # Opción 2: Mapearlo con tipo correcto pero gestionarlo diferente (más complejo).
    texto_busqueda = column_property(Column(TSVECTOR)) # Mapeo solo lectura con tipo correcto


    estado: Mapped["EstadoEquipo"] = relationship("EstadoEquipo", back_populates="equipos", lazy="selectin")
    proveedor: Mapped[Optional["Proveedor"]] = relationship("Proveedor", back_populates="equipos_suministrados", lazy="selectin")
    movimientos: Mapped[List["Movimiento"]] = relationship(
        "Movimiento",
        back_populates="equipo",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    documentos: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        foreign_keys="Documentacion.equipo_id",
        back_populates="equipo",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    mantenimientos: Mapped[List["Mantenimiento"]] = relationship(
        "Mantenimiento",
        back_populates="equipo",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    componentes: Mapped[List["EquipoComponente"]] = relationship(
        "EquipoComponente",
        foreign_keys="EquipoComponente.equipo_padre_id",
        back_populates="equipo_padre",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    parte_de: Mapped[List["EquipoComponente"]] = relationship(
        "EquipoComponente",
        foreign_keys="EquipoComponente.equipo_componente_id",
        back_populates="equipo_componente",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    licencias_asignadas_a_equipo: Mapped[List["AsignacionLicencia"]] = relationship(
        "AsignacionLicencia",
        foreign_keys="AsignacionLicencia.equipo_id",
        back_populates="equipo",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    reservas: Mapped[List["ReservaEquipo"]] = relationship(
        "ReservaEquipo",
        back_populates="equipo",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    movimientos_inventario_asociados: Mapped[List["InventarioMovimiento"]] = relationship(
        "InventarioMovimiento",
        back_populates="equipo_asociado",
        lazy="selectin"
    )


    def __repr__(self) -> str:
        return f"<Equipo(id={self.id}, nombre='{self.nombre}', serie='{self.numero_serie}')>"
