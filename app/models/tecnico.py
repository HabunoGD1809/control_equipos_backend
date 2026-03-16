import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base

if TYPE_CHECKING:
    from .proveedor import Proveedor
    from .mantenimiento import Mantenimiento


class Tecnico(Base):
    """Modelo ORM para la tabla 'tecnicos_mantenimiento'."""
    __tablename__ = "tecnicos_mantenimiento"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    es_externo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=func.false(), nullable=False)
    proveedor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    telefono_contacto: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email_contacto: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=func.true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    proveedor: Mapped[Optional["Proveedor"]] = relationship(
        "Proveedor",
        # Asegúrate de que en models/proveedor.py agregues: tecnicos = relationship("Tecnico", back_populates="proveedor")
        back_populates="tecnicos", 
        lazy="selectin"
    )
    
    mantenimientos: Mapped[List["Mantenimiento"]] = relationship(
        "Mantenimiento",
        back_populates="tecnico",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Tecnico(id={self.id}, nombre='{self.nombre_completo}', externo={self.es_externo})>"
