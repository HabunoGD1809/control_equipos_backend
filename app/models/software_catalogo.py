import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, String, Text, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .licencia_software import LicenciaSoftware # noqa: F401


class SoftwareCatalogo(Base):
    """
    Modelo ORM para la tabla 'software_catalogo'.
    """
    __tablename__ = "software_catalogo"
    __table_args__ = (
        UniqueConstraint('nombre', 'version', name='uq_software_nombre_version'),
        # {"schema": "control_equipos"}
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fabricante: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categoria: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tipo_licencia: Mapped[str] = mapped_column(String(50))
    metrica_licenciamiento: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relaciones mapeadas ---
    licencias: Mapped[List["LicenciaSoftware"]] = relationship(
        "LicenciaSoftware",
        back_populates="software_info",
        lazy="selectin",
        # Eliminar el parámetro 'cascade=False'
        # cascade=False # <--- CORRECCIÓN: Eliminar esta línea
    )

    def __repr__(self) -> str:
        version_str = f" v{self.version}" if self.version else ""
        return f"<SoftwareCatalogo(id={self.id}, nombre='{self.nombre}{version_str}')>"
