import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Date, Numeric
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .software_catalogo import SoftwareCatalogo
    from .proveedor import Proveedor
    from .asignacion_licencia import AsignacionLicencia
    from .documentacion import Documentacion


class LicenciaSoftware(Base):
    """
    Modelo ORM para la tabla 'licencias_software'.
    """
    __tablename__ = "licencias_software"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    software_catalogo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("software_catalogo.id", ondelete="RESTRICT"), index=True)
    clave_producto: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    fecha_adquisicion: Mapped[date] = mapped_column(Date)
    fecha_expiracion: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    proveedor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    costo_adquisicion: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    numero_orden_compra: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cantidad_total: Mapped[int] = mapped_column(Integer, default=1)
    cantidad_disponible: Mapped[int] = mapped_column(Integer, default=1)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    software_info: Mapped["SoftwareCatalogo"] = relationship(
        "SoftwareCatalogo",
        back_populates="licencias",
        lazy="joined"
    )
    proveedor: Mapped[Optional["Proveedor"]] = relationship(
        "Proveedor",
        back_populates="licencias_adquiridas",
        lazy="selectin"
    )
    asignaciones: Mapped[List["AsignacionLicencia"]] = relationship(
        "AsignacionLicencia",
        back_populates="licencia",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    # --- NUEVA RELACIÓN INVERSA ---
    documentos: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        foreign_keys="Documentacion.licencia_id", # Especificar FK
        back_populates="licencia",
        lazy="selectin",
        cascade="all, delete-orphan" # Opcional
    )
    # ---------------------------

    def __repr__(self) -> str:
        sw_nombre = self.software_info.nombre if hasattr(self, 'software_info') and self.software_info else "N/A"
        return f"<LicenciaSoftware(id={self.id}, sw='{sw_nombre}', disp={self.cantidad_disponible}/{self.cantidad_total})>"
