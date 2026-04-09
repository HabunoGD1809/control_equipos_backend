import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .departamento import Departamento
    from .equipo import Equipo
    from .movimiento import Movimiento
    from .usuario import Usuario

class Empleado(Base):
    """Modelo ORM para el catálogo de Empleados (Custodios de activos)."""
    __tablename__ = "empleados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo: Mapped[str] = mapped_column(String(255), index=True)
    cargo: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    email_corporativo: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    
    # Llave foránea al Departamento
    departamento_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departamentos.id", ondelete="SET NULL"), nullable=True, index=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    departamento_rel: Mapped[Optional["Departamento"]] = relationship("Departamento", lazy="selectin")
    
    # Conexión 1 a 1 con Usuario (Opcional, solo si el empleado tiene acceso al sistema)
    usuario_rel: Mapped[Optional["Usuario"]] = relationship("Usuario", back_populates="empleado_rel", lazy="selectin")
    
    # Activos que tiene asignados actualmente
    equipos_asignados: Mapped[List["Equipo"]] = relationship("Equipo", back_populates="empleado_asignado", lazy="selectin")
    
    # Historial de recepciones
    movimientos_recibidos: Mapped[List["Movimiento"]] = relationship("Movimiento", back_populates="empleado_destino", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Empleado(id={self.id}, nombre='{self.nombre_completo}')>"
